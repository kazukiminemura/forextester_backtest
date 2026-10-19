# BTC spot RR1 独立検証

状態: VERIFIED_DESCRIPTIVE / RESEARCH_SCREEN_FAILED。2026-10-07 に全12ケースの独立再現がexit0で完了。通常費用の主案は2018–2020年10件/PF0.245、2021–2023年70件/PF0.706、2024–2026-10-06年57件/PF1.217。事前screen不通過、採用承認なし。

開発runnerの売買・会計関数をimportしない。原履歴とcacheの一致、全シグナル、全判断、全取引列、保存equity、全M1から再計算したDD、年別指標、screenを比較する。

## 再実行手順

リポジトリルートで、以下のPythonコードブロックを抽出してメモリ実行する。ファイル編集はこの監査文書に限定する。

```powershell
$auditCode = @'
from pathlib import Path
p = Path('docs/quant_organization/experiments/btc_spot_rr1_20261007/validation.md')
code = p.read_text(encoding='utf-8').split('```python\n', 1)[1].split('\n```', 1)[0]
exec(compile(code, str(p), 'exec'))
'@
$auditCode | python -
```

## 独立再現コード

```python
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path.cwd()
OUT = ROOT / 'agent_runs/btc_spot_rr1_20261007'
DOC = ROOT / 'docs/quant_organization/experiments/btc_spot_rr1_20261007'
protocol = json.loads((DOC / 'protocol.json').read_text(encoding='utf-8'))
report = json.loads((OUT / 'results.json').read_text(encoding='utf-8'))
manifest = json.loads((OUT / 'input_manifest.json').read_text(encoding='utf-8'))
assert protocol['status'] == 'SPEC_FROZEN'
checks = {'signals': 0, 'trades': 0, 'decisions': 0, 'equity': 0, 'scalars': 0}

def digest(path):
    obj = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            obj.update(block)
    return obj.hexdigest()

def stamp(value):
    return int(np.datetime64(value, 's').astype('int64'))

def same(actual, expected, name):
    if isinstance(expected, dict):
        assert set(actual) == set(expected), (name, set(actual) ^ set(expected))
        for k, v in expected.items():
            same(actual[k], v, name + '/' + k)
    elif expected is None:
        assert actual is None, (name, actual, expected)
    elif isinstance(expected, (bool, np.bool_)):
        assert str(actual).lower() == str(bool(expected)).lower(), (name, actual, expected)
    elif isinstance(expected, (int, float, np.number)):
        assert np.isclose(float(actual), float(expected), rtol=2e-10, atol=2e-8), (name, actual, expected)
    else:
        assert actual == expected, (name, actual, expected)
    checks['scalars'] += 1

def csv_check(path, rows, kind):
    with path.open(newline='', encoding='utf-8') as f:
        actual = list(csv.DictReader(f))
    assert len(actual) == len(rows), (str(path), len(actual), len(rows))
    for i, (a, b) in enumerate(zip(actual, rows)):
        same(a, b, str(path.relative_to(OUT)) + '/' + str(i))
    checks[kind] += len(rows)

same(digest(DOC / 'protocol.json'), report['protocol_sha256'], 'protocol hash')
same(digest(ROOT / 'scripts/research_btc_spot_rr1.py'), report['code_sha256'], 'runner hash')
frozen = json.loads((DOC / 'freeze_manifest.json').read_text(encoding='utf-8'))
for relative, expected_hash in frozen['files'].items():
    same(digest(ROOT / relative), expected_hash, 'freeze/' + relative)
same(digest(manifest['source']), manifest['source_sha256'], 'source hash')
same(digest(OUT / 'btc_m1.npz'), manifest['cache_sha256'], 'cache hash')
cache = np.load(OUT / 'btc_m1.npz')
tm, px = cache['time'], cache['prices']
raw = np.memmap(manifest['source'], mode='r', dtype='<f8', offset=4,
                shape=(manifest['valid_count'], 6))
assert np.array_equal(tm, np.rint((raw[:, 0] - 25569) * 86400).astype('int64'))
assert np.array_equal(px, raw[:, [1, 3, 4, 2]])
assert np.all(np.diff(tm) > 0) and np.all(tm % 60 == 0)
assert np.isfinite(px).all() and np.all(px > 0)
assert np.all(px[:, 1] >= px[:, [0, 2, 3]].max(axis=1))
assert np.all(px[:, 2] <= px[:, [0, 1, 3]].min(axis=1))

def bars(seconds):
    bucket, first, count = np.unique(tm // seconds, return_index=True, return_counts=True)
    t, p = [], []
    for b, a, n in zip(bucket, first, count):
        finish = a + n
        if n != seconds // 60 or tm[a] != b * seconds or tm[finish-1] != (b+1)*seconds-60:
            continue
        block = px[a:finish]
        t.append(b * seconds)
        p.append([block[0, 0], max(block[:, 1]), min(block[:, 2]), block[-1, 3]])
    return np.asarray(t), np.asarray(p)

def smooth(values, length, alpha):
    out = np.full(len(values), np.nan)
    if len(values) >= length:
        current = float(sum(values[:length]) / length)
        out[length-1] = current
        for i in range(length, len(values)):
            current = current + alpha * (float(values[i]) - current)
            out[i] = current
    return out

ht, hp = bars(3600)
qt, qp = bars(14400)
e20 = smooth(hp[:, 3], 20, 2/21)
e50 = smooth(qp[:, 3], 50, 2/51)
e200 = smooth(qp[:, 3], 200, 2/201)
tr = np.empty(len(hp))
for i, (o, h, l, c) in enumerate(hp):
    prior = hp[i-1, 3] if i else c
    tr[i] = max(h-l, abs(h-prior), abs(l-prior))
atr = smooth(tr, 14, 1/14)
signals = []
for i in range(3, len(ht)):
    if not np.isfinite(e20[i-3:i+1]).all() or ht[i] - ht[i-3] != 3*3600:
        continue
    touched = any(hp[k, 2] <= e20[k] <= hp[k, 1] for k in range(i-3, i))
    if not touched or hp[i, 3] <= max(hp[i-3:i, 1]) or hp[i, 3] <= e20[i]:
        continue
    available = int(ht[i] + 3600)
    j = int(np.searchsorted(qt, available-14400, side='right')-1)
    higher = int(qt[j]+14400) if j >= 0 else 0
    trend = bool(j >= 199 and available-higher < 14400 and qp[j, 3] > e200[j]
                 and e50[j] > e200[j] and e50[j] > e50[j-3])
    signals.append(dict(signal_time=available, signal_bar=int(ht[i]), close=float(hp[i, 3]),
                        stop=float(min(hp[i-3:i+1, 2])-.1*atr[i]), atr14=float(atr[i]),
                        ema20=float(e20[i]), trend=trend, higher_available=higher))
csv_check(OUT/'signals.csv', signals, 'signals')

def stats(rows):
    values = [r['net_pnl'] for r in rows]
    profit = sum(x for x in values if x > 0)
    loss = -sum(x for x in values if x < 0)
    n = len(rows)
    return dict(trades=n, wins=sum(x > 0 for x in values),
                win_rate=sum(x > 0 for x in values)/n if n else 0., net_pnl=sum(values),
                gross_profit=profit, gross_loss=loss, profit_factor=profit/loss if loss else None,
                mean_pnl=sum(values)/n if n else 0.,
                mean_net_r=sum(r['net_r'] for r in rows)/n if n else 0.,
                forced_closes=sum(r['reason']=='period_end' for r in rows),
                gap_exposed=sum(r['gap_exposed'] for r in rows))

normal = protocol['cost_and_fill_model']['scenarios']['normal']

def reproduce(bounds, arm, cost):
    left, right = map(stamp, bounds)
    cut = (tm >= left) & (tm < right)
    t, p = tm[cut], px[cut]
    eq = np.full(len(t), 10000.)
    cash, free, previous_exit_hour = 10000., 0, -1
    rows, decisions = [], []
    fee, slip, spread = cost['fee'], cost['slippage'], cost['spread']
    for s in signals:
        when = s['signal_time']
        if not left <= when < right:
            continue
        d = dict(signal_time=when, allowed=False, reason='', arm=arm)
        decisions.append(d)
        if arm == 'trend' and not s['trend']:
            d['reason'] = 'higher_timeframe'
            continue
        a = int(np.searchsorted(t, when))
        if a == len(t) or t[a] != when:
            d['reason'] = 'missing_entry_minute'
            continue
        if a < free or when//3600 <= previous_exit_hour:
            d['reason'] = 'position_or_exit_hour'
            continue
        close, stop = s['close'], s['stop']
        expense = normal['spread'] + 2*close*(normal['fee']+normal['slippage'])
        ratio = expense / (close-stop) if close > stop else float('inf')
        if stop <= 0 or close <= stop or ratio > .15:
            d['reason'] = 'signal_cost_or_risk'
            continue
        planned_entry = (close+spread)*(1+slip)
        planned_exit = stop*(1-slip)
        planned_loss = planned_entry*(1+fee)-planned_exit*(1-fee)
        wanted = min(cash*.0025/planned_loss, cash/(planned_entry*(1+fee)))
        entry = (p[a, 0]+spread)*(1+slip)
        if entry <= stop:
            d['reason'] = 'invalid_bracket_at_fill'
            continue
        quantity = min(wanted, cash/(entry*(1+fee)))
        target = 2*entry-stop
        candidates = np.where((p[a:, 2] <= stop) | (p[a:, 1] >= target))[0]
        if len(candidates):
            b = int(a+candidates[0])
            if p[b, 0] <= stop:
                raw_exit, reason = float(p[b, 0]), 'stop_gap'
            elif p[b, 0] >= target:
                raw_exit, reason = target, 'target_gap'
            elif p[b, 2] <= stop:
                raw_exit, reason = stop, 'stop'
            else:
                raw_exit, reason = target, 'target'
        else:
            b, raw_exit, reason = len(t)-1, float(p[-1, 3]), 'period_end'
        exit_price = raw_exit*(1-slip)
        buy, sell = quantity*entry*fee, quantity*exit_price*fee
        net = quantity*(exit_price-entry)-buy-sell
        eq[free:a] = cash
        idle = cash-quantity*entry-buy
        eq[a:b+1] = idle+quantity*p[a:b+1, 3]*(1-slip)*(1-fee)
        before = cash
        cash += net
        eq[b] = cash
        free, previous_exit_hour = b+1, int(t[b]//3600)
        durations = np.diff(t[a:b+1])
        missing = durations[durations > 60]
        risk = quantity*(entry-stop)
        actual_loss = quantity*(entry*(1+fee)-stop*(1-slip)*(1-fee))
        row = dict(s, quantity_requested=wanted, estimated_entry=planned_entry,
                   estimated_loss_per_btc=planned_loss, estimated_cost_ratio=ratio,
                   entry_time=int(t[a]), exit_time=int(t[b]), entry=entry, target=target,
                   raw_exit=raw_exit, exit=exit_price, quantity=quantity, cash_capped=quantity < wanted,
                   buy_fee=buy, sell_fee=sell, gross_pnl=quantity*(exit_price-entry), net_pnl=net,
                   net_r=net/risk, initial_price_risk=risk, actual_stop_loss_with_cost=actual_loss,
                   actual_risk_fraction=actual_loss/before, cash_before=before, cash_after=cash,
                   reason=reason, gap_exposed=bool(len(missing)), holding_gap_count=len(missing),
                   holding_missing_minutes=int(sum(missing//60-1)),
                   signal_to_open_gap=float(p[a, 0]-close), entry_index=a, exit_index=b)
        rows.append(row)
        d.update(allowed=True, reason='filled')
    eq[free:] = cash
    peak = np.maximum.accumulate(np.r_[10000., eq])[1:]
    out = stats(rows)
    out.update(initial_cash=10000., final_cash=cash, return_pct=(cash/10000.-1)*100,
               max_drawdown_pct=float(max((peak-eq)/peak))*100,
               max_drawdown_basis='all observed M1 closes, liquidation-value equity',
               signals=len(decisions), holding_gap_count=sum(r['holding_gap_count'] for r in rows),
               holding_missing_minutes=sum(r['holding_missing_minutes'] for r in rows),
               no_gap_trades_descriptive=stats([r for r in rows if not r['gap_exposed']]),
               bracket_exits=stats([r for r in rows if r['reason']!='period_end']),
               period_end_exits=stats([r for r in rows if r['reason']=='period_end']))
    years = {}
    for year in range(int(bounds[0][:4]), int(str(np.datetime64(int(t[-1]), 's'))[:4])+1):
        begin, end = stamp(f'{year}-01-01'), stamp(f'{year+1}-01-01')
        a, b = np.searchsorted(t, [begin, end])
        selected = [r for r in rows if begin <= r['exit_time'] < end]
        prior = 10000. if a == 0 else eq[a-1]
        after = eq[b-1] if b > a else prior
        years[str(year)] = dict(stats(selected), mtm_change=float(after-prior))
    out['yearly_exit_year'] = years
    return rows, decisions, t, eq, out

independent = {}
for period, bounds in protocol['periods'].items():
    for arm in ['trend', 'baseline']:
        for scenario, cost in protocol['cost_and_fill_model']['scenarios'].items():
            key = '_'.join([period, arm, scenario])
            rows, decisions, t, eq, expected = reproduce(bounds, arm, cost)
            folder = OUT/key
            csv_check(folder/'trades.csv', rows, 'trades')
            csv_check(folder/'decisions.csv', decisions, 'decisions')
            indices = set(np.where(np.diff(t//3600) != 0)[0]) | {len(t)-1}
            indices |= {r[k] for r in rows for k in ['entry_index', 'exit_index']}
            csv_check(folder/'equity.csv', [dict(time=int(t[i]), equity=float(eq[i])) for i in sorted(indices)], 'equity')
            same(report['cases'][key], expected, key)
            independent[key] = expected
            print('VERIFIED', key, len(rows), flush=True)

gates = {}
for period in ['validation', 'final_confirmation']:
    n, s = independent[period+'_trend_normal'], independent[period+'_trend_stress']
    gates[period] = dict(trades_ge_100=n['trades']>=100, net_positive=n['net_pnl']>0,
                         pf_ge_1_1=n['profit_factor'] is not None and n['profit_factor']>=1.1,
                         dd_le_20pct=n['max_drawdown_pct']<=20, stress_net_positive=s['net_pnl']>0)
same(report['research_screen'], gates, 'screen')
same(report['research_screen_pass'], all(all(x.values()) for x in gates.values()), 'screen pass')
same(report['adoption_approved'], False, 'adoption')
print('AUDIT_JSON='+json.dumps(dict(status='VERIFIED_DESCRIPTIVE', counts=checks,
      m1=len(tm), h1=len(ht), h4=len(qt), protocol_sha256=report['protocol_sha256'],
      code_sha256=report['code_sha256'], results_sha256=digest(OUT/'results.json'))))
```

## 実行結果

再実行手順のコマンドを実行しexit0。開発runnerをimportせず別実装で全12ケースが一致した。通常とストレスの費用ゲート共通化、TPgap先着順の修正は本履歴の結果計算前に確定した。結果閲覧後の戦略・費用・基準変更はない。

```text
VERIFIED training_trend_normal 10
VERIFIED training_trend_stress 10
VERIFIED training_baseline_normal 31
VERIFIED training_baseline_stress 30
VERIFIED validation_trend_normal 70
VERIFIED validation_trend_stress 67
VERIFIED validation_baseline_normal 219
VERIFIED validation_baseline_stress 210
VERIFIED final_confirmation_trend_normal 57
VERIFIED final_confirmation_trend_stress 57
VERIFIED final_confirmation_baseline_normal 181
VERIFIED final_confirmation_baseline_stress 180
AUDIT_JSON={"status":"VERIFIED_DESCRIPTIVE","counts":{"signals":3770,"trades":1122,"decisions":14184,"equity":279049,"scalars":985811},"m1":4309797,"h1":65256,"h4":14877,"protocol_sha256":"10546232de83002c9bac9a6f2fca3394d7147558ebfdc27e6f53ef0d4f793003","code_sha256":"c70d85b607796a3d93f68281c59a72c2272ebdce4ef48ecd1cffacb46ae1940a","results_sha256":"5ce537f9bec77fc104fabba13f39595474e95f0d75755ce80e8f2ece23333f26"}
```

原履歴の4,309,797 M1とcacheを全件一致確認。独立集約は完全1h 65,256本/完全4h 14,877本。凍結7ファイルのSHA256も一致。numeric比較許容誤差は相対2e-10、絶対2e-8。判断文字列・bool・行数は完全一致。

保存equity 279,049行を比較し、DDは保存sampleに依存せず全観測M1から別計算。全取引のsignal/entry/exit/SL/TP/fee/quantity/現金/欠損フラグ、および全期間集計・exit年別損益/年別MTM変化・screenを照合した。

開発境界テストを監査担当が別途実行: `python -m pytest tests/test_btc_spot_rr1.py -q` → **15 passed / exit0**。確定4h境界、prefix不変、欠損、同M1両到達、既知TPgap、SLgap、費用、数量cash上限、実risk変動、期間末決済、同時間再入場を含む。

## 固定12ケースの結果

各ケースは資金10,000 USDから別々に開始する。以下の損益は往復費用控除後USD、勝率は純益>0の比率、DDは観測M1終値ベース。

|期間|条件|費用|件数|勝率|PF|純損益USD|最大DD|保有gap件数|
|---|---|---|---:|---:|---:|---:|---:|---:|
|2018–2020|主案|通常|10|20.00%|0.2446|-137.30|1.7416%|3|
|2018–2020|主案|stress|10|20.00%|0.2203|-142.88|1.7542%|3|
|2018–2020|4h条件なし|通常|31|35.48%|0.5356|-222.22|2.7808%|16|
|2018–2020|4h条件なし|stress|30|33.33%|0.4600|-258.63|3.0722%|15|
|2021–2023|主案|通常|70|44.29%|0.7059|-283.63|4.0724%|23|
|2021–2023|主案|stress|67|44.78%|0.6446|-324.14|4.3618%|23|
|2021–2023|4h条件なし|通常|219|43.84%|0.6946|-896.18|10.1200%|56|
|2021–2023|4h条件なし|stress|210|42.86%|0.5985|-1,135.01|12.3766%|55|
|2024–2026-10-06|主案|通常|57|59.65%|1.2165|125.11|1.1293%|10|
|2024–2026-10-06|主案|stress|57|57.89%|1.0334|19.25|1.2503%|10|
|2024–2026-10-06|4h条件なし|通常|181|53.04%|0.9566|-91.70|3.5007%|44|
|2024–2026-10-06|4h条件なし|stress|180|52.22%|0.8163|-383.44|5.4718%|43|

## 判定

2021–2023年は最低100件・純益正・PF1.1以上・stress純益正を満たさない。2024年以降も最低100件を満たさない。後期主案の黒字だけで全体合格にはしない。`research_screen_pass=false`、`adoption_approved=false`。結果を受けた再探索は実施していない。

細かな年別値・gap除外参考値・期間末決済の内訳は `agent_runs/btc_spot_rr1_20261007/results.json` に保存され、全項目を独立照合済み。gap除外参考集計は事後診断で、除外後の別戦略口座曲線ではない。
