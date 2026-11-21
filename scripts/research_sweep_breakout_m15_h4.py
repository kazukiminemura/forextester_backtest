"""Replay the frozen bidirectional sweep-breakout indicator on local M1.

Pine sweep/setup state and the M1 fill model are separate. All state starts
in 2015, and only entries from 2017 onward contribute to reported results.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import gzip
import json
from pathlib import Path
from typing import NamedTuple

import numpy as np

from forextester_backtest.data import HistoryRepository
from scripts.research_dinapoli_3x3_daily import DAY, dump, iso, sha, timestamp
from scripts.research_fx65_pf15 import load_minutes
from scripts.research_luxalgo_sweeps_m15 import bounded_first_exit, confirmed_pivots, summarize


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "sweep_breakout_m15_h4_20261121"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
PROTOCOL = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
PINE = ROOT / "scripts/tradingview/sweep_breakdown_levels_m15.pine"
SYMBOLS = ("USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF")
TIMEFRAMES = {"M15": 900, "H4": 14400}
PHASES = ("2017-2019", "2020-2022", "2023-2025")


@dataclass(frozen=True)
class Candles:
    time: np.ndarray
    first: np.ndarray
    end: np.ndarray
    prices: np.ndarray


class Signal(NamedTuple):
    side: int
    signal_bar: int
    entry_minute: int
    stop: float
    trigger: float
    sweep_bar: int


def aggregate(times, prices, seconds):
    buckets = times // seconds * seconds
    first = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
    end = np.r_[first[1:], len(times)]
    ohlc = np.column_stack((
        prices[first, 0], np.maximum.reduceat(prices[:, 1], first),
        np.minimum.reduceat(prices[:, 2], first), prices[end - 1, 3],
    ))
    return Candles(buckets[first], first, end, ohlc)


def generate_signals(candles):
    """Match both independent written calls to the Pine f_levels function."""
    high, low, close = candles.prices[:, 1], candles.prices[:, 2], candles.prices[:, 3]
    confirmed = {
        1: confirmed_pivots(high, 5, True),
        -1: confirmed_pivots(low, 5, False),
    }
    pivots = {1: [], -1: []}
    setups = {1: None, -1: None}
    signals = []
    counts = Counter()
    for n in range(len(close)):
        for side in (1, -1):
            if np.isfinite(confirmed[side][n]):
                pivots[side].append((n - 5, float(confirmed[side][n])))
            swept_levels = []
            retained = []
            for origin, level in pivots[side]:
                swept = (high[n] > level and close[n] < level) if side == 1 else (
                    low[n] < level and close[n] > level
                )
                invalid = close[n] > level if side == 1 else close[n] < level
                if swept:
                    swept_levels.append(level)
                if not (swept or invalid or n - origin > 2000):
                    retained.append((origin, level))
            pivots[side] = retained
            if swept_levels:
                level = min(swept_levels) if side == 1 else max(swept_levels)
                trigger = high[n] if side == 1 else low[n]
                setups[side] = (float(trigger), level, n)
                counts["long_sweep_bars" if side == 1 else "short_sweep_bars"] += 1
            elif setups[side] is not None:
                trigger, level, sweep_n = setups[side]
                if side * close[n] > side * trigger:
                    counts["long_break_bars" if side == 1 else "short_break_bars"] += 1
                    if n + 1 < len(close):
                        signals.append(Signal(side, n, int(candles.first[n + 1]), level, trigger, sweep_n))
                    else:
                        counts["last_bar_no_next_open"] += 1
                    setups[side] = None
    return signals, dict(counts)


def phase_for(entry_time):
    year = int(iso(entry_time)[:4])
    if year < 2020:
        return PHASES[0]
    if year < 2023:
        return PHASES[1]
    return PHASES[2]


def replay(symbol, timeframe, times, prices, candles, signals, pip, report_start):
    """Replay warmup trades too, retaining one simultaneous position per side."""
    last_exit = {1: -1, -1: -1}
    trades = []
    counts = Counter()
    decimals = int(round(-np.log10(pip))) + 1
    for signal in signals:
        side, n, entry_i, stop, trigger, sweep_n = signal
        if entry_i <= last_exit[side]:
            counts["long_open_skip" if side == 1 else "short_open_skip"] += 1
            continue
        entry = float(prices[entry_i, 0])
        risk = side * (entry - stop)
        if risk <= 0:
            counts["long_invalid_gap" if side == 1 else "short_invalid_gap"] += 1
            continue
        target = round(2. * entry - stop, decimals)
        exit_i, exit_price, reason = bounded_first_exit(
            times, prices, entry_i, len(times), side, stop, target,
        )
        last_exit[side] = exit_i
        if times[entry_i] < report_start:
            counts["warmup_entries"] += 1
            continue
        risk_pips = risk / pip
        gross_pips = side * (exit_price - entry) / pip
        net_pips = gross_pips - 1.
        trades.append(dict(
            symbol=symbol, timeframe=timeframe, side=side, direction="long" if side == 1 else "short",
            phase=phase_for(times[entry_i]), sweep_time=iso(candles.time[sweep_n]),
            signal_time=iso(candles.time[n]), signal_last_minute=iso(times[candles.end[n] - 1]),
            entry_time=iso(times[entry_i]), exit_time=iso(times[exit_i]), entry=entry,
            stop=stop, target=target, trigger=trigger, exit=float(exit_price), risk_pips=risk_pips,
            gross_pips=gross_pips, net_pips=net_pips, gross_r=gross_pips / risk_pips,
            net_r=net_pips / risk_pips, reason=reason,
        ))
    return trades, dict(counts)


def grouped_scores(trades):
    return {
        "all": summarize(trades),
        "long": summarize([t for t in trades if t["side"] == 1]),
        "short": summarize([t for t in trades if t["side"] == -1]),
    }


def self_check():
    # Distinct observed buckets retain their first minute, including gaps.
    times = np.array([60, 120, 960, 14400], dtype=np.int64)
    prices = np.array([[10., 11., 9., 10.], [10., 12., 8., 11.], [11., 13., 10., 12.], [12., 14., 11., 13.]])
    candles = aggregate(times, prices, 900)
    assert candles.time.tolist() == [0, 900, 14400]
    assert candles.first.tolist() == [0, 2, 3]
    assert candles.prices[0].tolist() == [10., 12., 8., 11.]
    # One bullish sweep creates a short only on a later close below its low.
    p = np.tile([100., 102., 99., 100.], (16, 1))
    p[5, 2] = 90.
    p[11] = [100., 102., 89., 100.]
    p[12] = [100., 101., 88., 88.]
    t = np.arange(len(p), dtype=np.int64) * 900
    c = aggregate(t, p, 900)
    signals, _ = generate_signals(c)
    shorts = [s for s in signals if s.side == -1]
    assert shorts == [Signal(-1, 12, 13, 90., 89., 11)]
    # Mirroring all prices mirrors direction and keeps the signal timing.
    mirrored = p.copy()
    mirrored[:, 0], mirrored[:, 3] = 200. - p[:, 0], 200. - p[:, 3]
    mirrored[:, 1], mirrored[:, 2] = 200. - p[:, 2], 200. - p[:, 1]
    mirror_signals, _ = generate_signals(aggregate(t, mirrored, 900))
    assert [s for s in mirror_signals if s.side == 1] == [Signal(1, 12, 13, 110., 111., 11)]
    # A more recent sweep replaces the older trigger before its breakdown.
    replacement = np.tile([100., 102., 99., 100.], (26, 1))
    replacement[5, 2], replacement[11, 2], replacement[14, 2] = 90., 89., 88.
    replacement[20, 2] = 87.
    replacement[21] = [100., 102., 88., 88.]
    replacement[22] = [100., 102., 86., 86.]
    replacement_times = np.arange(26, dtype=np.int64) * 900
    replaced, _ = generate_signals(aggregate(replacement_times, replacement, 900))
    assert [s for s in replaced if s.side == -1] == [Signal(-1, 22, 23, 88., 87., 20)]
    # A simultaneous two-pivot sweep selects the level nearest to the close.
    nearest = np.tile([100., 102., 99., 100.], (24, 1))
    nearest[5, 2], nearest[15, 2], nearest[21, 2] = 90., 92., 89.
    nearest[22] = [100., 102., 88., 88.]
    nearest_times = np.arange(24, dtype=np.int64) * 900
    nearest_signals, _ = generate_signals(aggregate(nearest_times, nearest, 900))
    assert [s for s in nearest_signals if s.side == -1] == [Signal(-1, 22, 23, 92., 89., 21)]
    # Same-minute barrier ambiguity resolves at the stop. Sides are independent.
    fill_prices = np.array([[100., 102., 98., 100.], [100., 100., 100., 100.]])
    fill_times = np.array([0, 60], dtype=np.int64)
    fill_candles = aggregate(fill_times, fill_prices, 60)
    fill_signals = [Signal(1, 0, 0, 99., 101., 0), Signal(-1, 0, 0, 101., 99., 0)]
    trades, _ = replay("TEST", "M15", fill_times, fill_prices, fill_candles, fill_signals, 1., 0)
    assert len(trades) == 2 and all(t["reason"] == "both_stop_first" for t in trades)
    assert all(t["gross_r"] == -1. and t["net_r"] == -2. for t in trades)
    # Warmup entries still block a new entry of that direction.
    quiet = np.array([[100., 100., 100., 100.], [100., 100., 100., 100.]])
    warmup_signals = [Signal(1, 0, 0, 99., 101., 0), Signal(1, 0, 1, 99., 101., 0)]
    trades, skips = replay("TEST", "M15", fill_times, quiet, fill_candles, warmup_signals, 1., 60)
    assert not trades and skips["warmup_entries"] == 1 and skips["long_open_skip"] == 1
    # No three-year boundary resets, and entry determines the reported phase.
    assert phase_for(timestamp("2019-12-31")) == "2017-2019"
    assert phase_for(timestamp("2020-01-01")) == "2020-2022"
    return {"assertions": 12, "status": "passed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    checks = self_check()
    if args.self_check:
        print(json.dumps(checks))
        return
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8-sig"))
    if protocol.get("status") != "SPEC_FROZEN":
        raise ValueError("Frozen protocol required")
    args.output.mkdir(parents=True, exist_ok=True)
    source_pine_sha = sha(PINE)
    repo = HistoryRepository()
    all_trades = []
    inputs = []
    records = []
    start, report_start, end = map(timestamp, ("2015-01-01", "2017-01-01", "2026-01-01"))
    for symbol in args.symbols:
        # Shared load_minutes subtracts 31 days. Compensate to read from 2015.
        times, prices, _, pip, manifest = load_minutes(repo, symbol, start + 31 * DAY, end)
        tick = pip / 10
        manifest["price_tick"] = tick
        manifest["max_off_tick_units"] = float(np.max(abs(prices / tick - np.rint(prices / tick))))
        if manifest["max_off_tick_units"] > 1e-7:
            raise ValueError(f"Prices exceed declared tick grid: {symbol}")
        manifest["symbol"] = symbol
        inputs.append(manifest)
        for timeframe, seconds in TIMEFRAMES.items():
            candles = aggregate(times, prices, seconds)
            signals, signal_counts = generate_signals(candles)
            trades, skips = replay(symbol, timeframe, times, prices, candles, signals, pip, report_start)
            all_trades.extend(trades)
            records.append(dict(
                symbol=symbol, timeframe=timeframe, bars=len(candles.time),
                partial_bars=int(np.count_nonzero(candles.end - candles.first != seconds // 60)),
                signal_counts_including_warmup=signal_counts, execution_counts_including_warmup=skips,
                metrics=grouped_scores(trades),
            ))
            print(f"Completed {symbol} {timeframe}: {len(trades)} trades", flush=True)
    if sha(PINE) != source_pine_sha:
        raise ValueError("Pine source changed during research")
    all_trades.sort(key=lambda t: (t["exit_time"], t["timeframe"], t["symbol"], t["side"], t["entry_time"]))
    with gzip.open(args.output / "trades.csv.gz", "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_trades[0]) if all_trades else [])
        writer.writeheader()
        writer.writerows(all_trades)
    by_timeframe = {}
    for timeframe in TIMEFRAMES:
        subset = [t for t in all_trades if t["timeframe"] == timeframe]
        by_timeframe[timeframe] = {
            **grouped_scores(subset),
            "by_phase": {phase: grouped_scores([t for t in subset if t["phase"] == phase]) for phase in PHASES},
            "by_symbol": {symbol: grouped_scores([t for t in subset if t["symbol"] == symbol]) for symbol in args.symbols},
            "excluding_usdchf": grouped_scores([t for t in subset if t["symbol"] != "USDCHF"]),
        }
    dependencies = (
        "scripts/research_luxalgo_sweeps_m15.py", "scripts/research_fx65_pf15.py",
        "scripts/research_dinapoli_3x3_daily.py", "src/forextester_backtest/data.py",
    )
    result = dict(
        experiment=EXPERIMENT, implementation_sha256=sha(Path(__file__)),
        protocol_sha256=sha(PROTOCOL), pine_sha256=source_pine_sha,
        dependencies_sha256={path: sha(ROOT / path) for path in dependencies},
        self_check=checks, inputs=inputs, records=records, by_timeframe=by_timeframe,
        configuration=dict(
            state_start="2015-01-01", reported_entry_start="2017-01-01", end_exclusive="2026-01-01",
            anchor="naive saved timestamp midnight", nonempty_buckets=True,
            reset_at_period_boundaries=False, independent_long_and_short=True,
            costs_roundtrip_pips=1., breakeven_tolerance_r=1e-10,
        ),
    )
    dump(args.output / "results.json", result)
    print("RESULT_JSON=" + str(args.output / "results.json"), flush=True)


if __name__ == "__main__":
    main()
