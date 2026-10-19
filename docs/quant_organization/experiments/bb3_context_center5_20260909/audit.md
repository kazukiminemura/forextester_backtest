# BB3 minimum-center-distance descriptive audit

## Status

**Independent accounting status: VERIFIED_DESCRIPTIVE / 独立記述照合完了**。
Research adoption judgment: **未検証** (this is a fixed performance check,
not candidate selection/adoption approval). Measured min5 closed P/L is
negative across all nine continuous-window pairs in both cost models.
Read the current Pine in full and reread the charter.
This is a fixed descriptive comparison of minimum center distance **0** versus
**5 pips**, not threshold optimization or a new selection procedure. Only this
report is owned/modified by the independent reviewer; Pine remains read-only.

## Current-Pine reproduction requirements

- The current Pine defaults to 5-pip minimum signed distance from the confirmed
  candidate close to that same bar's SMA20, before costs. It tests only after
  the existing preparation cancellation checks and band-return confirmation.
- If distance + **1e-9 pips** is below the threshold, **cancel** preparation and
  do not rearm on the same bar. This differs from the older timing experiment's
  distance gate, which kept waiting; it must not be reused unchanged.
- A sufficient-distance signal queues next-available-open entry, including
  gaps. Entry-price distance is not retrospectively filtered. Default stop
  remains disabled. Current bar exits use the previous confirmed center;
  update to the current SMA only if the trade survives the bar.
- Preserve wick and four independent impulse histories, preparation expiry,
  gap reset, no exit-bar reuse, one fixed-size position, full cost at close,
  and separately marked open P/L. Do not force the last trade into PF.
- All nine pairs share the cutoff **2026-08-31 exclusive**, before the known
  GBPJPY source-price anomaly, without changing, repairing or deleting raw
  history. Compare continuous history and three independent sections; the
  final section ends eight calendar days earlier than earlier experiments.
- Both 0/5 configurations are fixed before outcomes and evaluated descriptively
  on already viewed dates. No claim of untouched holdout, learned selection,
  universally profitable settings or monetary portfolio returns is justified.

## Required evidence

Frozen protocol/code/Pine/input hashes, original-source stat checks, inspected
cutoff data quality, final process completion, all saved trade/diagnostic
outputs, independent state replay, threshold boundary examples, prefix
causality, per-pair/per-section net PF/mean/DD/open and increased-cost checks.
Local parity checks do not establish TradingView compilation or runtime.

## Completed evidence

- The runner completed `python -m scripts.research_bb3_context_center5`, exit
  **0**, chunk `76cb6b`, final status `DESCRIPTIVE_COMPLETE`. Final results,
  execution record, source/input hashes, original manifest and per-symbol
  used-prefix manifest were inspected. Neither optimization nor live approval
  is recorded in the result.
- Independent report-owned replay completed in session **69430**, exit **0**,
  printing `VERIFIED_DESCRIPTIVE`. All **144** artifacts and **42,828** trade
  rows were replayed from every included bar with a separate dictionary-state
  implementation. All nine trade columns and eleven diagnostics matched,
  including distance cancellations, open P/L and bar-close MTM drawdown.
- **144** mid-period prefix checks preserved all previously closed trades;
  **72** min0 baseline checks exactly matched the original simulator. Both
  cost models have identical execution geometry per condition/pair/period;
  costs change only accounting in this comparison.
- **52** gap-crossing entries and **19,014** negative-net center exits remain
  represented in the saved scenarios. Counts include duplicate costs and
  overlapping continuous/segment periods, not independent observations.
- Independently confirmed source/Pine/protocol/cache hashes and current raw
  source size/mtime, reconstructed all used-prefix hashes, and checked every
  participating timestamp is before 2026-08-31. All used OHLC values are on
  metadata's tick grid within tolerance; no used open/previous-close ratio is
  below 0.5 or above 2. This excludes the **known** anomaly from this comparison
  without claiming full vendor-data authentication or repairing the source.
- All per-pair and per-period PF, net, win rate, expectancy, realized DD,
  bar-close MTM DD, open marks, distance rejections and aggregates matched
  separate arithmetic. Largest individual-pair DD is not a portfolio DD.
- Independent tests:
  `python -m pytest tests/test_bb3_context_center5.py tests/test_bb3_context_pf_indicator.py -q`
  completed exit **0**, **62 passed**. These include cancellation versus waiting,
  no same-bar rearming, a fresh subsequent preparation, the 1e-9-pip threshold
  boundary, next-open/gap execution, dynamic target order and unclosed P/L.
  They are not Pine compiler or TradingView runtime tests.

## Verified result / handoff

Continuous period: 2023-09-08 inclusive to 2026-08-31 exclusive. Values are
equal-pip research-score totals, **not** monetary account returns.

| Setting and cost | Trades | Win rate | Net PF | Closed net pips | Open pips |
|---|---:|---:|---:|---:|---:|
| min0, fixed 1.4 | 7,710 | 53.26% | 0.645 | -7,338.870 | -3.300 |
| min5, fixed 1.4 | 2,997 | 65.17% | 0.826 | -2,253.755 | 0.000 |
| min0, metadata + 0.2 | 7,710 | 50.80% | 0.592 | -8,682.770 | -3.600 |
| min5, metadata + 0.2 | 2,997 | 64.43% | 0.782 | -2,865.655 | 0.000 |

Min5 fixed-cost expectancy is **-0.7520 pips/trade**; metadata-cost expectancy
is **-0.9562 pips/trade**. Higher win rate and PF than min0 do not establish
profitability. Every min5 continuous pair is negative in both cost models.
All three min5 segment aggregates are also negative; their fixed-cost PFs
are approximately **0.618 / 0.932 / 0.837**. Min5 has zero open P/L at each
reported endpoint without forced liquidation. Min0's final/continuous open
loss remains included separately, not hidden in the PF calculation.

On unchanged saved trades, increasing metadata costs by 50% leaves min5
continuous P/L at **-5,269.505** equal-pip-score pips, and the three min5
segments at **-1,818.385 / -1,689.730 / -1,761.390**. This is descriptive cost
stress, not a new threshold-selection exercise. Only user-fixed 0 and 5 were
compared; no parameter plateau or optimized profitable threshold is claimed.

Full per-pair/per-period counts, PF, expectancy, DD and open marks are in
`agent_runs/bb3_context_center5_20260909/results.json`; `validation.md` provides
the readable pair tables. The current Pine source was not changed by this
reviewer. Its 5-pip rule has **not** achieved positive P/L in the evaluated
history. Five pips measures signal-close room, not guaranteed entry-to-exit
profit. No SL, variable spreads, swap, broker constraints or account-currency
portfolio sizing is introduced here, and no live/TradingView result is asserted.

The source GBPJPY anomaly still exists after the common cutoff. Results from
this earlier prefix do not validate the anomalous day or any later chart.

## Independent replay command

From the project root, read this report into `source` and execute
`exec(source.split('```python\n',1)[1].split('\n```',1)[0])` in Python.

```python
from pathlib import Path
from datetime import datetime
import numpy as np,math,json,hashlib
root=Path.cwd();out=root/'agent_runs/bb3_context_center5_20260909';cache=root/'agent_runs/bb3_context_timing_20260909/completed'
read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
def epoch(s):return int((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds())
def near(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7),(a,b)

def independent_center(f,t,start,end,pip,cost,minimum):
    setup=queued=position=None;records=[];realized=peak=dd=0.;preps=signals=rejections=0;last_entry=-1
    for i in np.flatnonzero((t>=start)&(t<end)):
        op,hi,lo,cl,mid,upper,lower=f[i,:7];exited=False
        if queued is not None:
            side,prepi,signali,target=queued;queued=None;last_entry=i
            position=dict(side=side,prep=prepi,signal=signali,index=i,entry=op,target=target)
        if position is not None:
            p=position;d=p['side'];target=p['target']
            if (hi>=target if d==1 else lo<=target):
                fill=max(op,target) if d==1 else min(op,target);net=d*(fill-p['entry'])/pip-cost
                records.append([d,p['prep'],p['signal'],p['index'],i,p['entry'],fill,target,net]);realized+=net
                position=None;exited=True
            else:position['target']=mid
        openp=0. if position is None else position['side']*(cl-position['entry'])/pip-cost
        equity=realized+openp;peak=max(peak,equity);dd=max(dd,peak-equity)
        ready=(position is None and queued is None and not exited and np.isfinite(mid)
               and upper>mid and np.isfinite(f[i,7]) and np.isfinite(f[i,8]))
        if not ready or f[i,14]:setup=None
        if not ready:continue
        touch=[lo<=lower,hi>=upper];blocked=False;chosen=0
        if setup is not None:
            d,pidx=setup;k=0 if d==1 else 1
            blocked=bool(f[i,10+k] or f[i,12+k] or i-pidx>3 or d*(cl-mid)>=0 or touch[1-k])
            if blocked:setup=None
            elif i>pidx and lower<cl<upper:
                if d*(mid-cl)/pip+1e-9<minimum:
                    rejections+=1;blocked=True;setup=None
                else:chosen=d;queued=(d,pidx,i,mid);signals+=1;setup=None
        if setup is None and not blocked and not chosen and any(touch):
            k=0 if touch[0] else 1
            if not all(touch) and not f[i,10+k] and not f[i,12+k]:setup=(1 if k==0 else -1,i);preps+=1
    p=position
    diag=np.array([0. if p is None else p['side']*(cl-p['entry'])/pip-cost,dd,
                   0 if p is None else p['side'],np.nan if p is None else p['entry'],cl,
                   0 if queued is None else queued[0],preps,signals,last_entry,
                   p['target'] if p else queued[3] if queued else np.nan,rejections])
    return np.asarray(records).reshape((-1,9)),diag

protocol=read('protocol.json');result=read('results.json');manifest=read('data_manifest.json');used=read('used_prefix_manifest.json')
cutoff=epoch('2026-08-31');prefix_manifest={m['symbol']:m for m in used}
for path,digest in read('code_input_hashes.json').items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,('hash',path)
assert manifest==json.loads((cache/'data_manifest.json').read_text(encoding='utf-8'))
assert protocol==json.loads((root/'docs/quant_organization/experiments/bb3_context_center5_20260909/protocol.json').read_text(encoding='utf-8'))
inputs={}
for m in manifest:
    z=np.load(cache/(m['symbol']+'_features.npz'));edge=np.searchsorted(z['times'],cutoff)
    f=z['features'][:edge].copy();t=z['times'][:edge].copy();inputs[m['symbol']]=(f,t,m)
    expected=prefix_manifest[m['symbol']]
    assert len(t)==expected['bars'] and t[0]==expected['first_timestamp'] and t[-1]==expected['last_timestamp']<cutoff
    assert expected['all_used_before_anomaly'] is True
    assert hashlib.sha256(t.tobytes()+f.tobytes()).hexdigest()==expected['used_prefix_sha256']
    tickvals=f[:,:4]/m['tick'];assert np.all(abs(tickvals-np.rint(tickvals))<1e-6)
    ratios=f[1:,0]/f[:-1,3];assert np.all((ratios>.5)&(ratios<2))
    st=(Path(protocol['history_directory'])/m['symbol']/'Bars.dat').stat()
    assert {'size':st.st_size,'mtime_ns':st.st_mtime_ns}==m['after']
total=prefix_checks=baseline_checks=gap_entries=loss_exits=0
stress={};costcase_matrices={}
from scripts.research_bb3_context_center5 import simulate_center
from scripts.research_bb3_context_timing import simulate
minimums={c['id']:c['min_center_pips'] for c in protocol['search_space']}
assert minimums=={'min0':0.,'min5':5.}
for row in result['rows']:
    f,t,m=inputs[row['symbol']];pip=m['pip'];cost=row['cost_pips'];minimum=minimums[row['candidate']]
    start,end=map(epoch,protocol['periods'][row['period']]);assert end<=cutoff
    z=np.load(out/row['artifact']);trades=z['trades'];d=z['diagnostic']
    expected,diag=independent_center(f,t,start,end,pip,cost,minimum)
    np.testing.assert_allclose(trades,expected,atol=1e-9,rtol=1e-12,equal_nan=True)
    np.testing.assert_allclose(d,diag,atol=1e-8,rtol=1e-12,equal_nan=True)
    edge=np.searchsorted(t,(start+end)//2)
    short,_=simulate_center(f[:edge],t[:edge],start,int(t[edge]),pip,cost,minimum)
    np.testing.assert_array_equal(short,trades[trades[:,4]<edge]);prefix_checks+=1
    if minimum==0:
        baseline,bdiag=simulate(f,t,start,end,pip,cost)
        np.testing.assert_array_equal(trades,baseline);np.testing.assert_array_equal(d[:10],bdiag);baseline_checks+=1
    if len(trades):
        signal=trades[:,2].astype(int);enter=trades[:,3].astype(int);exits=trades[:,4].astype(int)
        assert np.all(enter==signal+1) and np.all(t[exits]<end)
        assert np.all(trades[:,0]*(f[signal,4]-f[signal,3])/pip+1e-9>=minimum)
        np.testing.assert_array_equal(trades[:,5],f[enter,0])
        np.testing.assert_array_equal(trades[:,7],f[exits-1,4])
        gap_entries+=int(np.sum(t[enter]-t[signal]>300));loss_exits+=int(np.sum(trades[:,8]<0))
    values=trades[:,0]*(trades[:,6]-trades[:,5])/pip-cost
    np.testing.assert_allclose(values,trades[:,8],atol=1e-9,rtol=1e-12)
    gp=math.fsum(v for v in values if v>0);gl=-math.fsum(v for v in values if v<0);net=math.fsum(values);wins=sum(v>0 for v in values)
    eq=np.r_[0.,np.cumsum(values)];rdd=float(np.max(np.maximum.accumulate(eq)-eq))
    for key,value in {'trades':len(values),'wins':wins,'gross_profit_pips':gp,'gross_loss_pips':gl,
                      'profit_factor':gp/gl if gl else None,'net_pips':net,'average_pips':net/len(values) if len(values) else None,
                      'win_rate_pct':100*wins/len(values) if len(values) else 0,
                      'open_net_pips':d[0],'net_plus_open_pips':net+d[0],'bar_close_mtm_drawdown_pips':d[1],
                      'realized_drawdown_pips':rdd,'distance_rejections':d[10]}.items():near(row[key],value)
    if row['cost_case']=='metadata_spread_plus_0p2':stress.setdefault((row['candidate'],row['period']),[]).extend(values-cost*.5)
    costcase_matrices[(row['candidate'],row['period'],row['symbol'],row['cost_case'])]=trades
    total+=len(trades);print('CHECKED',row['artifact'],len(trades),flush=True)
for cid,costs in result['summaries'].items():
    for cost,periods in costs.items():
        for period,s in periods.items():
            rows=[v for v in result['rows'] if (v['candidate'],v['cost_case'],v['period'])==(cid,cost,period)];assert len(rows)==9
            for key in ('trades','wins','gross_profit_pips','gross_loss_pips','net_pips','open_net_pips','net_plus_open_pips','distance_rejections'):near(s[key],math.fsum(v[key] for v in rows))
            near(s['profit_factor'],s['gross_profit_pips']/s['gross_loss_pips'] if s['gross_loss_pips'] else None)
            near(s['win_rate_pct'],100*s['wins']/s['trades'] if s['trades'] else None)
            near(s['average_pips'],s['net_pips']/s['trades'] if s['trades'] else None)
            near(s['largest_pair_mtm_drawdown_pips'],max(v['bar_close_mtm_drawdown_pips'] for v in rows))
            near(s['largest_pair_realized_drawdown_pips'],max(v['realized_drawdown_pips'] for v in rows))
            assert s['positive_pairs']==sum(v['net_pips']>0 for v in rows)
for cid in minimums:
    for period in protocol['periods']:
        for symbol in inputs:
            a=costcase_matrices[(cid,period,symbol,'fixed_1p4')];b=costcase_matrices[(cid,period,symbol,'metadata_spread_plus_0p2')]
            np.testing.assert_array_equal(a[:,:8],b[:,:8])
assert result['status']=='DESCRIPTIVE_COMPLETE' and result['optimization_performed'] is False and result['live_approved'] is False
assert result['baseline_cases_exactly_reproduced']==baseline_checks==72
assert len(list(out.glob('*__*.npz')))==len(result['rows'])==144
print({'status':'VERIFIED_DESCRIPTIVE','artifacts':144,'full_state_reproduced_trade_rows':total,
       'prefix_checks':prefix_checks,'baseline_exact_checks':baseline_checks,'gap_entries':gap_entries,'loss_center_exits':loss_exits,
       'fixed_trade_1p5_metadata_cost_net':{k[0]+'.'+k[1]:round(math.fsum(v),6) for k,v in stress.items()},
       'min5_continuous_summary':result['summaries']['min5']})
```
