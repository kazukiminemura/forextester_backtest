# TradingView よすが式分析補助の実装計画

2026-10-09 JST。ユーザーは「よすあ式のYTTを実装して」、実装先は「TradingView」と指定。

## 範囲と必要性

公式YTTの公開機能に対応するチャート分析・手動シナリオ補助を、独立したPine v6 indicatorとして作る。既存yosuga Pineは別の機械近似でありYTTそのものではない。既存研究の不採用戦略を移植せず、自動売買条件・勝率・PFを新たに提示しない。本作は戦略研究の採用工程ではなく、表示と計算の補助ツール作成である。

公式機能説明: https://fx-space.com/trade/ 。公式内部の高安確定・オートラインの完全な数値仕様は未取得。近似の根拠と未定義事項は `../yosuga_channel_20261003/source_inventory.md` に記録済み。

## 結果前の仕様

1. 設定可能な左右確定ピボット、チャート足の水平線、終値突破方向、2点と反対極値を使う平行チャネル。ピボットの過去時刻と検出時刻を区別し、過去から利用可能だったと扱わない。突破線削除と保持上限を備える。
2. D/H4/H1/M15の確定足方向を表示。上位足はexpressionの1本offsetとlookahead_onを組み合わせる。同じ足は確定時だけ更新。下位足の通常security値を確定MTF値と扱わず無効表示とする。
3. ユーザーが有効にした手動シナリオのみ描画。方向・Entry・SL・開始日時・RRを入力し、最小tickへ整列、価格の大小とゼロ幅を検査する。既定RR1。Entry/TP/SLは文字と価格で明示し、注文・約定の表示とはしない。
4. 資金×リスク率を損失上限、EntryとSLの差×明示入力の換算係数を1数量あたりの理論損失とし、入力数量刻みで切り下げる。係数未設定なら数量算定しない。契約数量とFXロットを暗黙同一視せず、費用を含まないことを表示する。
5. 確定足の水平線接触・方向変化をalertconditionとして用意。TradingView側でアラートの作成が必要。市場注文・口座接続・外部API・公開・Git pushは含めない。

## 担当と確認

主担当: 計画、統合、TradingView UI検証、作業台帳、`tests/test_yosuga_ytt_assistant.py`。Pine担当: `scripts/tradingview/yosuga_ytt_assistant.pine` と `docs/yosuga_ytt_assistant.md`。独立検証担当: 読取レビュー、独立確認の実行、validation.md。品質監査: 最終ソースと検証証拠の読取確認、audit.md。共有ファイルの同時編集を避ける。独立検証役の実装編集禁止に従い、テスト作成は主担当に割り当てた。

ローカルpytestは構造検査として報告する。TradingViewの実コンパイル・チャート描画は別に確認し、未実施ならTV_UNVERIFIEDとする。収益性を評価するバックテストはこの表示ツールの完了条件にしない。

状態: DELIVERED_LIMITED_UTILITY / TV_VERIFIED_LIMITED_UTILITY / AUDITED_DELIVERABLE_LIMITED_UTILITY。実機で確認した表示・算術の修正と範囲は verification.md、独立所見は validation.md、引渡し判定は audit.md に記録。
