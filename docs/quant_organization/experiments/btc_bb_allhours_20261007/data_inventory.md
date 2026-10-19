# BTC BB全時間帯研究 データ台帳

調査日: 2026-10-07 JST。担当: quant_data。状態: `DATA_READY_WITH_LIMITATIONS`。
保存BTCUSDキャッシュを全時間帯の記述研究に再利用できる。保存時計が未確定でも、JST時間帯フィルターを使用しない今回の計算は進められる。市場の再現性・欠測・実費用の制約は引き継ぐ。戦略成績と採用判定は本担当では計算していない。

研究責任者追記（データ調査後・損益計算前）：ユーザーが「CFDなど・買いと売り」「GMOコイン・暗号資産FX」と指定。現物long onlyの暫定条件は撤回する。保存BTCUSDをbid仮定として合成askを作る参考検証であり、GMO BTCJPYの実feed/実spreadを再現した証拠ではない。source時計不明のためJST6時持越課金も再現不可。日またぎ費用は明示した時計不要の保守proxyを使用し、実GMO成績・採用承認と呼ばない。この追記はデータ担当による新たな市場side確認ではない。

## 入力と今回確認した同一性

主データ源: `C:/ForexTester6/data/History/BTCUSD/{Bars.dat,ticks.dat,info.dat}`。
優先再利用: `agent_runs/btc_spot_rr1_20261007/btc_m1.npz`。
schemaは `time` がint64の保存時計秒、`prices` がfloat64のOHLC。

旧 `input_manifest.json` と `docs/quant_organization/experiments/btc_spot_rr1_20261007/freeze_manifest.json` を照合した。freezeに記録されたコード・tests・protocol・hypothesis・旧data_inventory・input_manifest・cacheの7 SHA256はすべて一致。cacheのSHAは `c085f3ae069fc12e06313f86b53cc75e0a813fd7c2688e58cedf86cca6e2d7e6`、input manifestは `1a90013989dc2a34549a5aa6942e6af707d49ea2124b54671363b10dddafe88c`。

原Bars.datは206,880,772 bytes、mtime_ns=1791370606804472900で旧manifestと一致。今回原Barsの全bytes SHAは再計算していない。現在のinfo.datはSHA `f9b6ddb5627c113ddec848e4ae84176a120bdea8b104f00b73db50c2f0b0b813` で旧データ台帳と一致。原履歴の読取APIは既存HistoryRepository.metadata/summaryを使用した。

旧cache全4,309,797 M1を今回全件検査し、非有限OHLC・非正価格・OHLC包絡異常・高値<安値・時刻重複・逆転・60秒グリッド外はすべて0。サンプル検査ではない。ただし今回全原M1や全tickの値を再照合したという意味ではない。価格の市場正当性や実行可能性も保証しない。

## 利用期間と全曜日coverage

cache全体は保存時計2017-05-09 02:00～2026-10-06 23:59、M1 4,309,797件。
今回指定範囲は保存時計2020-01-01以上2026-10-07未満。M1 **3,349,973件、全曜日の暦日2,471日**。
1,440 M1すべてある完全日は1,431、1～1,439 M1の部分日は997、M1が0の欠測日は43。
完全M5が0の暦日も43日。週末を除外せず、土曜・日曜を含む。

|年|暦日数|M1|完全日|部分日|欠測日|完全M5|完全H1|
|---|---:|---:|---:|---:|---:|---:|---:|
|2020|366|421,030|196|136|34|83,967|6,816|
|2021|365|523,366|305|60|0|104,594|8,638|
|2022|365|488,131|176|189|0|93,485|6,972|
|2023|365|482,288|44|319|2|86,235|5,300|
|2024|366|518,788|250|114|2|102,803|8,242|
|2025|365|522,102|259|105|1|104,035|8,368|
|2026（10/6まで）|279|394,268|201|74|4|78,432|6,251|

全2,471日の日付・曜日（0=月曜～6=日曜）・M1件数・完全M5/H1件数・complete/partial/missingを `agent_runs/btc_bb_allhours_20261007/data_evidence.json` の `daily_coverage` に保存した。年別曜日ごとのM1数も保存している。

2020年の土曜M1は22,836件・日曜29,484件で、後続年の同曜日より収録が少ない。元台帳では2017–2019の土曜が0であり、今回2020以降に限っても24/7の完全履歴にはならない。欠測が供給元休場か通信欠損かは確定しない。欠けた価格を補完しない。

## M5・H1と日別頻度への必須条件

1. M5は保存時計の5分開始境界から連続5 M1を持つbucketのみ。H1も毎時00分から連続60 M1のみ。cacheは時刻重複なし・分グリッド一致なので、件数と先頭/末尾時刻を合わせて完全性を判定できる。
2. 指定範囲の完全M5は653,551本。観測された679,435 bucketのうち25,884が部分bucketであり、新M5入力から除外する。完全H1は50,587本、観測56,793 bucketのうち部分6,206。観測ゼロbucketはこれらの観測bucket数に含まない。
3. 足のラベルは開始時刻、利用可能な確定時刻はM5開始+300秒、H1開始+3,600秒。上位足はsignal時までに終了した足だけを利用する。部分bucketの除外でできたgapを連続足として扱わず、必要なwarmupの連続性を別に確認する。
4. 1日平均・0件率・2件以上率の分母は、全7曜日の保存時計暦日を基に、完全日・部分日・欠測日を区別する。欠測43日は「0取引が観測された日」ではない。観測可能日の平均を出すなら分母と除外日数を明記し、部分日に機会がなかったと推測しない。完全日でもsignal warmupが有効とは限らない。
5. 時刻はsource calendarでありJSTではない。全時間帯利用のためJST換算は実走の必須前提ではないが、将来日本時間に絞る場合は時差/DST証拠が必要。日別の分布にも日境界の依存がある。

日全体の将来欠測情報でその日の過去signalを遡って見送る実装にはしない。coverageは事後の観測品質分類、入場条件の因果判定とは分離する。
部分期間に保有した取引、欠測中のTP/SLと窓開けは責任者が約定仕様に明記し、検証担当が確認する。

## 商品・価格・費用

HistoryRepositoryが返す現在のinfo.datはBroker=Advanced Data Feed、type=0、group=Crypto。
lot_size=100000、BaseCurrency/LotCurrency=BTC、MarginCurrency=BTC。
FTのlot設定は現物取引所の最小BTC枚数・注文単位の証明ではなく、無批判に現物数量へ使わない。

- spread=60643 points、decimals=3なので60.643価格単位。BTCUSDとmetadata APIの末尾3文字規則からUSD/BTCと解釈する。この値は静的設定であり、GMOの実spreadや歴史的実測値ではない。
- point/tick表示幅は0.001。暗号資産pipの契約上の定義は未確認。FXのJPY pip換算を流用せず、BTC数量・USD価格幅を明示する。
- ApplyCommission=0、CommPerLot=0、SwapLong/Short=0はFT設定。現物取引所の実fee・滑り・swapが0という根拠ではない。
- 現物取引所feedとは未確認。CFDと断定する根拠も不足する。元取引所・全価格side・約定可能性は未確認。
- 旧データ台帳のtick比較は3つの1時間窓・25,422 tickだけの限定サンプルでBid主体を示唆した。今回tick再照合・全tick監査は実施していない。その観察を全期間へ拡張しない。

## 既閲覧と再現

2020–2026は旧BTC実験で閲覧済み。期間分割の名称にかかわらず未使用holdoutと保証しない。新規ロジックで再利用した結果は、既閲覧履歴に対する記述研究として扱う。

機械可読証拠: `agent_runs/btc_bb_allhours_20261007/data_evidence.json`。
`reproduction_command` に今回の読取専用PowerShell/Pythonを全文保存した。旧freeze全7SHA、原stat、全cache品質、完全bucket数、全曜日の日別/年別coverageを再現し、実行終了コード0。
追加のinfo SHAはPowerShell `Get-FileHash -Algorithm SHA256 -LiteralPath C:/ForexTester6/data/History/BTCUSD/info.dat` で照合した。

元全M1/tickの初回監査根拠は `../btc_spot_rr1_20261007/data_inventory.md` を参照。今回の担当成果物は本書とdata_evidence.jsonのみ。旧cache・原履歴は変更せず、再取得・新戦略損益計算・有料API・注文は行っていない。
次担当: 研究開発と独立検証。

