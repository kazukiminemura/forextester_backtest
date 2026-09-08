# データ担当 初回調査

調査日: 2026-09-08。対象: `C:\ForexTester6\data\History`。既存 `HistoryRepository.symbols()` / `summary()` / `metadata()` による読取専用調査。バックテスト・最適化・元データ更新は実施していない。

## 実データの所在と期間

30銘柄のディレクトリを確認。以下は Bars.dat の端点と有効レコード数であり、内部欠損・重複・価格異常・連続性の全件監査結果ではない。時刻はファイル保存値のまま。

| 通貨 | M1開始 | M1終了 | バー数 | メタデータspread（pips） |
|---|---|---|---:|---:|
| AUDUSD | 2009-10-01 00:00 | 2026-07-19 23:59 | 6,236,644 | 1.2 |
| EURUSD | 2003-05-06 00:00 | 2026-07-17 20:59 | 8,517,565 | 1.1 |
| GBPUSD | 2003-05-06 00:00 | 2026-07-17 20:59 | 8,631,252 | 1.4 |
| NZDUSD | 2003-08-05 00:00 | 2026-07-17 20:59 | 8,525,392 | 1.4 |
| USDCHF | 2001-01-02 23:01 | 2026-07-17 20:59 | 9,176,194 | 1.5 |
| USDJPY | 2003-05-06 00:00 | 2026-07-17 20:59 | 8,486,336 | 1.2 |
| AUDJPY | 2003-12-02 00:00 | 2026-07-17 20:59 | 8,429,303 | 1.4 |
| CHFJPY | 2001-01-02 23:01 | 2026-07-19 23:59 | 9,136,956 | 1.8 |
| EURCHF | 2003-08-05 00:00 | 2026-07-17 20:59 | 8,471,194 | 1.7 |
| GBPCHF | 2003-08-15 08:55 | 2026-07-17 20:59 | 8,539,678 | 1.6 |
| GBPJPY | 2001-01-02 23:01 | 2026-07-17 20:59 | 9,222,676 | 1.8 |
| USDCAD | 2003-08-05 00:00 | 2026-06-30 23:59 | 8,526,293 | 1.5 |
| EURJPY | 2001-01-02 23:01 | 2026-08-20 23:59 | 9,224,543 | 1.3 |
| EURGBP | 2003-08-05 00:00 | 2026-08-21 20:59 | 8,524,941 | 1.4 |
| NZDJPY | 2018-04-01 21:04 | 2018-04-30 23:59 | 30,385 | 1.7 |

先頭11通貨は既存 `scripts/research_strict_rr_portfolio.py:SYMBOLS` と同じ。端点上の共通範囲は2009-10-01〜2026-07-17 20:59である。USDCADも含めると共通終了は2026-06-30になる。NZDJPYは長期間比較には不足し、CADJPYは銘柄一覧に存在しない。調査対象のcommission_per_lotはすべて0だが、実ブローカーの費用がゼロという意味ではない。

NZDJPY以外の表内通貨にはticks.datの有効レコードもある。NZDJPYは0件。USDCHF・EURJPY・GBPJPY・CHFJPYはM1が2001年から存在する一方、tick開始は2003年であり、M1とtickの検証期間を同一とみなしてはいけない。tick全件読取は実施していない。

## 現行実装の制約

- `src/forextester_backtest/data.py`: OLE日時をタイムゾーンなしdatetimeへ変換。UTC/JST/ブローカー時刻の識別・変換はない。セッション条件やTradingView移植前に出所の時間帯とDSTを確認する。OHLCはファイル内のOpen, Close, High, Low順を読み替える。
- 集約足はOLE基準の時間バケット。欠損バーを補間せず、構成M1が不足した集約足も返す。営業日・祝日を考慮した欠損監査は別途必要。`bars(end=...)` の終了日時は包含。
- `src/forextester_backtest/agents.py:run`: 現行エージェント検証は15分足を生成し `TamukaiBacktester` へ渡す。90日ウォームアップと期間端の7日以内確認はあるが、内部欠損の全件検査ではない。tick約定検証は行わない。
- `src/forextester_backtest/tamukai.py:_process_execution`: 足内価格経路は始値から近い高値/安値へ先に進むOHLC仮定。同一足のTP/SLを常にSL優先とする実装ではない。ブレイク確定後の次足始値約定は `require_breakout_close` 条件次第であり、全戦略共通と記載しない。
- 同ファイル `_enter` / `_exit_units`: メタデータの固定spreadを買いエントリー・売り決済へ反映。commissionはエントリーと決済それぞれに適用。時間変動spread、実スリッページ、スワップ、口座通貨換算はこの経路でモデル化していない。異なる決済通貨の金額損益をそのまま合算しない。
- バー始値ギャップの処理はあるが、シグナル終値→次足始値差は実注文のスリッページ計測ではない。
- 別の研究スクリプトは異なる約定モデルを持ち得るため、研究ごとに実際に使うエンジンと費用設定を固定・記録する。

## 次担当への引継ぎ

1. 研究責任者: 比較母集団・期間・時間足を実験前に固定。上記固定11通貨を出発案とするが、今回の調査を戦略の採用根拠にしない。
2. 検証担当: 初回の研究実行前に対象期間の内部欠損、重複、時系列順、OHLC整合を監査し、入力バーとメタデータの指紋を保存。閲覧済み期間を「完全未使用」と表示しない。
3. 約定検証担当: M1または利用可能範囲のtick再検証とコスト増加テストを別段階として設計。タイムゾーンを確認できなければ時間帯戦略の判断を保留する。
4. TradingView担当: 保存時刻・足境界・Bid/Ask・足内約定・確定足判定を仕様書に明記。Forex TesterとTradingViewは価格配信元が異なる可能性があるため、ロジック一致と損益一致を別々に検証する。

本調査の成果はデータ台帳と制約の確認であり、戦略性能評価やPineコンパイル成功を示すものではない。

## 調査再現コマンドと終了コード

作業ディレクトリは `C:\Users\minemura\projects\forextester_backtest`。以下は実際に実行したPowerShellコマンド。Pythonは既存リポジトリの読取専用APIのみ呼び出す。

```powershell
$env:PYTHONPATH = 'src'; python -c "from forextester_backtest.data import HistoryRepository; from dataclasses import asdict; import json; r=HistoryRepository(); print(json.dumps({'available_symbols':r.symbols()},ensure_ascii=False)); pairs=['USDJPY','EURUSD','GBPUSD','AUDUSD','NZDUSD','USDCAD','USDCHF','EURJPY','GBPJPY','AUDJPY','CADJPY','CHFJPY','NZDJPY','EURGBP']; [(print(json.dumps(dict(asdict(r.summary(s)),spread_price=r.metadata(s).spread_price,commission_per_lot=r.metadata(s).commission_per_lot),default=str))) for s in pairs if s in r.symbols()]"
```

終了コード0。30銘柄一覧と、実在する13通貨のsummary・spread・commissionを取得した。CADJPYは一覧にないため出力対象にならない。

```powershell
$env:PYTHONPATH = 'src'; python -c "from forextester_backtest.data import HistoryRepository; from dataclasses import asdict; import json; r=HistoryRepository(); [(print(json.dumps(dict(asdict(r.summary(s)),spread_price=r.metadata(s).spread_price,commission_per_lot=r.metadata(s).commission_per_lot),default=str))) for s in ['EURCHF','GBPCHF']]"
```

終了コード0。固定11通貨に含まれる残り2通貨を取得した。

文書作成後は `git diff --check -- docs/quant_organization/data_inventory.md` と `Get-Item docs/quant_organization/data_inventory.md | Select-Object FullName,Length` を同じ呼出しで実行し、呼出し全体の終了コード0・ファイル存在・5,310バイト（本追記前）を確認した。新規未追跡ファイルのため、`git diff --check` だけでは本文の検証を保証しない。この追記に伴うデータ再読取・バックテストは実施していない。
