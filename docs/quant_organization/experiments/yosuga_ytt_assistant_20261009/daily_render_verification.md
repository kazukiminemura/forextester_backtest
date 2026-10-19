# SMR日足の描画修正・TradingView実機確認

2026-10-09。状態: TV_VERIFIED_LIMITED_UTILITY。TradingView個人保存版11。最終ソースSHA256 `716889E23B5EB5A5AAD6A3743098CE57AE1376579E95C808AD4A7C771AF3CEFD`。

## 対象と再現

ユーザー回答SMR。画面はNuScale Power Corporation・1D・NYSE（無料Cboe/BATS配信）。通常ローソク足、ピボット2/2、保持12、突破線削除ON、チャネルON、候補1D/1W、手動シナリオOFF。旧版10で画像と同じ高値14.66/14.20/14.30等と縦線を再現。

旧描画はセッション終了時刻と終了+1ms等をX座標にし、日足上で両点が同じ列へ描画されていたと推定。異なるバー列へ変更したところ水平線へ改善。高安・候補・チャネルはbar_index+1/+2、突破線の終端もbar_indexで統一。force_overlayは維持。

## 最終コードの実機証拠

1. 最終全文をPineエディタへ貼り付け、Ctrl+Sで保存・チャート更新。版11とUndo update scriptを確認。エラー表示なし。
2. 保存済みエディタから全文をコピーし、改行正規化後ローカル全文一致・上記SHA一致を確認。
3. 高値14.66/14.20/14.30/11.85/11.37/9.26/8.37、安値7.21が水平線へ改善。下降チャネルは橙実線・破線の平行斜線、基準8.26/平行7.31。
4. 左への移動と価格軸ドラッグ後も高安価格と線位置が一致。さらに縦移動して2本のチャネルを視認。撮影後、一時1440x900 viewport指定を解除。

画像はrepoのagent_runs/yosuga_ytt_assistant_20261009/に保存。

- daily_smr_before_fix.png: 旧版の縦線。
- daily_smr_after_fix.png: 最終ソースの更新後。
- daily_smr_after_move.png: 横移動後。
- daily_smr_after_rescale.png: 価格目盛り変更後。
- daily_smr_final.png: 縦移動後の平行チャネル。

## 限界

チャネル現在基準価格・幅は従来の時刻算術。未来傾きは標準時間幅/バーの近似で休日を厳密投影しない（tooltip記載）。手動シナリオは未変更・今回OFFで未検証。日足で候補1D/1Wは1Dが現足と同じなので「時間足設定を確認」となる。日足で候補を使用するなら厳密な上位2足（例1W/1M）を利用者が選択する必要がある。

ローカル構造pytest11件成功はPine実行証拠とは区別する。候補イベント全遷移、アラート受信、全銘柄、収益性は今回の描画確認に含まない。

座標仕様の参照: [TradingView公式 Lines and boxes](https://www.tradingview.com/pine-script-docs/visuals/lines-and-boxes/)（2026-10-09）。
