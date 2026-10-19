# YTT × Jev 独立検証

2026-10-10 JST。最終判定は **未検証 / NEEDS_EVIDENCE：API不整合3件で事前停止、採用不可**。全1,887送信・1,884有効の部分結果と費用会計は独立一致したが、6,659母候補の完全比較ではない。通常/2倍費用とも全RRの合算期待値は負。改善実績や研究合格を認定しない。以下には結果前ゲート案から最終照合までを時系列の証拠として保持する。本担当は戦略・コード・採用基準を変更していない。

## 確認した入力

- `docs/quant_organization/charter.md`、`board.md`、`.agents/skills/typesafe-ai/SKILL.md`。
- `ytt_monthly5_fx_20261009/{protocol.json,validation.md,data_inventory.md}`。前回D/W M15のUSDJPY継続円口座は通常費用229決済、PF_JPY 0.7516、90万円停止。既存YTT表示機能は利益戦略の合格証明ではない。
- `bb3_jev_20260925/results.md`。同待機AIなし554決済・勝率51.08%・PF_R 0.752に対し、Jev部分結果375決済・50.67%・PF_R 0.741。API欠測が通貨末尾に偏り、完全なAI比較ではない。利益改善は立証されていない。
- `tamukai_stocks_jev_20260926/jev_plan.md`、`scripts/review_bb3_code_with_jev.py`、`scripts/research_bb3_jev.py`を読取確認。新しい送信はしていない。前実験の金額枠・回数枠・キャッシュは新実験の暗黙予算にしない。

## 事前採用ゲート案（責任者の固定待ち）

1. **再現可能な凍結**：仮説、対照、最大候補数、期間、学習範囲、費用、AI用途・質問・モデル・閾値、全入力とコードSHAを結果前に固定する。既閲覧2020–2025を真のholdoutと呼ばない。最終確認は選抜済み候補のみ、既閲覧期間だけなら結論は記述研究に限定する。
2. **時間と情報の整合**：確定足・確定上位足・当時利用可能な情報だけで判断する。過去打切り再計算で一致、pivot右足確定遅延を保持、同足TP/SLは不明ならSL優先、gapと実在始値欠損を検査する。AIが売買に入る場合はAIなし同待機対照、推論遅延、欠測、未送信、無効応答、重複を全件台帳に含める。AI補助レビュー用途なら売買結果への応答依存を禁止する。
3. **十分な件数と費用後採算**：各後期区間で合計100決済以上、3通貨中2通貨以上で各100決済・通常費用後PF_R >= 1.2・期待値 > 0、費用2倍でも合算等R期待値 > 0を案とする。初期案の候補数に収まる固定パラメータ感度とleave-one-symbol-outも報告し、単一設定・通貨への集中を確認する。閾値は結果を見て変更しない。
4. **勝率・RRの改善を分離して証明**：費用後勝率、指定TP/SL比、実現平均利益/平均損失、1取引期待値、元候補1件当たり期待値（見送り0）を別々に出す。同期間・同母集団の対照との差を月block bootstrapで示し、主要改善指標である元候補当たり期待値差の95%CI下限 > 0を案とする。「勝率とRRの両方が改善」と報告するには両指標それぞれの差とCIが必要。建値を表示上の勝ちへ含めても金銭損益は別。損失0・取引0でPFやpayoffが未定義なら合格扱いしない。
5. **口座・通信の上限**：100万円から90万円到達で停止、再入金・再開なしを再現。リスク量、数量刻み、同時保有、円換算時点、終値MTMと足内損失を固定する。異なるクオート通貨の金額は直接合算しない。費用・swapなど未実装を明記する。API上限、送信前引当、モデル版、入力SHA、応答、usage、遅延、失敗停止、再送規則を別台帳に固定する。AI推論費用も円運用結果の費用へ含める。資産90万円停止はgap時の損失10万円以内を保証しない。

各数値は責任者への提案であり、本担当が採用基準を変更・確定するものではない。従来のRR1固定はbaselineとして保存し、ユーザーのRR向上依頼による新しい出口比較は別候補・新仕様として固定する。

## Pineと外部APIの境界

公式のPine `request.*` 一覧には任意URLへのGET/POST関数がなく、指定feed/時間足/企業情報等の取得が列挙されている。この仕様から、Jev HTTPレスポンスをPineへ直接取り込む実装は提供できないと判断する。`request.seed`もPine Seeds用で、任意の推論APIへの同期要求ではない。出典: [TradingView Other timeframes and data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/)（2026-10-10確認）。

TradingViewアラートは外部URLへHTTP POSTを送る方式で、3秒を超える受信処理は取消され、配達失敗もあり得る。Jev結果をPineへ返す機構とは説明されていない。必要なら外部処理側で保存・表示し、受付と推論を分ける設計が必要。今回の読取監査ではendpoint公開、アラート作成、常時サービス、取引接続を実施していない。出典: [TradingView Webhook alerts](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)（同日確認）。

## Jevの出力と実測値

公式APIはstateとquestionsを受け取りtyped answersを返す。Choiceは選択肢の分布、Scoreは定義した段階への分布、Noulは質問へのyes確率である。一般的なセットアップ判定の確率を、将来トレードが費用後に勝つ実測確率として表示してはいけない。売買成績は価格と約定・費用の決定的計算で集計する。[API](https://docs.typesafe.ai/api)、[Confidence](https://docs.typesafe.ai/confidence)（同日確認）。

信頼度閾値は用途別の検証が必要。モデルaliasは更新で挙動が変わるため、再現研究では版IDと実応答modelを保存する。現在公式modelsのaliasはjev-1.13.0を指しているが、新送信時は別途確認する。[Models](https://docs.typesafe.ai/models)（同日確認）。

## 実行と引継ぎ

実施はファイル読取と公開公式資料のGETのみ。戦略バックテスト、Jev推論API、追加テストは未実行。今回の改善値・期間通貨別実績・再現コマンドは未作成であり、実行済みと報告しない。

次の入力は責任者が凍結したprotocol・hypothesis・data_inventory・code SHA。受領後に、仕様一致、未来参照、比較母集団、費用会計、資産停止、API欠測を独立照合する。未実装費用と失敗理由を結果に併記し、判定は未検証／不採用／研究合格とし実運用承認は行わない。

## 実装前検査の追記（2026-10-10）

責任者よりユーザーAPI予算100円承認と、引当上限90円・RR1/1.5/2・1本待機・同待機control・失敗3件停止を受領。本担当は引き続き推論APIを呼ばず、モック通信とローカル再計算だけを実施した。実装が編集中のため凍結確認ではない。検査中の一時点source SHAは `eb791fa4134d60787d3b6330940614a9179bb043b70f3af0456454a962f85989`。

成功（全てPython子プロセスexit0）：

1. RNG seed991、各300本、cash有無×20ケースの40合成軌跡で、新simulateのRR1は旧coreと全取引辞書・曲線・口座辞書が完全一致。時刻gap、先頭M1欠損mask、不完全足を含めた。
2. entry100/SL99の同一価格列でRR1/1.5/2はSL99を保持しtarget101/101.5/102、grossR1/1.5/2となる。
3. signal後の全OHLCを大きく変更しても24本payloadは同一。将来価格を参照しない境界検査。
4. 有効mock応答100tokens×2の精算は0.00168円、同output再実行は2cache hits/0 calls。実通信0。

差戻し事項：

1. 初版inferではrun内failuresしか数えない。10jobs全失敗mockで初回3call停止後、同じoutput再実行で更に3call、累積6callを再現。3失敗停止を実験累積にする修正を責任者へ依頼した。無応答で残ったreservationも不明失敗として安全側に扱う必要がある。
2. 初版load_data(training)は `Invalid breakout or stop` でexit1。3通貨の母候補にsignal close時点でSLが反対側のものが計8件（USDJPY2/EURUSD3/GBPUSD3）。突破は正方向。旧engineは翌始値riskで除外するため、母候補段階にこの状態が存在する。例USDJPY2020-02-25 10:45 BUY、close110.487/SL110.766/break110.476。signal時signed SL情報を保持して遅延側で自然棄却するか、事前除外を全対照へ同じく適用し件数を記録することを依頼した。
3. 最新読取でlater_selectionにtraining SHA・independent_review_passed・RRのgate追加と、円口座にcandidate_coverage_complete/eligible_for_adoption_evaluation=false追加を確認。数値基準の計算と選抜JSONの作成責任をprotocolに固定する必要がある。
4. AI遅延1本の間にD/W方向を再検査しない仕様。signal時の確定D/Wを固定する執行なら整合するが、常時合意条件とは異なるため仮説に明記する。API費用は現runnerでは売買P/L外で明記されており、採用用円期待値には別途控除が必要。

この段階で新研究の期間通貨別成績は未生成。コード修正後の再検査とfreeze照合が必要。

追加の実データ互換検査もexit0。保存executionを読取り、2020–2022 training・通常/2倍費用で新RR1と旧coreを逐次実行し、3通貨のR全取引辞書とUSDJPY円口座・全曲線が完全一致した。R決済数は各費用につきUSDJPY1,386、EURUSD1,615、GBPUSD1,645。円決済は通常229/2倍135、曲線は各74,906行。旧engineとの互換性証明であり、独立した生M1約定再構築やJev利益改善の証明ではない。

## 修正後の送信前確認

完成source SHA `3d77d4539d90e57c5b9cc61d6128e3c16ec862f93ba92628bd080752750ea477` を照合。初版の2不具合は修正後の独立再実行で解消した（exit0）。

- 累積3失敗後の同一output再実行はcall0、failures3、引当1.6515072円のまま。実通信なし。
- trainingのloadは全6,659payloadで成功。USDJPY2,021/EURUSD2,246/GBPUSD2,392、事前risk除外2/3/3を別記。delay_controlとJevは同じ有効母集団。全signal確定時刻がtraining終端未満であることを確認。
- 完成protocolの初回読取時にはexecution_orderがhash順と記載されていたが、実装は通貨別midpoint反復順をround-robinで組み合わせる。実装へ文面を一致させる修正を責任者に依頼。実装自体は結果に依存しない固定順。

以下はAPIを呼ばない失敗停止・入力再現コマンド。

```powershell
@'
import tempfile
from scripts import research_ytt_jev as j
j.client.api_key = lambda: 'test-not-a-key'
def bad(request, timeout):
    raise RuntimeError('mock failure; no HTTP')
with tempfile.TemporaryDirectory() as td:
    jobs = [dict(model=j.MODEL, state={'n': n}, questions={'gate': j.QUESTION}) for n in range(10)]
    first = j.infer(jobs, td, live=True, max_calls=10, transport=bad)
    second = j.infer(jobs, td, live=True, max_calls=10, transport=bad)
    assert first['calls'] == 3 and second['calls'] == 0 and second['failures'] == 3
data, jobs, hashes = j.load_data(j.SOURCE, 'training')
assert len(jobs) == 6659
assert [len(d['deterministic_invalid']) for d in data.values()] == [2, 3, 3]
assert all(d['times'][i] + 900 < j.core.epoch('2023-01-01') for d in data.values() for i in d['bodies'])
print('INDEPENDENT_PRECHECK_PASS; NO_HTTP')
'@ | python -
```

戦略改善の判定は引き続き未検証。送信前の機能検査通過と、勝率・RR・期待値改善の証明を区別する。

## 実API先頭25件の独立診断

主担当が保存した `training_results_smoke25.json` とreserve台帳の先頭25hashを照合。全件trainingは別途実行中であり、この小標本を改善実績や完了として扱わない。本担当からAPI送信なし。

凍結manifest 11ファイルSHAがすべて現在bytesと一致した。最終凍結sourceは `3d9e0f34507019e30265e5aa723f5f672cd3dbbac7785419be037c9d3d1c591a`（送信前追加修正後）。以下の別実装検算はexit0、`SMOKE25_ALL_MATCH`。

|独立照合|結果|
|---|---:|
|response/request hash、model、型、確率範囲・合計、選択最大値、accept規則|25/25一致|
|保存entry900から当時24本OHLC・MTR・D/W・gap・SL・突破値を再構築|25/25完全一致|
|有効数 USDJPY/EURUSD/GBPUSD|9 / 8 / 8|
|accept数 USDJPY/EURUSD/GBPUSD|5 / 1 / 0|
|input tokens|35,120|
|単価×token×200円換算とsettle台帳|0.295008円・全一致|
|実応答時間|min0.160378秒 / max0.230257秒|
|smoke JSONに対応するCSV|60ファイル|
|CSV取引観測（対照・RR・費用の重複あり）|28,478|

CSV各行のrisk=side×(entry−SL)、target=entry+side×risk×RR、net=side×(exit−entry)−cost、netR=net/riskを独立算出。件数・合計R・平均R・勝率・実現payoffをJSONと照合。Jev/covered_controlのentry index−2が対応する元候補集合に含まれることも全一致した。これらは保存結果の会計・情報時点確認であり、全M1による新しい独立約定エンジン再生ではない。

25件は固定送信順の一部に過ぎず、小標本での勝率/PF向上を結論にしない。training全件の最終出力とプロセス終了を確認後に、全応答・費用・選抜ゲートの検算を追加する。

## 最終独立照合：途中停止したtraining

主担当から実行session84865のexit0を受領。最終 `agent_runs/ytt_jev_20261010/training_results.json` の存在・内容・SHA256 `06df3a8cecbba686479265c596d197fc5330a65cf2eb733f903ce6ac665cf8a8`、inference.lock解放、11凍結SHA一致を確認した。exit0は規定どおりの3失敗停止と結果保存の成功であり、全候補評価の完遂ではない。

独立コマンド2本はともにexit0、`RESPONSE_ALL_MATCH` および `INDEPENDENT_REPLAY_ALL_MATCH files=60 rows=37490`。新engineのsimulate/delayed_signals/payload/acceptedを呼ばず、標準PythonとNumPyだけで当時OHLCから全要求、応答判定、遅延信号、M15約定、取引会計を再実装して照合した。原M1からの再集約は今回再実施していない。

1. 全1,887要求のSHA、原entry900から24本OHLC/MTR正規化・上位足方向・gap・SL/突破値を再構築して完全一致。未来足・銘柄名・日付・口座・結果損益を要求stateに含まない。
2. 有効1,884の型、model版、確率値域・合計、選択最大値、0.5閾値、usage上限、latencyを独立検査。一致した。実測応答時間0.144334–0.511465秒。既定1本待機を全条件へ適用し、実測速度に合わせて後から待機を短縮していない。
3. reserve1,887件・settle1,884件に重複なし。確認済み有効usage2,646,595 tokens → 22.231398円、失敗3件の保守引当1.6515072円、管理費用23.8829052円。これは請求確定額ではない。
4. 全60CSV・37,490取引観測（arm/RR/費用重複あり）でentry時刻・SL・TP・risk・exit時刻/価格/理由・grossR/netR・不完全足曝露が別実装と一致。SL優先、gap始値/利確上限、欠損足清算、日次清算、96本、期末を再現。Jevと同待機対照は同じ遅延無効化条件を使用。
5. 全通貨/arm/RR/費用の件数・netR・meanR・PF・勝率・実現payoffをCSVから再集計しJSONと一致。後期選抜・後期API・Pine採用はなし。既存関連テストも52件成功（0.44秒、exit0）。

### 応答欠測と失敗理由

|通貨|有効母候補|有効応答|accept|未評価または無効|
|---|---:|---:|---:|---:|
|USDJPY|2,021|628|196|1,393|
|EURUSD|2,246|628|114|1,618|
|GBPUSD|2,392|628|150|1,764|
|合計|6,659|1,884|460|4,775|

元機械候補は6,667、signal closeでSLまでの正riskがない8件を事前規則で除外。未評価4,775の内訳は無効3と未送信4,772。有効応答の割合は28.2925%。固定順のprefixでありランダムな欠測ではない。

無効3件はいずれも選択と最大確率の不一致で、通信失敗ではない。`0ebc13fb…` はchoice accept0.41に対しuncertain0.42、`4048297e…` はchoice uncertain0.36に対しskip0.37、`a8c3a8f9…` はchoice skip0.45に対しaccept0.46。結果後に許容条件を緩和・再送・手動acceptへ変更していない。

### 2020–2022 部分結果：同じ有効応答集合で比較

通常費用の合算等R。P/Lの金額合算ではない。指定RRは当初TP/SL距離比であり、実現payoffは費用後平均勝ちR/平均負けR。

|RR|方式|決済|勝率|PF_R|平均netR|実現payoff|
|---|---|---:|---:|---:|---:|---:|
|1|同待機covered対照|1,246|45.746%|0.779928|-0.089421|0.924968|
|1|Jev部分|302|46.358%|0.813185|-0.069435|0.940971|
|1.5|同待機covered対照|1,230|40.976%|0.802348|-0.089356|1.155764|
|1.5|Jev部分|300|42.333%|0.796741|-0.084689|1.085324|
|2|同待機covered対照|1,209|38.627%|0.795470|-0.097716|1.263895|
|2|Jev部分|297|40.404%|0.796994|-0.088484|1.175567|

通常JevのnetRはRR1/1.5/2で−20.969314/−25.406589/−26.279625。2倍費用はPF0.645597/0.649369/0.656664、平均R−0.147214/−0.162753/−0.166824。全体の黒字を示していない。合計損失の小ささには見送りと決済数減少が含まれ、優位性の証明にはしない。

### 期間・通貨別Jev部分成績

全行training2020–2022。DDは決済列のR DDで、円の最大損失ではない。

|通貨|RR|件数|通常勝率|通常PF|通常平均R|通常DD_R|2倍PF|2倍平均R|2倍DD_R|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|USDJPY|1|132|47.727%|0.916465|-0.029083|11.849769|0.716836|-0.111683|19.771732|
|USDJPY|1.5|130|44.615%|0.929416|-0.027128|12.447321|0.745315|-0.110459|19.338233|
|USDJPY|2|129|42.636%|0.915157|-0.034348|13.372841|0.741921|-0.118139|19.550508|
|EURUSD|1|70|42.857%|0.590902|-0.183241|16.798417|0.461858|-0.266967|21.539258|
|EURUSD|1.5|70|35.714%|0.475576|-0.275990|19.681540|0.381268|-0.359715|25.404598|
|EURUSD|2|68|32.353%|0.353120|-0.361156|25.420893|0.277875|-0.445464|31.016043|
|GBPUSD|1|100|47.000%|0.876819|-0.043035|7.574850|0.714708|-0.110289|12.841301|
|GBPUSD|1.5|100|44.000%|0.932955|-0.025607|6.014657|0.779809|-0.092861|9.286052|
|GBPUSD|2|100|43.000%|1.069021|0.027100|6.176927|0.907289|-0.040154|7.905501|

GBPUSD RR2だけの通常黒字を採用根拠にしない。PF1.2に届かず、費用2倍は赤字、他通貨と全体も満たさない。2023–2024、2025の新候補評価は実行していない。

USDJPYの部分円口座は通常RR1/1.5/2で最終983,401/983,917/979,719円、2倍で941,796/940,389/938,114円、いずれも90万円停止はまだ発生していない。ただしcandidate_coverage_complete=false、eligible_for_adoption_evaluation=falseであり、欠測候補を見送った部分口座。未観測候補を含む実運用継続性能と解釈しない。今回の新円口座の全曲線独立再生は未実施（送信前にRR1旧engine互換を検査済み）。

## 最終判定と引継ぎ

**未検証 / NEEDS_EVIDENCE。Pine反映・研究採用不可。** 評価されなかった母候補が多いため、固定戦略全体を完全検証した不採用とは呼ばない。観測部分では全RRの合算通常/2倍期待値が負、学習screenを進める根拠もない。後期送信、閾値調整、失敗応答修正を行わない。

未実装は実bid/ask履歴、実spread/slippage/commission/swap、API費用の売買P/L控除、ライブアラート欠配・市場時計差・実遅延の運用再現。全期間既閲覧、真holdoutなし。月block CI・元候補期待値CI・leave-one-symbol-outの最終採用検査は完全coverage未達のため未実施。実運用承認なし。

再現用の既存結果読み込み（API送信なし、同一仕様のCSV/JSONを再生成）とテスト:

```powershell
python scripts/research_ytt_jev.py --phase training
python -m pytest tests/test_ytt_jev.py tests/test_ytt_monthly5_fx.py tests/test_ytt_profit_feasibility.py -q
```

1行目は保存済み応答のみ読み、追加送信しない。既存training_results.jsonのinference欄はoffline情報になるため、原実API結果を保全してから実行すること。本担当は原結果を上書きしていない。引継ぎ先は研究責任者。初回25件・最終結果・無効応答・引当台帳・凍結識別子を保存したまま、改善未証明として報告する。
