# FX月利5%研究：再利用データ台帳

調査日2026-10-09、quant_data。状態 `DATA_READY_WITH_LIMITATIONS`。
対象はUSDJPY/EURUSD/GBPUSD。元金100万円・損失10万円停止・月利5%という依頼条件を記録するが、本書は候補仕様や戦略成績・採用判断を作成しない。
編集責任は本書のみ。原履歴・旧成果物・実装は不変、新ダウンロード・API・実注文なし。

## 再利用可能な入力

主データ源は `C:/ForexTester6/data/History`。端点・有効件数・設定は `HistoryRepository.summary/metadata` で今回再確認した。

1. 原M1は各通貨の `Bars.dat`。旧YTT実験に独立した全M1 NPZキャッシュがあるわけではない。
2. 再利用M5は `agent_runs/bb_alternatives_2020_2025_20260925/<symbol>_features.npz`。
   `times` は元時計を1970年からの秒で数値化した配列、`features[:, :4]` はOHLC。15列の残り特徴量は新条件へ暗黙流用しない。
3. M1完全性maskは `agent_runs/yosuga_channel_20261003/completed/<symbol>_complete_m5.npz` の `complete`。同通貨M5の行と一対一で対応する。
4. 入力固定の照合先はM5ディレクトリの `data_manifest.json` と、旧最終 `agent_runs/ytt_profit_feasibility_20261009/run_manifest.json` の `inputs`。

旧最終run manifest自体の今回SHA256は `7ea844440746a5fd4f91c7c7f5caf016ceaa0fa09706d87a8b08d307496e2914`。
`first_run_before_m1_open_fix` は初回無効成果物なので参照入力・正しい約定時刻の根拠にしない。

## 今回の確認範囲

軽量監査は終了コード0。保存M5・完全性mask・info.datの全bytes SHAを各3通貨で再計算し、**9/9一致**。
元Bars.datはsize/mtime_nsが旧manifestと3通貨すべて一致。今回、元Bars全bytes SHAを再計算していない。stat一致だけで内容完全一致を証明しない。
今回はM1/M5価格の全件再検査をせず、API端点・配列形状・mask長・mask件数を確認した。tickはAPI端点と件数のみ。

同日旧実験の[データ台帳](../ytt_profit_feasibility_20261009/data_inventory.md)では、原Barsを含む12 SHA一致、2019-12〜2025末の元M1全6,788,346件のOHLC・時刻検査、全M5再集約とmask一致が検証済み。
その過去検査を再利用する。新実験で全件再走した結果とは区別する。旧台帳とprotocolも読取確認した。

|通貨|原M1件数|保存M5件数・列数|完全M5件数|
|---|---:|---:|---:|
|USDJPY|8,534,100|455,085 × 15|446,773|
|EURUSD|8,567,792|455,004 × 15|445,417|
|GBPUSD|8,680,197|454,932 × 15|447,550|

3通貨共通の原M1範囲は2003-05-06 00:00〜2026-09-07 23:59。
再利用M5は2019-12-01 22:00〜2025-12-31 21:55。2019-12を初期化に用い、2020-01-01以上2026-01-01未満を評価可能。
旧検査で選択M1の非有限・非正価格・OHLC包絡違反・重複・逆転・分グリッド外は0件。
間隔60秒超はUSDJPY 8,948、EURUSD 10,386、GBPUSD 7,996。休日・週末・その他欠損の全分類はしていない。

|通貨|cache SHA256|mask SHA256|info.dat SHA256|
|---|---|---|---|
|USDJPY|a0ea23715fdc88187195661181b402f3c05b480d0403eb2e42c5b64b2f144866|f00e8b1c1aea9a1052bf85a02f645d59632f497bd66e42f2a2f4ac9fda90dd55|cea2c8b470c145f236577f466937e8c5b04a17960ac5a4f281769338b65b38c4|
|EURUSD|e2026fa0e136eef4a20fbab8098492e2f63fc251eee38be6eef782634ca2fe42|2e4f6db4c69371d65d12c403c08b2b9a6604cce46e0c27108246a4ffb1808295|2bf533cbaad2715e47cdb477de21c3e894bf61430a7d6ee82130f9f54fe31541|
|GBPUSD|7cf11d7c8f98e00f9b64f57fd1136af2873a7a7cfc9f01866e1b2113728dbc9c|6733d4e83fb7003f4a59e00681b736671066d80da7d1f78c19b84b840eec14c7|fd4a6244c76ef686a52e43d9f773b77354e506fbbd8adadc08f2b81dc8dfdf31|

旧確認済み原Bars SHAはUSDJPY `31fc474177e6b2235dbd6a46760d5f428d53de3bc864120677647f651b1828a7`、EURUSD `a7c97f167fb1b0bb016872f73796d1870b68286395b9a5818a797301065d016c`、GBPUSD `573be0820fb6ea2147266084bbec85bb3824b0a7e0eb9032edf10bf4d3d3d601`。新実走が原M1へ依存する場合は実走側でSHAを固定する。

## 時刻・集約・約定時刻の制約

`HistoryRepository` はOLE日時をtimezoneなしdatetimeへ変換する。保存時計のUTC/JST offset・DSTは未確定。
M15/H1/H4は元時計00:00アンカー、開始時刻ラベル。確定可用時刻は開始+幅。集約APIは不完全bucketを保持し、`bars(end=...)` は終端を包含する。
W/Dを追加する場合も元時計の曜日・日境界定義を事前固定し、TradingView配信境界と同一とは仮定しない。

特にM1の先頭欠損があるbucketでは、ラベル時点にその始値が観測されたとは限らない。
旧最終実装 `scripts/research_ytt_profit_feasibility.py:actual_open_times/raw_open_metadata` は原M1から実最初観測時刻と境界一致maskを得る。
M15ラベルに実M1がある件数は旧固定結果でUSDJPY 151,148/151,740、EURUSD 151,002/151,718、GBPUSD 151,121/151,716。
欠損先頭を架空の境界始値で約定させない。新実装が異なる時間幅を使う場合、旧helperの900秒既定を無条件流用しない。

M5完全性、上位足完成、前足状態の配布、欠損中のエントリー停止・保有評価・exitは候補仕様に明記する。
元時計月別の損益を「日本時間の月別」と表示しない。市場カレンダー照合・全tick約定検証は未実施。

## 価格側・費用・換算

|通貨|tick|pip定義|spread points / pips|lot_size|quote通貨|
|---|---:|---:|---:|---:|---|
|USDJPY|0.001|0.01|12 / 1.2|100,000|JPY|
|EURUSD|0.00001|0.0001|11 / 1.1|100,000|USD|
|GBPUSD|0.00001|0.0001|14 / 1.4|100,000|USD|

現物info.datのBrokerはAdvanced Data Feed、ApplyCommission=0、CommPerLot=0、SwapLong/Short=0。
spreadは設定points×tickで、歴史的実測spreadではない。pipは既存FX研究定義、lotはinfo.dat、quoteはAPIの銘柄末尾3文字定義に基づく。
OHLCがBid/Ask/中値のどれかは未確定。手数料・swap設定0も実運用費用0の証拠ではない。slippageは仮定と実測を区別する。
新研究の費用ケースは結果前に固定する。旧0.2pip片側slippageやswap除外を新仕様へ自動適用しない。

円口座を扱うならUSDJPY単独はquote=JPYで直接計算可能。EURUSD/GBPUSDのUSD損益を足すには事前固定のUSDJPY換算時刻・欠損時の処理が必要。
`MarginCurrency` とquote通貨を混同せず、等Rや等pip合算を円口座利益と呼ばない。数量下限・step・証拠金・実口座契約仕様は別途証拠が必要。

## 2026保存記録と閲覧状況

既存 `agent_runs/bb3_context_timing_20260909/completed/data_manifest.json` を読取確認。
3通貨とも2023-08-01 00:00〜2026-09-07 23:55のM5集約記録があり、件数はUSDJPY 230,927、EURUSD 231,432、GBPUSD 231,123。
今回このmanifest記載の2026配列の現物SHA・価格・構成M1完全性は検証していない。
原履歴の2026端点は現APIで確認済みだが、2026価格全件監査をした意味ではない。

2020〜2025は繰返し探索・閲覧済み。2026も上記旧研究で使用されており、真の未使用holdoutを保証できない。
新条件で計算するだけでは未使用データに変わらない。新仕様の記述的評価用に2020–2025再利用可、2026拡張は追加品質確認を要する。

## 再現コマンド

リポジトリルートのPowerShell。今回の軽量監査と同じ検査。戦略結果は計算しない。

```powershell
$env:PYTHONPATH='src'
@'
import json,hashlib
from pathlib import Path
from dataclasses import asdict
from forextester_backtest.data import HistoryRepository
import numpy as np
r=HistoryRepository(); b=Path('agent_runs/bb_alternatives_2020_2025_20260925'); c=Path('agent_runs/yosuga_channel_20261003/completed')
old=Path('agent_runs/ytt_profit_feasibility_20261009/run_manifest.json')
meta={x['symbol']:x for x in json.loads((b/'data_manifest.json').read_text())}
frozen={x['symbol']:x for x in json.loads(old.read_text())['inputs']}
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for s in ('USDJPY','EURUSD','GBPUSD'):
 q=meta[s]; p=Path(q['raw_path']); st=p.stat()
 paths={'cache_sha256':b/(s+'_features.npz'),'mask_sha256':c/(s+'_complete_m5.npz'),'metadata_sha256':p.parent/'info.dat'}
 hashes={k:sha(v) for k,v in paths.items()}
 assert hashes['cache_sha256']==frozen[s]['cache_sha256'] and hashes['mask_sha256']==frozen[s]['mask_sha256'] and hashes['metadata_sha256']==q['metadata_sha256']
 assert st.st_size==q['raw_stat']['bytes'] and st.st_mtime_ns==q['raw_stat']['mtime_ns']
 with np.load(paths['cache_sha256'],allow_pickle=False) as z:t=z['times']; shape=z['features'].shape
 with np.load(paths['mask_sha256'],allow_pickle=False) as z:mask=z['complete'];assert len(mask)==len(t)
 print(json.dumps(dict(symbol=s,summary=asdict(r.summary(s)),metadata=asdict(r.metadata(s)),hashes=hashes,cache_shape=shape,first=str(np.datetime64(int(t[0]),'s')),last=str(np.datetime64(int(t[-1]),'s')),complete=int(mask.sum())),default=str))
later=json.loads(Path('agent_runs/bb3_context_timing_20260909/completed/data_manifest.json').read_text())
print('2026_EXISTING_MANIFEST',json.dumps([{k:q[k] for k in ('symbol','bars','first','last','time_ohlc_sha256')} for q in later if q['symbol'] in ('USDJPY','EURUSD','GBPUSD')]))
print('PRIOR_FREEZE_SHA256',sha(old))
'@ | python -
```

次担当は研究責任者・研究開発。適用期間・足の完全性・実最初観測時刻・口座換算と費用を候補仕様へ固定する。
