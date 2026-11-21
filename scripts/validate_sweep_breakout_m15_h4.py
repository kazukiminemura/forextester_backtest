"""Independently replay the frozen Pine sweep-breakout setup and M1 fills."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import struct

from numba import njit
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "sweep_breakout_m15_h4_20261121"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
SPEC = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
PINE = ROOT / "scripts/tradingview/sweep_breakdown_levels_m15.pine"
SYMBOLS = ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF"]


def stamp(text):
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


def iso(value):
    return datetime.fromtimestamp(int(value), timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def load_source(symbol):
    source = Path("C:/ForexTester6/data/History") / symbol / "Bars.dat"
    with source.open("rb") as stream:
        count = struct.unpack("<I", stream.read(4))[0]
    slots = (source.stat().st_size - 4) // 48
    if not 0 < count <= slots:
        raise ValueError(f"Invalid header in {source}")
    raw = np.memmap(source, mode="r", dtype="<f8", offset=4, shape=(count, 6))
    left, right = np.searchsorted(
        raw[:, 0], [stamp("2015-01-01") / 86400 + 25569,
                    stamp("2026-01-01") / 86400 + 25569],
    )
    used = raw[left:right]
    times = np.rint((used[:, 0] - 25569) * 86400).astype(np.int64)
    prices = np.ascontiguousarray(used[:, [1, 3, 4, 2]])
    if (not np.isfinite(prices).all() or np.any(np.diff(times) <= 0)
            or np.any(times % 60) or np.any(prices <= 0)
            or np.any(prices[:, 1] < np.maximum(prices[:, 0], prices[:, 3]))
            or np.any(prices[:, 2] > np.minimum(prices[:, 0], prices[:, 3]))):
        raise ValueError(f"Invalid M1 in {source}")
    manifest = dict(source=str(source), rows=len(times), first=iso(times[0]), last=iso(times[-1]),
                    raw_slice_sha256=sha256(memoryview(used)).hexdigest())
    return times, prices, manifest


def aggregate(times, prices, seconds):
    buckets = times // seconds * seconds
    first = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
    end = np.r_[first[1:], len(times)]
    candles = np.column_stack([
        prices[first, 0], np.maximum.reduceat(prices[:, 1], first),
        np.minimum.reduceat(prices[:, 2], first), prices[end - 1, 3],
    ])
    return buckets[first], first, end, candles


def candidates(candles, side):
    """Keep setup lifecycle independent from the later position occupancy filter."""
    highs, lows, closes = candles[:, 1], candles[:, 2], candles[:, 3]
    pivots = []
    trigger, stop, sweep_bar = None, None, None
    events = []
    sweeps = []
    for bar in range(len(candles)):
        center = bar - 5
        if center >= 5:
            values = highs if side == 1 else lows
            left, right = values[center - 5:center], values[center + 1:bar + 1]
            is_pivot = (values[center] >= left.max() and values[center] > right.max()
                        if side == 1 else
                        values[center] <= left.min() and values[center] < right.min())
            if is_pivot:
                pivots.append((center, values[center]))
        keep, swept_levels = [], []
        for origin, level in pivots:
            swept = (highs[bar] > level and closes[bar] < level if side == 1
                     else lows[bar] < level and closes[bar] > level)
            invalid = side * (closes[bar] - level) > 0
            if swept:
                swept_levels.append(level)
            if not swept and not invalid and bar - origin <= 2000:
                keep.append((origin, level))
        pivots = keep
        if swept_levels:
            trigger = highs[bar] if side == 1 else lows[bar]
            stop = min(swept_levels) if side == 1 else max(swept_levels)
            sweep_bar = bar
            sweeps.append((bar, float(trigger), float(stop)))
        elif trigger is not None and side * (closes[bar] - trigger) > 0:
            if bar + 1 < len(candles):
                events.append((bar, side, float(stop), sweep_bar, float(trigger)))
            trigger, stop, sweep_bar = None, None, None
    return events, sweeps


@njit(cache=True)
def first_exit(prices, entry_index, side, stop, target):
    for minute in range(entry_index, len(prices)):
        opened, high, low, _ = prices[minute]
        if side * (opened - stop) <= 0:
            return minute, opened, 0
        if side * (opened - target) >= 0:
            return minute, target, 1
        stop_hit = low <= stop if side == 1 else high >= stop
        target_hit = high >= target if side == 1 else low <= target
        if stop_hit:
            return minute, stop, 4 if target_hit else 2
        if target_hit:
            return minute, target, 3
    return len(prices) - 1, prices[-1, 3], 5


def replay(symbol, timeframe, times, prices, buckets, first, end, events):
    ledger = []
    last_exit = -1
    pip = .01 if symbol.endswith("JPY") else .0001
    decimals = 3 if symbol.endswith("JPY") else 5
    for bar, side, stop, sweep_bar, trigger in events:
        if end[bar] - 1 < last_exit:
            continue
        entry_index = first[bar + 1]
        entry = float(prices[entry_index, 0])
        risk = side * (entry - stop)
        if risk <= 0:
            continue
        target = round(2 * entry - stop, decimals)
        exit_index, exit_price, reason_code = first_exit(prices, entry_index, side, stop, target)
        last_exit = exit_index
        if times[entry_index] < stamp("2017-01-01"):
            continue
        gross_r = side * (exit_price - entry) / risk
        year = datetime.fromtimestamp(int(times[entry_index]), timezone.utc).year
        phase = "2017-2019" if year < 2020 else "2020-2022" if year < 2023 else "2023-2025"
        reason = ["stop_gap", "target_gap", "stop", "target", "both_stop_first", "period_end"][reason_code]
        ledger.append(dict(symbol=symbol, timeframe=timeframe, side=side, phase=phase,
                           sweep_time=iso(buckets[sweep_bar]), trigger=trigger,
                           signal_time=iso(buckets[bar]), entry_time=iso(times[entry_index]),
                           signal_last_minute=iso(times[end[bar] - 1]),
                           exit_time=iso(times[exit_index]), entry=entry, stop=stop, target=target,
                           exit=float(exit_price), gross_r=gross_r, net_r=gross_r - pip / risk,
                           reason=reason))
    return ledger


def metrics(rows):
    ordered = sorted(rows, key=lambda row: (row["exit_time"], row["symbol"],
                                           row["entry_time"], row["side"]))
    result = dict(trades=len(rows))
    for key in ["gross_r", "net_r"]:
        values = np.array([row[key] for row in ordered])
        wins, losses = values > 1e-10, values < -1e-10
        curve = np.r_[0., values.cumsum()]
        result[key] = dict(wins=int(wins.sum()), breakevens=int((abs(values) <= 1e-10).sum()),
                           win_rate=float(wins.mean()) if len(values) else None,
                           pf_r=float(values[wins].sum() / -values[losses].sum()) if losses.any() else None,
                           mean_r=float(values.mean()) if len(values) else None,
                           total_r=float(values.sum()),
                           max_realized_dd_r=float((np.maximum.accumulate(curve) - curve).max()))
    return result


def compare(rows, research_path, inputs):
    with gzip.open(research_path, "rt", encoding="utf-8-sig", newline="") as stream:
        research = list(csv.DictReader(stream))
    lookup = {"15m": "M15", "4h": "H4"}

    def key(row):
        return (row["symbol"], lookup.get(row["timeframe"], row["timeframe"]),
                int(row["side"]), stamp(row["entry_time"]))

    expected = {key(row): row for row in rows}
    observed = {key(row): row for row in research}
    if len(expected) != len(rows) or len(observed) != len(research):
        raise ValueError("Duplicate trade identity")
    missing = len(expected.keys() - observed.keys())
    extra = len(observed.keys() - expected.keys())
    differences, max_difference = {}, 0.
    for identity in expected.keys() & observed.keys():
        left, right = expected[identity], observed[identity]
        for field in ["phase", "reason"]:
            if left[field] != right[field]:
                differences[field] = differences.get(field, 0) + 1
        for field in ["sweep_time", "signal_time", "signal_last_minute", "exit_time"]:
            if stamp(left[field]) != stamp(right[field]):
                differences[field] = differences.get(field, 0) + 1
        for field in ["entry", "stop", "target", "trigger", "exit", "gross_r", "net_r"]:
            delta = abs(left[field] - float(right[field]))
            max_difference = max(max_difference, delta)
            if delta > 1e-10:
                differences[field] = differences.get(field, 0) + 1
    result_path = research_path.with_name("results.json")
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    manifest_matches = sum(inputs[row["symbol"]]["raw_slice_sha256"] == row["raw_slice_sha256"]
                           for row in result["inputs"])
    comparison = dict(rows=len(rows), missing=missing, extra=extra, differences=differences,
                      max_absolute_difference=max_difference, matching_input_slices=manifest_matches,
                      research_ledger_sha256=sha256(research_path.read_bytes()).hexdigest(),
                      research_results_sha256=sha256(result_path.read_bytes()).hexdigest())
    if missing or extra or differences or manifest_matches != len(SYMBOLS):
        raise ValueError(comparison)
    return comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8-sig"))
    pine_sha = sha256(PINE.read_bytes()).hexdigest()
    if spec["status"] != "SPEC_FROZEN" or pine_sha.upper() not in spec["code_identifier"]:
        raise ValueError("Frozen Pine identification mismatch")
    rows, inputs, events_summary = [], {}, []
    for symbol in SYMBOLS:
        times, prices, inputs[symbol] = load_source(symbol)
        for timeframe, seconds in [("15m", 900), ("4h", 14400)]:
            buckets, first, end, candles = aggregate(times, prices, seconds)
            for side in [-1, 1]:
                events, sweeps = candidates(candles, side)
                subset = replay(symbol, timeframe, times, prices, buckets, first, end, events)
                rows.extend(subset)
                events_summary.append(dict(symbol=symbol, timeframe=timeframe, side=side,
                                           sweeps=len(sweeps), breakout_events=len(events),
                                           metrics=metrics(subset)))
            print(f"Completed independent {symbol} {timeframe}", flush=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = dict(experiment=EXPERIMENT, pine_sha256=pine_sha, inputs=inputs,
                  independent_code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                  records=events_summary,
                  by_timeframe={tf: metrics([r for r in rows if r["timeframe"] == tf]) for tf in ["15m", "4h"]})
    with gzip.open(OUTPUT / "independent_trades.csv.gz", "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if args.compare:
        result["comparison"] = compare(rows, args.compare, inputs)
    (OUTPUT / "independent_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["by_timeframe"]), flush=True)
    print(json.dumps(result.get("comparison", {})), flush=True)


if __name__ == "__main__":
    main()
