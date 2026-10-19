"""User-described BB20/3sigma mean-reversion model, not an authenticated WEMOF implementation."""
from datetime import datetime,timedelta
from dataclasses import asdict
from pathlib import Path
import hashlib,json,math
import numpy as np
from forextester_backtest import HistoryRepository

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'agent_runs/bb3_usdjpy_20260908'
START,END=datetime(2023,9,8),datetime(2026,9,8)


def bands(close):
    mid=np.full(len(close),np.nan); std=mid.copy()
    if len(close)>=20:
        windows=np.lib.stride_tricks.sliding_window_view(np.asarray(close,dtype=float),20)
        mid[19:]=windows.mean(axis=1); std[19:]=windows.std(axis=1,ddof=0)
    return mid,mid+3*std,mid-3*std


def simulate(bars,spread,stop_pips=None,slip_pips=.1):
    close=np.array([b.close for b in bars]); mid,upper,lower=bands(close)
    slip=slip_pips*.01; trades=[]; active=None; pending=None
    realized=peak=dd=0.; both=skipped=0
    last=max(i for i,b in enumerate(bars) if b.time<END)
    for i,b in enumerate(bars):
        if not START<=b.time<END: continue
        just_exited=False
        if pending is not None:
            d,signal_i=pending; pending=None
            if b.time-bars[signal_i].time==timedelta(minutes=5):
                entry=b.open+(spread if d==1 else 0)+d*slip
                target=mid[i-1]+(spread if d==-1 else 0)
                if d*(target-entry)>0:
                    active={'direction':d,'entry':entry,'signal_time':bars[signal_i].time.isoformat(),
                            'entry_time':b.time.isoformat(),'mae_pips_upper_bound':0.,
                            'stop':entry-d*stop_pips*.01 if stop_pips is not None else None}
                else: skipped+=1
        if active is not None:
            d=active['direction']; ask=spread if d==-1 else 0
            opening,high,low=b.open+ask,b.high+ask,b.low+ask
            target=mid[i-1]+ask # only the previous confirmed SMA, held constant inside this bar
            stop=active['stop']; price=None; reason=None
            worst=low if d==1 else high
            active['mae_pips_upper_bound']=max(active['mae_pips_upper_bound'],max(0,d*(active['entry']-worst)/.01))
            hit_stop=stop is not None and (low<=stop if d==1 else high>=stop)
            hit_target=high>=target if d==1 else low<=target
            ambiguous=bool(hit_stop and hit_target)
            if stop is not None and d*(opening-stop)<=0: price,reason=opening,'stop_gap'
            elif d*(opening-target)>=0: price,reason=opening,'center_gap'
            elif hit_stop: price,reason=stop,'stop'
            elif hit_target: price,reason=target,'center'
            elif i==last: price,reason=b.close+ask,'period_end'
            if price is not None:
                price-=d*slip
                net=float(d*(price-active['entry'])/.01)
                trades.append({**active,'exit_time':b.time.isoformat(),'exit':price,'net_pips':net,
                               'reason':reason,'ambiguous':ambiguous,'center_order':float(target),
                               'holding_minutes':(b.time-datetime.fromisoformat(active['entry_time'])).total_seconds()/60})
                realized+=net; active=None; just_exited=True
                equity=realized
            else: equity=realized+d*(b.close+ask-d*slip-active['entry'])/.01
        else: equity=realized
        peak=max(peak,equity); dd=max(dd,peak-equity)
        if active is None and not just_exited and i<last and np.isfinite(mid[i]):
            sell=b.high>=upper[i]; buy=b.low<=lower[i]
            if sell and buy: both+=1
            elif sell or buy: pending=(-1 if sell else 1,i)
    return trades,{'bar_close_mtm_drawdown_pips':dd,'both_band_signals_skipped':both,'center_already_passed_entries_skipped':skipped}


def stats(trades):
    values=[t['net_pips'] for t in trades]; n=len(values)
    profit=math.fsum(v for v in values if v>0); loss=-math.fsum(v for v in values if v<0)
    wins=sum(v>0 for v in values); losses=sum(v<0 for v in values)
    equity=peak=dd=0.
    for t in trades:
        equity+=t['net_pips']; peak=max(peak,equity); dd=max(dd,peak-equity)
    return {'trades':n,'wins':wins,'losses':losses,'win_rate_pct':100*wins/n if n else 0,
            'profit_factor':profit/loss if loss else None,'net_pips':math.fsum(values),
            'average_pips':math.fsum(values)/n if n else None,'average_win_pips':profit/wins if wins else None,
            'average_loss_pips':loss/losses if losses else None,'worst_loss_pips':min(values) if n else None,
            'realized_drawdown_pips':dd,'max_mae_pips_upper_bound':max((t['mae_pips_upper_bound'] for t in trades),default=0),
            'average_holding_minutes':sum(t['holding_minutes'] for t in trades)/n if n else None,
            'max_holding_minutes':max((t['holding_minutes'] for t in trades),default=0),
            'forced_period_exits':sum(t['reason']=='period_end' for t in trades),
            'center_exits_at_loss':sum(t['reason'].startswith('center') and t['net_pips']<0 for t in trades)}


def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def main():
    import argparse
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=OUT)
    OUT=parser.parse_args().output
    OUT.mkdir(parents=True,exist_ok=False)
    p={'model':'User-provided BB mean reversion; not verified official WEMOF',
       'symbol':'USDJPY','timeframe':'5m','period':[START.isoformat(),END.isoformat()],
       'bands':'close SMA20 +/- 3 population standard deviations; touch evaluated after bar closes',
       'entry':'next adjacent 5m open; both-band touches skipped; skip if current executable center is not profitable relative to entry',
       'exit':'moving center based on previous completed 5m close; next-bar update, bid chart touch, short pays ask spread; gap executes actual open; SL first for dual touch',
       'stops_pips':[None,5,10],'slippage_pips_each_side':.1,'positions':'one, no averaging, no exit-bar reuse',
       'risk':'No position sizing or margin model. Report pips, close-based MTM drawdown and high/low MAE upper bound; not live risk certification.',
       'limits':'Unspecified original rules made explicit; no swaps, variable spread, tick execution. 3 years previously viewed. Baseline has no stop; final position forcibly closed.',
       'subagents_used':False,'live_approved':False}
    dump('protocol.json',p)
    dump('code_hashes.json',{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in ['scripts/research_bb3_mean_reversion.py','src/forextester_backtest/data.py','src/forextester_backtest/models.py']})
    repo=HistoryRepository(); file=repo.root/'USDJPY/Bars.dat'
    snap=lambda:{'size':file.stat().st_size,'mtime_ns':file.stat().st_mtime_ns}
    before=snap(); dump('source_before.json',before)
    try:
        meta=repo.metadata('USDJPY')
        if meta.commission_per_lot!=0: raise ValueError('nonzero commission unverified')
        print('Loading USDJPY 5m',flush=True)
        bars=list(repo.bars('USDJPY',datetime(2023,8,1),END-timedelta(microseconds=1),'5m'))
        for i,b in enumerate(bars):
            if not all(math.isfinite(v) and v>0 for v in [b.open,b.high,b.low,b.close]) or b.high<max(b.open,b.close) or b.low>min(b.open,b.close): raise ValueError('OHLC')
            if b.time.minute%5 or b.time.second or (i and not timedelta(0)<b.time-bars[i-1].time<=timedelta(days=7)): raise ValueError('ordering/gap')
        if bars[0].time>START or bars[-1].time<END-timedelta(days=7): raise ValueError('period edges')
        dump('data_manifest.json',{'metadata':asdict(meta),'bars':len(bars),'first':bars[0].time.isoformat(),'last':bars[-1].time.isoformat(),
             'price_time_sha256':hashlib.sha256(repr([(b.time,b.open,b.high,b.low,b.close) for b in bars]).encode()).hexdigest()})
        results=[]
        for stop in [None,5,10]:
            label='no_stop' if stop is None else f'stop_{stop}pips'
            trades,diagnostics=simulate(bars,meta.spread_price,stop)
            with (OUT/(label+'_trades.jsonl')).open('w',encoding='utf-8') as f:
                for t in trades: f.write(json.dumps(t,allow_nan=False)+'\n')
            years=[]
            for y in range(2023,2026):
                a,b=datetime(y,9,8).isoformat(),datetime(y+1,9,8).isoformat()
                years.append({'start':a,'end':b,**stats([t for t in trades if a<=t['entry_time']<b])})
            results.append({'case':label,'stop_pips':stop,'summary':stats(trades),'years':years,**diagnostics})
            print(label,json.dumps(stats(trades)),flush=True)
        after=snap(); dump('source_after.json',after)
        if before!=after: raise ValueError('history changed')
        dump('results.json',{'status':'DESCRIPTIVE_COMPLETE','cases':results,'live_approved':False})
        print('RESULT_JSON='+json.dumps({'status':'DESCRIPTIVE_COMPLETE','output':str(OUT)}),flush=True)
    except Exception as e:
        dump('failure.json',{'type':type(e).__name__,'message':str(e)}); raise


if __name__=='__main__': main()
