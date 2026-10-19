# 独立検証: daily_edge_reset_20260910

- 担当: quant_validator。編集責任はこの audit.md のみ。
- 現在判定: **不採用 / VERIFIED_REJECTED_TRAINING_ONLY**。研究結果の再現と事前基準不通過を独立に確認した。勝てるアルゴリズムの確立を示す結果ではない。
- 入力: 同実験 hypothesis.md / protocol.json / data_inventory.md、旧実験 completed の日足キャッシュ・data_manifest.json。
- 研究開発者とは分離して検証する。採用基準・戦略コード・元履歴は変更しない。

## 結果前仕様レビュー

2026-09-10、結果生成前の SPEC_FROZEN を読了。10ルール（採用対象9＋比較1）、15通貨、期間、共通250本ウォームアップ、2主コスト、0.2 pip/暦日の保有費用、学習選抜1候補、後続不合格で停止・fallbackなしが記載されている。実装パスだけでは凍結コード識別子として不足するため、結果生成前のSHA記録を研究担当へ要求した。

未来参照対策として、当日除外チャネル・確定終値での判断・次観測始値約定・追尾SL翌日有効が仕様化されている。上位足・未来ピボットは使用しない。同足SL/TPはSL優先、SLギャップは始値、TP上方ギャップはTP価格に制限する。予定翌始値決済にもSLギャップを先行させる。これらは仕様上の確認であり、実装確認完了を意味しない。

初期2ATRの価格リスクでR正規化し、通貨をまたぐR加算を研究尺度とする。口座通貨の金額損益、資金制約、複利、実ロット数量は実装対象外。15通貨は共通基軸通貨を含み相関するため、15個の独立標本とは扱えない。日付整列した合算日次MTM DDを確認予定。日中最大DDや証拠金余力を証明する尺度ではない。

学習3区分ゲートは決済年別realized損益を基準にしている。区分境界での含み損益が決済年へ移る影響を確認するため、区分別MTM増分とrealizedの両方の診断出力を依頼した。期間末強制清算は主損益へ含み、除外感度も検証する。

0.2 pip/暦日の費用は仮定であり、実際の方向別・通貨別スワップや三倍日を再現しない。0/1 pip感度、実保有暦日、日中出口の保有費用計算を確認する。固定spread・往復0.4 pip slippage仮定の有無と控除単位も照合する。保存metadata手数料ゼロは実ブローカー費用ゼロの証拠ではない。

学習・検証・最終確認の区分は固定されているが全期間既閲覧。真の未使用holdoutではない。候補数は今回10に限定されても、過去の研究を含む探索履歴は消えない。合格した場合も、その制約下での研究合格として扱う。

## 実施した証拠確認

1. コード/仕様/入力ハッシュを実行前後照合。研究実走exit0は研究担当から受領し、最終results.jsonとtraining_results.json、選抜前保存ファイルの存在・内容を確認。独立実行はsession 89511の最終exit0を直接確認。
2. 別状態実装で300通貨費用JSON、11,490取引明細、300日次MTM配列、20合算配列/集計/判定が一致。45指標prefix、600約定/MTM prefixが一致。
3. 期間別件数・コスト後PF・期待値・DD・区分別realized/含み・選抜0を再計算。後半成果物なしを確認した。全15通貨・10ルール・二費用の学習結果のみ。
4. 19挙動テストを本担当も実走しexit0。ギャップ、同足両到達、SL優先、追尾翌日、次始値、warmup、保有暦日、費用、当日再発注抑止、MTMゼロ初期資産を検査するテスト内容を読了。
5. 下記結果・不採用理由・未実装費用と再現コマンドを引き渡す。戦略・基準の変更はなし。

## 凍結識別子と実行確認

- 凍結UTC: `2026-09-10T00:42:38.512706+00:00`。
- 最終結果UTC: `2026-09-10T00:42:41.597905+00:00`。
- research_daily_edge_reset.py SHA256: `37f1d47e7f7279648d9a4a9aa45a93e81db20135cb45cc3a92a663dc6f052dd5`。
- protocol.json SHA256: `248691baace75b028223554af72b09e300e7565282e3f84ba00e02d82e8ce470`。
- 全5依存ファイルSHAと15キャッシュSHAは `agent_runs/daily_edge_reset_20260910/completed/code_input_hashes.json` を参照。現在値一致を確認。
- 結果前レビューで、追尾最高/最低closeの初期値へentry始値を混ぜる問題を指摘。研究担当が初回生存closeで初期化するよう凍結前に修正した。独立側は仕様どおりcloseだけで再計算し一致した。

## 結果と不採用理由

全て学習2010–2018、往復1.8pips＋仮定0.2pip/暦日、等初期R尺度。実口座金額の合算ではない。

|候補|件数|PF|平均R|損益R|日次MTM DD R|利益通貨数|
|---|---:|---:|---:|---:|---:|---:|
|sma200_cross 比較|577|0.8853|−0.03620|−20.8865|34.7647|5|
|trend20|1,079|0.8077|−0.10165|−109.6759|128.4900|3|
|trend55|603|0.8830|−0.06623|−39.9366|61.4729|4|
|trend100|441|0.8166|−0.11075|−48.8408|62.3886|5|
|pullback05|706|1.0652|0.03642|25.7105|43.4796|9|
|pullback10|616|1.0300|0.01673|10.3075|49.1342|7|
|pullback15|478|1.0128|0.00715|3.4196|51.7203|8|
|range15|553|0.8834|−0.03913|−21.6371|24.9810|5|
|range20|414|0.7835|−0.08584|−35.5371|39.2432|7|
|range25|278|0.7037|−0.13273|−36.8986|41.5956|5|

9採用候補は全て両主費用のPF1.10と利益通貨10/15を満たさない。押戻り3近傍は総損益こそ正だが、DD40Rと学習3区分の利益条件も不通過。pullback05は単独通貨DD20Rにも不通過（USDCHF 20.3552R）。最高候補の勝率は40.23%であり、母数の少ない高勝率による採用は行っていない。

pullback05のmetadata＋0.4pips費用でも706件/PF1.0645/平均0.03603R/25.4399R/DD43.5393R/利益9通貨。1pip/暦日へ増額すると固定費用PF0.8570/−62.4728R、0pipならPF1.1242/47.7563R。利益が仮定保有費用に敏感である。費用1pip感度では全候補PF1未満。

|pullback05 学習区分|件数|PF|平均R|実現損益R|MTM増分R|区分末含みR|
|---|---:|---:|---:|---:|---:|---:|
|2010–2012|188|1.0397|0.02353|4.4236|6.4500|2.0264|
|2013–2015|261|1.1994|0.10485|27.3671|28.8305|3.4898|
|2016–2018|257|0.9583|−0.02366|−6.0802|−9.5701|0|

後半学習の赤字は区分境界含みを含めても解消しない。2013–2015など特定区分の利益を全期間の頑健性と読み替えない。学習比較用baselineでは決済年別で2013–2015/2016–2018が正でもMTM増分はそれぞれ−8.501/−2.139Rであり、含み確認の必要性を実データでも確認した。

|pullback05 通貨|件数|PF|平均R|損益R|日次MTM DD R|
|---|---:|---:|---:|---:|---:|
|AUDUSD|51|0.7979|−0.12708|−6.4812|11.7248|
|EURUSD|44|0.9901|−0.00526|−0.2312|11.8571|
|GBPUSD|46|1.3754|0.18581|8.5472|10.6242|
|NZDUSD|41|1.1317|0.07512|3.0798|8.9577|
|USDCAD|50|0.9855|−0.00829|−0.4147|12.0626|
|USDCHF|46|0.8575|−0.08997|−4.1388|20.3552|
|USDJPY|50|1.0533|0.02864|1.4319|9.7130|
|AUDJPY|50|1.1325|0.07819|3.9095|8.0297|
|CHFJPY|47|1.1090|0.06298|2.9601|8.5426|
|EURCHF|42|1.2106|0.10522|4.4191|7.9392|
|EURGBP|48|0.5275|−0.31416|−15.0799|15.1704|
|EURJPY|50|1.4214|0.21145|10.5727|6.7924|
|GBPCHF|49|1.0603|0.03411|1.6713|9.7339|
|GBPJPY|46|1.7594|0.35377|16.2732|4.1013|
|NZDJPY|46|0.9670|−0.01757|−0.8083|7.2063|

全候補・全費用・全通貨の数値は results.json の rows、取引は同ディレクトリの候補/期間/通貨/費用別JSONへ保存済みで、全300行を独立照合した。上表の利益通貨のみを事後選択して推奨しない。

境界強制清算は全11,490明細中84件（二費用を重複計数）。pullback05は706件中2件で、除外後も704件/PF1.0626/24.6502R、採用根拠は改善しない。実明細ではSLギャップ140件、TPギャップ上限4件を照合、同足SL/TP両到達は0件で該当順序は合成テストで確認。全候補最長保有155暦日、最悪取引−1.8044R。初期SLは損失上限1Rを保証しない。

選抜前ファイル passing_training=[] / selected=""、results status=`REJECTED_BY_FROZEN_GATES`。validation/finalの成果物なしを確認。後続期間・Pine移植へ渡せる候補は0。既閲覧履歴の有限研究として不採用を保存して終了する。

## 再現コマンドと引継ぎ

研究コマンド（既存 completed を上書きしないので再実行時は新規の専用出力先を指定）:

```powershell
$env:PYTHONPATH='src'
python -m scripts.research_daily_edge_reset --phase training --output agent_runs/daily_edge_reset_20260910/reproduction
python -m pytest tests/test_daily_edge_reset.py -q
```

独立検証コマンド（保存成果物を読取専用で照合、今回実行exit0）:

```powershell
$env:PYTHONPATH='src'
@'
from pathlib import Path
s=Path('docs/quant_organization/experiments/daily_edge_reset_20260910/audit.md').read_text(encoding='utf-8')
code=s.split('```python\n',1)[1].split('```',1)[0]
exec(compile(code,'independent_audit','exec'))
'@ | python -
```

最終標準出力:

```json
{"status": "INDEPENDENT_REPLAY_OK", "phase": "training", "selected": "", "symbol_case_artifacts": 300, "trades": 11490, "feature_prefix_checks": 45, "replay_prefix_checks": 600, "aggregates": 20}
```

未実装費用/制約は変動spread、実slippage、実ブローカー手数料、方向別通貨別swap・三倍日、数量/証拠金/口座通貨換算、tick内順序・日中DD、配信時間帯/TradingView日足一致。データ品質の原M1再集約は今回データ担当に依存し、本担当はキャッシュSHAと時刻可用性・全値計算を確認した。成功確率や実運用収益を保証しない。

次担当は研究責任者。引渡し可能なのは再現済み不採用結果と上記限界。修正すべき実装不一致は現時点残っていない。新仮説を別実験で研究する場合も、この履歴を未閲覧へ戻せない。独立検証の編集ファイルはこのaudit.mdのみ、実注文なし。

実注文・口座接続・外部公開: なし。

## 独立再現プログラム（読取専用）

研究側のシグナル・約定・費用・集計関数は呼ばず、別の状態変数で再計算した。以下は今回exit0を確認した再現コード。

```python
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib, json, math
import numpy as np

root = Path.cwd()
out = root / 'agent_runs/daily_edge_reset_20260910/completed'
spec = root / 'docs/quant_organization/experiments/daily_edge_reset_20260910/protocol.json'
p = json.loads(spec.read_text(encoding='utf-8'))
result = json.loads((out/'results.json').read_text(encoding='utf-8'))
frozen = json.loads((out/'code_input_hashes.json').read_text(encoding='utf-8'))
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for path, expected in frozen['sha256'].items():
    assert digest(root/path) == expected, ('frozen drift', path)
assert p == json.loads((out/'protocol.json').read_text(encoding='utf-8'))
ts = lambda text: int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())
year = lambda stamp: datetime.fromtimestamp(int(stamp), timezone.utc).year

def close(a, b, context=''):
    assert np.allclose(a, b, rtol=1e-9, atol=1e-8, equal_nan=True), context

def derived(x):
    n = len(x); c=x[:,3]
    tr=[]
    for i,(o,h,l,z) in enumerate(x):
        tr.append(h-l if i==0 else max(h-l,abs(h-c[i-1]),abs(l-c[i-1])))
    atr=np.full(n,np.nan)
    for i in range(19,n):
        atr[i]=sum(tr[:20])/20 if i==19 else (atr[i-1]*19+tr[i])/20
    f={'atr':atr}
    for w in (20,100,200):
        a=np.full(n,np.nan)
        for i in range(w-1,n): a[i]=sum(c[i-w+1:i+1])/w
        f['sma'+str(w)]=a
    for w in (10,20,50,55,100):
        a=np.full(n,np.nan); b=a.copy()
        for i in range(w,n):
            a[i]=max(x[i-w:i,1]); b[i]=min(x[i-w:i,2])
        f['high'+str(w)]=a; f['low'+str(w)]=b
    return f

def replay(d,f,c,period,pip,fee,cutoff=None):
    start,end=map(ts,p['periods'][period])
    a,b=map(int,np.searchsorted(d.dates,[start,end]))
    if cutoff is not None: b=min(b,cutoff)
    x=d.ohlc; daily=[]; done=[]; booked=0.; entry_i=None; order=None; leave=''
    for i in range(a,b):
        gone=False; op,hi,lo,z=x[i]
        if order is not None:
            sig,side=order; order=None; entry_i=i; entry=op; risk=2*f['atr'][sig]
            stop=entry-side*risk; target=entry+side*3*risk if c['family']=='pullback' else None
            extrema=None; leave=''
            assert d.last[sig]+60<=d.first[i]
        if entry_i is not None:
            reason=''; price=None; instant=False
            if (side==1 and op<=stop) or (side==-1 and op>=stop):
                price=op; reason='stop_gap'; instant=True
            elif leave:
                price=op; reason=leave; instant=True
            elif target is not None and side*(op-target)>=0:
                price=target; reason='target_gap_capped'; instant=True
            else:
                hit_stop=lo<=stop if side==1 else hi>=stop
                hit_target=target is not None and (hi>=target if side==1 else lo<=target)
                if hit_stop: price=stop; reason='both_stop_first' if hit_target else 'stop'
                elif hit_target: price=target; reason='target'
                elif i==b-1: price=z; reason='period_boundary'
            if price is not None:
                end_ts=int(d.first[i] if instant else d.last[i]+60)
                days=math.ceil(max(0,end_ts-int(d.first[entry_i]))/86400)
                gross=side*(price-entry)/risk; fee_r=fee*pip/risk; carry_r=.2*days*pip/risk
                t=dict(signal_index=sig,entry_index=entry_i,exit_index=i,direction=side,
                       signal_timestamp=int(d.last[sig]+60),entry_timestamp=int(d.first[entry_i]),
                       entry=entry,risk=risk,initial_stop=entry-side*risk,target=target,
                       exit_exposure_timestamp=end_ts,exit_price=price,reason=reason,
                       exit_date=datetime.fromtimestamp(int(d.dates[i]),timezone.utc).replace(tzinfo=None).isoformat(),
                       holding_bars=i-entry_i+1,carry_days=days,gross_r=gross,fee_r=fee_r,
                       carry_r=carry_r,net_r=gross-fee_r-carry_r,risk_pips=risk/pip,
                       net_zero_carry_r=gross-fee_r,net_one_carry_r=gross-fee_r-days*pip/risk)
                done.append(t); booked+=t['net_r']; entry_i=None; gone=True
        mark=0.
        if entry_i is not None:
            days=math.ceil(max(0,int(d.last[i]+60)-int(d.first[entry_i]))/86400)
            mark=(side*(z-entry)-(fee+.2*days)*pip)/risk
            leave=''
            if i-entry_i+1>=c['holding']: leave='holding_limit'
            elif c['family']=='range' and side*(z-f['sma20'][i])>=0: leave='mean_recovered'
            elif c['family']=='baseline' and side*(z-f['sma200'][i])<0: leave='opposite_sma'
            elif c['family']=='trend':
                channel=f[('low' if side==1 else 'high')+str(c['exit_window'])][i]
                if side*(z-channel)<0: leave='opposite_channel'
            if c['family'] in ('trend','baseline'):
                extrema=z if extrema is None else (max(extrema,z) if side==1 else min(extrema,z))
                trail=extrema-side*3*f['atr'][i]
                stop=max(stop,trail) if side==1 else min(stop,trail)
        daily.append([int(d.dates[i]),booked,booked+mark])
        if entry_i is None and not gone and i>=249 and i<b-1 and f['atr'][i]>0:
            k=c['parameter']; fam=c['family']; side=0; prev=x[i-1,3]
            if fam=='trend':
                if z>f['high'+str(int(k))][i]: side=1
                elif z<f['low'+str(int(k))][i]: side=-1
            elif fam=='baseline':
                if prev<=f['sma200'][i-1] and z>f['sma200'][i]: side=1
                elif prev>=f['sma200'][i-1] and z<f['sma200'][i]: side=-1
            else:
                buy=prev<=f['sma20'][i-1]-k*f['atr'][i-1] and z>f['sma20'][i]-k*f['atr'][i]
                sell=prev>=f['sma20'][i-1]+k*f['atr'][i-1] and z<f['sma20'][i]+k*f['atr'][i]
                if fam=='pullback':
                    buy=buy and z>f['sma200'][i] and f['sma200'][i]>f['sma200'][i-20]
                    sell=sell and z<f['sma200'][i] and f['sma200'][i]<f['sma200'][i-20]
                elif abs(f['sma100'][i]-f['sma100'][i-20])>=.5*f['atr'][i]: buy=sell=False
                if buy!=sell: side=1 if buy else -1
            if side: order=(i,side)
    return done,np.asarray(daily)

def stats(values):
    values=list(values); pos=sum(v for v in values if v>0); neg=-sum(v for v in values if v<0)
    return dict(trades=len(values),win_rate_pct=100*sum(v>0 for v in values)/len(values) if values else 0.,
                pf=pos/neg if neg else None,profit_r=pos,loss_r=neg,net_r=sum(values),
                average_net_r=sum(values)/len(values) if values else 0.)

def dd(curve):
    peak=0.; worst=0.
    for value in curve: peak=max(peak,value); worst=max(worst,peak-value)
    return worst

def summary(t,e):
    v=stats(q['net_r'] for q in t)
    for key,field in [('gross','gross_r'),('zero_carry','net_zero_carry_r'),('one_pip_carry','net_one_carry_r')]:
        v[key]=stats(q[field] for q in t)
    v['without_boundary']=stats(q['net_r'] for q in t if q['reason']!='period_boundary')
    v.update(mtm_drawdown_r=dd(e[:,2]),max_holding_bars=max([q['holding_bars'] for q in t],default=0),
             mean_carry_days=sum(q['carry_days'] for q in t)/len(t) if t else 0.,
             boundary_trades=sum(q['reason']=='period_boundary' for q in t))
    return v

def check(actual,expected,context):
    if isinstance(actual,dict):
        for k,v in actual.items(): check(v,expected[k],context+'/'+k)
    elif isinstance(actual,list):
        assert len(actual)==len(expected),context
        for i,(a,b) in enumerate(zip(actual,expected)): check(a,b,context+'/'+str(i))
    elif actual is None or isinstance(actual,str): assert actual==expected,(context,actual,expected)
    else: close(actual,expected,context)

manifest=json.loads((root/p['data_manifest']).read_text(encoding='utf-8'))
inputs={}; feature_checks=0
for m in manifest:
    symbol=m['symbol']; path=root/p['cached_daily_directory']/(symbol+'_daily.npz')
    assert digest(path)==frozen['inputs'][symbol]['npz_sha256']
    with np.load(path,allow_pickle=False) as z:
        d=SimpleNamespace(**{a:z[b].copy() for a,b in [('dates','dates'),('ohlc','ohlc'),('first','raw_first_timestamp'),('last','raw_last_timestamp')]})
    f=derived(d.ohlc)
    for length in (250,1000,2000):
        prefix=derived(d.ohlc[:length])
        for k in f: close(prefix[k],f[k][:length],(symbol,k,length))
        feature_checks+=1
    inputs[symbol]=(d,f,m['pip'],m['metadata_spread_pips']+.4)

rows=0; trades_checked=0; prefix_checks=0; bundles={}
for row in result['rows']:
    c=next(c for c in p['search_space'] if c['id']==row['candidate'])
    d,f,pip,metadata=inputs[row['symbol']]; fee=1.8 if row['case']=='fixed_1p8' else metadata
    t,e=replay(d,f,c,row['period'],pip,fee)
    saved=json.loads((out/row['artifact']).read_text(encoding='utf-8'))
    check(t,saved['trades'],row['artifact']+'/trades')
    s=summary(t,e); check(s,saved['summary'],row['artifact']+'/summary'); check(s,row,row['artifact']+'/row')
    with np.load(out/(Path(row['artifact']).stem+'_equity.npz'),allow_pickle=False) as z: close(e,z['equity'],row['artifact']+'/equity')
    a,b=map(int,np.searchsorted(d.dates,list(map(ts,p['periods'][row['period']]))))
    for cut in (a+(b-a)//3,a+2*(b-a)//3):
        pt,pe=replay(d,f,c,row['period'],pip,fee,cut)
        check([q for q in pt if q['exit_index']<cut-1],[q for q in t if q['exit_index']<cut-1],row['artifact']+'/prefix')
        close(pe[:-1],e[:len(pe)-1],row['artifact']+'/prefix_equity'); prefix_checks+=1
    bundles.setdefault((c['id'],row['period'],row['case']),[]).append((t,e,s))
    rows+=1; trades_checked+=len(t)

def failures(s,period):
    g=p['acceptance_gates']; k=g[period]; reasons=[]
    for test,label in [(s['trades']<k['minimum_trades'],'trades'),
                       ((s['pf'] if s['pf'] is not None else (math.inf if s['profit_r']>0 else 0.))<k['minimum_pf'],'pf'),
                       (s['average_net_r']<=0,'expectancy'),(s['profitable_symbols']<k['minimum_profitable_symbols'],'symbol_breadth'),
                       (s['mtm_drawdown_r']>g['maximum_aggregate_daily_mtm_drawdown_r'],'mtm_dd'),
                       (s['max_single_symbol_mtm_drawdown_r']>g['maximum_single_symbol_daily_mtm_drawdown_r'],'single_symbol_mtm_dd')]:
        if test: reasons.append(label)
    if period=='training' and (len(s['training_subperiods'])!=3 or any(z['realized']['net_r']<=0 for z in s['training_subperiods'])): reasons.append('training_subperiods')
    return dict(passed=not reasons,failures=reasons)

for (cid,period,case),items in bundles.items():
    days=sorted(set(int(row[0]) for _,e,_ in items for row in e)); marks={day:[0.,0.] for day in days}
    for _,e,_ in items:
        j=0; previous=[0.,0.]
        for day in days:
            while j<len(e) and e[j,0]<=day: previous=e[j,1:]; j+=1
            marks[day][0]+=previous[0]; marks[day][1]+=previous[1]
    e=np.array([[day,*marks[day]] for day in days]); t=[q for group,_,_ in items for q in group]
    s=summary(t,e); s['profitable_symbols']=sum(v['net_r']>0 for _,_,v in items)
    s['max_single_symbol_mtm_drawdown_r']=max(v['mtm_drawdown_r'] for _,_,v in items)
    subs=[]
    for lo,hi in p['acceptance_gates']['training_subperiods']:
        indices=[j for j,day in enumerate(days) if lo<=year(day)<=hi]
        if indices:
            a,b=indices[0],indices[-1]; base=e[a-1,2] if a else 0.
            selected=[q['net_r'] for q in t if lo<=int(q['exit_date'][:4])<=hi]
            subs.append(dict(years=[lo,hi],realized=stats(selected),mtm_net_r=e[b,2]-base,end_open_r=e[b,2]-e[b,1]))
    s['training_subperiods']=subs
    check(s,result['totals'][cid][period][case],cid+'/'+period+'/'+case)
    check(failures(s,period),result['decisions'][cid][period][case],cid+'/gate')
    with np.load(out/f'{cid}__{period}__{case}_aggregate_equity.npz',allow_pickle=False) as z: close(e,z['equity'],cid+'/aggregate')

passing=[c['id'] for c in p['search_space'] if c['eligible'] and all(x['passed'] for x in result['decisions'][c['id']]['training'].values())]
def rank(cid):
    s=list(result['totals'][cid]['training'].values())
    return (-min(x['pf'] if x['pf'] is not None else math.inf for x in s),-min(x['average_net_r'] for x in s),max(x['mtm_drawdown_r'] for x in s),cid)
selected=sorted(passing,key=rank)[0] if passing else ''
assert selected==result['selected']
selection=json.loads((out/'selection_before_validation.json').read_text(encoding='utf-8'))
assert selection['selected']==selected and selection['passing_training']==passing
assert selection['protocol_sha256']==digest(spec)
for row in result['rows']:
    if row['period']!='training': assert row['candidate']==selected
    if row['period']=='final_confirmation': assert all(z['passed'] for z in result['decisions'][selected]['validation'].values())
if not selected:
    assert result['phase']=='training'
    assert not list(out.glob('*__validation__*')) and not list(out.glob('*__final_confirmation__*'))
expected_json=set(row['artifact'] for row in result['rows'])
assert {f.name for f in out.glob('*__*.json')}==expected_json
for path, expected in frozen['sha256'].items(): assert digest(root/path)==expected
print(json.dumps(dict(status='INDEPENDENT_REPLAY_OK',phase=result['phase'],selected=selected,
                     symbol_case_artifacts=rows,trades=trades_checked,feature_prefix_checks=feature_checks,
                     replay_prefix_checks=prefix_checks,aggregates=len(bundles)),ensure_ascii=False))
```
