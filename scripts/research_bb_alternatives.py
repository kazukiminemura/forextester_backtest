"""Two preregistered BB alternatives. Deterministic research; no AI trade calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np

from research_bb3_jev_engine import CACHE, ROOT, START, END, candidates, load_symbol, round_tick, simulate
from research_bb3_jev_refine import add_curve, file_hash, periods, totals_for, write_json, write_progress

DOC = ROOT / "docs/quant_organization/experiments/bb_alternatives_20260925"
OUT = ROOT / "agent_runs/bb_alternatives_20260925"
POLICIES = ("original", "bb2_reentry", "wm")
COSTS = (1.0, 1.2)


def bands(close):
    """Trailing closed-bar SMA20 and population sigma; no future information."""
    result = np.full((len(close), 3), np.nan)
    if len(close) >= 20:
        windows = np.lib.stride_tricks.sliding_window_view(close, 20)
        mid, dev = windows.mean(axis=1), windows.std(axis=1, ddof=0)
        result[19:] = np.column_stack((mid, mid+2*dev, mid-2*dev))
    return result


def reentry_signals(f, times, bb, tick):
    result = []
    for i in range(1, len(f)):
        mid, upper, lower = bb[i]
        if times[i]-times[i-1] != 300 or not lower < f[i, 3] < upper:
            continue
        side = 1 if f[i-1, 3] < bb[i-1, 2] else -1 if f[i-1, 3] > bb[i-1, 1] else 0
        if side:
            result.append(dict(index=i, side=side, target=round_tick(mid, tick)))
    return result


def wm_signals(f, times, bb, tick):
    """Close pivots known only two bars later; independent mirrored W/M states."""
    states, result, segment_start = {}, [], 0
    for i in range(len(f)):
        if i and times[i]-times[i-1] != 300:
            states.clear()
            segment_start = i
        emitted = []
        for side in (1, -1):
            state = states.get(side)
            if state and i-state["first"] > 60:
                states.pop(side)
                state = None
            p = i-2
            pivot = p >= segment_start+2 and np.isfinite(bb[p]).all() and all(
                side*(f[p, 3]-f[k, 3]) < 0 for k in (p-2, p-1, p+1, p+2))
            if pivot and (not state or "second" not in state):
                inside = bb[p, 2] < f[p, 3] < bb[p, 1]
                first = state["first"] if state else p
                rebound = state and any(side*(f[k, 3]-bb[k, 0]) >= 0 for k in range(first+1, p))
                if state and p > first and side*(f[p, 3]-f[first, 3]) < 0 and inside and rebound:
                    extreme = float(f[p, 2 if side == 1 else 1])
                    raw_stop = extreme-side*tick
                    stop = (math.floor(raw_stop/tick+1e-8) if side == 1
                            else math.ceil(raw_stop/tick-1e-8))*tick
                    state.update(second=p, confirmed=i, extreme=extreme, stop_anchor=stop,
                                 neckline=float(np.max(f[first+1:p, 1]) if side == 1
                                                else np.min(f[first+1:p, 2])))
                elif side*(f[p, 3]-bb[p, 2 if side == 1 else 1]) < 0:
                    states[side] = state = dict(first=p)
            if state and "second" in state:
                adverse = f[state["second"]+1:i+1, 2 if side == 1 else 1]
                if np.any(side*(adverse-state["extreme"]) < 0):
                    states.pop(side)
                elif side*(f[i, 3]-state["neckline"]) > 0:
                    emitted.append(dict(index=i, side=side, **state))
                    states.pop(side)
        if len(emitted) == 1:
            result.extend(emitted)
    return result


def execute(f, times, pip, tick, signals, policy, cost, start, end):
    """Price W/M orders at their actual next open, not in the signal generator.

    The fixed-stop RR1 identity target=2*fill-stop lets the unchanged simulator
    own occupancy, gap checks, SL-first exits, costs and MTM. Rejected next-open
    risk is handled by its minimum reward check. The adapted target is NEVER
    consulted by candidate generation or filtering. Out-of-range pending orders
    get an inert finite target and cannot fill within this book.
    """
    if policy == "wm":
        signals = [dict(s, target=2*float(f[s["index"]+1, 0])-s["stop_anchor"]
                        if s["index"]+1 < len(f) and times[s["index"]+1] < end
                        else float(f[s["index"], 3])) for s in signals]
    return simulate(f, times, pip, tick, signals, rr=1.0, entry_delay=1,
                    cost_pips=cost, min_center_pips=3.0, start=start, end=end)


def arm_name(policy, cost):
    return f"{policy}_rr1.0_cost{cost}"


def gates_for(totals, policy):
    gates = {}
    for year in ("2024", "2025"):
        a, stress = totals[arm_name(policy, 1.0)][year], totals[arm_name(policy, 1.2)][year]
        gates[year] = dict(count=a["trades"] >= 100,
                           pf=a["profit_factor_r"] is not None and a["profit_factor_r"] >= 1.2,
                           average_r=a["average_r"] is not None and a["average_r"] > 0,
                           cost_stress=stress["net_plus_open_r"] > 0,
                           cross_pair=a["positive_pairs"] >= 4)
    gates["continuous"] = dict(drawdown=totals[arm_name(policy, 1.0)]["all"]["bar_close_mtm_drawdown_r"]
        <= 1.2*totals[arm_name("original", 1.0)]["all"]["bar_close_mtm_drawdown_r"])
    return gates


def run(protocol, protocol_path, out):
    data = {}
    for symbol in protocol["symbols"]:
        write_progress(out, "preparing", f"価格・候補準備: {symbol}", completed_jobs=0, total_jobs=168)
        f, times, pip, tick = load_symbol(symbol)
        bb = bands(f[:, 3])
        choices = dict(original=candidates(f, times, pip, tick),
                       bb2_reentry=reentry_signals(f, times, bb, tick), wm=wm_signals(f, times, bb, tick))
        choices = {p: [s for s in ss if START <= times[s["index"]] < END] for p, ss in choices.items()}
        data[symbol] = f, times, pip, tick, choices
        for policy, signals in choices.items():
            write_json(out / f"{symbol}_{policy}_candidates.json", signals)
        print(f"PREPARED {symbol}", flush=True)
    if sum(len(v[4]["original"]) for v in data.values()) != 828:
        raise RuntimeError("Original frozen candidate universe differs")
    write_json(out / "run_manifest.json", dict(protocol_sha=file_hash(protocol_path),
        started_utc=datetime.now(timezone.utc).isoformat(),
        candidate_counts={s: {p: len(ss) for p, ss in v[4].items()} for s, v in data.items()},
        data_sha256={s: file_hash(CACHE / f"{s}_features.npz") for s in data},
        code_hashes={p: file_hash(ROOT / p) for p in (
            "scripts/research_bb_alternatives.py", "tests/test_bb_alternatives.py",
            "scripts/research_bb3_jev_engine.py", "scripts/research_bb3_jev_refine.py",
            "scripts/tradingview/bb3_reversal_confirmation_indicator.pine")},
        model_trade_calls=0, model_trade_cache_reads=0))
    spans = periods()
    timelines = {period: np.unique(np.concatenate([v[1][(v[1] >= start) & (v[1] < end)]
                 for v in data.values()])) for period, (start, end) in spans.items()}
    rows, annual_rows, trades, curves = [], [], {}, {}
    completed, tasks = 0, len(data)*len(POLICIES)*len(COSTS)*len(spans)
    labels = {arm_name(p, c): {"original": "現行BB3", "bb2_reentry": "BB2終値復帰", "wm": "W底/M天井"}[p]
              + f" / RR1 / {c}pips" for p in POLICIES for c in COSTS}
    for pair_number, (symbol, (f, times, pip, tick, choices)) in enumerate(data.items(), 1):
        for policy in POLICIES:
            for cost in COSTS:
                key = arm_name(policy, cost)
                for period, (start, end) in spans.items():
                    result = execute(f, times, pip, tick, choices[policy], policy, cost, start, end)
                    tags = dict(symbol=symbol, selected_policy=policy, rr=1.0)
                    row = dict(tags, arm=key, **result["summary"])
                    (rows if period == "all" else annual_rows).append(row if period == "all" else dict(row, year=int(period)))
                    items = [dict(t, **tags) for t in result["trades"]]
                    trades.setdefault((key, period), []).extend(items)
                    curve = curves.setdefault((key, period), np.zeros(len(timelines[period])))
                    add_curve(curve, timelines[period], result["mtm"])
                    suffix = key if period == "all" else f"{key}_{period}"
                    np.savez_compressed(out / f"{symbol}_{suffix}_mtm.npz", mtm=result["mtm"])
                    write_json(out / f"{symbol}_{suffix}_trades.json", items)
                    completed += 1
                    write_progress(out, "evaluation", f"{symbol} / {policy} / {period}",
                                   completed_jobs=completed, total_jobs=tasks)
        partial = dict(protocol=protocol, complete=False, pair_summaries=rows,
                       annual_pair_summaries=annual_rows, totals=totals_for(rows, annual_rows, trades, curves),
                       arm_labels=labels, completed_pairs=pair_number, total_pairs=len(data),
                       model_trade_calls=0, model_trade_cache_reads=0)
        write_json(out / "partial_results.json", partial)
        print(f"SIMULATED {symbol} ({pair_number}/{len(data)})", flush=True)
    for (key, period), items in trades.items():
        suffix = key if period == "all" else f"{key}_{period}"
        write_json(out / f"{suffix}_trades.json", items)
        np.savez_compressed(out / f"{suffix}_combined_mtm.npz",
                            mtm=np.column_stack((timelines[period], curves[key, period])))
    gates = {p: gates_for(partial["totals"], p) for p in POLICIES[1:]}
    final = dict(partial, complete=True, gates=gates,
                 numeric_gates_pass={p: all(all(g.values()) for g in vv.values()) for p, vv in gates.items()},
                 eligible_for_forward_test=False, status="INDEPENDENT_REPLAY_REVIEW_REQUIRED")
    write_json(out / "results.json", final)
    write_progress(out, "validation", "計算完了・独立検証待ち", completed_jobs=tasks, total_jobs=tasks)
    print("RESULT_JSON=" + str(out / "results.json"), flush=True)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DOC / "protocol.json")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("status") != "SPEC_FROZEN" or protocol.get("candidate_budget") != 2:
        raise ValueError("Frozen two-alternative protocol required")
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in ("run_manifest.json", "results.json")):
        raise RuntimeError("Refuse to overwrite prior research")
    write_json(args.output / "protocol.json", protocol)
    run(protocol, args.protocol, args.output)


if __name__ == "__main__":
    main()
