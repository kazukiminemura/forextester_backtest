"""Frozen daily 3x3 DMA research: data, signals, execution and scoring are separate.

Run from the repository: python -m scripts.research_dinapoli_3x3_daily
Only passed training candidates reach validation; only passed validation candidates
reach final confirmation. No optimization or writes to source history occur.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from forextester_backtest.data import HistoryRepository, _RecordFile, BAR_STRUCT

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/quant_organization/experiments/dinapoli_3x3_daily_20260909/protocol.json"
OUT = ROOT / "agent_runs/dinapoli_3x3_daily_20260909/completed"
DAY = 86400
OLE_UNIX_DAYS = 25569


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def timestamp(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


def iso(value: int) -> str:
    # Display naive source time explicitly; attaching UTC here is only epoch arithmetic.
    return datetime.fromtimestamp(int(value), timezone.utc).replace(tzinfo=None).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class DailyData:
    dates: np.ndarray
    ohlc: np.ndarray
    first: np.ndarray
    last: np.ndarray
    counts: np.ndarray


def aggregate_daily(times: np.ndarray, ohlc: np.ndarray) -> DailyData:
    """Aggregate observed bars; Sunday belongs to the following Monday label."""
    if len(times) == 0 or len(times) != len(ohlc):
        raise ValueError("Nonempty aligned source arrays required")
    if np.any(np.diff(times) <= 0):
        raise ValueError("Source timestamps must strictly increase")
    days = times // DAY
    labels = days + (((days + 3) % 7) == 6)
    starts = np.r_[0, np.flatnonzero(np.diff(labels)) + 1]
    ends = np.r_[starts[1:] - 1, len(times) - 1]
    daily = np.column_stack((ohlc[starts, 0], np.maximum.reduceat(ohlc[:, 1], starts),
                             np.minimum.reduceat(ohlc[:, 2], starts), ohlc[ends, 3]))
    return DailyData(labels[starts] * DAY, daily, times[starts], times[ends], ends - starts + 1)


def load_daily(repository: HistoryRepository, symbol: str, start: str, end: str):
    """Read a bounded M1 prefix directly using the documented 6-double record layout."""
    path = repository._symbol_dir(symbol) / "Bars.dat"
    before = {"size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
    count = _RecordFile(path, BAR_STRUCT.size).count()
    raw = np.memmap(path, mode="r", dtype="<f8", offset=4, shape=(count, 6))
    lower = timestamp(start) / DAY + OLE_UNIX_DAYS
    upper = timestamp(end) / DAY + OLE_UNIX_DAYS
    left, right = np.searchsorted(raw[:, 0], [lower, upper], side="left")
    used = raw[left:right]
    if len(used) == 0 or not np.isfinite(used[:, :5]).all():
        raise ValueError(f"Empty or nonfinite history: {symbol}")
    times = np.rint((used[:, 0] - OLE_UNIX_DAYS) * DAY).astype(np.int64)
    prices = np.asarray(used[:, [1, 3, 4, 2]])  # stored Open, Close, High, Low
    if (np.any(prices <= 0) or np.any(prices[:, 1] < np.maximum(prices[:, 0], prices[:, 3]))
            or np.any(prices[:, 2] > np.minimum(prices[:, 0], prices[:, 3]))):
        raise ValueError(f"Invalid OHLC: {symbol}")
    if np.any(np.diff(times) <= 0) or np.any(times % 60):
        raise ValueError(f"Duplicate, unsorted or off-grid timestamps: {symbol}")
    ratio = prices[1:, 3] / prices[:-1, 3]
    if np.any((ratio < .5) | (ratio > 1.5)):
        raise ValueError(f"Unresolved price scale discontinuity: {symbol}")
    # The direct M1->daily reduction equals M1->5m->daily for these OHLC fields.
    # Keep source first/last timestamps so the availability condition is auditable.
    daily = aggregate_daily(times, prices)
    keep = daily.dates < timestamp(end)  # Sunday before cutoff can label Monday cutoff.
    daily = DailyData(*(getattr(daily, name)[keep] for name in ("dates", "ohlc", "first", "last", "counts")))
    metadata = repository.metadata(symbol)
    if metadata.commission_per_lot != 0:
        raise ValueError("Nonzero metadata commission requires a new execution specification")
    pip = .01 if symbol.endswith("JPY") else .0001
    after = {"size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
    if before != after:
        raise ValueError("Source history changed during read")
    manifest = {"symbol": symbol, "path": str(path), "before": before, "after": after,
                "source_rows": len(used), "source_sha256": hashlib.sha256(memoryview(used)).hexdigest(),
                "first_raw_timestamp": iso(times[0]), "last_raw_timestamp": iso(times[-1]),
                "daily_bars": len(daily.dates), "first_trading_date": iso(daily.dates[0]),
                "last_trading_date": iso(daily.dates[-1]), "excluded_end_label_days": int((~keep).sum()),
                "metadata": metadata.values, "pip": pip, "metadata_spread_pips": metadata.spread_price / pip,
                "daily_sha256": hashlib.sha256(b"".join(getattr(daily, n).tobytes() for n in
                    ("dates", "ohlc", "first", "last", "counts"))).hexdigest()}
    return daily, manifest


def indicators(ohlc: np.ndarray):
    close = ohlc[:, 3]
    dma = np.full(len(close), np.nan)
    for i in range(5, len(close)):
        dma[i] = close[i-5:i-2].mean()
    tr = ohlc[:, 1] - ohlc[:, 2]
    if len(close) > 1:
        tr[1:] = np.maximum(tr[1:], np.maximum(abs(ohlc[1:, 1] - close[:-1]), abs(ohlc[1:, 2] - close[:-1])))
    atr = np.full(len(close), np.nan)
    if len(close) >= 14:
        atr[13] = tr[:14].mean()
        for i in range(14, len(close)):
            atr[i] = (13 * atr[i-1] + tr[i]) / 14
    return dma, atr


def generate_signals(ohlc: np.ndarray, dma: np.ndarray, atr: np.ndarray, candidate: dict,
                     first_index: int, end_index: int, warmup: int = 30):
    """Pure finite-state signal engine; output contains only information available at close."""
    signals = np.zeros(len(ohlc), dtype=np.int8)
    stops = np.full(len(ohlc), np.nan)
    prep = np.full(len(ohlc), -1, dtype=np.int64)
    thrust = candidate["thrust"]
    # Each tuple is initial adverse-cross index, preceding thrust start, returned flag.
    states = {1: None, -1: None}
    for i in range(max(first_index, warmup - 1, thrust), end_index):
        if not np.isfinite(dma[i]) or not np.isfinite(atr[i]):
            continue
        possibilities = []
        if candidate["kind"] == "cross":
            if ohlc[i-1, 3] <= dma[i-1] and ohlc[i, 3] > dma[i]:
                possibilities.append((1, i-thrust+1))
            if ohlc[i-1, 3] >= dma[i-1] and ohlc[i, 3] < dma[i]:
                possibilities.append((-1, i-thrust+1))
        else:
            for direction in (1, -1):
                adverse = direction * (ohlc[i, 3] - dma[i]) > 0
                original = direction * (ohlc[i, 3] - dma[i]) < 0
                state = states[direction]
                if state is not None and i - state[0] > candidate["expiry"]:
                    state = states[direction] = None
                if state is not None:
                    crossed, begin, returned = state
                    if i > crossed and returned and adverse:
                        possibilities.append((direction, begin))
                        states[direction] = None
                    elif i > crossed and original:
                        states[direction] = (crossed, begin, True)
                elif adverse and np.all(direction * (ohlc[i-thrust:i, 3] - dma[i-thrust:i]) < 0):
                    states[direction] = (i, i-thrust, False)
        if len(possibilities) == 1:
            direction, begin = possibilities[0]
            extreme = ohlc[begin:i+1, 2].min() if direction == 1 else ohlc[begin:i+1, 1].max()
            signals[i] = direction
            stops[i] = extreme - direction * .1 * atr[i]
            prep[i] = begin
    return signals, stops, prep


def exit_fill(direction: int, entry: float, stop: float, target: float, bar: np.ndarray):
    op, hi, lo, _ = bar
    if direction * (op - stop) <= 0:
        return float(op), "stop_gap"
    if direction * (op - target) >= 0:
        return float(target), "target_gap_capped"
    stop_hit = lo <= stop if direction == 1 else hi >= stop
    target_hit = hi >= target if direction == 1 else lo <= target
    if stop_hit:
        return float(stop), "both_stop_first" if target_hit else "stop"
    if target_hit:
        return float(target), "target"
    return None


def simulate(data: DailyData, candidate: dict, start: int, end: int, pip: float, cost: float,
             warmup: int = 30):
    """Next-bar fills and strict gross 1R full exits; no boundary force liquidation."""
    first, last = np.searchsorted(data.dates, [start, end], side="left")
    dma, atr = indicators(data.ohlc)
    signals, stops, preps = generate_signals(data.ohlc, dma, atr, candidate, int(first), int(last), warmup)
    trades = []
    pending = position = None
    cancelled = ignored = 0
    equity = []
    realized = 0.0
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
                    raise AssertionError("Signal not available before entry")
                position = {"direction": int(direction), "prep_index": int(begin), "signal_index": int(signal),
                    "entry_index": int(i), "entry": entry, "stop": float(stop), "target": entry + direction * risk,
                    "risk_pips": float(risk / pip), "cost_pips": float(cost),
                    "signal_trading_date": iso(data.dates[signal]), "signal_raw_last_timestamp": iso(data.last[signal]),
                    "signal_available_timestamp": iso(data.last[signal] + 60),
                    "entry_trading_date": iso(data.dates[i]), "entry_raw_first_timestamp": iso(data.first[i])}
        if position is not None:
            p = position
            fill = exit_fill(p["direction"], p["entry"], p["stop"], p["target"], data.ohlc[i])
            if fill is not None:
                price, reason = fill
                net_pips = p["direction"] * (price - p["entry"]) / pip - cost
                net_r = net_pips / p["risk_pips"]
                trades.append({**p, "exit_index": int(i), "exit_trading_date": iso(data.dates[i]),
                    "exit_raw_first_timestamp": iso(data.first[i]), "exit_raw_last_timestamp": iso(data.last[i]),
                    "exit_price": price, "reason": reason, "net_pips": net_pips, "net_r": net_r,
                    "holding_calendar_days": int((data.first[i] - data.first[p["entry_index"]]) // DAY)})
                realized += net_r
                position, exited = None, True
        open_r = 0.0
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
        marked = {**p, "mark_trading_date": iso(data.dates[last-1]), "mark_raw_last_timestamp": iso(data.last[last-1]),
                  "mark_price": price, "net_pips": net_pips, "net_r": net_pips / p["risk_pips"]}
    diagnostics = {"open_count": int(marked is not None), "open_net_r": marked["net_r"] if marked else 0.0,
                   "open_position": marked, "cancelled_at_open": cancelled, "ignored_signals": ignored,
                   "pending_at_end": int(pending is not None), "signal_count": int(np.count_nonzero(signals))}
    return trades, diagnostics, np.asarray(equity, dtype=float).reshape((-1, 3))


def drawdown(values):
    curve = np.r_[0., np.cumsum(values)]
    return float(np.max(np.maximum.accumulate(curve) - curve))


def distribution(values):
    values = np.asarray(values, dtype=float)
    wins, losses = values[values > 0], values[values < 0]
    profit, loss = float(wins.sum()), float(-losses.sum())
    return {"trades": len(values), "wins": len(wins), "losses": len(losses),
            "win_rate_pct": float(100 * len(wins) / len(values)) if len(values) else None,
            "pf": profit / loss if loss else None, "gross_profit_r": profit, "gross_loss_r": loss,
            "net_r": float(values.sum()), "average_net_r": float(values.mean()) if len(values) else None}


def summarize(trades, diagnostics, equity):
    values = [t["net_r"] for t in trades]
    result = distribution(values)
    changes = {}
    for t in trades:
        changes[t["exit_trading_date"]] = changes.get(t["exit_trading_date"], 0.) + t["net_r"]
    result.update({"closed_drawdown_r": drawdown([changes[k] for k in sorted(changes)]),
                   "mtm_drawdown_r": drawdown(np.diff(np.r_[0., equity[:, 2]])) if len(equity) else 0.,
                   "net_pips": float(sum(t["net_pips"] for t in trades)),
                   "open_count": diagnostics["open_count"], "open_net_r": diagnostics["open_net_r"],
                   "boundary_force_close_sensitivity": distribution(values + ([diagnostics["open_net_r"]] if diagnostics["open_count"] else []))})
    return result


def combine(evaluations):
    trades = [t for item in evaluations for t in item["trades"]]
    diagnostics = {"open_count": sum(item["diagnostics"]["open_count"] for item in evaluations),
                   "open_net_r": sum(item["diagnostics"]["open_net_r"] for item in evaluations)}
    changes, daily_mtm = {}, {}
    for item in evaluations:
        previous = 0.
        for date, _, marked in item["equity"]:
            daily_mtm[date] = daily_mtm.get(date, 0.) + marked - previous
            previous = marked
        for t in item["trades"]:
            changes[t["exit_trading_date"]] = changes.get(t["exit_trading_date"], 0.) + t["net_r"]
    result = distribution([t["net_r"] for t in trades])
    result.update({"closed_drawdown_r": drawdown([changes[k] for k in sorted(changes)]),
        "mtm_drawdown_r": drawdown([daily_mtm[k] for k in sorted(daily_mtm)]),
        "largest_single_symbol_closed_drawdown_r": max(i["summary"]["closed_drawdown_r"] for i in evaluations),
        "profitable_symbols": sum(i["summary"]["net_r"] > 0 for i in evaluations), **diagnostics,
        "boundary_force_close_sensitivity": distribution([t["net_r"] for t in trades] +
            [i["diagnostics"]["open_net_r"] for i in evaluations if i["diagnostics"]["open_count"]])})
    return result


def gate(summary, thresholds, gates):
    failures = []
    if summary["trades"] < thresholds["minimum_trades"]:
        failures.append("insufficient_trades")
    # No-loss finite sample passes the PF requirement only if positive gross profit exists.
    pf_ok = summary["pf"] >= thresholds["minimum_pf"] if summary["pf"] is not None else summary["gross_profit_r"] > 0
    if not pf_ok:
        failures.append("pf")
    if summary["average_net_r"] is None or summary["average_net_r"] <= thresholds["minimum_average_net_r_exclusive"]:
        failures.append("average_net_r")
    if summary["closed_drawdown_r"] > gates["maximum_aggregate_closed_drawdown_r"]:
        failures.append("aggregate_drawdown")
    if summary["largest_single_symbol_closed_drawdown_r"] > gates["maximum_single_symbol_closed_drawdown_r"]:
        failures.append("single_symbol_drawdown")
    if "minimum_profitable_symbols" in thresholds and summary["profitable_symbols"] < thresholds["minimum_profitable_symbols"]:
        failures.append("profitable_symbols")
    return {"passed": not failures, "failures": failures}


def run(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    dump(output / "protocol.json", protocol)
    dependencies = [SPEC, SPEC.with_name("hypothesis.md"), Path(__file__), ROOT / "src/forextester_backtest/data.py", ROOT / "src/forextester_backtest/models.py"]
    frozen = {"frozen_before_simulation_utc": datetime.now(timezone.utc).isoformat(),
              "sha256": {str(p.relative_to(ROOT)): sha(p) for p in dependencies}}
    dump(output / "code_input_hashes.json", frozen)
    repository = HistoryRepository(protocol["history_directory"])
    inputs, manifests = {}, []
    for symbol in protocol["symbols"]:
        print("LOAD", symbol, flush=True)
        data, manifest = load_daily(repository, symbol, protocol["warmup_start"], protocol["periods"]["final_confirmation"][1])
        np.savez_compressed(output / f"{symbol}_daily.npz", dates=data.dates, ohlc=data.ohlc,
            raw_first_timestamp=data.first, raw_last_timestamp=data.last, source_counts=data.counts)
        inputs[symbol] = (data, manifest["pip"], {"fixed_1p4": 1.4, "metadata_spread": manifest["metadata_spread_pips"]})
        manifests.append(manifest)
    dump(output / "data_manifest.json", manifests)
    rows, totals, decisions, selected = [], {}, {}, []
    gates = protocol["acceptance_gates"]
    per_symbol = {}

    def evaluate(candidate, period):
        bounds = protocol["periods"][period]
        collected = {"fixed_1p4": [], "metadata_spread": []}
        for symbol, (data, pip, costs) in inputs.items():
            for cost_name, cost in costs.items():
                trades, diagnostics, equity = simulate(data, candidate, timestamp(bounds[0]), timestamp(bounds[1]), pip, cost,
                                                       protocol["minimum_warmup_bars"])
                summary = summarize(trades, diagnostics, equity)
                name = f"{candidate['id']}__{period}__{symbol}__{cost_name}"
                dump(output / f"{name}.json", {"trades": trades, "diagnostics": diagnostics, "summary": summary})
                np.savez_compressed(output / f"{name}_equity.npz", equity=equity)
                rows.append({"candidate": candidate["id"], "period": period, "symbol": symbol,
                             "cost_case": cost_name, "cost_pips": cost, "artifact": f"{name}.json", **summary})
                per_symbol[(candidate["id"], period, cost_name, symbol)] = summary
                collected[cost_name].append({"trades": trades, "diagnostics": diagnostics, "equity": equity, "summary": summary})
        totals.setdefault(candidate["id"], {})[period] = {case: combine(items) for case, items in collected.items()}
        print("COMPLETE", candidate["id"], period, flush=True)
        return totals[candidate["id"]][period]

    for candidate in protocol["search_space"]:
        evaluate(candidate, "training")
    dump(output / "training_results.json", {"totals": totals, "rows": rows})
    for candidate in protocol["search_space"]:
        if not candidate["eligible"]:
            continue
        cid = candidate["id"]
        decisions[cid] = {"training": {case: gate(summary, gates["training"], gates)
            for case, summary in totals[cid]["training"].items()}}
        if not all(d["passed"] for d in decisions[cid]["training"].values()):
            continue
        evaluate(candidate, "validation")
        decisions[cid]["validation"] = {case: gate(summary, gates["validation"], gates)
            for case, summary in totals[cid]["validation"].items()}
        for case, decision in decisions[cid]["validation"].items():
            profitable = sum(per_symbol[(cid, "training", case, s)]["net_r"] +
                             per_symbol[(cid, "validation", case, s)]["net_r"] > 0 for s in protocol["symbols"])
            decision["training_plus_validation_profitable_symbols"] = profitable
            if profitable < gates["training_plus_validation_minimum_profitable_symbols"]:
                decision["failures"].append("joint_profitable_symbols")
                decision["passed"] = False
        if all(d["passed"] for d in decisions[cid]["validation"].values()):
            selected.append(cid)
    dump(output / "selection_before_final.json", {"saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected": selected, "decisions": decisions, "protocol_sha256": sha(SPEC)})
    for candidate in protocol["search_space"]:
        if candidate["id"] in selected:
            evaluate(candidate, "final_confirmation")
            decisions[candidate["id"]]["final_confirmation"] = {case: gate(summary, gates["final_confirmation"], gates)
                for case, summary in totals[candidate["id"]]["final_confirmation"].items()}
    passed = [cid for cid in selected if all(d["passed"] for d in decisions[cid]["final_confirmation"].values())]
    result = {"status": "RESEARCH_GATES_PASSED_AWAITING_INDEPENDENT_VALIDATION" if passed else "REJECTED_BY_FROZEN_GATES",
        "selected_for_final": selected, "passed_research_gates": passed, "totals": totals, "rows": rows,
        "decisions": decisions, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "prior_exposure": protocol["final_period_prior_exposure"], "adoption_approved": False}
    # Detect implementation/spec mutation during simulation; outputs are invalid if hashes drift.
    if frozen["sha256"] != {str(p.relative_to(ROOT)): sha(p) for p in dependencies}:
        raise ValueError("Frozen code or protocol changed during run")
    dump(output / "results.json", result)
    print("RESULT_JSON=" + json.dumps({"status": result["status"], "selected": selected, "passed": passed,
                                       "output": str(output)}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    run(parser.parse_args().output)
