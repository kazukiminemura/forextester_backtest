"""Preregistered daily FX hypotheses. Pure decisions, execution and scoring separated."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np

from scripts.research_dinapoli_3x3_daily import DailyData, timestamp, iso, sha, dump, DAY

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/quant_organization/experiments/daily_edge_reset_20260910/protocol.json"
OUT = ROOT / "agent_runs/daily_edge_reset_20260910/completed"


def sma(values, n):
    out = np.full(len(values), np.nan)
    if len(values) >= n:
        cs = np.r_[0., np.cumsum(values)]
        out[n-1:] = (cs[n:] - cs[:-n]) / n
    return out


def features(ohlc):
    close = ohlc[:, 3]
    tr = ohlc[:, 1] - ohlc[:, 2]
    if len(close) > 1:
        tr[1:] = np.maximum(tr[1:], np.maximum(abs(ohlc[1:, 1]-close[:-1]), abs(ohlc[1:, 2]-close[:-1])))
    atr = np.full(len(close), np.nan)
    if len(close) >= 20:
        atr[19] = tr[:20].mean()
        for i in range(20, len(close)):
            atr[i] = (19 * atr[i-1] + tr[i]) / 20
    f = {"atr": atr, **{f"sma{n}": sma(close, n) for n in (20, 100, 200)}}
    for n in (10, 20, 50, 55, 100):
        high, low = np.full(len(close), np.nan), np.full(len(close), np.nan)
        for i in range(n, len(close)):
            high[i], low[i] = ohlc[i-n:i, 1].max(), ohlc[i-n:i, 2].min()
        f[f"high{n}"], f[f"low{n}"] = high, low
    return f


def signal(ohlc, f, c, i):
    """Information available at close i only; callers enforce shared warmup."""
    close, prev = ohlc[i, 3], ohlc[i-1, 3]
    family, k = c["family"], c["parameter"]
    if family == "trend":
        return 1 if close > f[f"high{int(k)}"][i] else -1 if close < f[f"low{int(k)}"][i] else 0
    if family == "baseline":
        return 1 if prev <= f["sma200"][i-1] and close > f["sma200"][i] else -1 if prev >= f["sma200"][i-1] and close < f["sma200"][i] else 0
    buy = prev <= f["sma20"][i-1]-k*f["atr"][i-1] and close > f["sma20"][i]-k*f["atr"][i]
    sell = prev >= f["sma20"][i-1]+k*f["atr"][i-1] and close < f["sma20"][i]+k*f["atr"][i]
    if family == "pullback":
        buy = buy and close > f["sma200"][i] and f["sma200"][i] > f["sma200"][i-20]
        sell = sell and close < f["sma200"][i] and f["sma200"][i] < f["sma200"][i-20]
    elif abs(f["sma100"][i]-f["sma100"][i-20]) >= .5*f["atr"][i]:
        return 0
    return 1 if buy and not sell else -1 if sell and not buy else 0


def close_decision(ohlc, f, c, i, p):
    d, close = p["direction"], ohlc[i, 3]
    if i - p["entry_index"] + 1 >= c["holding"]:
        return "holding_limit"
    if c["family"] == "range" and d*(close-f["sma20"][i]) >= 0:
        return "mean_recovered"
    if c["family"] == "trend":
        channel = f[f"low{c['exit_window']}"][i] if d == 1 else f[f"high{c['exit_window']}"][i]
        if d*(close-channel) < 0:
            return "opposite_channel"
    if c["family"] == "baseline" and d*(close-f["sma200"][i]) < 0:
        return "opposite_sma"
    return ""


def bar_fill(p, bar):
    """Open stop gaps precede queued open exits; intrabar stop before target."""
    op, hi, lo, _ = bar
    d, stop, target = p["direction"], p["stop"], p["target"]
    if d*(op-stop) <= 0:
        return float(op), "stop_gap", True
    if p["queued_exit"]:
        return float(op), p["queued_exit"], True
    if target is not None and d*(op-target) >= 0:
        return float(target), "target_gap_capped", True
    sh = lo <= stop if d == 1 else hi >= stop
    th = target is not None and (hi >= target if d == 1 else lo <= target)
    if sh:
        return float(stop), "both_stop_first" if th else "stop", False
    if th:
        return float(target), "target", False
    return None


def charged_days(entry_ts, exit_ts):
    return int(np.ceil(max(0, int(exit_ts)-int(entry_ts))/DAY))


def simulate(data, f, c, start, end, pip, cost, carry=.2, warmup=250):
    first, last = np.searchsorted(data.dates, [start, end], side="left")
    p, pending, realized = None, None, 0.
    trades, equity = [], []
    for i in range(first, last):
        exited = False
        if pending is not None:
            si, d = pending
            entry, risk = float(data.ohlc[i, 0]), float(2*f["atr"][si])
            p = {"direction": d, "signal_index": int(si), "entry_index": int(i),
                 "entry_timestamp": int(data.first[i]), "signal_timestamp": int(data.last[si]+60),
                 "entry_date": iso(data.dates[i]), "entry": entry, "risk": risk,
                 "stop": entry-d*risk, "initial_stop": entry-d*risk,
                 "target": entry+d*3*risk if c["family"] == "pullback" else None,
                 "extreme_close": None, "queued_exit": ""}
            if p["entry_timestamp"] < p["signal_timestamp"]:
                raise ValueError("signal not available at entry")
            pending = None
        if p is not None:
            fill = bar_fill(p, data.ohlc[i])
            if fill is None and i == last-1:
                fill = (float(data.ohlc[i, 3]), "period_boundary", False)
            if fill is not None:
                price, reason, at_open = fill
                exposure = int(data.first[i] if at_open else data.last[i]+60)
                days = charged_days(p["entry_timestamp"], exposure)
                gross = p["direction"]*(price-p["entry"])/p["risk"]
                fee = cost*pip/p["risk"]
                carry_r = carry*days*pip/p["risk"]
                trade = {**p, "exit_index": int(i), "exit_date": iso(data.dates[i]),
                         "exit_exposure_timestamp": exposure, "exit_price": price, "reason": reason,
                         "holding_bars": int(i-p["entry_index"]+1), "carry_days": days,
                         "gross_r": gross, "fee_r": fee, "carry_r": carry_r,
                         "net_r": gross-fee-carry_r, "risk_pips": p["risk"]/pip,
                         "net_zero_carry_r": gross-fee, "net_one_carry_r": gross-fee-days*pip/p["risk"]}
                trades.append(trade)
                realized += trade["net_r"]
                p, exited = None, True
        mark = 0.
        if p is not None:
            days = charged_days(p["entry_timestamp"], data.last[i]+60)
            mark = (p["direction"]*(data.ohlc[i, 3]-p["entry"])-(cost+carry*days)*pip)/p["risk"]
            p["queued_exit"] = close_decision(data.ohlc, f, c, i, p)
            if c["family"] in ("trend", "baseline"):
                d = p["direction"]
                if p["extreme_close"] is None:
                    p["extreme_close"] = float(data.ohlc[i, 3])
                else:
                    p["extreme_close"] = max(p["extreme_close"], data.ohlc[i, 3]) if d == 1 else min(p["extreme_close"], data.ohlc[i, 3])
                proposed = p["extreme_close"]-d*3*f["atr"][i]
                p["stop"] = float(max(p["stop"], proposed) if d == 1 else min(p["stop"], proposed))
        equity.append([int(data.dates[i]), realized, realized+mark])
        if i >= warmup-1 and i < last-1 and p is None and not exited and np.isfinite(f["atr"][i]) and f["atr"][i] > 0:
            d = signal(data.ohlc, f, c, i)
            if d:
                pending = (i, d)
    return trades, np.asarray(equity).reshape((-1, 3))


def distribution(values):
    values = np.asarray(values, float)
    gain, loss = float(values[values > 0].sum()), float(-values[values < 0].sum())
    return {"trades": len(values), "win_rate_pct": float(100*np.mean(values>0)) if len(values) else 0.,
            "pf": gain/loss if loss else None, "profit_r": gain, "loss_r": loss,
            "net_r": float(values.sum()), "average_net_r": float(values.mean()) if len(values) else 0.}


def mtm_dd(curve):
    curve = np.r_[0., curve]
    return float(np.max(np.maximum.accumulate(curve)-curve))


def summarize(trades, equity):
    out = distribution([t["net_r"] for t in trades])
    out.update({"gross": distribution([t["gross_r"] for t in trades]),
                "zero_carry": distribution([t["net_zero_carry_r"] for t in trades]),
                "one_pip_carry": distribution([t["net_one_carry_r"] for t in trades]),
                "without_boundary": distribution([t["net_r"] for t in trades if t["reason"] != "period_boundary"]),
                "mtm_drawdown_r": mtm_dd(equity[:, 2]) if len(equity) else 0.,
                "max_holding_bars": max((t["holding_bars"] for t in trades), default=0),
                "mean_carry_days": float(np.mean([t["carry_days"] for t in trades])) if trades else 0.,
                "boundary_trades": sum(t["reason"] == "period_boundary" for t in trades)})
    return out


def combine(items, protocol):
    trades = [t for item in items for t in item["trades"]]
    dates = sorted({int(row[0]) for item in items for row in item["equity"]})
    curve, realized = np.zeros(len(dates)), np.zeros(len(dates))
    for item in items:
        e = item["equity"]
        index = np.searchsorted(e[:, 0], dates, side="right")-1
        valid = index >= 0
        curve[valid] += e[index[valid], 2]
        realized[valid] += e[index[valid], 1]
    equity = np.column_stack((dates, realized, curve))
    out = summarize(trades, equity)
    out["profitable_symbols"] = sum(item["summary"]["net_r"] > 0 for item in items)
    out["max_single_symbol_mtm_drawdown_r"] = max(item["summary"]["mtm_drawdown_r"] for item in items)
    subs = []
    for lo, hi in protocol["acceptance_gates"]["training_subperiods"]:
        selected = [t["net_r"] for t in trades if lo <= int(t["exit_date"][:4]) <= hi]
        a, b = np.searchsorted(dates, [timestamp(f"{lo}-01-01"), timestamp(f"{hi+1}-01-01")])
        if b > a:
            base = curve[a-1] if a else 0.
            subs.append({"years": [lo, hi], "realized": distribution(selected),
                         "mtm_net_r": float(curve[b-1]-base),
                         "end_open_r": float(curve[b-1]-realized[b-1])})
    out["training_subperiods"] = subs
    return out, equity


def gate(summary, period, protocol):
    g, failures = protocol["acceptance_gates"], []
    thresholds = g[period]
    if summary["trades"] < thresholds["minimum_trades"]: failures.append("trades")
    pf = summary["pf"] if summary["pf"] is not None else (float("inf") if summary["profit_r"]>0 else 0.)
    if pf < thresholds["minimum_pf"]: failures.append("pf")
    if summary["average_net_r"] <= 0: failures.append("expectancy")
    if summary["profitable_symbols"] < thresholds["minimum_profitable_symbols"]: failures.append("symbol_breadth")
    if summary["mtm_drawdown_r"] > g["maximum_aggregate_daily_mtm_drawdown_r"]: failures.append("mtm_dd")
    if summary["max_single_symbol_mtm_drawdown_r"] > g["maximum_single_symbol_daily_mtm_drawdown_r"]: failures.append("single_symbol_mtm_dd")
    if period == "training" and (len(summary["training_subperiods"]) != 3 or any(s["realized"]["net_r"] <= 0 for s in summary["training_subperiods"])): failures.append("training_subperiods")
    return {"passed": not failures, "failures": failures}


def load_inputs(protocol):
    source = ROOT / protocol["cached_daily_directory"]
    manifests = json.loads((ROOT/protocol["data_manifest"]).read_text(encoding="utf-8"))
    inputs, identities = {}, {}
    for symbol in protocol["symbols"]:
        m = next(m for m in manifests if m["symbol"] == symbol)
        path = source/f"{symbol}_daily.npz"
        with np.load(path) as z:
            data = DailyData(*(z[k].copy() for k in ("dates", "ohlc", "raw_first_timestamp", "raw_last_timestamp", "source_counts")))
        actual = hashlib.sha256(b"".join(getattr(data,k).tobytes() for k in ("dates", "ohlc", "first", "last", "counts"))).hexdigest()
        if actual != m["daily_sha256"]:
            raise ValueError(f"daily hash mismatch {symbol}")
        inputs[symbol] = (data, features(data.ohlc), m["pip"], {"fixed_1p8": 1.8, "metadata_plus_0p4": m["metadata_spread_pips"]+.4})
        identities[symbol] = {"npz_sha256": sha(path), "daily_sha256": actual}
    return inputs, identities


def run(output, phase="training"):
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    inputs, identities = load_inputs(protocol)
    deps = [SPEC, SPEC.with_name("hypothesis.md"), Path(__file__), ROOT/"scripts/research_dinapoli_3x3_daily.py", ROOT/protocol["data_manifest"]]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in deps}
    if phase == "training":
        output.mkdir(parents=True, exist_ok=False)
        dump(output/"protocol.json", protocol)
        dump(output/"code_input_hashes.json", {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "sha256": hashes, "inputs": identities})
        result = {"totals": {}, "decisions": {}, "rows": [], "selected": "", "phase": "training", "adoption_approved": False}
        candidates = protocol["search_space"]
    else:
        frozen = json.loads((output/"code_input_hashes.json").read_text(encoding="utf-8"))
        if frozen["sha256"] != hashes or frozen["inputs"] != identities: raise ValueError("frozen input drift")
        result = json.loads((output/"results.json").read_text(encoding="utf-8"))
        previous = "training" if phase == "validation" else "validation"
        if not result["selected"] or result["phase"] != previous: raise ValueError("phase order or no selection")
        if not all(v["passed"] for v in result["decisions"][result["selected"]][previous].values()): raise ValueError("previous gate failed")
        candidates = [c for c in protocol["search_space"] if c["id"] == result["selected"]]
    for c in candidates:
        collected = {"fixed_1p8": [], "metadata_plus_0p4": []}
        for symbol, (data, f, pip, costs) in inputs.items():
            for case, cost in costs.items():
                trades, equity = simulate(data, f, c, *map(timestamp, protocol["periods"][phase]), pip, cost,
                                          protocol["cost_and_fill_model"]["primary_carry_pips_per_calendar_day"], protocol["minimum_warmup_bars"])
                summary = summarize(trades, equity)
                name = f"{c['id']}__{phase}__{symbol}__{case}"
                dump(output/f"{name}.json", {"trades": trades, "summary": summary})
                np.savez_compressed(output/f"{name}_equity.npz", equity=equity)
                collected[case].append({"trades": trades, "equity": equity, "summary": summary})
                result["rows"].append({"candidate": c["id"], "period": phase, "symbol": symbol, "case": case, "artifact": name+".json", **summary})
        totals, decisions = {}, {}
        for case, items in collected.items():
            totals[case], aggregate = combine(items, protocol)
            np.savez_compressed(output/f"{c['id']}__{phase}__{case}_aggregate_equity.npz", equity=aggregate)
            decisions[case] = gate(totals[case], phase, protocol)
        result["totals"].setdefault(c["id"], {})[phase] = totals
        result["decisions"].setdefault(c["id"], {})[phase] = decisions
        print("COMPLETE", c["id"], phase, flush=True)
    if phase == "training":
        passing = [c["id"] for c in candidates if c["eligible"] and all(x["passed"] for x in result["decisions"][c["id"]][phase].values())]
        def rank(cid):
            values = list(result["totals"][cid][phase].values())
            return (-min(v["pf"] if v["pf"] is not None else float("inf") for v in values), -min(v["average_net_r"] for v in values), max(v["mtm_drawdown_r"] for v in values), cid)
        result["selected"] = sorted(passing, key=rank)[0] if passing else ""
        dump(output/"selection_before_validation.json", {"saved_at_utc": datetime.now(timezone.utc).isoformat(), "selected": result["selected"], "passing_training": passing, "protocol_sha256": sha(SPEC)})
    result["phase"] = phase
    passed = bool(result["selected"]) and all(v["passed"] for v in result["decisions"][result["selected"]][phase].values())
    result["status"] = "PHASE_PASSED_AWAITING_INDEPENDENT_REVIEW" if passed else "REJECTED_BY_FROZEN_GATES"
    if phase == "validation":
        dump(output/"selection_before_final.json", {"saved_at_utc": datetime.now(timezone.utc).isoformat(),
             "selected": result["selected"] if passed else "", "validation_decisions": result["decisions"][result["selected"]][phase],
             "protocol_sha256": sha(SPEC), "code_sha256": sha(Path(__file__))})
    result["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    if hashes != {str(p.relative_to(ROOT)): sha(p) for p in deps}: raise ValueError("code drift during run")
    dump(output/"results.json", result)
    dump(output/f"{phase}_results.json", result)
    print("RESULT_JSON="+json.dumps({"status": result["status"], "selected": result["selected"], "phase": phase, "output": str(output)}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--phase", choices=("training", "validation", "final_confirmation"), default="training")
    args = parser.parse_args()
    run(args.output, args.phase)
