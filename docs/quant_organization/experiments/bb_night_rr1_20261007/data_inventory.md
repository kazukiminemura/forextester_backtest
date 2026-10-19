# BB夜間RR1研究 データ台帳

調査日: 2026-10-07 JST。担当: quant_data。
状態: `DATA_READY_CONDITIONAL_CLOCK_ASSUMPTIONS`。
7通貨の保存M5は条件付き研究に利用できる。保存時計のUTC差と歴史的DSTは未確定なので、日本時間の実測頻度とは表示しない。戦略成績・採用判定は本書の担当外。

## 入力同一性と今回の検査範囲

主データ源は `C:/ForexTester6/data/History`。今回のmetadata・原M1/tick件数・端点は `HistoryRepository.metadata/summary` を用いて読取確認した。再利用入力は `agent_runs/bb_alternatives_2020_2025_20260925/<symbol>_features.npz` と同ディレクトリ `data_manifest.json`。
構成M1完全性は `agent_runs/yosuga_channel_20261003/completed/<symbol>_complete_m5.npz` の `complete`。このmaskは元キャッシュと同順序で、単独の時刻列は持たない。

全7キャッシュ、7 info.dat、7完全性maskの全bytes SHA256が旧manifestと21/21一致した。保存M5 3,182,106本（warmup込み）を今回全件検査し、非有限・非正価格・OHLC包絡異常・高値<安値・重複時刻・逆順・300秒グリッド外はいずれも0。2020–2025分は3,139,023本で、通貨別年別件数もmanifestと一致。
原Bars.datはサイズ・mtimeのみ照合（全7一致）し、今回の原全bytes SHA再計算・原M1全OHLC再監査・全tick検査は行っていない。端点確認を全履歴品質検査と扱わない。

|通貨|保存M5 warmup込み|2020–2025 M5|構成M1完全M5 warmup込み|300秒超gap|metadata spread pips|
|---|---:|---:|---:|---:|---:|
|USDJPY|455,085|448,929|446,773|415|1.2|
|EURUSD|455,004|448,846|445,417|441|1.1|
|GBPUSD|454,932|448,777|447,550|447|1.4|
|AUDUSD|454,115|447,958|443,670|491|1.2|
|NZDUSD|454,315|448,161|442,249|557|1.4|
|AUDJPY|454,390|448,233|450,179|503|1.4|
|NZDJPY|454,265|448,119|449,430|525|1.7|

全キャッシュの最初は保存時計2019-12-01 22:00、最後は2025-12-31 21:55。2019-12をwarmupとして2020-01-01以上2026-01-01未満の6年を利用できる。今回読取でも全7通貨の原M1最終は2026-09-07 23:59。配信一覧brokers.txtの掲載提供終端とローカル実収録終端は区別する。

原M1→M5再集計の過去の独立監査は `../bb_alternatives_2020_2025_20260925/data_inventory.md` と `../yosuga_channel_20261003/data_inventory.md` を継承する。今回再実行したという意味ではない。週末・祝日以外のgapもある。AUDJPY/NZDJPYの2023年6月の長い欠落、部分M1欠落M5を保持する旧集約の制約を継承する。

## 時計の一次根拠と未確定事項

1. 公式Data Center説明は履歴情報のTimeshift欄と標準GMT+0を明記している。これは配信標準仕様であり、このPCの過去importや設定を証明しない。[公式Data Center](https://desktop.forextester.com/datacenter)
2. 公式新規project説明ではTimezoneを変更でき、標準GMT+0、DSTは標準では適用せず地域別に設定可能としている。[公式project設定](https://desktop.forextester.com/newproject)
3. ローカル10 projectのsettings.datを限定読取するとTimeZoneは0/9/-8で混在、DSTは全10件0。`yosuga1/settings.dat:10` は9、`yosuga2/settings.dat:10` は0。projectの表示・生成設定は共通History保存時計の確定根拠にならない。
4. 全7原info.datにtime/zone/gmt/utc/dstを含むキーはない。options.dat、desktop.dsk、ptSettings.dat、doSettings.dat、yosuga1/2 desktop.dskも限定検索し、時計を確定する明示キーは見つからなかった。全ディスクやレジストリを調査したという意味ではない。
5. `src/forextester_backtest/data.py:11,21–22` はOLE epochからnaive日時、同219–223行は保存時計の足開始bucketへ集約する。Unix秒表現や週末終了時間だけからUTCを断定しない。旧 `research_yosuga_5m_market_sessions.py:185` のUTC扱いは仮定である。

実際のData CenterのHistory/対象通貨のTime zone・Timeshift表示は今回取得できていない。native UI操作は利用不可であり、推測で埋めない。最小追加証拠はその表示の画像、import由来ならimport時のShift/DST設定と元履歴の由来。現在表示だけで過去に混在importがなかったことまで保証するものではない。

## 条件付き時間窓研究への引継ぎ

事前固定したsource GMT+0/+2/+3/+9の4仮定で、`仮定JST = source + (9 - offset)時間` を使える。標準0は公式defaultからの研究仮定、2/3/9は感度分析でありローカル時計の認定ではない。固定2/3は歴史的DSTの再現でもない。成績の良いoffsetを真の時計として選ばない。JST夜の実測値・達成済みと表示しない。

夜窓を仮定JST19:00以上24:00未満とする場合、入場の実next-open時刻で窓を判定する。M5ラベルは足開始、足確定は開始+300秒。shift後の暦日・曜日でnightを分類する。無取引夜も分母に含め、観測完全/部分/欠落nightを別集計し、7通貨合計を作る。7通貨×60本M5の全観測はM5観測完全であって、構成M1完全とは限らない。complete maskを併用した数を別に明記する。

H1を用いる場合は毎時bucketの12本M5連続と必要なcomplete maskを確認し、signal時までに終了したH1だけを参照する。H1確定やSMAの必要履歴が欠けた場合、前のH1を無制限に持ち越さない。これらは未来参照と欠測誤認を避けるデータ要件であり、売買条件の採用判断ではない。

## 価格・費用と既閲覧期間

全7通貨BrokerはAdvanced Data Feed、lot_size=100000、commission設定0。JPY末尾3通貨はpip=0.01、tick=0.001、他4通貨はpip=0.0001、tick=0.00001。quote通貨はmetadata APIの銘柄末尾3文字によるJPY/USDであり、元info.datのBaseCurrencyと混同しない。

表のspreadは元info.dat設定を小数桁で価格幅に換算した値。歴史的実測・GMO実測ではない。commission・swap設定0は実口座費用0の証明にならない。BB研究の1/1.2pip等は別の仮定費用。OHLC価格の全期間Bid/Ask側は未確定、tick全件照合は未実施。口座通貨換算をしていないR/pipsを円利益と表示しない。

2020–2025は既閲覧。2026も過去研究の閲覧記録があるため、延長しても未使用holdoutと保証しない。

## 証拠と再現

機械可読証拠: `agent_runs/bb_night_rr1_20261007/data_clock_evidence.json`。
各cache/metadata/mask SHA、原stat、年別件数、API端点、品質件数、project設定SHA、公式URL、時差仮定と未確認事項を保存した。JSONの `reproduction_commands` に今回実行した読取専用PowerShell/Pythonコマンドを全文保存し、2コマンドとも終了コード0。

簡易再確認:
```powershell
rg -n 'TimeZone=|DST=' C:/ForexTester6/Projects -g settings.dat
rg -n 'OLE_EPOCH|def _to_datetime|bucket_time =' src/forextester_backtest/data.py
```

次担当: 研究開発・独立検証。時計4仮定を結果前に固定し、source/JST仮定とデータ欠測区分を出力へ引き継ぐ。今回、原履歴変更・外部データ代替・再取得・有料API・戦略実走・注文は行っていない。

