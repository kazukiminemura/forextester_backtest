# 日足アルゴリズム再設計 — データ再利用台帳

- 実験ID / 担当 / 次担当: `daily_edge_reset_20260910` / quant_data / 研究開発・独立検証。
- 状態: `DATA_READY_WITH_LIMITATIONS`。2026-09-10 JST、下記再現コマンドの実走終了コード0、最終 `DATA_REUSE_VERIFIED`。
- 主データ源: `C:\ForexTester6\data\History`。HistoryRepositoryを入口に既存 `scripts/research_dinapoli_3x3_daily.py::load_daily` を読取専用利用。
- 再利用先: `agent_runs/dinapoli_3x3_daily_20260909/completed/` の15通貨 `*_daily.npz` と `data_manifest.json`。
- 編集責任: この文書のみ。原Bars.dat / ticks.dat / info.dat、旧NPZ、他担当ファイルは変更していない。戦略成績・採用判定は本担当の成果に含まない。

## 今回の確認範囲

原M1の2009-10-01以上2026-08-31未満を全15通貨について再読込・再集約し、66,096日足の `dates / ohlc / raw_first_timestamp / raw_last_timestamp / source_counts` の全要素が旧NPZに完全一致した。サンプル検査ではない。使用M1領域のSHA256、件数、端点、原ファイルsize/mtime_ns、metadata、日足SHA256を含むmanifest全体が旧保存値と一致した。NPZ読取前後statも一致。

この実走で既存loaderの使用M1全件の非有限値・非正OHLC・内部OHLC整合・重複/逆順/分格子外時刻・終値比0.5未満/1.5超の桁断絶チェックを通過。全日足の時刻厳密増加、実開始<=実終了、前足実終了+60秒<=次足実開始も通過した。前回凍結5ファイルのSHA256は現在も一致した。

今回の再集約は旧loaderを再使用した照合であり、別実装による独立再集約を今回やり直したとは扱わない。前実験 `dinapoli_3x3_daily_20260909/audit.md` には全66,096日足の別実装照合完了が記録されており、その文書を今回確認した。全履歴・全tickの再監査ではない。

- data_manifest.json SHA256: `9a5b64f18ac98257e9991a3e5751cb5d8f3ad88c798f8ad96032b5e8300ecaf2`
- load_dailyを含む旧research script SHA256: `b1cf94d2f3c3937a681b267ddce30b8f39d126fab3874bb105dda0b89704fff5`
- data.py SHA256: `bbbe0e0212480ea463726eac437c5262f380a78cd57eeedbde5d55c088d14af0`
- models.py SHA256: `9a815c3b304a5df57dcd4036486b2bd6112f259be0720c75377cc3a44757b8b7`

使用M1領域SHAは原ファイル全体や全履歴のSHAではなく、期間内の有効48バイトレコード列で、ヘッダ・予約スロットを含まない。NPZファイルSHAは前回 `dinapoli_3x3_daily_dow_exit_20260910/data_inventory.md` の15行と今回全行一致。旧日足内部配列SHAは現在一致を確認したmanifestの各 `daily_sha256` に保存されている。

## 使用可能期間・件数・費用設定

全通貨の保存日足ラベルは2009-10-01〜2026-08-28。2009Q4からのデータを指標初期化に使い、研究責任者指定で全候補共通250観測本のウォームアップを要求する。このため2010年初めから直ちに取引できるわけではない。暦日250日ではなく、その通貨に実在する足数で判定する。具体的な初回シグナル・初回約定可能日は新実装側で確認する。

|通貨|使用領域M1件数|ウォームアップ込み日足数|metadata spread pips|
|---|---:|---:|---:|
|AUDUSD|6,278,131|4,407|1.2|
|EURUSD|6,305,142|4,410|1.1|
|GBPUSD|6,309,023|4,410|1.4|
|NZDUSD|6,292,217|4,409|1.4|
|USDCAD|6,300,640|4,409|1.5|
|USDCHF|6,200,016|4,399|1.5|
|USDJPY|6,294,949|4,408|1.2|
|AUDJPY|6,310,405|4,408|1.4|
|CHFJPY|6,195,935|4,401|1.8|
|EURCHF|6,287,846|4,410|1.7|
|EURGBP|6,301,384|4,407|1.4|
|EURJPY|6,201,223|4,401|1.3|
|GBPCHF|6,296,309|4,407|1.6|
|GBPJPY|6,204,197|4,402|1.8|
|NZDJPY|6,296,645|4,408|1.7|

使用M1件数は集約後に除外される2026-08-30の日曜stubを含む。日足件数にはそのstubを含まない。過去の各通貨全履歴開始・全有効件数・ギャップ数は、前実験 `dinapoli_3x3_daily_20260909/data_inventory.md` を参照する。今回は全履歴端点を改めて全通貨取得していない。

15通貨info.datは旧manifestに一致し、Broker=Advanced Data Feed、lot_size=100000、LotCurrency/BaseCurrency=先頭3文字、ApplyCommission=0、CommPerLot=0、SwapLong/Short=0。pipはJPYクオート0.01、その他0.0001という研究定義であり、`models.py` の spread_points×10^(-decimals) をpipで割ると上表になる。全対象で1pip=10 metadata points。クオート通貨は6文字FX銘柄末尾3文字から決定する。Rや異なるクオートのpips合算を口座通貨金額と同一視しない。

metadata spreadは保存された固定Bid/Ask幅の設定であり、片道手数料ではない。Bidベースの入口・出口価格差に対して、一定spreadモデルならロングは入口Ask、ショートは出口Askの調整に対応する1 spreadを往復全体から引く。これを入口・出口で各1 spread引くと2 spreadになる。新実験で往復1.4pipsや追加slippageを置くなら、保存metadataから観測された実約定費用とは分けた仮定であることと、片道/往復の加算単位をprotocolに明記する。

手数料ゼロ・swapゼロは保存設定であり、実ブローカーのゼロ費用を示さない。対象metadataとHistory配下ファイル名の確認から利用できる実日次・方向別swap時系列は確認できず、現loaderもそれを返さない。実swapを反映した検証とは呼べない。仮想pips/暦日保有費用は感応度であり、通貨別金利差、三倍日、売買方向を再現する実swapではない。長期保有するルールでは保有暦日数を必ず残す必要がある。

## 日足境界・品質上の制約

保存日時のタイムゾーン/DST根拠はmetadataにない。epoch算術中のUTC付与を配信時間帯の証明に使わない。NY17時区切り、TradingViewの特定ブローカー日足との同一性は未確認。

日曜の保存日付を翌月曜ラベルへ移して、実時刻順の先頭O、最大H、最小L、末尾Cを集約する。足完成は末尾M1の実開始+60秒。月曜ラベル00:00を完成時刻として使わず、次日足始値約定には次足の実開始を使う。欠けた日付やM1は補間しない。各通貨の実在日付集合は異なる。

全通貨で原保存時刻2026-08-31以上を打ち切り、日曜を翌月曜に移した後にも同じ終端を適用する。各manifestの `excluded_end_label_days=1` は今回も一致し、8/30 stubを捨てて最終日足8/28を維持する。対象範囲外のGBPJPYの2点サンプルでは、8/31 00:00始値2.16791、9/1 00:00始値216.435が現在も残る。これは範囲外全件監査ではない。桁異常を100倍補正したり異常日のみ削って接続したりしない。

原M1の時計上ギャップには正常週末・休場が含まれる。配信稼働予定がないので真の欠落と休場の完全分類は未確認。使用領域SHA一致により、旧台帳の当範囲ギャップ診断と同じ入力であることを確認した。小さな誤配信・実市場価格との一致を保証しない。

Bars.datにはBid/Ask識別フィールドがない。旧台帳のEURUSD/GBPJPY各1分のtick Bid OHLC一致はサンプル証拠であり、今回はtick再検査をしていない。全期間Bid価格種別、変動spread、実slippage、tick順序/欠損/足内約定は未確認。

2010–2018年は前回日足研究の戦略結果を閲覧済み。2019年以降の前回日足戦略結果が未計算であっても、他研究と日足品質/価格確認による閲覧が存在する。今回も後半を含む全日足配列を品質照合した。どの過去期間も真の未使用とは保証しない。

## 再現コマンド

リポジトリ直下の既存Python/NumPy環境で実走、終了コード0。原履歴と旧NPZへの書込なし。

```powershell
$env:PYTHONPATH='src'; @'
from pathlib import Path
from scripts.research_dinapoli_3x3_daily import load_daily,sha,iso
from forextester_backtest.data import HistoryRepository
from datetime import datetime
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
 total+=len(d.dates)
 print(json.dumps({'symbol':s,'n':len(d.dates),'source_rows':m['source_rows'],'first':iso(d.dates[0]),'last':iso(d.dates[-1]),'spread':current['metadata_spread_pips'],'npz_sha256':sha(f),'source_sha256':m['source_sha256'],'all_arrays_manifest_equal':True}),flush=True)
print(json.dumps({'status':'DATA_REUSE_VERIFIED','pairs':len(manifest),'daily_bars':total,'manifest_sha256':sha(p/'data_manifest.json'),'frozen_dependencies_equal':True}),flush=True)
for dt in [datetime(2026,8,31),datetime(2026,9,1)]:
 print('GBPJPY_SAMPLE',str(dt),[(x.open,x.close) for x in r.bars('GBPJPY',dt,dt)],flush=True)
'@ | python -
```

次工程は新ルールの指標ウォームアップ、確定情報時刻、片道/往復費用、保有費用仮定、日次ポートフォリオ評価を研究・独立検証担当が今回の仕様に対して確認する。
