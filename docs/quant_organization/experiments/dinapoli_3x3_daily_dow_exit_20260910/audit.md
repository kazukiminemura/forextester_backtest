# 独立検証・監査

- 実験ID / 担当 / 次担当: `dinapoli_3x3_daily_dow_exit_20260910` / 独立検証 / 研究責任者。
- 判定: **不採用**（`VERIFIED_REJECTED_TRAINING_ONLY`）。日足再利用・pivot確認・別状態実装による全明細・集計・事前ゲートの照合完了。
- 編集所有: このレポートのみ。戦略・採用基準・原データを変更しない。実注文なし。

## 結果前確認と監査計画

入力は同ディレクトリのhypothesis.md、protocol.json、data_inventory.md。ユーザーがダウトレンド転換までの保有を指定したため、規約のRR1既定に対し今回の候補はTPを廃止する。初期構造SLは維持し、比較専用2条件は旧RR1。ダウ転換の機械的定義は左右2/2・3/3の厳密pivot、直近2高値・2安値の同方向更新で状態確定、混合時は保持。4候補で有限探索する。

因果性はpivot本体kではなくk+pの引けで利用可能となることを独立実装し、prefix切断一致を検査する。同時high/low更新、同値不成立、long/short対称性を確認する。初期SL始値ギャップ→予定ダウ始値決済→日中SL→引け転換判定の優先順を照合する。日足実末尾M1+60秒から翌足実始値への時間順も確認する。

結果前の責任者レビューで出口の意味を修正した。最終仕様はentry時未armed、entry後の引けで一度ポジション方向のDow stateを観測してarmed、その後反対状態への新規transitionで翌始値出口。入る前から逆状態であるだけでは出口にしない。研究担当は修正通知時点でテスト/実走結果ゼロと報告し、更新仕様・コードの結果前ハッシュ凍結を完了監査で確認する。

保存日足のSHA・配列と前実験の一致、凍結依存ファイル識別子、取引明細、各通貨/区分の勝率・コスト後PF・平均R・closed/MTM DD、期末含み/未実行出口、選抜ゲートを再計算する。日足生成についてはデータ担当が現原M1から66,096本再集約一致を確認し、前実験の独立監査が別集約実装一致を確認した。今回の入力同一性を現在ファイルで確認して引き継ぐ。

training 2010–2018から両コスト全基準通過候補を最大1つ選抜し、selection保存後validation、通過後のみfinalを評価する。次点繰上げなし。両コスト・複数通貨・件数・PF・期待値・DDを判定する。過去に閲覧した期間を真の未使用holdoutと呼ばない。採用候補が出ない停止も正式な結果として保存する。

Rは初期リスクで正規化した等リスク研究スコアであり、異なる決済通貨の口座損益単純合算ではない。金銭的勝ちはnet R>0、建値は金銭利益へ含めない。swap=0・slippage=0・commission=0・固定spreadは実市場費用がゼロである証拠ではない。左右pivot感度、metadata費用増加、1pip/暦日の仮想保有費用を診断し、長期保有の未計上費用を明示する。

最終判定には終了コード0・最終results.json・稼働プロセス終了・完全照合結果が必要。研究合格と実運用承認は区別し、監査は後者を行わない。

## 完了証拠と識別子

研究実行は終了コード0、最終RESULT_JSONとcompleted/results.jsonを確認。凍結UTCは2026-09-09T23:56:01.328863+00:00、完了は23:56:29.946626+00:00（JST 2026-09-10）。独立確認時に本実験名を含む研究Pythonプロセスは0件。凍結7依存ファイルSHAは現ファイルと全件一致した。

|入力|SHA256|
|---|---|
|新研究コード|9d601f25a02e2deed8e3e1d40bfa051c2a749eebfef33e8333e899baa7b82e93|
|protocol.json|1b53a84c55ac8a49b25b6b8b3b85f79a746a4d49ad34c8de335ba6aa59261e95|
|hypothesis.md|5fbe57d94a6dd6bde46a104cee5eb7857490e62f7ac44c001d55698f6b816ffc|

`agent_runs/dinapoli_3x3_daily_dow_exit_20260910/completed/` の66,096日足は旧保存配列・配列SHA・manifestと全件一致、原ファイルsize/mtimeも現時点で一致。30組のpivot state/event列を別計算し、90のpivot prefixと価格反転対称性を確認した。全180取引成果物（6条件×15通貨×2費用）・6,134明細、全equity配列、期末含み・pending出口を別状態実装で一致確認した。entry signal prefix540件を加えて計630prefix、12合算指標、60旧RR1成果物一致。監査実行の終了コード0、最終 `VERIFIED` / selected null / passed []。

監査コード初回抽出時のIndexErrorはレポート内のmarker文字列衝突であり、監査用コードのmarkerだけを修正して再実行した。戦略コード・仕様・基準・結果には変更なし。関連テストは本担当も `python -m pytest tests/test_dinapoli_3x3_daily.py tests/test_dinapoli_3x3_daily_dow_exit.py -q -p no:cacheprovider` を実行し41 passed、exit0。

研究再現コマンド: `$env:PYTHONPATH='src'; python -m scripts.research_dinapoli_3x3_daily_dow_exit --output agent_runs/dinapoli_3x3_daily_dow_exit_20260910/reproduction`。未作成の出力先を指定する。独立監査の読取専用コマンドは下記に完全保存した。

## 期間・条件別結果

以下はtraining 2010-01-01以上2019-01-01未満、往復固定1.4pips。DDはclosed等R研究曲線。勝率はnet R>0。同じentry/SL仕様でも保有期間変更により1通貨1ポジション制約で取引集合が変化する。

|条件|件数|勝率%|PF|平均net R|net R|最大DD R|利益通貨|
|---|---:|---:|---:|---:|---:|---:|---:|
|DR8 RR1比較|604|47.68|0.8932|-0.05645|-34.098|48.224|7/15|
|DR10 RR1比較|506|50.40|0.9962|-0.00188|-0.953|28.151|8/15|
|DR8 Dow2|541|33.27|0.8912|-0.06390|-34.572|60.621|6/15|
|DR8 Dow3|505|30.50|0.8506|-0.09331|-47.121|71.298|3/15|
|DR10 Dow2|465|34.41|0.9290|-0.04027|-18.724|63.345|5/15|
|DR10 Dow3|446|30.04|0.7385|-0.16613|-74.094|95.952|2/15|

metadata spreadでの4候補PFは順に0.8904 / 0.8498 / 0.9280 / 0.7378、平均Rは-0.06442 / -0.09384 / -0.04084 / -0.16672、DDは60.887 / 71.490 / 63.577 / 96.180R。いずれも両費用でPF>=1.10・平均R>0・集計DD<=20R・個別DD<=10R・利益通貨>=10をすべて不通過。件数100以上だけは満たす。選抜nullなのでvalidation 2019–2022とfinal 2023–2026-08-31未満は戦略損益未評価。これは事前停止条件の適用で、途中失敗による未完了ではない。

新出口による平均R改善の仮説は4候補すべて対応RR1を下回り支持されない。Dow2→Dow3で両entryともPF・平均R・DDが悪化し、隣接pivot設定の利益頑健性もない。

### 通貨別training

表中は固定1.4 / metadata。勝率・net R・MTM DD・期末含みの未丸め値はresults.jsonのrowsと各個別JSONで参照でき、これらも独立照合済み。

DR8 Dow2:

|通貨|件数|PF|平均R|DD R|
|---|---:|---:|---:|---:|
|AUDUSD|44|0.699 / 0.701|-0.1919 / -0.1904|12.919 / 12.858|
|EURUSD|34|0.429 / 0.431|-0.3456 / -0.3441|11.829 / 11.788|
|GBPUSD|40|0.345 / 0.345|-0.4546 / -0.4546|20.846 / 20.846|
|NZDUSD|27|1.079 / 1.079|0.0494 / 0.0494|4.958 / 4.958|
|USDCAD|38|0.762 / 0.761|-0.1437 / -0.1444|9.580 / 9.590|
|USDCHF|46|0.769 / 0.768|-0.1529 / -0.1538|14.581 / 14.613|
|USDJPY|32|1.051 / 1.054|0.0298 / 0.0314|8.211 / 8.187|
|AUDJPY|38|0.901 / 0.901|-0.0612 / -0.0612|11.550 / 11.550|
|CHFJPY|33|1.234 / 1.228|0.1435 / 0.1405|8.404 / 8.440|
|EURCHF|36|0.950 / 0.944|-0.0299 / -0.0338|6.928 / 6.954|
|EURGBP|33|1.716 / 1.716|0.3436 / 0.3436|6.373 / 6.373|
|EURJPY|38|1.286 / 1.287|0.1463 / 0.1468|4.487 / 4.483|
|GBPCHF|36|1.051 / 1.049|0.0259 / 0.0248|6.748 / 6.762|
|GBPJPY|34|0.775 / 0.773|-0.1150 / -0.1165|12.875 / 12.914|
|NZDJPY|32|0.924 / 0.920|-0.0386 / -0.0408|8.301 / 8.345|

DR8 Dow3:

|通貨|件数|PF|平均R|DD R|
|---|---:|---:|---:|---:|
|AUDUSD|41|0.766 / 0.768|-0.1472 / -0.1458|9.937 / 9.892|
|EURUSD|32|0.288 / 0.289|-0.4766 / -0.4750|15.250 / 15.201|
|GBPUSD|35|0.296 / 0.296|-0.4517 / -0.4517|18.400 / 18.400|
|NZDUSD|26|0.993 / 0.993|-0.0052 / -0.0052|5.856 / 5.856|
|USDCAD|34|0.971 / 0.970|-0.0173 / -0.0180|8.301 / 8.307|
|USDCHF|40|0.563 / 0.562|-0.3087 / -0.3096|16.878 / 16.911|
|USDJPY|27|2.034 / 2.038|0.5816 / 0.5831|6.090 / 6.077|
|AUDJPY|36|0.843 / 0.843|-0.0987 / -0.0987|11.304 / 11.304|
|CHFJPY|33|0.974 / 0.970|-0.0176 / -0.0207|8.144 / 8.181|
|EURCHF|34|0.847 / 0.842|-0.0997 / -0.1033|8.246 / 8.282|
|EURGBP|34|1.460 / 1.460|0.2459 / 0.2459|4.751 / 4.751|
|EURJPY|37|1.134 / 1.135|0.0762 / 0.0766|8.010 / 8.002|
|GBPCHF|35|0.886 / 0.884|-0.0647 / -0.0658|8.671 / 8.694|
|GBPJPY|30|0.865 / 0.862|-0.0815 / -0.0829|12.442 / 12.477|
|NZDJPY|31|0.410 / 0.408|-0.3743 / -0.3764|13.688 / 13.746|

DR10 Dow2:

|通貨|件数|PF|平均R|DD R|
|---|---:|---:|---:|---:|
|AUDUSD|34|0.834 / 0.836|-0.1053 / -0.1040|8.680 / 8.656|
|EURUSD|27|0.252 / 0.254|-0.4780 / -0.4763|12.906 / 12.861|
|GBPUSD|35|0.576 / 0.576|-0.2429 / -0.2429|11.309 / 11.309|
|NZDUSD|31|0.751 / 0.751|-0.1655 / -0.1655|10.404 / 10.404|
|USDCAD|34|0.917 / 0.916|-0.0447 / -0.0454|13.117 / 13.134|
|USDCHF|34|0.908 / 0.907|-0.0516 / -0.0524|7.042 / 7.067|
|USDJPY|30|0.833 / 0.836|-0.1048 / -0.1031|14.560 / 14.514|
|AUDJPY|34|1.116 / 1.116|0.0696 / 0.0696|7.970 / 7.970|
|CHFJPY|32|1.498 / 1.491|0.2757 / 0.2727|7.230 / 7.273|
|EURCHF|30|1.881 / 1.867|0.4631 / 0.4582|4.628 / 4.643|
|EURGBP|29|1.030 / 1.030|0.0170 / 0.0170|7.261 / 7.261|
|EURJPY|30|1.192 / 1.193|0.0975 / 0.0979|4.104 / 4.101|
|GBPCHF|31|0.978 / 0.975|-0.0099 / -0.0110|4.909 / 4.930|
|GBPJPY|29|0.479 / 0.477|-0.2646 / -0.2660|11.914 / 11.951|
|NZDJPY|25|0.802 / 0.798|-0.1082 / -0.1104|8.996 / 9.035|

DR10 Dow3:

|通貨|件数|PF|平均R|DD R|
|---|---:|---:|---:|---:|
|AUDUSD|34|0.773 / 0.775|-0.1454 / -0.1441|9.951 / 9.919|
|EURUSD|25|0.286 / 0.287|-0.5137 / -0.5120|12.843 / 12.800|
|GBPUSD|31|0.549 / 0.549|-0.2600 / -0.2600|10.819 / 10.819|
|NZDUSD|31|0.690 / 0.690|-0.2270 / -0.2270|11.502 / 11.502|
|USDCAD|33|0.878 / 0.877|-0.0783 / -0.0790|10.894 / 10.910|
|USDCHF|29|0.696 / 0.695|-0.1905 / -0.1914|10.440 / 10.462|
|USDJPY|30|0.373 / 0.374|-0.4538 / -0.4522|19.316 / 19.272|
|AUDJPY|32|0.828 / 0.828|-0.1078 / -0.1078|10.178 / 10.178|
|CHFJPY|33|1.102 / 1.097|0.0658 / 0.0629|7.497 / 7.539|
|EURCHF|30|1.718 / 1.704|0.3889 / 0.3840|6.013 / 6.027|
|EURGBP|27|0.927 / 0.927|-0.0438 / -0.0438|6.819 / 6.819|
|EURJPY|30|0.872 / 0.873|-0.0813 / -0.0808|6.184 / 6.179|
|GBPCHF|30|0.624 / 0.623|-0.2077 / -0.2087|10.207 / 10.233|
|GBPJPY|28|0.284 / 0.283|-0.4287 / -0.4302|13.791 / 13.825|
|NZDJPY|23|0.490 / 0.488|-0.3486 / -0.3508|9.116 / 9.162|

USDJPY DR8 Dow3のPF2.034は9年間27件であり、通貨の事後選別による採用根拠にはしない。

## 含み・約定・保有費用の診断

DR8 Dow2 / DR8 Dow3 / DR10 Dow2 / DR10 Dow3順に、固定費用期末未決済は3/1/4/3件、含みは+5.107/+4.417/+6.852/+7.085R。終値清算補助PFは0.9074/0.8646/0.9550/0.7635であり、未決済を計上しても損益の符号と不採用は変わらない。MTM DDは63.912/75.113/68.584/99.382R。closed DDを口座の最大リスクとみなさない。

同順に初期SL出口は289/290/237/259件（stop_gapを含む）、Dow次始値出口は252/215/228/187件。SLギャップ6/4/4/4件は始値へ悪化約定する。Dow候補にはTPがなく同日TP/SL競合はない。旧RR1比較について同日競合・ギャップを含め旧明細と完全一致した。数量は1通貨1ポジションで初期R正規化のみ、注文ロット・口座換算・証拠金制約は未実装。

|条件|平均保有日|最長日|2倍metadata PF|仮想1pip/日追加の固定費用PF|
|---|---:|---:|---:|---:|
|DR8 Dow2|27.20|157|0.8742|0.6283|
|DR8 Dow3|33.51|247|0.8352|0.5718|
|DR10 Dow2|27.62|141|0.9100|0.6384|
|DR10 Dow3|33.56|245|0.7242|0.4798|

固定1.4とmetadataは通貨により大小が逆転するので、この比較だけを一律コスト増加とは呼ばない。2倍metadataは同一明細から追加cost/riskを控除する単調ストレスであり採用基準を変えない。1pip/日は実swap値ではなく事前固定の仮想費用。保有日数は実開始時刻差の24時間単位切捨てで、日中SLの正確な約定時刻は不明。実ブローカーのロール時刻・3倍日・受取swapを再現していない。期末未決済の追加日次費用は正式PFに入らず、上記補助PFも決済明細に対する診断である。

swap、実slippage、変動spread、Bid/Ask約定、commission、税・口座換算・資金拘束・通貨相関・tick内約定順序は未実装。日足保存時刻の市場タイムゾーン/TradingView配信足との一致も未確認。研究モデルの結果から実運用承認はしない。

## 引継ぎ

変更したファイルは本audit.mdのみ。次担当へ渡せるのは凍結仕様と再現可能な不採用結果・上記限界。4候補とも研究基準不合格なのでPine移植対象はない。出口の別定義へ変更する場合は別実験ID・結果前固定・既閲覧ラベル維持が必要。本実験で後半を実行しなかったことはその期間が真の未使用であることを意味しない。

## 読取専用・独立照合の再現コマンド

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
@'
from pathlib import Path
text=Path('docs/quant_organization/experiments/dinapoli_3x3_daily_dow_exit_20260910/audit.md').read_text(encoding='utf-8')
code=text.rsplit('<!-- audit_python_begin -->',1)[1].split('```python\n',1)[1].split('\n```',1)[0]
exec(compile(code,'independent_dow_audit','exec'))
'@ | python -
```

<!-- audit_python_begin -->
```python
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timedelta
import hashlib,json,math
import numpy as np
ROOT=Path.cwd(); OUT=ROOT/'agent_runs/dinapoli_3x3_daily_dow_exit_20260910/completed'
OLD=ROOT/'agent_runs/dinapoli_3x3_daily_20260909/completed'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
iso=lambda n:(datetime(1970,1,1)+timedelta(seconds=int(n))).isoformat()
ts=lambda s:int((datetime.fromisoformat(s)-datetime(1970,1,1)).total_seconds())
# Reuse only the preceding independent auditor's numeric and entry-state code.
# No research implementation is imported or called by this verifier.
oldtext=(ROOT/'docs/quant_organization/experiments/dinapoli_3x3_daily_20260909/audit.md').read_text(encoding='utf-8')
oldcode=oldtext.rsplit('<!-- audit_python_'+'begin -->',1)[1].split('```python\n',1)[1].split('\n```',1)[0]
exec(oldcode[oldcode.index('def close('):oldcode.index('cache={};')])
exec(oldcode[oldcode.index('def features('):oldcode.index('groups=defaultdict')])
p=read(OUT/'protocol.json'); result=read(OUT/'results.json'); hashes=read(OUT/'code_input_hashes.json')
assert p==read(ROOT/'docs/quant_organization/experiments/dinapoli_3x3_daily_dow_exit_20260910/protocol.json')
for path,digest in hashes['sha256'].items(): assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
assert datetime.fromisoformat(hashes['frozen_before_simulation_utc'])<datetime.fromisoformat(result['completed_at_utc'])
assert read(OUT/'data_manifest.json')==read(OLD/'data_manifest.json')
cache={}; daily=prefix=statechecks=tradeschecked=baselinechecks=aggregatechecks=0

def dow(o,n):
 events=[]
 # First determine each strict pivot in its bounded window; attach confirmation time.
 for k in range(n,len(o)-n):
  for col,sign in [(1,1),(2,-1)]:
   value=o[k,col]
   if all(sign*(value-o[j,col])>0 for j in range(k-n,k+n+1) if j!=k): events.append((k+n,k,sign,value))
 confirmed=defaultdict(list)
 for e in events: confirmed[e[0]].append(e)
 highs=[]; lows=[]; state=0; states=[]
 for i in range(len(o)):
  for _,k,sign,value in confirmed[i]:
   (highs if sign==1 else lows).append(value)
  if len(highs)>1 and len(lows)>1:
   dh=highs[-1]-highs[-2]; dl=lows[-1]-lows[-2]
   if dh>0 and dl>0: state=1
   elif dh<0 and dl<0: state=-1
  states.append(state)
 return np.array(states),np.array(events,dtype=float).reshape((-1,4))

for m in read(OUT/'data_manifest.json'):
 s=m['symbol']; z=dict(np.load(OUT/(s+'_daily.npz'))); old=dict(np.load(OLD/(s+'_daily.npz')))
 for key in z: np.testing.assert_array_equal(z[key],old[key])
 digest=hashlib.sha256(b''.join(z[key].tobytes() for key in ['dates','ohlc','raw_first_timestamp','raw_last_timestamp','source_counts'])).hexdigest()
 assert digest==m['daily_sha256']; assert iso(z['dates'][-1])=='2026-08-28T00:00:00'
 assert np.all(z['raw_last_timestamp'][:-1]+60<=z['raw_first_timestamp'][1:])
 stat=Path(m['path']).stat(); assert {'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}==m['after']
 cache[s]=(z,m); daily+=len(z['dates'])
 for length in [2,3]:
  states,events=dow(z['ohlc'],length); saved=dict(np.load(OUT/f'{s}_dow{length}.npz'))
  np.testing.assert_array_equal(states,saved['states']); np.testing.assert_array_equal(events,saved['events'])
  for cut in [len(states)//3,2*len(states)//3,len(states)]:
   a,b=dow(z['ohlc'][:cut],length); np.testing.assert_array_equal(a,states[:cut]); np.testing.assert_array_equal(b,events[events[:,0]<cut]); prefix+=1
  mirrored=z['ohlc'][:,[0,2,1,3]]*-1
  a,_=dow(mirrored,length); np.testing.assert_array_equal(a,-states)
  statechecks+=1
 print('DAILY_DOW_VERIFIED',s,len(z['dates']),flush=True)

groups=defaultdict(list)
for rec in result['rows']:
 s=rec['symbol']; z,m=cache[s]; o=z['ohlc']; dates=z['dates']; pip=m['pip']; cost=1.4 if rec['cost_case']=='fixed_1p4' else m['metadata_spread_pips']
 candidate=next(x for x in p['search_space'] if x['id']==rec['candidate']); isdow=candidate['exit']=='dow'
 b,e=np.searchsorted(dates,list(map(ts,p['periods'][rec['period']]))); sig=signals(o,candidate,b,e)
 states=dow(o,candidate['pivot'])[0] if isdow else None
 for cut in [b+(e-b)//3,b+2*(e-b)//3,e]:
  assert signals(o[:cut],candidate,b,cut)=={k:v for k,v in sig.items() if k<cut}; prefix+=1
 actual=read(OUT/rec['artifact']); rows=actual['trades']; pos=pending=scheduled=None
 expected=[]; curve=[]; ignored=cancelled=0; realized=0.; openr=0.
 for i in range(b,e):
  exited=False
  if pending is not None:
   si,side,start,stop=pending; pending=None; entry=o[i,0]; risk=side*(entry-stop)
   if risk<=0 or not math.isfinite(risk): cancelled+=1
   else:
    pos=dict(signal_index=si,direction=side,prep_index=start,entry_index=i,entry=entry,stop=stop,target='none' if isdow else entry+side*risk,risk_pips=risk/pip,cost_pips=cost)
    armed=False; armindex=-1
  if pos is not None:
   side=pos['direction']; op,hi,lo,cl=o[i]; stop=pos['stop']; reason=None
   if side*(op-stop)<=0: price=op; reason='stop_gap'
   elif isdow and scheduled is not None: price=op; reason='dow_next_open'
   elif not isdow and side*(op-pos['target'])>=0: price=pos['target']; reason='target_gap_capped'
   else:
    sh=lo<=stop if side==1 else hi>=stop
    th=False if isdow else (hi>=pos['target'] if side==1 else lo<=pos['target'])
    if sh: price=stop; reason='both_stop_first' if th else 'stop'
    elif th: price=pos['target']; reason='target'
   if reason:
    netp=side*(price-pos['entry'])/pip-cost
    trade=dict(pos,exit_index=i,exit_price=price,reason=reason,net_pips=netp,net_r=netp/pos['risk_pips'],holding_calendar_days=int((z['raw_first_timestamp'][i]-z['raw_first_timestamp'][pos['entry_index']])//86400))
    if isdow: trade.update(dow_signal_index=scheduled if scheduled is not None else -1,dow_armed=armed,dow_armed_index=armindex)
    expected.append(trade); realized+=trade['net_r']; pos=scheduled=None; exited=True
   elif isdow:
    if not armed and states[i]==side: armed=True; armindex=i
    elif armed and states[i]==-side and states[i-1]!=states[i]: scheduled=i
  openr=(pos['direction']*(o[i,3]-pos['entry'])/pip-cost)/pos['risk_pips'] if pos else 0.
  curve.append([dates[i],realized,realized+openr])
  if i in sig:
   if pos is None and not exited:
    side,start,stop=sig[i]; pending=(i,side,start,stop)
   else: ignored+=1
 assert len(rows)==len(expected),(rec['artifact'],len(rows),len(expected))
 for a,v in zip(rows,expected):
  for key,value in v.items():
   if isinstance(value,str): assert a[key]==value,(key,a[key],value)
   else: close(a[key],value,key)
  si,en,ex=[a[k] for k in ['signal_index','entry_index','exit_index']]
  assert en==si+1 and b<=si<en<=ex<e
  assert a['signal_available_timestamp']==iso(z['raw_last_timestamp'][si]+60)
  assert a['entry_raw_first_timestamp']==iso(z['raw_first_timestamp'][en])
  assert a['exit_trading_date']==iso(dates[ex])
  assert z['raw_last_timestamp'][si]+60<=z['raw_first_timestamp'][en]
  if isdow and a['dow_signal_index']>=0:
   di=a['dow_signal_index']; assert di==ex-1 and en<=di
   assert states[di]==-a['direction'] and states[di-1]!=states[di]
   assert any(states[j]==a['direction'] for j in range(en,di))
   assert a['dow_signal_available_timestamp']==iso(z['raw_last_timestamp'][di]+60)
   assert z['raw_last_timestamp'][di]+60<=z['raw_first_timestamp'][ex]
  tradeschecked+=1
 np.testing.assert_allclose(np.load(OUT/(rec['artifact'][:-5]+'_equity.npz'))['equity'],curve,rtol=2e-10,atol=2e-9)
 diag=actual['diagnostics']
 for key,value in dict(open_count=int(pos is not None),open_net_r=openr,cancelled_at_open=cancelled,ignored_signals=ignored,pending_at_end=int(pending is not None),signal_count=len(sig)).items(): close(diag[key],value,key)
 if isdow:
  close(diag['pending_dow_exit_at_end'],int(scheduled is not None))
  if pos is not None:
   for key,value in pos.items():
    if isinstance(value,str): assert diag['open_position'][key]==value
    else: close(diag['open_position'][key],value,key)
   close(diag['open_position']['dow_armed'],armed); close(diag['open_position']['dow_armed_index'],armindex)
   close(diag['open_position']['mark_price'],o[e-1,3])
   close(diag['open_position']['holding_calendar_days'],int((z['raw_last_timestamp'][e-1]+60-z['raw_first_timestamp'][pos['entry_index']])//86400))
 for sm in [actual['summary'],rec]:
  verify_stats(rows,sm); close(sm['closed_drawdown_r'],dd([t['net_r'] for t in rows])); close(sm['mtm_drawdown_r'],dd(np.diff(np.r_[0,np.array(curve)[:,2]])))
  verify_stats(rows+([{'net_r':openr}] if pos else []),sm['boundary_force_close_sensitivity'])
  verify_stats([{'net_r':t['net_r']-t['holding_calendar_days']/t['risk_pips']} for t in rows],sm['hypothetical_1pip_per_calendar_day_cost'])
 if not isdow:
  oldname=rec['artifact'].replace('_rr1__','__'); previous=read(OLD/oldname)
  assert rows==previous['trades']; assert diag==previous['diagnostics']; baselinechecks+=1
 groups[(rec['candidate'],rec['period'],rec['cost_case'])].append((rows,actual['summary'],curve))

for (cid,period,cost),items in groups.items():
 rows=[t for rr,_,_ in items for t in rr]; summary=result['totals'][cid][period][cost]; verify_stats(rows,summary)
 changes=defaultdict(float); mtm=defaultdict(float)
 for rr,ss,curve in items:
  for t in rr: changes[t['exit_trading_date']]+=t['net_r']
  previous=0.
  for date,_,value in curve: mtm[date]+=value-previous; previous=value
 close(summary['closed_drawdown_r'],dd([changes[k] for k in sorted(changes)])); close(summary['mtm_drawdown_r'],dd([mtm[k] for k in sorted(mtm)]))
 close(summary['largest_single_symbol_closed_drawdown_r'],max(ss['closed_drawdown_r'] for _,ss,_ in items))
 close(summary['profitable_symbols'],sum(ss['net_r']>0 for _,ss,_ in items))
 close(summary['open_count'],sum(ss['open_count'] for _,ss,_ in items)); close(summary['open_net_r'],sum(ss['open_net_r'] for _,ss,_ in items))
 verify_stats(rows+[{'net_r':ss['open_net_r']} for _,ss,_ in items if ss['open_count']],summary['boundary_force_close_sensitivity'])
 verify_stats([{'net_r':t['net_r']-t['holding_calendar_days']/t['risk_pips']} for t in rows],summary['hypothetical_1pip_per_calendar_day_cost'])
 days=[t['holding_calendar_days'] for t in rows]
 for key,value in dict(mean_holding_days=np.mean(days),median_holding_days=np.median(days),p95_holding_days=np.percentile(days,95),max_holding_days=max(days)).items(): close(summary[key],value,key)
 assert summary['exit_reasons']==dict(Counter(t['reason'] for t in rows)); aggregatechecks+=1
g=p['acceptance_gates']
for cid,periods in result['decisions'].items():
 for period,cases in periods.items():
  for cost,decision in cases.items():
   s=result['totals'][cid][period][cost]; threshold=g[period]; failed=[]
   if s['trades']<threshold['minimum_trades']: failed.append('insufficient_trades')
   if not(s['pf']>=threshold['minimum_pf'] if s['pf'] is not None else s['gross_profit_r']>0): failed.append('pf')
   if s['average_net_r'] is None or s['average_net_r']<=threshold['minimum_average_net_r_exclusive']: failed.append('average_net_r')
   if s['closed_drawdown_r']>g['maximum_aggregate_closed_drawdown_r']: failed.append('aggregate_drawdown')
   if s['largest_single_symbol_closed_drawdown_r']>g['maximum_single_symbol_closed_drawdown_r']: failed.append('single_symbol_drawdown')
   if s['profitable_symbols']<threshold['minimum_profitable_symbols']: failed.append('profitable_symbols')
   assert failed==decision['failures'] and decision['passed']==(not failed)
eligible=[cid for cid,periods in result['decisions'].items() if all(d['passed'] for d in periods['training'].values())]
def rank(cid):
 s=list(result['totals'][cid]['training'].values())
 return (-min(x['pf'] if x['pf'] is not None else float('inf') for x in s),-min(x['average_net_r'] for x in s),max(x['closed_drawdown_r'] for x in s),cid)
selected=min(eligible,key=rank) if eligible else None
assert selected==result['selected_for_validation']==read(OUT/'selection_before_validation.json')['selected']
selectedfinal=selected if selected is not None and all(d['passed'] for d in result['decisions'][selected]['validation'].values()) else None
assert selectedfinal==result['selected_for_final']==read(OUT/'selection_before_final.json')['selected']
assert result['passed_research_gates']==([selectedfinal] if selectedfinal is not None and all(d['passed'] for d in result['decisions'][selectedfinal]['final_confirmation'].values()) else [])
assert set(r['period'] for r in result['rows'])==({'training'}|({'validation'} if selected else set())|({'final_confirmation'} if selectedfinal else set()))
print(json.dumps(dict(status='VERIFIED',daily_bars=daily,pivot_state_checks=statechecks,full_state_checks=len(result['rows']),saved_trade_rows=tradeschecked,prefix_checks=prefix,aggregate_checks=aggregatechecks,baseline_checks=baselinechecks,selected=selected,passed=result['passed_research_gates'])),flush=True)
for (cid,period,cost),items in groups.items():
 if cost!='metadata_spread': continue
 rows=[t for rr,_,_ in items for t in rr]
 stress=[{'net_r':t['net_r']-t['cost_pips']/t['risk_pips']} for t in rows]
 print(json.dumps(dict(candidate=cid,period=period,diagnostic_2x_metadata=stats(stress))),flush=True)
```
<!-- audit_python_end -->
