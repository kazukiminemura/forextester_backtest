"""Audit the frozen refinement candidate with original Forex Tester minute execution."""
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta
import json

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.gold_signals import features
from forextester_backtest.gold_refinement import entry_signals, managed_outcome
from forextester_backtest.sniper import Technicals
from research_gold_pf_refinement import admission_stats, simulate
from research_sniper_daytrade import ROOT, outcome


def capture_days(stream, wanted):
    """Capture each selected day through its first observed bar at/after 20:00."""
    captured = {}
    active, deadline = None, None
    for bar in stream:
        day = bar.time.date()
        if active is not None:
            captured[active].append(bar)
            if bar.time >= deadline:
                active = None
            else:
                continue
        if day in wanted and day not in captured:
            captured[day] = [bar]
            deadline = bar.time.replace(hour=20,minute=0,second=0)
            if bar.time < deadline:
                active = day
    return captured


def main():
    previous = json.loads((ROOT/"scripts/gold_pf_refinement_results.json").read_text(encoding="utf-8"))
    c = previous["selected"]
    minutes = c["minutes"]
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    end = datetime(2026,7,17,23,59,59)
    bars = list(_aggregate_bars(repo.bars("XAUUSD",datetime(2009,1,1),end,"5m"),timedelta(minutes=minutes)))
    frame = features(bars)
    ta = Technicals(dict(atrLength=14,emaLength=200,rsiLength=14,dmiLength=14,stFactor=3))
    adx = []
    for b in bars:
        ta.update(b)
        adx.append(ta.adx)
    dates = [b.time.date() for b in bars]
    sides = entry_signals(frame,dates,c["entry_mode"])
    indexes = [i for i in np.flatnonzero(sides) if i+1<len(bars) and bars[i].time.year>=2010 and
               bars[i+1].time==bars[i].time+timedelta(minutes=minutes) and 6<=bars[i+1].time.hour<16 and adx[i]>=c["adx_min"]]
    meta = repo.metadata("XAUUSD")
    hourly_rows = simulate(bars,indexes,sides,frame.atr.to_numpy(),meta.spread_price,minutes,c["exit_mode"])
    hourly = admission_stats(hourly_rows)
    for m,e in zip(hourly,previous["results"]):
        for key in m:
            assert np.isclose(m[key],e[key]),key
    wanted = {dates[i+1] for i in indexes}
    print("READ_MINUTE_DAYS",len(wanted),flush=True)
    captured = capture_days(repo.bars("XAUUSD",bars[0].time,end,"1m"),wanted)
    hour_times = [b.time for b in bars]
    minute_times = {d:[b.time for b in v] for d,v in captured.items()}
    results, missing_opens = [], 0
    for multiplier in (1,2):
        rows = []
        missing = 0
        for k in indexes:
            day = dates[k+1]
            quotes = captured[day]
            entry_time = bars[k+1].time
            i = bisect_left(minute_times[day],entry_time)
            if i>=len(quotes) or quotes[i].time!=entry_time:
                missing += 1
                continue
            spread = meta.spread_price*multiplier
            atr = frame.atr.iloc[k]
            if c["exit_mode"].startswith("fixed"):
                trade = outcome(quotes,i,int(sides[k]),atr,spread,1,1.5 if c["exit_mode"]=="fixed1R" else 3,None)
            else:
                trade = managed_outcome(quotes,i,int(sides[k]),atr,spread,c["exit_mode"])
            if trade is None:
                raise ValueError("Unresolved selected minute trade")
            j,r,reason,late = trade
            exit_index = bisect_right(hour_times,quotes[j].time)-1
            rows.append((k+1,exit_index,quotes[j].time.year,r,25,55,0,entry_time.hour,late,reason=="target",spread/atr,reason=="time"))
        results.append(admission_stats(np.asarray(rows,dtype=float).reshape((-1,12))))
        missing_opens = missing
    gates = [m["n"]>=n and (m["pf"] or 0)>1 and m["mean_r"]>0 for m,n in zip(results[0],(250,100,50,50))]
    result = dict(selected=c,hourly_execution=hourly,minute_execution=results[0],minute_doubled_spread=results[1],
                  missing_minute_open_signals=missing_opens,gates=gates,adopted=all(gates),
                  captured_minutes=sum(len(v) for v in captured.values()),candidate_reselected=False,
                  limitations="Same previously inspected periods. Minute OHLC still uses stop-first if both barriers touch inside one minute.")
    path = ROOT/"scripts/gold_pf_minute_results.json"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RESULT_JSON",path,flush=True)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
