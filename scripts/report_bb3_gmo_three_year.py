"""User-requested fixed calendar-2023-2025 descriptive BB/GMO report."""
from datetime import datetime, timedelta
import hashlib
import json

import numpy as np

from forextester_backtest import HistoryRepository
from scripts.research_bb3_candle_shapes import simulate_shapes, summarize, source_stat
from scripts.research_bb3_context_center5 import simulate_center
from scripts.research_bb3_context_timing import ROOT, EPOCH, features, timestamp, dump, aggregate

OUT = ROOT / 'agent_runs/bb3_gmo_2023_2025'
COST = dict(USDJPY=.2, EURUSD=.3, GBPUSD=.6, AUDUSD=.4, NZDUSD=1.6, AUDJPY=.5, NZDJPY=.6)


def totals(values):
    gp, gl = values[values > 0].sum(), -values[values < 0].sum()
    return dict(trades=len(values), wins=int((values > 0).sum()),
                win_rate_pct=100 * float((values > 0).mean()) if len(values) else None,
                profit_factor=float(gp / gl) if gl else None, net_pips=float(values.sum()))


def main():
    OUT.mkdir(exist_ok=False)
    protocol = dict(start='2023-01-01', end_exclusive='2026-01-01', warmup='2022-12-01',
        symbols=list(COST), cost_pips=COST, timeframe='5m', modes=[0,1,2,3,4],
        scope='Descriptive all five frozen modes, no selection or retuning; user requested previously unrun dates.',
        annual='Continuous positions across years; annual closed trades grouped by exit bar year.',
        cost_scope='Current GMO FXneo normal-session spreads applied to ALL hours, not historical actual spread; unknown source timezone.',
        cost_source='https://www.click-sec.com/corp/guide/fxneo/commission_list/',
        source_checked='2026-09-19', source_advertised='2026-09-15',
        stop=False, swap=False, min_center_pips=3, forced_end_exit=False, stress_extra_pips=.2)
    dump(OUT/'protocol.json',protocol)
    repo=HistoryRepository()
    rows=[]; manifests=[]; annual=[]; parity=0
    for symbol, cost in COST.items():
        print('Loading',symbol,flush=True)
        raw=repo.root/symbol/'Bars.dat'; before=source_stat(raw)
        bars=list(repo.bars(symbol,datetime(2022,12,1),datetime(2026,1,1)-timedelta(microseconds=1),'5m'))
        times=np.array([int((b.time-EPOCH).total_seconds()) for b in bars],dtype=np.int64)
        ohlc=np.array([(b.open,b.high,b.low,b.close) for b in bars])
        assert times[0]<timestamp('2023-01-01') and times[-1]>=timestamp('2025-12-30')
        assert np.all(np.diff(times)>0) and np.all(np.isfinite(ohlc)) and np.all(ohlc>0)
        assert np.all(ohlc[:,1]>=np.maximum(ohlc[:,0],ohlc[:,3])) and np.all(ohlc[:,2]<=np.minimum(ohlc[:,0],ohlc[:,3]))
        assert before==source_stat(raw)
        pip=.01 if symbol.endswith('JPY') else .0001
        f=features(ohlc,times,pip,10.**-repo.metadata(symbol).decimals)
        np.savez_compressed(OUT/f'{symbol}_features.npz',features=f,times=times)
        manifests.append(dict(symbol=symbol,raw_path=str(raw),stat=before,first=bars[0].time.isoformat(),last=bars[-1].time.isoformat(),bars=len(bars),input_sha256=hashlib.sha256(times.tobytes()+f.tobytes()).hexdigest()))
        for mode in range(5):
            t,d=simulate_shapes(f,times,timestamp('2023-01-01'),timestamp('2026-01-01'),pip,cost,mode)
            if mode==0:
                old,od=simulate_center(f,times,timestamp('2023-01-01'),timestamp('2026-01-01'),pip,cost,3.)
                np.testing.assert_array_equal(t,old); np.testing.assert_array_equal(d[:11],od); parity+=1
            name=f'{symbol}_c{mode}.npz'
            np.savez_compressed(OUT/name,trades=t,diagnostic=d)
            rows.append(dict(symbol=symbol,mode=mode,cost=cost,artifact=name,**summarize(t,d,times),stress=totals(t[:,8]-.2)))
            for year in (2023,2024,2025):
                exits=times[t[:,4].astype(int)]
                values=t[(exits>=timestamp(f'{year}-01-01')) & (exits<timestamp(f'{year+1}-01-01')),8]
                annual.append(dict(symbol=symbol,mode=mode,year=year,**totals(values)))
        print('COMPLETE',symbol,flush=True)
    summary=[]
    for mode in range(5):
        group=[r for r in rows if r['mode']==mode]; total=aggregate(group)
        total['win_rate_pct']=100*total['wins']/total['trades'] if total['trades'] else None
        stress=np.concatenate([np.load(OUT/r['artifact'])['trades'][:,8]-.2 for r in group])
        summary.append(dict(mode=mode,**total,stress=totals(stress)))
    dump(OUT/'data_manifest.json',manifests)
    dump(OUT/'results.json',dict(summary=summary,rows=rows,annual=annual,baseline_exact_cases=parity))
    paths=[ROOT/'scripts/report_bb3_gmo_three_year.py',ROOT/'scripts/research_bb3_candle_shapes.py',ROOT/'scripts/research_bb3_context_center5.py',ROOT/'scripts/research_bb3_context_timing.py']
    dump(OUT/'code_hashes.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    print('RESULT_JSON='+str(OUT/'results.json'),flush=True)


if __name__=='__main__':
    main()
