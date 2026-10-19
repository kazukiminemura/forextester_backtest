# 聖杯・研究用indicator対応表

ユーザーの「indicatorにして」に基づく研究表示版。状態は `REJECTED_TRAINING_ONLY / TV_UNVERIFIED`。
[凍結仕様](hypothesis.md)と[独立検証](validation.md)の不採用判定を維持する。
[indicator全文](../../../../scripts/tradingview/holy_grail_first_pullback_rr1_indicator.pine)を新規作成し、既存strategyは保持した。

## 導入と表示

1. 通常のFXローソク足チャートをH1またはH4で開く。
2. Pine Editorで新規インジケーターを作り、既存テンプレートを全削除して上記ファイルの全文を貼る。1行目は `//@version=6`。
3. 保存してチャートに追加する。研究開始/終了はUTC入力。初期期間は2010年から2099年で、読み込まれた履歴に計算対象が限定される。
4. `ARM`はADX episode開始、`1st`は最初のEMA接触の消費。条件外の初回接触にも1stが付く。`Entry候補`は次足以降の逆指値候補、`Entry約定`はOHLC模擬約定。TPは約定前が仮1R、約定後が実際の模擬Entry基準1R。SLは固定。
5. 右上表は模擬決済のみの費用後R/PF/勝率。保有中の含み損益は含まない。indicatorはStrategy Tester非対応。

Entry候補/約定Entry/TP/SLには名称と価格を併記し、通常100注文、設定で最大120注文分を残す。上限超過時は最古の注文の全オブジェクトをまとめて削除する。ギャップ約定でもEntry候補は元価格に残り、別の約定Entryを表示する。TPは実約定基準に更新される。

## 仕様対応

|凍結条件|indicatorの処理|
|---|---|
|EMA20・ADX14・250本warmup|既存strategyと同じseed式、`bar_index >= 249`。開始前のepisodeを持ち越さない|
|ADX30上抜け/DI優勢/EMAトレンド側終値|確定足のみ。arm足で接触を判定しない|
|ADX<25/DI優勢喪失で解除|その足のentry/exit処理後、終値でpending取消。既存保有は継続|
|最初の接触だけ|前足離脱不成立/逆向き終値/保有中でも初回を消費。次回へ置換しない|
|押し期間極値SL|最新同値anchorの次足から接触足までの極値±1tick。接触評価後にanchorを更新|
|次3観測足のstop entry|接触高値+1tick/安値-1tick。signal足では約定しない。3本目の約定機会を与えてから失効|
|SL側始値は未約定取消|entry判定より先に実行。始値がSLと同値でも取消|
|entry gap|triggerを超えた始値で模擬約定。SL距離と全決済RR1をその価格から計算|
|既存保有のgap|SLを越えた不利gapは始値、TPを越えた有利gapはTPに上限|
|同足の両到達|entry足を含めSL優先。entry前のSL接触でも全足OHLCで保守的にSL扱い|
|決済足の新規なし|`lastExitBar`で制限。episodeと初回消費は継続|
|費用|往復1.8pips＋保有0.2pip×ceil暦日を控除。費用は価格水準へ加えず、決済後のRへ1回反映|
|期間境界|終了時刻以後のpending約定を停止。既存保有はTP/SLまで継続。Pythonのphase最終足強制清算とは異なる|

インジケーターはリアルタイム足で再計算されるが、状態・約定・通知は `barstate.isconfirmed` のときだけ更新する。したがって始値/足内到達という模擬価格は、その足の終値時に観測結果として通知する。未来足の使用やバックデートした通知ではない。確定前の価格推移ではEntry/TP/SLイベントを確定しない。

## 配信差・約定差・通知

Forex Testerは独自M1集約、TradingViewは選んだ配信元のOHLCであり、時刻基準、H4起点、週末足、欠損、チャート履歴開始によるEMA/ADX初期値が異なる。`syminfo.mintick`が元metadata pointと違えば候補/SLも変わる。pipはJPY建て0.01、それ以外0.0001のFX既定、異なる銘柄は手動指定が必要。

保有費用はEntry足の `time` からexit gapなら同足 `time`、足内exitなら `time_close` までを使用する。Pythonは元データの実際の最初のM1時刻を使うため、欠損を含む部分足では費用日数が異なり得る。Bid/Ask差・実スリッページ・実スワップは再現していない。非標準足では合成OHLCになるため比較対象外。

通知条件はsetup/entry/TP/SLの4種。TradingViewで必要な条件を選び「バーの終値ごとに1回」に設定する。setupは実際にpendingを作った場合だけ通知し、Data Windowのfill-independent setup方向は保有見送りも含む。Entry足でSLも到達するとentryとSLの両条件が同じ確定足で成立する。自動アラート作成、webhook、発注口座接続は含めない。

## 比較サンプル

ローカルテストはPineファイルにある `f_entry` / `f_exit` の実際の関数本文を限定構文でPythonへ読み替え、凍結Python関数と比較する。Pineコンパイラーやindicator全体の実行検証ではない。

|方向/状態|設定とOHLC例|期待イベント|
|---|---|---|
|long候補|trigger100 / SL98、次足O101 H106 L94|Entry101、risk3、TP104へ更新、同足SL98で全決済|
|short候補|trigger100 / SL102、次足O99 H106 L94|Entry99、risk3、TP96へ更新、同足SL102で全決済|
|long候補取消|trigger100 / SL98、O98 H105 L97|Entryなし。SL側始値で取消|
|long保有のSL gap|Entry100 / SL98 / TP102、O97 H103 L96|SL97、不利gapは1Rを超える損失|
|long保有のTP gap|Entry100 / SL98 / TP102、O104 H105 L97|TP102。始値でTP到達済みのため後続rangeのSLより先|
|long保有で両到達|Entry100 / SL98 / TP102、O100 H103 L97|SL98優先|
|候補3本目|1・2本目で未到達、3本目H100以上かつO>98|3本目にもEntry可能。未到達なら終値で期限切れ|

実データ比較には[保存済みEURUSD H1明細](../../../../agent_runs/holy_grail_first_pullback_20260913/completed/h1_first__training__EURUSD__fixed_1p8.json)を使用する。まず対応足のOHLC/EMA/ADX/ARM/1stを確認し、Data WindowのSetup方向、Simulated entry、Simulated exit、Exit net R、Exit reasonを照合する。異なる配信で損益一致を保証しない。

## 確認状況

実行コマンド: `python -m pytest tests/test_holy_grail_first_pullback_indicator.py tests/test_holy_grail_first_pullback_pine.py tests/test_holy_grail_first_pullback.py -q`。
2026-09-14実行結果: **40 passed / exit 0**。indicator追加12件、既存strategy/Python28件。関数比較はlong/short・fresh/既存保有を含む4,920 OHLCケース。
ローカル構造と約定関数境界の検査。TradingViewでのコンパイル・描画・リアルタイム通知は `TV_UNVERIFIED`。

2026-09-14公式確認: [Pine実行モデル](https://www.tradingview.com/pine-script-docs/language/execution-model/)、[アラート条件](https://www.tradingview.com/pine-script-docs/concepts/alerts/)。
