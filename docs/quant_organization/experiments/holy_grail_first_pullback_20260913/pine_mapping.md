# 聖杯・研究用Pine仕様対応

2026-09-14。ユーザーの不採用後の「一応 pineコードを書いて」に基づく研究・可視化用下書き。
状態は **REJECTED_TRAINING_ONLY / TV_UNVERIFIED**。本番移植の合格物ではない。
入力は本実験の `hypothesis.md`、`protocol.json`、Python研究実装と `validation.md`。
出力は `scripts/tradingview/holy_grail_first_pullback_rr1_research.pine`。

## 導入

1. TradingViewで通常のローソク足チャートを開き、FX通貨と1時間足または4時間足を選択する。
2. Pine Editorの新規strategyに `.pine` 全文を貼り付け、保存してチャートへ追加する。
3. 「研究開始」「研究終了」を設定する。初期値は2010年から2099年で、利用可能な現在の足も表示する。研究学習期間に限定するなら終了を2019-01-01 UTCへ変更する。ただしForex Tester元時刻のタイムゾーンは未確定なのでUTC値の一致は元足の一致を意味しない。
4. 手法の数値は固定。約定後の再計算はON、毎ティック・終値約定・Bar MagnifierはOFFの初期値を保持する。手数料/slippageは0で、Testerはgross。右上の補助費用後Rだけ往復1.8pipsと保有0.2pip/日を引く。Tester側費用を変更した場合、表の「コストなし」は初期設定の説明であり、変更値を自動検出しない。
5. ARM、1st、Entry/SL/TPの価格を確認する。待機注文のTPは「TP仮1R」、約定後はfill callbackでEntryとTPを実約定価格の「TP 1R」へ即更新する。描画はシグナル状態更新とは独立している。過去の取引/取消水準は120注文分を初期表示し、最大150注文分。上限を超えた古い線とラベルのみ削除する。

## 対応表

|Python凍結条件|Pine実装・差|
|---|---|
|自身の時間足EMA20/ADX14|chart OHLCを使用。EMA初値はfirst close、TR/DMはindex1..14のWilder seed、ADXはDX14..27のmean。チャート履歴開始が違えばseedも違う|
|250観測足warmup|`bar_index >= 249`。指定開始前のchart足でwarmup。開始前episodeは持ち越さない|
|ADX30上抜け、DI優勢、終値がEMAトレンド側|同じ厳密不等号。arm足は接触判定しない|
|ADX<25またはDI優勢喪失でreset|確定足で解除。同じ足に新規30上抜けがあれば反対方向armも可能。既存保有は決済しない|
|最初のEMA接触で消費|前足完全離脱/終値の向き/保有の有無にかかわらず消費。条件外の初回を次回へ置換しない|
|押し期間の極値SL|方向極値の最新同値更新を含め、anchor次足からtouchまでのmin/max。touchでsignalを評価した後にanchor更新|
|touch高値+point / 安値-point の逆指値|`syminfo.mintick`使用。元metadata pointと異なる配信では注文価格が違う|
|次の3観測足だけ有効|signal終値でstop注文、`process_orders_on_close=false`。3本目の約定機会後に取消。resetも当該足の約定処理後に取消|
|実約定価格から全決済1R|fill callbackで`strategy.position_avg_price`からSL距離を計算し、TPを設定。SLはsignal時の固定価格。100%全決済|
|決済足で新規なし|`lastExitBar`で禁止。fill callbackはepisode・setup生成を進めず、確定足の通常計算でのみ状態更新|
|SL側始値なら未約定注文を即取消|**完全再現不可**。close-only Pineは始値で未約定注文を事前取消できない。その足でTVが約定していれば取り消せず、未約定なら終値で取消。追加tick/未来情報を使った補正はしない|
|同足SL優先、entry前のSL接触も保守的SL|**完全再現不可**。TVは推定OHLC経路で順序決定。entry前のSL接触を後付け損失にしない。Bar Magnifierで結果はさらに変わる|
|有利target gapはTP価格に上限|TVは有利gapで始値改善を付け得る。SL不利gapもTVの約定規則を使う|
|固定往復1.8pips＋ceil保有日×0.2pip|Testerはgrossの固定1単位。補助表は各取引をriskで割った等R、費用をpipsで引く。保有期間終点は決済足`time_close`の保守的近似で、Pythonのgap時始値・部分足の元実時刻と異なる|
|phase最終足で強制清算|Pineの終了入力は新規停止と未約定取消のみ。保有は既存SL/TPへ継続。チャート最終足での後付け清算はしないため、Python期間境界清算とは異なる。endTime到達足でも取消は通常終値計算時となり、その前に既存stop注文が約定する場合がある。endTimeは厳密な最終約定時刻ではない|
|Forex Tester M1集約|TVブローカー配信のOHLC・セッション・タイムゾーン・週末足・欠損が異なる。通常足H1/H4でも同一系列とはみなさない|

全注文の`disable_alert=true`。発注先/口座/webhook連携は作成していない。描画・注文管理を含む実機動作は未確認。
`calc_on_order_fills=true`の歴史足再計算ではOHLC確定情報が見えるため、ポジション/closedtradesの変化を検出した呼出しでは指標を利用したシグナル決定を禁止する。指標計算はシリーズとして毎回行うが、状態遷移は一足一回の確定計算のみ。

## 保存成果物との手動照合

[独立検証の入力・約定条件](validation.md)と、保存済み `agent_runs/holy_grail_first_pullback_20260913/completed/h1_first__training__EURUSD__fixed_1p8.json` の取引明細を手動照合する。Data Windowの `Setup direction (fill-independent)` は+1/-1/0で、保有見送りを含む生setupを示す。まず対象日時のOHLC、EMA/ADX、ARM/1stを照合し、次にstop注文価格/SL、実約定/TP、決済を照合する。元足の時刻基準とTV配信の差を先に確認し、上表の差に該当する取引の損益一致を主張しない。

## ローカル確認と公式根拠

`python -m pytest tests/test_holy_grail_first_pullback_pine.py tests/test_holy_grail_first_pullback.py -q`。
2026-09-14実行結果: **27 passed / exit 0** (研究19件＋Pine移植8件)。
構造チェックとPineのincremental anchor設計を別Python実装にしたランダム境界照合。Pine自体を実行/コンパイルするテストではない。

2026-09-14確認: [TradingView公式strategy・broker emulator・fill再計算](https://www.tradingview.com/pine-script-docs/concepts/strategies/)、[確定足の公式定義](https://www.tradingview.com/pine-script-docs/concepts/bar-states/)。
実際のTradingViewでコンパイル、履歴/リアルタイムの約定callback、価格ラベル、取引明細の一致確認を残している。状態 **TV_UNVERIFIED**。
