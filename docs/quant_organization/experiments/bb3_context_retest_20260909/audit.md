# BB3 pullback-limit independent audit

## Status

**VERIFIED_REJECTED / 不採用**。全6指値候補が両コストの学習基準不通過。
Protocol and hypothesis were read before retest execution.
The prior `bb3_context_timing_20260909` experiment remains rejected; this new
experiment does not relabel already viewed data as untouched.

## Frozen-spec review

- Six ATR-offset/TTL limit candidates plus baseline, same nine symbols and
  fixed train-only selection. Only the selected candidate and baseline may
  access later periods. No fallback or symbol postselection.
- Original preparation and exclusions must remain. Freeze order price from
  signal close and prior ATR; activate only from the next available bar.
  Director requested before execution: buy limits floor and sell limits ceil
  to the instrument tick, so untradable fractional-tick entry prices are not
  credited as executions. Verify this in the final frozen protocol and code.
- Pending cancellation at the open can use the previous confirmed target.
  A current-close cancellation cannot erase an earlier valid intrabar fill.
  TTL-th bar can fill; cancel an unfilled order only after that bar.
- If open fills, the price can improve to open and a later same-bar target is
  causally possible. If limit fills intrabar and target also touches, suppress
  same-bar profit under the declared target-before-entry convention. Count
  these ambiguous bars. This is not a worst-case result over future paths.
- All fill/exit tests use the target valid before the current close; update
  the target afterward. Preserve no stop, no forced last-bar close, negative
  center exits, cost debit and separate open P/L.
- Cached features may be reused only with matching identifiers and current
  source stat checks. Reuse does not create a fresh or independent holdout.

## Required evidence / handoff

Review exact frozen code and hashes, completed process/final artifacts, then
independently recompute per-trade execution geometry, all summaries and
selection. Test gap/TTL/cancellation/ambiguous-bar cases and prefix causality.
Any positive result still requires execution-risk discussion and TradingView
verification before a runtime claim. No real-money approval is granted.

Only this report is changed by the independent reviewer; implementation and
adoption gates remain owned by the researcher/director.

## Completed evidence and decision

- The researcher completed `python -m scripts.research_bb3_context_retest`,
  exit **0**, `RESULT_JSON` status `REJECTED`, selected `null`. The final
  `results.json`, `execution.json`, frozen protocol, code/input hashes and
  manifest were inspected under `agent_runs/bb3_context_retest_20260909/`.
- Before execution, the director's tick-floor/ceil rule was saved into
  `protocol.json` and the implementation. Following the independent review,
  the cached manifest was included among hashed inputs because it defines
  pip, tick and metadata cost. Hashes and current history-file stat snapshots
  matched. The implementation retains the causal ordering listed above.
- Independent replay command below completed in session **7537**, exit **0**,
  printing `VERIFIED_REJECTED`. It checked **180** saved result artifacts and
  **44,110** trade rows. The baseline rows exactly equal the already audited
  prior experiment's results and diagnostics.
- All **13,066** limit-trade rows were reproduced by a separately implemented
  dictionary-based order/preparation/position state machine, replaying every
  included bar. Trade matrices and all **14** diagnostics matched, including
  entry price, pending cancellations, open/intrabar fills, unclosed positions,
  marked-to-close drawdown and ambiguity counts.
- **108** independently requested prefix truncations preserved exactly the
  corresponding previously closed trades. **1,166** ambiguous entry bars
  followed the specified no-same-bar-profit convention. These counts include
  duplicate cost scenarios and are not independent market observations.
- All net/PF/mean/win/open-P/L summaries, equal-pip aggregates and train-only
  candidate rejection were independently recalculated. Only baseline accessed
  later-period descriptive evaluation; no selected candidate exists.
- A fixed-trade-list 50% increase in metadata round-trip cost leaves every
  limit candidate negative. Least-negative stress score: `limit100_ttl2`,
  **-1,400.595** equal-pip research-score pips. This descriptive stress does
  not change selection gates. The six frozen neighboring parameter settings
  all failed rather than reveal a robust profitable plateau.
- Re-executed `python -m pytest tests/test_bb3_context_timing.py
  tests/test_bb3_context_retest.py -q`: **20 passed**, exit **0**. These include
  next-bar activation, price improvement, same-bar ambiguity, cancellation
  order, TTL final live bar, and buy/sell tick rounding. Not Pine runtime tests.

The final per-pair/per-period results are the `rows` and `summaries` in
`results.json`; `validation.md` provides the human-readable numerical report.
No account-currency P/L is established by sums of pips across quotes. Variable
spread, financing/swap, liquidity/queue priority, partial fills and broker
constraints remain unimplemented. Limit touch alone is an optimistic fill
assumption despite the conservative same-bar target rule.

**Handoff:** reject these six entry changes; do not overwrite the current Pine
with them. Positive closed profitability has not been established, and the
user objective is not completed. No TradingView compilation/runtime evidence
or real-money approval is asserted.

## Independent replay command

From the project root, extract the following Python block with
`exec(source.split('```python\n',1)[1].split('\n```',1)[0])`, where `source`
is this report read with `Path.read_text(encoding='utf-8')`.

```python
from pathlib import Path
import numpy as np, json, math, hashlib
from datetime import datetime
root=Path.cwd();out=root/'agent_runs/bb3_context_retest_20260909'
cache=root/'agent_runs/bb3_context_timing_20260909/completed'
def read(name):return json.loads((out/name).read_text(encoding='utf-8'))
def epoch(s):return int((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds())
def near(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7),(a,b)

def independent_limit(f,t,start,end,pip,cost,fraction,ttl,tick):
    position=order=setup=None;records=[];realized=peak=dd=0.
    nprep=nsignal=namb=ncancel=nopen=nintra=0;last_entry=-1;last_target=np.nan
    for i in np.flatnonzero((t>=start)&(t<end)):
        op,hi,lo,cl,mid,upper,lower=f[i,:7];handled=skip_exit=False
        if order is not None:
            q=order;d=q['side'];target=q['target'];limit=q['limit'];k=0 if d==1 else 1
            at_target=d*(op-target)>=0
            target_touch=(hi>=target if d==1 else lo<=target)
            at_limit=d*(op-limit)<=0
            limit_touch=(lo<=limit if d==1 else hi>=limit)
            if at_target:
                order=None;handled=True;ncancel+=1
            elif limit_touch:
                position={**q,'entry':op if at_limit else limit,'index':i}
                order=None;last_entry=i;skip_exit=not at_limit
                nopen+=int(at_limit);nintra+=int(not at_limit);namb+=int(not at_limit and target_touch)
            elif target_touch:
                order=None;handled=True;ncancel+=1
            else:
                cancel=(i-q['signal']>=ttl or f[i,10+k] or f[i,12+k] or d*(cl-mid)>=0
                        or (hi>=upper if d==1 else lo<=lower) or f[i,14])
                if cancel:order=None;handled=True;ncancel+=1
                else:order['target']=mid;last_target=mid
        if position is not None:
            p=position;d=p['side'];target=p['target']
            touched=hi>=target if d==1 else lo<=target
            if touched and not skip_exit:
                fill=max(op,target) if d==1 else min(op,target)
                net=d*(fill-p['entry'])/pip-cost
                records.append([d,p['prep'],p['signal'],p['index'],i,p['entry'],fill,target,net])
                realized+=net;position=None;handled=True;last_target=np.nan
            else:position['target']=mid;last_target=mid
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
                chosen=d;raw=cl-d*fraction*f[i,7]
                limit=(math.floor(raw/tick) if d==1 else math.ceil(raw/tick))*tick
                order=dict(side=d,prep=prep,signal=i,target=mid,limit=limit)
                last_target=mid;nsignal+=1;setup=None
        if setup is None and not blocked and not chosen and any(touch):
            k=0 if touch[0] else 1
            if not all(touch) and not f[i,10+k] and not f[i,12+k]:setup=(1 if k==0 else -1,i);nprep+=1
    p=position
    diag=np.array([0. if p is None else p['side']*(cl-p['entry'])/pip-cost,dd,
                   0 if p is None else p['side'],np.nan if p is None else p['entry'],cl,
                   0 if order is None else order['side'],nprep,nsignal,last_entry,last_target,
                   namb,ncancel,nopen,nintra])
    return np.asarray(records).reshape((-1,9)),diag

protocol=read('protocol.json');result=read('results.json');manifest=read('data_manifest.json')
for path,digest in read('code_input_hashes.json').items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,('hash',path)
assert manifest==json.loads((cache/'data_manifest.json').read_text(encoding='utf-8'))
assert protocol==json.loads((root/'docs/quant_organization/experiments/bb3_context_retest_20260909/protocol.json').read_text(encoding='utf-8'))
inputs={}
for m in manifest:
    z=np.load(cache/(m['symbol']+'_features.npz'));inputs[m['symbol']]=(z['features'],z['times'],m)
    st=(Path(protocol['history_directory'])/m['symbol']/'Bars.dat').stat()
    assert {'size':st.st_size,'mtime_ns':st.st_mtime_ns}==m['after']
candidates={c['id']:c for c in protocol['search_space']}
total=limit_count=prefix_checks=ambiguous=0;stress={c:[] for c in candidates}
for row in result['rows']:
    f,t,m=inputs[row['symbol']];pip=m['pip'];cost=row['cost_pips'];c=candidates[row['candidate']]
    z=np.load(out/row['artifact']);trades=z['trades'];d=z['diagnostic']
    bounds=protocol['periods'].get(row['period'],['2023-09-08','2026-09-08']);start,end=map(epoch,bounds)
    if row['candidate']=='baseline':
        old=np.load(cache/row['artifact']);np.testing.assert_array_equal(trades,old['trades']);np.testing.assert_array_equal(d,old['diagnostic'])
    else:
        expected,diag=independent_limit(f,t,start,end,pip,cost,c['atr_fraction'],c['ttl'],m['tick'])
        np.testing.assert_allclose(trades,expected,atol=1e-9,rtol=1e-12,equal_nan=True)
        np.testing.assert_allclose(d,diag,atol=1e-8,rtol=1e-12,equal_nan=True)
        limit_count+=len(trades);ambiguous+=int(d[10])
        # Audit a mid-training prefix for each candidate/pair/cost from saved full results.
        from scripts.research_bb3_context_retest import simulate_limit
        edge=np.searchsorted(t,(start+end)//2)
        short,_=simulate_limit(f[:edge],t[:edge],start,int(t[edge]),pip,cost,c['atr_fraction'],c['ttl'],m['tick'])
        np.testing.assert_array_equal(short,trades[trades[:,4]<edge]);prefix_checks+=1
        near(row['ambiguous_entry_bars'],d[10]);near(row['canceled_orders'],d[11])
    values=trades[:,0]*(trades[:,6]-trades[:,5])/pip-cost
    np.testing.assert_allclose(values,trades[:,8],atol=1e-9,rtol=1e-12)
    gp=math.fsum(v for v in values if v>0);gl=-math.fsum(v for v in values if v<0);net=math.fsum(values);wins=sum(v>0 for v in values)
    for key,value in {'trades':len(values),'wins':wins,'gross_profit_pips':gp,'gross_loss_pips':gl,
                      'profit_factor':gp/gl if gl else None,'net_pips':net,'average_pips':net/len(values) if len(values) else None,
                      'win_rate_pct':100*wins/len(values) if len(values) else 0,
                      'open_net_pips':d[0],'net_plus_open_pips':net+d[0],'bar_close_mtm_drawdown_pips':d[1]}.items():near(row[key],value)
    if row['period']=='training' and row['cost_case']=='metadata_spread_plus_0p2':stress[row['candidate']].extend(values-cost*.5)
    total+=len(trades)
    print('CHECKED',row['artifact'],len(trades),flush=True)
for cid,costs in result['summaries'].items():
    for cost,periods in costs.items():
        for period,s in periods.items():
            rows=[v for v in result['rows'] if (v['candidate'],v['cost_case'],v['period'])==(cid,cost,period)];assert len(rows)==9
            for key in ('trades','wins','gross_profit_pips','gross_loss_pips','net_pips','open_net_pips','net_plus_open_pips','ambiguous_entry_bars','canceled_orders'):near(s[key],math.fsum(v[key] for v in rows))
            near(s['profit_factor'],s['gross_profit_pips']/s['gross_loss_pips'] if s['gross_loss_pips'] else None)
            assert s['positive_pairs']==sum(v['net_pips']>0 for v in rows)
eligible=[]
for cid,costs in result['summaries'].items():
    train=[v['training'] for v in costs.values()]
    if cid!='baseline' and all(s['net_pips']>0 and s['net_plus_open_pips']>0 and s['trades']>=40 and s['positive_pairs']>=6 for s in train):eligible.append(cid)
eligible.sort(key=lambda cid:(-min(v['training']['net_pips'] for v in result['summaries'][cid].values()),cid))
selection=read('selection_before_validation.json')
assert selection['eligible_train']==eligible and selection['selected']==(eligible[0] if eligible else None)==result['selected']
assert all(row['candidate'] in ('baseline',result['selected']) for row in result['rows'] if row['period']!='training')
assert result['status']=='REJECTED' and not eligible and result['live_approved'] is False
print({'status':'VERIFIED_REJECTED','artifacts':len(result['rows']),'saved_trade_rows':total,
       'independent_full_state_limit_trade_rows':limit_count,'prefix_checks':prefix_checks,'ambiguous_bars':ambiguous,
       'fixed_trade_1p5_metadata_cost_training_net':{k:round(math.fsum(v),6) for k,v in stress.items()}})
```
