"""Frozen daily Double Repo entries with causal Dow exits and original structural SL.

python -m scripts.research_dinapoli_3x3_daily_dow_exit
Data access, entry detection and common scoring reuse the preceding frozen study.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from scripts import research_dinapoli_3x3_daily as base

ROOT = base.ROOT
SPEC = ROOT / "docs/quant_organization/experiments/dinapoli_3x3_daily_dow_exit_20260910/protocol.json"
OUT = ROOT / "agent_runs/dinapoli_3x3_daily_dow_exit_20260910/completed"


def dow_states(ohlc: np.ndarray, length: int):
    """State at each close, based exclusively on pivots confirmed at that close.

    Strict ties are excluded. Every same-type pivot is retained. Simultaneously
    confirmed highs and lows update atomically. Mixed relations preserve state.
    Event columns: confirmation index, pivot index, side (+high/-low), price.
    """
    if length not in (2, 3):
        raise ValueError("Frozen pivot lengths are 2 and 3")
    states = np.zeros(len(ohlc), dtype=np.int8)
    highs, lows, events = [], [], []
    state = 0
    for i in range(2 * length, len(ohlc)):
        k = i - length
        for col, side, history in ((1, 1, highs), (2, -1, lows)):
            price = float(ohlc[k, col])
            neighbors = np.r_[ohlc[k-length:k, col], ohlc[k+1:i+1, col]]
            if np.all(side * (price - neighbors) > 0):
                history.append(price)
                if len(history) > 2:
                    del history[0]
                events.append([i, k, side, price])
        if len(highs) == 2 and len(lows) == 2:
            if highs[1] > highs[0] and lows[1] > lows[0]:
                state = 1
            elif highs[1] < highs[0] and lows[1] < lows[0]:
                state = -1
        states[i] = state
    return states, np.asarray(events, dtype=float).reshape((-1, 4))


def dow_exit_fill(direction, stop, bar, pending_dow: bool):
    """Open events precede intraday range; no target, no movable stop."""
    op, high, low, _ = bar
    if direction * (op - stop) <= 0:
        return float(op), "stop_gap"
    if pending_dow:
        return float(op), "dow_next_open"
    if low <= stop if direction == 1 else high >= stop:
        return float(stop), "stop"
    return None


def simulate(data, candidate, start, end, pip, cost, warmup=30):
    if candidate["exit"] == "rr1":
        return base.simulate(data, candidate, start, end, pip, cost, warmup)
    first, last = np.searchsorted(data.dates, [start, end], side="left")
    dma, atr = base.indicators(data.ohlc)
    signals, stops, preps = base.generate_signals(data.ohlc, dma, atr, candidate, int(first), int(last), warmup)
    states, _ = dow_states(data.ohlc, candidate["pivot"])
    trades, equity = [], []
    pending = position = pending_exit = None
    cancelled = ignored = 0
    realized = 0.
    for i in range(first, last):
        exited = False
        if pending is not None:
            signal, direction, stop, begin = pending
            pending = None
            entry = float(data.ohlc[i, 0])
            risk = direction * (entry - stop)
            if risk <= 0 or not np.isfinite(risk):
                cancelled += 1
            else:
                if data.last[signal] + 60 > data.first[i]:
                    raise AssertionError("Entry signal unavailable at fill")
                position = {"direction": int(direction), "prep_index": int(begin), "signal_index": int(signal),
                    "entry_index": int(i), "entry": entry, "stop": float(stop), "target": "none",
                    "risk_pips": float(risk / pip), "cost_pips": float(cost), "dow_armed": False, "dow_armed_index": -1,
                    "signal_trading_date": base.iso(data.dates[signal]), "signal_raw_last_timestamp": base.iso(data.last[signal]),
                    "signal_available_timestamp": base.iso(data.last[signal] + 60),
                    "entry_trading_date": base.iso(data.dates[i]), "entry_raw_first_timestamp": base.iso(data.first[i])}
        if position is not None:
            p = position
            if pending_exit is not None and data.last[pending_exit] + 60 > data.first[i]:
                raise AssertionError("Dow signal unavailable at fill")
            fill = dow_exit_fill(p["direction"], p["stop"], data.ohlc[i], pending_exit is not None)
            if fill is not None:
                price, reason = fill
                net_pips = p["direction"] * (price - p["entry"]) / pip - cost
                net_r = net_pips / p["risk_pips"]
                trades.append({**p, "exit_index": int(i), "exit_trading_date": base.iso(data.dates[i]),
                    "exit_raw_first_timestamp": base.iso(data.first[i]), "exit_raw_last_timestamp": base.iso(data.last[i]),
                    "exit_price": price, "reason": reason, "net_pips": net_pips, "net_r": net_r,
                    "dow_signal_index": int(pending_exit) if pending_exit is not None else -1,
                    "dow_signal_available_timestamp": base.iso(data.last[pending_exit] + 60) if pending_exit is not None else "none",
                    "holding_calendar_days": int((data.first[i] - data.first[p["entry_index"]]) // base.DAY)})
                realized += net_r
                position = pending_exit = None
                exited = True
            elif states[i] == p["direction"]:
                if not p["dow_armed"]:
                    p["dow_armed"] = True
                    p["dow_armed_index"] = int(i)
            elif p["dow_armed"] and states[i] == -p["direction"] and i > 0 and states[i-1] != states[i]:
                pending_exit = int(i)
        open_r = 0.
        if position is not None:
            p = position
            open_r = (p["direction"] * (data.ohlc[i, 3] - p["entry"]) / pip - cost) / p["risk_pips"]
        equity.append([int(data.dates[i]), realized, realized + open_r])
        if signals[i]:
            if position is None and not exited:
                pending = (i, int(signals[i]), stops[i], preps[i])
            else:
                ignored += 1
    marked = None
    if position is not None:
        p = position
        price = float(data.ohlc[last-1, 3])
        net_pips = p["direction"] * (price - p["entry"]) / pip - cost
        marked = {**p, "mark_trading_date": base.iso(data.dates[last-1]), "mark_raw_last_timestamp": base.iso(data.last[last-1]),
            "mark_price": price, "net_pips": net_pips, "net_r": net_pips / p["risk_pips"],
            "holding_calendar_days": int((data.last[last-1] + 60 - data.first[p["entry_index"]]) // base.DAY)}
    diagnostics = {"open_count": int(marked is not None), "open_net_r": marked["net_r"] if marked else 0.,
        "open_position": marked, "cancelled_at_open": cancelled, "ignored_signals": ignored,
        "pending_at_end": int(pending is not None), "pending_dow_exit_at_end": int(pending_exit is not None),
        "signal_count": int(np.count_nonzero(signals))}
    return trades, diagnostics, np.asarray(equity, dtype=float).reshape((-1, 3))


def holding_summary(trades):
    days = np.asarray([t["holding_calendar_days"] for t in trades], dtype=float)
    return {"mean_holding_days": float(days.mean()) if len(days) else None,
        "median_holding_days": float(np.median(days)) if len(days) else None,
        "p95_holding_days": float(np.percentile(days, 95)) if len(days) else None,
        "max_holding_days": int(days.max()) if len(days) else None,
        "hypothetical_1pip_per_calendar_day_cost": base.distribution([
            t["net_r"] - t["holding_calendar_days"] / t["risk_pips"] for t in trades]),
        "exit_reasons": {reason: sum(t["reason"] == reason for t in trades) for reason in sorted({t["reason"] for t in trades})}}


def select_training(totals, decisions):
    eligible = [cid for cid, decision in decisions.items() if all(d["passed"] for d in decision["training"].values())]
    def rank(cid):
        summaries = list(totals[cid]["training"].values())
        return (-min(s["pf"] if s["pf"] is not None else float("inf") for s in summaries),
            -min(s["average_net_r"] for s in summaries), max(s["closed_drawdown_r"] for s in summaries), cid)
    return min(eligible, key=rank) if eligible else None


def no_nulls(value):
    if value is None:
        raise ValueError("Protocol contains an unfrozen null")
    if isinstance(value, dict):
        for item in value.values():
            no_nulls(item)
    elif isinstance(value, list):
        for item in value:
            no_nulls(item)


def run(output: Path):
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    no_nulls(protocol)
    output.mkdir(parents=True, exist_ok=False)
    base.dump(output / "protocol.json", protocol)
    dependencies = [SPEC, SPEC.with_name("hypothesis.md"), Path(__file__), Path(base.__file__),
        base.SPEC.with_name("hypothesis.md"), ROOT / "src/forextester_backtest/data.py", ROOT / "src/forextester_backtest/models.py"]
    frozen = {"frozen_before_simulation_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": {str(p.relative_to(ROOT)): base.sha(p) for p in dependencies}}
    base.dump(output / "code_input_hashes.json", frozen)
    repository = base.HistoryRepository(protocol["history_directory"])
    inputs, manifests = {}, []
    for symbol in protocol["symbols"]:
        print("LOAD", symbol, flush=True)
        data, manifest = base.load_daily(repository, symbol, protocol["warmup_start"], protocol["periods"]["final_confirmation"][1])
        np.savez_compressed(output / f"{symbol}_daily.npz", dates=data.dates, ohlc=data.ohlc,
            raw_first_timestamp=data.first, raw_last_timestamp=data.last, source_counts=data.counts)
        for length in (2, 3):
            state, events = dow_states(data.ohlc, length)
            np.savez_compressed(output / f"{symbol}_dow{length}.npz", states=state, events=events)
        inputs[symbol] = (data, manifest["pip"], {"fixed_1p4": 1.4, "metadata_spread": manifest["metadata_spread_pips"]})
        manifests.append(manifest)
    base.dump(output / "data_manifest.json", manifests)
    rows, totals, decisions = [], {}, {}
    gates = protocol["acceptance_gates"]

    def evaluate(candidate, period):
        bounds = protocol["periods"][period]
        collected = {"fixed_1p4": [], "metadata_spread": []}
        for symbol, (data, pip, costs) in inputs.items():
            for cost_name, cost in costs.items():
                trades, diagnostics, equity = simulate(data, candidate, base.timestamp(bounds[0]), base.timestamp(bounds[1]), pip, cost,
                    protocol["minimum_warmup_bars"])
                summary = {**base.summarize(trades, diagnostics, equity), **holding_summary(trades)}
                name = f"{candidate['id']}__{period}__{symbol}__{cost_name}"
                base.dump(output / f"{name}.json", {"trades": trades, "diagnostics": diagnostics, "summary": summary})
                np.savez_compressed(output / f"{name}_equity.npz", equity=equity)
                rows.append({"candidate": candidate["id"], "period": period, "symbol": symbol,
                    "cost_case": cost_name, "cost_pips": cost, "artifact": f"{name}.json", **summary})
                collected[cost_name].append({"trades": trades, "diagnostics": diagnostics, "equity": equity, "summary": summary})
        totals.setdefault(candidate["id"], {})[period] = {case: {**base.combine(items),
            **holding_summary([t for item in items for t in item["trades"]])} for case, items in collected.items()}
        print("COMPLETE", candidate["id"], period, flush=True)
        return totals[candidate["id"]][period]

    def decide(cid, period):
        decisions.setdefault(cid, {})[period] = {case: base.gate(summary, gates[period], gates)
            for case, summary in totals[cid][period].items()}
        return all(d["passed"] for d in decisions[cid][period].values())

    for candidate in protocol["search_space"]:
        evaluate(candidate, "training")
        if candidate["eligible"]:
            decide(candidate["id"], "training")
    base.dump(output / "training_results.json", {"totals": totals, "rows": rows, "decisions": decisions})
    selected = select_training(totals, decisions)
    base.dump(output / "selection_before_validation.json", {"saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected": selected, "decisions": decisions, "protocol_sha256": base.sha(SPEC)})
    selected_final = None
    if selected is not None:
        candidate = next(c for c in protocol["search_space"] if c["id"] == selected)
        evaluate(candidate, "validation")
        if decide(selected, "validation"):
            selected_final = selected
    base.dump(output / "selection_before_final.json", {"saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected": selected_final, "decisions": decisions, "protocol_sha256": base.sha(SPEC)})
    passed = []
    if selected_final is not None:
        evaluate(candidate, "final_confirmation")
        if decide(selected_final, "final_confirmation"):
            passed.append(selected_final)
    result = {"status": "RESEARCH_GATES_PASSED_AWAITING_INDEPENDENT_VALIDATION" if passed else "REJECTED_BY_FROZEN_GATES",
        "selected_for_validation": selected, "selected_for_final": selected_final, "passed_research_gates": passed,
        "totals": totals, "rows": rows, "decisions": decisions, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "prior_exposure": protocol["final_period_prior_exposure"], "adoption_approved": False}
    if frozen["sha256"] != {str(p.relative_to(ROOT)): base.sha(p) for p in dependencies}:
        raise ValueError("Frozen code or protocol changed during simulation")
    base.dump(output / "results.json", result)
    print("RESULT_JSON=" + json.dumps({"status": result["status"], "selected": selected, "passed": passed, "output": str(output)}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    run(parser.parse_args().output)
