"""Frozen 150-variant confirmation/management study aiming for PF > 1 in all periods."""
import hashlib
import itertools
import json
from datetime import datetime, timedelta

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.gold_signals import features
from forextester_backtest.gold_refinement import ENTRY_MODES, EXIT_MODES, entry_signals, managed_outcome
from forextester_backtest.sniper import Technicals
from research_sniper_daytrade import ROOT, PERIODS, outcome, evaluate, selected

FRAMES = (30,60)


def simulate(bars, indexes, sides, atr, spread, minutes, mode):
    rows = []
    for k in indexes:
        i = k+1
        if mode.startswith("fixed"):
            result = outcome(bars,i,int(sides[k]),atr[k],spread,minutes,1.5 if mode=="fixed1R" else 3,None)
        else:
            result = managed_outcome(bars,i,int(sides[k]),atr[k],spread,mode)
        if result is None:
            continue
        j,r,reason,late = result
        rows.append((i,j,bars[j].time.year,r,25,55,0,bars[i].time.hour,late,reason=="target",spread/atr[k],reason=="time"))
    return np.asarray(rows,dtype=float).reshape((-1,12))


def admission_stats(rows):
    stats = evaluate({"XAUUSD":rows},(18,100,100,(6,16)))["periods"]
    trades = selected(rows,(18,100,100,(6,16)))
    for (a,b),m in zip(PERIODS,stats):
        rewards = trades[(trades[:,2]>=a)&(trades[:,2]<=b),3]
        equity = np.r_[0,rewards.cumsum()]
        m["max_drawdown_r"] = float(np.max(np.maximum.accumulate(equity)-equity))
    return stats


def main():
    specification = dict(frames=FRAMES,entry_modes=ENTRY_MODES,adx_min=(0,18,25),exit_modes=EXIT_MODES,
                         stop_atr=1.5,entry_hours=(6,16),exit_hour=20,cooldown=5,counts=(250,100,50,50),
                         target="PF > 1 and positive mean R in every period",selection="maximize minimum development PF",
                         periods=PERIODS,prior_evaluation_inspected=True)
    (ROOT/"scripts/gold_pf_refinement_protocol.json").write_text(json.dumps(specification,indent=2),encoding="utf-8")
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    meta = repo.metadata("XAUUSD")
    assert meta.commission_per_lot == 0
    base = list(repo.bars("XAUUSD",datetime(2009,1,1),datetime(2026,7,17,23,59,59),"5m"))
    contexts, candidates = {}, []
    baseline_verified = False
    for minutes in FRAMES:
        bars = list(_aggregate_bars(base,timedelta(minutes=minutes)))
        frame = features(bars)
        ta = Technicals(dict(atrLength=14,emaLength=200,rsiLength=14,dmiLength=14,stFactor=3))
        adx = []
        for b in bars:
            ta.update(b)
            adx.append(ta.adx)
        adx = np.asarray(adx)
        dates = [b.time.date() for b in bars]
        allowed = np.array([i+1<len(bars) and b.time.year>=2010 and bars[i+1].time==b.time+timedelta(minutes=minutes) and 6<=bars[i+1].time.hour<16 for i,b in enumerate(bars)])
        contexts[minutes] = (bars,frame,adx,dates,allowed)
        for entry_mode in ENTRY_MODES:
            sides = entry_signals(frame,dates,entry_mode)
            for minimum,exit_mode in itertools.product((0,18,25),EXIT_MODES):
                indexes = np.flatnonzero(allowed & (sides!=0) & ((adx>=minimum) if minimum else True))
                rows = simulate(bars,indexes,sides,frame.atr.to_numpy(),meta.spread_price,minutes,exit_mode)
                dev = evaluate({"XAUUSD":rows[rows[:,2]<=2022]},(18,100,100,(6,16)))["periods"][:2]
                candidates.append(dict(minutes=minutes,entry_mode=entry_mode,adx_min=minimum,exit_mode=exit_mode,train=dev[0],validation=dev[1]))
                if minutes==60 and entry_mode=="direct" and minimum==0 and exit_mode=="fixed2R":
                    actual = admission_stats(rows)
                    expected = json.loads((ROOT/"scripts/gold_pf_results.json").read_text(encoding="utf-8"))["results"]
                    for m,e in zip(actual,expected):
                        for key in m:
                            assert np.isclose(m[key],e[key]),(key,m,e)
                    baseline_verified = True
            print("COMPLETE",minutes,entry_mode,flush=True)
    eligible = [c for c in candidates if c["train"]["n"]>=250 and c["validation"]["n"]>=100]
    ranking = sorted(eligible,key=lambda c:(min(c["train"]["pf"] or 0,c["validation"]["pf"] or 0),c["validation"]["mean_r"]),reverse=True)
    if not ranking:
        raise ValueError("Insufficient sample counts")
    chosen = ranking[0]
    bars,frame,adx,dates,allowed = contexts[chosen["minutes"]]
    sides = entry_signals(frame,dates,chosen["entry_mode"])
    indexes = np.flatnonzero(allowed&(sides!=0)&((adx>=chosen["adx_min"]) if chosen["adx_min"] else True))
    final = []
    for multiplier in (1,2):
        rows = simulate(bars,indexes,sides,frame.atr.to_numpy(),meta.spread_price*multiplier,chosen["minutes"],chosen["exit_mode"])
        final.append(admission_stats(rows))
    gates = [m["n"]>=n and (m["pf"] or 0)>1 and m["mean_r"]>0 for m,n in zip(final[0],(250,100,50,50))]
    result = dict(specification=specification,candidate_count=len(candidates),eligible_count=len(eligible),
                  development_profitable_count=sum((c["train"]["pf"] or 0)>1 and (c["validation"]["pf"] or 0)>1 for c in eligible),
                  selected=chosen,results=final[0],doubled_spread=final[1],gates=gates,adopted=all(gates),
                  baseline_verified=baseline_verified,development_candidates=candidates,development_top10=ranking[:10],
                  logic_sha256=hashlib.sha256((ROOT/"src/forextester_backtest/gold_refinement.py").read_bytes()).hexdigest())
    path = ROOT/"scripts/gold_pf_refinement_results.json"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RESULT_JSON",path,flush=True)
    print(json.dumps(dict(selected=chosen,results=final[0],doubled_spread=final[1],adopted=all(gates),eligible=len(eligible)),ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
