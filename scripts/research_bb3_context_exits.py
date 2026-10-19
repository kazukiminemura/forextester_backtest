"""Frozen 19-case stop/target study. Not a broker emulator/adoption approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from numba import njit

from scripts.research_bb3_context_timing import (ROOT, TRADE_COLUMNS as BASE_COLUMNS,
    aggregate, dump, eligible_train, gate, simulate, stats, timestamp)

SPEC = ROOT / "docs/quant_organization/experiments/bb3_context_exits_20260909/protocol.json"
CACHE = ROOT / "agent_runs/bb3_context_timing_20260909/completed"
OUT = ROOT / "agent_runs/bb3_context_exits_20260909"
TRADE_COLUMNS = BASE_COLUMNS + ["stop", "initial_target", "risk_price", "signal_prior_atr", "entry_kind", "stopped"]


@njit(cache=True)
def risk_distance(stop_mode, pip, signal_atr, tick):
    raw = 5 * pip if stop_mode == 1 else 10 * pip if stop_mode == 2 else 1.5 * signal_atr
    return max(1, math.ceil(raw / tick)) * tick


@njit(cache=True)
def fixed_target(entry, side, risk, rr, tick):
    risk_ticks = round(risk / tick)
    return entry + side * max(1, math.ceil(risk_ticks * rr)) * tick


@njit(cache=True)
def bracket_fill(side, op, hi, lo, target, stop, suppress_target=False):
    gap_stop = op <= stop if side == 1 else op >= stop
    gap_target = op >= target if side == 1 else op <= target
    hit_stop = lo <= stop if side == 1 else hi >= stop
    hit_target = hi >= target if side == 1 else lo <= target
    if gap_stop:
        return op, True, hit_stop and hit_target
    if not suppress_target and gap_target:
        return op, False, hit_stop and hit_target
    if hit_stop:
        return stop, True, hit_stop and hit_target
    if not suppress_target and hit_target:
        return target, False, hit_stop and hit_target
    return np.nan, False, hit_stop and hit_target


@njit(cache=True)
def simulate_exits(f, times, start, end, pip, cost, tick, limit_entry, stop_mode, rr):
    """rr=0 moving SMA; 1.3/1.5 fixed reward. entry_kind:0market,1limit-open,2limit-touch.
    Trade columns: original 9 + stop, initialTP, risk, signalATR, entrykind, stopped.
    Diagnostics original10 + ambiguous entry, canceled orders, openfills,
    touchfills, dualtouch bars, active stop/risk/initialTP/signalATR/entrykind.
    """
    trades = np.empty((len(f), 15))
    count = 0
    side = pending = armed = 0
    prep = signal = entry_i = -1
    entry = target = limit = stop = initial_target = risk = signal_atr = np.nan
    entry_kind = 0
    prep_count = signal_count = ambiguous_count = cancel_count = open_fills = touch_fills = dual_count = 0
    realized = peak = dd = 0.0
    last_close = np.nan
    for i in range(len(f)):
        if times[i] < start or times[i] >= end:
            continue
        op, hi, lo, cl, mid, upper, lower = f[i, :7]
        last_close = cl
        handled = suppress_target = new_entry = False
        if side == 0 and pending != 0 and i > signal:
            if not limit_entry:
                side, pending, entry, entry_i = pending, 0, op, i
                new_entry, entry_kind = True, 0
                open_fills += 1
            else:
                center_open = op >= target if pending == 1 else op <= target
                center_hit = hi >= target if pending == 1 else lo <= target
                limit_open = op <= limit if pending == 1 else op >= limit
                limit_hit = lo <= limit if pending == 1 else hi >= limit
                if center_open:
                    pending, handled = 0, True
                    cancel_count += 1
                elif limit_open or limit_hit:
                    side, pending = pending, 0
                    entry, entry_i = (op if limit_open else limit), i
                    new_entry, suppress_target = True, not limit_open
                    entry_kind = 1 if limit_open else 2
                    if limit_open:
                        open_fills += 1
                    else:
                        touch_fills += 1
                elif center_hit:
                    pending, handled = 0, True
                    cancel_count += 1
                else:
                    explained = f[i, 10] if pending == 1 else f[i, 11]
                    wick = f[i, 12] if pending == 1 else f[i, 13]
                    center_passed = cl >= mid if pending == 1 else cl <= mid
                    opposite = hi >= upper if pending == 1 else lo <= lower
                    if i - signal >= 3 or explained != 0 or wick != 0 or center_passed or opposite or f[i, 14] != 0:
                        pending, handled = 0, True
                        cancel_count += 1
                    else:
                        target = mid
        if new_entry:
            stop = entry - side * risk
            if rr > 0:
                target = fixed_target(entry, side, risk, rr, tick)
            initial_target = target
            if suppress_target and (hi >= target if side == 1 else lo <= target):
                ambiguous_count += 1
        if side != 0:
            fill, stopped, dual = bracket_fill(side, op, hi, lo, target, stop, suppress_target)
            if dual:
                dual_count += 1
            if not np.isnan(fill):
                net = side * (fill - entry) / pip - cost
                trades[count] = (float(side), float(prep), float(signal), float(entry_i), float(i),
                                 entry, fill, target, net, stop, initial_target, risk, signal_atr,
                                 float(entry_kind), 1.0 if stopped else 0.0)
                count += 1
                realized += net
                side, handled = 0, True
                entry = target = stop = initial_target = np.nan
            elif rr == 0:
                target = mid
        equity = realized + (side * (cl - entry) / pip - cost if side else 0.0)
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
        ready = side == 0 and pending == 0 and not handled and not np.isnan(mid) and upper > mid and not np.isnan(f[i, 7]) and not np.isnan(f[i, 8])
        touch_buy, touch_sell = lo <= lower, hi >= upper
        if not ready or f[i, 14] != 0:
            armed = 0
        cancelled = False
        selected = 0
        if ready and armed != 0:
            explained = f[i, 10] if armed == 1 else f[i, 11]
            wick = f[i, 12] if armed == 1 else f[i, 13]
            center_passed = cl >= mid if armed == 1 else cl <= mid
            opposite = touch_sell if armed == 1 else touch_buy
            cancelled = explained != 0 or wick != 0 or i - prep > 3 or center_passed or opposite
            if not cancelled and i > prep and cl > lower and cl < upper:
                selected = armed
            if cancelled or selected != 0:
                armed = 0
        if ready and armed == 0 and not cancelled and selected == 0 and (touch_buy or touch_sell):
            explained = f[i, 10] if touch_buy else f[i, 11]
            wick = f[i, 12] if touch_buy else f[i, 13]
            if not (touch_buy and touch_sell) and explained == 0 and wick == 0:
                armed = 1 if touch_buy else -1
                prep = i
                prep_count += 1
        if selected:
            pending, signal, target = selected, i, mid
            signal_atr = f[i, 7]
            risk = risk_distance(stop_mode, pip, signal_atr, tick)
            raw_limit = cl - selected * signal_atr
            limit = (math.floor(raw_limit / tick) if selected == 1 else math.ceil(raw_limit / tick)) * tick
            signal_count += 1
    open_net = side * (last_close - entry) / pip - cost if side else 0.0
    return trades[:count], np.array([open_net, dd, side, entry, last_close, pending, prep_count, signal_count,
                                    entry_i, target, ambiguous_count, cancel_count, open_fills, touch_fills,
                                    dual_count, stop, risk, initial_target, signal_atr, entry_kind])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    manifests = json.loads((CACHE / "data_manifest.json").read_text(encoding="utf-8"))
    dump(output / "protocol.json", protocol)
    paths = [SPEC, Path(__file__), ROOT / "scripts/research_bb3_context_timing.py", CACHE / "data_manifest.json"]
    paths.extend(CACHE / f"{s}_features.npz" for s in protocol["symbols"])
    dump(output / "code_input_hashes.json", {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    inputs = {}
    for m in manifests:
        file = Path(protocol["history_directory"]) / m["symbol"] / "Bars.dat"
        if {"size": file.stat().st_size, "mtime_ns": file.stat().st_mtime_ns} != m["after"]:
            raise ValueError("Raw history changed since cached snapshot")
        data = np.load(CACHE / f"{m['symbol']}_features.npz")
        spread = float(m["metadata"]["values"]["spread"]) * m["tick"] / m["pip"]
        inputs[m["symbol"]] = (data["features"], data["times"], m["pip"], m["tick"], {"fixed_1p4": 1.4, "metadata_spread_plus_0p2": spread + .2})
    dump(output / "data_manifest.json", manifests)
    candidates = protocol["search_space"]
    summaries, results = {}, []

    def run(candidate, period, bounds):
        collected = {}
        for symbol, (f, times, pip, tick, costs) in inputs.items():
            for cost_name, cost in costs.items():
                args = (f, times, timestamp(bounds[0]), timestamp(bounds[1]), pip, cost)
                if candidate["id"] == "baseline":
                    trades, diagnostic = simulate(*args)
                else:
                    stop_mode = {"pips5": 1, "pips10": 2, "atr1.5": 3}[candidate["stop"]]
                    rr = {"center": 0., "rr1.3": 1.3, "rr1.5": 1.5}[candidate["target"]]
                    trades, diagnostic = simulate_exits(*args, tick, candidate["entry"] == "limit", stop_mode, rr)
                name = f"{candidate['id']}__{period}__{symbol}__{cost_name}.npz"
                np.savez_compressed(output / name, trades=trades, diagnostic=diagnostic)
                s = stats(trades, diagnostic)
                s["ambiguous_entry_bars"] = int(diagnostic[10]) if len(diagnostic) > 10 else 0
                s["canceled_orders"] = int(diagnostic[11]) if len(diagnostic) > 11 else 0
                s["dual_touch_bars"] = int(diagnostic[14]) if len(diagnostic) > 14 else 0
                s["stop_exits"] = int(trades[:, 14].sum()) if trades.shape[1] > 14 else 0
                results.append({"candidate": candidate["id"], "period": period, "symbol": symbol,
                                "cost_case": cost_name, "cost_pips": cost, "artifact": name, **s})
                collected.setdefault(cost_name, []).append(s)
        return {cost: {**aggregate(rows), **{key: sum(r[key] for r in rows) for key in
                  ("ambiguous_entry_bars", "canceled_orders", "dual_touch_bars", "stop_exits")}} for cost, rows in collected.items()}

    for candidate in candidates:
        training = run(candidate, "training", protocol["periods"]["training"])
        summaries[candidate["id"]] = {cost: {"training": s} for cost, s in training.items()}
        print("TRAIN", candidate["id"], json.dumps(training), flush=True)
    eligible = [c for c in candidates if c["id"] != "baseline" and eligible_train({k: v["training"] for k, v in summaries[c["id"]].items()})]
    eligible.sort(key=lambda c: (-min(v["training"]["net_pips"] for v in summaries[c["id"]].values()), c["id"]))
    selected = eligible[0]["id"] if eligible else None
    dump(output / "selection_before_validation.json", {"selected": selected, "eligible_train": [c["id"] for c in eligible], "training_summaries": summaries})
    for candidate in (c for c in candidates if c["id"] in ("baseline", selected)):
        for period, bounds in {**{k: v for k, v in protocol["periods"].items() if k != "training"},
                               "continuous": ["2023-09-08", "2026-09-08"]}.items():
            for cost, s in run(candidate, period, bounds).items():
                summaries[candidate["id"]][cost][period] = s
        print("COMPLETE", candidate["id"], flush=True)
    checks = gate(summaries[selected]) if selected else {}
    result = {"status": "GATES_PASSED_REQUIRES_INDEPENDENT_VALIDATION" if selected and all(checks.values()) else "REJECTED",
              "selected": selected, "checks": checks, "trade_columns": TRADE_COLUMNS, "baseline_trade_columns": BASE_COLUMNS,
              "summaries": summaries, "rows": results, "live_approved": False,
              "limits": "Previously viewed data; equal-pip score NOT account profit; limit touch/SL-first OHLC conventions; TV_UNVERIFIED"}
    dump(output / "results.json", result)
    print("RESULT_JSON=" + json.dumps({"status": result["status"], "selected": selected, "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
