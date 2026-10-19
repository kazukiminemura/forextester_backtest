# BB3 causal DMA slope-change independent audit

## Status

**VERIFIED_REJECTED / 不採用。** Independent replay, accounting and selection
checks completed. Neither filter establishes the requested win-rate
improvement. Charter and current board were reread. This
reviewer owns only this new report; existing Pine, source data, prior BB
studies and the unrelated daily DiNapoli study are outside edit scope.

## Pre-outcome requirements (initial review)

- Freeze exactly three cases: unchanged min3 baseline, favorable signed DMA
  second difference, and non-adverse signed DMA slope OR favorable second
  difference. DMA is `SMA(close,3)[3]`, using only past closes.
- Preserve expression evaluation as `(dma[i] - dma[i-1]) - (dma[i-1] - dma[i-2])`,
  then multiply by trade direction and test strictly greater than zero.
  The broader rule accepts signed first difference greater than or equal
  to zero OR that strict second-difference condition. Do not introduce a
  new numerical epsilon or silently rewrite the floating-point operations.
- A positive signed second difference includes favorable acceleration as
  well as deceleration of adverse slope. It is not strictly a test of
  adverse-motion deceleration alone. Near-zero values may be sensitive to
  floating-point summation differences between platforms; flag that limitation.
- Apply the gate at the first otherwise eligible BB-return min3 candidate.
  Failure cancels setup and prevents same-bar rearming. Do not add waiting,
  entry delays, alternative exits, SL or threshold changes. Preserve original
  preparation index, next-available-open fill and previous-center exit order.
- Keep nine pairs, both costs and the common prefix strictly before
  2026-08-31; do not repair the known subsequent GBPJPY source anomaly.
  Preserve viewed-period disclosure and equal-pip research-score semantics.
- Segment1 alone selects at most one rule under the unchanged finite-stat,
  win-rate/PF/mean, 25% retention/minimum count and 6/9 pair gates. Ranking is
  frozen before outcomes. Only baseline and that selected rule access later
  periods, with no fallback. Profitability additionally requires both closed
  net and net-plus-open positive, separate from win-rate improvement.

## Required evidence (initial review)

Read frozen hypothesis/protocol and full source; check exact arithmetic and
zero/equality boundaries, causal DMA, setup reset, gaps and cost accounting.
Reproduce every saved trade and diagnostic with a separate state machine,
independently reconstruct selection, and verify code/input hashes, baseline
and prefix invariants, PF/expectancy/DD/open and cost sensitivity. Confirm
process completion and final artifacts before changing the audit status.

The frozen hypothesis and protocol were read in full before outcomes. The
reviewer flagged a discrepancy between two algebraically equivalent floating
expressions in the delegated instructions. Before execution, the director
confirmed **difference of first differences** as the sole canonical order,
consistent with the research specification. The report above was corrected
before outcomes; no epsilon, candidate or parameter was added. This avoids
silently mixing two rounding-sensitive interpretations of the zero boundary.

## Completed evidence

- Research command `python -m scripts.research_bb3_context_dinapoli_deceleration`
  completed exit **0**, chunk **1acae7**. Final result, execution record,
  pre-later selection, frozen protocol and all **108** artifacts were inspected.
- Separate report-owned dictionary-state replay completed in session **15737**,
  exit **0**, chunk **64fd32**, printing **VERIFIED_REJECTED**. All **20,770**
  saved trade rows and **12** diagnostics matched, including original setup,
  actual signal, next-open fill, moving target, cancellations, open P/L and
  bar-close marked drawdown. Counts include duplicate cost scenarios and
  overlapping evaluation periods, not independent observations.
- All **108** prefix checks preserved closed trades; all **72** baseline
  cases exactly matched min3 center behavior. Separate DMA arithmetic matched
  every stored DMA hash and recomputed short prefixes. Both cost cases have
  identical execution geometry. The scenarios retain **24** gap entries and
  **7,346** negative-net center exits rather than treating all target exits
  as wins. Cost is subtracted once; terminal open marks are separate from PF.
- Verified every input/code/Pine/protocol hash, raw history size/mtime and
  nine used-prefix hashes. All participating timestamps precede 2026-08-31,
  prices pass the metadata tick-grid check, and no used open/previous-close
  ratio is outside 0.5–2. The known original GBPJPY anomaly after the cutoff
  is excluded, not repaired. Complete vendor-data authenticity is unproven.
- Independently recomputed pair/period count, net PF, win rate, expectancy,
  realized DD, bar-close MTM DD, open marks and all aggregate fields. Rebuilt
  training checks/deltas and confirmed an empty eligible list and null
  selection. Pre-later selection contains only segment1; later artifacts
  contain baseline alone. No threshold relaxation or fallback was used.
- Independent tests `python -m pytest tests/test_bb3_context_dinapoli_deceleration.py
  tests/test_bb3_context_dinapoli_wait.py tests/test_bb3_context_dinapoli.py
  tests/test_bb3_context_pf_indicator.py -q` completed exit **0**, **98 passed**.
  These cover strict/inclusive zero, missing DMA, one-ULP positive movement,
  canonical arithmetic order, unchanged entry timing, cancellation, min3
  precedence and prefix behavior. They are not TradingView runtime tests.

## Verified result and failure reason

Learning period: 2023-09-08 inclusive to 2024-09-08 exclusive, nine pairs.
Values are equal-pip research scores, **not account-currency returns**.

| Rule | Trades | Fixed-cost win rate | Fixed-cost PF | Mean net pips | Fixed-cost net pips | Metadata-cost win rate | Metadata-cost PF |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current min3 baseline | 1,146 | 61.52% | 0.576 | -1.566 | -1,794.250 | 60.30% | 0.543 |
| Favorable slope change | 420 | 60.95% | 0.667 | -1.079 | -453.335 | 60.24% | 0.626 |
| Nonadverse slope OR favorable change | 505 | 60.79% | 0.612 | -1.331 | -672.135 | 60.20% | 0.575 |

Both retain more than 25% of baseline and exceed 30 trades. PF and average
return improve but remain unprofitable; win rate is lower under both costs.
The first rule improves only **5/9** pair win rates; the second improves
**4/9** at fixed cost and **3/9** at metadata cost. Six are required. Thus
both fail the frozen improvement gates and neither receives later evaluation.
No claim of later-period acceleration-filter performance is justified.

On unchanged trades, a 50% metadata-cost increase produces learning net
**-843.635 / -1,139.935 pips** for the two filters. This descriptive stress
does not alter selection. No epsilon or parameter sweep was run; comparing
two logical gates is not evidence of a stable parameter plateau.

Baseline reference remains fixed-cost PF **0.576 / 0.879 / 0.774** across
independent segments; continuous **4,730** trades have PF **0.767**, net
**-3,862.875**. Metadata continuous PF is **0.717**, net **-4,769.275**.
All evaluated endpoint open marks are zero without forced liquidation.
Full pair/period PF, expectancy and individual drawdowns remain in
`agent_runs/bb3_context_dinapoli_deceleration_20260910/results.json` and the
research `validation.md`. Largest-pair DD is not portfolio DD.

## Numerical limitation and handoff

On the **1,146 learning baseline signals only**, tick-integer arithmetic
gives exactly zero second difference for **31** signals. Canonical floating
arithmetic classifies **6** as tiny positive, **9** as tiny negative and
**16** as zero. The independent diagnostic was reproduced in the final
replay. The alternative algebraic order disagreed on zero **boolean** tests
in **0** of these baseline samples, which does not prove universal platform
equivalence. No rule was changed using this diagnostic. Future Pine numeric
parity remains unverified, especially around zero.

All dates were previously viewed, not true holdout. No SL, variable spread,
swap, liquidity, margin or account-currency sizing was added. The definition
includes favorable acceleration, not solely adverse-motion deceleration, and
is not authenticated original DiNapoli methodology. Only this report was
modified by the reviewer. Final judgment: **不採用**; do not adopt these
filters into Pine or claim live approval. Preserve this finite failed study.

## Independent replay command

From the project root, execute this report's Python fenced block. It contains
a separate dictionary-state replay and arithmetic; the research simulator
is called only for supplementary prefix tests. Final numeric diagnostics are
limited to learning-period baseline signals and do not redefine the rule.

```python
from pathlib import Path
from datetime import datetime
import numpy as np, math, json, hashlib
root=Path.cwd(); out=root/'agent_runs/bb3_context_dinapoli_deceleration_20260910'; cache=root/'agent_runs/bb3_context_timing_20260909/completed'
read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
def epoch(s):return int((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds())
def near(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7),(a,b)
def own_dma(c):
    d=np.full(len(c),np.nan)
    d[5:]=(c[:-5]+c[1:-4]+c[2:-3])/3
    return d
def allows(f,dma,i,side,mode):
    if mode==0:return True
    if i<2 or not all(np.isfinite(dma[j]) for j in (i,i-1,i-2)):return False
    velocity=dma[i]-dma[i-1]
    previous_velocity=dma[i-1]-dma[i-2]
    favorable_change=side*(velocity-previous_velocity)>0
    return favorable_change if mode==1 else side*velocity>=0 or favorable_change
def replay(f,t,dma,start,end,pip,cost,mode):
    setup=queued=position=None;records=[];realized=peak=dd=0.;preps=signals=reject=dreject=0;lastentry=-1
    for i in np.flatnonzero((t>=start)&(t<end)):
        op,hi,lo,cl,mid,upper,lower=f[i,:7];exited=False
        if queued is not None:
            side,prepi,signali,target=queued;queued=None;lastentry=i
            position=dict(side=side,prep=prepi,signal=signali,index=i,entry=op,target=target)
        if position is not None:
            p=position;side=p['side'];target=p['target']
            if (hi>=target if side==1 else lo<=target):
                fill=max(op,target) if side==1 else min(op,target);net=side*(fill-p['entry'])/pip-cost
                records.append([side,p['prep'],p['signal'],p['index'],i,p['entry'],fill,target,net]);realized+=net
                position=None;exited=True
            else:position['target']=mid
        openp=0. if position is None else position['side']*(cl-position['entry'])/pip-cost
        equity=realized+openp;peak=max(peak,equity);dd=max(dd,peak-equity)
        ready=(position is None and queued is None and not exited and np.isfinite(mid) and upper>mid and np.isfinite(f[i,7]) and np.isfinite(f[i,8]))
        if not ready or f[i,14]:setup=None
        if not ready:continue
        touch=[lo<=lower,hi>=upper];blocked=False;chosen=0
        if setup is not None:
            side,pidx=setup;k=0 if side==1 else 1
            blocked=bool(f[i,10+k] or f[i,12+k] or i-pidx>3 or side*(cl-mid)>=0 or touch[1-k])
            if blocked:setup=None
            elif i>pidx and lower<cl<upper:
                if side*(mid-cl)/pip+1e-9<3:
                    reject+=1;blocked=True;setup=None
                elif not allows(f,dma,i,side,mode):
                    dreject+=1;blocked=True;setup=None
                else:chosen=side;queued=(side,pidx,i,mid);signals+=1;setup=None
        if setup is None and not blocked and not chosen and any(touch):
            k=0 if touch[0] else 1
            if not all(touch) and not f[i,10+k] and not f[i,12+k]:setup=(1 if k==0 else -1,i);preps+=1
    p=position
    diag=np.array([0. if p is None else p['side']*(cl-p['entry'])/pip-cost,dd,
        0 if p is None else p['side'],np.nan if p is None else p['entry'],cl,
        0 if queued is None else queued[0],preps,signals,lastentry,
        p['target'] if p else queued[3] if queued else np.nan,reject,dreject])
    return np.asarray(records).reshape((-1,9)),diag

protocol=read('protocol.json');result=read('results.json');manifest=read('data_manifest.json');selection=read('selection_before_later_periods.json')
cutoff=epoch('2026-08-31');used={m['symbol']:m for m in read('used_prefix_manifest.json')}
for path,digest in read('code_input_hashes.json').items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,('hash',path)
assert manifest==json.loads((cache/'data_manifest.json').read_text(encoding='utf-8'))
assert protocol==json.loads((root/'docs/quant_organization/experiments/bb3_context_dinapoli_deceleration_20260910/protocol.json').read_text(encoding='utf-8'))
inputs={}
for m in manifest:
    z=np.load(cache/(m['symbol']+'_features.npz'));edge=np.searchsorted(z['times'],cutoff)
    f=z['features'][:edge].copy();t=z['times'][:edge].copy();dma=own_dma(f[:,3]);inputs[m['symbol']]=(f,t,dma,m)
    u=used[m['symbol']];assert len(t)==u['bars'] and t[-1]==u['last_timestamp']<cutoff and u['all_before_cutoff']
    assert hashlib.sha256(t.tobytes()+f.tobytes()).hexdigest()==u['used_prefix_sha256']
    assert hashlib.sha256(dma.tobytes()).hexdigest()==u['dma_sha256']
    tickvals=f[:,:4]/m['tick'];assert np.all(abs(tickvals-np.rint(tickvals))<1e-6)
    ratios=f[1:,0]/f[:-1,3];assert np.all((ratios>.5)&(ratios<2))
    st=(Path(protocol['history_directory'])/m['symbol']/'Bars.dat').stat();assert {'size':st.st_size,'mtime_ns':st.st_mtime_ns}==m['after']
from scripts.research_bb3_context_dinapoli_deceleration import simulate_dma
from scripts.research_bb3_context_center5 import simulate_center
modes={c['id']:c['dma_mode'] for c in protocol['search_space']};assert modes=={'baseline':0,'deceleration':1,'no_adverse_acceleration':2}
total=prefixchecks=basechecks=gaps=losses=0;stress={};geometry={}
for row in result['rows']:
    f,t,dma,m=inputs[row['symbol']];pip=m['pip'];cost=row['cost_pips'];mode=modes[row['candidate']]
    expectedcost=1.4 if row['cost_case']=='fixed_1p4' else float(m['metadata']['values']['spread'])*m['tick']/pip+.2
    near(cost,expectedcost);start,end=map(epoch,protocol['periods'][row['period']]);assert end<=cutoff
    z=np.load(out/row['artifact']);tr=z['trades'];d=z['diagnostic'];expected,diag=replay(f,t,dma,start,end,pip,cost,mode)
    np.testing.assert_allclose(tr,expected,atol=1e-9,rtol=1e-12,equal_nan=True);np.testing.assert_allclose(d,diag,atol=1e-8,rtol=1e-12,equal_nan=True)
    edge=np.searchsorted(t,(start+end)//2);shortdma=own_dma(f[:edge,3]);np.testing.assert_array_equal(shortdma,dma[:edge])
    short,_=simulate_dma(f[:edge],t[:edge],shortdma,start,int(t[edge]),pip,cost,mode)
    np.testing.assert_array_equal(short,tr[tr[:,4]<edge]);prefixchecks+=1
    if mode==0:
        baseline,bdiag=simulate_center(f,t,start,end,pip,cost,3.)
        np.testing.assert_array_equal(tr,baseline);np.testing.assert_array_equal(d[:11],bdiag);basechecks+=1
    if len(tr):
        si=tr[:,2].astype(int);en=tr[:,3].astype(int);ex=tr[:,4].astype(int)
        assert np.all(en==si+1) and np.all(t[ex]<end)
        assert np.all(tr[:,0]*(f[si,4]-f[si,3])/pip+1e-9>=3)
        assert all(allows(f,dma,i,side,mode) for i,side in zip(si,tr[:,0]))
        np.testing.assert_array_equal(tr[:,5],f[en,0]);np.testing.assert_array_equal(tr[:,7],f[ex-1,4])
        gaps+=int(np.sum(t[en]-t[si]>300));losses+=int(np.sum(tr[:,8]<0))
    v=tr[:,0]*(tr[:,6]-tr[:,5])/pip-cost;np.testing.assert_allclose(v,tr[:,8],atol=1e-9,rtol=1e-12)
    gp=math.fsum(x for x in v if x>0);gl=-math.fsum(x for x in v if x<0);net=math.fsum(v);wins=sum(x>0 for x in v)
    eq=np.r_[0.,np.cumsum(v)];rdd=float(np.max(np.maximum.accumulate(eq)-eq))
    for key,value in {'trades':len(v),'wins':wins,'gross_profit_pips':gp,'gross_loss_pips':gl,'profit_factor':gp/gl if gl else None,
        'net_pips':net,'average_pips':net/len(v) if len(v) else None,'win_rate_pct':100*wins/len(v) if len(v) else None,
        'open_net_pips':d[0],'net_plus_open_pips':net+d[0],'bar_close_mtm_drawdown_pips':d[1],
        'realized_drawdown_pips':rdd,'distance_rejections':d[10],'dma_rejections':d[11]}.items():near(row[key],value)
    if row['cost_case']=='metadata_spread_plus_0p2':stress.setdefault((row['candidate'],row['period']),[]).extend(v-cost*.5)
    geometry[(row['candidate'],row['period'],row['symbol'],row['cost_case'])]=tr
    total+=len(tr);print('CHECKED',row['artifact'],len(tr),flush=True)
for cid,costs in result['summaries'].items():
    for cost,periods in costs.items():
        for period,s in periods.items():
            rows=[v for v in result['rows'] if (v['candidate'],v['cost_case'],v['period'])==(cid,cost,period)];assert len(rows)==9
            for key in ('trades','wins','gross_profit_pips','gross_loss_pips','net_pips','open_net_pips','net_plus_open_pips','distance_rejections','dma_rejections'):near(s[key],math.fsum(v[key] for v in rows))
            near(s['profit_factor'],s['gross_profit_pips']/s['gross_loss_pips'] if s['gross_loss_pips'] else None)
            near(s['win_rate_pct'],100*s['wins']/s['trades'] if s['trades'] else None);near(s['average_pips'],s['net_pips']/s['trades'] if s['trades'] else None)
            near(s['largest_pair_mtm_drawdown_pips'],max(v['bar_close_mtm_drawdown_pips'] for v in rows))
            near(s['largest_pair_realized_drawdown_pips'],max(v['realized_drawdown_pips'] for v in rows));assert s['positive_pairs']==sum(v['net_pips']>0 for v in rows)
            assert selection['training_summaries'][cid][cost]['segment1']==result['summaries'][cid][cost]['segment1']
            assert set(selection['training_summaries'][cid][cost])=={'segment1'}
for (cid,period,symbol,cost),a in geometry.items():
    if cost=='fixed_1p4':np.testing.assert_array_equal(a[:,:8],geometry[(cid,period,symbol,'metadata_spread_plus_0p2')][:,:8])
eligible=[]
for cid in list(modes)[1:]:
    checks={};deltas={}
    for cost in result['summaries'][cid]:
        c=result['summaries'][cid][cost]['segment1'];b=result['summaries']['baseline'][cost]['segment1'];prefix=cost+'.segment1.'
        finite=all(c[k] is not None and b[k] is not None for k in ('win_rate_pct','profit_factor','average_pips'))
        bp={r['symbol']:r for r in result['rows'] if (r['candidate'],r['period'],r['cost_case'])==('baseline','segment1',cost)}
        cp=[r for r in result['rows'] if (r['candidate'],r['period'],r['cost_case'])==(cid,'segment1',cost)]
        n=sum(r['trades']>0 and bp[r['symbol']]['trades']>0 and r['win_rate_pct']>bp[r['symbol']]['win_rate_pct']+1e-12 for r in cp)
        metrics={'finite_statistics':finite,'winrate_up':finite and c['win_rate_pct']-b['win_rate_pct']>1e-12,
            'pf_not_lower':finite and c['profit_factor']-b['profit_factor']>=-1e-12,
            'average_not_lower':finite and c['average_pips']-b['average_pips']>=-1e-9,
            'minimum_count':c['trades']>=30,'sample_retained':c['trades']>=.25*b['trades'],'six_pairs_winrate_up':n>=6}
        checks.update({prefix+k:v for k,v in metrics.items()})
        if finite:deltas[cost]={'winrate_pp':c['win_rate_pct']-b['win_rate_pct'],'pf':c['profit_factor']-b['profit_factor'],'average_pips':c['average_pips']-b['average_pips'],'improved_pairs':n}
    assert checks==result['training_checks'][cid]==selection['training_checks'][cid]
    assert deltas==result['training_deltas'][cid]==selection['training_deltas'][cid]
    if all(checks.values()):eligible.append(cid)
eligible.sort(key=lambda c:(-min(d['winrate_pp'] for d in result['training_deltas'][c].values()),-min(d['pf'] for d in result['training_deltas'][c].values()),c))
assert eligible==selection['eligible']==[] and result['selected'] is selection['selected'] is None
assert all(r['candidate']=='baseline' or r['period']=='segment1' for r in result['rows'])
assert result['status']=='NO_VERIFIED_IMPROVEMENT' and not result['improvement_passed'] and not result['profit_requirement_met'] and not result['live_approved']
assert result['later_checks']==result['later_deltas']==result['profit_checks']=={}
assert result['baseline_cases_exactly_reproduced']==basechecks==72
assert len(list(out.glob('*__*.npz')))==len(result['rows'])==108
print({'status':'VERIFIED_REJECTED','artifacts':108,'full_state_trade_rows':total,'prefix_checks':prefixchecks,
    'baseline_checks':basechecks,'gap_entries':gaps,'negative_net_center_exits':losses,
    'fixed_trade_1p5_metadata_cost_net':{k[0]+'.'+k[1]:round(math.fsum(v),6) for k,v in stress.items()}})
n=positive=negative=alternate=0
for symbol,(f,t,dma,m) in inputs.items():
    tr=np.load(out/('baseline__segment1__'+symbol+'__fixed_1p4.npz'))['trades']
    i=tr[:,2].astype(int);side=tr[:,0];q=np.rint(f[:,3]/m['tick']).astype(np.int64)
    canonical=side*((dma[i]-dma[i-1])-(dma[i-1]-dma[i-2]))
    alternative=side*((dma[i]-2*dma[i-1])+dma[i-2])
    exact=side*(q[i-3]-q[i-6]-q[i-4]+q[i-7]);zero=exact==0
    n+=int(np.sum(zero));positive+=int(np.sum(zero&(canonical>0)));negative+=int(np.sum(zero&(canonical<0)))
    alternate+=int(np.sum((canonical>0)!=(alternative>0)))
print({'baseline_segment1_exact_tick_acceleration_zero':n,'float_positive':positive,'float_negative':negative,
       'different_algebraic_order_boolean_disagreements':alternate})

```
