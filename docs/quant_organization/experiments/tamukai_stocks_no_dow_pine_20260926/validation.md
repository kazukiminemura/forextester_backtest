# 移植チェック（実機コンパイル未確認）

## 追記：ユーザー指定のindicator版

旧strategyの配列範囲外エラー画像を受領したため、使用対象を
`scripts/tradingview/research/tamukai_stocks_no_dow_rr1_indicator.pine` に変更した。
旧strategyは未修復の比較資料として保全。indicatorではstrategy台帳・配列を使用しない。

indicator SHA256: `f09af6439ec63a6226de82392110e1150037397e010dcbdf4e0599b307fc043f`

`python -m pytest tests/test_tamukai_stocks_no_dow_indicator.py tests/test_tamukai_stocks_jev.py tests/test_tamukai_stocks_daily.py -q`

結果: **15 passed、exit 0**（indicator構造5件＋既存Python10件）。
独立担当の仮想状態遷移照合では、保存10銘柄の自然決済495件が元Pythonと一致。
期末強制決済4件はindicatorにないため対象外。実Pineコンパイル・実画面の証明ではない。
状態は研究用／TV_UNVERIFIED。今回のindicatorについてTradingView実コンパイルは実施していない。

---

2026-09-26。状態: RESEARCH_DRAFT / NOT_ADOPTED / TV_UNVERIFIED。

## 入力・出力識別

- 凍結no_dow原本SHA256: `3c1267a497d5ddf40848720da18b2c7ada56cdf54e7c09e57782f1b40c114b50`
- 凍結Python会計SHA256: `ea45264616f7f8f83f835571cd1fbd9f73e20560456b75f460e0ed2f3387c6b7`
- Pine: `scripts/tradingview/research/tamukai_stocks_no_dow_rr1_strategy.pine`
- Pine SHA256: `eb19d626c7ae8ec55301778235d48b6c1525b7b292456515252445c6a0ddca49`

## ローカル

`python -m pytest tests/test_tamukai_stocks_no_dow_pine.py tests/test_tamukai_stocks_jev.py tests/test_tamukai_stocks_daily.py -q`

実行結果: **16 passed、exit 0**（当該Pine構造6件＋既存Python10件）。
Pine文字列の契約検査とPythonテストであり、PineコンパイラーでもTradingView約定再現でもない。
元Python2ファイルのSHAが過去研究の識別子と一致することも確認。
保存CSVの独立信号照合とPine注文制御の監査は同ディレクトリーの `audit.md` 参照。

## TradingView実画面

新規匿名タブ、TSE:7203、標準ローソク足1D。
新規Untitled scriptに貼付、全選択・コピーしてファイル全文との一致を確認（CRLF/LFのみ正規化）。
最終ファイル全文で「Add to chart」を実行するとサインイン画面が開いた。
コンパイル応答・チャート上表示・ストラテジー損益は取得できていない。
認証情報の入力、保存、公開、アラートや注文接続は実行していない。

画面証拠:

- `agent_runs/tamukai_stocks_no_dow_pine_20260926/tradingview-login-required.png`
- `agent_runs/tamukai_stocks_no_dow_pine_20260926/pine-editor-ready.png`

## 残る確認

ログイン済み環境で最終ファイルをコンパイルし、買い翌始値・Entry/TP/SL・同日決済・gap例外・日終値決済と再シグナルの境界を確認する。
Pythonと同一OHLCを確保できない限り、両者の損益差をロジック差と断定しない。
既知の約定・数量・期間末・データ差は `docs/tamukai_stocks_no_dow_pine.md` に明記。
