# 品質監査: 日足押し目の失敗診断と6候補

実験ID: `tamukai_stocks_deep_20260926`。2026-09-26。
編集所有はdata_inventory.md/本書のみ。戦略・成績・API設定を変更していない。
確定判定: **AUDITED_REJECTED_VALIDATION_DATA_LIMITED**。新6案の不採用研究と、固定referenceの記述追跡・頑健性診断として限定引渡し可。候補の採否とreference成績は別扱いで、採用・実運用承認なし。

## 所見

1. **高・採用基準不通過。** 学習を通ったrisk_bandは97件/PF1.27549/純益+42,176.44円だが、検証2020–2022は82件/PF0.99629/−499.50円、stress−17,102.47円。件数100・PF1.1・純益正・stress純益正を満たさず、選抜none/NO_VALIDATION_ELIGIBLE。最終確認候補は空。学習の見栄えを採用根拠にしない。
2. **高・referenceの黒字は採用確認ではない。** no_dowは今回の選抜不可の固定比較対象。連続9年499件/PF1.29715/+422,727.02円は記述追跡の成果であり、学習gate不通過を覆して昇格させない。`final.json` の `FIXED_DESCRIPTIVE_NOT_ADOPTION_CANDIDATES` と選抜経路の空結果を保持する。
3. **高・探索と真の未使用性。** 全期間既閲覧。Dの幅2–4%は旧学習取引の事後部分集合を見て設計したtrain内探索。旧診断は実entry幅、新条件は信号close幅であり、53取引の部分集合PFを新戦略の成績として再利用しない。今回6案、累積は初回1+前回3+今回6の10条件（重複reference除く）。多重比較補正や新しい未使用期間はない。
4. **高・データ/運用モデル制約継承。** Yahoo後方調整、Sony分離調整未解明、2件合成高安、現存大型株の選択/生存バイアス、端株資金枠、配当/税/金利/単元/呼値/執行不能未再現。参考価格損益という限定を外せない。詳細はdata_inventory.md。
5. **中・失敗診断は因果証明ではない。** 幅/gap/exit別の集計は勝敗両方を含む記述比較。groupの差は相場/銘柄/時期/保有構造などを統制した因果効果ではない。gross=既存純益+費用は同じ実数量での帰属計算で、無費用で資金を再運用した反実仮想成績ではない。gapは信号終値→翌始値の差で、実スリッページではない。
6. **中・頑健性診断の意味。** 3/6か月moving-block bootstrapは保存済口座経路の条件付き再標本、月PFは決済月、月リターンはMTM。将来勝率/利益確率、選抜補正した有意性、売買再シミュレーションではない。銘柄除外・費用分岐も診断として使い、良い部分だけを選抜に戻さない。

## 工程・実装対応

- 最大6候補はno_dowにA強度/B浅さ/C引け位置/D信号時リスク幅を単独または指定2組だけ追加。全組合せ探索なし。閾値/候補/停止条件は研究実走開始hashと現在protocolで一致。
- A=(SMA21−SMA21[5])/WilderATR14>=0.25、B=前3足各(low−SMA21)/ATR14>=−1、C=引け位置>=0.75、D=信号close基準2–4%（境界含む）。Aは26本目以降、ATR正値、Cレンジ0不成立。
- `evaluate` は評価期間末でバーを切ってから信号計算。既存SMA・WilderATRは現在以前のみ。上位足なし。約定は旧simulateの翌足始値/全決済RR1/窓/両hit SL優先/entry日決済/期末清算を継承。
- training JSON保存→適格risk_bandだけvalidation→validation JSON保存→selection保存→selected_final。referenceの後期/9年計算は選抜保存後。比較no_dow/baseline/buyholdを選択候補に入れていない。
- trainingには主候補6+reference3、validationにはrisk_bandだけ、selected_final.results={}、reference各期間には固定3手法だけ。最終観察gate falseと停止理由を確認。
- 費用は各片道0.1%/0.2%、各銘柄10万円独立sleeve。品質除外9/7株は既存sleeveの合算で再配分なし。DDは引けMTM、年利益はMTM差と決済年別実現利益を区別する。
- 今回はJev呼出しなし。前研究のAPI失敗を成功に読み替えず、Pine対応/TradingView実機/実運用承認は今回も対象外。

## 監査担当の実行証拠

- 保存snapshot21 SHAと全23,140行OHLC/日付を再検査してexit0。前2研究と同一、再DL/補正追加なし。
- 原因診断元の旧学習40明細CSV・428取引について、費用/gross/net/R/信号close→entry gap/実entry幅/保有営業日を元tradeとOHLCから別計算し一致。幅/exit/gapの全群件数/損益合計も一致、exit0。診断ソースSHAは `0539cccf5b69f29587789387d8cb9b2ef9a4826ed31b9888062a907bd00363c5`。
- `python -m pytest -q tests/test_tamukai_stocks_deep.py tests/test_stock_pullback_diagnostics.py`：5 passed/exit0。要因条件と組合せ、D境界・信号close基準、stress gate/tie-break/prefix、診断営業日/会計を確認。
- run_startから現行ソース/仕様/tests/data計17hash、全段階evidence、training→validation→selection参照hashを照合して一致、exit0。selection時刻09:10:55 UTCは研究開始09:10:53と最終完了09:10:57の間。
- 研究runner SHA `e6cdaeb44130e110b22e22fe9ac5c746d379d2958a283a218b6317f54d63e12b`、protocol `3d627766105113444ebaaebd4fd019e43403ebe2138a58b1130acf3d00bec1c0`。
- training `51310b98479f27fee190178f569138c18dd26bf8d7e94fa5c7321bb4010addf0`、validation `42584023cde587a2674ab95c686c5b1b532a2dd1535c564ead2afc2e7419dc08`、selection `f11fd1e925a6583a2a63a2475e217b83bd7b1d9608de8b34edd68c00b005995a`、final `aadf837dce048f2e32ede3f03bc6a5391f083bd5613ac6b571e721cc6ec70324`。
- 独立担当の `independent/verify_replay.py` と `robustness.py` を全文読取後、監査でも再実行。出力JSON書込みだけをmockし、生成JSONと保存JSONの完全一致を確認（exit0）。380ケース/4,096取引観測/366,340個別MTM/114集約/450年別/1,965,274 scalar/5,612 prefix/4,355信号観測/旧360CSV byte一致。これら件数は条件・費用・期間の重複を含む。
- 頑健性は11群について両block各2,000回、保存bootstrap/費用損益分岐/利益集中/leave-one-out値を全再現。保存両費用と分岐式の残高照合、対象/方法/plan hash整合も同実行で確認。新しい売買や選抜を計算していない。
- 最終validation.md・主報告 `docs/tamukai_stocks_deep.md`・boardの当該欄を照合。6案不採用、reference非昇格、累積10条件、データ制約、探索起源、費用率単位、期間/銘柄/品質除外/年別の引用数値は整合。主報告の「未計算の強度/引け案と親の後期優劣」に読めた表現を指摘し、「未計算候補との後期優劣は比較していない」への修正を確認した。ダッシュボード実画面は主担当確認の範囲で、監査担当は独立UI確認していない。

## 頑健性の解釈確認

no_dow連続のPF再標本95%区間は3か月blockで[1.01027,1.69601]、6か月で[0.99352,1.65278]。3か月だけを取り上げて統計的優位性が確定したとはしない。6か月の月次平均リターン区間が正であることと、PF区間が1を跨ぐことも異なる統計量なので矛盾ではない。

no_dow連続の最大黒字銘柄は黒字銘柄利益合計の51.23%を占める。1銘柄ずつ除いた10組はすべて純益正だが、現存10銘柄という母集団の偏りを取り除く検査ではない。同じ約定経路での費用損益分岐は片道46.74265bps（約0.46743%）で、現実の執行コストや許容手数料を保証する数値ではない。

risk_bandのvalidation費用分岐は片道9.70267bps（約0.09703%）で通常仮定10bpsを下回り、通常純益負と整合。bootstrap PF区間が広いことを、既に不通過の数値gateを緩める根拠にしない。

## 未確認と引渡し

独立計算/頑健性再現・独立validation文書・主報告の照合は完了。頑健性対象の「訓練通過後のvalidation/risk_bandを含むか」という文言差は修正確認済み。訓練/validation成績閲覧後・頑健性結果閲覧前の補足と明示し、算出済み不合格validationも対象に含める。ブロック長/回数/seed/診断式は不変。後期を未計算の候補を診断用に新規計算していない。

取引所原票全件、真の未使用相場、実単元/板/約定、将来収益、Pine/TradingView実機は未確認。限定された追加研究は、不採用結果と参考比較の発見を含めて完了。利益を生む戦略の確立・研究合格・実運用承認を意味しない。次担当は研究責任者とし、元データ/取引コード/成績を変更せず、本監査付きで結果を引き渡してよい。
