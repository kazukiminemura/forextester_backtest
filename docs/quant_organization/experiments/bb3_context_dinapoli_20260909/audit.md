# BB3 causal 3x3 DMA independent audit

## Status

**VERIFIED_REJECTED / 不採用。** Independent replay and selection checks are
complete. No DMA candidate establishes the requested win-rate improvement
under the frozen sample-size and cross-pair gates. The charter and current Pine were read in full.
The current baseline minimum center distance is **3 pips**, not the preceding
5-pip study. Only this audit report is owned/modified by the reviewer.

## Pre-outcome requirements and selection clarification (initial review)

- Freeze baseline plus three DMA filters before outcomes: favorable-side
  confirmed close; a same-bar directional crossover; favorable-side close
  with favorable DMA slope. Exact strict/equality conditions must be specified.
- `ta.sma(close, 3)[3]` at bar t is the mean of closes t-5, t-4 and t-3.
  It is a lagged series, not future-price access or just a drawing offset.
  Crossing compares each bar's close against that bar's own delayed DMA;
  slope compares current and previous delayed DMA.
- Apply DMA only at the otherwise valid confirmed min3 candidate. Failure
  cancels preparation and blocks same-bar rearming; do not wait for a later
  DMA recovery. Preserve current Pine's distance tolerance, wick/impulse/gap
  states, next-open entry, no SL, moving-center full exit and cost accounting.
- Use the same nine-pair prefix strictly before 2026-08-31, with unchanged
  source data and causal pre-period warmup. All dates are already viewed.
- Before outcomes, the reviewer raised the charter's final-period restriction.
  The director instructed segment1-only preselection: both cost cases require
  higher win rate, non-worse PF/mean, at least 25% of baseline trades and 30
  trades, and higher win rate in at least 6/9 pairs. Rank by minimum win-rate
  improvement, then PF improvement, then ID; select at most one. Only that
  candidate and baseline access later segments/continuous; no fallback.
- Historical win-rate improvement and profitability/research adoption are
  distinct. A higher win rate alone cannot erase negative net expectancy,
  inadequate samples or hidden open losses. No actual live approval is given.

## Required evidence (initial review)

Inspect frozen protocol and identifiers; independently recompute delayed DMA,
state transitions, orders, trades, all P/L/PF/expectancy/DD/open diagnostics,
prefix causality, cost sensitivity and serialized segment1 selection. Confirm
completed processes/final files and exact current baseline reproduction.
Report no-adoption honestly when thresholds fail. Local tests are not
TradingView compilation or runtime verification.

## Completed evidence and handoff

- Research command `python -m scripts.research_bb3_context_dinapoli` completed
  exit **0**, chunk **aa0db2**. Final `results.json`, pre-later selection,
  execution record, protocol and all **126** NPZ case files were inspected.
- The report-owned independent replay below completed in session **40595**,
  exit **0**, chunk **910d25**, printing **VERIFIED_REJECTED**. All **18,970**
  saved trade rows and all **12** diagnostics matched a separate dictionary
  state implementation. This includes **24** gap-crossing entries and **6,634**
  negative-net center exits; these counts include repeated cost cases and
  overlapping periods, not independent observations.
- All **126** mid-period prefix checks preserved closed trades. All **72**
  baseline cases exactly reproduced the prior center simulator at **3 pips**.
  Both costs have identical execution geometry. Independent delayed-DMA
  arithmetic matched all nine stored hashes, and recomputing shortened DMA
  prefixes preserved every earlier value. No future/upper-timeframe price is
  used. DMA rejection cancels preparation rather than waiting for recovery.
- Independently verified code/Pine/protocol/cache hashes, original source
  size/mtime and every safe-prefix hash. All used timestamps precede
  **2026-08-31**, all used OHLC lie on metadata tick grids within tolerance,
  and no used open/previous-close ratio is outside 0.5–2. The known GBPJPY
  source anomaly remains after the shared cutoff; no source was repaired.
  These checks do not authenticate all vendor history.
- Recomputed every pair/period count, net PF, win rate, expectancy, realized
  drawdown, bar-close MTM drawdown, open mark and rejection count, plus the
  research-score aggregates. Reconstructed all training checks and deltas:
  eligible list is empty, selected is null, and only baseline has later
  artifacts. The serialized preselection contains segment1 only. No fallback
  candidate or post-outcome threshold change was used.
- Independent `python -m pytest tests/test_bb3_context_dinapoli.py
  tests/test_bb3_context_pf_indicator.py -q` completed exit **0**, **66 passed**.
  They are local behavior tests, not TradingView compilation/runtime tests.
- The first reviewer run stopped because the checker expected zero-trade win
  rate to be 0, whereas the documented statistics correctly use `None`.
  Only the checker in this report was corrected; the complete successful
  rerun above is the final evidence. Research and Pine source were unchanged.

### Verified first-segment result

Dates: 2023-09-08 inclusive to 2024-09-08 exclusive; nine pairs. Values are
equal-pip research scores, **not account-currency portfolio returns**.

| Rule | Trades | Fixed-cost win rate | Fixed-cost PF | Fixed-cost net pips | Metadata-cost win rate | Metadata-cost PF |
|---|---:|---:|---:|---:|---:|---:|
| Current min3 baseline | 1,146 | 61.52% | 0.576 | -1,794.25 | 60.30% | 0.543 |
| Favorable DMA side | 15 | 66.67% | 0.673 | -11.17 | 60.00% | 0.593 |
| Directional DMA cross | 9 | 77.78% | 5.600 | +11.50 | 66.67% | 3.179 |
| Favorable side and slope | 1 | 0.00% | 0.000 | -12.22 | 0.00% | 0.000 |

All three variants fail at least 30 trades and 25% retention (requiring
**287** trades given the baseline). Improved-pair counts are **4 / 4 / 0**,
below six. The apparent crossover success comes from only nine trades and
is not accepted. DMA-side also reduces win rate under metadata costs. No
candidate was allowed to access later periods; win-rate improvement and
profit requirements therefore remain unestablished, not retroactively waived.

On the fixed saved trades with metadata costs increased by 50%, first-segment
net becomes **-26.77 / +0.70 / -13.22 pips** for side/cross/side+slope.
Crossover's nine-trade profit nearly disappears. This is descriptive cost
stress, not a fresh selection criterion. Only three frozen DMA variants were
compared; no parameter plateau or profitable waiting-state variant is claimed.

Baseline fixed-cost PF by independent segment is **0.576 / 0.879 / 0.774**;
continuous **4,730** trades have PF **0.767**, win rate **65.64%**, closed net
**-3,862.875** and open **0** pips. Metadata continuous PF is **0.717** and net
**-4,769.275**; a 50% metadata-cost increase makes net **-8,533.475**. All
reported endpoint open marks are zero without forced liquidation.

Full pair/period counts, expectancy, drawdowns and costs are retained in
`agent_runs/bb3_context_dinapoli_20260909/results.json`; readable pair tables
are in `validation.md`. Largest-pair DD is not portfolio DD. No SL is enabled,
so adverse center movement and long holding risks persist. Variable spread,
swap, liquidity, commissions beyond the modeled costs and account-currency
position sizing are not modeled. Dates were previously viewed, not true
holdout. The reviewer modified only this audit report and recommends no Pine
adoption of these failed filters; no live approval is issued.

## Reproducible independent audit

Run the Python block below from the project root. It uses a separate
dictionary-state replay, not the research simulator, for all saved scenarios.
The research simulator is used only for supplementary prefix comparisons.

```python
from pathlib import Path
from datetime import datetime
import numpy as np, math, json, hashlib
root=Path.cwd(); out=root/'agent_runs/bb3_context_dinapoli_20260909'; cache=root/'agent_runs/bb3_context_timing_20260909/completed'
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
assert protocol==json.loads((root/'docs/quant_organization/experiments/bb3_context_dinapoli_20260909/protocol.json').read_text(encoding='utf-8'))
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
from scripts.research_bb3_context_dinapoli import simulate_dma
from scripts.research_bb3_context_center5 import simulate_center
modes={c['id']:c['dma_mode'] for c in protocol['search_space']};assert modes=={'baseline':0,'dma_side':1,'dma_cross':2,'dma_side_slope':3}
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
assert len(list(out.glob('*__*.npz')))==len(result['rows'])==126
print({'status':'VERIFIED_REJECTED','artifacts':126,'full_state_trade_rows':total,'prefix_checks':prefixchecks,
    'baseline_checks':basechecks,'gap_entries':gaps,'negative_net_center_exits':losses,
    'fixed_trade_1p5_metadata_cost_net':{k[0]+'.'+k[1]:round(math.fsum(v),6) for k,v in stress.items()}})
```
