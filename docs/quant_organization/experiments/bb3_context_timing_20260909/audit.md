# BB3 entry-timing independent audit

## Status

**VERIFIED_REJECTED / 不採用**。凍結12候補すべてが学習段階で基準不通過。
既存Pineを採用候補へ変更する根拠なし。実運用承認なし。
対象は `scripts/tradingview/bb3_context_pf_indicator.pine` の売買タイミング。
現行 Pine 全文、`charter.md`、`board.md` を確認した。既存Pineは変更しない。
ユーザーの追加指示により USDJPY, EURUSD, GBPUSD, AUDUSD, NZDUSD,
USDCHF, USDCAD, EURJPY, GBPJPY の9通貨を対象とする責任者通知を受領。

## Pine reproduction requirements

1. BB20 is a 20-close SMA with population standard deviation. ATR14 is Wilder
   RMA initialized from the first 14 true ranges, using high-low for the first
   true range; momentum uses the **previous** ATR. Previous high/low excludes
   the current bar. No future or unconfirmed higher-timeframe values are used.
2. The four breakout memories must update independently on every bar. Reclaim,
   expiry (`age > 3`) and missing-bar gap clear old state before the current
   trigger may initialize a new state. Round-number arithmetic follows Pine's
   tick-rounded interval and previous-close floor/ceil semantics.
3. Wick exclusion is directional and only applies while the corresponding
   band is touched. Its body denominator has a one-minimum-tick floor; the
   default requires wick/body >= 2 and wick/range >= 0.5. It applies both to
   preparation and a later retouch during preparation.
4. Preparation is cleared by unavailable position state or a missing-bar gap.
   The gap bar can start a new preparation. A preparation cannot signal on its
   own bar and expires after three subsequent bars. Exclusion/center/opposite
   checks precede the candidate check. A rejected or signaled bar cannot
   simultaneously initialize another preparation.
5. Pending orders survive missing-bar gaps and enter at the next available bar
   open, even when that open is beyond the prior center target. Do not silently
   cancel these entries. One fixed-size position only; no pyramiding.
6. The entry bar can exit immediately. Open-price gap stops and targets take
   precedence; if neither gap applies and both intrabar levels are reached,
   stop wins. Fill checks use the previously established center; update to the
   current closing SMA **only after** checking this bar's exit. A center exit
   can realize a loss and must not be renamed or hidden.
7. The exit bar cannot prepare or signal. No forced liquidation is part of the
   current Pine. Report the final cost-adjusted open position separately and
   include it when judging whether a positive closed result conceals a loss.
8. Net pips deduct spread + two one-way slippages + round-trip fee once. PF is
   positive net trade amounts / absolute negative net trade amounts. Zero P/L
   is not a win; open P/L is not part of PF. Loss-free finite samples do not
   establish infinite expected profitability.

## Evidence required for adoption

- A results-before-inspection frozen hypothesis, candidate list, data manifest,
  numerical gates, split dates and exact code hashes; otherwise unverified.
- Reproducible completed process, final output JSON and saved individual
  trades, per-pair/per-split counts, net PF, expectancy and drawdown.
- Independent trade arithmetic, temporal/price geometry and summary checks;
  baseline state-machine parity and boundary checks, including both stop and
  center reached, gaps, untouched dojis and center moving behind entry.
- Select once using development/validation evidence, before later-period
  evaluation. Already viewed dates are not a true untouched holdout. Costs
  must not each choose a different favorable candidate for a single adoption
  claim. Require cost stress and neighboring parameter sensitivity evidence.
- Monetary P/L from JPY, USD, CHF and CAD quoted pairs cannot be naively summed.
  Cross-pair pips summaries must be labeled descriptive, not account returns;
  use per-pair results and fixed predeclared gates for selection.
- Unmodeled variable spreads, liquidity slippage, commissions beyond configured
  pips, financing/swap, position sizing and execution limitations must remain
  explicit. Local checks are not TradingView compiler or runtime verification.

## Handoff

This report is the only file owned and changed by the independent reviewer.
The researcher owns the implementation and corrections. No live trading or
real-money adoption is authorized by this audit.

## Initial checks completed

- Read the newly frozen `protocol.json`, `hypothesis.md`, and the director's
  `acceptance.md` before research output existed. The protocol fixes 12
  candidates, three annual splits, two cost cases, and train-only selection
  without a later-period fallback. Its scope amendment to nine pairs is
  recorded as pre-outcome. Source/code hashes and completed results remain
  necessary before establishing actual execution compliance.
- Executed `python -m pytest tests/test_bb3_context_pf_indicator.py -q`:
  **29 passed**, process exit **0**. This checks current source contracts and
  reference examples, not execution of Pine or the new research implementation.
- Caution: 100 full-period trades and 30 final-period trades across nine pairs
  do not ensure adequate per-pair samples. Even a mechanical pass would be
  research-only; display each pair's count rather than imply broad certainty.
- Cost-dependent distance gates change the entry set between the two cost
  cases. Such results are not a pure fixed-trade-list cost stress. A separate
  increased-cost arithmetic check on unchanged saved trades is useful and
  will not be substituted for the frozen adoption gates.

## Final verification evidence

- Researcher reported process `52497` terminal **exit 0** with final
  `RESULT_JSON`, status `REJECTED`, selected `null`. The independent reviewer
  inspected the completed artifacts under
  `agent_runs/bb3_context_timing_20260909/completed/`, not incomplete files
  from the first failed launch. `results.json`, the pre-validation selection,
  source/protocol hashes and data manifest are consistent with each other.
- Two pre-result implementation failures were corrected by the researcher:
  Numba `float(bool)` typing and module-path cache loading. The independent
  reviewer did not modify implementation or gates. Full-period evaluation of
  all unselected candidates was removed before completed execution, following
  reviewer feedback; only baseline had later-period descriptive evaluation
  because no candidate passed training.
- Independent synthetic check exited **0**: **20,000 feature rows**, **48**
  simulation settings, **269** matched closed trades and all final diagnostics,
  **144** prefix-truncation comparisons with identical already-closed trades.
  This used standard-library mean/population variance, an alternative ATR
  recurrence and a separate dictionary-based position/preparation state.
- Saved-history verification exited **0**, printing `VERIFIED_REJECTED`:
  **270** result artifacts, **47,196** saved trade rows. All entry/exit geometry,
  first eligible signal, chronological constraints, costs, net P/L, PF, mean,
  win rate, open P/L and bar-close MTM drawdown were independently checked.
  This row count includes overlapping periods/cost scenarios; it is not a
  count of independent market observations.
- All nine saved OHLC hashes match manifests; source files still match captured
  size/mtime, all saved BB/ATR observations were independently recomputed,
  and **9,000** prior-high/low observations matched. Source/code/protocol hashes
  matched current files. Source stat stability does not authenticate the vendor
  feed or establish broker-specific TradingView equivalence.
- **46** saved gap-crossing entries and **24,021** net-loss center exits were
  preserved, not discarded to improve results. All aggregate summaries and the
  frozen train-only candidate ranking/rejection were independently reproduced.
- On unchanged training trade lists, increasing each metadata round-trip cost
  by 50% left every candidate negative. The least-negative candidate under
  this extra descriptive stress was `previous_break_distance3`, **-624.105**
  equal-pip research-score pips. This is neither an account return nor a new
  selection criterion. No parameter-sensitivity claim rescues a failed gate.
- Per-pair and per-period numerical results are in `completed/results.json`
  (`rows` and `summaries`); the researcher's `validation.md` is the human-readable
  handoff. No unselected candidate has an independently unseen final-period
  result, and all dates were already viewed in earlier work anyway.

The user objective (a positively profitable modified Pine) remains **not
achieved** by this experiment. Existing Pine is unchanged; local parity checks
are not TradingView compilation or live/backtest-runtime verification.

## Reproducible independent checks

Run from the project root (the embedded Python is audit-owned evidence, not a
strategy change):

```powershell
@'
from pathlib import Path
source = Path('docs/quant_organization/experiments/bb3_context_timing_20260909/audit.md').read_text(encoding='utf-8')
exec(source.split('```python\n', 1)[1].split('\n```', 1)[0])
'@ | python -
```

```python
import sys, math, statistics
sys.path.insert(0, 'scripts')
import numpy as np
import scripts.research_bb3_context_timing as r
rng = np.random.default_rng(74012)
n = 20000
c = 150 + np.cumsum(rng.normal(0, .04, n)); o = np.r_[c[0], c[:-1]]
h = np.maximum(o, c) + rng.exponential(.01, n)
l = np.minimum(o, c) - rng.exponential(.01, n)
a = np.column_stack((o, h, l, c)); t = np.arange(n, dtype=np.int64) * 300
t[9000:] += 172800
f = r.features(a, t, .01, .001)
ref = np.full((n, 15), np.nan); ref[:, :4] = a
atr = None; trs = []; memories = [None] * 4
for i, (op, hi, lo, cl) in enumerate(a):
    prev = a[i-1, 3] if i else cl
    tr = max(hi-lo, abs(hi-prev), abs(lo-prev)); trs.append(tr)
    ref[i, 7] = atr if atr is not None else np.nan
    if i == 13: atr = statistics.mean(trs)
    elif i > 13: atr = atr + (tr-atr)/14
    if i >= 19:
        x = c[i-19:i+1]; mid = statistics.mean(x); dev = statistics.pstdev(x)
        ref[i, 4:7] = mid, mid+3*dev, mid-3*dev
    if i: ref[i, 8:10] = max(h[max(0, i-12):i]), min(l[max(0, i-12):i])
    gap = bool(i and t[i]-t[i-1] > 300); ref[i, 14] = gap
    levels = [ref[i, 8], ref[i, 9], (math.floor(prev/.5)+1)*.5, (math.ceil(prev/.5)-1)*.5]
    impulse = tr >= ref[i, 7]*1.5
    triggers = [cl>levels[0] and impulse, cl<levels[1] and impulse,
                hi>=levels[2] and cl>levels[2] and impulse,
                lo<=levels[3] and cl<levels[3] and impulse]
    for k, m in enumerate(memories):
        if m is not None and (gap or i-m[0]>3 or (cl<=m[1] if k in (0, 2) else cl>=m[1])):
            memories[k] = None
        if triggers[k]: memories[k] = (i, levels[k])
    ref[i, 10:12] = any(memories[k] is not None for k in (1, 3)), any(memories[k] is not None for k in (0, 2))
    body = max(abs(cl-op), .001)
    ref[i, 12] = lo<=ref[i, 6] and hi>lo and min(op, cl)-lo>=max(2*body, (hi-lo)/2)
    ref[i, 13] = hi>=ref[i, 5] and hi>lo and hi-max(op, cl)>=max(2*body, (hi-lo)/2)
np.testing.assert_allclose(f, ref, rtol=1e-12, atol=1e-12, equal_nan=True)

def replay(f, t, start, end, pip, cost, mode, expiry, distance):
    setup = queued = position = None
    records = []; realized = peak = dd = 0.; preps = signals = 0; last_entry = -1
    for i in np.flatnonzero((t>=start) & (t<end)):
        op, hi, lo, cl, mid, upper, lower = f[i, :7]; exited = False
        if queued is not None:
            side, prepi, signali, target = queued; queued = None; last_entry = i
            position = dict(side=side, prep=prepi, signal=signali, index=i, entry=op, target=target)
        if position is not None:
            p = position; d = p['side']; target = p['target']
            reached = hi>=target if d==1 else lo<=target
            if reached:
                fill = max(op, target) if d==1 else min(op, target)
                net = d*(fill-p['entry'])/pip-cost
                records.append([d, p['prep'], p['signal'], p['index'], i, p['entry'], fill, target, net])
                realized += net; position = None; exited = True
            else: position['target'] = mid
        openp = 0. if position is None else position['side']*(cl-position['entry'])/pip-cost
        equity = realized+openp; peak = max(peak, equity); dd = max(dd, peak-equity)
        ready = (position is None and queued is None and not exited and np.isfinite(mid)
                 and upper>mid and np.isfinite(f[i, 7]) and np.isfinite(f[i, 8]))
        if not ready or f[i, 14]: setup = None
        if not ready: continue
        touch = [lo<=lower, hi>=upper]; blocked = False; chosen = 0
        if setup is not None:
            d, pidx = setup; k = 0 if d==1 else 1
            blocked = bool(f[i, 10+k] or f[i, 12+k] or i-pidx>expiry or d*(cl-mid)>=0 or touch[1-k])
            if blocked: setup = None
            else:
                inside = lower<cl<upper
                confirm = (mode==0 or (mode==1 and d*(cl-op)>0 and d*(cl-f[i-1, 3])>0)
                           or (mode==2 and d*(cl-f[i-1, 1 if d==1 else 2])>0)
                           or (mode==3 and d*(cl-f[pidx, 1 if d==1 else 2])>0))
                if i>pidx and inside and confirm and d*(mid-cl)/pip>=distance*cost:
                    chosen = d; queued = (d, pidx, i, mid); signals += 1; setup = None
        if setup is None and not blocked and not chosen and any(touch):
            k = 0 if touch[0] else 1
            if not all(touch) and not f[i, 10+k] and not f[i, 12+k]:
                setup = (1 if k==0 else -1, i); preps += 1
    p = position
    diag = np.array([0. if p is None else p['side']*(cl-p['entry'])/pip-cost,
                     dd, 0 if p is None else p['side'], np.nan if p is None else p['entry'],
                     cl, 0 if queued is None else queued[0], preps, signals, last_entry,
                     p['target'] if p else queued[3] if queued else np.nan])
    return np.asarray(records).reshape((-1, 9)), diag

count = prefix_checks = 0
for mode in range(4):
    for expiry in (3, 6):
        for distance in (0., 2., 3.):
            for cost in (1.4, 3.2):
                args = (f, t, t[100], t[-1]+300, .01, cost, mode, expiry, distance)
                x, d = r.simulate(*args); y, e = replay(*args)
                np.testing.assert_allclose(x, y, rtol=1e-12, atol=1e-10, equal_nan=True)
                np.testing.assert_allclose(d, e, rtol=1e-12, atol=1e-10, equal_nan=True)
                for edge in (5000, 9000, 15000):
                    p, _ = r.simulate(f[:edge], t[:edge], t[100], t[edge], .01, cost, mode, expiry, distance)
                    np.testing.assert_array_equal(p, x[x[:, 4]<edge]); prefix_checks += 1
                count += len(x)
print({'status':'PASS', 'seed':74012, 'feature_rows':n, 'simulation_variants':48,
       'matched_closed_trades':count, 'prefix_checks':prefix_checks,
       'scope':'independent scalar features and dictionary-state OHLC replay; no Pine runtime'})
```

Saved-result checks below can be run by changing the extraction command to
`source.split('```python\n')[2].split('\n```', 1)[0]`. They do not call the
researcher's statistics or simulation functions.

```python
from pathlib import Path
from datetime import datetime
import hashlib, json, math
import numpy as np
root = Path.cwd(); out = root/'agent_runs/bb3_context_timing_20260909/completed'
read = lambda name: json.loads((out/name).read_text(encoding='utf-8'))
p = read('protocol.json'); result = read('results.json'); manifest = read('data_manifest.json')
selection = read('selection_before_validation.json')
for path, digest in read('code_hashes.json').items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest() == digest, ('code drift', path)
assert json.loads((root/'docs/quant_organization/experiments/bb3_context_timing_20260909/protocol.json').read_text(encoding='utf-8')) == p
def near(a, b):
    if a is None or b is None: assert a is b, (a,b)
    else: assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-7), (a,b)
def epoch(s): return int((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds())
inputs = {}; feature_samples = 0
for m in manifest:
    z = np.load(out/(m['symbol']+'_features.npz')); f = z['features']; t = z['times']; inputs[m['symbol']] = (f,t,m)
    assert hashlib.sha256(t.tobytes()+f[:,:4].copy().tobytes()).hexdigest() == m['time_ohlc_sha256']
    assert m['before'] == m['after']
    stat = (Path(p['history_directory'])/m['symbol']/'Bars.dat').stat()
    assert {'size':stat.st_size,'mtime_ns':stat.st_mtime_ns} == m['after']
    assert len(t) == m['bars'] and np.all(np.diff(t)>0)
    closes = np.lib.stride_tricks.sliding_window_view(f[:,3],20)
    mid = closes.mean(axis=1); dev = closes.std(axis=1,ddof=0)
    np.testing.assert_allclose(f[19:,4],mid,atol=1e-10,rtol=1e-12)
    np.testing.assert_allclose(f[19:,5],mid+3*dev,atol=1e-10,rtol=1e-12)
    np.testing.assert_allclose(f[19:,6],mid-3*dev,atol=1e-10,rtol=1e-12)
    previous = np.r_[f[0,3],f[:-1,3]]
    tr = np.maximum.reduce((f[:,1]-f[:,2],abs(f[:,1]-previous),abs(f[:,2]-previous)))
    atr = math.fsum(tr[:14])/14
    for i in range(14,len(t)):
        near(f[i,7],atr); atr += (tr[i]-atr)/14
    np.testing.assert_array_equal(f[1:,14], np.diff(t)>300)
    for i in np.unique(np.linspace(20,len(t)-1,1000,dtype=int)):
        near(f[i,8],max(f[i-12:i,1])); near(f[i,9],min(f[i-12:i,2]));feature_samples+=1
candidates = {c['id']:c for c in p['search_space']}
trade_count = gap_entries = center_loss = 0; row_results = {}
stress = {cid:[] for cid in candidates}
for row in result['rows']:
    f,t,m = inputs[row['symbol']]; pip = m['pip']; cost = row['cost_pips']; cand = candidates[row['candidate']]
    z = np.load(out/row['artifact']); trades = z['trades']; d = z['diagnostic']; last_exit = -1
    bounds = p['periods'].get(row['period'],['2023-09-08','2026-09-08']); start,end=map(epoch,bounds)
    vals=[]
    for side,prep,signal,entry_i,exit_i,entry,exit_price,target,net in trades:
        prep,signal,entry_i,exit_i = map(int,(prep,signal,entry_i,exit_i)); k=0 if side==1 else 1
        assert side in (-1,1) and last_exit<prep<signal<entry_i<=exit_i and entry_i==signal+1
        assert start<=t[prep] and t[exit_i]<end and signal-prep<=cand['expiry'];last_exit=exit_i
        assert not np.any(f[prep+1:signal+1,14])
        assert f[prep,2]<=f[prep,6] if side==1 else f[prep,1]>=f[prep,5]
        assert not (f[prep,2]<=f[prep,6] and f[prep,1]>=f[prep,5])
        assert not np.any(f[prep:signal+1,10+k]) and not np.any(f[prep:signal+1,12+k])
        assert np.all(side*(f[prep+1:signal+1,3]-f[prep+1:signal+1,4])<0)
        assert np.all(f[prep+1:signal+1,1]<f[prep+1:signal+1,5]) if side==1 else np.all(f[prep+1:signal+1,2]>f[prep+1:signal+1,6])
        first_allowed=None
        for i in range(prep+1,signal+1):
            cl=f[i,3];mode=cand['mode']
            allowed=(f[i,6]<cl<f[i,5] and side*(f[i,4]-cl)/pip>=cand['distance_cost_multiple']*cost)
            if mode==1: allowed=allowed and side*(cl-f[i,0])>0 and side*(cl-f[i-1,3])>0
            if mode==2: allowed=allowed and side*(cl-f[i-1,1 if side==1 else 2])>0
            if mode==3: allowed=allowed and side*(cl-f[prep,1 if side==1 else 2])>0
            if allowed:first_allowed=i;break
        assert first_allowed==signal
        near(entry,f[entry_i,0]); near(target,f[exit_i-1,4])
        if side==1:
            assert np.all(f[entry_i:exit_i,1]<f[entry_i-1:exit_i-1,4]); assert f[exit_i,1]>=target
            near(exit_price,max(f[exit_i,0],target))
        else:
            assert np.all(f[entry_i:exit_i,2]>f[entry_i-1:exit_i-1,4]); assert f[exit_i,2]<=target
            near(exit_price,min(f[exit_i,0],target))
        value=side*(exit_price-entry)/pip-cost;near(net,value);vals.append(value)
        gap_entries+=int(t[entry_i]-t[signal]>300);center_loss+=int(value<0)
    gp=math.fsum(v for v in vals if v>0);gl=-math.fsum(v for v in vals if v<0);net=math.fsum(vals)
    calc={'trades':len(vals),'wins':sum(v>0 for v in vals),'gross_profit_pips':gp,'gross_loss_pips':gl,
          'net_pips':net,'profit_factor':gp/gl if gl else None,'average_pips':net/len(vals) if vals else None,
          'win_rate_pct':100*sum(v>0 for v in vals)/len(vals) if vals else 0}
    for key,value in calc.items():near(row[key],value)
    last=np.flatnonzero((t>=start)&(t<end))[-1];near(d[4],f[last,3])
    open_net=d[2]*(d[4]-d[3])/pip-cost if d[2] else 0.
    near(d[0],open_net);near(row['open_net_pips'],open_net);near(row['net_plus_open_pips'],net+open_net)
    near(row['bar_close_mtm_drawdown_pips'],d[1])
    # Reconstruct realized plus marked-to-close equity without research replay.
    begin=np.searchsorted(t,start);finish=np.searchsorted(t,end);equity=np.zeros(finish-begin);realized=0.
    for trd in trades:
        side,_,_,en,ex,entry,_,_,v=trd;en,ex=int(en),int(ex)
        equity[en-begin:ex-begin] += side*(f[en:ex,3]-entry)/pip-cost
        equity[ex-begin:] += v
    if d[2]:
        en=int(d[8]);equity[en-begin:] += d[2]*(f[en:finish,3]-d[3])/pip-cost
    dd=float(np.max(np.maximum.accumulate(np.r_[0.,equity])[1:]-equity)) if len(equity) else 0.
    near(d[1],dd)
    trade_count+=len(vals);row_results[(row['candidate'],row['cost_case'],row['period'],row['symbol'])]=calc
    if row['period']=='training' and row['cost_case']=='metadata_spread_plus_0p2':stress[row['candidate']].extend(v-cost*.5 for v in vals)
for cid,costs in result['summaries'].items():
    for cost,periods in costs.items():
        for period,s in periods.items():
            rows=[row for row in result['rows'] if (row['candidate'],row['cost_case'],row['period'])==(cid,cost,period)]
            assert len(rows)==9
            for key in ('trades','wins','gross_profit_pips','gross_loss_pips','net_pips','open_net_pips','net_plus_open_pips'):
                near(s[key],math.fsum(row[key] for row in rows))
            near(s['profit_factor'],s['gross_profit_pips']/s['gross_loss_pips'] if s['gross_loss_pips'] else None)
            assert s['positive_pairs']==sum(row['net_pips']>0 for row in rows)
eligible=[]
for cid,costs in result['summaries'].items():
    train=[v['training'] for v in costs.values()]
    if cid!='baseline' and all(s['net_pips']>0 and s['net_plus_open_pips']>0 and s['trades']>=40 and s['positive_pairs']>=6 for s in train):eligible.append(cid)
eligible.sort(key=lambda cid:(-min(v['training']['net_pips'] for v in result['summaries'][cid].values()),cid))
assert selection['eligible_train']==eligible and selection['selected']==(eligible[0] if eligible else None)==result['selected']
assert all(row['candidate'] in ('baseline',result['selected']) for row in result['rows'] if row['period']!='training')
assert result['status']=='REJECTED' and not eligible and result['live_approved'] is False
print({'status':'VERIFIED_REJECTED','artifacts':len(result['rows']),'independently_checked_trades':trade_count,
       'sampled_prior_extrema':feature_samples,'gap_entries':gap_entries,'loss_center_exits':center_loss,
       'fixed_trade_1p5_metadata_cost_training_net':{k:round(math.fsum(v),6) for k,v in stress.items()},
       'scope':'hashes, features, all trade chronology/earliest entry/exit, net/PF/mean/wins/open/MTM DD, aggregate, train-only rejection'})
```
