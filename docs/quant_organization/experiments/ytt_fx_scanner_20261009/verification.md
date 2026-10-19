# 実機確認

2026-10-09。状態: TV_VERIFIED_LIMITED_UTILITY。収益戦略の採用判定ではない。

- 最終 source SHA256: `7095369E0E5D91C17189FB914A397FBA09B9AAD0817E1208DFDC0AA00250F8CD`。
- 個人TradingView「よすが式 FX候補一覧（YTT近似・分析補助）」版2。エディターからコピーした本文はCRLF、ローカルはLF。LF正規化後は全文一致（9659文字）。貼付ではなく、この最終本文を実コンパイルして追加後の描画を確認。
- OANDA:USDJPY通常15分チャートで全8通貨描画。最終スクリーンショット20:15 JST台: USDJPY見送り、EURUSD/GBPUSD売り突破済、AUDUSD見送り、EURJPY売り待ち177.304、GBPJPY売り待ち209.731、AUDJPY売り待ち110.282、USDCHF買い待ち0.83150。これらは時点の表示で、以後の最新候補を保証しない。
- 1時間チャートで設定不正、価格等がダッシュになり、新規候補を抑制。15分へ復帰して表示回復。画像 `agent_runs/ytt_fx_scanner_20261009/chart_too_large.png` は表示修正前の版1で判定ロジックは同一。最終版2との差は余白/時間足名のみ。
- 下段専用パネルの上部余白でインジケーター名と表見出しの重なりを解消。最終画像 `agent_runs/ytt_fx_scanner_20261009/final_8_pairs.png`。
- Basicプランの追加制限ダイアログが表示された際、旧スキャナーをオブジェクトツリーから外して最終版を置換。課金・公開・アラート作成・注文なし。
- `python -m pytest tests/test_yosuga_ytt_fx_scanner.py tests/test_yosuga_ytt_assistant.py -q` →15 passed、exit0。構造チェックでありPineコンパイルは上記実機で別確認。
- 既存assistant SHA `857A0548729C96DDBA326D7B0E5D6F573E7DFAD1EDED603FEC7DAFD42AD0F1AD` を保持。

独立レビューは `validation.md`。境界18件は独立Python述語検算でPine実行ではない。実通知受信、成立時の実機発生、下位チャート5分の実機確認、過去リプレイは未確認。ホスト更新・データ鮮度・配信元差・近似条件の制約は使い方文書に記載。
