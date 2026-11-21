"""Descriptive RR1 replay of LuxAlgo's default Only Wicks liquidity sweeps.

The indicator determines signals. Entries, exits and costs are the separately
frozen research contract. Source is credited to LuxAlgo, CC BY-NC-SA 4.0.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from forextester_backtest.data import HistoryRepository
from scripts.research_dinapoli_3x3_daily import DAY, dump, iso, sha, timestamp
from scripts.research_fx65_pf15 import first_exit, load_minutes


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "luxalgo_sweeps_m15_20261120"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
SOURCE_URL = (
    "https://indie-script.github.io/indicators/Liquidity%20Sweeps/"
    "Liquidity%20Sweeps.pinescript5"
)
PHASES = (
    ("2017-2019", "2017-01-01", "2020-01-01"),
    ("2020-2022", "2020-01-01", "2023-01-01"),
    ("2023-2025", "2023-01-01", "2026-01-01"),
)
SYMBOLS = ("USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF")


@dataclass(frozen=True)
class Candles:
    time: np.ndarray
    first: np.ndarray
    prices: np.ndarray
    complete: np.ndarray


def aggregate_m15(times, prices):
    buckets = times // 900 * 900
    starts = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
    ends = np.r_[starts[1:], len(times)]
    complete = (ends - starts == 15) & (times[starts] == buckets[starts])
    candles = np.column_stack((
        prices[starts, 0], np.maximum.reduceat(prices[:, 1], starts),
        np.minimum.reduceat(prices[:, 2], starts), prices[ends - 1, 3],
    ))
    return Candles(buckets[starts], times[starts], candles, complete)


def confirmed_pivots(values, length, high):
    """Pine chooses the most recent equal extreme in the centered window."""
    windows = sliding_window_view(values, 2 * length + 1)
    centers = windows[:, length]
    if high:
        matches = (centers >= windows[:, :length].max(axis=1)) & (
            centers > windows[:, length + 1:].max(axis=1)
        )
    else:
        matches = (centers <= windows[:, :length].min(axis=1)) & (
            centers < windows[:, length + 1:].min(axis=1)
        )
    confirmed = np.full(len(values), np.nan)
    confirmed[2 * length:] = np.where(matches, centers, np.nan)
    return confirmed


def wick_signals(candles, length=5):
    """Process newly confirmed pivots before sweeps, then expire old pivots."""
    highs, lows, closes = candles.prices[:, 1], candles.prices[:, 2], candles.prices[:, 3]
    ph = confirmed_pivots(highs, length, True)
    pl = confirmed_pivots(lows, length, False)
    # A taken wick never signals again in Only Wicks mode. Removing it early
    # preserves all signal events while avoiding drawing-only lifecycle state.
    pivots = {1: [], -1: []}
    signals = []
    counts = Counter()
    for n in range(len(closes)):
        if np.isfinite(ph[n]):
            pivots[-1].append((n - length, ph[n]))
        if np.isfinite(pl[n]):
            pivots[1].append((n - length, pl[n]))
        directions = []
        for side in (1, -1):
            keep = []
            for pivot_i, level in pivots[side]:
                mitigated = side * closes[n] < side * level
                swept = (
                    lows[n] < level and closes[n] > level if side == 1
                    else highs[n] > level and closes[n] < level
                )
                if swept:
                    directions.append(side)
                    counts["bullish_levels" if side == 1 else "bearish_levels"] += 1
                if not mitigated and not swept and n - pivot_i <= 2000:
                    keep.append((pivot_i, level))
            pivots[side] = keep
        if not directions:
            continue
        counts["event_bars"] += 1
        if len(set(directions)) == 2:
            counts["both_direction_bars"] += 1
            continue
        if n + 1 == len(closes):
            counts["no_next_bar"] += 1
            continue
        side = directions[0]
        stop = lows[n] if side == 1 else highs[n]
        signals.append((int(candles.first[n + 1]), side, float(stop), int(candles.time[n])))
    return signals, dict(counts)


def bounded_first_exit(times, prices, entry_i, end_i, side, stop, target):
    """Find the first hit in bounded chunks, reusing the common fill rules."""
    for left in range(entry_i, end_i, 2048):
        right = min(left + 2048, end_i)
        bars = prices[left:right]
        adverse = bars[:, 2] <= stop if side == 1 else bars[:, 1] >= stop
        favorable = bars[:, 1] >= target if side == 1 else bars[:, 2] <= target
        if np.any(adverse | favorable) or right == end_i:
            index, quote, reason = first_exit(
                times[left:right], bars, 0, right - left, side, stop, target, 0.,
            )
            return left + index, quote, reason
    raise ValueError("Empty execution interval")


def replay(symbol, times, prices, signals, start, end, pip, cost_pips=1.0):
    """One position per symbol. Costs affect net P/L after price-path execution."""
    trades = []
    skips = Counter()
    last_exit = -1
    end_i = int(np.searchsorted(times, end))
    for ready_at, side, stop, signal_at in signals:
        if not start <= signal_at < end or not start <= ready_at < end:
            continue
        entry_i = int(np.searchsorted(times, ready_at))
        if entry_i >= end_i or times[entry_i] != ready_at:
            skips["missing_exact_entry"] += 1
            continue
        if entry_i <= last_exit:
            skips["position_open"] += 1
            continue
        entry = float(prices[entry_i, 0])
        risk = side * (entry - stop)
        if risk <= 0:
            skips["invalid_stop"] += 1
            continue
        # All observed source prices lie on pip/10. Round arithmetic back to
        # that lattice so an exact quoted target touch is executable.
        decimals = int(round(-np.log10(pip))) + 1
        target = round(entry + side * risk, decimals)
        exit_i, exit_price, reason = bounded_first_exit(
            times, prices, entry_i, end_i, side, stop, target,
        )
        gross_pips = side * (exit_price - entry) / pip
        net_pips = gross_pips - cost_pips
        risk_pips = risk / pip
        trades.append(dict(
            symbol=symbol, signal_time=iso(signal_at), entry_time=iso(ready_at),
            exit_time=iso(times[exit_i]), side=side, entry=entry, stop=stop, target=target,
            exit=float(exit_price), risk_pips=risk_pips, gross_pips=gross_pips,
            net_pips=net_pips, gross_r=gross_pips / risk_pips, net_r=net_pips / risk_pips,
            reason=reason,
        ))
        last_exit = exit_i
    return trades, dict(skips)


def summarize(trades):
    result = dict(trades=len(trades), exit_reasons=dict(Counter(t["reason"] for t in trades)))
    for prefix in ("gross", "net"):
        values = np.array([t[f"{prefix}_r"] for t in trades])
        positive = values[values > 1e-10].sum()
        negative = -values[values < -1e-10].sum()
        wins = int((values > 1e-10).sum())
        breakevens = int((abs(values) <= 1e-10).sum())
        curve = np.r_[0.0, values.cumsum()]
        result[prefix] = dict(
            wins=wins, losses=len(values) - wins - breakevens, breakevens=breakevens,
            win_rate=wins / len(values) if len(values) else None,
            win_rate_including_breakevens=(wins + breakevens) / len(values) if len(values) else None,
            pf_r=float(positive / negative) if negative else None,
            total_r=float(values.sum()), mean_r=float(values.mean()) if len(values) else None,
            max_realized_dd_r=float((np.maximum.accumulate(curve) - curve).max()),
            total_pips=float(sum(t[f"{prefix}_pips"] for t in trades)),
        )
    return result


def self_check():
    # Flat/equal pivots choose the latest tie, with the full right-side delay.
    values = np.array([1., 2., 5., 5., 2., 1.])
    pivots = confirmed_pivots(values, 2, True)
    assert np.isnan(pivots[:5]).all() and pivots[5] == 5
    t = np.arange(30, dtype=np.int64) * 60
    p = np.tile([100., 102., 98., 100.], (30, 1))
    candles = aggregate_m15(t, p)
    assert len(candles.time) == 2 and candles.complete.all()
    # Same M1 touches both thresholds. The stop wins the ambiguity.
    trades, _ = replay("TEST", t, p, [(0, 1, 99., 0)], 0, 1800, 1.)
    assert len(trades) == 1 and trades[0]["reason"] == "both_stop_first"
    assert trades[0]["gross_r"] == -1 and trades[0]["net_r"] == -2
    # A stop gap fills at the observed open. A favorable gap fills at the limit.
    gap = p[:2].copy()
    gap[0] = [100., 100., 100., 100.]
    gap[1] = [98., 98., 98., 98.]
    assert first_exit(t[:2], gap, 0, 2, 1, 99., 101., 0.)[1:] == (98., "stop_gap")
    gap[1] = [102., 102., 102., 102.]
    assert first_exit(t[:2], gap, 0, 2, 1, 99., 101., 0.)[1:] == (101., "target_gap")
    # Invalid stop due to the next open is rejected. Missing exact entry is rejected.
    assert replay("TEST", t, p, [(0, 1, 101., 0)], 0, 1800, 1.)[1] == {"invalid_stop": 1}
    assert replay("TEST", t, p, [(1, 1, 99., 0)], 0, 1800, 1.)[1] == {"missing_exact_entry": 1}
    # Confirm a swing only after five right bars and allow its first wick once.
    signal_prices = np.tile([100., 102., 99., 100.], (16, 1))
    signal_prices[5, 1] = 110.
    signal_prices[11, 1], signal_prices[12, 1] = 111., 112.
    signal_times = np.arange(16) * 900
    events, _ = wick_signals(Candles(signal_times, signal_times, signal_prices, np.ones(16, dtype=bool)))
    assert events == [(10800, -1, 111., 9900)]
    # Decimal TP calculation must execute on an equal source quote.
    decimal_prices = np.array([[1.23002, 1.23009, 1.23002, 1.23009]])
    decimal_trade, _ = replay("TEST", np.array([0]), decimal_prices, [(0, 1, 1.22995, 0)], 0, 60, .0001)
    assert decimal_trade[0]["reason"] == "target"
    return {"assertions": 10, "status": "passed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    checks = self_check()
    if args.self_check:
        print(json.dumps(checks))
        return
    spec = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
    if not spec.exists():
        raise ValueError("Frozen protocol.json required before research execution")
    args.output.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(SOURCE_URL) as response:
        source_sha = hashlib.sha256(response.read()).hexdigest()
    repo = HistoryRepository()
    all_trades = []
    records = []
    for symbol in args.symbols:
        for phase, begin, finish in PHASES:
            start, end = timestamp(begin), timestamp(finish)
            # The shared loader adds 31 calendar days. Another 29 yields 60.
            times, prices, _, pip, inputs = load_minutes(repo, symbol, start - 29 * DAY, end)
            tick = pip / 10
            max_off_tick = float(np.max(abs(prices / tick - np.rint(prices / tick))))
            if max_off_tick > 1e-7:
                raise ValueError(f"Source price exceeds assumed precision: {symbol}")
            inputs["price_tick"] = tick
            inputs["max_off_tick_units"] = max_off_tick
            candles = aggregate_m15(times, prices)
            if (candles.time < start).sum() < 2006:
                raise ValueError(f"Insufficient pivot warmup: {symbol}/{phase}")
            signals, signal_counts = wick_signals(candles)
            trades, skips = replay(symbol, times, prices, signals, start, end, pip)
            for trade in trades:
                trade["phase"] = phase
            all_trades.extend(trades)
            records.append(dict(
                symbol=symbol, phase=phase, inputs=inputs,
                m15_bars=len(candles.time), incomplete_m15_bars=int((~candles.complete).sum()),
                signal_counts_including_warmup=signal_counts, skips=skips, metrics=summarize(trades),
            ))
            print(f"Completed {symbol} {phase}: {len(trades)} trades", flush=True)
    all_trades.sort(key=lambda t: (t["exit_time"], t["symbol"], t["entry_time"]))
    with gzip.open(args.output / "trades.csv.gz", "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_trades[0]) if all_trades else [])
        writer.writeheader()
        writer.writerows(all_trades)
    results = dict(
        experiment=EXPERIMENT, implementation_sha256=sha(Path(__file__)),
        protocol_sha256=sha(spec), source_url=SOURCE_URL, source_sha256=source_sha,
        dependencies_sha256={path: sha(ROOT / path) for path in (
            "scripts/research_fx65_pf15.py", "scripts/research_dinapoli_3x3_daily.py",
            "src/forextester_backtest/data.py",
        )},
        self_check=checks, configuration=dict(
            timeframe="15m", swing_length=5, mode="Only Wicks", rr=1., cost_pips=1.,
            incomplete_policy="all nonempty observed M15 buckets retained",
            entry_policy="first observed M1 in next nonempty M15 bucket",
            warmup_calendar_days=60,
        ), records=records, overall=summarize(all_trades),
        by_phase={phase: summarize([t for t in all_trades if t["phase"] == phase]) for phase, _, _ in PHASES},
        by_symbol={symbol: summarize([t for t in all_trades if t["symbol"] == symbol]) for symbol in args.symbols},
    )
    dump(args.output / "results.json", results)
    print("RESULT_JSON=" + str(args.output / "results.json"), flush=True)


if __name__ == "__main__":
    main()
