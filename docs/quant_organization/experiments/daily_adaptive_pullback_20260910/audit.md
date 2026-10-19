# 独立検証: daily_adaptive_pullback_20260910

- 担当: quant_validator。編集責任はこのaudit.mdのみ。
- 現在判定: **不採用 / VERIFIED_REJECTED_TRAINING_ONLY**。全3候補を独立再現し、学習両費用で負の期待値と事前基準不通過を確認した。
- 入力: 今回hypothesis.md / protocol.json、第一daily_edge_reset_20260910の凍結コード・仕様・データ台帳と日足キャッシュ。
- 前実験の不採用結果は変更しない。今回はその学習成績を見て設計した追試であり、独立した未使用データ選抜とは呼ばない。

## 結果前レビュー

月初選抜は当月trading dateに属するraw最初時刻の全15通貨最小をcutoffとし、shadowのexit exposureがそれより厳密に前である取引だけを使う。日曜統合の場合cutoffは前月になり得るが、24/36/60か月の下限はtrading月初からの暦月減算である。時刻比較の混同がないか実装で確認する。

shadowは2010年からphase末まで連続し、actual採否がshadowの取引進行を変えない。shadowの研究上の末尾強制清算をrankingへ含めない。actualはphase開始flatで、期首より前に発生したentryへ途中参入しない。期末actualは研究清算を行う。選抜通貨から外れても既存保有は継続する。

月初rankingはmetadata＋0.4pipとcarry0.2による一つのscoreを両主費用ケースで共用する。採否は月次選択と入場時容量だけに依存し、将来exit損益・理由・期間を参照しないことを、別イベント実装で確認する。確定した出口から順次枠を解放し、日中exitは日末まで保守的に占有する。時刻が同じexitはentry前、entry同士はsymbol順。

最大5ポジション・構成通貨各3はgrossの件数上限である。口座通貨リスク、正味通貨数量、証拠金、相関損失を上限保証するものではない。等R日次MTMを確認し、実口座リターンとは区別する。

3候補の事前基準、学習から1候補選抜、fallbackなし、後半不合格で停止を固定。全期間既閲覧であり、第一学習結果から押戻り05を選んだ選択バイアスが残る。主費用0.2pip/暦日は実swapではない。利益が確認されても研究合格の範囲に限る。

## 実施結果

1. 第一の独立指標/取引状態実装で30 shadow JSON・1,412取引明細（二費用）を全件再現した。第一と同じpullback05の連続取引母集団を使っている。
2. 別entry/exitイベント列を作り、324月次score/選択（108月×3）、2,118全entry採否を一致確認。選抜は既確定exitのみ、採否は月次選択とその時点のactive構成だけで計算した。未来のexit損益や保有期間をentry判定の説明変数に使っていない。
3. actual 90 JSON・1,284取引明細・90日次MTM・6合算MTM/集計/ゲートが一致。両費用actualのentry集合が一致し、最大同時5・構成通貨各3を確認した。
4. 全3候補で中間時点以後のshadow exit/netRを撹乱し、その時点以前の月次score/選択・入場採否が不変であることを確認した。研究コードの対応する未来損益撹乱テストも通過。第一の別実装照合で指標/価格prefixも確認済み。
5. 研究実走exit0は研究担当から受領。独立再計算は最終 `INDEPENDENT_ADAPTIVE_REPLAY_OK` とプロセスexit0を直接確認。関連32テストを本担当も実走しexit0。最終resultsとtraining_results一致、8依存SHAと15日足NPZ SHA一致、selected空・後半成果物なしを確認した。

## 凍結と成果物

- 凍結UTC: `2026-09-10T00:51:05.941760+00:00`。
- 最終結果UTC: `2026-09-10T00:51:06.781355+00:00`。
- research_daily_adaptive_pullback.py SHA256: `708a6463c9eab80c7c80077327d7788f02d4488de948e948a641703462c050e8`。
- protocol.json SHA256: `730eeb3daaf27cb5704bf28295a8c4ca232a1f8ea9d8f9884e07aad8a1194ea7`。
- 全識別子: `agent_runs/daily_adaptive_pullback_20260910/completed/code_input_hashes.json`。
- 数値結果: 同ディレクトリの `results.json` / `training_results.json`、候補/期間/通貨/費用別JSONとequity.npz。
- 全月初score/選択: 各 `adaptiveXX__training__monthly.json`。
- 全採否・直前保有件数/構成通貨件数: 各 `adaptiveXX__training__admissions.json`。

## 不採用結果

学習2010–2018、往復固定1.8pips＋仮定0.2pip/暦日の主評価。Rは等初期リスク尺度で口座通貨金額ではない。

|候補|取引数|勝率%|PF|平均R|損益R|日次MTM DD R|利益/出場通貨|
|---|---:|---:|---:|---:|---:|---:|---:|
|全通貨pullback05 比較|706|40.23|1.0652|0.03642|25.7105|43.4796|9/15|
|adaptive24|214|36.45|0.8949|−0.06339|−13.5644|25.3571|7/15|
|adaptive36|216|36.57|0.9275|−0.04311|−9.3116|22.3400|5/14|
|adaptive60|212|36.79|0.9536|−0.02733|−5.7932|19.7448|6/14|

metadata＋0.4pips＋同保有費用では順にPF0.8940/0.9265/0.9525、損益−13.6979/−9.4487/−5.9380R。全3候補が両主費用でPF・正の期待値・利益通貨過半数・学習3区分利益を満たさない。adaptive24/36はDD20Rも超える。adaptive60がDDを満たすことは利益の証拠にならない。

|候補/区分|件数|PF|平均R|実現損益R|MTM増分R|期末含みR|
|---|---:|---:|---:|---:|---:|---:|
|24 / 2010–2012|29|0.4781|−0.40936|−11.8714|−11.8714|0|
|24 / 2013–2015|92|1.1747|0.09552|8.7881|8.6013|−0.1868|
|24 / 2016–2018|93|0.8129|−0.11270|−10.4811|−10.2943|0|
|36 / 2010–2012|29|0.4781|−0.40936|−11.8714|−11.8714|0|
|36 / 2013–2015|94|1.0187|0.01070|1.0056|3.2276|2.2220|
|36 / 2016–2018|93|1.0299|0.01671|1.5542|−0.6678|0|
|60 / 2010–2012|29|0.4781|−0.40936|−11.8714|−11.8714|0|
|60 / 2013–2015|97|1.0588|0.03221|3.1240|3.5348|0.4108|
|60 / 2016–2018|86|1.0604|0.03435|2.9542|2.5434|0|

全候補の初区分は29件と少なく大幅な赤字。36か月候補の最終学習区分は決済年帰属で正でもMTM増分では負になる。区分末含みを別表示して結論を都合よく変えていない。

|adaptive60 通貨|件数|PF|平均R|損益R|日次MTM DD R|
|---|---:|---:|---:|---:|---:|
|AUDUSD|1|0|−1.01817|−1.0182|1.4150|
|EURUSD|21|0.7043|−0.18256|−3.8337|6.9221|
|GBPUSD|10|2.4306|0.43661|4.3661|2.0076|
|NZDUSD|12|0.9268|−0.04604|−0.5525|4.5583|
|USDCAD|8|1.3413|0.21860|1.7488|3.4510|
|USDCHF|22|1.0229|0.01379|0.3034|8.8774|
|USDJPY|24|0.8771|−0.06766|−1.6238|6.2377|
|AUDJPY|20|0.4678|−0.38698|−7.7396|7.7396|
|CHFJPY|9|0|−0.97751|−8.7976|8.9553|
|EURCHF|22|1.2038|0.10636|2.3399|4.0883|
|EURGBP|0|—|0|0|0|
|EURJPY|14|1.9085|0.39781|5.5693|3.4308|
|GBPCHF|6|0.7606|−0.16544|−0.9926|4.4279|
|GBPJPY|35|1.5147|0.26420|9.2471|4.8256|
|NZDJPY|8|0.1328|−0.60124|−4.8100|5.8094|

24/36を含む全90通貨費用行はresults.rowsへ保存済みで全件照合した。GBPUSDのPF2.43は10件だけであり、こうした一部銘柄の小標本を採用根拠にしない。

パラメータ近傍24/36/60は全て主費用で赤字。保有0pipではPF0.9427/0.9773/1.0096、保有1pipでは0.7257/0.7527/0.7591。保有費用ゼロの最長窓だけの僅かな黒字を主評価に置き換えない。actual期末強制清算は全候補0件で、除外感度も主損益と一致。shadow強制清算はrankingから除外されている。

容量判断も独立一致。24か月候補は706機会中214採用/488月次非選択/3構成通貨枠/1総枠、36か月は216/487/2/1、60か月は212/490/4/0。未来の成績から良かったactualだけを抽出した研究ではなく、全不採用イベントも保存・検証している。それでも今回の過去実績選抜は正の期待値を再現しなかった。

## 再現コマンド・引継ぎ

研究再現は新規出力先を指定し既存completedへ上書きしない。

```powershell
$env:PYTHONPATH='src'
python -m scripts.research_daily_adaptive_pullback --phase training --output agent_runs/daily_adaptive_pullback_20260910/reproduction
python -m pytest tests/test_daily_edge_reset.py tests/test_daily_adaptive_pullback.py -q
```

独立検証（今回exit0、保存成果物読取のみ）:

```powershell
$env:PYTHONPATH='src'
@'
from pathlib import Path
s=Path('docs/quant_organization/experiments/daily_adaptive_pullback_20260910/audit.md').read_text(encoding='utf-8')
code=s.split('```python\n',1)[1].split('\n```',1)[0]
exec(compile(code,'independent_adaptive_audit','exec'))
'@ | python -
```

最終出力:

```json
{"status": "INDEPENDENT_ADAPTIVE_REPLAY_OK", "phase": "training", "selected": "", "shadow_trades": 1412, "actual_trades": 1284, "actual_artifacts": 90, "monthly_decisions": 324, "entry_admissions": 2118, "aggregate_checks": 6, "future_perturbation_checks": 3, "max_positions": 5, "max_constituent_positions": 3}
```

最初の独立実行はMarkdown中のコード抽出でquoted backtickを終端と誤認しSyntaxErrorとなった。抽出終端を改行付きfenceへ限定して修正し、同じ独立コードの再実行exit0を確認。研究コード・採用基準・取引結果の修正ではない。

未実装費用/制約: 実通貨別・方向別swap/三倍日、変動spread、実slippage、実ブローカー手数料、lot/証拠金/口座通貨換算、tick内順序・日中DD、配信TZ・TradingView日足同一性。元M1品質は第一データ担当証拠を継承し、本担当はキャッシュSHAと別計算を確認した。全期間既閲覧、第一学習結果を見た追試という制約を維持する。

次担当は研究責任者。引継ぎ可能範囲は再現済み不採用結果、候補選抜0、後半未実行。Pine移植へ渡す候補はない。修正が必要な実装不一致は現時点残っていない。編集はこのaudit.mdのみ。実注文なし。

実注文・口座接続・公開なし。

## 独立再現コード

第一auditに保存した独立実装から関数定義のみを読み込み、今回の取引を再計算する。研究側の選抜・約定関数は使わない。

```python
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import ast, hashlib, json, math, collections
import numpy as np

root=Path.cwd()
spec=root/'docs/quant_organization/experiments/daily_adaptive_pullback_20260910/protocol.json'
p=json.loads(spec.read_text(encoding='utf-8'))
out=root/'agent_runs/daily_adaptive_pullback_20260910/completed'
r=json.loads((out/'results.json').read_text(encoding='utf-8'))
basep=json.loads((root/p['base_protocol']).read_text(encoding='utf-8'))
old=(root/'docs/quant_organization/experiments/daily_edge_reset_20260910/audit.md').read_text(encoding='utf-8')
tree=ast.parse(old.split('```python\n',1)[1].split('```',1)[0])
independent={'np':np,'math':math,'datetime':datetime,'timezone':timezone,'p':basep,
             'ts':lambda s:int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())}
names={'close','derived','replay','stats','dd','summary','check'}
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name in names:
        exec(compile(ast.Module(body=[node],type_ignores=[]),'independent_base','exec'),independent)
close,derived,replay,stats,dd,summary,check=(independent[x] for x in ('close','derived','replay','stats','dd','summary','check'))
ts=independent['ts']
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
base_candidate=next(c for c in basep['search_space'] if c['id']=='pullback05')
manifest=json.loads((root/p['data_manifest']).read_text(encoding='utf-8'))
inputs={}
for m in manifest:
    path=root/basep['cached_daily_directory']/(m['symbol']+'_daily.npz')
    with np.load(path,allow_pickle=False) as z:
        d=SimpleNamespace(**{a:z[b].copy() for a,b in [('dates','dates'),('ohlc','ohlc'),('first','raw_first_timestamp'),('last','raw_last_timestamp')]})
    inputs[m['symbol']]=(d,derived(d.ohlc),m['pip'],m['metadata_spread_pips']+.4)

def prior_month(month,n):
    y,m=map(int,month.split('-')); serial=y*12+m-1-n
    return ts(f'{serial//12:04d}-{serial%12+1:02d}-01')

def month_name(label):
    return datetime.fromtimestamp(int(label),timezone.utc).strftime('%Y-%m')

def choose_months(shadow,phase,months):
    start,end=map(ts,p['periods'][phase]); cutoffs={}
    for symbol,(d,_,_,_) in inputs.items():
        for i in np.flatnonzero((d.dates>=start)&(d.dates<end)):
            month=month_name(d.dates[i]); raw=int(d.first[i])
            cutoffs[month]=min(cutoffs.get(month,raw),raw)
    decisions={}
    for month,cutoff in sorted(cutoffs.items()):
        lower=prior_month(month,months); scores=[]
        for symbol,trade_list in shadow.items():
            past=[t for t in trade_list if t['reason']!='period_boundary' and lower<=t['exit_exposure_timestamp']<cutoff]
            total=sum(t['net_r'] for t in past); n=len(past)
            scores.append(dict(symbol=symbol,trades=n,net_r=total,score=total/(n+10),eligible=n>=8 and total>0))
        eligible=sorted((s for s in scores if s['eligible']),key=lambda s:(-s['score'],s['symbol']))
        decisions[month]=dict(cutoff=cutoff,lower=lower,selected=[s['symbol'] for s in eligible[:5]],scores=scores)
    return decisions

def event_accept(shadow,monthly,phase):
    # Queue exits and entries as separate observable-time events. An exit only
    # releases an actually accepted position when its event is reached.
    start,end=map(ts,p['periods'][phase]); events=[]; catalog={}
    for symbol,trade_list in shadow.items():
        d=inputs[symbol][0]
        for t in trade_list:
            if not start<=d.dates[t['entry_index']]<end: continue
            key=(symbol,t['entry_index']); catalog[key]=t
            events.append((t['entry_timestamp'],1,symbol,t['entry_index']))
            events.append((t['exit_exposure_timestamp'],0,symbol,t['entry_index']))
    active=set(); decisions=[]; accepted=[]
    for stamp,kind,symbol,index in sorted(events):
        key=(symbol,index)
        if kind==0: active.discard(key); continue
        # Only the current event's entry label and active constituent names are
        # inspected here; future exit fields and future returns cannot rank it.
        month=month_name(inputs[symbol][0].dates[index])
        counts=collections.Counter(currency for s,_ in active for currency in (s[:3],s[3:]))
        before=sorted(active)
        reason='accepted'
        if symbol not in monthly[month]['selected']: reason='not_selected'
        elif len(active)>=5: reason='position_limit'
        elif counts[symbol[:3]]>=3 or counts[symbol[3:]]>=3: reason='currency_limit'
        if reason=='accepted': active.add(key); accepted.append(key)
        assert len(active)<=5
        counts_after=collections.Counter(currency for s,_ in active for currency in (s[:3],s[3:]))
        assert max(counts_after.values(),default=0)<=3
        decisions.append(dict(symbol=symbol,entry_index=index,entry_timestamp=stamp,month=month,
                              reason=reason,active_before=before,active_after=sorted(active)))
    return accepted,decisions

def equity_for(d,trades,phase,pip,fee):
    start,end=map(ts,p['periods'][phase]); curve=[]
    for i in np.flatnonzero((d.dates>=start)&(d.dates<end)):
        realized=sum(t['net_r'] for t in trades if t['exit_index']<=i)
        holding=[t for t in trades if t['entry_index']<=i<t['exit_index']]
        assert len(holding)<=1
        mark=0.
        for t in holding:
            days=math.ceil(max(0,int(d.last[i]+60)-t['entry_timestamp'])/86400)
            mark+=(t['direction']*(d.ohlc[i,3]-t['entry'])-(fee+.2*days)*pip)/t['risk']
        curve.append([int(d.dates[i]),realized,realized+mark])
    return np.asarray(curve)

def aggregate(items):
    dates=sorted(set(int(row[0]) for _,e,_ in items for row in e)); e=np.array([[day,0.,0.] for day in dates])
    for _,part,_ in items:
        index=0; prior=[0.,0.]
        for j,day in enumerate(dates):
            while index<len(part) and part[index,0]<=day: prior=part[index,1:]; index+=1
            e[j,1:]+=prior
    t=[trade for group,_,_ in items for trade in group]; s=summary(t,e)
    s['profitable_symbols']=sum(v['net_r']>0 for _,_,v in items)
    s['max_single_symbol_mtm_drawdown_r']=max(v['mtm_drawdown_r'] for _,_,v in items)
    subs=[]
    for lo,hi in p['acceptance_gates']['training_subperiods']:
        indices=[j for j,day in enumerate(dates) if ts(f'{lo}-01-01')<=day<ts(f'{hi+1}-01-01')]
        if indices:
            a,b=indices[0],indices[-1]; previous=e[a-1,2] if a else 0.
            subs.append(dict(years=[lo,hi],realized=stats(q['net_r'] for q in t if lo<=int(q['exit_date'][:4])<=hi),
                             mtm_net_r=e[b,2]-previous,end_open_r=e[b,2]-e[b,1]))
    s['training_subperiods']=subs
    return s,e

def gate(s,phase):
    g=p['acceptance_gates']; fail=[]
    pf=s['pf'] if s['pf'] is not None else math.inf if s['profit_r']>0 else 0.
    for no,label in [(s['trades']<g[phase]['minimum_trades'],'trades'),(pf<g[phase]['minimum_pf'],'pf'),
                     (s['average_net_r']<=0,'expectancy'),(s['mtm_drawdown_r']>g['maximum_daily_mtm_drawdown_r'],'mtm_dd'),
                     (s['active_symbols']<g['minimum_active_symbols'],'active_symbols'),
                     (s['profitable_symbols']*2<=s['active_symbols'],'profitable_majority')]:
        if no: fail.append(label)
    if phase=='training' and (len(s['training_subperiods'])!=3 or any(z['realized']['net_r']<=0 for z in s['training_subperiods'])): fail.append('training_subperiods')
    return dict(passed=not fail,failures=fail)

frozen=json.loads((out/'code_input_hashes.json').read_text(encoding='utf-8'))
for path,value in frozen['sha256'].items(): assert digest(root/path)==value
for symbol in inputs:
    assert digest(root/basep['cached_daily_directory']/(symbol+'_daily.npz'))==frozen['inputs'][symbol]['npz_sha256']
assert p==json.loads((out/'protocol.json').read_text(encoding='utf-8'))
phases=[phase for phase in ('training','validation','final_confirmation') if any(row['period']==phase for row in r['rows'])]
shadow_count=actual_count=artifact_count=monthly_count=admission_count=aggregate_count=prefix_count=0
max_positions=max_currency=0
reason_map={'not_selected':'monthly_not_selected','position_limit':'position_capacity','currency_limit':'currency_capacity','accepted':'accepted'}
for phase in phases:
    basep['periods'][phase]=['2010-01-01',p['periods'][phase][1]]
    shadows={}; baseline={case:[] for case in ('fixed_1p8','metadata_plus_0p4')}
    for case in baseline:
        shadows[case]={}
        for symbol,(d,f,pip,meta) in inputs.items():
            fee=1.8 if case=='fixed_1p8' else meta
            t,e=replay(d,f,base_candidate,phase,pip,fee)
            saved=json.loads((out/f'shadow__{phase}__{symbol}__{case}.json').read_text(encoding='utf-8'))['trades']
            check(t,saved,f'shadow/{phase}/{symbol}/{case}')
            shadows[case][symbol]=t; shadow_count+=len(t)
            baseline[case].append((t,e,summary(t,e)))
        if phase=='training': check(aggregate(baseline[case])[0],r['baseline_training'][case],'baseline/'+case)
    for c in p['search_space']:
        cid=c['id']
        if phase not in r['totals'].get(cid,{}): continue
        monthly=choose_months(shadows['metadata_plus_0p4'],phase,c['months'])
        saved_monthly=json.loads((out/f'{cid}__{phase}__monthly.json').read_text(encoding='utf-8'))
        assert set(monthly)==set(saved_monthly)
        for month,v in monthly.items():
            expected=saved_monthly[month]
            check({'cutoff':v['cutoff'],'lookback_lower':v['lower'],'selected':v['selected'],'stats':v['scores']},expected,cid+'/'+month)
            for stat in expected['stats']:
                t=[q for q in shadows['metadata_plus_0p4'][stat['symbol']] if q['reason']!='period_boundary' and v['lower']<=q['exit_exposure_timestamp']<v['cutoff']]
                assert stat['last_exit_exposure']==max([q['exit_exposure_timestamp'] for q in t],default=0)
            monthly_count+=1
        accepted,admissions=event_accept(shadows['metadata_plus_0p4'],monthly,phase)
        saved_logs=json.loads((out/f'{cid}__{phase}__admissions.json').read_text(encoding='utf-8'))
        assert len(admissions)==len(saved_logs)
        idmap={(symbol,t['entry_index']):f'{symbol}:{i}' for symbol,trades in shadows['metadata_plus_0p4'].items() for i,t in enumerate(trades)}
        for log,saved in zip(admissions,saved_logs):
            counts=collections.Counter(cur for s,_ in log['active_before'] for cur in (s[:3],s[3:]))
            expected=dict(trade_id=idmap[(log['symbol'],log['entry_index'])],entry_timestamp=log['entry_timestamp'],
                          entry_month=log['month'],symbol=log['symbol'],monthly_cutoff=monthly[log['month']]['cutoff'],
                          positions_before=len(log['active_before']),constituent_counts_before=dict(sorted(counts.items())),reason=reason_map[log['reason']])
            check(expected,saved,cid+'/admission')
            assert expected['monthly_cutoff']<=log['entry_timestamp']
            max_positions=max(max_positions,len(log['active_after']))
            max_currency=max(max_currency,max(collections.Counter(cur for s,_ in log['active_after'] for cur in (s[:3],s[3:])).values(),default=0))
            admission_count+=1
        # A future-return or future-exit rewrite must not alter earlier choices or admissions.
        horizon=sorted(v['cutoff'] for v in monthly.values())[len(monthly)//2]
        altered={symbol:[{**t,'net_r':1e6,'exit_exposure_timestamp':t['exit_exposure_timestamp']+1234567} if t['exit_exposure_timestamp']>=horizon else dict(t) for t in trades] for symbol,trades in shadows['metadata_plus_0p4'].items()}
        future_monthly=choose_months(altered,phase,c['months'])
        for month,v in monthly.items():
            if v['cutoff']<=horizon: check(v,future_monthly[month],cid+'/future_choice')
        _,future_admissions=event_accept(altered,monthly,phase)
        assert [x for x in admissions if x['entry_timestamp']<horizon]==[x for x in future_admissions if x['entry_timestamp']<horizon],cid+'/future_admission'
        prefix_count+=1
        for case,shadow in shadows.items():
            selected_items=[]
            for symbol,(d,_,pip,meta) in inputs.items():
                selected=[]
                for i,t in enumerate(shadow[symbol]):
                    if (symbol,t['entry_index']) in accepted:
                        selected.append({**t,'symbol':symbol,'shadow_trade_id':f'{symbol}:{i}'})
                fee=1.8 if case=='fixed_1p8' else meta
                eq=equity_for(d,selected,phase,pip,fee); s=summary(selected,eq)
                filename=f'{cid}__{phase}__{symbol}__{case}'
                actual=json.loads((out/(filename+'.json')).read_text(encoding='utf-8'))
                check(selected,actual['trades'],filename+'/trades'); check(s,actual['summary'],filename+'/summary')
                row=next(row for row in r['rows'] if row['artifact']==filename+'.json'); check(s,row,filename+'/row')
                with np.load(out/(filename+'_equity.npz'),allow_pickle=False) as z: close(eq,z['equity'],filename+'/equity')
                artifact_count+=1; actual_count+=len(selected); selected_items.append((selected,eq,s))
            total,eq=aggregate(selected_items)
            total['active_symbols']=sum(s['trades']>0 for _,_,s in selected_items)
            total['admission_counts']=dict(collections.Counter(reason_map[log['reason']] for log in admissions))
            check(total,r['totals'][cid][phase][case],cid+'/'+phase+'/'+case)
            check(gate(total,phase),r['decisions'][cid][phase][case],cid+'/gate')
            with np.load(out/f'{cid}__{phase}__{case}_aggregate_equity.npz',allow_pickle=False) as z: close(eq,z['equity'],cid+'/aggregate')
            aggregate_count+=1

passing=[c['id'] for c in p['search_space'] if all(v['passed'] for v in r['decisions'][c['id']]['training'].values())]
def rank(cid):
    vals=list(r['totals'][cid]['training'].values())
    return (-min(v['pf'] if v['pf'] is not None else math.inf for v in vals),-min(v['average_net_r'] for v in vals),max(v['mtm_drawdown_r'] for v in vals),cid)
selected=sorted(passing,key=rank)[0] if passing else ''
assert selected==r['selected']
selection=json.loads((out/'selection_before_validation.json').read_text(encoding='utf-8'))
assert selection['selected']==selected and selection['passing_training']==passing and selection['protocol_sha256']==digest(spec)
for row in r['rows']:
    if row['period']!='training': assert row['candidate']==selected
    if row['period']=='final_confirmation': assert all(v['passed'] for v in r['decisions'][selected]['validation'].values())
if not selected:
    assert r['phase']=='training'
    assert not list(out.glob('*__validation__*')) and not list(out.glob('*__final_confirmation__*'))
assert r==json.loads((out/(r['phase']+'_results.json')).read_text(encoding='utf-8'))
for path,value in frozen['sha256'].items(): assert digest(root/path)==value
print(json.dumps(dict(status='INDEPENDENT_ADAPTIVE_REPLAY_OK',phase=r['phase'],selected=selected,
                     shadow_trades=shadow_count,actual_trades=actual_count,actual_artifacts=artifact_count,
                     monthly_decisions=monthly_count,entry_admissions=admission_count,aggregate_checks=aggregate_count,
                     future_perturbation_checks=prefix_count,max_positions=max_positions,max_constituent_positions=max_currency)))
```
