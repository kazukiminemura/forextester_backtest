# Patrick逆方向swap・想定費用10%以下：Pine仕様対応

状態: `PINE_CREATED_RESEARCH_DRAFT / TV_UNVERIFIED`。ユーザーが指定した未合格条件を、独立した研究用indicatorとして作成。利益戦略の研究合格・本番用移植ではない。

## 正本とファイル

- Pine: `scripts/tradingview/patrick_vp_jst_reverse_cost10_indicator.pine`。
- Pine SHA256: `567cf3c4cfadff7ede0c1d3322393c5eae2866334183c5bc65d9d41549296ea3`。
- 元Pine SHA256: `dc31af681b043540f8566b02f41921ec925a9606b4955b46c54e026b32b2f0f9`。元ファイルは変更していない。
- 固定Python: `scripts/backtest_patrick_reverse_costfilter.py`、SHA256 `a8dcf8752a8037a94c9c59db59b5cc9818d8edd2a41ec32ca400758c162c7cb9`、`min_risk_cost=10`。
- 研究仕様: `docs/quant_organization/experiments/patrick_reverse_costfilter_20261107/protocol.json`、学習結果`agent_runs/patrick_reverse_costfilter_20261107/train/result.json`。
- 当該条件のFT学習2017–2019・通常費用は6,180件/勝率61.12%/PF_R0.945654、厳しめPF_R0.851632。両費用で不採用、選抜なし、後半候補成績は未計算。これらの数値をPine画面の実績として固定表示しない。

## Python→Pine対応

|条件|Python正本|Pine|
|---|---|---|
|追加H4値幅gate|常時OFF|追加の1/2/3ATR gateなし。元の初動0.5ATR、3H4初動+2H4rangeは保持|
|シグナルside|元sideのsetup/VAH・VAL/先触れ/used|`Setup.side`を維持。原シグナル文脈表示も元side|
|候補期間|初動start>=判定−7暦日、completed<=判定|元`selectAtOpen`/削除処理を保持|
|08JST判定|元geometry→逆geometryとSL/C>=10、失敗は次候補|`selectAtOpen`で`executionSide=-s.side`、逆quote、geometry、`costFits`|
|予定水準|逆Entry、逆TP=元SL、逆SL=元TP|`drawPending`は実行side/交換後価格を名称+数値で描画|
|08:15約定|元quoteで元geometry、逆quoteで逆geometryと実SL/C>=10|`process`の`planned`/`actual`/2geometry/`costFits`、失敗は取消のみ|
|実行sideと価格|逆side、元TP→新SL/元SL→新TP|`enterPosition`: `e.side=-s.side`, `e.stop=s.target`, `e.target=e.pendingStop`|
|費用比|C=spread+2slip+3carry、SL距離/C>=10|`filterCost`と固定`MIN_RISK_COST=10.0`。閾値変更inputなし|
|費用|通常1.0/0.1/0.2pip、厳しめ2.0/0.2/1.0pip|元costMode/AskBid/slip/carryを保持。Cは1.8/5.4pip|
|期限・決済順|3暦日/金20UTC、OPEN期限→SLgap→TPgap、同分SL優先|元の処理順を保持し、実行sideのAskBidを使う|
|先触れ|元side/元targetで決済分の極値を判定後に更新|`f_touch(s.side,s.target,...)`を変更しない|
|数量/損益|新SL距離+保守費用を分母、entry資産1%|元分母/資産会計を保持し、交換後SLが入る|
|勝率/PF|winsはpnl>0、PF_RはRの正負合算|勝率は元pnl判定。追加profitR/lossRでPF_R、口座金額PFと別表示|
|表示|Entry/TP/SLを価格で保持|逆sideのBUY/SELL、予定/実約定の交換水準、今日/保有中/過去切替と元フォントを保持|

元の3本初動からの構造的TP/SLをswapするためRRは可変。今回のユーザー指定を優先し、一般RR1規約によって価格を変更していない。利確幅・損切幅を保つmirror方式ではない。

## 導入と期間設定

1. TradingViewのPineエディタで新規indicatorを作成し、上記.pine全文を貼り付ける。
2. 1分足または15分足の通常ローソク足へ追加する。15分足は`request.security_lower_tf`の利用可能なM1を時刻順に仮想再生する。
3. 費用シナリオを通常/厳しめから選ぶ。JPYの1pipは0.01、他FXは0.0001を自動設定。必要なら費用1pip価格幅inputを調整する。
4. 通常利用の既定ENTRY期間は2017-01-01以上、2099-01-01未満（UTC）。現在の価格表示が過去の学習終端で停止しないよう元の長い期間を保持した。学習sliceを比較する場合のみ、ENTRY終了を2020-01-01 UTCへ手動変更する。2017以前のwarmupと年末保有の決済尾部が必要。
5. 集計表は既定ON（OFF可）。PF_R/口座PF/勝率を区別し、研究未採用・後半収益未検証・FTとの価格/volume差を表示する。Entry/SL/TPと過去水準は名称と価格を確認する。

ENTRY期間を2020年以降へ広げて仮想再生することは可能だが、そのPine集計は新しいFT研究合格や独立した後半検証を意味しない。標準Strategy Testerと同一ではなく、外部注文/アラート送信/口座連携は実装していない。

## 照合サンプル（単純な価格例）

JPY価格・通常費用: spread0.01、slip片道0.001、carry日0.002、C=0.018。08時Bid100、原買い/原SL98/原TP102なら、逆SELL参考100、新TP98、新SL102、SL/C=111.11で候補採用。08:15Bid100.4なら元買いquote100.41の元geometryと、逆SELL100.4/TP98/SL102の逆geometry・実SL/C=88.89を確認し約定する。予定表示を実約定と混同しない。

原売り/原SL102/原TP98の場合は、逆BUYのquote100.01、新TP102、新SL98。元VP/先触れは原売りsideのまま、新SL距離は2.01となる。費用が上がるとCも上がるので採否・取引数が変わる。

08時の比率を満たしても、08:15のgapでSL距離が10C未満または方向不成立なら取消し、その時刻に別候補を再選抜しない。元TP先触れも従来どおり取消要因。同一分に新TP/新SLの両方へ達した場合は新SLを優先する。

## 確認範囲・限界

- ローカルの構造/価格式assertはexit0。元`f_week`〜H4検出/ATR/週VPと、`renderTradeLevels`が文字列完全一致すること、2時点の固定費用判定、実行side/交換SLTP/数値ラベル、元side先触れ維持、後半期間をinputで扱うことを確認した。
- ローカルassertはPineコンパイルではない。実TradingViewのコンパイル/表示/新規シグナルのruntime証拠は主担当が確認する。確認前はTV_UNVERIFIED。
- FT保存時計UTC/BidとTradingView feedが同じとは保証しない。TVのvolume代理やM1履歴上限・欠落により同一週VP/形/件数/PFになるとは限らない。初期部分週を除外し2完成週+ATR20を要求する。
- 15分足では親足確定後、1分足でも各M1確定後に仮想処理するので、画面表示は仮想時刻より遅れる。08時/08:15のラベルは仮想約定時刻であり、即時発注を保証する通知ではない。
- 未採用の学習結果を踏まえた研究用の別ファイル。全元Pine/研究コード/元履歴は変更していない。

## 確認した公式仕様

2026-11-07、TradingView公式Pine v6 docsの[Other timeframes and data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/)で`request.security_lower_tf`のintrabar配列/取得範囲制約、[Chart information](https://www.tradingview.com/pine-script-docs/concepts/chart-information/)で`barstate.isconfirmed`、[Methods](https://www.tradingview.com/pine-script-docs/language/methods/)と[Objects](https://www.tradingview.com/pine-script-docs/language/objects/)でUDT/methodの構文を確認した。新しい外部APIやデータを送信していない。
