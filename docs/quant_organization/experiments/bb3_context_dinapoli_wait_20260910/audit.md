# BB3 causal DMA waiting-state independent audit

## Status

**VERIFIED_REJECTED / 不採用。** Independent state, accounting and selection
verification completed successfully; neither waiting rule improves win rate
under the frozen criteria. The charter and board were reread. The reviewer
owns only this report; strategy, gates, Pine, source history and prior studies
are read-only. This experiment is a new finite state-machine hypothesis, not
a retrospective replacement of the rejected immediate-DMA filters.

## Pre-outcome requirements (initial review)

- Freeze baseline and DMA waiting TTL 3/6 bars. Keep minCenter3, original
  preparation filters/expiry, no SL, next-open entry, moving-center full exit,
  one position and both existing round-trip cost models.
- First eligible BB-return candidate has age zero for DMA waiting. If the
  close already lies on the favorable side of SMA3[3], queue next-open entry;
  otherwise enter an unfilled waiting state. No order exists merely because
  waiting began. Preserve the original preparation index separately.
- During waiting, TTL replaces the original preparation expiry; TTL edge is
  inclusive and expiry is age greater than TTL. Actual signal index is the
  later qualifying confirmed bar, never the original candidate timestamp.
- Waiting cancels on gap, direction-specific explained impulse/long wick,
  opposite-band touch, center passed, distance below 3 pips using the existing
  1e-9-pip tolerance, or TTL expiry. Cancellation prohibits same-bar rearming.
  Merely being outside the original band is not by itself cancellation, but
  never authorizes entry; favorable DMA, strictly inside BB and min3 must all
  hold on the eventual signal bar.
- DMA uses only closes t-5, t-4 and t-3. Confirmed close controls entry queued
  for next available open. Gap fills retain queued orders; current-bar center
  must not replace the active prior-confirmed target before checking exit.
- All nine pairs share the prefix before 2026-08-31. Original GBPJPY source
  anomaly remains unmodified after the cutoff. Previously viewed dates are
  not true holdout. Equal-pip totals are research scores, not money.
- Freeze segment1-only selection, both-cost sample/retention/6-pair and
  win-rate/PF/mean gates and ranking before results. Only baseline plus at
  most one eligible candidate may access later periods, with no fallback.
  Improvement and positive closed/net-plus-open P/L remain separate tests.

## Required completion evidence (initial review)

Frozen hypothesis, protocol, code/input identifiers, final exit and files;
independent delayed-DMA and separate waiting-state replay of every saved case;
all order/trade/diagnostic and PF/expectancy/DD/open accounting; prefix checks,
baseline parity, cost robustness, cancellation/TTL/gap boundaries; independent
selection reconstruction. No Pine adoption or live approval without evidence.

Protocol and hypothesis were inspected in full before outcomes. Research and
reviewer agreed on the inclusive waiting deadline, frozen origin, preserved
preparation index, and waiting-gap cancellation semantics. No specification
defect was identified at this stage. The two TTL values are the entire new
candidate budget, not permission for a wider search after rejection.

## Completed audit and decision

- Research run `python -m scripts.research_bb3_context_dinapoli_wait` completed
  exit **0**, chunk **cae67e**. Final results, execution record, protocol,
  serialized pre-later selection and all **108** case artifacts were inspected.
- Independent report-owned replay completed session **61955**, exit **0**,
  chunk **103eac**, printing **VERIFIED_REJECTED**. All **19,868** saved trade
  rows and **24** diagnostics match the separate dictionary-state replay below,
  including all waiting starts, delayed signals, overlapping cancellation
  reasons, final waiting direction/origin, original preparation and actual
  signal indices. Waiting-start conservation also held in every case.
- All **108** prefix tests preserved closed trades; all **72** baseline cases
  exactly reproduced the min3 center simulator. Independent DMA arithmetic
  reproduced all nine stored hashes; recomputed short DMA prefixes matched.
  Both cost cases use identical fills and timing. The recorded scenarios
  retain **24** gap-crossing entries and **7,026** negative-net center exits,
  including duplicated cost cases and overlapping periods.
- Source/code/Pine/protocol/cache hashes, raw history size/mtime and all used
  prefix hashes matched. Every participating timestamp is before 2026-08-31;
  OHLC grid and extreme open/previous-close ratio checks pass in this prefix.
  No original source was repaired and the known GBPJPY anomaly after the
  cutoff remains. No claim of complete vendor-data authentication is made.
- All pair/period PF, win rate, net expectancy, realized DD, bar-close MTM DD,
  open marks and aggregates were separately recomputed. Training gate values,
  deltas and the empty eligible list were independently reconstructed. Only
  baseline appears in later periods; the saved selection snapshot contains
  segment1 only. No candidate substitution or post-outcome criterion change.
- Independent command `python -m pytest tests/test_bb3_context_dinapoli_wait.py
  tests/test_bb3_context_dinapoli.py tests/test_bb3_context_pf_indicator.py -q`
  completed exit **0**, **83 passed**. Covered inclusive TTL in both directions,
  expiry before confirmation, gap/impulse/wick/distance cancellation, no
  same-bar rearm, band-outside waiting, origin preservation and terminal waits.
  Local tests are not TradingView compilation or runtime confirmation.

### Verified learning-period result

2023-09-08 inclusive to 2024-09-08 exclusive, nine pairs, minCenter3 and
moving-center exit without SL. Pips below are equal-pip research scores,
**not monetary portfolio returns**.

| Rule | Trades | Fixed-cost win rate | Fixed-cost PF | Mean net pips | Fixed-cost net pips | Metadata-cost win rate | Metadata-cost PF |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current baseline | 1,146 | 61.52% | 0.576 | -1.566 | -1,794.250 | 60.30% | 0.543 |
| Wait at most 3 bars | 173 | 57.80% | 0.411 | -2.264 | -391.745 | 55.49% | 0.382 |
| Wait at most 6 bars | 301 | 57.48% | 0.493 | -1.593 | -479.425 | 56.15% | 0.458 |

Both waiting rules reduce win rate, PF and net expectancy in both cost cases.
Wait3 retains only **15.10%**, below 25%; wait6 retains **26.27%** but fails
the quality gates. Improved pair counts are **4/9** and **3/9**, below six.
Smaller total losses arise with fewer trades and are not improved expectancy.
Neither rule is selected; its later-period behavior is therefore untested.

Wait3 begins **1,144** waits: **159** delayed signals plus **985** cancellations.
Wait6 begins **1,143**: **287** delayed plus **856** canceled. Both also have
14 immediate trades and no final active wait. The same-side retouch does not
extend the deadline. Distance cancellation counts **495 / 541** and TTL
counts **370 / 118** are overlapping reason counts, not disjoint populations.
Observed distance cancellations do not prove a relaxed-distance variant works.

Raising metadata costs by 50% on unchanged saved trades makes learning net
**-554.095 / -755.525 pips** for wait3/wait6. This is descriptive stress, not
a new selection gate. Comparing only TTL 3 and 6 does not establish a robust
parameter plateau. No further tuning is authorized by this failed experiment.

Baseline remains negative in every aggregate segment: fixed-cost PF
**0.576 / 0.879 / 0.774**; continuous **4,730** trades, PF **0.767**, net
**-3,862.875**. Metadata continuous PF **0.717**, net **-4,769.275**.
All evaluated terminal open marks are zero without forced liquidation.
Full pair/period statistics and individual-pair drawdowns are retained in
`agent_runs/bb3_context_dinapoli_wait_20260910/results.json`; the research
`validation.md` summarizes both waiting states and baseline references.

### Limits and handoff

All dates were previously viewed, not untouched holdout. Aggregate pips and
largest single-pair DD are not account-currency profit or portfolio DD. The
modeled one fixed-unit position has no SL; moving-center exits can create
losses, and long holding/swaps remain a risk. Variable spreads, liquidity,
margin, broker restrictions, swaps and costs beyond the two prescribed models
are not implemented. This study tests these bounded DMA states, not the full
DiNapoli methodology. Existing Pine and prior research were not changed by
the reviewer. Final judgment is **不採用**, no Pine adoption and no live
approval; deliver the failed finite experiment without relaxing its gates.

## Independent replay command

From the project root, read this report and execute its Python fenced block.
The dictionary-state replay and arithmetic below are separate from research
implementation; the research simulator is called only for prefix tests.

```python
from pathlib import Path
from datetime import datetime
import numpy as np, math, json, hashlib
root=Path.cwd(); out=root/'agent_runs/bb3_context_dinapoli_wait_20260910'; cache=root/'agent_runs/bb3_context_timing_20260909/completed'
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
    if not np.isfinite(dma[i]) or side*(f[i,3]-dma[i])<=0:return False
    if mode==1:return True
    if i<1 or not np.isfinite(dma[i-1]):return False
    if mode==2:return side*(f[i-1,3]-dma[i-1])<=0
    return side*(dma[i]-dma[i-1])>0
def replay(f,t,dma,start,end,pip,cost,mode):
    setup=queued=position=waiting=None;records=[];realized=peak=dd=0.
    preps=signals=reject=starts=delayed=cancels=0;lastentry=origin=-1;reasons=np.zeros(8)
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
        touch=[lo<=lower,hi>=upper];blocked=False;chosen=0
        if waiting is not None:
            side,pidx,first=waiting;k=0 if side==1 else 1
            causes=[not ready,bool(f[i,14]),bool(f[i,10+k]),bool(f[i,12+k]),
                    side*(cl-mid)>=0,touch[1-k],side*(mid-cl)/pip+1e-9<3,i-first>mode]
            if any(causes):
                blocked=True;waiting=None;cancels+=1;reject+=int(causes[6]);reasons+=np.array(causes,dtype=int)
            elif lower<cl<upper and allows(f,dma,i,side,1):
                chosen=side;queued=(side,pidx,i,mid);signals+=1;delayed+=1;waiting=None
        else:
            if not ready or f[i,14]:setup=None
            if ready and setup is not None:
                side,pidx=setup;k=0 if side==1 else 1
                blocked=bool(f[i,10+k] or f[i,12+k] or i-pidx>3 or side*(cl-mid)>=0 or touch[1-k])
                if blocked:setup=None
                elif i>pidx and lower<cl<upper:
                    if side*(mid-cl)/pip+1e-9<3:
                        reject+=1;blocked=True;setup=None
                    elif mode==0 or allows(f,dma,i,side,1):
                        chosen=side;queued=(side,pidx,i,mid);signals+=1;setup=None
                    else:
                        origin=i;waiting=(side,pidx,i);setup=None;starts+=1
        if ready and setup is None and waiting is None and not blocked and not chosen and any(touch):
            k=0 if touch[0] else 1
            if not all(touch) and not f[i,10+k] and not f[i,12+k]:setup=(1 if k==0 else -1,i);preps+=1
    p=position
    diag=np.r_[np.array([0. if p is None else p['side']*(cl-p['entry'])/pip-cost,dd,
        0 if p is None else p['side'],np.nan if p is None else p['entry'],cl,
        0 if queued is None else queued[0],preps,signals,lastentry,
        p['target'] if p else queued[3] if queued else np.nan,reject,
        starts,delayed,cancels,waiting[0] if waiting else 0,origin]),reasons]
    assert starts==delayed+cancels+int(waiting is not None)
    return np.asarray(records).reshape((-1,9)),diag

protocol=read('protocol.json');result=read('results.json');manifest=read('data_manifest.json');selection=read('selection_before_later_periods.json')
cutoff=epoch('2026-08-31');used={m['symbol']:m for m in read('used_prefix_manifest.json')}
for path,digest in read('code_input_hashes.json').items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,('hash',path)
assert manifest==json.loads((cache/'data_manifest.json').read_text(encoding='utf-8'))
assert protocol==json.loads((root/'docs/quant_organization/experiments/bb3_context_dinapoli_wait_20260910/protocol.json').read_text(encoding='utf-8'))
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
from scripts.research_bb3_context_dinapoli_wait import simulate_wait
from scripts.research_bb3_context_center5 import simulate_center
modes={c['id']:c['wait_bars'] for c in protocol['search_space']};assert modes=={'baseline':0,'wait3':3,'wait6':6}
waitkeys=('wait_starts','delayed_signals','wait_cancellations','final_waiting_side','final_wait_origin','cancel_not_ready','cancel_gap','cancel_explained','cancel_wick','cancel_center','cancel_opposite','cancel_distance','cancel_ttl')
total=prefixchecks=basechecks=gaps=losses=0;stress={};geometry={}
for row in result['rows']:
    f,t,dma,m=inputs[row['symbol']];pip=m['pip'];cost=row['cost_pips'];mode=modes[row['candidate']]
    expectedcost=1.4 if row['cost_case']=='fixed_1p4' else float(m['metadata']['values']['spread'])*m['tick']/pip+.2
    near(cost,expectedcost);start,end=map(epoch,protocol['periods'][row['period']]);assert end<=cutoff
    z=np.load(out/row['artifact']);tr=z['trades'];d=z['diagnostic'];expected,diag=replay(f,t,dma,start,end,pip,cost,mode)
    np.testing.assert_allclose(tr,expected,atol=1e-9,rtol=1e-12,equal_nan=True);np.testing.assert_allclose(d,diag,atol=1e-8,rtol=1e-12,equal_nan=True)
    edge=np.searchsorted(t,(start+end)//2);shortdma=own_dma(f[:edge,3]);np.testing.assert_array_equal(shortdma,dma[:edge])
    short,_=simulate_wait(f[:edge],t[:edge],shortdma,start,int(t[edge]),pip,cost,mode)
    np.testing.assert_array_equal(short,tr[tr[:,4]<edge]);prefixchecks+=1
    if mode==0:
        baseline,bdiag=simulate_center(f,t,start,end,pip,cost,3.)
        np.testing.assert_array_equal(tr,baseline);np.testing.assert_array_equal(d[:11],bdiag);basechecks+=1
    if len(tr):
        si=tr[:,2].astype(int);en=tr[:,3].astype(int);ex=tr[:,4].astype(int)
        assert np.all(en==si+1) and np.all(t[ex]<end)
        assert np.all(tr[:,0]*(f[si,4]-f[si,3])/pip+1e-9>=3)
        assert mode==0 or all(allows(f,dma,i,side,1) for i,side in zip(si,tr[:,0]))
        np.testing.assert_array_equal(tr[:,5],f[en,0]);np.testing.assert_array_equal(tr[:,7],f[ex-1,4])
        gaps+=int(np.sum(t[en]-t[si]>300));losses+=int(np.sum(tr[:,8]<0))
    v=tr[:,0]*(tr[:,6]-tr[:,5])/pip-cost;np.testing.assert_allclose(v,tr[:,8],atol=1e-9,rtol=1e-12)
    gp=math.fsum(x for x in v if x>0);gl=-math.fsum(x for x in v if x<0);net=math.fsum(v);wins=sum(x>0 for x in v)
    eq=np.r_[0.,np.cumsum(v)];rdd=float(np.max(np.maximum.accumulate(eq)-eq))
    for key,value in {'trades':len(v),'wins':wins,'gross_profit_pips':gp,'gross_loss_pips':gl,'profit_factor':gp/gl if gl else None,
        'net_pips':net,'average_pips':net/len(v) if len(v) else None,'win_rate_pct':100*wins/len(v) if len(v) else None,
        'open_net_pips':d[0],'net_plus_open_pips':net+d[0],'bar_close_mtm_drawdown_pips':d[1],
        'realized_drawdown_pips':rdd,'distance_rejections':d[10],**dict(zip(waitkeys,d[11:]))}.items():near(row[key],value)
    if row['cost_case']=='metadata_spread_plus_0p2':stress.setdefault((row['candidate'],row['period']),[]).extend(v-cost*.5)
    geometry[(row['candidate'],row['period'],row['symbol'],row['cost_case'])]=tr
    total+=len(tr);print('CHECKED',row['artifact'],len(tr),flush=True)
for cid,costs in result['summaries'].items():
    for cost,periods in costs.items():
        for period,s in periods.items():
            rows=[v for v in result['rows'] if (v['candidate'],v['cost_case'],v['period'])==(cid,cost,period)];assert len(rows)==9
            for key in ('trades','wins','gross_profit_pips','gross_loss_pips','net_pips','open_net_pips','net_plus_open_pips','distance_rejections')+waitkeys[:3]+waitkeys[5:]:near(s[key],math.fsum(v[key] for v in rows))
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
```
