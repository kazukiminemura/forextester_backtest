# ステータス配置の実機確認

シンプル化（2026-10-09）: 既定シンプルON、YTTを3列・新規成立→突破待ちに絞る。詳細上位足と過去YTT/BB候補ラベルを隠し、未消費閾値の価格描画は保持。古い/欠損データは更新待ちと表示。元の確定snapshotと通知gateを変更していない。関連51テスト成功。最終SHA256 `4A32C53B407D501EE3B625F18319B2B0B9CFDD5377301CCC20ACCC65E0A6F8E3`、個人保存版8、保存エディター本文のLF正規化後全文一致。EURJPY15分で最終Pine実更新を確認。画面では候補なしの空状態を確認、実市場で新しい成立イベント/通知実受信の確認は未実施。画像 `agent_runs/ytt_status_layout_20261009/simple_layout.png`。条件/収益/自動注文の変更ではない。

追加修正（2026-10-09）: ユーザー指定の右側突破候補表を削除。SHA256 `DC8809777428C9BCD24D814DA543F88516264A597261A5791E728744C8B324C7`、TradingView個人保存版6。貼り付け本文のLF正規化後の全文一致、EURJPY15分で実追加・右表なし・高安/チャネル/BB描画を確認。保存済みレイアウトに重複していた旧版はチャートから除去した。関連50テスト成功。画像 `agent_runs/ytt_status_layout_20261009/candidate_panel_removed.png`。以下は版4の確認履歴。

2026-10-09。状態: TV_VERIFIED_LIMITED_UTILITY。

- 対象: `scripts/tradingview/yosuga_ytt_combined.pine`
- SHA256: `3FB07470D456F85401BB3376ACF3A5E5F56185BF87C577DA1690CDC24FACFEDC`
- TradingView個人保存版4、保存本文をコピーし改行LF正規化後にローカル全文と一致。実チャート追加成功。
- OANDA:GBPJPY・5分足、1280×900。価格チャートにBB・高安線とチャネル、下段に左=上位足/高安、中央=通貨一覧、右=突破候補。
- BB集計ONでは右欄の候補下に全7行を表示。OFF後も突破候補6行を保持。YTT/BB通貨一覧切替で他の表を保持。最後はYTT、BB集計OFF。
- 下段の境界を上へドラッグして高さを約350pxに拡大。旧版をメインチャートへ移動したレイアウトでは、旧版を外して再追加する必要がある。3列表は横長画面向けで、狭い画面の自動折返しは未対応。
- pytest対象: combined/assistant/fx_scanner/bb3_reversal_confirmation_indicator、50 passed。構造検証と実機表示確認は別の証拠。

画像: `agent_runs/ytt_status_layout_20261009/stats_on.png`、`bb_scanner.png`、`final_layout.png`。

売買条件・BB仮想RR1計算・元の独立ソースは変更していない。表示修正の確認であり、収益性・全遷移・通知実受信の検証ではない。
