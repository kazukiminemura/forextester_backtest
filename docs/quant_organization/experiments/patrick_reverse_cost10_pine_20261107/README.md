# Patrick VP / JST08 逆方向・費用10% 研究用Pine

[研究用Pine](../../../../scripts/tradingview/patrick_vp_jst_reverse_cost10_indicator.pine)にK10条件を移植済み。[TradingViewでの動作確認](verification.md)と[仕様・導入方法](mapping.md)を参照。費用後PFが1未満の未採用条件で、仮想約定の研究用。

1. 現行Pineを別ファイルへ複製し、元signal/VP/先触れは保持する。08候補判定と08:15約定時にSL距離>=10×計画費用を確認し、実行方向だけ逆にする。TP/SL絶対価格を交換し、幅保持mirrorとは区別する。
2. 予定/実行Entry・TP・SLと履歴切替を逆実行側に合わせる。原VAH/VAL文脈は原signalと明記する。
3. 現在チャートで使えるよう既定期間は元の2017〜2099を維持。学習再現では終了2020-01-01へ設定する。2020以降の収益は検証していないことをpanelに表示する。
4. 主が検査test/実機コンパイル/表示確認、Pine担当が新Pine/mapping、独立validatorがvalidation.md、auditorがaudit.md。旧Pine・Python研究・結果は変更しない。

初めに計画し、既存エンジンを再利用して変更範囲を固定する。構造検査だけでTradingViewのcompile成功と主張せず、実機結果を別途記録する。現在の観測dataでの動作確認は新しい後半経済バックテストの合格ではない。
