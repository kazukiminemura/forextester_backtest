# Jev結果評価の実行記録

本計画は訓練計算後・Jev初回送信前に保存。候補、訓練gate、選抜後のみ後期計算、最大2call、confidence 0.8は訓練前に担当間で固定しprotocolへ保存済み。訓練結果を見たgate変更はしない。

- モデル `jev-1.13.0`、HTTP Choice。候補ごとのadvance/reject/insufficientと全体候補/none選抜を1回にまとめる。説明文を生成するモデルではないため、理由の文章は人間向け統合報告として主担当が別途書く。
- Jevの選抜を採用するのは数値適格候補かつselectionと候補advance双方confidence>=0.8のみ。それ以外はnone。0.8は未校正の保守的な研究進行制限であり、勝率・利益の確率ではない。
- 全候補不適格ならJevによる評価は記録するが、後期を計算しない。API失敗/型不整合も停止。自動再送なし。同一phase1attempt、合計2attemptまで。
- この新実験専用台帳。65,536 input tokens/回を$0.042/Mtokenで引当。最大2回=$0.005505024、200円/USDの予算仮定で約1.101円、2円上限内。旧研究の500円枠や3回枠は変更しない。APIキーは環境から取得し保存・送信stateに含めない。
- 送信は訓練集計と制約のみ。通常の銘柄別/年別、通常とstress全体・年別・品質診断合計を含む。stress銘柄別と品質診断年別は重複を減らすため省略。元JSONは完全保存。表示数値のみ小数4桁、数値ゲートは元精度で確定済み。
- 最初のdry-runは41,517 bytesで上限28,000超過を検知。未送信のまま上記の情報圧縮を追加し23,048 bytesへ縮小。判定文・閾値は不変。入力圧縮のみ訓練後変更であることを明示。
- 初回API前judge SHA256: `3df1ec36fbd5eec7407c9fecd8181b030d3c88ceedc92de9098ab0b7e4893ff5`。
- 同tests SHA256: `9ccc70d5b7c1b46ba6955b0ea2356708c6c40f810c240e64f9208416748d4caf`。モック2tests成功、課金callなし。
- 訓練SHA256: `0da06299f6053cc8441c1bdc1e0b30f6cca48d1c58fdc0d61585c9c008cb3533`。

公式資料確認（2026-09-26）: [API](https://docs.typesafe.ai/api)、[モデル・料金](https://docs.typesafe.ai/models)、[Choice](https://docs.typesafe.ai/primitives/choice)、[Confidence](https://docs.typesafe.ai/confidence)、[証拠との照合例](https://docs.typesafe.ai/cookbooks/citation_check)。TypeSafeスキルに従い、決定的な損益計算と意味的な結果評価を分離した。
