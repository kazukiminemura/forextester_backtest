# TradingView表示確認

状態: TV_VERIFIED_LIMITED_UTILITY。2026-10-09。売買戦略の採用判定ではない。

最終 source SHA256 `767BDEE5731A91D0B3840A614177D5F922B4878DA221D953032B88F8AA74163D`。個人保存版3の本文をコピーし、CRLFをLFへ正規化後にローカル本文と全文一致。実際に保存版3をチャートへ追加して表示確認。旧統合版は外し、最終版1本へ置換。外部公開・課金・注文・実アラート作成なし。

1. EURUSD15分、YTT一覧モード: BB中央線/±3σ、準備取消水準/反転突破基準ラベル、YTT高安水平線・上位状態・突破価格、下段YTT8通貨を同時確認。
2. EURUSD15分、BB3σ反転一覧モード: 同じ8通貨を監視し、YTT一覧と排他切替。BB状態・突破/取消水準・中央線幅・確定時刻を表示。最終版3でも反転一覧を実取得し、request制限エラーなし。
3. EURUSD5分、版2: BBバンド・YTT水平線と候補ラベル・BB8通貨一覧を確認。仮想勝率を一時ONにして右上へ表示し、YTT右下との重なりがないことを確認、OFFへ戻した。画像の勝率は読み込み履歴1件の参考集計で採用根拠にしない。
4. 版2→版3差分は両一覧の空白行高さ4→8だけ。最終版の見出しと凡例の重なりを修正。BB全履歴ラベルは300件FIFO、YTT高安ラベルのGC消失を抑制。

`python -m pytest tests/test_yosuga_ytt_combined.py tests/test_yosuga_ytt_assistant.py tests/test_yosuga_ytt_fx_scanner.py tests/test_bb3_reversal_confirmation_indicator.py -q` →50 passed/exit0。構造テストはPineコンパイルではない。元BB状態遷移/前足中央線幅/取消優先/仮想RR1台帳/銘柄別scannerの独立逆変換一致は `validation.md` を参照。

画像 `agent_runs/ytt_bb_combined_20261009/final_bb15m.png`、`bb5m_stats_position.png`（版2）。通知実受信、独自時間足設定による最大40 requestの極端設定、収益性は未確認。5分限定の既定OFFと、YTT厳密終値突破/BB足内突破の違いを使い方文書に記載。
