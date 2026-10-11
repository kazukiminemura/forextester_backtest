"""Independent new-logic verification. Never changes the research implementation."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scripts import verify_ytt_monthly5_fx as checks

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "agent_runs/new_logic_20261011"
DOC = ROOT / "docs/quant_organization/experiments/new_logic_20261011"
ARMS = ("compression_retest", "compression_direct", "failed_excursion", "inside_edge_bounce")


def independent_events(times, prices, complete, tick, start, end):
    """Literal specification, recalculating each preceding window from OHLC."""
    n = len(times)
    events = {a: {k: np.full(n, np.nan) for k in ("stop", "atr", "room", "threshold")}
              for a in ARMS}
    for event in events.values():
        event["side"] = np.zeros(n, dtype=np.int8)
    pending = None
    previous = {a: -1000000 for a in ARMS}
    for i in range(n):
        if not start <= times[i] < end:
            pending = None
            previous = {a: -1000000 for a in ARMS}
            continue
        if i < 25 or not complete[i-25:i+1].all() or not (np.diff(times[i-25:i+1]) == 900).all():
            pending = None
            previous = {a: -1000000 for a in ARMS}
            continue
        op, hi, lo, close = prices[i]
        upper = prices[i-24:i, 1].max()
        lower = prices[i-24:i, 2].min()
        width = upper-lower
        middle = (upper+lower)/2
        true_ranges = [max(prices[j, 1]-prices[j, 2], abs(prices[j, 1]-prices[j-1, 3]),
                           abs(prices[j, 2]-prices[j-1, 3])) for j in range(i-20, i)]
        atr = sum(true_ranges)/20
        motion = np.abs(np.diff(prices[i-25:i, 3])).sum()
        efficiency = abs(prices[i-1, 3]-prices[i-25, 3])/motion if motion else 0.
        if width <= 0 or atr <= 0:
            continue

        def record(arm, side, stop, volatility, room, threshold):
            event = events[arm]
            for key, value in dict(side=side, stop=stop, atr=volatility, room=room, threshold=threshold).items():
                event[key][i] = value
            previous[arm] = i

        had_pending = pending is not None
        if pending is not None:
            direction, boundary, frozen_atr, armed_at = pending
            touched = lo <= boundary if direction == 1 else hi >= boundary
            confirmed = direction*(close-boundary) > 0 and direction*(close-op) > 0
            if touched:
                if confirmed:
                    stop = lo-tick if direction == 1 else hi+tick
                    record("compression_retest", direction, stop, frozen_atr, np.nan, boundary)
                pending = None
            elif i-armed_at >= 6:
                pending = None
        direction = 0
        if width <= 3*atr:
            if close > upper and close-op >= .5*atr:
                direction = 1
            elif close < lower and op-close >= .5*atr:
                direction = -1
        if direction and not had_pending:
            boundary = upper if direction == 1 else lower
            stop = lo-tick if direction == 1 else hi+tick
            record("compression_direct", direction, stop, atr, np.nan, boundary)
            if not had_pending:
                pending = (direction, boundary, atr, i)
        if not 3*atr <= width <= 8*atr or efficiency > .25:
            continue
        for arm in ("failed_excursion", "inside_edge_bounce"):
            if i-previous[arm] < 24:
                continue
            buy_touch = lo < lower if arm == "failed_excursion" else lower <= lo <= lower+.1*width
            sell_touch = hi > upper if arm == "failed_excursion" else upper-.1*width <= hi <= upper
            direction = (1 if buy_touch and lower < close < middle and close > op and hi < upper
                         else -1 if sell_touch and middle < close < upper and close < op and lo > lower else 0)
            if direction:
                stop = lo-tick if direction == 1 else hi+tick
                record(arm, direction, stop, atr, middle, lower if direction == 1 else upper)
    return events


def replay(z,a,rr,start,end,cost,normal_cost,cash):
    t,b=z['times'],z['prices'];indices=np.flatnonzero((t>=start)&(t<end))
    balance=1000000.;halt=False;stop_time='';peak=minimum=balance;dd=0.
    skipped=dict(occupied=0,invalid_risk=0,missing_entry=0,zero_quantity=0,cost_floor=0,atr_ceiling=0,insufficient_room=0)
    trades=[];curve=[];position=None
    for i in indices:
        op,hi,lo,cl=map(float,b[i]);stamp=int(t[i]);out=None;why=''
        gap=i>0 and (stamp-int(t[i-1])!=900 or not z['starts_at_open'][i])
        held_at_open=position is not None
        if held_at_open and gap:
            d=position['side'];out=op;why='data_gap_open'
            if d*op>d*position['target']:out=position['target'];why='data_gap_tp_capped'

        intent=i>0 and t[i-1]>=start and z['sides'][a,i-1]!=0 and not halt
        if held_at_open:
            skipped['occupied']+=int(intent)
        elif not halt and intent:
            if gap or stamp!=int(t[i-1])+900:
                skipped['missing_entry']+=1
            else:
                d=int(z['sides'][a,i-1]);sl=float(z['stops'][a,i-1]);risk=d*(op-sl)
                if not math.isfinite(risk) or risk<=0: skipped['invalid_risk']+=1
                elif risk<10*normal_cost:skipped['cost_floor']+=1
                elif risk>2*z['atrs'][a,i-1]:skipped['atr_ceiling']+=1
                elif math.isfinite(z['rooms'][a,i-1]) and d*(z['rooms'][a,i-1]-op)<2*risk:skipped['insufficient_room']+=1
                else:
                    qty=math.floor(min(.005*balance/(risk+cost),25*balance/op)/1000)*1000 if cash else 1.
                    if qty<=0:skipped['zero_quantity']+=1
                    else:
                        position=dict(entry=op,stop=sl,target=op+d*rr*risk,side=d,risk=risk,rr=float(rr),qty=float(qty),
                                      entry_time=stamp,signal_time=int(t[i-1])+900,threshold=float(z['thresholds'][a,i-1]),
                                      entry_index=int(i),incomplete_bars=0)
        if position is not None:
            p=position;d=p['side'];qstop=d*p['stop'];reason='sl';qtarget=d*p['target']
            if cash:
                qfloor=d*p['entry']+(900000-balance)/p['qty']+cost
                if qfloor>=qstop:qstop=qfloor;reason='account_floor'
            if out is None:
                qop=d*op;qlow=min(d*hi,d*lo);qhigh=max(d*hi,d*lo)
                if qop<=qstop:out=op;why=reason+'_gap'
                elif qop>=qtarget:out=p['target'];why='tp_gap_capped'
                elif qlow<=qstop:out=d*qstop;why=reason
                elif qhigh>=qtarget:out=p['target'];why='tp'
            if not z['complete'][i]:
                p['incomplete_bars']+=1
                if out is None:out=cl;why='incomplete_bar_close'
            if out is None and stamp%86400==85500:out=cl;why='daily_close'
            if out is None and i-p['entry_index']>=15:out=cl;why='max_16_bars'
            if out is None and i==indices[-1]:out=cl;why='period_end_mark'
            if cash:
                protective=out is not None and any(tag in why for tag in ('sl','account_floor','gap'))
                adverse=out if protective else (lo if d==1 else hi)
                worst=balance+p['qty']*(d*(adverse-p['entry'])-cost)
                minimum=min(minimum,worst);dd=max(dd,peak-worst)
            if out is not None:
                gross=d*(out-p['entry']);net=gross-cost;pnl=net*p['qty']
                exit_time=int(z['observed_open_times'][i]) if 'gap' in why else stamp+900
                if cash:
                    balance+=pnl
                    if why.startswith('account_floor') or balance<=900000+1e-7:
                        halt=True;stop_time=str(np.datetime64(int(exit_time),'s'))
                trades.append(dict(**p,exit_time=exit_time,exit_price=out,reason=why,cost_price=cost,
                                   gross_r=gross/p['risk'],net_r=net/p['risk'],net_price=net,
                                   pnl_yen=pnl if cash else 0.,balance_yen=balance if cash else 0.))
                position=None
        equity=balance
        if position is not None:
            equity+=position['qty']*(position['side']*(cl-position['entry'])-cost)
        if cash:
            peak=max(peak,equity);minimum=min(minimum,equity);curve.append((stamp+900,equity))
    account=dict(final_equity_yen=balance,net_yen=balance-1000000,stopped=halt,stop_time_source=stop_time,
                 minimum_equity_yen=minimum,max_observed_intrabar_drawdown_yen=dd,skipped=skipped)
    return trades,np.asarray(curve).reshape(-1,2),account


def metrics(rows):
    values = [float(r['net_r']) for r in rows]
    wins = [v for v in values if v > 0]
    losses = [v for v in values if v < 0]
    mean_win = sum(wins)/len(wins) if wins else None
    mean_loss = sum(losses)/len(losses) if losses else None
    return dict(**checks.stats(rows), win_rate=len(wins)/len(rows) if rows else None,
                realized_payoff_rr=mean_win/abs(mean_loss) if wins and losses else None,
                mean_win_r=mean_win, mean_loss_r=mean_loss,
                reason_counts={r:sum(x['reason']==r for x in rows) for r in sorted({x['reason'] for x in rows})})


def compare_csv(path, rows):
    with path.open(encoding='utf-8', newline='') as stream:
        saved = list(csv.DictReader(stream))
    assert len(rows) == len(saved), (str(path),len(rows),len(saved))
    for actual, expected in zip(rows, saved):
        expected = {k: v if k == 'reason' else float(v) for k,v in expected.items()}
        checks.eq(actual, expected, path.name)


def main():
    import argparse
    from scripts import research_new_logic_20261011 as research
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', default='training')
    phase = parser.parse_args().phase
    target = OUT/phase
    protocol = json.loads((DOC/'protocol.json').read_text())
    result = json.loads((target/'results.json').read_text())
    manifest = json.loads((target/'run_manifest.json').read_text())
    start,end = map(checks.seconds, protocol['periods'][phase])
    for name, digest in manifest['files'].items():
        assert checks.sha(ROOT/name) == digest, name
    assert checks.sha(target/'results.json') == manifest['results_sha256']
    configurations = sorted({(r['arm'],r['rr']) for r in result['records']})
    pooled, accounts = {}, {}
    prefix_checks = csv_files = observations = 0
    for symbol in protocol['symbols']:
        cache = ROOT/protocol['cache_directory']/f'{symbol}_execution.npz'
        assert checks.sha(cache) == protocol['input_sha256'][symbol]
        with np.load(cache, allow_pickle=False) as source:
            data = {k:source[k].copy() for k in ('times','prices','complete','starts_at_open','observed_open_times')}
        mask = data['times'] < end
        data = {k:v[mask] for k,v in data.items()}
        costs = protocol['cost_and_fill_model']
        cost = costs['pip'][symbol]*costs['round_trip_pips'][symbol]
        independent = independent_events(data['times'],data['prices'],data['complete'],costs['tick'][symbol],start,end)
        key_map = dict(sides='side',stops='stop',atrs='atr',rooms='room',thresholds='threshold')
        sig = {key:np.array([independent[a][field] for a in ARMS]) for key,field in key_map.items()}
        with np.load(target/f'{symbol}_signals.npz',allow_pickle=False) as saved:
            checks.arr(data['times'],saved['times'],'times')
            for key,values in sig.items():
                checks.arr(values,saved[key],symbol+'/'+key,1e-10)
        for cut in (len(data['times'])//3,len(data['times'])//2,len(data['times'])-3):
            prefix = research.signals(data['times'][:cut],data['prices'][:cut],data['complete'][:cut],costs['tick'][symbol],start,end)
            for key in sig:
                checks.arr(prefix[key],sig[key][:,:cut],symbol+'/prefix/'+key,1e-10)
            prefix_checks += 1
        merged = dict(**data,**sig)
        for arm,rr in configurations:
            for multiplier in (1,2):
                key = f'{arm}_rr{rr:g}_cost{multiplier}'
                rows,_,details = replay(merged,ARMS.index(arm),rr,start,end,cost*multiplier,cost,False)
                compare_csv(target/f'{symbol}_{key}.csv',rows)
                csv_files += 1; observations += len(rows)
                record = next(r for r in result['records'] if r['symbol']==symbol and r['arm']==arm and r['rr']==rr and r['cost_multiplier']==multiplier)
                checks.eq(record,metrics(rows),symbol+'/'+key)
                checks.eq(record['skipped'],details['skipped'],symbol+'/skipped')
                with np.load(target/f'{symbol}_{key}_closed_r_curve.npz') as curve:
                    checks.arr([x['exit_time'] for x in rows],curve['times'],key+'/time')
                    checks.arr(np.cumsum([x['net_r'] for x in rows]),curve['equity_r'],key+'/R',1e-8)
                for month in record['monthly']:
                    selected = [r for r in rows if checks.date(checks.economic_time(r))[:7]==month['month']]
                    checks.eq(month,checks.stats(selected),key+'/'+month['month'])
                for year in record['annual']:
                    selected = [r for r in rows if checks.date(checks.economic_time(r))[:4]==str(year['year'])]
                    checks.eq(year,metrics(selected),key+'/'+str(year['year']))
                pooled.setdefault(key,[]).extend([dict(symbol=symbol,**r) for r in rows])
                if symbol == 'USDJPY':
                    cash_rows,curve,account = replay(merged,ARMS.index(arm),rr,start,end,cost*multiplier,cost,True)
                    compare_csv(target/f'{symbol}_{key}_cash.csv',cash_rows)
                    csv_files += 1; observations += len(cash_rows)
                    checks.eq(result['usdjpy_accounts'][key],account,key+'/account')
                    checks.eq(result['usdjpy_accounts'][key],metrics(cash_rows),key+'/cashmetrics')
                    with np.load(target/f'{symbol}_{key}_cash_curve.npz') as saved:
                        checks.arr(curve,saved['curve'],key+'/cashcurve',1e-6)
                    prior=1000000.
                    for month in result['usdjpy_accounts'][key]['monthly']:
                        selected=[r for r in cash_rows if checks.date(checks.economic_time(r))[:7]==month['month']]
                        checks.eq(month,checks.stats(selected),key+'/cashmonth')
                        boundary=int((np.datetime64(month['month'],'M')+1).astype('datetime64[s]').astype(np.int64))
                        available=curve[curve[:,0]<=boundary]
                        equity=float(available[-1,1]) if len(available) else prior
                        ret=equity/prior-1
                        checks.eq(month,dict(equity_yen=equity,pnl_yen=equity-prior,monthly_return=ret,reaches_5_percent=ret>=.05))
                        assert 'goal_met' not in month
                        prior=equity
                    accounts[key] = account
        print('VERIFIED',symbol,flush=True)
    for key,rows in pooled.items():
        rows.sort(key=lambda r:(r['exit_time'],r['symbol'],r['entry_time']))
        checks.eq(result['pooled_equal_r'][key],metrics(rows),key+'/pooled')
    gates = protocol['acceptance_gates']
    passed=[]
    for screen in result['screens']:
        arm,rr = screen['arm'],screen['rr']; key=f'{arm}_rr{rr:g}'
        normal=metrics(pooled[key+'_cost1']); stress=metrics(pooled[key+'_cost2'])
        symbols=[metrics([r for r in pooled[key+'_cost1'] if r['symbol']==s]) for s in protocol['symbols']]
        positive=[max(0,s['net_r']) for s in symbols]
        concentration=max(positive)/sum(positive) if sum(positive) else 1.
        control=protocol['baseline'][arm]
        expected=dict(count=normal['trades']>=gates['aggregate_trades_min'],
                      per_symbol_count=all(s['trades']>=gates['per_symbol_trades_min'] for s in symbols),
                      normal_pf=normal['pf'] is not None and normal['pf']>=gates['normal_pf_min'],normal_mean=normal['mean_net_r']>0,
                      stress_pf=stress['pf'] is not None and stress['pf']>gates['stress_pf_strict_min'],stress_mean=stress['mean_net_r']>0,
                      profitable_symbols=sum(s['net_r']>0 for s in symbols)>=gates['profitable_symbols_min'],
                      concentration=concentration<=gates['max_positive_symbol_contribution'],
                      no_usdjpy_halt=not accounts[key+'_cost1']['stopped'],
                      above_control=normal['mean_net_r']>metrics(pooled[f'{control}_rr{rr:g}_cost1'])['mean_net_r'])
        checks.eq(screen['checks'],expected,key+'/gates')
        checks.eq(screen['passes'],all(expected.values()),key+'/pass')
        checks.eq(screen['positive_symbol_concentration'],concentration)
        if all(expected.values()): passed.append((arm,rr))
    passed.sort(key=lambda x:(-metrics(pooled[f'{x[0]}_rr{x[1]:g}_cost1'])['pf'],
                              -metrics(pooled[f'{x[0]}_rr{x[1]:g}_cost1'])['mean_net_r'],
                              -len(pooled[f'{x[0]}_rr{x[1]:g}_cost1']),x[0],x[1]))
    checks.eq(result['selected'],dict(arm=passed[0][0],rr=passed[0][1]) if passed else None)
    evidence=dict(status='PASS_INDEPENDENT_REPLAY',phase=phase,csv_files=csv_files,trade_observations=observations,
                  prefix_checks=prefix_checks,counts=dict(checks.counts),selected=result['selected'],
                  research_status=result['status'],validator_sha256=checks.sha(Path(__file__)),
                  result_sha256=checks.sha(target/'results.json'),adoption_approved=False)
    (target/'independent_validation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence),flush=True)


if __name__ == '__main__':
    main()
