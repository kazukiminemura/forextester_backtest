"""Three-year fixed 36-condition PF screen. Clock filters gate entries, never force exits."""
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np

from forextester_backtest import HistoryRepository
from research_strict_rr_portfolio import _prepare
from research_quant70 import quality, dump
from quant_rr_execution import simulate
from research_jpy_recent3m import checked_stats
START, END = datetime(2023,9,8), datetime(2026,9,8)


def month_index(trade):
    entry=datetime.fromisoformat(trade.entry_time)
    return (entry.year-2023)*12+entry.month-9-int(entry.day<8)

from simple_rr_signals import candidates, signals
from revalidate_quant70_jpy import SYMBOLS, snapshot
from verify_quant70_results import require, close, summarize

ROOT=Path(__file__).resolve().parents[1]
ID='quant_simple_rr13_15_three_year_20260908'
OUT=ROOT/'agent_runs'/ID
WINDOWS=[('all',0,24),('08_16',8,16)]


def filter_entries(direction,hours,start,end):
    return np.where((hours>=start)&(hours<end),direction,0)


def screen(summary,monthly,minimum):
    # PF is the objective: deliberately no 70% win-rate gate.
    return bool(summary['trades']>=minimum and summary['profit_factor'] is not None
                and summary['profit_factor']>=1.5 and summary['expectancy_r']>0
                and summary['realized_drawdown_pct']<=10
                and all(m['trades']>=10 and m['net_r']>0 for m in monthly))


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    specs=candidates()
    protocol={'id':ID,'symbols':SYMBOLS,'start':START.isoformat(),'end_exclusive':END.isoformat(),
              'candidates':specs,'windows':WINDOWS,'budget':36,'win_rate_gate':False,'reward_risks':[1.3,1.4,1.5],
              'execution':'Unchanged 15m confirmed 4h, full RR1:1.3/1.4/1.5 per candidate, ATR2, metadata spread, 0.1pip each side; next open; adverse SL-first; final-period liquidation.',
              'window_semantics':'Source-naive signal-bar start hour. Not verified JST or exchange sessions. Entry at next 15m open; positions can outlive window.',
              'screen':'PF>=1.5, expectancy>0, realized DD<=10%; total >=900 aggregate or >=360 individual; each entry-month >=10 trades and positive net R. Aggregate also each pair>=10 and >=4 profitable pairs.',
              'monthly':'36 monthly entry cohorts from Sep8 2023; annual cohorts Sep8-Sep8. No monthly forced exits.',
              'selection':'Descriptive only on already-seen three years. No untouched validation, no live approval. Stop at fixed 36 conditions; no result-driven retuning.',
              'limits':'Overlapping candidate trades; multiple comparisons. No swaps, variable spread, live slippage or mark-to-market DD. Fixed 0.25% initial risk for realized DD.',
              'subagents_used':False}
    dump(OUT/'protocol.json',protocol)
    paths=['scripts/research_simple_rr13_15.py','scripts/research_jpy_recent3m.py','scripts/quant_rr_execution.py','scripts/research_quant70.py',
           'scripts/simple_rr_signals.py','scripts/quant70_signals.py','scripts/quant70_intraday_signals.py','scripts/research_strict_rr_portfolio.py',
           'scripts/revalidate_quant70_jpy.py','scripts/verify_quant70_results.py','src/forextester_backtest/data.py']
    dump(OUT/'code_hashes.json',{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})
    directory=Path(r'C:\ForexTester6\data\History'); repo=HistoryRepository(directory)
    before=snapshot(directory); dump(OUT/'source_before.json',before)
    records={}; combined={}; manifest={}
    for spec in specs:
        for window,a,b in WINDOWS:
            name=spec['name']+'__'+window
            records[name]={'name':name,'candidate':spec,'window':window,'pairs':{},'pair_months':{}}
            combined[name]=[]
    try:
        for symbol in SYMBOLS:
            require(snapshot(directory)==before,'history changed')
            print('Loading '+symbol,flush=True)
            full=_prepare(repo,symbol,END-timedelta(microseconds=1),'15m')
            meta=repo.metadata(symbol); require(meta.commission_per_lot==0,'nonzero commission unverified')
            manifest[symbol]={**quality(full,datetime(2010,1,1),END),'metadata':asdict(meta)}
            indices=np.array([i for i,t in enumerate(full.times) if START<=t<END])
            recent=SimpleNamespace(times=[full.times[i] for i in indices],spread=full.spread,
                                   **{k:getattr(full,k)[indices] for k in ['open','high','low','close','atr']})
            hours=full.hours[indices]
            for spec in specs:
                direction=signals(full,spec)[indices]
                for window,a,b in WINDOWS:
                    name=spec['name']+'__'+window; r=records[name]
                    trades=simulate(recent,filter_entries(direction,hours,a,b),symbol,START,END,0.01,reward_risk=spec['reward_risk'])
                    combined[name].extend(trades)
                    r['pairs'][symbol]=checked_stats(trades,36)
                    r['pair_months'][symbol]=[checked_stats([t for t in trades if month_index(t)==i],1) for i in range(36)]
                    with (OUT/'trades.jsonl').open('a',encoding='utf-8') as f:
                        for t in trades: f.write(json.dumps({'condition':name,**asdict(t)},allow_nan=False)+'\n')
            dump(OUT/'data_manifest.json',manifest)
            print('Completed '+symbol,flush=True)
        after=snapshot(directory); dump(OUT/'source_after.json',after); require(before==after,'history changed')
        for name,r in records.items():
            trades=combined[name]
            r['summary']=checked_stats(trades,36)
            r['months']=[checked_stats([t for t in trades if month_index(t)==i],1) for i in range(36)]
            r['aggregate_pass']=screen(r['summary'],r['months'],900) and all(s['trades']>=10 for s in r['pairs'].values()) and sum(s['net_r']>0 for s in r['pairs'].values())>=4
            r['pair_passes']=[s for s in SYMBOLS if screen(r['pairs'][s],r['pair_months'][s],360)]
            r['years']=[checked_stats([t for t in trades if month_index(t)//12==i],12) for i in range(3)]
            r['pair_years']={s:[checked_stats([t for t in trades if t.symbol==s and month_index(t)//12==i],12) for i in range(3)] for s in SYMBOLS}
        dump(OUT/'results.json',{'status':'DESCRIPTIVE_COMPLETE','records':list(records.values()),'live_approved':False})
        print('RESULT_JSON='+json.dumps({'status':'DESCRIPTIVE_COMPLETE','aggregate_passes':[k for k,v in records.items() if v['aggregate_pass']],
              'pair_passes':{k:v['pair_passes'] for k,v in records.items() if v['pair_passes']}}),flush=True)
    except Exception as e:
        dump(OUT/'failure.json',{'type':type(e).__name__,'message':str(e)}); raise


if __name__=='__main__': main()
