"""Frozen-signal diagnostic rerun on refreshed JPY history; never selects a strategy."""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
from forextester_backtest import HistoryRepository
from research_strict_rr_portfolio import _prepare
from research_quant70 import simulate, stats, quality, rejection_reasons, dump
from quant70_intraday_signals import candidates, comparators, signals, daily_context
from research_quant70_intraday import context_effect
from verify_quant70_results import summarize, close, require, qualifies

ROOT = Path(__file__).resolve().parents[1]
ID = 'quant70_intraday_jpy_refreshed_20260908'
SYMBOLS = ['AUDJPY', 'CHFJPY', 'EURJPY', 'GBPJPY', 'NZDJPY']
PERIODS = {'train': ('2010-01-01', '2019-01-01'),
           'validation': ('2019-01-01', '2023-01-01'),
           'confirmation': ('2023-01-01', '2025-01-01'),
           'recent_reference': ('2025-01-01', '2026-09-08')}


def month_count(start, end):
    """Whole calendar months plus fractional final month (exclusive end)."""
    import calendar
    assert start.day == 1
    return (end.year-start.year)*12+end.month-start.month+(end.day-1)/calendar.monthrange(end.year,end.month)[1]


def snapshot(directory):
    return {s: {'size': (p := directory/s/'Bars.dat').stat().st_size,
                'mtime_ns': p.stat().st_mtime_ns} for s in SYMBOLS}


def protocol():
    p = json.loads((ROOT/'docs/quant_organization/experiments/quant70_intraday_jpy_20260908/protocol.json').read_text(encoding='utf-8'))
    p.update(experiment_id=ID, symbols=SYMBOLS, periods=PERIODS,
             universe='Five non-USD JPY crosses with complete refreshed history; NZDJPY now available. CADJPY absent.',
             selection='Diagnostic rerun only: all frozen candidates and controls across all periods. No selection, no retuning, no live approval. Later periods are descriptive, not untouched holdout. Report all-period gates, but passing needs a separate validation decision.',
             stress='Not a selection experiment; no stress test and no adoption permitted.',
             gate_adjustment='ceil(8/11 * 5) = 4 positive pairs; all other absolute and context gates unchanged.',
             data_manifest=f'agent_runs/{ID}/data_manifest.json',
             code_identifier=f'agent_runs/{ID}/code_hashes.json',
             frozen_at='Before performance evaluation of refreshed history in this run',
             prior_exposure='All periods may have been seen in earlier research. Frozen 12 intraday candidates unchanged; historical data may have vendor revisions.',
             operator='Single primary agent, no subagents; separate-formula reconciliation is not independent-person review.')
    p['gates']['min_positive_pairs'] = 4
    p['execution']['max_positions'] = 'one per symbol; up to 5 aggregate'
    return p


def reconcile(output):
    read = lambda name: json.loads((output/name).read_text(encoding='utf-8'))
    p, result = read('protocol.json'), read('results.json')
    for path, digest in read('code_hashes.json').items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, f'code drift {path}')
    dates = {k: tuple(map(datetime.fromisoformat,v)) for k,v in p['periods'].items()}
    names = {s['name'] for s in read('candidates.json')+read('comparators.json')} | {'baseline_htf_hourly'}
    require(len(names) == 25 and {r['candidate']['name'] for r in result['records']} == names, 'candidate scope')
    groups, last_exit = defaultdict(list), {}
    count = 0
    with (output/'trades.jsonl').open(encoding='utf-8') as f:
        for line in f:
            t = json.loads(line)
            key = t['candidate'],t['period'],t['symbol']
            require(key[0] in names and key[1] in dates and key[2] in SYMBOLS, 'trade scope')
            st,en,ex = [datetime.fromisoformat(t[k]) for k in ('signal_time','entry_time','exit_time')]
            a,b = dates[key[1]]
            require(a <= st < en <= ex < b and en-st == timedelta(minutes=15), 'split/entry ordering')
            require(key not in last_exit or st > last_exit[key], 'overlap/reused signal')
            last_exit[key] = ex
            d = t['direction']; risk = d*(t['entry']-t['stop'])
            require(d in (-1,1) and risk > 0, 'positive directional risk')
            close(d*(t['target']-t['entry']),risk,'RR1 geometry')
            close(t['net_r'],d*(t['exit']-t['entry'])/risk,'net R')
            if t['reason'] in ('target','target_gap','stop'):
                barrier = t['stop'] if t['reason']=='stop' else t['target']
                close(t['exit'],barrier-d*0.001,'exit cost')
            groups[key].append((t['exit_time'],key[2],t['entry_time'],t['net_r'],t['reason'],t['ambiguous']))
            count += 1
    eligible = []
    for r in result['records']:
        name = r['candidate']['name']
        for period,(a,b) in dates.items():
            combined, pairs = [], {}
            for symbol in SYMBOLS:
                rows = groups[name,period,symbol]
                independent = summarize(rows,month_count(a,b))
                for k,v in r['pairs'][period][symbol].items(): close(v,independent[k],f'{name}/{period}/{symbol}/{k}')
                pairs[symbol] = independent
                combined.extend(rows)
            independent = summarize(combined,month_count(a,b))
            for k,v in r['periods'][period].items(): close(v,independent[k],f'{name}/{period}/{k}')
            require(qualifies(independent,pairs,period,p['gates']) == (not r['absolute_rejections'][period]), 'gate disagreement')
        if r['candidate'].get('selectable') and not any(r['absolute_rejections'].values()) and all(e['passes'] for e in r['context_effects'].values()):
            eligible.append(name)
    require(eligible == result['all_period_gate_passes'], 'overall gate disagreement')
    require(read('source_before.json') == read('source_after.json'), 'history changed during run')
    dump(output/'reconciliation.json', {'status':'VERIFIED', 'trade_rows':count, 'all_period_gate_passes':eligible,
                                       'independent_person_review':False})
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history-dir', type=Path, default=Path(r'C:\ForexTester6\data\History'))
    parser.add_argument('--output', type=Path, default=ROOT/'agent_runs'/ID)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if args.verify_only:
        print('VERIFIED_ROWS='+str(reconcile(args.output)),flush=True); return
    out = args.output
    out.mkdir(parents=True,exist_ok=False)
    p = protocol(); dump(out/'protocol.json',p)
    specs, controls = candidates(), comparators()
    dump(out/'candidates.json',specs); dump(out/'comparators.json',controls)
    paths = ['scripts/revalidate_quant70_jpy.py','scripts/research_quant70_intraday.py',
             'scripts/quant70_intraday_signals.py','scripts/research_quant70.py',
             'scripts/quant70_signals.py','scripts/research_strict_rr_portfolio.py',
             'src/forextester_backtest/data.py','scripts/verify_quant70_results.py']
    dump(out/'code_hashes.json',{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths})
    before = snapshot(args.history_dir); dump(out/'source_before.json',before)
    repo = HistoryRepository(args.history_dir)
    dump(out/'history_inventory.json',{s:{k:str(v) if isinstance(v,datetime) else v for k,v in asdict(repo.summary(s)).items()} for s in SYMBOLS})
    dates = {k:tuple(map(datetime.fromisoformat,v)) for k,v in PERIODS.items()}
    all_specs = specs+controls+[{'name':'baseline_htf_hourly','family':'baseline','selectable':False}]
    combined = defaultdict(list)
    records = {s['name']:{'candidate':s,'pairs':{},'periods':{},'absolute_rejections':{},'context_effects':{}} for s in all_specs}
    manifest = {}
    try:
        for symbol in SYMBOLS:
            require(snapshot(args.history_dir) == before,'history changed before load')
            print(f'Loading {symbol}: 2010-01-01 to 2026-09-08',flush=True)
            data = _prepare(repo,symbol,datetime(2026,9,8)-timedelta(microseconds=1),'15m')
            meta = repo.metadata(symbol)
            require(meta.commission_per_lot == 0,'nonzero commission unverified')
            manifest[symbol] = {**quality(data,datetime(2010,1,1),datetime(2026,9,8)),'metadata':asdict(meta)}
            context = daily_context(data)
            dump(out/'data_manifest.json',manifest)
            for a,b in dates.values():
                subset = [t for t in data.times if a<=t<b]
                require(bool(subset) and subset[0]<=a+timedelta(days=7) and subset[-1]>=b-timedelta(days=7),'period edge gap')
            for spec in all_specs:
                if spec['family']=='baseline':
                    direction = np.where(data.minutes==0,data.htf_trend,0).astype(np.int8); direction[:208]=0
                else: direction = signals(data,spec,context=context)
                for period,(a,b) in dates.items():
                    trades = simulate(data,direction,symbol,a,b,0.01,0.1,1.0)
                    combined[spec['name'],period].extend(trades)
                    records[spec['name']]['pairs'].setdefault(period,{})[symbol] = stats(trades,month_count(a,b))
                    with (out/'trades.jsonl').open('a',encoding='utf-8') as f:
                        for t in trades: f.write(json.dumps({'candidate':spec['name'],'period':period,**asdict(t)},allow_nan=False)+'\n')
            print(f'Completed {symbol}',flush=True)
            dump(out/'progress.json',{'last_completed_symbol':symbol})
        after = snapshot(args.history_dir); dump(out/'source_after.json',after)
        require(after == before,'history changed during evaluation')
        for name,r in records.items():
            for period,(a,b) in dates.items():
                summary = stats(combined[name,period],month_count(a,b))
                r['periods'][period] = summary
                r['absolute_rejections'][period] = rejection_reasons(summary,r['pairs'][period],'recent' if period=='recent_reference' else period,p['gates'])
        for c in controls:
            r = records[c['comparison_of']]
            for period in ('train','validation'):
                r['context_effects'][period] = context_effect(r['periods'][period],records[c['name']]['periods'][period])
        passes = [s['name'] for s in specs if not any(records[s['name']]['absolute_rejections'].values()) and all(e['passes'] for e in records[s['name']]['context_effects'].values())]
        result = {'status':'DIAGNOSTIC_COMPLETE','records':list(records.values()),'all_period_gate_passes':passes,
                  'selected':None,'live_approved':False,'subagents_used':False}
        dump(out/'results.json',result)
        n = reconcile(out)
        print('RESULT_JSON='+json.dumps({'status':result['status'],'all_period_gate_passes':passes,'verified_trade_rows':n,'output':str(out)}),flush=True)
    except Exception as e:
        dump(out/'failure.json',{'type':type(e).__name__,'message':str(e)})
        raise


if __name__=='__main__':
    main()
