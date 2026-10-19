# FX候補一覧の表示計画

ユーザー依頼: どの通貨にチャンスがあるか分かるようにする。

既存のYTT近似分析条件を変更せず、専用Pineインジケーターの別パネルで8通貨を比較する。利益研究で不採用となったルールを合格戦略として移植する工程ではない。候補表示の使いやすさを改善する。

1. Pine担当は新規 `scripts/tradingview/yosuga_ytt_fx_scanner.pine` のみ編集する。
2. 既定15分足、確定日足・週足の方向合意、確定ピボット、厳密な終値突破と消費済み管理を維持する。
3. 買い/売り待ち・直近成立・突破済・見送り・データ不足を区別し、価格と判定対象足時刻を表示する。古い成立を現在の成立にしない。
4. 主担当は使い方とチェックを作成し、TradingViewでコンパイル・8通貨表示・設定不正ガードを確認する。

既存assistantと研究結果は保持する。利益・勝率・月利の順位付けや注文機能は追加しない。

実装根拠: TradingView公式 [Other timeframes and data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/) の確定値のoffset/lookaheadとnested requestsを参照。
