# BB3 finite stop/target independent audit

## Status

**VERIFIED_REJECTED / 不採用**。19候補すべて両コストの学習基準不通過。
Research director reports explicit user approval to
review stop-loss and take-profit rules. This is a new experiment after the two
entry-only experiments were rejected, not a retrospective change to their
results. The charter was reread before this audit began.

## Pre-implementation audit requirements

- Freeze 19 candidates before outcomes: original baseline plus market/limit
  entry crossed with SL 5 pips / 10 pips / 1.5 prior ATR and dynamic center /
  fixed gross RR 1.3 / fixed gross RR 1.5 full exits. Same nine pairs and
  previously viewed three years; same train-only selection and no fallback.
- Signal-time prior ATR must be frozen for the order. Stop/target levels must
  use actual entry fill, not a favorable assumed close. Tick quantization and
  its effect on the realized gross distance ratio must be explicit.
- Market entry occurs at the next available open. Limit entry retains the
  prior experiment's causal activation/TTL/cancellation rules. No cancellation
  based on a bar's final close may erase an earlier valid fill in that bar.
- For an intrabar buy limit, reaching an SL below that limit requires crossing
  the entry level first (sell symmetrically); same-bar SL can be counted.
  A simultaneously touched target does not establish target-after-entry, so
  same-bar target suppression must remain explicit. Opening fills permit
  ordinary same-bar stop/target testing.
- Gap stop/target fills use the opening price before intrabar reach tests;
  otherwise both SL and TP reached implies SL first. No omitted losses or
  changed transaction-cost accounting. Full exits, no breakeven numerator
  changes, no hidden partial exits.
- Only dynamic-center trades update target after current-bar fill checks.
  Fixed-RR targets and all stop levels remain fixed after entry. There is no
  forced last-bar liquidation in PF; open P/L remains separately visible.
- Verify frozen hashes/manifest, actual process completion, every saved trade,
  final open diagnostics, MTM drawdown, per-pair/per-period summaries, prefix
  invariance, cost stress and train-only selection. Only baseline plus the
  preselected candidate may access later-period evaluations.

Only this audit report is owned/modified by the independent reviewer. Strategy
implementation and adoption criteria are read-only. Local reference tests do
not constitute TradingView compilation, runtime validation or live approval.

## Specification review completed before outcomes

The newly saved `protocol.json` and `hypothesis.md` were read in full before
implementation execution. The candidate budget is exactly 19. Signal-time
risk is rounded upward to a positive integer count of ticks; fixed reward is
`ceil(risk_ticks * RR)` ticks from the actual fill. Thus the tick-quantized
gross ratio is at least the nominal value, with less than one reward tick of
rounding difference. Report actual distances rather than promise an exact
decimal ratio or net-of-cost RR.

For limit orders, pending cancellation remains based on the previous confirmed
center even if the eventual position will use a fixed-RR target. This is an
explicit pre-entry opportunity-expiry rule, not a mutation of a held fixed
target. Fixed SL and fixed RR prices must never subsequently follow the SMA.

No specification changes were requested by this reviewer. The cost models,
training ranking, numerical gates, quote-currency warning, and later-period
access restrictions are recorded before outcomes. Prior exposure and the
small possible per-pair sample sizes remain limitations despite these gates.

## Completed independent evidence

- Research command `python -m scripts.research_bb3_context_exits` completed
  with exit **0**, chunk `dc5110`, final `RESULT_JSON` status `REJECTED`,
  selected `null`. Final results, saved NPZ files, `execution.json`, input/code
  hashes, manifest and frozen pre-validation selection were inspected.
- The independent replay below completed in session **29760**, exit **0**,
  printing `VERIFIED_REJECTED`: **396** artifacts and **80,208** saved trades.
  The **49,164** finite-stop candidate trades were reproduced from every
  included bar by a separate dictionary-state implementation, not by invoking
  the researcher's simulation to generate expected trades. All **15** trade
  columns and **20** final diagnostics matched. Baseline arrays exactly matched
  the prior independently audited baseline. Counts include duplicate cost
  cases and overlapping baseline periods, not independent observations.
- **324** prefix truncations preserved all previously closed trades exactly.
  **598** ambiguous limit-entry bars, **504** dual SL/TP-touch position bars,
  and **23,708** stop exits matched the independent execution-order replay.
- Verified signal-time prior ATR, actual-fill-based stop, risk rounding,
  target rounding and actual gross RR, frozen fixed targets, dynamic-center
  update order, gap fills, intrabar-limit SL and TP suppression, open positions,
  marked-to-close drawdown, costs, PF, mean, win counts/rates and all aggregate
  summaries. No excluded losses or positive-P/L-only reporting was found.
- Input/code/protocol hashes and current source-file size/mtime matched.
  Train-only ranking yields no eligible candidate; only baseline accessed
  validation/final/continuous periods. All periods were previously viewed.
- Keeping the same saved trades and increasing metadata round-trip costs by
  50% leaves every candidate negative. The least-negative altered-stop case
  is `limit_slatr_rr13`, **-1,404.6** equal-pip research-score pips. This stress
  does not replace the frozen gates. All 18 neighboring entry/stop/target
  combinations failed the original gates, so no profitable robust region was
  established.
- Independent test rerun:
  `python -m pytest tests/test_bb3_context_timing.py tests/test_bb3_context_retest.py tests/test_bb3_context_exits.py -q`
  initially completed exit **0**, **36 passed**. After the researcher added
  test-only coverage (all 18 variants' prefix behavior, delayed-limit ATR
  freezing and pending-center cancellation for fixed-RR cases), the same
  command was independently rerun: exit **0**, **56 passed**. Research source
  and result-defining logic were unchanged. These are local behavior tests,
  not TradingView compiler/runtime tests.

## Per-pair evidence for the highest aggregate-PF alternative

This is a descriptive failed candidate, **not** a recommendation or a
postselected single-pair adoption. Candidate `limit_sl10_rr15`; training
2023-09-08 inclusive to 2024-09-08 exclusive; metadata spread + 0.2-pip costs.
All nine terminal open-P/L values are zero. DD is bar-close marked-to-market
drawdown in pips, not a monetary-account DD or an intrabar worst-case bound.

| Pair | Trades | Net PF | Net pips | Mean pips | DD pips |
|---|---:|---:|---:|---:|---:|
| USDJPY | 90 | 0.7640 | -148.0 | -1.6444 | 213.8 |
| EURUSD | 88 | 0.5959 | -269.4 | -3.0614 | 276.5 |
| GBPUSD | 100 | 0.6497 | -260.1 | -2.6010 | 319.8 |
| AUDUSD | 75 | 1.4389 | 170.1 | 2.2680 | 92.3 |
| NZDUSD | 93 | 0.9500 | -29.6 | -0.3183 | 173.4 |
| USDCHF | 40 | 0.7573 | -68.7 | -1.7175 | 125.9 |
| USDCAD | 98 | 0.8887 | -71.6 | -0.7306 | 164.6 |
| EURJPY | 42 | 0.4725 | -187.0 | -4.4524 | 217.3 |
| GBPJPY | 45 | 0.6027 | -139.4 | -3.0978 | 200.5 |

Only 1/9 pairs is positive, below the predeclared 6/9. The isolated AUDUSD
training result does not authorize selecting that pair after seeing results.
All other per-pair/per-period metrics are in `results.json` (`rows` and
`summaries`), and the researcher records candidate comparisons in
`validation.md`. Failed candidates were not run through later-period selection.

## Handoff and remaining limitations

Reject this finite stop/target experiment; preserve existing Pine. The user
objective of a verified positively profitable modified indicator is still not
achieved. Do not describe any alternative as a profitable replacement.

Costs remain fixed pips, not variable spread or a bid/ask execution replay.
Swap/financing, queue position, liquidity, partial fills, broker constraints,
account-currency sizing and intrabar mark-to-market risk are not implemented.
Mixed-quote pips aggregates are research scores, not actual monetary returns.
No true unseen holdout, TradingView runtime verification or real-money approval
is asserted. Only this audit report was modified by the independent reviewer.

## Independent reproduction

From the workspace root, read this report as `source` and run
`exec(source.split('```python\n',1)[1].split('\n```',1)[0])` in Python.
This report-owned replay does not invoke the research implementation to
produce expected full-run trades or statistics.

```python
from pathlib import Path
from datetime import datetime
import numpy as np, math, json, hashlib
root=Path.cwd();out=root/'agent_runs/bb3_context_exits_20260909'
cache=root/'agent_runs/bb3_context_timing_20260909/completed'
read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
def epoch(s):return int((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds())
def near(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7),(a,b)

def independent_exits(f,t,start,end,pip,cost,tick,is_limit,stop_mode,rr):
    position=order=setup=None;records=[];realized=peak=dd=0.
    nprep=nsignal=namb=ncancel=nopen=nintra=ndual=0;last_entry=-1;kind=0
    last_target=last_stop=last_initial=last_atr=last_risk=np.nan
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
                if at_target:order=None;handled=True;ncancel+=1
                elif limit_touch:
                    position={**q,'entry':op if at_limit else limit,'index':i};order=None;entered=True
                    suppress=not at_limit;kind=1 if at_limit else 2;nopen+=int(at_limit);nintra+=int(not at_limit)
                elif target_touch:order=None;handled=True;ncancel+=1
                else:
                    cancel=(i-q['signal']>=3 or f[i,10+k] or f[i,12+k] or d*(cl-mid)>=0
                            or (hi>=upper if d==1 else lo<=lower) or f[i,14])
                    if cancel:order=None;handled=True;ncancel+=1
                    else:order['target']=mid;last_target=mid
        if entered:
            p=position;d=p['side'];last_entry=i;p['kind']=kind
            p['stop']=p['entry']-d*p['risk'];last_stop=p['stop']
            if rr:p['target']=p['entry']+d*math.ceil(p['risk_ticks']*rr)*tick
            p['initial']=p['target'];last_initial=p['target'];last_target=p['target']
            namb+=int(suppress and (hi>=p['target'] if d==1 else lo<=p['target']))
        if position is not None:
            p=position;d=p['side'];target=p['target'];stop=p['stop']
            hit_sl=min(d*(lo-stop),d*(hi-stop))<=0
            hit_tp=max(d*(lo-target),d*(hi-target))>=0
            ndual+=int(hit_sl and hit_tp);price=None;stopped=False
            if d*(op-stop)<=0:price=op;stopped=True
            elif not suppress and d*(op-target)>=0:price=op
            elif hit_sl:price=stop;stopped=True
            elif not suppress and hit_tp:price=target
            if price is not None:
                net=d*(price-p['entry'])/pip-cost
                records.append([d,p['prep'],p['signal'],p['index'],i,p['entry'],price,target,net,
                                stop,p['initial'],p['risk'],p['atr'],p['kind'],int(stopped)])
                realized+=net;position=None;handled=True;last_target=last_stop=last_initial=np.nan
            elif not rr:position['target']=mid;last_target=mid
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
                chosen=d;raw=cl-d*f[i,7]
                limit=(math.floor(raw/tick) if d==1 else math.ceil(raw/tick))*tick
                rawrisk=5*pip if stop_mode==1 else 10*pip if stop_mode==2 else 1.5*f[i,7]
                ticks=max(1,math.ceil(rawrisk/tick));last_risk=ticks*tick;last_atr=f[i,7]
                order=dict(side=d,prep=prep,signal=i,target=mid,limit=limit,risk=last_risk,risk_ticks=ticks,atr=last_atr)
                last_target=mid;nsignal+=1;setup=None
        if setup is None and not blocked and not chosen and any(touch):
            k=0 if touch[0] else 1
            if not all(touch) and not f[i,10+k] and not f[i,12+k]:setup=(1 if k==0 else -1,i);nprep+=1
    p=position
    diag=np.array([0. if p is None else p['side']*(cl-p['entry'])/pip-cost,dd,
                   0 if p is None else p['side'],np.nan if p is None else p['entry'],cl,
                   0 if order is None else order['side'],nprep,nsignal,last_entry,last_target,
                   namb,ncancel,nopen,nintra,ndual,last_stop,last_risk,last_initial,last_atr,kind])
    return np.asarray(records).reshape((-1,15)),diag

protocol=read('protocol.json');result=read('results.json');manifest=read('data_manifest.json')
for path,digest in read('code_input_hashes.json').items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,('hash',path)
assert manifest==json.loads((cache/'data_manifest.json').read_text(encoding='utf-8'))
assert protocol==json.loads((root/'docs/quant_organization/experiments/bb3_context_exits_20260909/protocol.json').read_text(encoding='utf-8'))
inputs={}
for m in manifest:
    z=np.load(cache/(m['symbol']+'_features.npz'));inputs[m['symbol']]=(z['features'],z['times'],m)
    st=(Path(protocol['history_directory'])/m['symbol']/'Bars.dat').stat()
    assert {'size':st.st_size,'mtime_ns':st.st_mtime_ns}==m['after']
candidates={c['id']:c for c in protocol['search_space']}
total=independent_count=prefix_checks=ambiguous=dualtouch=stops=0;stress={c:[] for c in candidates}
from scripts.research_bb3_context_exits import simulate_exits
for row in result['rows']:
    f,t,m=inputs[row['symbol']];pip=m['pip'];cost=row['cost_pips'];c=candidates[row['candidate']]
    z=np.load(out/row['artifact']);trades=z['trades'];d=z['diagnostic']
    bounds=protocol['periods'].get(row['period'],['2023-09-08','2026-09-08']);start,end=map(epoch,bounds)
    if row['candidate']=='baseline':
        old=np.load(cache/row['artifact']);np.testing.assert_array_equal(trades,old['trades']);np.testing.assert_array_equal(d,old['diagnostic'])
    else:
        mode={'pips5':1,'pips10':2,'atr1.5':3}[c['stop']];rr={'center':0.,'rr1.3':1.3,'rr1.5':1.5}[c['target']]
        expected,diag=independent_exits(f,t,start,end,pip,cost,m['tick'],c['entry']=='limit',mode,rr)
        np.testing.assert_allclose(trades,expected,atol=1e-9,rtol=1e-12,equal_nan=True)
        np.testing.assert_allclose(d,diag,atol=1e-8,rtol=1e-12,equal_nan=True)
        independent_count+=len(trades);ambiguous+=int(d[10]);dualtouch+=int(d[14]);stops+=int(trades[:,14].sum())
        edge=np.searchsorted(t,(start+end)//2)
        short,_=simulate_exits(f[:edge],t[:edge],start,int(t[edge]),pip,cost,m['tick'],c['entry']=='limit',mode,rr)
        np.testing.assert_array_equal(short,trades[trades[:,4]<edge]);prefix_checks+=1
        near(row['ambiguous_entry_bars'],d[10]);near(row['canceled_orders'],d[11]);near(row['dual_touch_bars'],d[14]);near(row['stop_exits'],trades[:,14].sum())
        if len(trades):
            np.testing.assert_allclose(trades[:,12],f[trades[:,2].astype(int),7],rtol=0,atol=0)
            np.testing.assert_allclose(trades[:,9],trades[:,5]-trades[:,0]*trades[:,11],atol=1e-12)
            if rr:
                actual=trades[:,0]*(trades[:,10]-trades[:,5]);assert np.all(actual>=rr*trades[:,11]-1e-12)
                assert np.all(actual-rr*trades[:,11]<m['tick']+1e-12)
                np.testing.assert_array_equal(trades[:,7],trades[:,10])
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
            for key in ('trades','wins','gross_profit_pips','gross_loss_pips','net_pips','open_net_pips','net_plus_open_pips','ambiguous_entry_bars','canceled_orders','dual_touch_bars','stop_exits'):near(s[key],math.fsum(v[key] for v in rows))
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
       'independent_full_state_exit_trade_rows':independent_count,'prefix_checks':prefix_checks,
       'ambiguous_entry_bars':ambiguous,'dual_touch_bars':dualtouch,'stop_exits':stops,
       'fixed_trade_1p5_metadata_cost_training_net':{k:round(math.fsum(v),6) for k,v in stress.items()}})
```
