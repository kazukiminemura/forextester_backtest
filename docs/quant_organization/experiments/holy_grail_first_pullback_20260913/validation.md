# Holy Grail first pullback 独立検証

判定: **不採用 / REJECTED / VERIFIED_REJECTED_TRAINING_ONLY**。
H1/H4の「最初の押し目」2候補とも学習基準に不合格。学習中の比較対象よりPFと平均Rはわずかに改善したが、両費用・全3学習区分の合計損益が負。
選抜0。2019年以降の戦略成績は計算せず、Pine移植へ進めない。実運用承認ではない。

## 入力と実行完了の証拠

- 担当 / 次担当: 独立検証 / 品質監査・研究責任者。
- 入力: `hypothesis.md`、`protocol.json`、`data_inventory.md`、`completed/code_input_hashes.json`。11通貨、H1/H4、EMA20・ADX14、ADX30上抜けで準備、25未満またはDI方向喪失で解除、3観測足の注文期限、RR1全決済。
- 指標入力2009-10-01以降、売買対象2010-01-01以上2019-01-01未満。上位足入力なし。既閲覧履歴なので真の未使用holdoutとは呼ばない。
- 凍結UTC: `2026-09-12T23:49:28.182774+00:00`。コードSHA256: `8baa4aae677893d94f1ac93642c533cb129ace3a394e9012279913a80f48e6b3`。protocol SHA256: `2ab0ab7d8512bce7cd2c172a4f7caa427ac1777478f2348122cc19e4a6c937b8`。
- 独立training再実行: 最終`RESULT_JSON`取得、プロセス終了コード **0**。`independent_reproduction/replayed/results.json`の存在とphase/選抜を確認した。
- 研究担当の挙動テスト: **19 passed / exit 0**。独立検算: 最終`INDEPENDENT_VERIFICATION_JSON`取得、**exit 0**。詳細は `agent_runs/holy_grail_first_pullback_20260913/independent_reproduction/verification.json`。
- 元result SHA256: `a308d8542ac29bb2c4dee16f1ae6e44aa5597280e3341943c3c6b3249a9eb248`。再実行result SHA256: `1527158241c22fe3a6f5c331323d4ae3d00c31f82e0e035cc5d23fad24c802c4`。完了日時が異なるためファイルhash自体は一致しない。可変日時フィールドを除いたJSON内容は完全一致した。
- 変更: 本レポートと独立再現先の成果物のみ。研究コード・基準・元履歴は変更なし。実注文なし。

## 再現・独立検算の範囲

元runと別runの94 JSONを比較し、`completed_at_utc`、`frozen_at_utc`、`saved_at_utc`だけを除いて完全一致。NPZは206保存配列で完全一致（ファイル圧縮バイト列ではなく配列の同値）。コード・依存先・仕様8hashと、11通貨のphase-boundedデータ台帳も一致した。

独立コードは研究モジュールをimportせず、保存集約足からEMA/ADX、episodeと初回接触、因果的な構造SLを再構成した。44信号stream・16,322 setup、66指標prefix、61,622注文event、88成果物に含む16,644取引明細を照合。費用別明細を含むため16,644件を独立した機会数と解釈しない。

次足以降3本のentry stop、SL側の始値での注文取消、entry gap、既存positionの不利stop gap、有利TPの上限、同一足SL優先、signal足での未約定、occupied/exit足での見送り、初回接触の消費、episode reset確定時刻、境界清算を全明細で照合した。初回候補のsetupはepisodeごとに最大1件。setup決定は保有状態に依存せず、不適格な初回接触も消費される。

平均R・PF・金銭勝率相当の正net-R比率・費用・保有日数・通貨幅・88 MTM曲線・8合算曲線と事前ゲートを独立式で一致確認。PFは等初期Rの利益R合計/損失R合計、DDは各戦略足終値の含み込みR曲線から算定した研究尺度。異なるクオートの現金P/Lを合算しておらず、資金量・複利・口座通貨リターンを意味しない。建値は勝率の勝ちに加えていない。

独立signal/fill検算の入力は保存H1/H4集約足。元M1の全件集約を別エンジンで再構成した検査ではない。sourceへの再実行とhash一致、データ担当の元M1監査・限定集約サンプル検査を合わせた証拠である。OHLC内の実際の時系列、価格配信元一致、ライブ約定を検証したとはしない。

## 学習全体の指標

固定費用は往復1.8pips、metadata費用は保存spread+0.4pips。いずれも追加保有費用0.2pip/暦日。表のDDは含み込みR。

|候補|費用|件数|勝率%|PF|平均R|合計R|DD R|黒字通貨/11|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|H1 repeat 比較|固定|4,123|45.38|0.6500|-0.21561|-888.971|896.812|0|
|H1 first|固定|2,521|45.74|0.6527|-0.21401|-539.529|543.549|0|
|H4 repeat 比較|固定|1,057|47.49|0.7997|-0.11202|-118.405|129.166|2|
|H4 first|固定|621|47.67|0.8048|-0.10911|-67.759|81.182|3|
|H1 repeat 比較|metadata|4,123|45.31|0.6481|-0.21722|-895.609|903.461|0|
|H1 first|metadata|2,521|45.70|0.6516|-0.21492|-541.823|545.843|0|
|H4 repeat 比較|metadata|1,057|47.49|0.7978|-0.11326|-119.721|130.419|2|
|H4 first|metadata|621|47.67|0.8030|-0.11022|-68.446|81.904|3|

H1 firstはPF1.10、平均R>0、黒字8通貨、合算DD<=40R、単一通貨DD<=20R、全学習区分黒字の6項目で失敗。H4 firstは単一通貨DD以外の5項目で失敗。件数と比較改善だけは通過した。小標本の通貨だけを選び直すことは事前禁止。

## 学習3区分の指標

売買明細の決済年で件数・PF・平均Rを分類。DDは各区分の開始直前評価額を起点に、区分内の含み込み曲線から算定。学習区分で状態をリセットした別バックテストではない。

|候補|費用|区分|件数|PF|平均R|合計R|DD R|
|---|---|---|---:|---:|---:|---:|---:|
|H1 first|固定|2010–2012|864|0.68667|-0.18796|-162.397|171.497|
|H1 first|固定|2013–2015|800|0.71488|-0.16876|-135.008|136.300|
|H1 first|固定|2016–2018|857|0.56885|-0.28252|-242.124|245.108|
|H1 first|metadata|2010–2012|864|0.68576|-0.18879|-163.111|172.209|
|H1 first|metadata|2013–2015|800|0.71329|-0.17001|-136.009|137.456|
|H1 first|metadata|2016–2018|857|0.56802|-0.28320|-242.703|245.684|
|H4 first|固定|2010–2012|229|0.81880|-0.10077|-23.077|37.647|
|H4 first|固定|2013–2015|194|0.70388|-0.17521|-33.992|37.831|
|H4 first|固定|2016–2018|198|0.89817|-0.05399|-10.690|22.003|
|H4 first|metadata|2010–2012|229|0.81778|-0.10143|-23.227|37.815|
|H4 first|metadata|2013–2015|194|0.70123|-0.17702|-34.342|38.177|
|H4 first|metadata|2016–2018|198|0.89652|-0.05494|-10.878|22.185|

validation 2019–2022、final_confirmation 2023-01-01〜2026-08-31未満は、学習不合格により未評価。指標0とは扱わない。

## 通貨別指標

全学習期間・固定費用。metadata費用およびrepeat比較を含む全88行の指標は独立`verification.json`の`per_symbol`に保存。

|通貨|H1件数|H1 PF|H1平均R|H1 DD R|H4件数|H4 PF|H4平均R|H4 DD R|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|AUDJPY|219|0.60792|-0.24890|55.459|57|0.56454|-0.28263|18.458|
|AUDUSD|251|0.58438|-0.26957|68.532|61|0.91104|-0.04696|8.431|
|EURCHF|212|0.57309|-0.28017|62.594|52|0.58882|-0.26702|14.626|
|EURGBP|235|0.57708|-0.27721|72.266|62|0.61514|-0.24182|15.107|
|EURUSD|258|0.74024|-0.15230|43.968|58|0.97109|-0.01467|11.122|
|GBPCHF|234|0.60530|-0.24977|59.688|63|1.14738|0.06867|5.258|
|GBPUSD|220|0.65914|-0.20867|45.908|51|1.20821|0.09399|7.349|
|NZDJPY|207|0.72621|-0.16058|36.363|65|1.03907|0.01912|6.322|
|NZDUSD|245|0.72189|-0.16333|41.104|54|0.81831|-0.10056|12.229|
|USDCAD|202|0.58064|-0.27133|56.748|49|0.61296|-0.24257|12.871|
|USDJPY|238|0.83562|-0.08867|27.911|49|0.60936|-0.24700|17.898|

## 頑健性・制約・引継ぎ

- 固定費用のfirst候補PF: 保有費用0/0.2/1pipでH1 **0.67053/0.65268/0.58564**、H4 **0.81930/0.80480/0.74937**。保有費用をゼロにしても不合格。spread等もゼロにしたgross PFはH1 0.84153、H4 0.90949で負の期待値。
- metadata費用のfirst候補PF: 保有費用0/0.2/1pipでH1 **0.66942/0.65163/0.58478**、H4 **0.81752/0.80305/0.74775**。費用増加への利益頑健性は確認できない。
- H1/H4とfirst/repeatという結果前固定の範囲で感度を確認した。EMA長・ADX長/水準・注文期限等の周辺パラメータ感度は未実施。凍結4候補予算を超える変更は新実験を要し、今回の不採用を調整によって覆さない。
- 全88成果物の境界清算件数は0で、境界清算除外感度は元集計と同じ。保有費用はbucket first〜exit exposure endを暦日切上げした仮定で、同日短時間でも1日分を課し得る。
- 未実装費用: 実時変動spread、実約定slippageの分布、実swap/曜日別三倍日、ブローカー手数料時系列。metadataのcommission=0は確認するが、実業者の費用ゼロ証明ではない。1.8pipsとmetadata+0.4、0.2pip/日は研究仮定。
- 数量: 同一通貨ペアに注文/position各最大1、全11通貨の等初期Rを合算。相関・同一構成通貨エクスポージャー・lot丸め・必要証拠金・為替換算・資金制約を実装していない。
- データ制約: CHFJPY/EURJPY/GBPJPY/USDCHFは結果前に隔離。残る11通貨も全履歴tick一致を保証しない。保存時刻帯/DST、実配信元、TradingViewとの足境界一致は未確認。不完全bucketは補間せずnominal endで利用可能とする。
- 原著全章を検証したものではない。著者の一次インタビューを根拠に、初回episode・reset・方向・構造SL・RR1等を機械化した特定の解釈についての不採用であり、原著の裁量運用すべてを反証したとはしない。
- 軽微な仕様記述所見: hypothesisのATR14 index13 seed文は実装で算出・使用しないATRに触れている。実際のADX用Wilder TRはindex14からで同文書のADX説明に一致。担当へ文書訂正を依頼し、凍結hashは保全する。判定に影響する未解決不一致はなし。
- 次工程へ渡せる範囲: この凍結モデルの学習不採用証拠と制約。Pine移植・後半選抜・実運用承認には渡せない。

## 再現コマンド

独立再実行（既存出力を上書きしないため、再度走らせる場合は新しい出力名を指定）:

```powershell
python -m scripts.research_holy_grail_first_pullback --phase training --output agent_runs/holy_grail_first_pullback_20260913/independent_reproduction/replayed
python -m pytest tests/test_holy_grail_first_pullback.py -q
```

次の検算は研究モジュールを import せず、Python標準ライブラリとNumPyだけを使用する。
レポートから下のコードを取り出して実行できる。担当レポート以外の新規検証ソースは作成しない。

```powershell
$taskReport = Get-Content -Raw docs/quant_organization/experiments/holy_grail_first_pullback_20260913/validation.md
$taskCode = [regex]::Match($taskReport, '(?s)<!-- VERIFY_BEGIN -->\s*```python\r?\n(.*?)\r?\n```\s*<!-- VERIFY_END -->').Groups[1].Value
$taskCode | python -
```

上表の区分別DDの追加再現（読取り専用、実行exit 0確認済み）:

```powershell
@'
from pathlib import Path
import numpy as np
root=Path('agent_runs/holy_grail_first_pullback_20260913/completed')
for cid in ('h1_first','h4_first'):
 for case in ('fixed_1p8','metadata_plus_0p4'):
  e=np.load(root/f'{cid}__training__{case}_aggregate_equity.npz')['equity']
  for lo,hi in [(1262304000,1356998400),(1356998400,1451606400),(1451606400,1546300800)]:
   a,b=np.searchsorted(e[:,0],[lo,hi]); v=np.r_[0,e[a:b,2]-(e[a-1,2] if a else 0)]
   print(cid,case,lo,'DD',float(np.max(np.maximum.accumulate(v)-v)))
'@ | python -
```

<!-- VERIFY_BEGIN -->
```python
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, math
import numpy as np

base = Path('agent_runs/holy_grail_first_pullback_20260913')
original, replay = base/'completed', base/'independent_reproduction/replayed'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
p = read(original/'protocol.json')
result = read(original/'results.json')
manifest = {x['symbol']: x for x in read(original/'training_data_manifest.json')}
counts = {'json_exact': 0, 'npz_arrays': 0, 'trades': 0, 'signal_streams': 0, 'indicator_prefixes': 0, 'setups': 0, 'orders': 0, 'mtm_curves': 0}
def close(a,b):
    np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-9,equal_nan=True)
def check(actual, expected):
    if isinstance(expected,dict):
        assert set(actual)==set(expected), (set(actual),set(expected))
        for k in expected: check(actual[k],expected[k])
    elif isinstance(expected,list):
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected): check(a,b)
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool): close(actual,expected)
    else: assert actual==expected,(actual,expected)
for f in original.iterdir():
    other = replay/f.name
    assert other.exists(),f
    if f.suffix=='.npz':
        with np.load(f) as a,np.load(other) as b:
            assert set(a.files)==set(b.files)
            for k in a.files:
                np.testing.assert_array_equal(a[k],b[k]); counts['npz_arrays']+=1
    elif f.suffix=='.json':
        a,b=read(f),read(other)
        for key in ('completed_at_utc','frozen_at_utc','saved_at_utc'):
            if isinstance(a,dict): a.pop(key,None); b.pop(key,None)
        assert a==b,f
        counts['json_exact']+=1
assert {x.name for x in original.iterdir()}=={x.name for x in replay.iterdir()}
for path,h in read(original/'code_input_hashes.json')['sha256'].items(): assert digest(Path(path))==h,path
assert result['phase']=='training' and result['selected']==''
assert result['status']=='REJECTED_BY_FROZEN_GATES'
assert not any('validation__' in f.name or 'final_confirmation__' in f.name for f in original.iterdir())

def indicators(b):
    n=len(b); ema=np.empty(n); ema[0]=b[0,3]
    tr=np.zeros(n); up=np.zeros(n); dn=np.zeros(n)
    plus=np.full(n,np.nan); minus=plus.copy(); adx=plus.copy(); dx=plus.copy()
    for i in range(1,n):
        ema[i]=ema[i-1]+(b[i,3]-ema[i-1])*2/21
        tr[i]=max(b[i,1]-b[i,2],abs(b[i,1]-b[i-1,3]),abs(b[i,2]-b[i-1,3]))
        u,d=b[i,1]-b[i-1,1],b[i-1,2]-b[i,2]
        up[i]=u if u>max(d,0) else 0
        dn[i]=d if d>max(u,0) else 0
    if n>14:
        t,u,d=map(lambda a:math.fsum(a[1:15])/14,(tr,up,dn))
        for i in range(14,n):
            if i>14: t,u,d=[(13*v+a[i])/14 for v,a in zip((t,u,d),(tr,up,dn))]
            plus[i],minus[i]=(100*u/t,100*d/t) if t else (0,0)
            dx[i]=100*abs(plus[i]-minus[i])/(plus[i]+minus[i]) if plus[i]+minus[i] else 0
    if n>27:
        adx[27]=math.fsum(dx[14:28])/14
        for i in range(28,n): adx[i]=(13*adx[i-1]+dx[i])/14
    return ema,adx,plus,minus

def streams(b,features,start,first_only,point):
    ema,adx,plus,minus=features
    episodes=[]; resets=set(); setups={}; active=None
    for i in range(max(start,249),len(b)):
        d=int(plus[i]>minus[i])-int(plus[i]<minus[i])
        if active is not None and (adx[i]<25 or d!=active['d']):
            episodes.append({'index':i,'event':'reset','arm':active['arm']});resets.add(i);active=None
        if active is None:
            if adx[i-1]<=30 and adx[i]>30 and d*(b[i,3]-ema[i])>0:
                active={'d':d,'arm':i,'anchor':i,'touched':False}
                episodes.append({'index':i,'event':'arm','direction':d})
            continue
        if b[i,2]<=ema[i]<=b[i,1]:
            allowed=not first_only or not active['touched']
            if not active['touched']: episodes.append({'index':i,'event':'first_touch_consumed','arm':active['arm']})
            active['touched']=True
            away=b[i-1,2]>ema[i-1] if d>0 else b[i-1,1]<ema[i-1]
            if allowed and away and d*(b[i,3]-ema[i])>0:
                a=active['anchor']; begin=a+1
                extreme=min(b[begin:i+1,2]) if d>0 else max(b[begin:i+1,1])
                setups[i]={'direction':d,'signal_index':i,'arm_index':active['arm'],'anchor_index':a,'pullback_start_index':begin,'trigger':float(b[i,1]+point if d>0 else b[i,2]-point),'stop':float(extreme-d*point)}
        if (d>0 and b[i,1]>=b[active['anchor'],1]) or (d<0 and b[i,2]<=b[active['anchor'],2]): active['anchor']=i
    return setups,resets,episodes

def stats(v):
    v=list(v); gain=math.fsum(x for x in v if x>0); loss=-math.fsum(x for x in v if x<0)
    return {'trades':len(v),'win_rate_pct':100*sum(x>0 for x in v)/len(v) if v else 0.,'pf':gain/loss if loss else None,'profit_r':gain,'loss_r':loss,'net_r':math.fsum(v),'average_net_r':math.fsum(v)/len(v) if v else 0.}
def dd(v):
    peak=0.; worst=0.
    for x in v: peak=max(peak,x);worst=max(worst,peak-x)
    return worst
def summary(trades,equity):
    s=stats(t['net_r'] for t in trades)
    for name,field in [('gross','gross_r'),('zero_carry','net_zero_carry_r'),('one_pip_carry','net_one_carry_r')]: s[name]=stats(t[field] for t in trades)
    s.update(without_boundary=stats(t['net_r'] for t in trades if t['reason']!='period_boundary'),mtm_drawdown_r=dd(equity[:,2]),max_holding_bars=max((t['holding_bars'] for t in trades),default=0),mean_carry_days=math.fsum(t['carry_days'] for t in trades)/len(trades) if trades else 0.,boundary_trades=sum(t['reason']=='period_boundary' for t in trades))
    return s

collected={}; per_symbol=[]; timeframe={}
for symbol in p['symbols']:
    m=manifest[symbol]; pip,point=m['pip'],m['point']
    for minutes in (60,240):
        with np.load(original/f'training__{symbol}__{minutes}_bars.npz') as z: data={k:z[k].copy() for k in z.files}
        dates,b,first=data['dates'],data['ohlc'],data['first']; width=60*minutes
        assert dates[-1]<1546300800 and np.all(first>=dates) and np.all(data['last']<dates+width)
        assert np.all(data['counts']<=minutes) and np.all(np.diff(dates)>0)
        start=int(np.searchsorted(dates,1262304000)); features=indicators(b)
        for cut in (start+200,len(b)//2,len(b)-100):
            for a,v in zip(indicators(b[:cut]),features): close(a,v[:cut])
            counts['indicator_prefixes']+=1
        for candidate in [c for c in p['search_space'] if c['minutes']==minutes]:
            cid=candidate['id']; setups,resets,events=streams(b,features,start,candidate['first_only'],point)
            counts['signal_streams']+=1; counts['setups']+=len(setups)
            if candidate['first_only']: assert len({s['arm_index'] for s in setups.values()})==len(setups)
            for case in ('fixed_1p8','metadata_plus_0p4'):
                cost=1.8 if case=='fixed_1p8' else m['metadata_spread_pips']+.4
                name=f'{cid}__training__{symbol}__{case}'
                artifact=read(original/(name+'.json')); trades=artifact['trades']; diagnostics=artifact['diagnostics']
                check(diagnostics['episodes'],events)
                by_entry={t['entry_index']:t for t in trades}; assert len(by_entry)==len(trades)
                expected_orders=[]; pending=None; occupied=None; realized=0.; curve=[]; seen=0
                for i in range(start,len(b)):
                    op,hi,lo,cl=b[i]; fresh=False; exited=False
                    if pending:
                        si=pending['signal_index']; d=pending['direction']; trigger=pending['trigger']; stop=pending['stop']
                        if d*(op-stop)<=0:
                            expected_orders.append({'signal_index':si,'index':i,'event':'cancel_stop_gap'}); pending=None
                        elif d*(op-trigger)>=0 or (hi>=trigger if d>0 else lo<=trigger):
                            assert i in by_entry,(name,i)
                            t=by_entry[i]; occupied=t; fresh=True;seen+=1
                            for k,v in pending.items(): check(t[k],v)
                            at_open=d*(op-trigger)>=0; price=op if at_open else trigger; risk=d*(price-stop)
                            assert risk>0 and 1<=i-si<=3
                            close(t['entry'],price);close(t['risk'],risk);close(t['target'],price+d*risk)
                            assert t['entry_at_open']==bool(at_open)
                            assert t['signal_timestamp']==dates[si]+width<=first[i]==t['entry_timestamp']
                            assert t['entry_fill_timestamp_bound']==(first[i] if at_open else dates[i]+width)
                            expected_orders.append({'signal_index':si,'index':i,'event':'filled'});pending=None
                        elif i-si==3:
                            expected_orders.append({'signal_index':si,'index':i,'event':'expired'});pending=None
                    if occupied:
                        t=occupied; d=t['direction']; sl=t['stop']; tp=t['target']; fill=None
                        sh=(lo<=sl if d>0 else hi>=sl); th=(hi>=tp if d>0 else lo<=tp)
                        if not fresh and d*(op-sl)<=0: fill=(op,'stop_gap',first[i])
                        elif not fresh and d*(op-tp)>=0: fill=(tp,'target_gap_capped',first[i])
                        elif sh: fill=(sl,'both_stop_first' if th else 'stop',dates[i]+width)
                        elif th: fill=(tp,'target',dates[i]+width)
                        elif i==len(b)-1: fill=(cl,'period_boundary',dates[i]+width)
                        if fill:
                            price,reason,exposure=fill; assert t['exit_index']==i and t['reason']==reason
                            assert t['exit_exposure_timestamp']==exposure
                            close(t['exit_price'],price)
                            days=math.ceil(max(0,int(exposure)-int(first[t['entry_index']]))/86400)
                            gross=d*(price-t['entry'])/t['risk']; fee=cost*pip/t['risk']; carry=.2*days*pip/t['risk']
                            for key,value in dict(gross_r=gross,fee_r=fee,carry_r=carry,net_r=gross-fee-carry,net_zero_carry_r=gross-fee,net_one_carry_r=gross-fee-days*pip/t['risk'],risk_pips=t['risk']/pip,carry_days=days,holding_bars=i-t['entry_index']+1).items(): close(t[key],value)
                            realized+=gross-fee-carry;occupied=None;exited=True
                    if i in resets and pending:
                        expected_orders.append({'signal_index':pending['signal_index'],'index':i,'event':'cancel_episode_reset_at_close'});pending=None
                    mark=0.
                    if occupied:
                        t=occupied;days=math.ceil((int(dates[i]+width)-t['entry_timestamp'])/86400)
                        mark=t['direction']*(cl-t['entry'])/t['risk']-(cost+.2*days)/t['risk_pips']
                    curve.append([int(dates[i]+width),realized,realized+mark])
                    if i in setups:
                        submit=occupied is None and pending is None and not exited and i<len(b)-1
                        expected_orders.append({'signal_index':i,'index':i,'event':'submitted_at_close' if submit else 'skipped_occupied_exit_or_boundary'})
                        if submit: pending=setups[i]
                if pending: expected_orders.append({'signal_index':pending['signal_index'],'index':len(b)-1,'event':'cancel_period_boundary'})
                assert seen==len(trades)
                check(diagnostics['orders'],expected_orders);counts['orders']+=len(expected_orders)
                equity=np.array(curve);counts['trades']+=seen;counts['mtm_curves']+=1
                with np.load(original/(name+'_equity.npz')) as z: close(equity,z['equity'])
                s=summary(trades,equity);check(artifact['summary'],s)
                collected.setdefault((cid,case),[]).append((trades,equity,s))
                per_symbol.append(dict(candidate=cid,symbol=symbol,case=case,**s))

totals={}; decisions={}
for (cid,case),items in collected.items():
    trades=[t for ts,e,s in items for t in ts]; dates=np.unique(np.concatenate([e[:,0] for ts,e,s in items])); equity=np.column_stack((dates,np.zeros((len(dates),2))))
    for ts,e,s in items:
        indices=np.searchsorted(e[:,0],dates,side='right')-1;valid=indices>=0
        equity[valid,1:]+=e[indices[valid],1:]
    with np.load(original/f'{cid}__training__{case}_aggregate_equity.npz') as z: close(equity,z['equity'])
    s=summary(trades,equity);s['profitable_symbols']=sum(v['net_r']>0 for ts,e,v in items);s['max_single_symbol_mtm_drawdown_r']=max(v['mtm_drawdown_r'] for ts,e,v in items)
    s['training_subperiods']=[]
    for lo,hi in p['acceptance_gates']['training_subperiods']:
        selected=[t['net_r'] for t in trades if lo<=int(t['exit_date'][:4])<=hi]
        a,b=np.searchsorted(dates,[datetime(lo,1,1,tzinfo=timezone.utc).timestamp(),datetime(hi+1,1,1,tzinfo=timezone.utc).timestamp()])
        s['training_subperiods'].append(dict(years=[lo,hi],realized=stats(selected),mtm_net_r=float(equity[b-1,2]-(equity[a-1,2] if a else 0)),end_open_r=float(equity[b-1,2]-equity[b-1,1])))
    check(result['totals'][cid]['training'][case],s); totals.setdefault(cid,{})[case]=s
for c in p['search_space']:
    cid=c['id'];decisions[cid]={}
    for case,s in totals[cid].items():
        g=p['acceptance_gates'];f=[]
        if s['trades']<g['training']['minimum_trades']: f.append('trades')
        if s['pf']<g['training']['minimum_pf']: f.append('pf')
        if s['average_net_r']<=0: f.append('expectancy')
        if s['profitable_symbols']<g['training']['minimum_profitable_symbols']: f.append('symbol_breadth')
        if s['mtm_drawdown_r']>g['maximum_aggregate_daily_mtm_drawdown_r']: f.append('mtm_dd')
        if s['max_single_symbol_mtm_drawdown_r']>g['maximum_single_symbol_daily_mtm_drawdown_r']: f.append('single_symbol_mtm_dd')
        if any(x['realized']['net_r']<=0 for x in s['training_subperiods']): f.append('training_subperiods')
        if c['eligible']:
            b=totals[c['baseline']][case]
            if s['pf']<=b['pf']: f.append('baseline_pf_not_improved')
            if s['average_net_r']<=b['average_net_r']: f.append('baseline_mean_r_not_improved')
        decisions[cid][case]={'passed':not f,'failures':f}
        check(result['decisions'][cid]['training'][case],decisions[cid][case])
assert not [c['id'] for c in p['search_space'] if c['eligible'] and all(v['passed'] for v in decisions[c['id']].values())]
out={'status':'VERIFIED_REJECTED_TRAINING_ONLY','counts':counts,'totals':totals,'decisions':decisions,'per_symbol':per_symbol,'research_result_sha256':digest(original/'results.json'),'replay_result_sha256':digest(replay/'results.json'),'replay_exit_code':0,'later_periods_evaluated':False}
target=base/'independent_reproduction/verification.json';target.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print('INDEPENDENT_VERIFICATION_JSON='+str(target));print(json.dumps({'status':out['status'],'counts':counts,'totals':totals,'decisions':decisions},indent=2))
```
<!-- VERIFY_END -->
