"""Frozen conditional evening research. Clocks are assumptions, never inferred from P/L."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.research_bb_event_edge import digest, write_json
from scripts.research_bb3_jev_engine import simulate

ID="bb_night_rr1_20261007"
DOC=ROOT/"docs/quant_organization/experiments"/ID
OUT=ROOT/"agent_runs"/ID
ARMS=("baseline","range_bb","trend_reclaim")
CLOCKS={"gmt0":0,"gmt2":2,"gmt3":3,"gmt9":9,"all_hours":None}
PERIODS={"training":(2020,2023),"validation":(2023,2025),"final_descriptive":(2025,2026)}


def epoch(year):
    return int(np.datetime64(f"{year}-01-01","s").astype(int))


def shift_seconds(offset):
    return (9-(0 if offset is None else offset))*3600


def book_bounds(years,offset):
    shift=0 if offset is None else shift_seconds(offset)
    return epoch(years[0])-shift,epoch(years[1])-shift


def in_night(source_times,offset):
    local=np.asarray(source_times)+shift_seconds(offset)
    days=local//86400
    return ((days+3)%7<5)&(local%86400>=19*3600)


def prior_efficiency(close,times):
    """Twelve changes in thirteen prior closes; origin candle is excluded."""
    result=np.full(len(close),np.nan)
    if len(close)<=13:
        return result
    windows=np.lib.stride_tricks.sliding_window_view(close,13)[:-1]
    tw=np.lib.stride_tricks.sliding_window_view(times,13)[:-1]
    denominator=np.abs(np.diff(windows,axis=1)).sum(axis=1)
    ratio=np.divide(np.abs(windows[:,-1]-windows[:,0]),denominator,out=np.zeros(len(windows)),where=denominator>0)
    ok=np.isfinite(windows).all(axis=1)&(np.diff(tw,axis=1)==300).all(axis=1)
    result[13:]=np.where(ok,ratio,np.nan)
    return result


def h1_direction(f,times):
    """Only twenty-five consecutive, completed twelve-M5 hours are usable."""
    hours,starts,counts=np.unique(times//3600,return_index=True,return_counts=True)
    grid=np.arange(hours[0],hours[-1]+1,dtype=np.int64)
    closes=np.full(len(grid),np.nan)
    for hour,start,count in zip(hours,starts,counts):
        chunk=times[start:start+count]
        if count==12 and chunk[0]%3600==0 and np.all(np.diff(chunk)==300):
            closes[hour-grid[0]]=f[start+11,3]
    series=pd.Series(closes)
    mid=series.rolling(20,min_periods=20).mean().to_numpy()
    earlier=np.full(len(mid),np.nan)
    if len(mid)>5:
        earlier[5:]=mid[:-5]
    valid=series.rolling(25,min_periods=25).count().to_numpy()==25
    direction=np.where(valid&(closes>mid)&(mid>earlier),1,np.where(valid&(closes<mid)&(mid<earlier),-1,0)).astype(np.int8)
    available=np.searchsorted((grid+1)*3600,times+300,side="right")-1
    mapped=np.where(available>=0,direction[np.maximum(available,0)],0)
    return mapped,dict(hour_start=grid*3600,close=closes,sma20=mid,direction=direction)


def make_signals(f,times,baseline):
    efficiency=prior_efficiency(f[:,3],times)
    directions,hourly=h1_direction(f,times)
    filtered=[s for s in baseline if np.isfinite(efficiency[s["origin"]]) and efficiency[s["origin"]]<=.30]
    trend=[]
    for i in range(1,len(f)):
        side=int(directions[i])
        if not side or times[i]-times[i-1]!=300 or not np.isfinite(f[[i-1,i],4]).all() or not np.isfinite(f[i,7]) or f[i,7]<=0:
            continue
        if side*(f[i-1,3]-f[i-1,4])<=0 and side*(f[i,3]-f[i,4])>0:
            trend.append(dict(index=i,origin=i,side=side,risk_price=float(f[i,7]*1.5)))
    return dict(baseline=baseline,range_bb=filtered,trend_reclaim=trend),hourly


def execution_signals(signals,f,times,start,end,offset):
    """Signal data stay causal; fill-relative ATR brackets are priced here only."""
    result=[]
    for signal in signals:
        i=signal["index"]
        if not(start<=times[signal["origin"]]<end and start<=times[i]<end) or i+1>=len(times):
            continue
        if offset is not None and not bool(in_night(times[i+1],offset)):
            continue
        order=dict(signal)
        if "risk_price" in signal:
            order["target"]=float(f[i+1,0]+signal["side"]*signal["risk_price"])
        result.append(order)
    return result


def summarize_fills(f,times,signals,result,pip,start,end,cost):
    """Reconstruct only final open fill for exact counts, cost and holding evidence."""
    closed=result["trades"]
    last_exit=max((t["exit_index"] for t in closed),default=-1)
    open_trade=None
    if result["summary"]["open_side"]:
        for s in signals:
            i=s["index"]; j=i+1
            if i<last_exit or j>=len(times) or not start<=times[j]<end or times[j]-times[i]!=300:
                continue
            risk=s["side"]*(s["target"]-f[j,0])/pip
            if risk<=0 or risk+1e-9<3:
                continue
            open_trade=dict(s,entry_index=j,entry_time=int(times[j]),entry=float(f[j,0]),risk_pips=float(risk),
                stop=float(2*f[j,0]-s["target"]),mark_time=int(times[np.searchsorted(times,end)-1]+300),
                net_r=result["summary"]["open_net_r"],net_pips=result["summary"]["open_net_pips"],cost_pips=cost)
            break
        if open_trade is None:
            raise AssertionError("Final open fill not identified")
    fills=closed+([open_trade] if open_trade else [])
    costs_r=sum(cost/t["risk_pips"] for t in fills)
    summary=dict(result["summary"],entries=len(fills),cost_r=costs_r,cost_pips=cost*len(fills),
                 gross_r=result["summary"]["net_plus_open_r"]+costs_r,
                 max_hold_bars=max((t.get("exit_index",int(np.searchsorted(times,end))-1)-t["entry_index"]+1 for t in fills),default=0))
    return summary,fills,open_trade


def night_coverage(data,years,offset):
    """Future full-night completeness is diagnostic only, not a trading filter."""
    shift=shift_seconds(offset)
    start,end=book_bounds(years,offset)
    local_start,local_end=start+shift,end+shift
    days=np.arange(local_start//86400,local_end//86400+1,dtype=np.int64)
    days=days[((days+3)%7<5)&(days*86400+19*3600>=local_start)&((days+1)*86400<=local_end)]
    slots=days[:,None]*86400+19*3600+np.arange(60)*300-shift
    observed,complete=[],[]
    for values in data.values():
        times,mask=values["times"],values["complete"]
        idx=np.searchsorted(times,slots)
        safe=np.minimum(idx,len(times)-1)
        present=(idx<len(times))&(times[safe]==slots)
        observed.append(present.sum(axis=1))
        complete.append((present&mask[safe]).all(axis=1))
    counts=np.array(observed)
    return dict(days=days,observed_counts=counts,complete=(counts==60).all(axis=0),
                m1_complete=np.array(complete).all(axis=0),all_missing=(counts==0).all(axis=0))


def frequency_metrics(counts):
    if not len(counts):
        return dict(nights=0,mean=None,median=None,zero_pct=None,two_plus_pct=None,two_to_three_pct=None,above_three_pct=None)
    return dict(nights=len(counts),mean=float(np.mean(counts)),median=float(np.median(counts)),
                zero_pct=float(100*np.mean(counts==0)),two_plus_pct=float(100*np.mean(counts>=2)),
                two_to_three_pct=float(100*np.mean((counts>=2)&(counts<=3))),above_three_pct=float(100*np.mean(counts>3)))


def night_metrics(fills,coverage,offset):
    shift=shift_seconds(offset)
    evening=[t for t in fills if in_night(t["entry_time"],offset)]
    day_counts=Counter((t["entry_time"]+shift)//86400 for t in evening)
    unique_counts=Counter((t+shift)//86400 for t in set(t["entry_time"] for t in evening))
    days=coverage["days"]; valid=coverage["complete"]
    raw=np.array([day_counts[int(d)] for d in days],dtype=np.int64)
    unique=np.array([unique_counts[int(d)] for d in days],dtype=np.int64)
    carry,boundary,censored,next_day,closed,midnight_gaps=0,0,0,0,0,0
    for t in evening:
        midnight=((t["entry_time"]+shift)//86400+1)*86400-shift
        if "exit_time" in t:
            closed+=1
            carry+=t["exit_time"]>midnight
            midnight_gap=t["exit_time"]==midnight and t.get("exit_reason") in ("gap_stop","gap_target")
            midnight_gaps+=midnight_gap
            boundary+=t["exit_time"]==midnight and not midnight_gap
            next_day+=(t["exit_time"]+shift)//86400>(t["entry_time"]+shift)//86400
        elif t["mark_time"]>midnight:
            carry+=1
        else:
            censored+=1
    observed=len(evening)-censored
    return dict(primary=frequency_metrics(raw[valid]),deduplicated=frequency_metrics(unique[valid]),
        weekday_nights=len(days),m5_complete_nights=int(valid.sum()),m1_complete_nights=int(coverage["m1_complete"].sum()),
        all_missing_nights=int(coverage["all_missing"].sum()),partial_nights=int((~valid&~coverage["all_missing"]).sum()),
        missing_or_partial_pct=float(100*np.mean(~valid)) if len(valid) else None,
        entries_on_complete_nights=int(raw[valid].sum()),entries_on_incomplete_nights=int(raw[~valid].sum()),
        simultaneous_duplicate_entries=int((raw[valid]-unique[valid]).sum()),
        evening_entries=len(evening),strict_midnight_carry=int(carry),possible_midnight_carry=int(carry+boundary),
        midnight_boundary_uncertain=int(boundary),midnight_gap_exits=int(midnight_gaps),midnight_right_censored=int(censored),
        strict_carry_pct=100*carry/observed if observed else None,possible_carry_pct=100*(carry+boundary)/observed if observed else None,
        next_day_closed=int(next_day),next_day_closed_pct=100*next_day/closed if closed else None,
        daily=[dict(day=str(np.datetime64(int(d),"D")),m5_complete=bool(v),entries=int(n),unique_times=int(u)) for d,v,n,u in zip(days,valid,raw,unique)])


def prepare(protocol,output):
    from scripts.research_bb_event_edge import stage_b_signals
    old=ROOT/"agent_runs/bb_event_edge_20261003"
    entries=json.loads((ROOT/protocol["data_manifest"]).read_text(encoding="utf-8"))
    masks=json.loads((ROOT/protocol["complete_m5_directory"]/"run_manifest.json").read_text(encoding="utf-8"))["inputs"]
    old_a=json.loads((old/"run_manifest.json").read_text(encoding="utf-8"))
    data,inputs={},[]
    for symbol in protocol["symbols"]:
        entry=next(r for r in entries if r["symbol"]==symbol)
        mask_info=next(r for r in masks if r["symbol"]==symbol)
        cache=ROOT/protocol["cache_directory"]/f"{symbol}_features.npz"
        mask_path=ROOT/protocol["complete_m5_directory"]/f"{symbol}_complete_m5.npz"
        origin_path=old/f"{symbol}_events.npz"
        signal_path=old/"stage_b"/f"{symbol}_signals.json"
        expected_origin=next(r for r in old_a["data"] if r["symbol"]==symbol)["event_file_sha256"]
        if digest(cache)!=entry["cache_sha256"] or digest(mask_path)!=mask_info["mask_sha256"] or digest(origin_path)!=expected_origin:
            raise ValueError(f"Input SHA changed {symbol}")
        with np.load(cache,allow_pickle=False) as z:
            f,times=z["features"],z["times"]
        with np.load(mask_path,allow_pickle=False) as z:
            complete=z["complete"].astype(bool)
        if len(complete)!=len(times) or np.any(np.diff(times)<=0):
            raise ValueError(f"Misaligned data {symbol}")
        baseline=json.loads(signal_path.read_text(encoding="utf-8"))["reversal_close_next_open"]
        with np.load(origin_path,allow_pickle=False) as z:
            rebuilt,_=stage_b_signals(f,times,z["index"],z["side"],entry["tick"])
        if rebuilt["reversal_close_next_open"]!=baseline:
            raise ValueError(f"Saved baseline differs {symbol}")
        signals,hourly=make_signals(f,times,baseline)
        write_json(output/f"{symbol}_signals.json",signals)
        np.savez_compressed(output/f"{symbol}_h1.npz",**hourly)
        data[symbol]=dict(f=f,times=times,complete=complete,signals=signals,pip=entry["pip"],tick=entry["tick"])
        inputs.append(dict(symbol=symbol,cache_sha256=entry["cache_sha256"],mask_sha256=mask_info["mask_sha256"],
            origin_sha256=expected_origin,baseline_signals_sha256=digest(signal_path),signals_sha256=digest(output/f"{symbol}_signals.json")))
        print(f"PREPARED {symbol}",flush=True)
    return data,inputs


def closed_stats(trades):
    net=np.array([t["net_r"] for t in trades],dtype=float)
    pips=np.array([t["net_pips"] for t in trades],dtype=float)
    gp,gl=float(net[net>0].sum()),float(-net[net<0].sum())
    gpp,glp=float(pips[pips>0].sum()),float(-pips[pips<0].sum())
    return dict(trades=len(trades),wins=int((net>1e-9).sum()),win_rate_pct=100*float((net>1e-9).mean()) if len(net) else None,
        profit_factor_r=gp/gl if gl else None,profit_factor_pips=gpp/glp if glp else None,net_r=float(net.sum()),
        net_pips=float(pips.sum()),average_r=float(net.mean()) if len(net) else None,
        gross_r=float(sum(t["net_r"]+t["cost_pips"]/t["risk_pips"] for t in trades)),cost_r=float(sum(t["cost_pips"]/t["risk_pips"] for t in trades)))


def research_gates(base,stress):
    f=base["frequency"]; rate=f["primary"]
    return dict(coverage_nights=f["m5_complete_nights"]>=100,
        coverage_fraction=f["weekday_nights"]>0 and f["m5_complete_nights"]/f["weekday_nights"]>=.8,
        frequency=rate["mean"] is not None and rate["mean"]>=2,
        pf=(base["profit_factor_r"] or 0)>=1.2,net=base["net_plus_open_r"]>0,
        stress=stress["net_plus_open_r"]>0,positive_pairs=base["positive_pairs"]>=4,closed=base["trades"]>=200,
        zero_nights=rate["zero_pct"] is not None and rate["zero_pct"]<=40,
        two_plus_nights=rate["two_plus_pct"] is not None and rate["two_plus_pct"]>=50)


def run(protocol,protocol_path,output):
    sources=["scripts/research_bb_night_rr1.py","tests/test_bb_night_rr1.py","scripts/research_bb3_jev_engine.py","scripts/research_bb_event_edge.py"]
    manifest=dict(started_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=digest(protocol_path),
        source_hashes={p:digest(ROOT/p) for p in sources},data_clock_evidence_sha256=digest(OUT/"data_clock_evidence.json"),
        source_manifest_sha256=digest(ROOT/protocol["data_manifest"]),api_calls=0,inputs=[])
    write_json(output/"run_manifest.json",manifest)
    data,inputs=prepare(protocol,output)
    manifest["inputs"]=inputs
    manifest["pnl_started_utc"]=datetime.now(timezone.utc).isoformat()
    write_json(output/"run_manifest.json",manifest)
    summaries,totals,annual=[],{},{ }
    count=0
    for clock,offset in CLOCKS.items():
        totals[clock]={};annual[clock]={}
        for period,years in PERIODS.items():
            start,end=book_bounds(years,offset)
            coverage=night_coverage(data,years,offset)
            np.savez_compressed(output/f"{clock}_{period}_night_coverage.npz",**coverage)
            timeline=np.unique(np.concatenate([d["times"][(d["times"]>=start)&(d["times"]<end)] for d in data.values()]))
            totals[clock][period]={};annual[clock][period]={}
            for arm in ARMS:
                totals[clock][period][arm]={};annual[clock][period][arm]={}
                for cost in (1.,1.2):
                    closed,fills,rows=[],[],[]
                    combined=np.zeros(len(timeline))
                    pair_annual={}
                    for symbol,d in data.items():
                        f,times=d["f"],d["times"]
                        signals=execution_signals(d["signals"][arm],f,times,start,end,offset)
                        simulation=simulate(f,times,d["pip"],d["tick"],signals,rr=1.,cost_pips=cost,start=start,end=end,min_center_pips=3.)
                        row,entries,opened=summarize_fills(f,times,signals,simulation,d["pip"],start,end,cost)
                        row["terminal_unpriced_signals"]=int(sum(s["index"]+1>=len(times) and start<=times[s["origin"]]<end and start<=times[s["index"]]<end for s in d["signals"][arm]))
                        row.update(symbol=symbol,clock=clock,period=period,arm=arm,cost=cost)
                        prefix=f"{symbol}_{clock}_{period}_{arm}_cost{cost:g}"
                        write_json(output/f"{prefix}_trades.json",simulation["trades"])
                        write_json(output/f"{prefix}_open.json",opened)
                        np.savez_compressed(output/f"{prefix}_mtm.npz",mtm=simulation["mtm"])
                        rows.append(row);summaries.append(row)
                        closed.extend(dict(symbol=symbol,**t) for t in simulation["trades"])
                        fills.extend(dict(symbol=symbol,**t) for t in entries)
                        curve=simulation["mtm"]
                        indices=np.searchsorted(curve[:,0],timeline,side="right")-1
                        combined+=np.where(indices>=0,curve[np.maximum(indices,0),1],0.)
                        attrib_shift=0 if offset is None else shift_seconds(offset)
                        pair_annual[symbol]={str(y):closed_stats([t for t in simulation["trades"] if epoch(y)<=t["exit_time"]+attrib_shift<epoch(y+1)]) for y in range(years[0],years[1])}
                        count+=1
                    stats=closed_stats(closed)
                    frequency=night_metrics(fills,coverage,offset)
                    daily=frequency.pop("daily")
                    prefix=f"{clock}_{period}_{arm}_cost{cost:g}"
                    write_json(output/f"{prefix}_night_ledger.json",daily)
                    np.savez_compressed(output/f"{prefix}_combined_mtm.npz",mtm=np.column_stack((timeline,combined)))
                    total=dict(stats,entries=len(fills),open_net_r=sum(r["open_net_r"] for r in rows),
                        net_plus_open_r=sum(r["net_plus_open_r"] for r in rows),
                        gross_plus_open_r=sum(r["gross_r"] for r in rows),cost_plus_open_r=sum(r["cost_r"] for r in rows),
                        open_positions=sum(bool(r["open_side"]) for r in rows),positive_pairs=sum(r["net_plus_open_r"]>0 for r in rows),
                        frequency=frequency,activity_above_target=frequency["primary"]["mean"] is not None and frequency["primary"]["mean"]>3,
                        max_hold_bars=max(r["max_hold_bars"] for r in rows),
                        combined_bar_close_mtm_drawdown_r=float(np.max(np.maximum.accumulate(np.maximum(combined,0))-combined)),
                        conditional_clock=True,adopted=False)
                    totals[clock][period][arm][str(cost)]=total
                    annual[clock][period][arm][str(cost)]=pair_annual
                    write_json(output/"progress.json",dict(completed_cases=count,total_cases=630,clock=clock,period=period,arm=arm,cost=cost))
                print(f"SIMULATED {clock}/{period}/{arm}: {count}/630",flush=True)
    gates={clock:{arm:{period:research_gates(totals[clock][period][arm]["1.0"],totals[clock][period][arm]["1.2"])
        for period in ("training","validation")} for arm in ARMS} for clock in CLOCKS if clock!="all_hours"}
    screen={clock:{arm:all(all(g.values()) for g in by_period.values()) for arm,by_period in by_arm.items()} for clock,by_arm in gates.items()}
    result=dict(experiment_id=ID,complete=True,status="CONDITIONAL_CLOCK_DESCRIPTIVE_REVIEW_REQUIRED",cases=count,
        protocol=protocol,summaries=summaries,totals=totals,annual_exit_attribution=annual,gates=gates,screen_pass=screen,
        primary_clock="gmt0",no_clock_selection=True,no_candidate_selection=True,adopted=False,api_calls=0)
    write_json(output/"results.json",result)
    manifest["finished_utc"]=datetime.now(timezone.utc).isoformat();manifest["results_sha256"]=digest(output/"results.json")
    write_json(output/"run_manifest.json",manifest)
    print("RESULT_JSON="+str(output/"results.json"),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol",type=Path,default=DOC/"protocol.json")
    parser.add_argument("--output",type=Path,default=OUT)
    args=parser.parse_args()
    protocol=json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol["status"]!="SPEC_FROZEN" or protocol["experiment_id"]!=ID:
        raise ValueError("Reviewed frozen protocol required")
    if (args.output/"run_manifest.json").exists():
        raise FileExistsError("Previous execution is preserved; use another output")
    args.output.mkdir(parents=True,exist_ok=True)
    write_json(args.output/"protocol.json",protocol)
    run(protocol,args.protocol,args.output)


if __name__=="__main__":
    main()
