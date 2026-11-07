# Patrick swap逆・費用比K10 Pine：品質監査

担当: quant_auditor。2026-11-07 JST。状態 `TV_COMPILE_AND_DISPLAY_CONFIRMED_LIMITED`。研究用として引渡し可。

## 依頼範囲

ユーザーが学習6,180件・勝率61.12%・PF_R約0.946（厳しめ約0.852）のK10研究条件のPine作成を明示依頼した。元Pythonの学習不採用・後半未実走は維持し、研究用として分離する。利益戦略の研究合格・本番採用として移植しない。旧Pine・Python・結果を上書きしない。

正本は`backtest_patrick_reverse_costfilter.py`の閾値10、swap逆方向、H4追加gate OFF。C=spread+2slip+3carry、08時候補選抜で新SL(原TP)距離/C>=10と逆geometry、不適格なら次候補、08:15実quoteで再確認し失敗なら取消のみ。原selectorのsignal sideと実行reverse sideを分離し、原VP/原TP先触れ/使用済み/候補7日を保持する。

## 重点監査要件

1. 予定表示も逆side・逆quoteを用い、予定SL=原TP、予定TP=原予定SL。Entry/TP/SLは名称と数値価格で表示し、約定後の逆side水準・過去水準を保持する。元Pineの予定TP/SLをそのまま描画しない。
2. 原H4/VPのVAH/VAL文脈はsignal sideで表示し、逆取引の方向と混同しない。実約定・同始値SL・gap・期限・同足両到達SL先・分母・slip/carryはexecution sideで計算する。
3. 勝率はpnl>0/closed。PF_Rと複利口座の金額PFを別名で示す。学習の保存16通貨合算PF_Rと、TVの現通貨/取得できた履歴のPFを同一と扱わない。
4. 当初検討した学習期固定では現在期間のEntryが出ず、TVのM1履歴上限では学習期間も取得できない。主担当がplan.jsonで既定2017〜2099を固定し、現在観測を可能にした。学習再現は終了2020-01-01へ設定し、後半収益未検証のpanelを既定ONにする。現在チャートの集計をFT学習集計と混同しない。
5. 静的/合成検証とTradingViewの実コンパイル・表示を区別する。最終source SHAと貼付コードの一致、実機で確認した範囲、未確認事項を証拠に基づき判定する。

主担当へ上記予定SL/TP反転表示と原文脈side分離、初期期間による無信号の扱いを早期報告した。plan.json、README.md、mapping.mdと新Pineを現物確認した。監査担当の編集は本書のみ。

## ソース対応の独立監査

現時点の新Pine SHA256は`567cf3c4cfadff7ede0c1d3322393c5eae2866334183c5bc65d9d41549296ea3`。元Pine `dc31af681b043540f8566b02f41921ec925a9606b4955b46c54e026b32b2f0f9`、Python正本 `a8dcf8752a8037a94c9c59db59b5cc9818d8edd2a41ec32ca400758c162c7cb9`の対応を確認した。新ファイルは元コードを上書きしていない。

監査側Pythonの文字列block比較（exit0）で、UTC/JST週、touch、weekend、期限、週VP、detect、finishH4、既存の今日/履歴renderの9blockが旧Pineと完全一致した。`process`は08:15entry blockを旧本文へ戻すと全文一致。`selectAtOpen`も宣言されたK10逆quote/逆geometry/費用guard、逆pendingQuote、表示status以外は全文一致した。

08時の不合格はloop継続、08:15の再check不合格は取消のみ。Setup.sideとtouched/usedを保持し、e.sideだけ逆、SL=原TP、TP=原pendingStop、新quoteと新SLから分母を計算する。予定と実価格ラベルも交換後で、原VP文脈はsignal sideを明記している。pnl>0勝率とprofitR/lossRによるPF_R・口座金額PFを分離している。現時点で重大な対応不整合を認めない。

これらは静的対応確認であり、Pineコンパイル・TV上の取引再現成功ではない。最終testと実機証拠を待つ。

## 独立検証証拠の監査

validation.mdに保存された両signal side各6ケース、合計12ケースの独立合成結果を確認した。K10等号/直下、08時通過後の08:15再拒否、08時参考と実quoteの区別、swap価格維持、新SL/TP両到達SL先、08時同M1極値をOPEN選抜へ先読みしないことが検証されている。正本Pythonの有限ケースとPine sourceの式/順序の照合であり、Pine実行環境のテストと誤記していない。

この時点で未解消の重大なソース対応不備は認めない。ユーザー指定の未採用条件を研究用Pineとして渡す範囲では妥当だが、TVコンパイル・実表示・貼付本文の最終同一性の状態は主担当の証拠を受けて別途確定する。

## 実機確認前の引渡し判定

**ソースと有限境界確認の範囲では、未採用条件の研究用draftとして引渡し可。** 最終確認したPine SHAは上記567cf3…96ea3。監査担当が確認した証拠に実TradingViewコンパイル・貼付本文同一性・新規取引遷移の記録はまだないため、その部分は`TV_PENDING / TV_UNVERIFIED`のまま。ローカルPASSを実機成功と読み替えない。

主担当の実機証拠が得られた場合は、実際に確認した銘柄/時間足/コンパイル/価格表示の範囲と未確認事項を追記する。後半の経済研究未実走・学習不採用の判定は、Pineの作成や実機コンパイルによって変更しない。

## TradingView実機の確認範囲と最終判定

監査担当が最終Pineとエディタ読み戻し本文を照合した。本文は36,275文字で完全一致し、両ファイルのSHA256も`567cf3c4cfadff7ede0c1d3322393c5eae2866334183c5bc65d9d41549296ea3`に一致した。[エディタ読み戻し](../../../../agent_runs/patrick_reverse_cost10_pine_20261107/editor_readback.txt)

主担当はTradingView DesktopのPine Editorで「Add to chart」を実行し、OANDA:EURJPYの15分足でコンパイル後のインジケータ名、損益パネル、過去のEntry・TP・SLラベルを確認した。チャート上の観測範囲は2026-08-02〜11-06、28決済、PF_R 0.405。値の出典は当該TradingViewフィードの動作確認時のパネル。画面の確認は主担当の観測報告に基づく。

元インジケータと表示が重なったため、個別取引のEntry・TP・SLの価格関係を画面上で照合する検査は未確認。取引ごとのForex Testerとの一致と2020年以降の独立経済検証も未確認で、学習時の不採用判定を維持する。今回の証拠に基づき、コンパイルと上記表示を確認した研究用Pineとして引渡し可と判定した。
