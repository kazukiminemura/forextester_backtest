# no_dow Pine 研究用移植・独立品質監査

現行対象は末尾追記の**indicator版**。旧strategy版はその後ユーザーから実行時の配列範囲外エラーが報告されたため使用非推奨。以下の旧監査は履歴であり、旧版の正常実行を保証しない。

2026-09-26 / 担当: stock_audit（Pine開発担当とは別）。

判定: **AUDITED_RESEARCH_DRAFT / NOT_ADOPTED / TV_UNVERIFIED**。
ユーザー明示の研究用参考移植として限定的に引渡し可。通常工程の「合格戦略だけをPineへ」の例外は本実験hypothesis.mdに明記されている。研究採用・TradingViewコンパイル成功・実運用承認へ昇格させない。

## 対象・識別子

- Pine: `scripts/tradingview/research/tamukai_stocks_no_dow_rr1_strategy.pine`
- 対応説明: `docs/tamukai_stocks_no_dow_pine.md`
- 信号原本: `scripts/research_tamukai_stocks_jev.py::candidate_signals(..., "no_dow")`
- 会計原本: `scripts/research_tamukai_stocks_daily.py::simulate`
- 規約、board、今回hypothesis、上記4ファイル、主担当所有の構造テストを読取照合した。監査担当は本auditのみ編集し、戦略・テスト・研究成績は変更していない。

| ファイル | SHA256（監査時点） |
|---|---|
| Pine | `eb19d626c7ae8ec55301778235d48b6c1525b7b292456515252445c6a0ddca49` |
| no_dow Python | `3c1267a497d5ddf40848720da18b2c7ada56cdf54e7c09e57782f1b40c114b50` |
| 日足会計 Python | `ea45264616f7f8f83f835571cd1fbd9f73e20560456b75f460e0ed2f3387c6b7` |
| 構造テスト（最終6件） | `816f91a17f43a1e64ffe4c39e78f3444b9213f4bf2a3ff04cb5c3f01106a9d82` |
| 保存データmanifest | `fdaf2c5e0d283d853cc295faf13cd031fbc2c03de3aa43e4301d32d83e12866b` |

## 重大度付き所見

### 高・未確認: TradingViewでの実コンパイル・実行

主担当から、匿名TradingViewのTSE:7203・D1の新規エディタへ当該ソースを貼り付け、Add to chartでSign in要求となり停止したとの報告を受領。コンパイラ応答なし。監査担当は保存画像 `agent_runs/tamukai_stocks_no_dow_pine_20260926/tradingview-login-required.png` のSign in表示を確認したが、実ブラウザ操作や貼付全文照合は独立再実行していない。従ってローカルtests成功をコンパイル・チャート表示・実行性能の証明に代用しない。認証後に同一SHAの追加、Entry/SL/TP、同日決済、無効gap、注文不成立、通常終値と約定再計算の境界を確認するまでTV_UNVERIFIED。

### 中・既知差分: 約定会計はPythonとの完全一致移植ではない

1. 次足始値が固定SL以下ならPythonは取引なし。Pineは前日成行が既に約定するので`immediately = true`で全決済し、INVALID GAP表示・counterを残す。費用や約定の差は消去しない。
2. Pythonの同足両到達は寄付gap優先、その後SL優先。PineのbracketはTradingView推定経路を使う。明示的なSL優先実装ではなく、この差を導入文書は正しく開示している。
3. Pythonは期間末終値で全決済するがPine終了日時は新規信号停止だけ。前営業日提出注文が終了日時以降に約定し得るし、既保有は継続する。
4. 端株数量、銘柄の最小数量、呼値、配信・調整設定、必要資金が異なり得る。Pine資産比率`100 / 1.001`は0.1%費用分の余裕であり、Pythonの各約定数量一致の証明ではない。片道費用変更時はこの比率の変更も必要。
5. `varip`で実position/closedtrades変化を検出してfill callbackを信号判定から除外している。通常closeが別に実行されれば決済日終値から新しい翌日注文を出せる。fillと通常closeが重なる境界で通常実行が省略される場合の信号取り逃し、リアルタイムrollback/注文不成立の挙動はPine実機未確認。差分説明にも記載あり。

上記は研究用近似移植として許容するが、Python収益の再現や実注文用の完全移植としては引渡し不可。

### 中・継承制約: 不採用・既閲覧・価格データ品質

no_dowは訓練基準を不通過だった固定参考戦略。後期黒字は選抜合格へ昇格させない。全2017–2025年既閲覧で真の未使用期間なし。保存YahooデータのSony調整未解明、8306/8035の2022-05-17高安修復、現在大型株への選択バイアス、配当・税・実滑り・金利なしを継承する。Pineは保存CSVではなくTradingView配信を使う。1銘柄10万円チャートであり10銘柄100万円の集計ではない。

### 低・表示上限

Entry/TP 1R/SLは名前と価格を表示し決済後線を保持する。同日保有は視認性のため1本先まで線を描くが将来価格の参照ではない。GC最大500個（概ね165取引）のため全履歴永久保持ではない。決済後描画は通常終値処理待ちで、実画面未確認。色だけに依存せず名称・価格を併用している。

## 条件対応と先読み確認

| 元条件 | Pine対応 | 読取結果 |
|---|---|---|
| 24本目以降 | `bar_index >= 23` | 一致 |
| 終値>SMA21>SMA21の2本前 | `close > sma21 and sma21 > sma21[2]` | 厳密不等号一致 |
| prior3いずれかlow<=同足SMA21 | `low[1..3] <= sma21[1..3]`のOR | 一致 |
| 終値>prior3高値 | `ta.highest(high[1], 3)` | 信号足を除外、一致 |
| SL=prior3最安値固定 | `ta.lowest(low[1], 3)`を注文時保存 | 信号足を除外、保有中追従なし |
| RR1全決済 | 実`position_avg_price`+実Entry−SL、`qty_percent = 100` | 意図一致、実fillは未確認 |
| 翌足買い、買いのみ1保有 | close判定内成行、process_orders_on_close=false、pyramiding=0 | 意図一致 |
| no_dow | pivot/HTF/ATR/SL幅条件なし | 移植漏れでなく対象仕様 |

約定callback内は固定SLと実約定価格を使用し、当日完成高安・終値を新しい注文信号へ使用していない。`barstate.isconfirmed`単独でなく`not fillExecution`と1bar1decisionの条件がある。`request.security`、lookahead、未来オフセットなし。標準1日足以外はruntime.error。アラート/外部発注コードなし、entry/exit/close各注文はdisable_alert=true。Pineの設定を利用者が変更した場合は監査対象設定と別条件となる。

## 監査担当が実走した範囲

- 初回Pine構造4件成功後、主担当が信号式・callback制御契約を追加。最終 `python -m pytest tests/test_tamukai_stocks_no_dow_pine.py tests/test_tamukai_stocks_jev.py tests/test_tamukai_stocks_daily.py -q`: **16 passed / exit 0**を監査担当も再実行（Pine6件+既存4件+日足6件）。Pineテストは文字列/構造契約で、コンパイラでもエミュレータでもない。
- 保存10CSVのSHAがmanifest一致。独立の`math.fsum`・21本窓から再計算した式と元Pythonを全23,140足で照合し、None/SLを含め全一致、素信号1,184件。期間・保有制約をかける前の信号であり1,184トレードではない。
- 信号/SL/fill guard/固定RR/無効gapのPine式10件を追加read-only assertしexit 0。
- position/closedtrades比較のguardを独立抽象イベント列4例で確認: 履歴entry→exit callbackは両方抑止、リアルタイムentry→exit callbackも抑止、後続通常closeは1回許可、同bar再実行は抑止、通常closeが無ければdecision無し。**Pineランタイムのイベント順序を実測したテストではない**。

| 銘柄 | 保存足 | 素信号 |
|---|---:|---:|
| 7203.T | 2314 | 123 |
| 6758.T | 2314 | 132 |
| 8306.T | 2314 | 128 |
| 9432.T | 2314 | 117 |
| 9984.T | 2314 | 102 |
| 6501.T | 2314 | 116 |
| 6861.T | 2314 | 111 |
| 8035.T | 2314 | 129 |
| 8058.T | 2314 | 111 |
| 4502.T | 2314 | 115 |

独立信号照合はPowerShell here-stringを`python -`へ渡してread-only実走。CSVを標準csvで読み、各終値21本を`math.fsum(window)/21`で再計算し、上記対応表を直接式にして原本no_dowとのリスト完全一致をassertした。保存対象は本結果のみで、別検査スクリプトは作成していない（実行コードは当タスクのツール記録）。

## 一次資料と次工程

2026-09-26に[TradingView公式Strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/)を確認。次tick成行、OHLC推定経路、gapの始値約定、約定再計算と先読みリスクをコード/差分説明と照合した。資料確認は実コンパイルの代用ではない。

次担当は主担当。TV_UNVERIFIED・研究不採用・近似差分を付してファイルを案内できる。認証後の実機確認が未完工程。外部公開・実注文・新AI呼出し・研究条件の再最適化は本移植の範囲外。

## 追記: indicator版への変更（2026-09-26）

判定: **AUDITED_INDICATOR_DRAFT / NOT_ADOPTED / TV_UNVERIFIED**。研究用表示ファイルとして限定引渡し可。
対象 `scripts/tradingview/research/tamukai_stocks_no_dow_rr1_indicator.pine`、SHA256 `f09af6439ec63a6226de82392110e1150037397e010dcbdf4e0599b307fc043f`。

- **高・旧版の既知障害**: ユーザー添付のIndex 20 / array size 20エラーは範囲外アクセス。台帳件数とSL配列の対応を崩した具体的イベントは未確定。新indicatorはstrategy台帳・配列アクセス自体を使用しない。旧strategyはSHA `eb19d626c7ae8ec55301778235d48b6c1525b7b292456515252445c6a0ddca49`のままで、修復済みとはしない。導入文書は旧版を使わず新indicatorを案内している。
- **条件/状態の読取照合**: no_dow信号式は同一。確定日足で前日pending→翌始値（open<=SLは見送り）→実Entry基準固定RR1→寄付gap優先→SL優先→TP→無保有なら翌日用新信号の順。単一仮想保有、同日entry/exit、決済日closeから次日用信号を許可し、同日の再エントリーはしない。先読み注文やcallback処理なし。
- **独立実走**: 上記状態遷移をPythonへ独立転記し、保存10株2017–2025年の自然決済**495件**について元simulateとEntry/Exit日・Entry/SL/TP/Exit価格が一致。無効gap **3件**見送り。元の499件に含まれる期間末強制決済**4件**はindicatorにはないため除外。等値見送り、両到達SL、上下寄付gap優先の**4境界assert**成功。転記モデルの確認でありPine実行結果の一致ではない。
- **ローカルテスト再実行**: `python -m pytest tests/test_tamukai_stocks_no_dow_indicator.py tests/test_tamukai_stocks_jev.py tests/test_tamukai_stocks_daily.py -q` → **15 passed / exit 0**（新構造5+既存10）。
- **中・残る限界**: 状態・描画は日足確定後のみ。Entryは翌始値の仮想価格を当日引け後に表示するため、場中通知や約定可能性を示さない。金額損益・数量・費用集計なし、期間末強制決済なし。配信/調整データ差と不採用研究の制約を維持。TradingViewでのindicatorコンパイル・表示は未確認。
- **表示**: 名称と価格付きEntry/SL/TPを描画、決済まで線を延長し完了線を削除しない。同日保有もtime→time_closeの線幅あり。最大500描画のGC上限、実表示未確認。損益機能等は追加していない。

Ponytail方針は、障害を起こした取引台帳との対応配列を新indicatorで不要にし、依頼された単一仮想保有・表示だけに限定する判断に適用。監査担当の編集は本追記のみ。
