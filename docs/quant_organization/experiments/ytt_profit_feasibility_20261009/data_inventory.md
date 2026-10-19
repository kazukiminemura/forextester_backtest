# YTT利益実現可能性調査：データ台帳

調査日 2026-10-09。担当 quant_data。状態 `DATA_READY_WITH_LIMITATIONS`。
担当文書は本書のみ。原履歴・保存キャッシュ・戦略・Pineは変更していない。
本書は入力品質・利用可能性の報告であり、戦略成績、月300万円の実現性、採用判定を示さない。

## 入力と適用期間

主データ源 `C:/ForexTester6/data/History`。`HistoryRepository.summary/metadata` で現物の端点、件数、設定を確認した。
利用候補は USDJPY/EURUSD/GBPUSD、2019-12をウォームアップ、2020-01-01以上2026-01-01未満を評価範囲とする。
これは利用可能期間であり、研究担当の学習・検証期間の凍結そのものではない。

1. 保存M5: `agent_runs/bb_alternatives_2020_2025_20260925/<symbol>_features.npz`。
   `times` は保存時計を1970年からの秒で表す配列、`features[:, :4]` はOpen/High/Low/Close。残り特徴量は今回YTT条件へ無条件流用しない。
2. 構成M1完全性: `agent_runs/yosuga_channel_20261003/completed/<symbol>_complete_m5.npz` の `complete`。
3. 識別子根拠: 前者の `data_manifest.json`、後者の `run_manifest.json` の `inputs`。
4. 原履歴直接API: `HistoryRepository().bars(symbol, start, end, timeframe='15m')`、`'1h'`、`'4h'`。
   `bars(end=...)` は終端包含であり、半開期間の切断は呼出側で必要。原APIは不完全bucketも保持する。

3通貨共通の保存M5は2019-12-01 22:00〜2025-12-31 21:55、対応元M1の末尾は21:58。
全原履歴の開始は2003-05-06 00:00、末尾は2026-09-07 23:59。2026年の価格品質は今回の検査範囲外。
GBPJPYは既知の2026-08-31桁異常を伴うため対象に含めない。

## 今回の全件検査

Python読取監査は終了コード0。原Bars.dat・info.dat・保存M5・完全性maskの全bytes SHA256を3通貨で再計算し、既存manifestと **12/12一致**。
原M1の **2019-12-01以上2026-01-01未満、合計6,788,346件を全件検査**した。
全履歴の価格品質検査ではない。tickは件数・端点のみで、サンプル価格検査も全件価格検査も行っていない。

|通貨|全M1件数|選択M1件数|保存M5件数|完全M5|M1間隔60秒超|最大間隔秒|
|---|---:|---:|---:|---:|---:|---:|
|USDJPY|8,534,100|2,263,374|455,085|446,773|8,948|259,260|
|EURUSD|8,567,792|2,261,333|455,004|445,417|10,386|259,260|
|GBPUSD|8,680,197|2,263,639|454,932|447,550|7,996|259,260|

選択M1の非有限値・非正OHLC・OHLC包絡違反・高値<安値・重複時刻・逆転・60秒グリッド外は全通貨で0件。
元M1から独立に全保存M5を再集約し、時刻とOHLCが完全一致。完全M5 maskも全件一致した。
gapには週末・祝日・その他欠損が混在し、全gapを市場カレンダーと照合していない。休場と断定しない。

|通貨|観測M15 / 完全M15|観測H1 / 完全H1|観測H4 / 完全H4|
|---|---:|---:|---:|
|USDJPY|151,740 / 145,410|37,939 / 34,045|9,807 / 7,007|
|EURUSD|151,718 / 144,440|37,936 / 33,515|9,805 / 6,840|
|GBPUSD|151,716 / 146,152|37,935 / 34,465|9,805 / 7,369|

この表は保存M5から計算したbucket数で、別保存M15/H1/H4の検査ではない。
完全とはbucket境界から所定数の連続M5があり、全構成M5のM1が充足すること。
不完全bucketを除くと隣接データの間隔が空く。欠落を連続バーと誤認しない。
不完全足保持・除外、gap時のピボット状態、上位足の有効期限は結果を見る前に仕様化する。

## SHA256

|通貨|対象|再計算したSHA256|
|---|---|---|
|USDJPY|Bars.dat|31fc474177e6b2235dbd6a46760d5f428d53de3bc864120677647f651b1828a7|
|USDJPY|info.dat|cea2c8b470c145f236577f466937e8c5b04a17960ac5a4f281769338b65b38c4|
|USDJPY|M5 cache|a0ea23715fdc88187195661181b402f3c05b480d0403eb2e42c5b64b2f144866|
|USDJPY|complete mask|f00e8b1c1aea9a1052bf85a02f645d59632f497bd66e42f2a2f4ac9fda90dd55|
|EURUSD|Bars.dat|a7c97f167fb1b0bb016872f73796d1870b68286395b9a5818a797301065d016c|
|EURUSD|info.dat|2bf533cbaad2715e47cdb477de21c3e894bf61430a7d6ee82130f9f54fe31541|
|EURUSD|M5 cache|e2026fa0e136eef4a20fbab8098492e2f63fc251eee38be6eef782634ca2fe42|
|EURUSD|complete mask|2e4f6db4c69371d65d12c403c08b2b9a6604cce46e0c27108246a4ffb1808295|
|GBPUSD|Bars.dat|573be0820fb6ea2147266084bbec85bb3824b0a7e0eb9032edf10bf4d3d3d601|
|GBPUSD|info.dat|fd4a6244c76ef686a52e43d9f773b77354e506fbbd8adadc08f2b81dc8dfdf31|
|GBPUSD|M5 cache|7cf11d7c8f98e00f9b64f57fd1136af2873a7a7cfc9f01866e1b2113728dbc9c|
|GBPUSD|complete mask|6733d4e83fb7003f4a59e00681b736671066d80da7d1f78c19b84b840eec14c7|

## 時刻・価格・費用

`data.py` はOLE日時をtimezoneなしdatetimeへ変換する。元時計のUTC/JST offsetやDSTは未確定。
数値の1970秒表現もUTCの証拠ではない。M15/H1/H4は保存時計00:00アンカーの整数bucket、ラベルは足開始。
利用可能時刻は開始+足幅。未確定H1/H4をM15へ遡及配布しない。TradingView/OANDAのH4境界と一致する保証はない。

|通貨|decimals / tick|pip定義|設定spread points / 価格 / pips|lot_size|quote通貨|
|---|---|---|---|---:|---|
|USDJPY|3 / 0.001|0.01|12 / 0.012 / 1.2|100,000|JPY|
|EURUSD|5 / 0.00001|0.0001|11 / 0.00011 / 1.1|100,000|USD|
|GBPUSD|5 / 0.00001|0.0001|14 / 0.00014 / 1.4|100,000|USD|

設定の根拠は現物info.datと `models.InstrumentMetadata`。pipは既存FX研究の定義で、metadataに独立したpipキーはない。
全3通貨でBroker=`Advanced Data Feed`、ApplyCommission=0、CommPerLot=0、SwapLong/SwapShort=0。
これらは静的設定であり、実口座の過去手数料・スプレッド・スワップがゼロまたは固定だった証拠ではない。
spreadはpoints×10^(-decimals)。slippageの履歴根拠はなく、研究仮定と実測を分ける。

OHLCのBid/Ask/中値は現資料で未確定。tick APIにはbid/askがあるが、OHLCとの全照合は今回していない。
全tick件数はUSDJPY 422,111,274、EURUSD 462,163,350、GBPUSD 448,346,540。価格品質・tick SHAは未検査。
quote通貨は6文字銘柄の末尾3文字というAPI定義。`MarginCurrency` はquote通貨ではない。
USD建て損益をJPY口座利益へ合算するには時点を固定したUSDJPY換算が必要。等R・等pipを円利益と呼ばない。
費用込みの固定spread近似研究は可能だが、実約定・実口座月利益の再現という位置付けにはできない。

## 既閲覧期間と再利用境界

2020–2025はBB・よすが等の既存研究で閲覧済み。2010–2026にも旧探索記録があり、新しいルールを計算しても未使用holdoutにはならない。
真の未使用期間を今回確定できていない。2026年を追加する場合はその範囲の価格品質確認が別途必要。

`scripts/research_yosuga_channel.py` の `structure` はgapリセット・厳密pivot・dual pivot除外等を持ち、現YTT Pineと同じ信号仕様とは限らない。
OHLCとmaskの再利用と、旧売買条件の再利用を区別する。信号・約定・費用・期末会計の判定は研究／独立検証担当が行う。

## 再現コマンド

リポジトリルートのPowerShell。今回実行した監査と同じ読取処理。終了コード0、上記12 hash・全M5・完全mask一致。

```powershell
$env:PYTHONPATH='src'
@'
import json,hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
import numpy as np
from forextester_backtest.data import HistoryRepository,_to_ole
r=HistoryRepository(); b=Path('agent_runs/bb_alternatives_2020_2025_20260925'); c=Path('agent_runs/yosuga_channel_20261003/completed')
qmap={q['symbol']:q for q in json.loads((b/'data_manifest.json').read_text())}
imap={q['symbol']:q for q in json.loads((c/'run_manifest.json').read_text())['inputs']}
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for s in ['USDJPY','EURUSD','GBPUSD']:
 q=qmap[s]; raw=Path(q['raw_path']); cache=b/(s+'_features.npz'); mask=c/(s+'_complete_m5.npz'); summary=r.summary(s); meta=r.metadata(s)
 hashes={'raw_sha256':sha(raw),'metadata_sha256':sha(raw.parent/'info.dat'),'cache_sha256':sha(cache),'mask_sha256':sha(mask)}
 assert all(hashes[k]==q[k] for k in ['raw_sha256','metadata_sha256','cache_sha256']) and hashes['mask_sha256']==imap[s]['mask_sha256']
 with np.load(cache,allow_pickle=False) as z:t=z['times'];p=z['features'][:,:4]
 with np.load(mask,allow_pickle=False) as z:complete=z['complete']
 assert complete.shape==t.shape
 a=np.memmap(raw,mode='r',dtype='<f8',offset=4,shape=(summary.bar_count,6))
 lo,hi=np.searchsorted(a[:,0],[_to_ole(datetime(2019,12,1)),_to_ole(datetime(2026,1,1))]); a=a[lo:hi]
 mt=np.rint((a[:,0]-_to_ole(datetime(1970,1,1)))*86400).astype(np.int64); dt=np.diff(mt)
 bucket=mt//300*300; ix=np.r_[0,np.flatnonzero(np.diff(bucket))+1]; ends=np.r_[ix[1:],len(a)]
 rebuilt=np.column_stack([a[ix,1],np.maximum.reduceat(a[:,3],ix),np.minimum.reduceat(a[:,4],ix),a[ends-1,2]])
 assert np.array_equal(t,bucket[ix]) and np.array_equal(p,rebuilt)
 mfull=(ends-ix==5)&(mt[ix]==bucket[ix])&(mt[ends-1]==bucket[ix]+240)
 assert np.array_equal(mfull,complete)
 errors=int(np.sum((a[:,3]<np.maximum(a[:,1],a[:,2]))|(a[:,4]>np.minimum(a[:,1],a[:,2]))|(a[:,3]<a[:,4])))
 counts={}
 for width in (900,3600,14400):
  bucket=t//width*width; st=np.r_[0,np.flatnonzero(np.diff(bucket))+1]; en=np.r_[st[1:],len(t)]; pre=np.r_[0,np.cumsum(~complete)]
  full=(en-st==width//300)&(t[st]==bucket[st])&(t[en-1]==bucket[st]+width-300)&(pre[en]-pre[st]==0)
  counts[str(width)]={'observed':len(st),'complete_m1':int(full.sum())}
 print(json.dumps(dict(symbol=s,summary=asdict(summary),metadata=asdict(meta),hashes=hashes,m1=len(a),m5=len(t),m5_complete=int(complete.sum()),m1_nonfinite=int(np.sum(~np.isfinite(a))),m1_nonpositive=int(np.sum(a[:,1:5]<=0)),ohlc_errors=errors,duplicates=int(np.sum(dt==0)),reversed=int(np.sum(dt<0)),off_minute=int(np.sum(mt%60!=0)),gaps=int(np.sum(dt>60)),max_gap=int(dt.max()),aggregate_counts=counts,all_m5_ohlc_and_mask_match=True),default=str))
'@ | python -
```

次担当は研究責任者・研究開発。時間足完全性と費用仮定を事前固定して、独立検証可能な入力として利用する。
