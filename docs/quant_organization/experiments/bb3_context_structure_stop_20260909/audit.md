# BB3 structure-stop independent audit

## Status

**VERIFIED_REJECTED_TRAINING_ONLY / 学習段階で不採用**。All four structural
alternatives failed the frozen training gates; no candidate was selected.
A source-data anomaly was identified before this experiment's outcomes;
later-period evaluation remains prohibited pending a data-quality decision.
New user-directed stop-rule study; earlier rejected
experiments and Pine remain unchanged. The charter was reread. Only this
report is owned/modified by the independent reviewer.

## Pre-outcome issue and resolution

The reviewer raised a gap-fill issue before outcomes: a resting limit can
already fill when the opening gap goes beyond the planned structural stop.
Retroactively canceling that order would not reproduce a resting-order fill.
The director accepted the issue and instructed the researcher to model both
market and limit opening fills beyond the frozen stop as an entry and immediate
stop exit at the same opening price, debiting the full round-trip cost and
recording a separate diagnostic count. A limit already on the wrong side of
the stop when the order is created can be withheld before submission.
Final protocol and implementation agreement was subsequently checked and
confirmed in the completed audit, as recorded below.

## Required independent checks

- Exactly four structural-stop alternatives plus two fixed-SL10/RR1.3 controls;
  same nine pairs, viewed dates, cost models, finite selection and no fallback.
- Structural extrema include preparation through signal, inclusive, and no
  later bar. Buffer is 0.1 or 0.25 times signal prior ATR, frozen at signal.
- Stop price is anchored to that structure, outward tick-rounded, and never
  moved to preserve an attractive risk after the actual fill. Actual risk is
  entry-to-stop; gross RR1.3 target is tick-rounded from that actual risk.
- Opening gaps beyond the stop remain recorded at full cost as described
  above; signal-time invalid limits are counted separately. Check side
  symmetry, gap priority, intrabar-limit SL reachability and TP ambiguity.
- Orders only become live after confirmed signal; preparation and pending
  states, limit TTL, center-opportunity cancellation and no exit-bar reuse
  must retain the frozen prior rules unless expressly amended before results.
- Inspect hashes, source/manifest consistency, final process exit and artifacts;
  independently replay all candidates, reconstruct metrics/open/MTM DD and
  ranking, test prefix invariance, and stress costs on unchanged trade lists.
- Only preselected candidates and controls may access later-period descriptive
  evaluation. Mixed-quote pips are not monetary portfolio returns. Already
  viewed periods are not an untouched holdout or evidence of future profit.

Local checks cannot establish TradingView compile/runtime success. No actual
orders, account connections, existing Pine changes or live-trading approval
are part of this independent audit.

## Pre-outcome source-data anomaly

An independent tick-grid check found **1,140 off-grid OHLC values in 288
five-minute GBPJPY bars**, all on **2026-08-31**. The maximum deviation from
metadata tick size 0.001 was 0.5 tick. The other eight pairs' deviations were
less than 3e-11 tick (floating-point noise). This is not just a harmless
rounding discrepancy: GBPJPY prices on that date are approximately **2.16**,
between neighboring prices approximately **216**.

Direct read-only source inspection confirms the anomaly is in
`C:/ForexTester6/data/History/GBPJPY/Bars.dat`, not created by the feature cache
or five-minute aggregation. Record **9,265,849** (zero-based; byte offset
`4 + 9,265,849 * 48`) directly unpacks as Forex Tester's
`OLE time, open, close, high, low, volume`:

```text
46265.0, 2.16791, 2.16734, 2.16794, 2.16728, 566750000.0
```

OLE time 46265.0 is 2026-08-31 00:00. The one-minute repository reader gives
the same values. The neighboring source rows are:

| Source time | Field | Value |
|---|---|---:|
| 2026-08-31 23:59 | close | 2.16436 |
| 2026-09-01 00:00 | open | 216.435 |

The cached preceding five-minute close before 2026-08-31 was 216.792; the
2026-08-31 opening was 2.16791. Cross-bar open/previous-close ratios are
0.009999953872836635 and 99.99953796965386 at the two boundaries. A source
scale error of **1/100** is therefore plausible, but not authenticated. No
prices were multiplied, deleted, imputed or repaired by this reviewer.

A read-only scan of all nine cached histories found no other cross-bar price
ratio below 0.5 or above 2. This coarse check does not establish full source
integrity or rule out less obvious defects.

The anomaly lies outside training (2023-09-08 to 2024-09-08), so the prior
experiments' all-candidate **training rejection** is not directly invalidated
by this specific date. Their GBPJPY final-year/continuous descriptive results
must not be treated as credible market-performance evidence without repair
and rerun. Hash agreement only proved faithful reuse of an anomalous source,
not correctness of the source prices. The issue and a request to pause later
evaluation were sent to the director and researcher before new outcomes.

Separately, absolute-price outward TP quantization is needed when source
prices can be off the declared tick grid; nearest-integer risk ticks alone
need not guarantee the requested gross RR. The researcher proposed absolute
buy-ceil/sell-floor TP rounding before outcomes, while preserving the exact
fixed10 controls. This arithmetic improvement does **not** cure the source
scale anomaly.

## Final pre-outcome amendment reviewed

The final frozen protocol and implementation use outward **absolute-price**
TP rounding from unrounded actual risk, and debit the full cost for adverse
opening fills beyond the stop. Only known-invalid signal-time limit orders are
withheld. Average risk includes normal bracket trades only; breached fills
remain in trade counts and PF. These resolve the issues above without changing
the pass/fail thresholds.

After the source-data issue, the director explicitly restricted this experiment
to **training only** before any outcomes. No validation, final-year or continuous
run is allowed, including controls. A train-eligible candidate would remain
NEEDS_EVIDENCE, not research-approved, pending source investigation. Absence of
any train-eligible candidate permits a training-stage rejection. No source
prices are repaired or dropped.

## Completed independent evidence

- Research execution completed exit **0**, chunk `4c65d5`, final status
  `REJECTED`, selected `null`. Inspected final results, selection, execution
  record, data-quality report, hashes, manifest and all saved artifacts.
- Independent replay completed in session **48289**, exit **0**, printing
  `VERIFIED_REJECTED_TRAINING_ONLY`: **108** artifacts, **15,112** trade rows.
  All **10,122** structural-stop rows were independently reproduced from every
  included bar using a separate dictionary-based order/preparation/position
  implementation. All 15 trade columns and 24 diagnostics matched. The
  **36** fixed10 control artifacts exactly matched the already audited prior
  experiment's trade and diagnostic arrays.
- **72** mid-training prefix truncations preserved previously closed trades
  exactly. Explicit per-trade checks confirmed preparation-through-signal
  extrema, signal prior ATR, absolute frozen stop, actual risk, tick-grid TP,
  gross RR floor, fixed-target invariance and adverse-gap cost retention.
- Across saved cost scenarios, **66** breached opening fills were recorded as
  immediate same-open cost losses. They were retained in PF and win rate,
  excluded only from the explicitly named normal-bracket average-risk metric.
  **4,204** already-invalid known limit orders were withheld before placement.
  All-result diagnostics also matched **974** ambiguous entry bars, **826**
  dual-touch bars and **8,558** stop exits. Counts include repeated cost cases,
  not independent market observations.
- Separate calculations matched trade costs, net P/L, PF, win rate, mean,
  normal average risk, realized drawdown, bar-close MTM drawdown, open P/L and
  all nine-pair research-score aggregates. Largest-pair DD was correctly
  distinguished from a monetary portfolio DD. Frozen selection reproduced
  `selected=null`; no later-period artifact exists in this experiment.
- Source/code/input hashes and current source stat checks matched. Every
  training OHLC value was on metadata's tick grid within floating tolerance;
  the identified GBPJPY source anomaly is outside this evaluated interval.
  This verifies this particular exclusion from training, not universal data
  correctness.
- With unchanged saved trades and metadata costs increased by 50%, all six
  training scores remain negative: market fixed10 **-4,285.85**, limit fixed10
  **-1,665.70**, market structure0.10 **-4,754.00**, market structure0.25
  **-4,768.05**, limit structure0.10 **-768.35**, limit structure0.25 **-896.90**
  equal-pip research-score pips. Neither neighboring buffer restores the
  frozen criteria; no profitable robust parameter region was established.
- Independent final test run:
  `python -m pytest tests/test_bb3_context_timing.py tests/test_bb3_context_retest.py tests/test_bb3_context_exits.py tests/test_bb3_context_structure_stop.py tests/test_bb3_context_pf_indicator.py -q`
  completed exit **0**, **101 passed**. This includes 16 new structural-stop
  boundary checks and retained prior research/Pine-source contracts, not
  TradingView compilation or runtime confirmation.

## Decision / handoff

Reject the four structural alternatives on the available training evidence.
The highest new structural aggregate PF is approximately **0.590** under the
fixed 1.4-pip case, below the market fixed10 comparator's approximately
**0.779**; neither is profitable. Per-pair/per-case counts, PF, mean, risks,
realized and MTM DD are in `results.json` rows; `validation.md` includes the
six-case comparisons and diagnostics. All training-end open P/L values are
zero, so these losses were not hidden in held positions.

The user goal of a verified positive-P/L replacement remains unachieved.
Preserve Pine and original history. Later-period/full-three-year market claims
require resolution of the documented source anomaly; no raw-price repair,
deletion or re-scaling was performed. Actual liquidity, stop slippage beyond
the fixed allowance, variable spread, swap and broker constraints remain
unmodeled. Do not infer actual-money portfolio returns from mixed-quote pips.
No TradingView runtime or live-trading approval is asserted.

## Reproducible independent replay

Read this report into `source` from the project root and run
`exec(source.split('```python\n',1)[1].split('\n```',1)[0])` in Python.

```python
from pathlib import Path
from datetime import datetime
import numpy as np, math, json, hashlib
root=Path.cwd();out=root/'agent_runs/bb3_context_structure_stop_20260909'
cache=root/'agent_runs/bb3_context_timing_20260909/completed';old=root/'agent_runs/bb3_context_exits_20260909'
read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
def epoch(s):return int((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds())
def near(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7),(a,b)
def target_at(entry,side,risk,tick):
    x=(entry+side*risk*1.3)/tick
    if math.isclose(x,round(x),rel_tol=0,abs_tol=1e-8):x=round(x)
    return (math.ceil(x) if side==1 else math.floor(x))*tick

def independent_structure(f,t,start,end,pip,cost,tick,is_limit,buffer):
    position=order=setup=None;records=[];realized=peak=dd=0.
    nprep=nsignal=namb=ncancel=nopen=nintra=ndual=ninvalid=nbreach=0;last_entry=-1;kind=0
    last_target=last_stop=last_initial=last_atr=last_risk=last_frozen=last_extreme=np.nan
    for i in np.flatnonzero((t>=start)&(t<end)):
        op,hi,lo,cl,mid,upper,lower=f[i,:7];handled=suppress=entered=False
        if order is not None:
            q=order;d=q['side'];target=q['target'];k=0 if d==1 else 1
            if not is_limit:
                position={**q,'entry':op,'index':i};order=None;entered=True;kind=0;nopen+=1
            else:
                limit=q['limit'];at_target=d*(op-target)>=0
                target_touch=(hi>=target if d==1 else lo<=target)
                at_limit=d*(op-limit)<=0;limit_touch=(lo<=limit if d==1 else hi>=limit)
                breach_open=at_limit and d*(op-q['frozen'])<tick*(1-1e-8)
                if breach_open:
                    position={**q,'entry':op,'index':i};order=None;entered=True;kind=1;nopen+=1
                elif at_target:order=None;handled=True;ncancel+=1
                elif limit_touch:
                    position={**q,'entry':op if at_limit else limit,'index':i};order=None;entered=True
                    suppress=not at_limit;kind=1 if at_limit else 2;nopen+=int(at_limit);nintra+=int(not at_limit)
                elif target_touch:order=None;handled=True;ncancel+=1
                else:
                    cancel=(i-q['signal']>=3 or f[i,10+k] or f[i,12+k] or d*(cl-mid)>=0
                            or (hi>=upper if d==1 else lo<=lower) or f[i,14])
                    if cancel:order=None;handled=True;ncancel+=1
                    else:order['target']=mid;last_target=mid
        breach=False
        if entered:
            p=position;d=p['side'];last_entry=i;p['kind']=kind
            p['stop']=p['frozen'];p['risk']=d*(p['entry']-p['stop'])
            last_stop=p['stop'];last_risk=p['risk']
            breach=p['risk']<tick*(1-1e-8)
            p['target']=np.nan if breach else target_at(p['entry'],d,p['risk'],tick)
            p['initial']=p['target'];last_initial=last_target=p['target']
            nbreach+=int(breach)
            namb+=int(not breach and suppress and (hi>=p['target'] if d==1 else lo<=p['target']))
        if position is not None:
            p=position;d=p['side'];target=p['target'];stop=p['stop'];price=None;stopped=False
            if breach:price=p['entry'];stopped=True
            else:
                hit_sl=min(d*(lo-stop),d*(hi-stop))<=0;hit_tp=max(d*(lo-target),d*(hi-target))>=0
                ndual+=int(hit_sl and hit_tp)
                if d*(op-stop)<=0:price=op;stopped=True
                elif not suppress and d*(op-target)>=0:price=op
                elif hit_sl:price=stop;stopped=True
                elif not suppress and hit_tp:price=target
            if price is not None:
                net=d*(price-p['entry'])/pip-cost
                records.append([d,p['prep'],p['signal'],p['index'],i,p['entry'],price,target,net,
                                stop,p['initial'],p['risk'],p['atr'],p['kind'],int(stopped)])
                realized+=net;position=None;handled=True;last_target=last_stop=last_initial=np.nan
        open_net=0. if position is None else position['side']*(cl-position['entry'])/pip-cost
        equity=realized+open_net;peak=max(peak,equity);dd=max(dd,peak-equity)
        ready=(position is None and order is None and not handled and np.isfinite(mid)
               and upper>mid and np.isfinite(f[i,7]) and np.isfinite(f[i,8]))
        if not ready or f[i,14]:setup=None
        if not ready:continue
        touch=[lo<=lower,hi>=upper];blocked=False;chosen=0
        if setup is not None:
            d,prep=setup;k=0 if d==1 else 1
            blocked=bool(f[i,10+k] or f[i,12+k] or i-prep>3 or d*(cl-mid)>=0 or touch[1-k])
            if blocked:setup=None
            elif i>prep and lower<cl<upper:
                chosen=d;last_atr=f[i,7];last_extreme=min(f[prep:i+1,2]) if d==1 else max(f[prep:i+1,1])
                rawstop=last_extreme-d*buffer*last_atr
                last_frozen=(math.floor(rawstop/tick) if d==1 else math.ceil(rawstop/tick))*tick
                rawlimit=cl-d*last_atr;limit=(math.floor(rawlimit/tick) if d==1 else math.ceil(rawlimit/tick))*tick
                order=dict(side=d,prep=prep,signal=i,target=mid,limit=limit,frozen=last_frozen,atr=last_atr)
                last_target=mid;nsignal+=1;setup=None
                if is_limit and d*(limit-last_frozen)<tick*(1-1e-8):order=None;ninvalid+=1
        if setup is None and not blocked and not chosen and any(touch):
            k=0 if touch[0] else 1
            if not all(touch) and not f[i,10+k] and not f[i,12+k]:setup=(1 if k==0 else -1,i);nprep+=1
    p=position
    diag=np.array([0. if p is None else p['side']*(cl-p['entry'])/pip-cost,dd,
                   0 if p is None else p['side'],np.nan if p is None else p['entry'],cl,
                   0 if order is None else order['side'],nprep,nsignal,last_entry,last_target,
                   namb,ncancel,nopen,nintra,ndual,last_stop,last_risk,last_initial,last_atr,kind,
                   ninvalid,nbreach,last_frozen,last_extreme])
    return np.asarray(records).reshape((-1,15)),diag

protocol=read('protocol.json');result=read('results.json');manifest=read('data_manifest.json')
for path,digest in read('code_input_hashes.json').items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,('hash',path)
assert manifest==json.loads((cache/'data_manifest.json').read_text(encoding='utf-8'))
assert protocol==json.loads((root/'docs/quant_organization/experiments/bb3_context_structure_stop_20260909/protocol.json').read_text(encoding='utf-8'))
inputs={};start,end=map(epoch,protocol['periods']['training'])
for m in manifest:
    z=np.load(cache/(m['symbol']+'_features.npz'));f=z['features'];t=z['times'];inputs[m['symbol']]=(f,t,m)
    st=(Path(protocol['history_directory'])/m['symbol']/'Bars.dat').stat()
    assert {'size':st.st_size,'mtime_ns':st.st_mtime_ns}==m['after']
    ticks=f[(t>=start)&(t<end),:4]/m['tick'];assert np.all(abs(ticks-np.rint(ticks))<=1e-6)
candidates={c['id']:c for c in protocol['search_space']}
total=independent_count=prefix_checks=ambiguous=dualtouch=stops=invalid=breached=controls=0
stress={c:[] for c in candidates}
from scripts.research_bb3_context_structure_stop import simulate_structure_stop
for row in result['rows']:
    assert row['period']=='training'
    f,t,m=inputs[row['symbol']];pip=m['pip'];cost=row['cost_pips'];c=candidates[row['candidate']]
    z=np.load(out/row['artifact']);trades=z['trades'];d=z['diagnostic']
    if c['stop']=='fixed10':
        previous=np.load(old/f"{c['entry']}_sl10_rr13__training__{row['symbol']}__{row['cost_case']}.npz")
        np.testing.assert_array_equal(trades,previous['trades']);np.testing.assert_array_equal(d,previous['diagnostic']);controls+=1
    else:
        expected,diag=independent_structure(f,t,start,end,pip,cost,m['tick'],c['entry']=='limit',c['buffer'])
        np.testing.assert_allclose(trades,expected,atol=1e-9,rtol=1e-12,equal_nan=True)
        np.testing.assert_allclose(d,diag,atol=1e-8,rtol=1e-12,equal_nan=True)
        independent_count+=len(trades);invalid+=int(d[20]);breached+=int(d[21])
        edge=np.searchsorted(t,(start+end)//2)
        short,_=simulate_structure_stop(f[:edge],t[:edge],start,int(t[edge]),pip,cost,m['tick'],c['entry']=='limit',c['buffer'])
        np.testing.assert_array_equal(short,trades[trades[:,4]<edge]);prefix_checks+=1
        near(row['invalid_known_limits'],d[20]);near(row['breached_fill_exits'],d[21])
        for tr in trades:
            side,prep,signal=tr[:3];prep,signal=int(prep),int(signal)
            extreme=min(f[prep:signal+1,2]) if side==1 else max(f[prep:signal+1,1])
            raw=extreme-side*c['buffer']*f[signal,7]
            sl=(math.floor(raw/m['tick']) if side==1 else math.ceil(raw/m['tick']))*m['tick']
            near(tr[9],sl);near(tr[12],f[signal,7]);near(tr[11],side*(tr[5]-sl))
            if np.isnan(tr[10]):
                assert tr[3]==tr[4] and tr[5]==tr[6] and tr[14]==1;near(tr[8],-cost)
            else:
                assert tr[7]==tr[10];near(tr[10],target_at(tr[5],side,tr[11],m['tick']))
                reward=side*(tr[10]-tr[5]);assert reward>=1.3*tr[11]-1e-10 and reward-1.3*tr[11]<m['tick']+1e-10
    values=trades[:,0]*(trades[:,6]-trades[:,5])/pip-cost
    np.testing.assert_allclose(values,trades[:,8],atol=1e-9,rtol=1e-12)
    gp=math.fsum(v for v in values if v>0);gl=-math.fsum(v for v in values if v<0);net=math.fsum(values);wins=sum(v>0 for v in values)
    normal=trades[(trades[:,11]>0)&np.isfinite(trades[:,10]),11]/pip
    eq=np.r_[0.,np.cumsum(values)];realdd=float(np.max(np.maximum.accumulate(eq)-eq))
    for key,value in {'trades':len(values),'wins':wins,'gross_profit_pips':gp,'gross_loss_pips':gl,
                      'profit_factor':gp/gl if gl else None,'net_pips':net,'average_pips':net/len(values) if len(values) else None,
                      'win_rate_pct':100*wins/len(values) if len(values) else 0,
                      'open_net_pips':d[0],'net_plus_open_pips':net+d[0],'bar_close_mtm_drawdown_pips':d[1],
                      'average_risk_pips':math.fsum(normal)/len(normal) if len(normal) else None,
                      'risk_trade_count':len(normal),'total_risk_pips':math.fsum(normal),
                      'realized_drawdown_pips':realdd,'stop_exits':trades[:,14].sum(),
                      'ambiguous_entry_bars':d[10],'dual_touch_bars':d[14]}.items():near(row[key],value)
    if row['cost_case']=='metadata_spread_plus_0p2':stress[row['candidate']].extend(values-cost*.5)
    total+=len(trades);ambiguous+=int(d[10]);dualtouch+=int(d[14]);stops+=int(trades[:,14].sum())
    print('CHECKED',row['artifact'],len(trades),flush=True)
for cid,costs in result['summaries'].items():
    for cost,s in costs.items():
        rows=[v for v in result['rows'] if (v['candidate'],v['cost_case'])==(cid,cost)];assert len(rows)==9
        for key in ('trades','wins','gross_profit_pips','gross_loss_pips','net_pips','open_net_pips','net_plus_open_pips','ambiguous_entry_bars','dual_touch_bars','stop_exits','invalid_known_limits','breached_fill_exits'):near(s[key],math.fsum(v[key] for v in rows))
        near(s['profit_factor'],s['gross_profit_pips']/s['gross_loss_pips'] if s['gross_loss_pips'] else None)
        near(s['win_rate_pct'],100*s['wins']/s['trades'] if s['trades'] else None)
        n=sum(v['risk_trade_count'] for v in rows);near(s['average_risk_pips'],math.fsum(v['total_risk_pips'] for v in rows)/n if n else None)
        near(s['largest_pair_mtm_drawdown_pips'],max(v['bar_close_mtm_drawdown_pips'] for v in rows))
        near(s['largest_pair_realized_drawdown_pips'],max(v['realized_drawdown_pips'] for v in rows))
        assert s['positive_pairs']==sum(v['net_pips']>0 for v in rows)
eligible=[]
for cid,costs in result['summaries'].items():
    if candidates[cid]['stop']=='structure' and all(s['net_pips']>0 and s['net_plus_open_pips']>0 and s['trades']>=40 and s['positive_pairs']>=6 for s in costs.values()):eligible.append(cid)
eligible.sort(key=lambda cid:(-min(v['net_pips'] for v in result['summaries'][cid].values()),cid))
selection=read('selection.json')
assert selection['eligible_training']==eligible and selection['selected']==(eligible[0] if eligible else None)==result['selected']
assert result['status']=='REJECTED' and not eligible and result['live_approved'] is False
assert result['scope']=='training_only_due_to_later_data_anomaly' and controls==36
assert len(list(out.glob('*__*.npz')))==len(result['rows'])==108
print({'status':'VERIFIED_REJECTED_TRAINING_ONLY','artifacts':len(result['rows']),'saved_trade_rows':total,
       'independent_full_state_structure_trade_rows':independent_count,'exact_control_artifacts':controls,
       'prefix_checks':prefix_checks,'ambiguous_entry_bars':ambiguous,'dual_touch_bars':dualtouch,'stop_exits':stops,
       'invalid_known_limits':invalid,'breached_fill_exits':breached,
       'fixed_trade_1p5_metadata_cost_training_net':{k:round(math.fsum(v),6) for k,v in stress.items()}})
```
