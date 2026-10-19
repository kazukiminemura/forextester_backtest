# ディナポリ3×3日足・Dow転換決済 — 入力再利用確認

- 実験ID / 担当 / 次担当: `dinapoli_3x3_daily_dow_exit_20260910` / quant_data / 研究責任者・研究開発・独立検証。
- 状態: `DATA_READY_WITH_LIMITATIONS`。2026-09-10 JSTの実走で `DATA_REUSE_VERIFIED`、終了コード0。
- 入力: `C:\ForexTester6\data\History`、前実験 `dinapoli_3x3_daily_20260909` の `data_inventory.md` と `agent_runs/dinapoli_3x3_daily_20260909/completed/` の日足NPZ・data_manifest.json。
- 出力・編集範囲: この文書のみ。原Bars.dat / ticks.dat / info.dat、既存成果物への書込なし。外部データ代替なし。実注文なし。
- 再利用可否: 下記の期間・集約・費用・閲覧制約を維持して15通貨の日足を再利用できる。戦略成績・採用判定は本担当の成果に含まない。

## 現状態による照合

HistoryRepositoryを入口とする既存 `scripts/research_dinapoli_3x3_daily.py::load_daily` で、原M1の2009-10-01以上2026-08-31未満を15通貨すべて読み取り専用で再集約した。全66,096日足について、NPZの `dates / ohlc / raw_first_timestamp / raw_last_timestamp / source_counts` の全要素が再集約値と完全一致した。サンプル検査ではない。

原Bars.datのsize・mtime_nsは旧manifestのbefore/afterと一致し、対象範囲の有効M1バイト列SHA256、日足配列SHA256、metadata、件数、端点を含むmanifest全体が旧保存値と完全一致した。source hashはファイル全体や全履歴のhashではなく、上記期間の有効レコード領域のhash。未使用予約領域は対象外。

NPZの読取前後size・mtime_nsも一致。原M1対象範囲の非有限値、非正OHLC、内部OHLC不整合、重複/逆順/分格子外時刻、大きな価格桁断絶は既存loaderの全件検査を再実行して通過。全日足の時刻厳密増加、実開始<=実終了、前足実終了+60秒<=次足実開始も確認した。既存loaderと異なる別集約実装による検証は今回は再実施していない。前実験の独立監査が全66,096日足を別実装で照合済みであることを前実験audit.mdから確認した。

前回凍結の5依存ファイル（旧protocol、hypothesis、research script、data.py、models.py）のSHA256も現ファイルと完全一致した。

- 旧data_manifest.json SHA256: `9a5b64f18ac98257e9991a3e5751cb5d8f3ad88c798f8ad96032b5e8300ecaf2`
- loader SHA256: `b1cf94d2f3c3937a681b267ddce30b8f39d126fab3874bb105dda0b89704fff5`
- data.py SHA256: `bbbe0e0212480ea463726eac437c5262f380a78cd57eeedbde5d55c088d14af0`
- models.py SHA256: `9a815c3b304a5df57dcd4036486b2bd6112f259be0720c75377cc3a44757b8b7`

## 使用可能な日足と指紋

全通貨の日足ラベル端点は2009-10-01〜2026-08-28。2009Q4をウォームアップ、2010-01-01以上2026-08-31未満を研究に使える。後半の使用可否・段階的開示は責任者のprotocolに従う。以下の日足件数はウォームアップ込み。日曜始まり数は採用された日足の実開始曜日が日曜の数で、打切りにより捨てた8/30のstubを含まない。

|通貨|日足数|日曜始まり|NPZ bytes|NPZ mtime_ns|NPZファイルSHA256|
|---|---:|---:|---:|---:|---|
|AUDUSD|4407|876|107778|1788965988689290900|0cbac98b71b62a9f75f487b1f434a294caa0b863dcd3d23ad7d459f61cfcf442|
|EURUSD|4410|877|112317|1788965989428239000|27f66618086862e09550669f24d6c200ef71fd9e583fe0de902e7445bed78d0a|
|GBPUSD|4410|876|111571|1788965990162657800|c08c566a44ad53b4ac2f9642e5545881f24a716164cc6c2c6f2a9009e20963e2|
|NZDUSD|4409|874|105387|1788965990888057400|359ef1a98ac79799eed237706b1b116640179978f4c198b2c401a9d6b31ca2c1|
|USDCAD|4409|877|110575|1788965991609707800|b82b3c1497e982617af49e1d311c685da65ed1d748add12ed285bde0e912da28|
|USDCHF|4399|872|85728|1788965992312927600|d639cfb47be0f03efcd1d3c2b7cd3957d6bfff54a040555caceb235d0527bac5|
|USDJPY|4408|879|95413|1788965993071704300|53da584f04613ecb90ae847c7ff205c12b9aced99371071757e1ca6d63f9d472|
|AUDJPY|4408|876|93660|1788965993802095800|59c5974e66450d0ab2ce0cb400454d019da1e3907dd8c1dc68f44deb9ddad912|
|CHFJPY|4401|872|86329|1788965994589023000|df66719566d064ed76a571284f54ba65736d4772d97b0c51922f5c29d37ccef2|
|EURCHF|4410|877|109320|1788965995322648200|c5192698dcf2500e0689cfb32276cbf18973115d518aa77e1100c005cd8ad00d|
|EURGBP|4407|877|103253|1788965996047216300|045b89bc3d6f7b108454ec334b4c90107579a225630d5e5e0bc832bcf6043bec|
|EURJPY|4401|872|87095|1788965996777955700|06332c8ff740b3e918d1cfc2e7af9fef78e02957a78eebff54d43ec3567546a2|
|GBPCHF|4407|874|112308|1788965997497659100|943d32889291db37ef46bef9c4fecf9bcab7d2a58b732579b648a22a45e140ac|
|GBPJPY|4402|872|88355|1788965998248000600|e52db848de782c6773f9f1ecbd5acd06c23de8e9ddac397a21b069caffcce78b|
|NZDJPY|4408|875|94670|1788965998964484100|7a2ab6e83915678f4ba5284f7bffe39f48c89f384944a430ce460cd53c77c763|

## 集約時刻とGBPJPY打切り

保存日時はタイムゾーンなし。UTCという市場時刻の根拠はなく、スクリプト中のUTC付与は整数epoch計算上の表現に限る。NY17時やTradingView配信元の日足との同一性は未確認。

日曜の保存日付を翌月曜の取引日ラベルへ移し、実時刻順の先頭O・最大H・最小L・末尾Cを使う。日足完成は末尾M1の実開始時刻+60秒。ラベル月曜00:00を完成時刻には使わない。次足始値約定はその足の実開始時刻を使用する。欠けた日やM1を補間しない。

全通貨の原保存時刻2026-08-31以降を切り、日曜変換後も8/31以上を切る。旧manifest・再集約とも `excluded_end_label_days=1`。8/30の日曜stubは次の月曜ラベルになるため全通貨で除外され、最終日足は8/28。

HistoryRepositoryのM1端点サンプル再確認では、GBPJPYの2026-08-31 00:00始値が2.16791、2026-09-01 00:00始値が216.435で、旧台帳の桁異常が現原データにも残る。これは対象範囲外の2点サンプル確認であり、対象範囲外全件の再監査ではない。100倍補正や異常日だけの削除・接続は行わない。

## 費用・価格・未確認事項

現metadataは旧manifestと全15通貨で一致。lot_size=100000、ApplyCommission=0、CommPerLot=0、SwapLong/Short=0は保存設定であり、実取引費用ゼロの根拠ではない。JPYクオートpip=0.01、その他pip=0.0001が本研究の定義。spreadはmodels.pyの `spread_points * 10**(-decimals)` をpipで割る。各通貨spreadは旧台帳の1.1〜1.8pipsを維持する。固定1.4pipsは別途置く実験仮定。クオート通貨はmodels.pyの6文字FX銘柄末尾3文字による。異なるクオートの金額を無換算で口座損益として合算しない。

Bars.datにはBid/Ask識別フィールドがなく、旧台帳のEURUSD/GBPJPY各1分のBid一致はサンプル証拠のみ。今回はtick全件やそのサンプルを再検査していない。実際の変動spread、slippage、口座換算、swapは未確認。Dow転換までの長期保有では実日数に応じたswapが重要な未計上要因となるため、保有期間を残し、別途費用仮定と感応度を仕様に固定する必要がある。

原M1欠損の診断値・各通貨全履歴開始/件数は旧台帳を参照する。本再利用チェックは全履歴の再監査ではない。使用期間のSHA一致により旧診断と同じ入力であることを確認した。旧台帳の1分超ギャップは正常週末・休場を含み、配信予定表がないので全てを真の欠落とは分類できない。日足日付集合も通貨間で異なる。補間や日付の事後選別はしない。

2010–2018年は前回戦略の成績を閲覧済み。2019年以降は前回日足戦略の成績が未評価でも、日足品質指標・OHLCや別研究で既閲覧。今回も全期間の集約配列を読み取った。真の未使用期間とは保証しない。

## 再現コマンドと引継ぎ

リポジトリ直下、Python/NumPy既存環境。下記を実走して終了コード0、最終 `DATA_REUSE_VERIFIED` / 15通貨 / 66096本を確認した。対象データやNPZは書き換えない。

```powershell
$env:PYTHONPATH='src'; @'
from pathlib import Path
from scripts.research_dinapoli_3x3_daily import load_daily,sha,iso
from forextester_backtest.data import HistoryRepository
import numpy as np,json
p=Path('agent_runs/dinapoli_3x3_daily_20260909/completed'); r=HistoryRepository()
manifest=json.loads((p/'data_manifest.json').read_text()); total=0
frozen=json.loads((p/'code_input_hashes.json').read_text())['sha256']
assert all(sha(Path(f))==h for f,h in frozen.items())
for m in manifest:
 s=m['symbol']; f=p/f'{s}_daily.npz'; before=f.stat(); d,current=load_daily(r,s,'2009-10-01','2026-08-31')
 assert current==m, s+' source/metadata/manifest changed'
 with np.load(f,allow_pickle=False) as z:
  for attr,key in [('dates','dates'),('ohlc','ohlc'),('first','raw_first_timestamp'),('last','raw_last_timestamp'),('counts','source_counts')]:
   assert np.array_equal(getattr(d,attr),z[key]),(s,key)
 assert before.st_size==f.stat().st_size and before.st_mtime_ns==f.stat().st_mtime_ns
 assert np.all(d.first<=d.last) and np.all(d.last[:-1]+60<=d.first[1:])
 assert np.all(np.diff(d.dates)>0) and np.isfinite(d.ohlc).all()
 sunday=int(np.sum(((d.first//86400+3)%7)==6)); total+=len(d.dates)
 print(json.dumps({'symbol':s,'n':len(d.dates),'first':iso(d.dates[0]),'last':iso(d.dates[-1]),'sunday_open_bars':sunday,'npz_bytes':before.st_size,'npz_mtime_ns':before.st_mtime_ns,'npz_sha256':sha(f),'bars_stat_equal':current['before']==m['before'],'source_hash_equal':current['source_sha256']==m['source_sha256'],'all_daily_arrays_equal':True}),flush=True)
print(json.dumps({'status':'DATA_REUSE_VERIFIED','pairs':len(manifest),'daily_bars':total,'manifest_sha256':sha(p/'data_manifest.json'),'frozen_dependencies_equal':True}),flush=True)
'@ | python -
```

GBPJPY異常端点確認（実走終了コード0）:

```powershell
$env:PYTHONPATH='src'; @'
from forextester_backtest.data import HistoryRepository
from datetime import datetime
from dataclasses import asdict
import json
r=HistoryRepository()
for dt in [datetime(2026,8,31),datetime(2026,9,1)]:
 print(json.dumps([asdict(x) for x in r.bars('GBPJPY',dt,dt)],default=str))
'@ | python -
```

次担当に渡せるのは上記15通貨の検証一致した研究用日足入力。Dowスイング確定の未来参照防止、保有中の転換状態、決済時刻・価格、期末未決済の評価は研究・独立検証担当が今回の新仕様として確認する。
