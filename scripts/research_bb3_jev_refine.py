"""Nine deterministic BB refinements; Jev is NOT in the trading decision path.

No API calls or model-response cache reads. Persist training selection before
evaluating later years; import the original candidate/execution engine unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from research_bb3_jev_engine import CACHE, ROOT, START, END, candidates, load_symbol, simulate

DOC = ROOT / "docs/quant_organization/experiments/bb3_jev_refine_20260925"
OUT = ROOT / "agent_runs/bb3_jev_refine_20260925"
POLICIES = ("close_hold", "room5", "deceleration")
RRS = (1.0, 1.3, 1.5)
COSTS = (1.0, 1.2)


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    # Windows readers may briefly deny atomic replacement; never drop an update.
    for attempt in range(10):
        try:
            temp.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(.05)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_signals(f, signals, policy):
    """Filter existing signals with closed, causal information; never regenerate."""
    if policy not in POLICIES:
        raise ValueError("Unknown frozen policy")
    result = []
    for signal in signals:
        i, side = signal["index"], signal["side"]
        op, hi, lo, cl, basis = f[i, :5]
        if not (side * (cl - signal["threshold"]) > 0 and side * (cl - op) > 0):
            continue
        if policy == "deceleration":
            if i < 6 or not np.isfinite(f[[i, i-3, i-6], 4]).all():
                continue
            tr = max(hi-lo, abs(hi-f[i-1, 3]), abs(lo-f[i-1, 3]))
            if not (side * (basis-f[i-3, 4]) >= side * (f[i-3, 4]-f[i-6, 4])
                    and tr <= 1.5 * f[i, 7]):
                continue
        result.append(signal)
    return result


def entry_room(policy):
    if policy not in (*POLICIES, "original"):
        raise ValueError("Unknown frozen policy")
    return 5.0 if policy in ("room5", "deceleration") else 3.0


def arms():
    """Three original RR controls plus exactly nine deterministic variants."""
    return [(p, rr) for p in ("original", *POLICIES) for rr in RRS]


def arm_name(policy, rr, cost):
    return f"{policy}_rr{rr}_cost{cost}"


def periods():
    result = {"all": (START, END)}
    for year in (2023, 2024, 2025):
        result[str(year)] = (int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()),
                             int(datetime(year+1, 1, 1, tzinfo=timezone.utc).timestamp()))
    return result


def add_curve(equity, timeline, curve):
    """Last known observation only; no future interpolation across pairs."""
    if not len(curve):
        return
    index = np.searchsorted(curve[:, 0], timeline, side="right")-1
    equity += np.where(index >= 0, curve[np.maximum(index, 0), 1], 0)


def aggregate(items):
    pips, risk = [t["net_pips"] for t in items], [t["net_r"] for t in items]
    gp, gl = math.fsum(v for v in pips if v > 0), -math.fsum(v for v in pips if v < 0)
    rp, rl = math.fsum(v for v in risk if v > 0), -math.fsum(v for v in risk if v < 0)
    n = len(items)
    return dict(trades=n, wins=sum(v > 1e-9 for v in pips),
                win_rate_pct=100 * sum(v > 1e-9 for v in pips) / n if n else 0,
                gross_profit_pips=gp, gross_loss_pips=gl, profit_factor=gp/gl if gl else None,
                gross_profit_r=rp, gross_loss_r=rl, profit_factor_r=rp/rl if rl else None,
                net_pips=math.fsum(pips), net_r=math.fsum(risk),
                average_r=math.fsum(risk)/n if n else 0)


def totals_for(rows, annual_rows, trades, curves):
    totals = {}
    for (key, period), items in trades.items():
        matching = [r for r in (rows if period == "all" else annual_rows)
                    if r["arm"] == key and (period == "all" or str(r["year"]) == period)]
        stats = aggregate(items)
        equity = curves[key, period]
        peaks = np.maximum.accumulate(np.maximum(equity, 0)) if len(equity) else np.array([])
        stats.update(open_net_r=math.fsum(r["open_net_r"] for r in matching),
                     net_plus_open_r=math.fsum(r["net_plus_open_r"] for r in matching),
                     open_net_pips=math.fsum(r["open_net_pips"] for r in matching),
                     net_plus_open_pips=math.fsum(r["net_plus_open_pips"] for r in matching),
                     bar_close_mtm_drawdown_r=float(np.max(peaks-equity)) if len(equity) else 0.0,
                     positive_pairs=sum(r["net_plus_open_r"] > 0 for r in matching),
                     evaluated_pairs=len(matching))
        totals.setdefault(key, {})[period] = stats
    return totals


def select_training(totals):
    """Highest 2023 average R, >=30 closed; ties lower RR then simpler policy."""
    contenders = [(p, rr) for p in POLICIES for rr in RRS
                  if totals[arm_name(p, rr, 1.0)]["2023"]["trades"] >= 30]
    if not contenders:
        return None
    p, rr = min(contenders, key=lambda a: (
        -totals[arm_name(*a, 1.0)]["2023"]["average_r"], a[1], POLICIES.index(a[0])))
    return dict(policy=p, rr=rr, arm=arm_name(p, rr, 1.0))


def acceptance_gates(totals, selected):
    if selected is None:
        return {"selection": {"minimum_training_count": False}}
    gates = {}
    for year in ("2024", "2025"):
        a = totals[selected["arm"]][year]
        b = totals[arm_name("original", 1.0, 1.0)][year]
        c = totals[arm_name("original", selected["rr"], 1.0)][year]
        stress = totals[arm_name(selected["policy"], selected["rr"], 1.2)][year]
        gates[year] = dict(count=a["trades"] >= 100,
            frequency=a["trades"] >= .7*b["trades"],
            win_rate=a["win_rate_pct"] >= max(b["win_rate_pct"], c["win_rate_pct"])+2,
            pf=a["profit_factor_r"] is not None and a["profit_factor_r"] >= max(
                1.2, b["profit_factor_r"] or 0, c["profit_factor_r"] or 0),
            average_r=a["average_r"] > max(b["average_r"], c["average_r"]),
            net_r=a["net_plus_open_r"] > max(b["net_plus_open_r"], c["net_plus_open_r"]),
            drawdown=a["bar_close_mtm_drawdown_r"] <= 1.2*b["bar_close_mtm_drawdown_r"],
            cost_stress=stress["net_plus_open_r"] > 0, cross_pair=a["positive_pairs"] >= 4)
    return gates


def write_progress(out, phase, message, **counts):
    if "completed_tasks" in counts:
        counts.update(completed_jobs=counts["completed_tasks"], total_jobs=counts["total_tasks"])
    write_json(out / "progress.json", dict(phase=phase, message=message, **counts,
               updated_utc=datetime.now(timezone.utc).isoformat()))


def prepare(protocol, protocol_path, out):
    """Rebuild original candidates and hash local inputs; no Jev trade caches."""
    data = {}
    for number, symbol in enumerate(protocol["symbols"], 1):
        write_progress(out, "preparing", f"元候補と価格履歴を確認: {symbol}",
                       completed_pairs=number-1, total_pairs=len(protocol["symbols"]))
        f, times, pip, tick = load_symbol(symbol)
        signals = [s for s in candidates(f, times, pip, tick) if START <= times[s["index"]] < END]
        data[symbol] = (f, times, pip, tick, signals)
        write_json(out / f"{symbol}_candidates.json", signals)
    count = sum(len(v[4]) for v in data.values())
    if count != 828:
        raise RuntimeError(f"Frozen original candidate universe differs: {count}")
    write_json(out / "run_manifest.json", dict(protocol_sha=file_hash(protocol_path), candidates=count,
        candidate_counts={s: len(v[4]) for s, v in data.items()},
        data_sha256={s: file_hash(CACHE / f"{s}_features.npz") for s in data},
        code_hashes={p: file_hash(ROOT / p) for p in (
            "scripts/research_bb3_jev_refine.py", "scripts/research_bb3_jev_engine.py",
            "scripts/tradingview/bb3_reversal_confirmation_indicator.pine")},
        model_trade_calls=0, model_trade_cache_reads=0))
    return data


def report(data, protocol, out):
    spans = periods()
    timelines = {period: np.unique(np.concatenate([t[(t >= start) & (t < end)]
                 for _, t, _, _, _ in data.values()])) for period, (start, end) in spans.items()}
    filtered = {symbol: {p: policy_signals(v[0], v[4], p) for p in POLICIES}
                for symbol, v in data.items()}
    rows, annual_rows, trades, curves = [], [], {}, {}
    completed, tasks = 0, len(data) * len(arms()) * len(COSTS) * len(spans)
    selected = None
    # Persist selection before any later-year or continuous-book P/L is calculated.
    for phase, period_names in (("training", ("2023",)), ("evaluation", ("2024", "2025", "all"))):
        for pair_number, (symbol, (f, times, pip, tick, signals)) in enumerate(data.items(), 1):
            for policy, rr in arms():
                chosen_signals = filtered[symbol][policy] if policy in POLICIES else signals
                for cost in COSTS:
                    key = arm_name(policy, rr, cost)
                    for period in period_names:
                        start, end = spans[period]
                        result = simulate(f, times, pip, tick, chosen_signals, rr=rr, entry_delay=1,
                                          cost_pips=cost, min_center_pips=entry_room(policy), start=start, end=end)
                        tags = dict(symbol=symbol, selected_policy=policy, rr=rr)
                        row = dict(tags, arm=key, **result["summary"])
                        if period == "all":
                            rows.append(row)
                        else:
                            annual_rows.append(dict(row, year=int(period)))
                        items = [dict(t, **tags) for t in result["trades"]]
                        trades.setdefault((key, period), []).extend(items)
                        curve = curves.setdefault((key, period), np.zeros(len(timelines[period])))
                        add_curve(curve, timelines[period], result["mtm"])
                        suffix = key if period == "all" else f"{key}_{period}"
                        np.savez_compressed(out / f"{symbol}_{suffix}_mtm.npz", mtm=result["mtm"])
                        write_json(out / f"{symbol}_{suffix}_trades.json", items)
                        completed += 1
                        write_progress(out, phase, f"{symbol} / {policy} / RR {rr} / {period}",
                                       completed_tasks=completed, total_tasks=tasks,
                                       completed_pairs=pair_number-1, total_pairs=len(data))
            partial = dict(protocol=protocol, complete=False, phase=phase,
                           completed_pairs=pair_number, total_pairs=len(data),
                           pair_summaries=rows, annual_pair_summaries=annual_rows,
                           totals=totals_for(rows, annual_rows, trades, curves),
                           incremental_api_cost_usd=0, incremental_api_cost_jpy=0,
                           model_trade_calls=0, model_trade_cache_reads=0,
                           arm_labels={arm_name(p, rr, cost): (
                               {"original": "現行", "close_hold": "終値突破維持", "room5": "利幅5pips",
                                "deceleration": "逆行減速"}[p] + f" / RR 1:{rr} / {cost} pips")
                               for p, rr in arms() for cost in COSTS})
            write_json(out / "partial_results.json", partial)
            print(f"SIMULATED {phase} {symbol} ({pair_number}/{len(data)})", flush=True)
        if phase == "training":
            selected = select_training(partial["totals"])
            write_json(out / "selection.json", dict(selected=selected, selection_period="2023",
                       later_periods_simulated=False, frozen_utc=datetime.now(timezone.utc).isoformat(),
                       training_totals=partial["totals"]))
            print("SELECTION_FROZEN=" + json.dumps(selected), flush=True)
    totals = totals_for(rows, annual_rows, trades, curves)
    for (key, period), items in trades.items():
        suffix = key if period == "all" else f"{key}_{period}"
        write_json(out / f"{suffix}_trades.json", items)
        np.savez_compressed(out / f"{suffix}_combined_mtm.npz",
                            mtm=np.column_stack((timelines[period], curves[key, period])))
    gates = acceptance_gates(totals, selected)
    summary = dict(partial, complete=True, phase="complete", totals=totals,
                   selected_from_2023=selected, gates=gates,
                   candidates=sum(len(v[4]) for v in data.values()),
                   policy_candidate_counts={s: {p: len(v[p]) for p in POLICIES} for s, v in filtered.items()},
                   numeric_gates_pass=all(all(g.values()) for g in gates.values()),
                   eligible_for_forward_test=False, status="INDEPENDENT_REPLAY_REVIEW_REQUIRED")
    write_json(out / "results.json", summary)
    write_progress(out, "validation", "全比較完了・独立判定待ち", completed_tasks=tasks, total_tasks=tasks,
                   completed_pairs=len(data), total_pairs=len(data))
    print("RESULT_JSON=" + str(out / "results.json"), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DOC / "protocol.json")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("status") != "SPEC_FROZEN" or protocol.get("candidate_budget") != 9:
        raise ValueError("The frozen nine-policy protocol is required")
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in ("run_manifest.json", "selection.json", "results.json")):
        raise RuntimeError("Refuse to overwrite a prior research run")
    write_json(args.output / "protocol.json", protocol)
    data = prepare(protocol, args.protocol, args.output)
    report(data, protocol, args.output)


if __name__ == "__main__":
    main()
