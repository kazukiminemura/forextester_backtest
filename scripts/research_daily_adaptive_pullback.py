"""Finite, past-only monthly selection of frozen daily pullback shadow trades."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np

from scripts import research_daily_edge_reset as base

ROOT = base.ROOT
SPEC = ROOT/"docs/quant_organization/experiments/daily_adaptive_pullback_20260910/protocol.json"
OUT = ROOT/"agent_runs/daily_adaptive_pullback_20260910/completed"


def month_lower(month, months):
    year, m = map(int, month.split("-"))
    ordinal = year*12+m-1-months
    y, m0 = divmod(ordinal,12)
    return base.timestamp(f"{y:04d}-{m0+1:02d}-01")


def monthly_calendar(inputs, start, end):
    calendar = {}
    for symbol,(data,*_) in inputs.items():
        indices = np.flatnonzero((data.dates >= start)&(data.dates < end))
        for i in indices:
            month = base.iso(data.dates[i])[:7]
            calendar[month] = min(calendar.get(month, int(data.first[i])), int(data.first[i]))
    return dict(sorted(calendar.items()))


def monthly_choices(shadow, calendar, months, protocol):
    choices, cfg = {}, protocol["monthly_selection"]
    for month, cutoff in calendar.items():
        lower, stats = month_lower(month, months), []
        for symbol,trades in shadow.items():
            past = [t for t in trades if t["reason"] != "period_boundary" and lower <= t["exit_exposure_timestamp"] < cutoff]
            n, total = len(past), sum(t["net_r"] for t in past)
            eligible = n >= cfg["minimum_trades"] and total > 0
            stats.append({"symbol":symbol,"trades":n,"net_r":total,"score":total/(n+10),
                          "eligible":eligible,"last_exit_exposure":max((t["exit_exposure_timestamp"] for t in past),default=0)})
        ranked = sorted((x for x in stats if x["eligible"]),key=lambda x:(-x["score"],x["symbol"]))
        choices[month] = {"cutoff":cutoff,"lookback_lower":lower,"selected":[x["symbol"] for x in ranked[:cfg["top"]]],"stats":stats}
    return choices


def select_entries(shadow, choices, start, end, protocol):
    """Admit entries from chronological events. Future P/L never enters admission."""
    cfg = protocol["capacity"]
    events = []
    by_id = {}
    for symbol,trades in shadow.items():
        for number,t in enumerate(trades):
            if start <= base.timestamp(t["entry_date"][:10]) < end:
                tid = f"{symbol}:{number}"
                by_id[tid] = (symbol,number,t)
                # Exit metadata schedules an event, never a feature used at entry.
                events.append((t["entry_timestamp"],1,symbol,tid))
                events.append((t["exit_exposure_timestamp"],0,symbol,tid))
    active, accepted, logs = {}, set(), []
    for when,event_type,symbol,tid in sorted(events):
        if event_type == 0:
            active.pop(tid,None)
            continue
        _,number,t = by_id[tid]
        month = t["entry_date"][:7]
        choice = choices[month]
        if choice["cutoff"] > when:
            raise ValueError("monthly choice not yet available")
        counts = Counter(ccy for s in active.values() for ccy in (s[:3],s[3:]))
        reason = "accepted"
        if symbol not in choice["selected"]:
            reason = "monthly_not_selected"
        elif len(active) >= cfg["maximum_positions"]:
            reason = "position_capacity"
        elif any(counts[c] >= cfg["maximum_positions_per_constituent_currency"] for c in (symbol[:3],symbol[3:])):
            reason = "currency_capacity"
        logs.append({"trade_id":tid,"entry_timestamp":when,"entry_month":month,"symbol":symbol,
                     "monthly_cutoff":choice["cutoff"],"positions_before":len(active),
                     "constituent_counts_before":dict(sorted(counts.items())),"reason":reason})
        if reason == "accepted":
            accepted.add(tid)
            active[tid] = symbol
    return accepted, logs


def actual_equity(data,trades,start,end,pip,cost,carry=.2):
    """Daily MTM for accepted shadow trades only, with no effect on shadow path."""
    first,last = np.searchsorted(data.dates,[start,end])
    opens = {t["entry_index"]:t for t in trades}
    closes = {t["exit_index"]:t for t in trades}
    p, realized, rows = None,0.,[]
    for i in range(first,last):
        if i in opens:
            if p is not None: raise ValueError("overlap within symbol")
            p=opens[i]
        if i in closes:
            realized+=closes[i]["net_r"]
            p=None
        mark=0.
        if p is not None:
            days=base.charged_days(p["entry_timestamp"],data.last[i]+60)
            mark=(p["direction"]*(data.ohlc[i,3]-p["entry"])-(cost+carry*days)*pip)/p["risk"]
        rows.append([int(data.dates[i]),realized,realized+mark])
    return np.asarray(rows).reshape((-1,3))


def gate(summary,phase,protocol):
    g,failures=protocol["acceptance_gates"],[]
    if summary["trades"]<g[phase]["minimum_trades"]: failures.append("trades")
    pf=summary["pf"] if summary["pf"] is not None else (float("inf") if summary["profit_r"]>0 else 0.)
    if pf<g[phase]["minimum_pf"]: failures.append("pf")
    if summary["average_net_r"]<=0: failures.append("expectancy")
    if summary["mtm_drawdown_r"]>g["maximum_daily_mtm_drawdown_r"]: failures.append("mtm_dd")
    if summary["active_symbols"]<g["minimum_active_symbols"]: failures.append("active_symbols")
    if summary["profitable_symbols"]*2<=summary["active_symbols"]: failures.append("profitable_majority")
    if phase=="training" and (len(summary["training_subperiods"])!=3 or any(x["realized"]["net_r"]<=0 for x in summary["training_subperiods"])): failures.append("training_subperiods")
    return {"passed":not failures,"failures":failures}


def run(output,phase="training"):
    protocol=json.loads(SPEC.read_text(encoding="utf-8"))
    base_spec=ROOT/protocol["base_protocol"]
    bp=json.loads(base_spec.read_text(encoding="utf-8"))
    inputs,identities=base.load_inputs(bp)
    deps=[SPEC,SPEC.with_name("hypothesis.md"),Path(__file__),Path(base.__file__),
          base_spec,base_spec.with_name("hypothesis.md"),ROOT/"scripts/research_dinapoli_3x3_daily.py",ROOT/bp["data_manifest"]]
    hashes={str(p.relative_to(ROOT)):base.sha(p) for p in deps}
    if phase=="training":
        output.mkdir(parents=True,exist_ok=False)
        base.dump(output/"protocol.json",protocol)
        base.dump(output/"code_input_hashes.json",{"frozen_at_utc":datetime.now(timezone.utc).isoformat(),"sha256":hashes,"inputs":identities})
        result={"selected":"","totals":{},"decisions":{},"rows":[],"adoption_approved":False}
        candidates=protocol["search_space"]
    else:
        frozen=json.loads((output/"code_input_hashes.json").read_text(encoding="utf-8"))
        if hashes!=frozen["sha256"] or identities!=frozen["inputs"]: raise ValueError("frozen drift")
        result=json.loads((output/"results.json").read_text(encoding="utf-8"))
        prior="training" if phase=="validation" else "validation"
        if not result["selected"] or result["phase"]!=prior: raise ValueError("invalid phase/selection")
        if not all(x["passed"] for x in result["decisions"][result["selected"]][prior].values()): raise ValueError("prior rejected")
        candidates=[c for c in protocol["search_space"] if c["id"]==result["selected"]]
    start,end=map(base.timestamp,protocol["periods"][phase])
    shadow_start=base.timestamp(protocol["periods"]["training"][0])
    rule=next(c for c in bp["search_space"] if c["id"]=="pullback05")
    shadow={case:{} for case in ("fixed_1p8","metadata_plus_0p4")}
    baseline={case:[] for case in shadow}
    for symbol,(data,f,pip,costs) in inputs.items():
        for case,cost in costs.items():
            trades,equity=base.simulate(data,f,rule,shadow_start,end,pip,cost,.2,bp["minimum_warmup_bars"])
            shadow[case][symbol]=trades
            base.dump(output/f"shadow__{phase}__{symbol}__{case}.json",{"trades":trades})
            if phase=="training":
                summary=base.summarize(trades,equity)
                baseline[case].append({"trades":trades,"equity":equity,"summary":summary})
    if phase=="training":
        result["baseline_training"]={case:base.combine(items,bp)[0] for case,items in baseline.items()}
    calendar=monthly_calendar(inputs,start,end)
    for c in candidates:
        choices=monthly_choices(shadow["metadata_plus_0p4"],calendar,c["months"],protocol)
        accepted,logs=select_entries(shadow["metadata_plus_0p4"],choices,start,end,protocol)
        base.dump(output/f"{c['id']}__{phase}__monthly.json",choices)
        base.dump(output/f"{c['id']}__{phase}__admissions.json",logs)
        totals,decisions={},{}
        for case,by_symbol in shadow.items():
            items=[]
            for symbol,trades in by_symbol.items():
                selected=[{**t,"symbol":symbol,"shadow_trade_id":f"{symbol}:{n}"} for n,t in enumerate(trades) if f"{symbol}:{n}" in accepted]
                data,_,pip,costs=inputs[symbol]
                eq=actual_equity(data,selected,start,end,pip,costs[case])
                summary=base.summarize(selected,eq)
                name=f"{c['id']}__{phase}__{symbol}__{case}"
                base.dump(output/f"{name}.json",{"trades":selected,"summary":summary})
                np.savez_compressed(output/f"{name}_equity.npz",equity=eq)
                items.append({"trades":selected,"equity":eq,"summary":summary})
                result["rows"].append({"candidate":c["id"],"period":phase,"case":case,"symbol":symbol,"artifact":name+".json",**summary})
            total,eq=base.combine(items,bp)
            total["active_symbols"]=sum(i["summary"]["trades"]>0 for i in items)
            total["admission_counts"]=dict(Counter(x["reason"] for x in logs))
            np.savez_compressed(output/f"{c['id']}__{phase}__{case}_aggregate_equity.npz",equity=eq)
            totals[case],decisions[case]=total,gate(total,phase,protocol)
        result["totals"].setdefault(c["id"],{})[phase]=totals
        result["decisions"].setdefault(c["id"],{})[phase]=decisions
        print("COMPLETE",c["id"],phase,flush=True)
    if phase=="training":
        passing=[c["id"] for c in candidates if all(x["passed"] for x in result["decisions"][c["id"]][phase].values())]
        def rank(cid):
            values=list(result["totals"][cid][phase].values())
            return (-min(v["pf"] if v["pf"] is not None else float("inf") for v in values),-min(v["average_net_r"] for v in values),max(v["mtm_drawdown_r"] for v in values),cid)
        result["selected"]=sorted(passing,key=rank)[0] if passing else ""
        base.dump(output/"selection_before_validation.json",{"selected":result["selected"],"passing_training":passing,"saved_at_utc":datetime.now(timezone.utc).isoformat(),"protocol_sha256":base.sha(SPEC)})
    passed=bool(result["selected"]) and all(x["passed"] for x in result["decisions"][result["selected"]][phase].values())
    if phase=="validation":
        base.dump(output/"selection_before_final.json",{"selected":result["selected"] if passed else "","decisions":result["decisions"][result["selected"]][phase],"saved_at_utc":datetime.now(timezone.utc).isoformat(),"protocol_sha256":base.sha(SPEC)})
    result["phase"],result["status"]=phase,"PHASE_PASSED_AWAITING_INDEPENDENT_REVIEW" if passed else "REJECTED_BY_FROZEN_GATES"
    result["completed_at_utc"]=datetime.now(timezone.utc).isoformat()
    if hashes!={str(p.relative_to(ROOT)):base.sha(p) for p in deps}: raise ValueError("runtime drift")
    base.dump(output/"results.json",result)
    base.dump(output/f"{phase}_results.json",result)
    print("RESULT_JSON="+json.dumps({"status":result["status"],"selected":result["selected"],"phase":phase,"output":str(output)}),flush=True)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=OUT)
    parser.add_argument("--phase",choices=("training","validation","final_confirmation"),default="training")
    args=parser.parse_args()
    run(args.output,args.phase)
