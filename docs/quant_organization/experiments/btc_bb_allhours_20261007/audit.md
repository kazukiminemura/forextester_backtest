# BTC BB 全時間帯・品質監査

2026-10-07 JST。最終状態: **AUDITED_REJECTED_DESCRIPTIVE_CFD_PROXY**。固定した代理モデルの検証完了・全方式不採用の記録として引渡し可。実GMOの再現・採用承認ではない。以下の事前監査状態は履歴として保持する。監査担当は研究開発者/独立検証者とは別の既存Astra担当へ監査役割指示を渡した運用であり、カスタム設定自動読込の確認とはしない。所有は本書と必要な `agent_runs/btc_bb_allhours_20261007/audit_evidence*` のみ。

## 事前に確認した範囲

charter、board、protocol、hypothesis、data_inventory、主統合報告、独立担当の事前validationを結果前に読んだ。初回監査時protocolは `DRAFT_NOT_EXECUTABLE`、SHA256 `704b069d90f3b6afee4e25cfbcf29832b4bd2b4494ff6f09e7a306048443f49f`。これは初回レビュー対象の識別子であり、今後の最終凍結SHAではない。

1. ユーザーの確定条件はBTC・時間制限なし・CFD買い売り・GMOコイン暗号資産FX。旧現物買い限定の暫定案は結果前に撤回され、data_inventoryの主担当追記も一致している。保存BTCUSDのbid仮定/合成askはGMO BTCJPYの実feed・実spread・履歴的価格sideの証拠ではない。USDとJPY、CFD会計と現物購入会計を区別する。
2. 比較対象BB反転と新規2案、3期間×3費用の27ケースを固定し、全期間既閲覧・無選抜の記述研究とする。RR1は実fill中心の価格bracketであり、費用、gap、期末強制決済で実現RRは異なる。BB中央線とtrend prior ATR出口も異なり、純粋な入口フィルター因果効果とは呼ばない。
3. 完全5M1のM5、完全12M5のH1、最新完了H1/25連続時間、origin/確認と効率窓の連続性、予定次M1 openの存在を仕様で区別する。次M5全体の未来完全性は入場判定に使用しない。BB/ATRは観測complete M5順にgapを越すという設計も明示されている。
4. longはask側入場/bid側退出、shortはbid側入場/合成ask側退出。片道不利slip、手数料、SL優先の同一M1両到達、stop gapの実open、target gapの有利約定を上限TPで抑える約定仕様が一致する。保有は欠測をまたぎ、欠測内の高安/順序が復元できない制約を保持する。
5. 全7曜日source暦日で、完全/部分/欠測日、raw観測エントリー、完全日のゼロ件を分ける。日全体の事後完全性は統計分類専用。学習677/1096・検証294/731の完全日率は事前80%gate未達と既知であり、採算条件と品質不合格を分けて報告する。これだけを戦略赤字の証拠にしない。

## GMO費用代理の監査

2026-10-07、監査担当もGMO公式資料を照合した。暗号資産FXの注文/決済手数料0、JST6時をまたいだ保有への0.04%/日という現行説明は主文書と一致する。[GMO公式手数料説明](https://support.coin.z.com/hc/ja/articles/115005453247-%E6%9A%97%E5%8F%B7%E8%B3%87%E7%94%A3FX%E3%82%92%E6%B3%A8%E6%96%87%E3%81%97%E3%81%9F%E9%9A%9B%E3%81%AE%E6%89%8B%E6%95%B0%E6%96%99%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6%E6%95%99%E3%81%88%E3%81%A6%E3%81%8F%E3%81%A0%E3%81%95%E3%81%84)、[商品説明](https://coin.z.com/jp/corp/product/info/margin/)を参照。取引所レバレッジや現物の別料金と混同しない。全研究期間の歴史的料金検証ではない。

通常spread60.643 USD、slip0.01%、増加spread90.9645 USD、slip0.02%はGMO実測ではない。fundingは正elapsedを24時間単位で切上げ、当該観測M1までの累積最大合成ask高値×数量×rateで評価する。過去MTMに後日の全取引最大高値を用いない一方、exit M1高値の時系列順序は不明、同timestamp exitはelapsed0である。この代理が真のGMO課金の厳密上限であるとは認定しない。

1x notional capと0.25%想定stop riskは研究用仮定。実GMOの最小注文、証拠金維持率、ロスカット、円換算を再現しない。各費用条件でentry/target/risk/quantity/経路が変化し得るため、費用なしと通常の最終損益差を単一不変取引集合の費用効果と同一視しない。

## 結果前の指摘と未完了

- P2（仕様境界・要明示）: funding/gapで資産が非正になった場合、数量式の適用可否が初回protocolでは明記されていなかった。主/研究担当へ、非正または非有限flat equity・想定stop損失・数量を新規拒否し、負債を0へ丸めないこと、保有中は既定退出を守り架空の実brokerロスカットを追加しないことを結果前に依頼した。初回実装の `order_at_open` はequity<=0を既に拒否していたが、最終仕様・有限性と数量境界のテスト確認は未完了。
- P2（固定された資料限界）: 価格side・source時差・実費用・欠測の原因・tick経路・未閲覧期間が未確認。all-hoursでも日付境界に依存する頻度集計がJSTになるわけではない。coverage基準は結果後に緩和しない。
- 実装の初回静的読取は完了したが、更新後の境界tests、入力/コード/仕様SHA凍結、27ケース実走の終了、独立全経路照合、最終監査は未完了。初回読取時点では新規テストファイルも作成待ちだった。

現段階で重大な市場商品取り違えや、実GMO成績への読み替えは仕様文書に認められない。上記資産境界の明示とテスト、主承認後の凍結を条件として事前仕様を引き継ぐ。実走の正しさ、収益性、Pine採用、実運用は承認しない。

## 修正後の事前判定

状態を **SPEC_PREREVIEW_PASS_FREEZE_PENDING** へ更新する。損益結果を見る前に `position_sizing_and_currency.insolvency`、`order_at_open` のfinite/positive guard、負equityを保持して以後の新規を拒否する合成testを確認した。監査担当自身の `python -m pytest tests/test_btc_bb_allhours.py -q` は **16 passed・終了コード0**。資産境界の事前P2は解消した。

signal/約定/資金調達/集計の分離、causal cumulative high、同足SL優先、gap、CFD両方向会計、欠測日分類の初回静的読取と更新箇所を確認した。凍結inputsにhypothesis/data_inventoryも加えられ、浮動小数厳密比較をpandas rolling演算で固定する仕様が追加されている。主担当/独立担当の事前確認後、仕様とsource/tests/入力を結果前にハッシュ凍結して固定27ケースを実走することに監査上の差戻し事項はない。

これは実走許可の最終決裁や最終品質合格ではない。凍結SHA、実走終了コード・最終出力、独立全経路検証を次工程で照合する。採用falseと既知のcoverage不合格は変更しない。

## 最終実走の証拠照合

主担当から研究実走exit0/RESULT_JSONと独立reference session14585 exit0を受領した。監査担当は保存成果物を直接読み、独立結果 `complete=true` / `VERIFIED_DESCRIPTIVE_CFD_PROXY`、全方式screen=false、actual_GMO_replay=false、adopted=falseを確認した。研究results自体にはcomplete flagがないため、その存在を創作せず、最終27ケース出力と終了コードを完了証拠とする。

凍結時刻はprotocol `2026-10-07T13:17:47+00:00`、manifest `2026-10-07T13:17:59.520945+00:00`。監査側の再ハッシュでprotocol/hypothesis/data_inventory/runner/tests/再利用helper2/cache/data_evidenceの全9件が一致した。

|対象|SHA256|
|---|---|
|凍結protocol|a3bf1145242bdaf2f5a0c9242badf8be3c0c3c622a6bc9931a11814951f1a088|
|専用runner|96b134ef20a6c1adee64203cc0a98eb835928ad7141ae0b200d5f508552bba5d|
|専用tests|69a1e4f52ac6e9c4fc58ab9fe8b2f1de9489d69948e386c4cc4ca00d2077a945|
|研究results.json|ec113c1c5278f33152bb612668dce7f9264cdad9814061ecdcf5627866d3392d|
|独立reference|9c9d0cafe785bfd4738e939e3a75609b8fb366afda1ffa6daeab38e5bbde7644|
|独立verification_result.json|868f1b3b96eabdb8007df28daad99777e8eecaf11217dc47bc4ed01ccffcaf8b|
|監査audit_evidence.py|3850abb8ef569f2d15fc40b91341217461a306d4ede76630b041f966656297e5|

独立担当の別経路再構成は、4,309,797入力M1、841,669 M5（warmup含む）、18,236 episodes、36,434 candidates、9 prefix、27ケース、64,138取引観測、88,359判断、30,149,757 MTM行、22,239日次行、63年別セルと全gateを一致確認した。費用別等の重複を含む観測数であり独立標本数ではない。厳密浮動小数仕様として同じpandas rolling primitiveを使用するが、production trading engineを呼ばずhourly構成/約定/資金調達/会計を別実装で照合した範囲である。

監査担当自身は `python agent_runs/btc_bb_allhours_20261007/audit_evidence.py` を実行し、**AUDIT_ACCOUNTING_MATCH・終了コード0**。全27ケース/64,138取引のentry quote、exit slip、fee、保有区間高値とelapsedからのfunding、方向別gross/net、価格RR1、数量cap、資産繰越、PF/勝率、保存全MTMからの最大DDを別式で照合した。これは自分でも信号から全売買経路を再実行したとの主張ではない。研究の初回文書読取では作成途中のresults.mdが未存在でコマンドexit1となったが、研究実走失敗とは無関係であり、results.jsonを一次成果物として読取した。

## 最終所見と未確認事項

1. P2（実約定非再現）: 固定USD spread/合成askはGMO BTCJPYではない。`stop_gap`には価格が後の足で飛んだ場合だけでなく、入口からspreadが小さいbracketを越えて即時SLとなる場合もある。全費用/期間を含む12,720取引観測でentry timestampとexit timestampが同じstop_gapを確認。例として学習通常BBの最初のshortはentry7353.16461、stop7366.51622に対して同時ask open7414.543で決済し、想定stop損失約19.16USDに対して約84.48USDの損失となる。0.25%リスク超過は将来gap/fundingだけの問題ではない。仕様通りの再現であり、結果後に都合よくentry除外を追加しない。
2. P2（数量と頻度）: fractional BTCに最低数量/最小notionalがない。trend学習通常は最終資産約0.00001167USDまで減少しても微小quantityで取引が続く。件数や1日頻度を実GMOの発注可能数と解釈しない。実ロスカットを再現したとも主張しない。
3. P2（標本・費用・時計）: 全期間既閲覧、source暦日、欠測/部分日、未知の全履歴sideとGMO実spread、代理fundingのintraminute曖昧さを保持する。品質gate不合格と費用条件下の経済不合格は別根拠である。実データ供給元/取引可能性/JPY換算、broker数量/証拠金/ロスカット、未使用期間、Pine実機は未確認。

全3方式は通常/増加費用で全期間赤字、screen不通過。BB通常のPFは学習/検証/最終記述で0.185/0.150/0.266。結果後の閾値変更・有利な費用/期間選抜・feeの二重減算・未使用holdoutへの読み替えは確認範囲で認められない。未解決の重大実装不一致はなく、モデルの不採用記録として引渡せる。**実GMO成績の認定・研究収益性合格・Pine採用・実運用承認はしない**。

最終 `validation.md` の不採用/VERIFIED_DESCRIPTIVE_CFD_PROXY、`results.md` の全通常結果表、主統合報告も読取照合した。研究報告の「独立検証待ち」旧進捗文言とrun_completionのPENDINGは担当へ更新依頼した（研究実行後に独立工程が完了したため）。一次証拠である独立JSONと検証報告は完了済み。監査実行の要約は `agent_runs/btc_bb_allhours_20261007/audit_evidence.json` に保存した。次担当は主研究責任者、board/統合報告の最終状態反映と条件付き不採用結果の引渡し。

監査による戦略・成績・原履歴の変更、有料API、実注文、Git公開: なし。
