"""Finite, descriptive three-month search; preserves existing signals and RR1 fills."""
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json

from forextester_backtest import HistoryRepository
from research_strict_rr_portfolio import _prepare
from research_quant70 import simulate, stats, quality, dump
from quant70_signals import candidates as basic_candidates, signals as basic_signals
from quant70_intraday_signals import candidates, signals, daily_context
from revalidate_quant70_jpy import SYMBOLS, snapshot
from verify_quant70_results import summarize, close, require

ROOT = Path(__file__).resolve().parents[1]
ID = 'quant70_jpy_recent3m_20260908'
OUT = ROOT/'agent_runs'/ID
START, END = datetime(2026,6,8), datetime(2026,9,8)


def month_index(trade):
    # Entry cohorts partition the full-period trades; no artificial monthly liquidation.
    entry = datetime.fromisoformat(trade.entry_time)
    return 0 if entry < datetime(2026,7,8) else 1 if entry < datetime(2026,8,8) else 2


def checked_stats(trades, months):
    result = stats(trades, months)
    independent = summarize([(t.exit_time,t.symbol,t.entry_time,t.net_r,t.reason,t.ambiguous) for t in trades],months)
    for key,value in result.items(): close(value,independent[key],key)
    return result


def passes(summary, monthly, minimum):
    return (summary['trades']>=minimum and summary['net_win_rate_pct']>=70
            and summary['profit_factor'] is not None and summary['profit_factor']>=1.5
            and summary['expectancy_r']>0 and summary['realized_drawdown_pct']<=10
            and all(m['trades']>=10 and m['net_r']>0 for m in monthly))


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    specs = basic_candidates()+candidates()
    require(len(specs)==36 and len({s['name'] for s in specs})==36,'candidate budget')
    protocol = {'experiment_id':ID,'symbols':SYMBOLS,'start':START.isoformat(),'end_exclusive':END.isoformat(),
                'candidate_count':36,'candidates':specs,'timeframe':'15m','trend':'confirmed 4h',
                'execution':'Unchanged simulate: full RR1, ATR2, metadata spread, 0.1pip each side, next open, SL first on dual touch, period-end liquidation',
                'monthly':'Entry cohorts [Jun8,Jul8), [Jul8,Aug8), [Aug8,Sep8); positions may cross month edges. Final liquidation Sep7.',
                'aggregate_screen':'70% net wins, PF>=1.5, positive expectancy, >=75 trades, >=10 per pair, >=4 positive pairs, realized DD<=10%, each month >=10 trades and net R>0',
                'pair_screen':'Same metrics, >=30 trades, each month >=10 trades and net R>0; no cross-pair gate',
                'prior_exposure':'All three months already viewed. Descriptive selection on same sample, no unseen holdout or live approval.',
                'limits':'Fixed spread; no swap, variable spread, live execution or mark-to-market DD. Source-naive date, not verified JST.',
                'subagents_used':False,'retuning':False,'stop_rule':'Evaluate fixed 36 once; save all results regardless of failure'}
    dump(OUT/'protocol.json',protocol)
    paths=['scripts/research_jpy_recent3m.py','scripts/quant70_signals.py','scripts/quant70_intraday_signals.py',
           'scripts/research_quant70.py','scripts/research_strict_rr_portfolio.py','src/forextester_backtest/data.py',
           'scripts/verify_quant70_results.py','scripts/revalidate_quant70_jpy.py']
    dump(OUT/'code_hashes.json',{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})
    directory=Path(r'C:\ForexTester6\data\History'); repo=HistoryRepository(directory)
    before=snapshot(directory); dump(OUT/'source_before.json',before)
    combined={s['name']:[] for s in specs}; records={s['name']:{'candidate':s,'pairs':{},'pair_months':{}} for s in specs}
    manifest={}
    try:
        for symbol in SYMBOLS:
            require(snapshot(directory)==before,'history changed')
            print('Loading '+symbol,flush=True)
            data=_prepare(repo,symbol,END-timedelta(microseconds=1),'15m')
            meta=repo.metadata(symbol); require(meta.commission_per_lot==0,'unverified commission')
            manifest[symbol]={**quality(data,datetime(2010,1,1),END),'metadata':asdict(meta)}
            context=daily_context(data)
            for spec in specs:
                direction=signals(data,spec,context=context) if spec.get('selectable') else basic_signals(data,spec)
                trades=simulate(data,direction,symbol,START,END,0.01)
                combined[spec['name']].extend(trades)
                r=records[spec['name']]
                r['pairs'][symbol]=checked_stats(trades,3)
                r['pair_months'][symbol]=[checked_stats([t for t in trades if month_index(t)==i],1) for i in range(3)]
                with (OUT/'trades.jsonl').open('a',encoding='utf-8') as f:
                    for t in trades: f.write(json.dumps({'candidate':spec['name'],**asdict(t)},allow_nan=False)+'\n')
            dump(OUT/'data_manifest.json',manifest)
            print('Completed '+symbol,flush=True)
        after=snapshot(directory); dump(OUT/'source_after.json',after); require(before==after,'history changed')
        for name,r in records.items():
            trades=combined[name]
            r['summary']=checked_stats(trades,3)
            r['months']=[checked_stats([t for t in trades if month_index(t)==i],1) for i in range(3)]
            r['aggregate_screen_pass']=passes(r['summary'],r['months'],75) and all(s['trades']>=10 for s in r['pairs'].values()) and sum(s['net_r']>0 for s in r['pairs'].values())>=4
            r['pair_screen_passes']=[s for s in SYMBOLS if passes(r['pairs'][s],r['pair_months'][s],30)]
        # Re-read saved trade evidence; verify geometry and count, not just in-memory objects.
        n=0; last_exit={}
        with (OUT/'trades.jsonl').open(encoding='utf-8') as f:
            for line in f:
                t=json.loads(line); key=t['candidate'],t['symbol']
                st,en,ex=[datetime.fromisoformat(t[k]) for k in ('signal_time','entry_time','exit_time')]
                require(START<=st<en<=ex<END and en-st==timedelta(minutes=15),'period/entry ordering')
                require(key not in last_exit or st>last_exit[key],'overlap')
                last_exit[key]=ex
                d=t['direction']; risk=d*(t['entry']-t['stop']); require(risk>0,'risk')
                close(d*(t['target']-t['entry']),risk,'RR1')
                close(t['net_r'],d*(t['exit']-t['entry'])/risk,'net R'); n+=1
        require(n==sum(len(v) for v in combined.values()),'saved count')
        result={'status':'DESCRIPTIVE_COMPLETE','records':list(records.values()),'verified_trade_rows':n,'live_approved':False}
        dump(OUT/'results.json',result)
        print('RESULT_JSON='+json.dumps({'status':result['status'],'verified_trade_rows':n,
              'aggregate_passes':[k for k,v in records.items() if v['aggregate_screen_pass']],
              'pair_passes':{k:v['pair_screen_passes'] for k,v in records.items() if v['pair_screen_passes']}}),flush=True)
    except Exception as e:
        dump(OUT/'failure.json',{'type':type(e).__name__,'message':str(e)}); raise


if __name__=='__main__': main()
