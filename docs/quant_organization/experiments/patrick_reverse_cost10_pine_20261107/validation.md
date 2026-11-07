# Patrick swap逆OFF K10研究用Pine：独立検証

担当はquant_validator。2026-11-07 JST。状態は `SOURCE_AND_FINITE_CHECKS_PASS / TV_CHART_SMOKE_VERIFIED`。

## 対象と判定範囲

ユーザー指定による未合格K10の研究用移植。正本は `scripts/backtest_patrick_reverse_costfilter.py` のK10、swap逆方向、H4 bigmove gate OFF。元研究は学習ゲート不合格で後半未評価。Pineへの移植を利益戦略合格と扱わない。

1. 08時の元signal候補loopで逆geometryと逆SL距離/C>=10を確認し、失敗時は古い候補へ進む。C=spread+2slip+3carry。08:15元quote geometry、新side実quote geometry、実SL/Cを再確認し、失敗なら取消・その場で再選抜しない。
2. signal side/週VP/元TP先触れ/7日窓/使用済setupは元条件を維持。実行sideだけ逆、SL=元TP、TP=元SL、Ask/Bid/新分母/費用/gap/時間決済/同分SL先を新sideで計算する。
3. M1処理は確定過去H4/週と現在始値だけで08時選抜し、その後で現在M1高安を更新する。現在足の極値がOPEN時の選抜へ漏れない。未確定H4を使わない。
4. 予定Entry/TP/SLは逆実行sideの数値とラベル、08:00参考と08:15実Entryを区別する。実約定後のEntry/TP/SLと過去履歴/今日切替を確認。VPの原signal sideを実行sideと混同表示しない。
5. 既定Entry期間は2017-01-01以上・2099-01-01未満へ主担当が変更した。2017–2019だけを既定にすると現在チャートのM1履歴上限により全取引0となり、表示確認に使えないため。これは現在観測の動作確認用で、後半の収益合格を意味しない。研究再現は終了を2020-01-01へ手動設定する。研究未採用・学習2017–2019のみ・後半未検証をpanel既定ONで表示する。TradingViewコンパイル/実機表示の確認は主担当が行い、ローカルsource/境界確認から実機成功を推定しない。

## 所有と未完了

検証担当はこの文書だけを編集し、旧Pine・新Pine・他者UI作業・戦略コードは変更しない。独立合成チェックはstdinで実行する。永続testsの保存とTradingView操作は主担当が行う。

## 独立source照合

検証した新Pineは `scripts/tradingview/patrick_vp_jst_reverse_cost10_indicator.pine`、SHA256 `567cf3c4cfadff7ede0c1d3322393c5eae2866334183c5bc65d9d41549296ea3`。Python正本は凍結costfilter K10（runner SHA `a8dcf8752a8037a94c9c59db59b5cc9818d8edd2a41ec32ca400758c162c7cb9`）。H4追加gateは導入していない。

1. 旧Pineとの関数単位比較で `f_week`、`f_jstWeek`、`f_touch`、`f_weekend`、`f_deadline`、`f_profile`、`detect`、`finishH4` の8core blockが文字列完全一致。元初動/週VP/完成足/7日窓を保持する。
2. K10とCの定義、08時候補で原geometry/原quote近接、逆quote/逆geometry、逆SL距離/C>=10を確認。合格候補だけbreakするため、不適合時は次の古い候補を検討する。元side/元TP/元SLは別に保持される。
3. `pendingStop` は元SLを保存し、予定TP/実TPに使う。`pendingS.target` は元TPのまま、予定SL/実SLに使う。`pendingQuote` は08時逆executionQuoteで、08:15のactualは新しく逆Ask/Bidで計算する。方向だけでなく水準/数値も逆実行へ合わせている。
4. processの文字列順で過去H4完了→OPEN既存決済→pending取消/08:15実行→08時選抜→当分高安決済（SL先）→元TP先触れ→現在H4/週更新を確認。08時選抜関数には現在M1の高安/終値を渡さず、始値oだけを渡す。
5. 勝ちはpnl>0、PF_Rは正/負Rの別集計、口座PFは正/負pnlの集計。予定Entryは08時参考と明記、実Entryはe.sideと実quoteをラベルへ記録。Entry/TP/SLの価格数値、今日/保有中/過去の6個別表示切替、原signalと逆executionの表示区別をsourceで確認した。panel既定ON、研究未採用・学習2017–2019不採用・後半収益未検証を表示する。

## 独立有限境界検算

`PYTHONPATH=src;scripts`、`python -B -` でsource assertionとPython正本の有限検算を実行し、exit0 `PINE_K10_SOURCE_AND_FINITE_CHECKS_PASS`。**Pine VMを実行した検査ではなく**、移植式と順序をsourceで固定し、正本Pythonの期待動作と照合する範囲である。

元signal買い/売りの両方について、各6ケース、計12ケースを確認した。

| ケース | 期待結果 |
|---|---|
| 08時/08:15のSL/Cが10ちょうど | 逆Entry、予定/実SL=元TP、TP=元SL |
| 10直下のfloat | 約定なし |
| 08時通過、08:15 quoteでSL/Cが10未満 | selection1件、Entry0、再選抜なし |
| 08時参考quoteと08:15実quoteが異なり両条件通過 | 実quoteでEntry、SL/TPの絶対水準は元予定値 |
| 08:15 M1内で新SL/TP両到達 | SL先、コスト後損失 |
| 08時の同M1高安が元TPへ達する | OPEN時selectionは1件、その後先触れで取消、Entry0 |

再現合成は2018-01-02T23:00UTC判定、M1は判定/+60/+900/+960秒、Bid1000、pip1、通常spread1/slip0.1/carry0.2（C=1.8）。setupのATR100/range900–1100、VP[1100,900]。逆quoteqに対して元TP=q+元side×18とすればK10等号となる。元SLは原買い875/原売り1125。元TPをq側へnextafterすれば直下。Entry Bidを元side×0.01だけSL側へ動かせば08:15再拒否、逆へ動かせば予定/実quote差の通過例となる。Entry M1高安1150/850なら両到達、08時高安を元TP外へ動かせば同M1未来極値がOPEN選抜へ漏れないことを確認できる。

## TradingView実機確認

主担当がTradingView DesktopのPine Editorでコンパイルしてチャートへ追加した。OANDA:EURJPYの15分足で、インジケーターのタイトル、損益パネル、過去のEntry・TP・SL表示を確認した。観測期間は2026-08-02〜11-06、28決済、PF_R 0.405。既存インジケーターの表示と重なるため、個別取引のEntry・TP・SLの価格関係は画面上で未照合。主担当は非公開保存・公開を行っていない。

検証担当は `agent_runs/patrick_reverse_cost10_pine_20261107/editor_readback.txt` と最終Pineを読み直し、双方36,275文字、`text_equal=True` を独立に確認した。最終Pineの実SHA256は上記の `567cf3c4cfadff7ede0c1d3322393c5eae2866334183c5bc65d9d41549296ea3` と一致した。実機の操作・表示の観測は主担当による。検証担当の再現範囲は本文照合、ソース確認、Python正本の合成12ケース。

28決済とPF_R 0.405はTradingViewの当該チャートの価格・出来高・取得履歴を使った動作確認値。Forex Testerの学習期間・16通貨合算との同値照合、および後半の収益性評価は未実施。
