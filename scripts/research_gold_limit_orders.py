"""Two existing signal sets, 24 frozen execution policies, minute-level fills."""
from bisect import bisect_right
from datetime import datetime,timedelta
import itertools
import json

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.gold_signals import features
from forextester_backtest.gold_refinement import entry_signals
from forextester_backtest.gold_limit import limit_trade
from forextester_backtest.sniper import Technicals
from research_gold_minute_execution import capture_days
from research_sniper_daytrade import ROOT,PERIODS,metrics


def main():
    policies = [dict(signal=s,offset=o,ttl_hours=t,anchored=a) for s,o,t,a in itertools.product(("direct","impulse"),(.1,.25,.5),(1,2),(False,True))]
    (ROOT/"scripts/gold_limit_protocol.json").write_text(json.dumps(dict(policies=policies,counts=[250,100,50,50],
        selection="minimum train/validation PF; later results are not used for reselection",target="all-period PF > 1",same_bar_fill="SL allowed; TP ignored unless filled at open"),indent=2),encoding="utf-8")
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    end = datetime(2026,7,17,23,59,59)
    bars = list(_aggregate_bars(repo.bars("XAUUSD",datetime(2009,1,1),end,"5m"),timedelta(hours=1)))
    frame = features(bars)
    ta = Technicals(dict(atrLength=14,emaLength=200,rsiLength=14,dmiLength=14,stFactor=3))
    adx = []
    for bar in bars:
        ta.update(bar)
        adx.append(ta.adx)
    adx = np.asarray(adx)
    dates = [b.time.date() for b in bars]
    hour_times = [b.time for b in bars]
    allowed = np.array([i+1<len(bars) and b.time.year>=2010 and bars[i+1].time==b.time+timedelta(hours=1) and 6<=bars[i+1].time.hour<16 for i,b in enumerate(bars)])
    signal_sets = {}
    wanted = set()
    for mode in ("direct","impulse"):
        sides = entry_signals(frame,dates,mode)
        indexes = np.flatnonzero(allowed&(sides!=0)&((adx>=18) if mode=="impulse" else True))
        signal_sets[mode] = (indexes,sides)
        wanted.update(dates[i+1] for i in indexes)
    print("READ_MINUTE_DAYS",len(wanted),flush=True)
    captured = capture_days(repo.bars("XAUUSD",bars[0].time,end,"1m"),wanted)
    times = {d:[b.time for b in q] for d,q in captured.items()}
    spread = repo.metadata("XAUUSD").spread_price

    def run_policy(policy,multiplier=1,development=False):
        indexes,sides = signal_sets[policy["signal"]]
        last_entry,blocked_hour,blocked_until = -100,-1,datetime.min
        placed,expired = 0,0
        rows = []
        for k in indexes:
            h = k+1
            time = bars[h].time
            if development and time.year>2022:
                break
            if time<blocked_until or h<=blocked_hour or h-last_entry<5:
                continue
            placed += 1
            day = dates[h]
            trade = limit_trade(captured[day],times[day],time,int(sides[k]),frame.atr.iloc[k],bars[k].close,
                                spread*multiplier,policy["offset"],policy["ttl_hours"],policy["anchored"])
            if not trade["filled"]:
                expired += 1
                blocked_until = trade["expiry"]
                continue
            last_entry = bisect_right(hour_times,trade["entry_time"])-1
            blocked_hour = bisect_right(hour_times,trade["exit_time"])-1
            blocked_until = trade["exit_time"]
            rows.append((last_entry,blocked_hour,trade["exit_time"].year,trade["r"],25,55,0,time.hour,
                         trade["late"],trade["reason"]=="target",spread*multiplier/frame.atr.iloc[k],trade["reason"]=="time"))
        rows = np.asarray(rows,dtype=float).reshape((-1,12))
        statistics = [metrics(rows[(rows[:,2]>=a)&(rows[:,2]<=b)]) for a,b in PERIODS]
        return dict(periods=statistics,orders=placed,expired=expired,filled=len(rows),fill_rate=100*len(rows)/placed if placed else None)

    candidates = []
    for policy in policies:
        dev = run_policy(policy,development=True)
        candidates.append(dict(policy=policy,train=dev["periods"][0],validation=dev["periods"][1],orders=dev["orders"],fill_rate=dev["fill_rate"]))
    eligible = [c for c in candidates if c["train"]["n"]>=250 and c["validation"]["n"]>=100]
    if not eligible:
        result = dict(selected=None,adopted=False,eligible_count=0,candidates=candidates)
    else:
        chosen = max(eligible,key=lambda c:(min(c["train"]["pf"] or 0,c["validation"]["pf"] or 0),c["validation"]["mean_r"]))
        final,stress = run_policy(chosen["policy"]),run_policy(chosen["policy"],multiplier=2)
        gates = [m["n"]>=n and (m["pf"] or 0)>1 and m["mean_r"]>0 for m,n in zip(final["periods"],(250,100,50,50))]
        result = dict(selected=chosen,results=final,doubled_spread=stress,gates=gates,adopted=all(gates),eligible_count=len(eligible),candidates=candidates)
    path = ROOT/"scripts/gold_limit_results.json"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RESULT_JSON",path,flush=True)
    print(json.dumps({k:v for k,v in result.items() if k!="candidates"},ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
