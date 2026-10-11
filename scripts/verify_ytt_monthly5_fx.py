"""Independent raw-M1 reconstruction and full accounting verification; no research imports."""
import csv
import hashlib
import json
import math
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "agent_runs/ytt_monthly5_fx_20261009"
DOC = ROOT / "docs/quant_organization/experiments/ytt_monthly5_fx_20261009"
ARMS = ("dw_m15", "dw_h1", "no_htf_h1")
counts = defaultdict(int)

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def eq(actual, expected, context=''):
    if isinstance(expected, dict):
        for key,value in expected.items():
            eq(actual[key],value,context+'/'+key)
    elif isinstance(expected, (str,bool)) or expected is None:
        assert actual == expected, (context,actual,expected)
    elif isinstance(expected,(list,tuple)):
        assert len(actual)==len(expected),(context,len(actual),len(expected))
        for i,v in enumerate(expected): eq(actual[i],v,f'{context}/{i}')
    else:
        assert np.isclose(float(actual),float(expected),rtol=1e-11,atol=1e-8,equal_nan=True),(context,actual,expected)
    counts['compared_items']+=1

def arr(actual,expected,context,tolerance=1e-11):
    np.testing.assert_allclose(actual,expected,rtol=0,atol=tolerance,equal_nan=True,err_msg=context)
    counts['array_values']+=int(np.size(expected))

def seconds(text): return int(np.datetime64(text,'s').astype(np.int64))

def date(t): return str(np.datetime64(int(t),'s'))

def structure(bars):
    n=len(bars)
    newh=np.zeros(n,bool);newl=np.zeros(n,bool)
    if n>=5:
        wh=np.lib.stride_tricks.sliding_window_view(bars[:,1],5)
        wl=np.lib.stride_tricks.sliding_window_view(bars[:,2],5)
        newh[4:]=(wh[:,2]>=wh[:,:2].max(1))&(wh[:,2]>wh[:,3:].max(1))
        newl[4:]=(wl[:,2]<=wl[:,:2].min(1))&(wl[:,2]<wl[:,3:].min(1))
    hi=lo=np.nan;direction=0
    hs=np.empty(n);ls=np.empty(n);ds=np.empty(n,dtype=np.int8)
    for i in range(n):
        if i:
            up=bars[i-1,3]<=hi<bars[i,3]
            dn=bars[i,3]<lo<=bars[i-1,3]
            if up and not dn: direction=1
            if dn and not up: direction=-1
        if newh[i]: hi=bars[i-2,1]
        if newl[i]: lo=bars[i-2,2]
        hs[i],ls[i],ds[i]=hi,lo,direction
    return dict(high=hs,low=ls,direction=ds,new_high=newh,new_low=newl)

def stats(rows):
    pos=neg=running=peak=dd=0.;wins=0
    for r in rows:
        x=float(r['net_r']);running+=x;peak=max(peak,running);dd=max(dd,peak-running)
        pos+=max(0,x);neg+=max(0,-x);wins+=x>0
    return dict(trades=len(rows),net_r=running,mean_net_r=running/len(rows) if rows else 0.,
                pf=pos/neg if neg else None,wins=wins,max_closed_trade_dd_r=dd,
                incomplete_exposed_trades=sum(int(r['incomplete_bars'])>0 for r in rows))

def replay(z,a,start,end,cost,cash):
    t,b=z['times'],z['prices'];indices=np.flatnonzero((t>=start)&(t<end))
    balance=1000000.;halt=False;stop_time='';peak=minimum=balance;dd=0.
    skipped=dict(occupied=0,nonpositive_risk=0,missing_entry=0,zero_quantity=0)
    trades=[];curve=[];position=None
    for i in indices:
        op,hi,lo,cl=map(float,b[i]);stamp=int(t[i]);out=None;why=''
        gap=i>0 and (stamp-int(t[i-1])!=900 or not z['starts_at_open'][i])
        held_at_open=position is not None
        if held_at_open and gap:
            d=position['side'];out=op;why='data_gap_open'
            if d*op>d*position['target']:out=position['target'];why='data_gap_tp_capped'
            if cash and balance+position['qty']*(d*(op-position['entry'])-cost)<=900000:
                why='account_floor_gap'
        intent=i>0 and z['sides'][a,i-1]!=0
        if held_at_open:
            skipped['occupied']+=int(intent)
        elif not halt and intent:
            if gap or stamp!=int(t[i-1])+900:
                skipped['missing_entry']+=1
            else:
                d=int(z['sides'][a,i-1]);sl=float(z['stops'][a,i-1]);risk=d*(op-sl)
                if not math.isfinite(risk) or risk<=0: skipped['nonpositive_risk']+=1
                else:
                    qty=math.floor(min(.005*balance/(risk+cost),25*balance/op)/1000)*1000 if cash else 1.
                    if qty<=0:skipped['zero_quantity']+=1
                    else:
                        position=dict(entry=op,stop=sl,target=op+d*risk,side=d,risk=risk,qty=float(qty),
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
            if out is None and i-p['entry_index']>=95:out=cl;why='max_96_bars'
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
                        halt=True;stop_time=date(exit_time)
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


def aggregate(raw_times, raw_prices, width, anchor=0):
    labels, first, number = np.unique((raw_times-anchor)//width*width+anchor,
                                      return_index=True, return_counts=True)
    last = first+number-1
    prices = np.column_stack((raw_prices[first, 0], np.maximum.reduceat(raw_prices[:, 1], first),
                              np.minimum.reduceat(raw_prices[:, 2], first), raw_prices[last, 3]))
    complete = ((number == width//60) & (raw_times[first] == labels)
                & (raw_times[last] == labels+width-60))
    return labels, prices, complete, raw_times[first]


def calendar_context(lower, upper, state, width, anchor):
    direction = np.zeros(len(lower), np.int8)
    ready = np.zeros(len(lower), bool)
    pointer = -1
    for i, timestamp in enumerate(lower):
        boundary = (int(timestamp)-anchor)//width*width+anchor
        while pointer+1 < len(upper) and upper[pointer+1]+width <= boundary:
            pointer += 1
        if pointer >= 0:
            ready[i] = (state['direction'][pointer] != 0 and np.isfinite(state['high'][pointer])
                        and np.isfinite(state['low'][pointer]))
            if ready[i]: direction[i] = state['direction'][pointer]
    return direction, ready


def event_states(prices, state, daily, weekly, tick):
    side = np.zeros((2, len(prices)), np.int8)
    stop = np.full(side.shape, np.nan)
    threshold = np.full(side.shape, np.nan)
    consumed = {1: False, -1: False}
    for i in range(len(prices)):
        if i:
            levels = {1: state['high'][i-1], -1: state['low'][i-1]}
            for d in (1, -1):
                cross = d*(prices[i, 3]-levels[d]) > 0 and d*(prices[i-1, 3]-levels[d]) <= 0
                if cross and not consumed[d]:
                    for a in (0, 1):
                        if a == 1 or daily[i] == weekly[i] == d:
                            side[a, i] = d
                            stop[a, i] = levels[-d]-d*tick
                            threshold[a, i] = levels[d]
                consumed[d] |= bool(d*(prices[i, 3]-levels[d]) > 0)
        if state['new_high'][i]: consumed[1] = bool(prices[i, 3] > state['high'][i])
        if state['new_low'][i]: consumed[-1] = bool(prices[i, 3] < state['low'][i])
    return side, stop, threshold


def prepare(raw_times, raw_prices, tick):
    t, p, full, actual = aggregate(raw_times, raw_prices, 900)
    execution = dict(times=t, prices=p, complete=full, starts_at_open=actual == t,
                     observed_open_times=actual, sides=np.zeros((3, len(t)), np.int8),
                     stops=np.full((3, len(t)), np.nan), thresholds=np.full((3, len(t)), np.nan))
    calendars = {}
    for label, width, anchor in [('D1', 86400, 0), ('W1', 604800, 345600)]:
        ct, cp, _, _ = aggregate(raw_times, raw_prices, width, anchor)
        calendars[label] = dict(times=ct, prices=cp, **structure(cp))
    entries = {}
    lookup = {int(v): i for i, v in enumerate(t)}
    for width in (900, 3600):
        et, ep, valid, _ = aggregate(raw_times, raw_prices, width)
        et, ep = et[valid], ep[valid]
        state = structure(ep)
        day, day_ready = calendar_context(et, calendars['D1']['times'], calendars['D1'], 86400, 0)
        week, week_ready = calendar_context(et, calendars['W1']['times'], calendars['W1'], 604800, 345600)
        sides, stops, levels = event_states(ep, state, day, week, tick)
        entries[width] = dict(times=et, prices=ep, daily=day, weekly=week, daily_ready=day_ready,
                              weekly_ready=week_ready, sides=sides, stops=stops, thresholds=levels, **state)
        for j, timestamp in enumerate(et):
            i = lookup[int(timestamp)+width-900]
            for target, source in ([(0, 0)] if width == 900 else [(1, 0), (2, 1)]):
                execution['sides'][target, i] = sides[source, j]
                execution['stops'][target, i] = stops[source, j]
                execution['thresholds'][target, i] = levels[source, j]
    return execution, calendars, entries


def calendar_quality(m5_times, m5_full, labels, width):
    answer = []
    for start in labels:
        mask = (m5_times >= start) & (m5_times < start+width)
        timestamps = m5_times[mask]
        days = np.unique(timestamps//86400)
        missing = sum(int((subset[-1]-subset[0])//300+1-len(subset))
                      for day in days for subset in [timestamps[timestamps//86400 == day]])
        answer.append(dict(start=int(start), available_at=int(start+width), observed_m5=len(timestamps),
                           complete_m5=int(m5_full[mask].sum()), complete_m5_ratio=float(m5_full[mask].mean()),
                           observed_calendar_days=len(days), weekdays=sorted(set(int((day+3)%7) for day in days)),
                           within_observed_day_missing_m5=missing, unobserved_calendar_days=width//86400-len(days)))
    return answer


def economic_time(row):
    return int(row['exit_time'])-int('gap' not in row['reason'])


def month_range(start, end):
    return [str(m) for m in np.arange(np.datetime64(date(start)[:7], 'M'), np.datetime64(date(end)[:7], 'M'))]


def monthly(rows, start, end, curve=None):
    answer = []
    prior = 1000000.
    for month in month_range(start, end):
        lo, hi = seconds(month), int((np.datetime64(month, 'M')+1).astype('datetime64[s]').astype(np.int64))
        chosen = [r for r in rows if lo <= economic_time(r) < hi]
        if curve is None:
            answer.append(dict(month=month, net_pips=sum(r['net_pips'] for r in chosen), **stats(chosen)))
        else:
            at = int(np.searchsorted(curve[:, 0], hi, side='right'))-1
            equity = float(curve[at, 1]) if at >= 0 else prior
            ret = (equity-prior)/prior if prior > 0 else None
            answer.append(dict(month=month, start_equity_yen=prior, equity_yen=equity, pnl_yen=equity-prior,
                               monthly_return=ret, trades=len(chosen), realized_pnl_yen=sum(r['pnl_yen'] for r in chosen),
                               reaches_5_percent=ret is not None and ret >= .05,
                               reaches_fixed_50000=equity-prior >= 50000))
            prior = equity
    return answer


def return_summary(months):
    returns = [m['monthly_return'] for m in months]
    valid = bool(returns) and all(r is not None and math.isfinite(r) and r > -1 for r in returns)
    geo = lambda rr: math.expm1(math.fsum(math.log1p(r) for r in rr)/len(rr))
    shortened = list(returns)
    if valid: shortened.remove(max(shortened))
    run = longest = 0
    for month in months:
        run = 0 if month['reaches_5_percent'] else run+1
        longest = max(longest, run)
    success = sum(m['reaches_5_percent'] for m in months)
    fixed = sum(m['reaches_fixed_50000'] for m in months)
    return dict(months=len(months), geometric_monthly_return=geo(returns) if valid else None,
                arithmetic_monthly_return=math.fsum(returns)/len(returns) if valid else None,
                median_monthly_return=float(np.median(returns)) if valid else None,
                worst_monthly_return=min(returns) if valid else None,
                best_monthly_return=max(returns) if valid else None,
                geometric_without_one_best_month=geo(shortened) if valid and shortened else None,
                max_consecutive_months_below_5_percent=longest, months_reaching_5_percent=success,
                ratio_months_reaching_5_percent=success/len(months), ratio_months_reaching_fixed_50000=fixed/len(months),
                every_month_reaches_5_percent=success == len(months))


def account_window(rows, months, curve, account, start, end):
    selected_months = [m for m in months if start <= seconds(m['month']) < end]
    selected = [r for r in rows if start <= economic_time(r) < end]
    profits = [r['pnl_yen'] for r in selected]
    gains, losses = sum(max(v, 0) for v in profits), -sum(min(v, 0) for v in profits)
    initial, final = selected_months[0]['start_equity_yen'], selected_months[-1]['equity_yen']
    peak, dd = initial, 0.
    for value in curve[(curve[:, 0] > start) & (curve[:, 0] <= end), 1]:
        peak = max(peak, value)
        dd = max(dd, peak-value)
    stopped = account['stopped'] and economic_time(rows[-1]) < end
    return dict(**return_summary(selected_months), trades=len(selected), starting_equity_yen=initial,
                ending_equity_yen=final, net_yen=final-initial, realized_net_yen=sum(profits),
                pf_jpy=gains/losses if losses else None, max_close_drawdown_yen=float(dd),
                halted_by_period_end=bool(stopped), stop_time_source=account['stop_time_source'])


def normal_gate(row):
    return dict(geometric_monthly_5pct=row['geometric_monthly_return'] is not None and row['geometric_monthly_return'] >= .05,
                pf_jpy=row['pf_jpy'] is not None and row['pf_jpy'] >= 1.2, net_yen=row['net_yen'] > 0,
                trades=row['trades'] >= 100, monthly_median=row['median_monthly_return'] is not None and row['median_monthly_return'] > 0,
                no_stop=not row['halted_by_period_end'])


def compare_trades(name, rows, months, curve=None):
    with (OUT/(name+'.csv')).open(encoding='utf-8', newline='') as stream:
        saved = list(csv.DictReader(stream))
    eq(saved, rows, name)
    eq(json.loads((OUT/(name+'_monthly.json')).read_text(encoding='utf-8')), months, name+'/months')
    counts['trade_files'] += 1
    counts['trade_observations'] += len(rows)
    counts['monthly_rows'] += len(months)
    if curve is not None:
        with np.load(OUT/(name+'_equity.npz'), allow_pickle=False) as saved:
            arr(saved['curve'], curve, name+'/curve', 1e-6)
        counts['equity_rows'] += len(curve)


def main():
    protocol = json.loads((DOC/'protocol.json').read_text(encoding='utf-8'))
    manifest = json.loads((OUT/'run_manifest.json').read_text(encoding='utf-8'))
    results = json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    assert protocol['status'] == 'SPEC_FROZEN' and manifest.get('completed_utc')
    paths = dict(protocol=DOC/'protocol.json', hypothesis=DOC/'hypothesis.md', plan=DOC/'plan.md',
                 data_inventory=DOC/'data_inventory.md', code=ROOT/'scripts/research_ytt_monthly5_fx.py',
                 tests=ROOT/'tests/test_ytt_monthly5_fx.py', results=OUT/'results.json')
    for key, path in paths.items():
        assert sha(path) == manifest[key+'_sha256'], key
    counts['frozen_hashes'] += len(paths)
    reference = protocol['reference_inputs']
    for key in ('core', 'baseline_result', 'baseline_manifest'):
        pathkey = 'core_code' if key == 'core' else key
        assert sha(ROOT/reference[pathkey]) == reference[key+'_sha256'], key
        counts['reference_hashes'] += 1
    old = json.loads((ROOT/reference['baseline_result']).read_text(encoding='utf-8'))
    metadata = {r['symbol']: r for r in json.loads((ROOT/protocol['data_manifest']).read_text(encoding='utf-8'))}
    period_records, accounts, combined_rows = [], [], defaultdict(list)
    start, end = map(seconds, protocol['continuous_account'])
    for symbol in protocol['symbols']:
        info = metadata[symbol]
        path = Path(info['raw_path'])
        frozen_input = next(r for r in manifest['inputs'] if r['symbol'] == symbol)
        assert sha(path) == frozen_input['raw_sha256'] == info['raw_sha256']
        assert sha(path.parent/'info.dat') == info['metadata_sha256']
        cache = ROOT/protocol['cache_directory']/f'{symbol}_features.npz'
        mask = ROOT/protocol['complete_m5_directory']/f'{symbol}_complete_m5.npz'
        assert sha(cache) == frozen_input['cache_sha256'] == info['cache_sha256']
        assert sha(mask) == frozen_input['mask_sha256']
        counts['input_hashes'] += 4
        raw = np.memmap(path, mode='r', dtype='<f8', offset=4, shape=((path.stat().st_size-4)//48, 6))
        first, last = np.searchsorted(raw[:, 0], [43800., 46023.])
        raw = raw[first:last]
        rt = np.rint((raw[:, 0]-25569)*86400).astype(np.int64)
        rp = np.asarray(raw[:, [1, 3, 4, 2]])
        assert np.all(np.diff(rt) > 0) and np.isfinite(rp).all()
        counts['raw_m1_rows'] += len(rt)
        m5t, m5p, m5f, _ = aggregate(rt, rp, 300)
        with np.load(cache, allow_pickle=False) as saved:
            arr(saved['times'], m5t, symbol+'/m5times')
            arr(saved['features'][:, :4], m5p, symbol+'/m5prices')
        with np.load(mask, allow_pickle=False) as saved: arr(saved['complete'], m5f, symbol+'/m5complete')
        z, calendars, entries = prepare(rt, rp, info['tick'])
        with np.load(OUT/f'{symbol}_execution.npz', allow_pickle=False) as saved:
            for key, value in z.items(): arr(saved[key], value, symbol+'/execution/'+key)
        for label, calendar in calendars.items():
            with np.load(OUT/f'{symbol}_{label}.npz', allow_pickle=False) as saved:
                for key, value in calendar.items(): arr(saved[key], value, symbol+'/'+label+'/'+key)
            quality = calendar_quality(m5t, m5f, calendar['times'], 86400 if label == 'D1' else 604800)
            eq(json.loads((OUT/f'{symbol}_{label}_coverage.json').read_text(encoding='utf-8')), quality, symbol+'/quality')
            counts['calendar_rows'] += len(quality)
        for width, entry in entries.items():
            with np.load(OUT/f'{symbol}_entry{width}.npz', allow_pickle=False) as saved:
                for key, value in entry.items(): arr(saved[key], value, f'{symbol}/entry{width}/{key}')
        counts['execution_rows'] += len(z['times'])
        counts['candidate_events'] += int(np.count_nonzero(z['sides']))
        for cutoff in ['2020-02-05T09:30', '2023-01-18T11:00', '2025-11-20T13:30']:
            limit = seconds(cutoff)
            cut = int(np.searchsorted(rt, limit))
            part, _, partial_entries = prepare(rt[:cut], rp[:cut], info['tick'])
            for key, value in part.items():
                reference_value = z[key][:, :len(part['times'])] if key in ('sides', 'stops', 'thresholds') else z[key][:len(value)]
                arr(value, reference_value, f'{symbol}/prefix/{cutoff}/{key}')
            for width, entry in partial_entries.items():
                for key, value in entry.items():
                    full = entries[width][key]
                    arr(value, full[:, :len(entry['times'])] if key in ('sides', 'stops', 'thresholds') else full[:len(value)],
                        f'{symbol}/prefix/{cutoff}/{width}/{key}')
            counts['prefixes'] += 1
        for a, arm in enumerate(ARMS):
            for multiplier in (1, 2):
                cost = (protocol['cost_and_fill_model']['spread_pips'][symbol]+.4)*info['pip']*multiplier
                all_rows = []
                for period, dates in protocol['periods'].items():
                    lo, hi = map(seconds, dates)
                    rows, _, _ = replay(z, a, lo, hi, cost, False)
                    for row in rows: row.update(net_pips=row['net_price']/info['pip'], period=period)
                    record = dict(symbol=symbol, arm=arm, period=period, cost_multiplier=multiplier,
                                  net_pips=sum(r['net_pips'] for r in rows), **stats(rows))
                    expected = next(r for r in results['records'] if all(r[k] == record[k] for k in ('symbol', 'arm', 'period', 'cost_multiplier')))
                    eq(expected, record, 'Rrecord')
                    period_records.append(record)
                    combined_rows[arm, period, multiplier].extend(rows)
                    all_rows.extend(rows)
                name = f'{symbol}_{arm}_cost{multiplier}'
                compare_trades(name, all_rows, monthly(all_rows, start, end))
                if symbol == 'USDJPY':
                    rows, curve, account = replay(z, a, start, end, cost, True)
                    name = 'JPY_'+name
                    mm = monthly(rows, start, end, curve)
                    compare_trades(name, rows, mm, curve)
                    eq(json.loads((OUT/(name+'_execution_summary.json')).read_text(encoding='utf-8')), account, name+'/execution_summary')
                    for period, dates in dict(protocol['periods'], continuous=protocol['continuous_account']).items():
                        window = account_window(rows, mm, curve, account, *map(seconds, dates))
                        if multiplier == 2: diagnostic = dict(net_yen=window['net_yen'] > 0, no_stop=not window['halted_by_period_end'])
                        elif period == 'continuous': diagnostic = {k: normal_gate(window)[k] for k in ('geometric_monthly_5pct', 'no_stop')}
                        else: diagnostic = normal_gate(window)
                        record = dict(arm=arm, period=period, cost_multiplier=multiplier, **window, account_gate_diagnostic=diagnostic)
                        expected = next(r for r in results['continuous_usdjpy_account_windows'] if all(r[k] == record[k] for k in ('arm', 'period', 'cost_multiplier')))
                        eq(expected, record, name+'/'+period)
                        accounts.append(record)
        print('INDEPENDENT_SYMBOL_COMPLETE', symbol, flush=True)
    combined = []
    for (arm, period, multiplier), rows in combined_rows.items():
        rows.sort(key=lambda r: (r['exit_time'], r['entry_time']))
        record = dict(arm=arm, period=period, cost_multiplier=multiplier, **stats(rows))
        expected = next(r for r in results['combined_equal_r_not_yen_portfolio'] if all(r[k] == record[k] for k in ('arm', 'period', 'cost_multiplier')))
        eq(expected, record, 'combined')
        combined.append(record)
    account_lookup = {(r['arm'], r['period'], r['cost_multiplier']): r for r in accounts}
    combined_lookup = {(r['arm'], r['period'], r['cost_multiplier']): r for r in combined}
    gates = []
    for arm in ('dw_m15', 'dw_h1'):
        checks = []
        for period in ('later_descriptive', 'latest_descriptive'):
            normal, stress = account_lookup[arm, period, 1], account_lookup[arm, period, 2]
            qualified = sum(r['pf'] is not None and r['pf'] >= 1.2 and r['mean_net_r'] > 0 and r['trades'] >= 100
                            for r in period_records if r['arm'] == arm and r['period'] == period and r['cost_multiplier'] == 1)
            if arm == 'dw_h1': baseline = combined_lookup['no_htf_h1', period, 1]
            else:
                old_period = 'validation' if period == 'later_descriptive' else period
                baseline = next(r for r in old['combined_trade_statistics_not_portfolio'] if r['arm'] == 'no_htf_baseline' and r['period'] == old_period and r['cost_multiplier'] == 1)
            checks.append(dict(period=period, normal=normal_gate(normal), stress=dict(net_yen=stress['net_yen'] > 0, no_stop=not stress['halted_by_period_end']),
                               qualified_currencies=qualified, currencies_pass=qualified >= 2, baseline_mean_net_r=baseline['mean_net_r'],
                               mean_r_comparison=combined_lookup[arm, period, 1]['mean_net_r'] >= baseline['mean_net_r']))
        continuous = account_lookup[arm, 'continuous', 1]
        whole = {k: normal_gate(continuous)[k] for k in ('no_stop', 'geometric_monthly_5pct')}
        passed = all(whole.values()) and all(all(c['normal'].values()) and all(c['stress'].values()) and c['currencies_pass'] and c['mean_r_comparison'] for c in checks)
        gates.append(dict(arm=arm, all_pass=passed, continuous=whole, periods=checks,
                          every_month_5pct=continuous['every_month_reaches_5_percent'],
                          disposition='NEEDS_EVIDENCE' if passed else 'GATES_FAILED_PENDING_INDEPENDENT_VALIDATION'))
    eq(results['gates'], gates, 'gates')
    for key, path in paths.items(): assert sha(path) == manifest[key+'_sha256'], ('changed_during_audit', key)
    answer = dict(status='ALL_MATCH', code_sha256=manifest['code_sha256'], results_sha256=manifest['results_sha256'],
                  verification_code_sha256=sha(__file__), counts=dict(counts), records=period_records, combined=combined,
                  accounts=accounts, gates=gates, limitations=['Previously viewed data; no pristine holdout',
                  'Source-calendar D/W approximation', 'No swap/variable bid ask replay', 'JPY accounts USDJPY only'])
    output = OUT/'independent_verification.json'
    output.write_text(json.dumps(answer, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print('INDEPENDENT_FINAL_JSON='+str(output), flush=True)
    print(json.dumps(dict(counts), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
