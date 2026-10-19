# 聖杯 研究用indicator 独立品質監査

- 実験ID / 担当 / 次担当: `holy_grail_first_pullback_20260913` / quant_auditor / 研究責任者。
- 監査日: 2026-09-14 JST。
- 判定: **DELIVERABLE_RESEARCH_ONLY / TV_UNVERIFIED**。研究用indicatorとして引渡し可。確認範囲では差戻しを要する実装不整合は発見していない。
- 編集したファイル: この indicator_audit.md のみ。Pine・テスト・対応表・凍結Python・原データは変更していない。
- 実注文・アラート作成・口座接続・外部公開・TradingView操作: なし。

## 対象と識別子

|監査対象|SHA256|
|---|---|
|scripts/tradingview/holy_grail_first_pullback_rr1_indicator.pine|4993caa171d2915ce78a1d6266bbb62f1b029c55f3e5a7074f13417c5be4c2a0|
|tests/test_holy_grail_first_pullback_indicator.py|7cc80211e365795af7d79e873df897250870f8362bc32620c37ed05b5a393176|
|同実験indicator_mapping.md|2f0126c2cfcae5c86edeeaeb76a6b64d7356e699ed5cb493ba790f8e15a3c441|

比較対象は同実験hypothesis/protocolと凍結Pythonのgenerate_setups、entry_fill、exit_fill、simulate。completed/code_input_hashes.jsonの8ファイルを現在ファイルから再計算し、全一致を終了コード0で確認した。研究採用判定は `REJECTED_TRAINING_ONLY` のままで、indicatorの作成は研究合格を意味しない。

## 重大度付き所見・残る制約

|ID|重大度|所見・判定|
|---|---|---|
|IA01|Medium / 開示済み制約|Pineコンパイラ、チャート描画、リアルタイム通知は未実行。ローカル40テスト通過は実機動作の保証ではない。TV_UNVERIFIEDを維持する。|
|IA02|Medium / 開示済みモデル差|期間後の既存保有はTP/SLまで継続し、Pythonのphase最終足清算を行わない。配信OHLC、足境界、履歴開始、欠損、mintick、Entry足時刻の違いでPythonのシグナル・費用・損益と異なり得る。対応表で開示済み。|
|IA03|Low / 入力解釈|期間判定はPine71行の `time >= startTime and time < endTime`、すなわち足始点ラベル基準。任意の足途中をendTimeに指定した場合に、実際の足内約定時刻を切り分ける機能はない。期間比較は足境界に合わせて行い、厳密な壁時計時刻による執行停止と解釈しない。|
|IA04|Low / 検証範囲|テストは実Pineの純粋約定関数本文を限定構文でPythonへ読み替えて比較するが、indicator全体を解釈実行しない。episode/描画/FIFOはソース照合と独立モデル確認であり、全履歴のPine状態列とPython状態列を実機で一致確認したものではない。|

High/Criticalの所見なし。これらの制約を添えた研究用引渡しを妨げる不備は確認していない。原典の裁量手法全体や実口座収益を再現する成果物とは扱わない。

## 条件対応と処理順の監査

|項目|独立確認結果|
|---|---|
|indicator構文・strategy依存|先頭 `//@version=6`、globalのindicator宣言、overlay、型付き関数/tuple構成を静的確認。Pine内に `strategy.`、request.security、lookahead_onなし。構文確認はコンパイル成功の意味ではない。|
|確定足状態管理|pending/active/episode/累計/履歴描画の更新は120行からの `if barstate.isconfirmed` 内。varipなし。イベントboolは各実行でfalseへ初期化し確定時だけ立てる。指標と右上の現在ADX表示は未確定足でも再計算されるが、仮想取引状態とは別。|
|処理順|期間外pending取消→前足以前のpending約定/SL始値取消/3本失効→active決済→closeによるepisode解除/arm/初回接触→履歴整理/描画。保有がある足のresetで、既に起きた仮想約定を遡及取消しない。|
|first touch消費|arm足を除外し、最初のtouchでspent=true、その後にaway・終値方向・空き判定。無効初回、保有/注文中の見送りでも初回は消費される。resetなしで再上抜けしてもepisode置換しない。|
|構造SL|anchor翌足からtouchまでの逆方向極値を累積。同値方向極値は最新anchorへ移動。touchでのstop計算後にanchor更新するので、現在足の極値を先にanchorへ移す誤りはない。未来pivot/上位足は使用しない。|
|3観測足期限| `bar_index > pendingBar` でsignal足約定を禁止。3本目もentry判定を先に行い、未到達の場合だけ期限切れ。|
|gap entry|SL側始値はtrigger判定前に取消。同値SLも取消。trigger越えの始値でentry、固定SLと実entryの距離からTPを全決済1Rへ再計算。|
|exit|既存保有のSL gapは始値、TP gapはTP価格に上限。その後に通常SL→TP判定。fresh entryでは全足rangeを使いSLを優先する。既存保有で始値TP gap成立後にrangeがSLへ届いてもTPとする順序はPythonと一致。|
|決済足再発注|lastExitBarで禁止。episode・初回消費は保有と独立して継続。|
|費用|gross価格差から往復費用とceil保有日数の仮定費用を各取引1回控除しriskで割る。gap exitはtime、足内exitはtime_closeを終点とする。含み損益は表の対象外と表示。|
|期間境界|期間外pending取消をentry処理より前に行うため、旧strategy版で開示した「期間外足で先にbroker emulator約定」の問題はこのOHLC模擬処理には持ち込まれていない。ただしIA03の足始点ラベル基準は残る。|

## 価格付き履歴と配列

待機時は候補Entry・SL・仮TPの3線/3ラベル。約定時は候補Entryを元価格に残して終端を固定し、別の約定Entry線/ラベルを追加する。stopは固定、TPは実entry基準へ更新する。名称とformat.mintick価格を持ち、取消/期限切れ/TP/SL状態も表示する設計。

historyCountsは待機/取消注文3、約定注文4を記録し、line/label双方を同数だけFIFO削除する。pendingまたはactive中は新規注文を作らないため、約定Entryを追加する時点で現在注文が配列末尾にある。keepLevels最小1なので削除対象が現在注文になる経路はない。最大120注文×4=480オブジェクト/種、次候補3個を作ってから削除する瞬間も理論上483個/種で、500上限内。

監査者は別のread-only Python FIFOモデルでkeepLevels=1/100/120、各5,000注文の約定/取消混在を確認し、line/label順序一致、count合計一致、現在注文保持を終了コード0で確認した。Pine描画APIを実行したテストではない。

## アラート・状態表示・参照

- globalのalertconditionはsetup/entry/TP/SLの正確に4種、title/messageは定数文字列。setupは実際にpendingを作成した場合、fill-independent Setup方向は保有見送りも含む。entryとSLが同じ確定足で両立することを対応表で説明している。
- 始値/足内価格による模擬イベントの通知時点は足終値。実際にその価格時点で通知したと主張せず、終値観測と表示する。
- [TradingView公式Alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/)を2026-09-14に確認し、globalのalertcondition、定数メッセージ、UIから条件別にアラートを作成する方式と照合した。監査者はアラートを作成していない。
- タイトル、冒頭コメント、右上表に研究用・不採用・TV_UNVERIFIEDを表示。Strategy Tester非対応、OHLC模擬・同足SL優先、保有中は集計外を区別する。
- indicator_mappingの相対リンクはテストにより全て実在確認済み。凍結仕様、独立検証、indicator本体、保存EURUSD H1明細を参照し、比較サンプル表の価格例もf_entry/f_exitと整合する。

## 実行したコマンド・結果

```powershell
python -m pytest tests/test_holy_grail_first_pullback_indicator.py tests/test_holy_grail_first_pullback.py -q
```

**31 passed in 0.13s / exit 0**。

```powershell
python -m pytest tests/test_holy_grail_first_pullback_indicator.py tests/test_holy_grail_first_pullback_pine.py tests/test_holy_grail_first_pullback.py -q
```

**40 passed in 0.21s / exit 0**。indicator追加12件、既存strategy9件、凍結Python19件。

実Pineのf_entry/f_exit関数本文を抽出するテストは、205始値×4range幅×long/shortでentry1,640ケース、同条件×fresh/既存でexit3,280ケース、合計4,920ケースを凍結Pythonと照合する。別にgap entryからRR1を再計算して同足SL優先を検査する。限定構文のPython読替えであり、Pineコンパイラの型・スコープ・描画・全状態列の試験とは区別する。

## 最終引渡し

**DELIVERABLE_RESEARCH_ONLY / TV_UNVERIFIED**。ユーザー指定のindicator版として引渡し可。研究自体は不採用のまま。TradingView上でのコンパイル、通常足H1/H4での履歴線/ラベル保持、リアルタイム確定通知、配信差を調整した明細照合が未確認。これらを確認済みと報告しない。
