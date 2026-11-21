"""Fixed H1 FX hypotheses, replayed on local Forex Tester M1 data."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
from typing import NamedTuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from forextester_backtest.data import BAR_STRUCT, HistoryRepository, _RecordFile
from scripts.research_dinapoli_3x3_daily import DAY, OLE_UNIX_DAYS, dump, iso, sha, timestamp


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "fx65_pf15_20261115"
SPEC = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
HOUR = 3600
LOOKBACK = 20
PHASES = ("training", "validation", "final_confirmation")


class Candidate(NamedTuple):
    id: str
    family: str
    threshold: float
    risk_atr: float


class Trade(NamedTuple):
    symbol: str
    signal_time: int
    entry_time: int
    exit_time: int
    side: int
    entry: float
    stop: float
    target: float
    exit: float
    net_r: float
    reason: str


def load_minutes(repo, symbol, start, end):
    path = repo.root / symbol / "Bars.dat"
    metadata_path = path.with_name("info.dat")
    before = path.stat()
    metadata_before = sha(metadata_path)
    metadata = repo.metadata(symbol)
    if metadata.commission_per_lot or any(float(metadata.values[key]) for key in ("SwapLong", "SwapShort")):
        raise ValueError(f"{symbol}: nonzero commission or swap")
    count = _RecordFile(path, BAR_STRUCT.size).count()
    raw = np.memmap(path, mode="r", dtype="<f8", offset=4, shape=(count, 6))
    bounds = [(start - 31 * DAY) / DAY + OLE_UNIX_DAYS, end / DAY + OLE_UNIX_DAYS]
    left, right = np.searchsorted(raw[:, 0], bounds, side="left")
    used = raw[left:right]
    seconds = (used[:, 0] - OLE_UNIX_DAYS) * DAY
    times = np.rint(seconds).astype(np.int64)
    prices = np.asarray(used[:, [1, 3, 4, 2]])
    if (
        not len(times) or not np.isfinite(used[:, :5]).all() or np.any(abs(seconds - times) > .001)
        or np.any(np.diff(times) <= 0) or np.any(times % 60) or np.any(prices <= 0)
        or np.any(prices[:, 1] < np.maximum(prices[:, 0], prices[:, 3]))
        or np.any(prices[:, 2] > np.minimum(prices[:, 0], prices[:, 3]))
    ):
        raise ValueError(f"{symbol}: invalid source M1 times or OHLC")
    ratio = prices[1:, 3] / prices[:-1, 3]
    if np.any((ratio < .5) | (ratio > 1.5)):
        raise ValueError(f"{symbol}: unresolved source price-scale discontinuity")
    digest = sha256(memoryview(used)).hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or sha(metadata_path) != metadata_before:
        raise ValueError(f"{symbol}: source changed during read")
    pip = .01 if symbol.endswith("JPY") else .0001
    inputs = dict(
        source=str(path), size=before.st_size, mtime_ns=before.st_mtime_ns, raw_slice_sha256=digest,
        metadata_sha256=metadata_before, record_start=int(left), record_end_exclusive=int(right),
        first=iso(times[0]), last=iso(times[-1]), rows=len(times), metadata_spread_pips=metadata.spread_price / pip,
    )
    return times, prices, metadata.spread_price, pip, inputs


def h1_features(times, prices):
    hours = times // HOUR * HOUR
    starts = np.r_[0, np.flatnonzero(np.diff(hours)) + 1]
    ends = np.r_[starts[1:], len(times)]
    complete = ends - starts == 60
    ready = hours[starts[complete]] + HOUR
    o, h, l, c = (prices[starts, 0][complete], np.maximum.reduceat(prices[:, 1], starts)[complete],
                  np.minimum.reduceat(prices[:, 2], starts)[complete], prices[ends-1, 3][complete])
    if len(ready) < LOOKBACK + 2:
        raise ValueError("Insufficient complete hour history")
    true_range = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    # Row 21 is the first signal with 20 prior true ranges and their previous close.
    atr = sliding_window_view(true_range, LOOKBACK)[:-1].mean(axis=1)
    prior_low = sliding_window_view(l[1:], LOOKBACK)[:-1].min(axis=1)
    prior_high = sliding_window_view(h[1:], LOOKBACK)[:-1].max(axis=1)
    prior_mean = sliding_window_view(c[1:], LOOKBACK)[:-1].mean(axis=1)
    n = LOOKBACK + 1
    return (ready[n:], o[n:], h[n:], l[n:], c[n:], atr, prior_low, prior_high, prior_mean), int(complete.sum()), int((~complete).sum())


def signals(features, candidate):
    ready, o, h, l, c, atr, prior_low, prior_high, mean = features
    offset = candidate.threshold * atr
    if candidate.family == "baseline":
        buy, sell = c < o, c > o
    elif candidate.family == "sweep":
        buy = (l <= prior_low - offset) & (c >= prior_low + .10 * atr) & (c > o)
        sell = (h >= prior_high + offset) & (c <= prior_high - .10 * atr) & (c < o)
    else:
        width = h - l
        buy = (width > 0) & (l <= mean - offset) & (c >= l + .65 * width)
        sell = (width > 0) & (h >= mean + offset) & (c <= h - .65 * width)
    mask = (buy ^ sell) & (atr > 0)
    return ready[mask], np.where(buy[mask], 1, -1), atr[mask] * candidate.risk_atr


def first_exit(times, prices, entry_index, expires_index, side, stop, target, spread):
    # Convert each side to a coordinate where favorable means increasing.
    ask = spread if side == -1 else 0
    stop_level, target_level = side * stop, side * target
    adverse_col, favorable_col = (2, 1) if side == 1 else (1, 2)
    bars = prices[entry_index:expires_index]
    adverse = side * (bars[:, adverse_col] + ask) <= stop_level
    favorable = side * (bars[:, favorable_col] + ask) >= target_level
    hits = np.flatnonzero(adverse | favorable)
    if len(hits):
        offset = hits[0]
        i = entry_index + offset
        opening = prices[i, 0] + ask
        if side * opening <= stop_level:
            return i, opening, "stop_gap"
        if side * opening >= target_level:
            return i, target, "target_gap"
        if adverse[offset]:
            return i, stop, "both_stop_first" if favorable[offset] else "stop"
        return i, target, "target"
    if expires_index == len(times):
        return len(times) - 1, prices[-1, 3] + ask, "period_end"
    opening = prices[expires_index, 0] + ask
    reason = "stop_gap" if side * opening <= stop_level else "timeout"
    return expires_index, opening, reason


def replay(symbol, times, prices, signal_rows, start, end, hold, spread, slip):
    ready, sides, risks = signal_rows
    valid = (ready >= start) & (ready <= end - hold)
    ready, sides, risks = ready[valid], sides[valid], risks[valid]
    indices = np.searchsorted(times, ready)
    trades = []
    last_exit = -1
    for ready_at, side, risk, entry_i in zip(ready, sides, risks, indices):
        if entry_i <= last_exit or entry_i == len(times):
            continue
        entry_at = times[entry_i]
        if entry_at - ready_at > 60 or entry_at > end - hold:
            continue
        entry = prices[entry_i, 0] + (spread if side == 1 else 0) + side * slip
        stop, target = entry - side * risk, entry + side * risk
        expiry = int(np.searchsorted(times, entry_at + hold))
        exit_i, quote, reason = first_exit(times, prices, entry_i, expiry, side, stop, target, spread)
        exit_fill = quote - side * slip
        net_r = side * (exit_fill - entry) / risk
        trades.append(Trade(symbol, int(ready_at), int(entry_at), int(times[exit_i]), int(side),
                            float(entry), float(stop), float(target), float(exit_fill), float(net_r), reason))
        last_exit = exit_i
    return trades


def metrics(trades):
    rows = sorted(trades, key=lambda trade: (trade.exit_time, trade.symbol, trade.entry_time))
    values = np.asarray([row.net_r for row in rows], dtype=float)
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    wins = int((values > 0).sum())
    if len(rows):
        exits = np.asarray([trade.exit_time for trade in rows])
        buckets = np.r_[0, np.flatnonzero(np.diff(exits)) + 1]
        equity = np.r_[0., np.add.reduceat(values, buckets).cumsum()]
    else:
        equity = np.array([0.])
    return dict(
        trades=len(rows), wins=wins, losses=int((values < 0).sum()), flat=int((values == 0).sum()),
        win_rate=wins / len(rows) if len(rows) else 0., pf_r=gains / losses if losses else None,
        gains_r=gains, losses_r=losses, net_r=gains - losses,
        expectancy_r=(gains - losses) / len(rows) if len(rows) else None,
        max_drawdown_r=float((np.maximum.accumulate(equity) - equity).max()),
        exit_reasons=dict(Counter(trade.reason for trade in rows)),
    )


def candidate_grid(protocol):
    base = protocol["baseline"]
    grid = [Candidate(base["id"], "baseline", 0., base["risk_atr"])]
    for family, spec in protocol["search_space"].items():
        key = "overshoot_atr" if family == "sweep" else "distance_atr"
        for threshold in spec[key]:
            for risk in spec["risk_atr"]:
                grid.append(Candidate(f"{family}_{threshold:g}_r{risk:g}", family, threshold, risk))
    if len(grid) != protocol["candidate_budget"] + 1 or len({candidate.id for candidate in grid}) != len(grid):
        raise ValueError("Grid differs from the frozen candidate budget")
    return grid


def score(per_symbol, gates, cost):
    pooled = metrics([trade for trades in per_symbol.values() for trade in trades])
    by_symbol = {symbol: metrics(trades) for symbol, trades in per_symbol.items()}
    profitable = sum(row["trades"] >= gates["minimum_trades_per_profitable_symbol"] and row["net_r"] > 0
                     for row in by_symbol.values())
    limits = gates[cost]
    checks = {
        "trades": pooled["trades"] >= gates["minimum_trades_per_phase_per_cost_model"],
        "win_rate": pooled["win_rate"] >= limits.get("minimum_win_rate", 0),
        "pf_r": pooled["gains_r"] > 0 and (pooled["pf_r"] is None or pooled["pf_r"] >= limits["minimum_pf_r"]),
        "drawdown": pooled["max_drawdown_r"] <= limits["maximum_drawdown_r"],
        "profitable_symbols": profitable >= gates["minimum_profitable_symbols_per_cost_model"],
    }
    return dict(pooled=pooled, by_symbol=by_symbol, profitable_symbols=profitable, checks=checks)


def ranks(results, minimum_trades):
    def normal(row):
        return row["costs"]["normal"]["pooled"]

    def pf(row):
        return row["pf_r"] if row["pf_r"] is not None else float("inf") if row["gains_r"] else 0.

    candidates = [row for row in results if row["candidate"]["family"] != "baseline"]
    eligible = [row for row in candidates if row["passes"]]
    eligible.sort(key=lambda row: (-pf(row["costs"]["stress"]["pooled"]), -pf(normal(row)),
                                   -normal(row)["trades"], row["candidate"]["id"]))
    descriptive = [row for row in candidates if normal(row)["trades"] >= minimum_trades]
    descriptive.sort(key=lambda row: (-min(normal(row)["win_rate"] / .65, pf(normal(row)) / 1.5),
                                      -pf(normal(row)), -normal(row)["trades"], row["candidate"]["id"]))
    return (eligible[0]["candidate"]["id"] if eligible else None,
            descriptive[0]["candidate"]["id"] if descriptive else None)


def evaluate(phase, history, output):
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    if protocol["status"] != "FROZEN" or not protocol["frozen_at"]:
        raise ValueError("Protocol must be frozen before scoring")
    identity = {
        "protocol_sha256": sha(SPEC), "runner_sha256": sha(Path(__file__)),
        "time_helper_sha256": sha(ROOT / "scripts/research_dinapoli_3x3_daily.py"),
        "data_helper_sha256": sha(ROOT / "src/forextester_backtest/data.py"),
    }
    grid = candidate_grid(protocol)
    previous_results_sha256 = None
    if phase != "training":
        previous_phase = PHASES[PHASES.index(phase) - 1]
        previous_path = output / f"{previous_phase}_results.json"
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        selected = previous["selected"]
        if not selected or previous["phase"] != previous_phase or previous["identity"] != identity:
            raise ValueError(f"No hash-matched winner from {previous_phase}; {phase} cannot run")
        grid = [candidate for candidate in grid if candidate.family == "baseline" or candidate.id == selected]
        if len(grid) != 2:
            raise ValueError("Selected candidate is not on the frozen grid")
        previous_results_sha256 = sha(previous_path)
    start, end = map(timestamp, protocol["periods"][phase])
    costs = {name: protocol["cost_and_fill_model"][name] for name in ("normal", "stress")}
    hold = HOUR * protocol["exit_rules"]["max_holding_hours"]
    repo = HistoryRepository(history)
    inputs = {}
    ledgers = {(candidate.id, name): {} for candidate in grid for name in costs}
    for symbol in protocol["symbols"]:
        times, prices, spread, pip, inputs[symbol] = load_minutes(repo, symbol, start, end)
        features, full, partial = h1_features(times, prices)
        inputs[symbol].update(full_h1=full, partial_h1=partial)
        for candidate in grid:
            signal_rows = signals(features, candidate)
            for name, model in costs.items():
                ledgers[candidate.id, name][symbol] = replay(symbol, times, prices, signal_rows, start, end, hold,
                                                           spread * model["spread_multiplier"],
                                                           model["slippage_pips_per_fill"] * pip)
        print(f"{phase} {symbol}: {len(times):,} M1, {full:,} complete H1", flush=True)
    results = []
    gates = protocol["acceptance_gates"]
    for candidate in grid:
        evaluated = {name: score(ledgers[candidate.id, name], gates, name) for name in costs}
        results.append(dict(candidate=candidate._asdict(), costs=evaluated,
                            passes=all(all(result["checks"].values()) for result in evaluated.values())))
    selected, descriptive = ranks(results, gates["minimum_trades_per_phase_per_cost_model"])
    output.mkdir(parents=True, exist_ok=True)
    ledger_path = output / f"{phase}_trades.csv.gz"
    with gzip.open(ledger_path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("candidate", "cost", *Trade._fields))
        for (candidate, cost), per_symbol in ledgers.items():
            for trades in per_symbol.values():
                writer.writerows((candidate, cost, *trade) for trade in trades)
    report = dict(phase=phase, identity=identity, previous_results_sha256=previous_results_sha256,
                  period=protocol["periods"][phase], inputs=inputs,
                  selected=selected, best_descriptive=descriptive, candidates=results,
                  ledger=ledger_path.name, ledger_sha256=sha(ledger_path))
    dump(output / f"{phase}_results.json", report)
    print(f"{phase}: selection={selected!r}, strongest descriptive={descriptive!r}", flush=True)


def self_check():
    times = np.array([0, 60])
    prices = np.array([[100., 102., 98., 100.], [96., 98., 95., 96.]])
    assert first_exit(times, prices, 0, 2, 1, 99., 101., 0.) == (0, 99., "both_stop_first")
    assert first_exit(times, prices, 0, 2, -1, 101.5, 99.5, .5) == (0, 101.5, "both_stop_first")
    assert first_exit(times, prices, 1, 1, 1, 99., 101., 0.) == (1, 96., "stop_gap")
    assert first_exit(times, prices, 1, 2, -1, 100., 97., .5) == (1, 97., "target_gap")
    assert first_exit(times, prices, 0, 1, 1, 90., 110., 0.) == (1, 96., "timeout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=(*PHASES, "self_check"))
    parser.add_argument("--history")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    self_check()
    if args.phase != "self_check":
        protocol = json.loads(SPEC.read_text(encoding="utf-8"))
        evaluate(args.phase, args.history or protocol["history_directory"], args.output)


if __name__ == "__main__":
    main()
