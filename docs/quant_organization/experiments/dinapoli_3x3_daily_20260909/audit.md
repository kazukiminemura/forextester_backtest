# 独立検証・監査結果

- 実験ID / 担当 / 次担当: `dinapoli_3x3_daily_20260909` / 独立検証 / 研究責任者。
- 判定: **不採用**（`VERIFIED_REJECTED_TRAINING_ONLY`）。
- 状態: 原データ日足再集約・別状態実装・約定・集計・事前判定を照合済み。実注文なし。
- 本担当の編集範囲: このレポートのみ。研究コード・採用条件・原履歴は変更していない。
- 完了日: 2026-09-10 JST。

## 入力と凍結

入力は同ディレクトリのhypothesis.md、protocol.json、data_inventory.md。出力は `agent_runs/dinapoli_3x3_daily_20260909/completed/`。
実行前の識別子は `code_input_hashes.json`、凍結実時刻は2026-09-09 14:59:47.928342 UTC。結果完了時刻は15:00:01.815533 UTC。
protocolの00:00記載はdate-levelの登録表記であり、実際の凍結時刻の根拠には使わない。

|入力|SHA256|
|---|---|
|research_dinapoli_3x3_daily.py|b1cf94d2f3c3937a681b267ddce30b8f39d126fab3874bb105dda0b89704fff5|
|protocol.json|8abe23959bfc27db11d0497600bdee6e22db171bd47d0b6728e68d42758976dc|
|hypothesis.md|f20697eebdc724411093d4c033d5b39ab262dcc7c83ca3f0e8ef7ef810423c96|

コード依存2ファイルのSHAも保存値と現ファイルを照合した。各原Bars.datは使用範囲のSHA、日足OHLC、実開始/終了時刻、構成本数まで再確認した。
使用範囲SHAはデータ担当の「全有効レコードSHA」と対象バイト範囲が異なるため、同じハッシュであるとは扱わない。

結果前に、初期hypothesisの日曜足保持・費用条件が責任者指定と不一致であることを指摘した。研究担当が日曜→月曜統合、固定1.4pips/metadataへ修正した後に凍結・実行された。
さらにhypothesis本体のSHA追加、M1末尾の完成時刻+60秒を使うassertを結果前に依頼し、最終コードへ反映された。結果を見てルールや基準を変えた修正はない。

## 事前判定と期間

採用候補はDR8、DR10の2個。単純DMAクロスは比較専用。推進8/10本・初回から再反転まで8/10本の隣接条件を独立判定し、結果後の追加探索はしない。
trainingは2010-01-01〜2019-01-01未満、validationは2019-01-01〜2023-01-01未満、finalは2023-01-01〜2026-08-31未満。

両費用でtraining/validationそれぞれ100件以上、PF>=1.10、平均net R>0、全通貨closed DD<=20R、各通貨closed DD<=10R。training+validationの利益通貨は10/15以上。
選抜された候補だけfinalを評価し、30件以上、PF>=1.05、平均net R>0、利益通貨8/15以上、同じDD条件を課す。
実際は両候補がtraining不合格なのでvalidation/finalの戦略成績を評価していない。これは欠落ではなく事前の停止条件どおり。
価格品質確認のため日足データ自体は後区分も読取済みであり、過去のプロジェクト研究でも閲覧済み。真の未使用holdoutとは呼ばない。

## 結果

以下は2010〜2018のtraining。Rは各取引の初期価格リスクによる正規化単位であり口座金額ではない。最大DDは同日決済を合算するclosed R曲線。

|条件|費用|件数|勝率|PF|平均net R|net R|最大DD R|最大個別DD R|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|単純クロス|固定1.4|2,035|50.57%|0.9986|-0.00068|-1.387|54.487|18.726|
|単純クロス|metadata|2,035|50.57%|0.9981|-0.00095|-1.929|54.520|18.839|
|DR8|固定1.4|604|47.68%|0.8932|-0.05645|-34.098|48.224|16.244|
|DR8|metadata|604|47.68%|0.8926|-0.05682|-34.321|48.406|16.244|
|DR10|固定1.4|506|50.40%|0.9962|-0.00188|-0.953|28.151|16.242|
|DR10|metadata|506|50.40%|0.9954|-0.00230|-1.165|28.249|16.197|

両候補とも両費用のPF・平均net R・全通貨DD・個別DDが不合格。件数不足による不合格ではない。利益通貨数はDR8が7/15、DR10が8/15だが、training+validationの利益通貨ゲートは後区分未評価のため適用していない。
DR10はDR8より改善するが、単純クロスと比べ勝率・PF・平均Rが上がった証拠はない。
DR8→DR10の固定費用PFは0.8932→0.9962、取引数604→506であり、隣接設定に安定した利益は確認できない。

### 通貨別 training

各セルの2値は固定1.4 / metadata。勝率・net R・含みを含む未丸め値はresults.jsonのrowsと個別JSONに保存されている。

DR8:

|通貨|件数|PF|平均R|最大DD R|
|---|---:|---:|---:|---:|
|AUDUSD|48|0.587 / 0.589|-0.2604 / -0.2589|15.354 / 15.303|
|EURUSD|39|0.616 / 0.618|-0.2384 / -0.2368|11.285 / 11.224|
|GBPUSD|45|0.544 / 0.544|-0.2959 / -0.2959|16.244 / 16.244|
|NZDUSD|33|1.475 / 1.475|0.1932 / 0.1932|3.318 / 3.318|
|USDCAD|37|0.531 / 0.531|-0.3070 / -0.3077|13.343 / 13.368|
|USDCHF|51|0.740 / 0.739|-0.1498 / -0.1507|10.599 / 10.642|
|USDJPY|38|1.085 / 1.088|0.0408 / 0.0423|6.106 / 6.091|
|AUDJPY|46|1.519 / 1.519|0.2057 / 0.2057|3.137 / 3.137|
|CHFJPY|41|0.847 / 0.842|-0.0831 / -0.0859|10.267 / 10.343|
|EURCHF|28|0.463 / 0.461|-0.3692 / -0.3717|11.276 / 11.336|
|EURGBP|37|1.029 / 1.029|0.0142 / 0.0142|7.212 / 7.212|
|EURJPY|44|1.426 / 1.427|0.1755 / 0.1759|4.039 / 4.036|
|GBPCHF|46|1.282 / 1.279|0.1234 / 0.1224|4.066 / 4.076|
|GBPJPY|33|0.931 / 0.928|-0.0358 / -0.0372|9.142 / 9.177|
|NZDJPY|38|1.211 / 1.206|0.0953 / 0.0931|6.129 / 6.157|

DR10:

|通貨|件数|PF|平均R|最大DD R|
|---|---:|---:|---:|---:|
|AUDUSD|36|0.624 / 0.626|-0.2320 / -0.2306|13.258 / 13.221|
|EURUSD|28|0.327 / 0.329|-0.5093 / -0.5076|16.242 / 16.197|
|GBPUSD|40|0.730 / 0.730|-0.1565 / -0.1565|10.187 / 10.187|
|NZDUSD|34|0.979 / 0.979|-0.0105 / -0.0105|7.166 / 7.166|
|USDCAD|36|0.982 / 0.981|-0.0090 / -0.0097|7.198 / 7.212|
|USDCHF|38|0.791 / 0.789|-0.1171 / -0.1179|7.279 / 7.298|
|USDJPY|33|1.036 / 1.039|0.0176 / 0.0192|5.155 / 5.141|
|AUDJPY|39|2.193 / 2.193|0.3726 / 0.3726|3.049 / 3.049|
|CHFJPY|38|1.089 / 1.083|0.0425 / 0.0397|5.194 / 5.249|
|EURCHF|23|0.426 / 0.423|-0.4049 / -0.4078|9.313 / 9.381|
|EURGBP|31|1.038 / 1.038|0.0185 / 0.0185|8.108 / 8.108|
|EURJPY|35|1.316 / 1.317|0.1363 / 0.1368|4.044 / 4.041|
|GBPCHF|35|1.478 / 1.475|0.1931 / 0.1921|3.053 / 3.060|
|GBPJPY|31|1.370 / 1.366|0.1560 / 0.1545|6.064 / 6.083|
|NZDJPY|29|1.862 / 1.854|0.2999 / 0.2977|4.046 / 4.056|

AUDJPYのDR10はPF2.193だが9年間39件に過ぎず、通貨事後選別は本実験の採用対象外。これだけを採用候補とはしない。

## 因果性・約定・数量・費用の確認

独立した指標計算・状態遷移・ポジション処理で90組すべてを再走し、6,290保存明細の方向/準備開始/シグナル/入口/出口/SL/TP/理由/net Rが一致した。
DMAは当日から3〜5本前の終値平均。ATRはシグナル日完成情報で確定する。上位足・学習器・ピボットは使わない。
実行対象区間の3つのprefixでシグナル/SLが同一である270チェックを確認した。将来の足が前半シグナルへ影響する証拠はない。

原M1から15通貨66,096日足を独立再集約し、すべてのOHLC・日付・実始終時刻・構成本数が一致。
SundayをMondayへ統合した後にも終了日を適用し、15通貨とも最終日足が2026-08-28であることを確認。
signal raw最終M1時刻+60秒<=entry raw初回時刻、翌観測日足始値への約定、1通貨1ポジション、決済当日の再シグナル抑止を照合した。
日足ラベルは実約定時刻ではなく、月曜ラベルの始値が日曜夕方にあるケースも適切に保存されている。

SL/TPの価格距離は全明細でgross 1:1。SL飛越えは当日始値、TP飛越えはTP価格へ制限し、同日両接触はSL優先。
DR8はstop gap4件/target gap2件/両接触SL1件、DR10は4/4/1件（各費用で同一取引集合）。
価格ギャップで損失は1R超になり得る。費用は損益から往復控除され、買い・売りの実Bid/Ask注文再現ではない。
実ロット・通貨換算・資金拘束をモデル化していないため、R合算とDDを口座収益・口座DDとして解釈できない。
勝率はnet R>0で計算し、建値を金銭上の利益にしていない。

DR8の期末未決済2件は固定費用で+0.2605R、DR10の1件は-0.2338R。終値強制決済の補助PFはDR8=0.8941、DR10=0.9953で、未決済除外によって不採用結論が逆転していない。
固定費用MTM DDはDR8=48.934R、DR10=30.224R。合否用closed DDとの違いも保存・照合した。

## 感度と未実装費用

固定1.4pipsとmetadataは通貨により大小が逆転するため、この2本だけを一律の費用増加ストレスとは呼ばない。
監査診断として既存metadata明細の往復費用のみ2倍へ引上げ、取引集合を変えずnet Rからcost/riskを追加控除した。
これは採用条件の変更・新たな最適化ではなく、既評価trainingに対する単調な追加費用診断である。

|条件|2倍metadata PF|平均net R|
|---|---:|---:|
|単純クロス|0.9758|-0.01226|
|DR8|0.8753|-0.06664|
|DR10|0.9759|-0.01221|

DR8/DR10の決済済み最長保有はどちらも1,240暦日、平均17.27/19.60日。時間決済なしと広い構造SLにより年単位の保有が起こる。
swap0・slippage0・commission0は実ブローカーの費用がゼロという証拠ではない。日跨ぎswap、変動spread、実滑り、通貨換算、証拠金・同時保有制約、tick順序を含む執行は未実装。
保存時刻帯が不明で、TradingView配信元の日足と同一であることも未確認。

## 実行証拠と引継ぎ

研究担当から本番実行exit0・最終RESULT_JSONを受領し、実ファイルresults.jsonと完了時刻を読取確認した。独立確認時に該当研究Pythonプロセスが残っていないことも確認した。
独立照合はexit0で `VERIFIED / daily_bars=66096 / saved_trade_rows=6290 / full_state_checks=90 / prefix_checks=270 / aggregate_checks=6 / selected=[] / passed=[]`。
関連テストは本担当も `python -m pytest tests/test_dinapoli_3x3_daily.py -q -p no:cacheprovider` を実行し、21 passed・exit0。
これらは本凍結研究モデルの再現性を支える。実運用やTradingView上のコンパイル・挙動の承認はしない。

研究本番の再現コマンドは `$env:PYTHONPATH='src'; python -m scripts.research_dinapoli_3x3_daily --output agent_runs/dinapoli_3x3_daily_20260909/reproduction`。
既存ディレクトリは上書きせずエラーとなる設計。初回の出力はcompleted/。再実行時は未作成の出力名を使う。
独立再計算は下のPython本文を読み取り専用で実行する。レポート以外の担当ファイル作成を避けるため、検証プログラムも本レポートへ保存した。

次担当へ渡せる範囲は、凍結仕様・再現可能な不採用結果・上記限界。合格候補0のためPine移植工程へ進めない。
改善研究を行うなら別実験ID・新しい事前仮説と基準が必要で、今回閲覧した期間を未使用へ戻せない。

## 独立照合の再現コマンド

本リポジトリで以下を実行。元データ、コード、成果物を読取るだけでファイルを書き込まない。

~~~powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
@'
from pathlib import Path
text=Path('docs/quant_organization/experiments/dinapoli_3x3_daily_20260909/audit.md').read_text(encoding='utf-8')
code=text.rsplit('<!-- audit_python_begin -->',1)[1].split('```python\n',1)[1].split('\n```',1)[0]
exec(compile(code,'audit_embedded_verifier','exec'))
'@ | python -
~~~

<!-- audit_python_begin -->
```python
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib,json,math
import numpy as np
ROOT=Path.cwd()
OUT=ROOT/'agent_runs/dinapoli_3x3_daily_20260909/completed'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
p=read(OUT/'protocol.json'); results=read(OUT/'results.json')
assert p==read(ROOT/'docs/quant_organization/experiments/dinapoli_3x3_daily_20260909/protocol.json')
hashes=read(OUT/'code_input_hashes.json')
for name,digest in hashes['sha256'].items(): assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
epoch=datetime(1970,1,1)
ts=lambda s:int((datetime.fromisoformat(s)-epoch).total_seconds())
iso=lambda n:(epoch+timedelta(seconds=int(n))).isoformat()
def close(a,b,label='value'):
 if a is None or b is None: assert a is b,(label,a,b)
 else: assert math.isclose(float(a),float(b),rel_tol=2e-10,abs_tol=2e-9),(label,a,b)
def dd(changes):
 peak=balance=worst=0.
 for n in changes:
  balance+=n; peak=max(peak,balance); worst=max(worst,peak-balance)
 return worst
def stats(rows):
 values=[r['net_r'] for r in rows]; wins=[v for v in values if v>0]; losses=[v for v in values if v<0]
 return dict(trades=len(values),wins=len(wins),losses=len(losses),win_rate_pct=100*len(wins)/len(values) if values else None,
 pf=sum(wins)/-sum(losses) if losses else None,gross_profit_r=sum(wins),gross_loss_r=-sum(losses),
 net_r=sum(values),average_net_r=sum(values)/len(values) if values else None)
def verify_stats(rows,actual):
 for k,v in stats(rows).items(): close(v,actual[k],k)
cache={}; aggregate_checks=daily_count=trade_count=prefix_count=signal_checks=0
# Independent source-to-day OHLC aggregation: no research loader or strategy imports.
from forextester_backtest.data import HistoryRepository
repo=HistoryRepository(p['history_directory'])
for m in read(OUT/'data_manifest.json'):
 s=m['symbol']; z=np.load(OUT/(s+'_daily.npz')); a=np.memmap(m['path'],mode='r',dtype='<f8',offset=4,shape=(repo.summary(s).bar_count,6))
 before=Path(m['path']).stat()
 raw=a[(a[:,0]>=ts(p['warmup_start'])/86400+25569)&(a[:,0]<ts(p['periods']['final_confirmation'][1])/86400+25569)]
 assert hashlib.sha256(raw).hexdigest()==m['source_sha256']
 rawsec=np.rint((raw[:,0]-25569)*86400).astype('int64')
 rawdays,inverse=np.unique(rawsec//86400,return_inverse=True)
 converted=np.array([d+int((epoch+timedelta(days=int(d))).weekday()==6) for d in rawdays],dtype='int64')
 labels=converted[inverse]; dates,first,counts=np.unique(labels,return_index=True,return_counts=True)
 last=first+counts-1; o=np.empty((len(dates),4))
 for j,(b,e) in enumerate(zip(first,last)):
  o[j]=[raw[b,1],max(raw[b:e+1,3]),min(raw[b:e+1,4]),raw[e,2]]
 keep=dates*86400<ts(p['periods']['final_confirmation'][1])
 expected={'dates':dates[keep]*86400,'ohlc':o[keep],'raw_first_timestamp':rawsec[first][keep],'raw_last_timestamp':rawsec[last][keep],'source_counts':counts[keep]}
 for k,v in expected.items(): np.testing.assert_array_equal(z[k],v,err_msg=s+'/'+k)
 assert iso(z['dates'][-1])=='2026-08-28T00:00:00'
 assert np.all(z['raw_last_timestamp'][:-1]+60<=z['raw_first_timestamp'][1:])
 assert before.st_size==Path(m['path']).stat().st_size and before.st_mtime_ns==Path(m['path']).stat().st_mtime_ns
 cache[s]=(dict(z),m); daily_count+=len(z['dates'])
 print('DAILY_VERIFIED',s,len(z['dates']),flush=True)
 del a,raw,rawsec,labels
def features(o):
 n=len(o); dma=np.full(n,np.nan); atr=np.full(n,np.nan); tr=[]
 for i in range(n):
  if i>=5: dma[i]=(o[i-5,3]+o[i-4,3]+o[i-3,3])/3
  prev=o[i-1,3] if i else o[i,3]
  tr.append(max(o[i,1]-o[i,2],abs(o[i,1]-prev),abs(o[i,2]-prev)))
  if i==13: atr[i]=sum(tr)/14
  elif i>13: atr[i]=(atr[i-1]*13+tr[i])/14
 return dma,atr
def signals(o,c,b,e):
 dma,atr=features(o); active={}; out={}; n=c['thrust']
 for i in range(max(b,29,n),e):
  events=[]
  if c['kind']=='cross':
   for side in [-1,1]:
    if side*(o[i-1,3]-dma[i-1])<=0 and side*(o[i,3]-dma[i])>0: events.append((side,i-n+1))
  else:
   for side in [-1,1]:
    if side in active and i>active[side][0]+c['expiry']: del active[side]
    value=side*(o[i,3]-dma[i])
    if side not in active:
     if value>0 and all(side*(o[j,3]-dma[j])<0 for j in range(i-n,i)): active[side]=[i,i-n,False]
    elif value<0: active[side][2]=True
    elif value>0 and active[side][2]:
     events.append((side,active[side][1])); del active[side]
  if len(events)==1:
   side,start=events[0]
   stop=(min(o[start:i+1,2])-.1*atr[i]) if side==1 else (max(o[start:i+1,1])+.1*atr[i])
   out[i]=(side,start,stop)
 return out
groups=defaultdict(list); pair_summaries={}
for rec in results['rows']:
 s=rec['symbol']; z,m=cache[s]; o=z['ohlc']; dates=z['dates']; pip=m['pip']; cost=1.4 if rec['cost_case']=='fixed_1p4' else m['metadata_spread_pips']
 c=next(x for x in p['search_space'] if x['id']==rec['candidate'])
 b,e=np.searchsorted(dates,list(map(ts,p['periods'][rec['period']])))
 sig=signals(o,c,b,e); data=read(OUT/rec['artifact']); rows=data['trades']
 # Prefix-invariance at three truncation boundaries in the evaluated period.
 for cut in [b+(e-b)//3,b+2*(e-b)//3,e]:
  assert signals(o[:cut],c,b,cut)=={k:v for k,v in sig.items() if k<cut}
  prefix_count+=1
 # Full independent daily execution over independently generated signals.
 expected=[]; pos=None; pending=None; ignored=cancelled=0; realized=0.; curve=[]
 for i in range(b,e):
  exited=False
  if pending is not None:
   si,side,begin,stop=pending; pending=None; entry=o[i,0]; risk=side*(entry-stop)
   if risk<=0 or not math.isfinite(risk): cancelled+=1
   else: pos=dict(signal_index=si,direction=side,prep_index=begin,entry_index=i,entry=entry,stop=stop,target=entry+side*risk,risk_pips=risk/pip,cost_pips=cost)
  if pos is not None:
   side=pos['direction']; stop=pos['stop']; target=pos['target']; op,hi,lo,cl=o[i]; reason=None
   if side*(op-stop)<=0: price=op; reason='stop_gap'
   elif side*(op-target)>=0: price=target; reason='target_gap_capped'
   else:
    sh=lo<=stop if side==1 else hi>=stop
    th=hi>=target if side==1 else lo<=target
    if sh: price=stop; reason='both_stop_first' if th else 'stop'
    elif th: price=target; reason='target'
   if reason:
    netp=side*(price-pos['entry'])/pip-cost
    expected.append(dict(pos,exit_index=i,exit_price=price,reason=reason,net_pips=netp,net_r=netp/pos['risk_pips']))
    realized+=expected[-1]['net_r']; pos=None; exited=True
  openr=(pos['direction']*(o[i,3]-pos['entry'])/pip-cost)/pos['risk_pips'] if pos else 0.
  curve.append([dates[i],realized,realized+openr])
  if i in sig:
   if pos is None and not exited:
    side,begin,stop=sig[i]; pending=(i,side,begin,stop)
   else: ignored+=1
 assert len(rows)==len(expected),(rec['artifact'],'count',len(rows),len(expected))
 for a,v in zip(rows,expected):
  for k,n in v.items():
   if isinstance(n,str): assert a[k]==n,(k,a[k],n)
   else: close(a[k],n,k)
  si,en,ex=[a[k] for k in ['signal_index','entry_index','exit_index']]
  assert en==si+1 and b<=si<en<=ex<e
  assert a['signal_raw_last_timestamp']==iso(z['raw_last_timestamp'][si])
  assert a['entry_raw_first_timestamp']==iso(z['raw_first_timestamp'][en])
  assert a['signal_available_timestamp']==iso(z['raw_last_timestamp'][si]+60)
  assert z['raw_last_timestamp'][si]+60<=z['raw_first_timestamp'][en]
  assert a['exit_trading_date']==iso(dates[ex])
  close(a['risk_pips'],a['direction']*(a['entry']-a['stop'])/pip)
  close(a['direction']*(a['target']-a['entry'])/pip,a['risk_pips'])
  trade_count+=1
 np.testing.assert_allclose(np.load(OUT/(rec['artifact'][:-5]+'_equity.npz'))['equity'],curve,rtol=2e-10,atol=2e-9)
 diag=data['diagnostics']; close(diag['open_count'],int(pos is not None)); close(diag['open_net_r'],openr)
 for k,v in {'cancelled_at_open':cancelled,'ignored_signals':ignored,'pending_at_end':int(pending is not None),'signal_count':len(sig)}.items(): close(diag[k],v,k)
 verify_stats(rows,data['summary']); verify_stats(rows,rec)
 close(data['summary']['closed_drawdown_r'],dd([r['net_r'] for r in rows]))
 close(data['summary']['mtm_drawdown_r'],dd(np.diff(np.r_[0,np.array(curve)[:,2]])))
 boundary=rows+([{'net_r':openr}] if pos else [])
 verify_stats(boundary,data['summary']['boundary_force_close_sensitivity'])
 groups[(rec['candidate'],rec['period'],rec['cost_case'])].append((rows,data['summary'],curve))
 pair_summaries[(rec['candidate'],rec['period'],rec['cost_case'],s)]=data['summary']
 signal_checks+=1
for (c,period,cost),items in groups.items():
 rows=[r for rr,_,_ in items for r in rr]; total=results['totals'][c][period][cost]; verify_stats(rows,total)
 changes=defaultdict(float); mtm=defaultdict(float)
 for rr,ss,curve in items:
  for r in rr: changes[r['exit_trading_date']]+=r['net_r']
  previous=0.
  for date,_,value in curve: mtm[date]+=value-previous; previous=value
 close(total['closed_drawdown_r'],dd([changes[t] for t in sorted(changes)]))
 close(total['mtm_drawdown_r'],dd([mtm[t] for t in sorted(mtm)]))
 close(total['largest_single_symbol_closed_drawdown_r'],max(s['closed_drawdown_r'] for _,s,_ in items))
 close(total['profitable_symbols'],sum(s['net_r']>0 for _,s,_ in items))
 close(total['open_count'],sum(s['open_count'] for _,s,_ in items))
 close(total['open_net_r'],sum(s['open_net_r'] for _,s,_ in items))
 verify_stats(rows+[{'net_r':s['open_net_r']} for _,s,_ in items if s['open_count']],total['boundary_force_close_sensitivity'])
 aggregate_checks+=1
# Gate and period selection are verified without opening any new evaluation period.
g=p['acceptance_gates']
for c,periods in results['decisions'].items():
 for period,cases in periods.items():
  for cost,decision in cases.items():
   s=results['totals'][c][period][cost]; t=g[period]; fail=[]
   if s['trades']<t['minimum_trades']: fail.append('insufficient_trades')
   if not(s['pf']>=t['minimum_pf'] if s['pf'] is not None else s['gross_profit_r']>0): fail.append('pf')
   if s['average_net_r'] is None or s['average_net_r']<=t['minimum_average_net_r_exclusive']: fail.append('average_net_r')
   if s['closed_drawdown_r']>g['maximum_aggregate_closed_drawdown_r']: fail.append('aggregate_drawdown')
   if s['largest_single_symbol_closed_drawdown_r']>g['maximum_single_symbol_closed_drawdown_r']: fail.append('single_symbol_drawdown')
   if 'minimum_profitable_symbols' in t and s['profitable_symbols']<t['minimum_profitable_symbols']: fail.append('profitable_symbols')
   if period=='validation':
    n=sum(pair_summaries[(c,'training',cost,s)]['net_r']+pair_summaries[(c,'validation',cost,s)]['net_r']>0 for s in p['symbols'])
    close(n,decision['training_plus_validation_profitable_symbols'])
    if n<g['training_plus_validation_minimum_profitable_symbols']: fail.append('joint_profitable_symbols')
   assert fail==decision['failures'] and decision['passed']==(not fail)
  if period=='validation': assert all(x['passed'] for x in periods['training'].values())
  if period=='final_confirmation': assert c in results['selected_for_final']
selection=read(OUT/'selection_before_final.json')
assert selection['selected']==results['selected_for_final']
assert set(results['passed_research_gates'])=={c for c in results['selected_for_final'] if all(x['passed'] for x in results['decisions'][c]['final_confirmation'].values())}
print(json.dumps(dict(status='VERIFIED',daily_bars=daily_count,saved_trade_rows=trade_count,full_state_checks=signal_checks,prefix_checks=prefix_count,aggregate_checks=aggregate_checks,selected=results['selected_for_final'],passed=results['passed_research_gates'])))

for cid in results['totals']:
 rr=[v for v in results['rows'] if v['candidate']==cid and v['cost_case']=='metadata_spread']
 tt=[t for v in rr for t in read(OUT/v['artifact'])['trades']]
 stress=[{'net_r':t['net_r']-t['cost_pips']/t['risk_pips']} for t in tt]
 print(json.dumps({'candidate':cid,'diagnostic_2x_metadata':stats(stress),'max_holding_days':max(t['holding_calendar_days'] for t in tt)}))

```
<!-- audit_python_end -->
