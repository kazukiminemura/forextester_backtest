"""Frozen Holy Grail interpretation. Pure signals, data, fills and scoring separated."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np

from forextester_backtest.data import HistoryRepository, _RecordFile, BAR_STRUCT
from scripts.research_dinapoli_3x3_daily import DailyData, timestamp, iso, sha, dump, DAY, OLE_UNIX_DAYS
from scripts.research_daily_edge_reset import summarize, combine, gate, charged_days

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/quant_organization/experiments/holy_grail_first_pullback_20260913/protocol.json"
OUT = ROOT / "agent_runs/holy_grail_first_pullback_20260913/completed"


def aggregate(times, prices, minutes):
    width = minutes * 60
    labels = times // width * width
    starts = np.r_[0, np.flatnonzero(np.diff(labels)) + 1]
    ends = np.r_[starts[1:]-1, len(times)-1]
    bars = np.column_stack((prices[starts, 0], np.maximum.reduceat(prices[:, 1], starts),
                            np.minimum.reduceat(prices[:, 2], starts), prices[ends, 3]))
    return DailyData(labels[starts], bars, times[starts], times[ends], ends-starts+1)


def load_symbol(repository, symbol, start, end):
    """Read-only bounded source prefix; no later-period prices are loaded."""
    path = repository._symbol_dir(symbol) / "Bars.dat"
    before = [path.stat().st_size, path.stat().st_mtime_ns]
    count = _RecordFile(path, BAR_STRUCT.size).count()
    raw = np.memmap(path, mode="r", dtype="<f8", offset=4, shape=(count, 6))
    lo, hi = np.searchsorted(raw[:, 0], [timestamp(start)/DAY+OLE_UNIX_DAYS,
                                        timestamp(end)/DAY+OLE_UNIX_DAYS])
    used = raw[lo:hi]
    if not len(used) or not np.isfinite(used[:, :5]).all():
        raise ValueError(f"empty/nonfinite source {symbol}")
    times = np.rint((used[:, 0]-OLE_UNIX_DAYS)*DAY).astype(np.int64)
    prices = np.asarray(used[:, [1, 3, 4, 2]])
    if (np.any(np.diff(times)<=0) or np.any(times%60) or np.any(prices<=0)
            or np.any(prices[:, 1]<np.maximum(prices[:, 0], prices[:, 3]))
            or np.any(prices[:, 2]>np.minimum(prices[:, 0], prices[:, 3]))):
        raise ValueError(f"invalid source time/OHLC {symbol}")
    ratios = prices[1:, 3]/prices[:-1, 3]
    if np.any((ratios<.5)|(ratios>1.5)):
        raise ValueError(f"price scale discontinuity {symbol}")
    m = repository.metadata(symbol)
    if m.commission_per_lot != 0:
        raise ValueError("nonzero commission unsupported by frozen specification")
    pip = .01 if symbol.endswith("JPY") else .0001
    point = 10.**(-m.decimals)
    if not np.isfinite(point) or point<=0:
        raise ValueError("invalid metadata point")
    datasets = {n: aggregate(times, prices, n) for n in (60, 240)}
    manifest = {"symbol": symbol, "path": str(path), "source_rows": len(used),
                "source_sha256": hashlib.sha256(memoryview(used)).hexdigest(),
                "first_raw": iso(times[0]), "last_raw": iso(times[-1]),
                "before": before, "after": [path.stat().st_size, path.stat().st_mtime_ns],
                "pip": pip, "point": point, "metadata_spread_pips": m.spread_price/pip,
                "metadata": m.values, "aggregates": {}, "period_prefix_sha256": {}}
    for boundary in ("2019-01-01", "2023-01-01", "2026-08-31"):
        if boundary<=end:
            index = np.searchsorted(times, timestamp(boundary))
            manifest["period_prefix_sha256"][boundary] = hashlib.sha256(memoryview(used[:index])).hexdigest()
    if manifest["before"] != manifest["after"]:
        raise ValueError("source changed during read")
    for n, data in datasets.items():
        manifest["aggregates"][str(n)] = {"bars": len(data.dates),
            "incomplete_buckets": int(np.sum(data.counts<n)),
            "sha256": hashlib.sha256(b"".join(getattr(data, k).tobytes() for k in
                                   ("dates", "ohlc", "first", "last", "counts"))).hexdigest()}
    return datasets, manifest


def indicators(ohlc):
    """EMA seed first close, exact Wilder seeds documented for Python/Pine parity."""
    n = len(ohlc)
    ema, adx = np.full(n, np.nan), np.full(n, np.nan)
    plus, minus = np.full(n, np.nan), np.full(n, np.nan)
    if not n:
        return {"ema": ema, "adx": adx, "plus": plus, "minus": minus}
    ema[0] = ohlc[0, 3]
    for i in range(1, n):
        ema[i] = ema[i-1]+2/21*(ohlc[i, 3]-ema[i-1])
    tr = ohlc[:, 1]-ohlc[:, 2]
    tr[1:] = np.maximum(tr[1:], np.maximum(abs(ohlc[1:, 1]-ohlc[:-1, 3]), abs(ohlc[1:, 2]-ohlc[:-1, 3])))
    up, down = np.diff(ohlc[:, 1]), -np.diff(ohlc[:, 2])
    pdm, mdm = np.r_[0., np.where((up>down)&(up>0), up, 0.)], np.r_[0., np.where((down>up)&(down>0), down, 0.)]
    dx = np.full(n, np.nan)
    if n>=15:
        t, p, m = tr[1:15].mean(), pdm[1:15].mean(), mdm[1:15].mean()
        for i in range(14, n):
            if i>14:
                t, p, m = (13*t+tr[i])/14, (13*p+pdm[i])/14, (13*m+mdm[i])/14
            plus[i], minus[i] = (100*p/t, 100*m/t) if t else (0., 0.)
            dx[i] = 100*abs(plus[i]-minus[i])/(plus[i]+minus[i]) if plus[i]+minus[i] else 0.
    if n>=28:
        adx[27] = dx[14:28].mean()
        for i in range(28, n):
            adx[i] = (13*adx[i-1]+dx[i])/14
    return {"ema": ema, "adx": adx, "plus": plus, "minus": minus}


def generate_setups(ohlc, f, first, last, first_only, point, warmup=250):
    """Decision stream is independent of fills. Every first touch consumes entitlement."""
    setups, resets, events = {}, set(), []
    direction, arm, anchor, spent = 0, -1, -1, False
    for i in range(max(first, warmup-1, 1), last):
        adx, ema = f["adx"][i], f["ema"][i]
        dominance = 1 if f["plus"][i]>f["minus"][i] else -1 if f["minus"][i]>f["plus"][i] else 0
        if direction and (adx<25 or dominance!=direction):
            events.append({"index": i, "event": "reset", "arm": arm})
            resets.add(i)
            direction = 0
        if not direction:
            if (f["adx"][i-1]<=30<adx and dominance and dominance*(ohlc[i, 3]-ema)>0):
                direction, arm, anchor, spent = dominance, i, i, False
                events.append({"index": i, "event": "arm", "direction": direction})
            continue
        touch = ohlc[i, 2]<=ema<=ohlc[i, 1]
        away = ohlc[i-1, 2]>f["ema"][i-1] if direction==1 else ohlc[i-1, 1]<f["ema"][i-1]
        if touch:
            entitled = not spent if first_only else True
            if not spent:
                events.append({"index": i, "event": "first_touch_consumed", "arm": arm})
            spent = True
            if entitled and away and direction*(ohlc[i, 3]-ema)>0:
                begin = min(anchor+1, i)
                extreme = float(ohlc[begin:i+1, 2].min() if direction==1 else ohlc[begin:i+1, 1].max())
                trigger = float(ohlc[i, 1]+point if direction==1 else ohlc[i, 2]-point)
                stop = extreme-direction*point
                setups[i] = {"direction": direction, "signal_index": i, "arm_index": arm,
                             "pullback_start_index": begin, "anchor_index": anchor,
                             "trigger": trigger, "stop": stop}
        if (direction==1 and ohlc[i, 1]>=ohlc[anchor, 1]) or (direction==-1 and ohlc[i, 2]<=ohlc[anchor, 2]):
            anchor = i
    return setups, resets, events


def entry_fill(order, bar):
    d, trigger, stop = order["direction"], order["trigger"], order["stop"]
    op, hi, lo, _ = bar
    if d*(op-stop)<=0:
        return "cancel", None, True
    if d*(op-trigger)>=0:
        return "fill", float(op), True
    if (hi>=trigger if d==1 else lo<=trigger):
        return "fill", float(trigger), False
    return "wait", None, False


def exit_fill(p, bar, fresh=False):
    d, stop, target = p["direction"], p["stop"], p["target"]
    op, hi, lo, _ = bar
    if not fresh and d*(op-stop)<=0:
        return float(op), "stop_gap", True
    if not fresh and d*(op-target)>=0:
        return float(target), "target_gap_capped", True
    sh, th = (lo<=stop, hi>=target) if d==1 else (hi>=stop, lo<=target)
    if sh:
        return float(stop), "both_stop_first" if th else "stop", False
    if th:
        return float(target), "target", False
    return None


def simulate(data, f, candidate, start, end, pip, point, cost, carry=.2, warmup=250):
    first, last = np.searchsorted(data.dates, [start, end])
    setups, resets, events = generate_setups(data.ohlc, f, first, last, candidate["first_only"], point, warmup)
    width = candidate["minutes"]*60
    pending, p, realized = None, None, 0.
    trades, equity, orders = [], [], []
    for i in range(first, last):
        fresh, exited = False, False
        if pending is not None:
            action, entry, at_open = entry_fill(pending, data.ohlc[i])
            if action=="cancel":
                orders.append({"signal_index": pending["signal_index"], "index": i, "event": "cancel_stop_gap"})
                pending = None
            elif action=="fill":
                d = pending["direction"]
                risk = d*(entry-pending["stop"])
                if risk<=0: raise ValueError("nonpositive risk")
                p = {**pending, "entry_index": i, "entry": entry, "risk": risk,
                     "target": entry+d*risk, "entry_timestamp": int(data.first[i]),
                     "entry_fill_timestamp_bound": int(data.first[i] if at_open else data.dates[i]+width),
                     "signal_timestamp": int(data.dates[pending["signal_index"]]+width),
                     "entry_date": iso(data.dates[i]), "entry_at_open": at_open}
                if p["entry_timestamp"]<p["signal_timestamp"]: raise ValueError("unavailable signal")
                orders.append({"signal_index": pending["signal_index"], "index": i, "event": "filled"})
                pending, fresh = None, True
            elif i-pending["signal_index"]>=3:
                orders.append({"signal_index": pending["signal_index"], "index": i, "event": "expired"})
                pending = None
        if p is not None:
            fill = exit_fill(p, data.ohlc[i], fresh)
            if fill is None and i==last-1:
                fill = float(data.ohlc[i, 3]), "period_boundary", False
            if fill is not None:
                price, reason, at_open = fill
                exposure = int(data.first[i] if at_open else data.dates[i]+width)
                days = charged_days(p["entry_timestamp"], exposure)
                gross, fee, holding = p["direction"]*(price-p["entry"])/p["risk"], cost*pip/p["risk"], carry*days*pip/p["risk"]
                trade = {**p, "exit_index": i, "exit_date": iso(data.dates[i]), "exit_price": price,
                         "exit_exposure_timestamp": exposure, "reason": reason, "carry_days": days,
                         "holding_bars": i-p["entry_index"]+1, "risk_pips": p["risk"]/pip,
                         "gross_r": gross, "fee_r": fee, "carry_r": holding, "net_r": gross-fee-holding,
                         "net_zero_carry_r": gross-fee, "net_one_carry_r": gross-fee-days*pip/p["risk"]}
                trades.append(trade)
                realized += trade["net_r"]
                p, exited = None, True
        if i in resets and pending is not None:
            orders.append({"signal_index": pending["signal_index"], "index": i, "event": "cancel_episode_reset_at_close"})
            pending = None
        mark = 0.
        if p is not None:
            days = charged_days(p["entry_timestamp"], data.dates[i]+width)
            mark = (p["direction"]*(data.ohlc[i, 3]-p["entry"])-(cost+carry*days)*pip)/p["risk"]
        equity.append([int(data.dates[i]+width), realized, realized+mark])
        if i in setups:
            if p is None and pending is None and not exited and i<last-1:
                pending = setups[i]
                orders.append({"signal_index": i, "index": i, "event": "submitted_at_close"})
            else:
                orders.append({"signal_index": i, "index": i, "event": "skipped_occupied_exit_or_boundary"})
    if pending is not None:
        orders.append({"signal_index": pending["signal_index"], "index": int(last-1), "event": "cancel_period_boundary"})
    return trades, np.asarray(equity).reshape((-1, 3)), {"episodes": events, "orders": orders}


def baseline_gate(summary, baseline, decision):
    result = {"passed": decision["passed"], "failures": decision["failures"].copy()}
    def pf(s):
        return s["pf"] if s["pf"] is not None else (float("inf") if s["profit_r"]>0 else 0.)
    if pf(summary)<=pf(baseline): result["failures"].append("baseline_pf_not_improved")
    if summary["average_net_r"]<=baseline["average_net_r"]: result["failures"].append("baseline_mean_r_not_improved")
    result["passed"] = not result["failures"]
    return result


def run(output, phase="training"):
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    deps = [SPEC, SPEC.with_name("hypothesis.md"), Path(__file__), ROOT/"tests/test_holy_grail_first_pullback.py",
            ROOT/"scripts/research_daily_edge_reset.py", ROOT/"scripts/research_dinapoli_3x3_daily.py",
            ROOT/"src/forextester_backtest/data.py", ROOT/"src/forextester_backtest/models.py"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in deps}
    if phase=="training":
        output.mkdir(parents=True, exist_ok=False)
        dump(output/"protocol.json", protocol)
        dump(output/"code_input_hashes.json", {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "sha256": hashes})
        result = {"totals": {}, "decisions": {}, "rows": [], "selected": "", "phase": "training", "adoption_approved": False}
        candidates = protocol["search_space"]
    else:
        frozen = json.loads((output/"code_input_hashes.json").read_text(encoding="utf-8"))
        if hashes!=frozen["sha256"]: raise ValueError("frozen code/spec drift")
        result = json.loads((output/"results.json").read_text(encoding="utf-8"))
        previous = "training" if phase=="validation" else "validation"
        if not result["selected"] or result["phase"]!=previous: raise ValueError("phase order/no selection")
        if not all(x["passed"] for x in result["decisions"][result["selected"]][previous].values()): raise ValueError("previous rejection")
        chosen = next(c for c in protocol["search_space"] if c["id"]==result["selected"])
        candidates = [c for c in protocol["search_space"] if c["id"] in (chosen["id"], chosen["baseline"])]
    costs = ("fixed_1p8", "metadata_plus_0p4")
    collected = {c["id"]: {k: [] for k in costs} for c in candidates}
    manifests = []
    repository = HistoryRepository(Path(protocol["history_directory"]))
    for symbol in protocol["symbols"]:
        datasets, manifest = load_symbol(repository, symbol, protocol["indicator_start"], protocol["periods"][phase][1])
        if phase!="training":
            previous_manifest = json.loads((output/f"{previous}_data_manifest.json").read_text(encoding="utf-8"))
            old = next(m for m in previous_manifest if m["symbol"]==symbol)
            boundary = protocol["periods"][previous][1]
            if manifest["period_prefix_sha256"][boundary]!=old["source_sha256"] or manifest["metadata"]!=old["metadata"]:
                raise ValueError("previously frozen source prefix/metadata drift")
        manifests.append(manifest)
        features = {n: indicators(data.ohlc) for n, data in datasets.items()}
        for n, data in datasets.items():
            np.savez_compressed(output/f"{phase}__{symbol}__{n}_bars.npz", dates=data.dates, ohlc=data.ohlc,
                                first=data.first, last=data.last, counts=data.counts)
        for c in candidates:
            for case in costs:
                cost = 1.8 if case=="fixed_1p8" else manifest["metadata_spread_pips"]+.4
                trades, equity, diagnostics = simulate(datasets[c["minutes"]], features[c["minutes"]], c,
                    *map(timestamp, protocol["periods"][phase]), manifest["pip"], manifest["point"], cost,
                    protocol["cost_and_fill_model"]["primary_carry_pips_per_calendar_day"], protocol["minimum_warmup_bars"])
                summary = summarize(trades, equity)
                name = f"{c['id']}__{phase}__{symbol}__{case}"
                dump(output/f"{name}.json", {"trades": trades, "summary": summary, "diagnostics": diagnostics})
                np.savez_compressed(output/f"{name}_equity.npz", equity=equity)
                collected[c["id"]][case].append({"trades": trades, "equity": equity, "summary": summary})
                result["rows"].append({"candidate": c["id"], "period": phase, "symbol": symbol, "case": case, "artifact": name+".json", **summary})
        print("COMPLETE", phase, symbol, flush=True)
    dump(output/f"{phase}_data_manifest.json", manifests)
    for c in candidates:
        totals, decisions = {}, {}
        for case, items in collected[c["id"]].items():
            totals[case], equity = combine(items, protocol)
            decisions[case] = gate(totals[case], phase, protocol)
            np.savez_compressed(output/f"{c['id']}__{phase}__{case}_aggregate_equity.npz", equity=equity)
        result["totals"].setdefault(c["id"], {})[phase] = totals
        result["decisions"].setdefault(c["id"], {})[phase] = decisions
    if phase in ("training", "validation"):
        for c in candidates:
            if c["eligible"]:
                for case in costs:
                    result["decisions"][c["id"]][phase][case] = baseline_gate(
                        result["totals"][c["id"]][phase][case], result["totals"][c["baseline"]][phase][case],
                        result["decisions"][c["id"]][phase][case])
    if phase=="training":
        passing = [c["id"] for c in candidates if c["eligible"] and all(x["passed"] for x in result["decisions"][c["id"]][phase].values())]
        def rank(cid):
            values = list(result["totals"][cid][phase].values())
            return (-min(v["pf"] if v["pf"] is not None else float("inf") for v in values), -min(v["average_net_r"] for v in values), max(v["mtm_drawdown_r"] for v in values), cid)
        result["selected"] = sorted(passing, key=rank)[0] if passing else ""
        dump(output/"selection_before_validation.json", {"saved_at_utc": datetime.now(timezone.utc).isoformat(), "selected": result["selected"], "passing": passing})
    result["phase"] = phase
    passed = bool(result["selected"]) and all(x["passed"] for x in result["decisions"][result["selected"]][phase].values())
    result["status"] = "PHASE_PASSED_AWAITING_INDEPENDENT_REVIEW" if passed else "REJECTED_BY_FROZEN_GATES"
    result["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    if hashes!={str(p.relative_to(ROOT)): sha(p) for p in deps}: raise ValueError("code/spec drift during run")
    dump(output/"results.json", result)
    dump(output/f"{phase}_results.json", result)
    print("RESULT_JSON="+json.dumps({"status": result["status"], "selected": result["selected"], "phase": phase, "output": str(output)}), flush=True)
    return result


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--phase", choices=("training", "validation", "final_confirmation"), default="training")
    args = parser.parse_args()
    run(args.output, args.phase)
