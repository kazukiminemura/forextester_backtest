# 独立検証と頑健性診断: 田向式派生6候補

実験ID: `tamukai_stocks_deep_20260926`。検証日: 2026-09-26。

判定: **不採用／VERIFIED_REJECTED_VALIDATION_DATA_LIMITED**。
訓練でrisk_bandだけ適格となったが、2020–2022検証は82件・PF0.9963・−499.50円、費用2倍−17,102.47円。100件/純PF1.1/黒字/stress黒字の基準に届かず、最終選抜none。
固定参考no_dowの後期成績は別枠で記述し、候補へ昇格しない。実運用承認なし。

## 凍結入力・実走証拠

- 4条件A/B/C/Dと指定2組合せからなる6候補、training→適格だけvalidation→選抜保存→選抜だけfinal、参考no_dow等の追跡は `protocol.json` / `hypothesis.md` に固定。
- Dのsignalclose基準2–4%は、既閲覧学習no_dowの実約定幅部分集合を見て作った仮説。前の部分集合成績を新戦略の成績と扱わない。未来の翌始値ではなく当日引けの幅で判定。
- protocol SHA256: `3d627766105113444ebaaebd4fd019e43403ebe2138a58b1130acf3d00bec1c0`。
- runner SHA256: `e6cdaeb44130e110b22e22fe9ac5c746d379d2958a283a218b6317f54d63e12b`。
- data manifest SHA256: `fdaf2c5e0d283d853cc295faf13cd031fbc2c03de3aa43e4301d32d83e12866b`。旧保存CSVと再利用daily/jev/indicatorsのhash一致。詳細は[data_inventory.md](data_inventory.md)。
- 頑健性plan SHA256: `491f264cddaeba586bc9d6b2f75aed65bb0d91da4af0f628cfc17a5d2dd6987a`。
- replay SHA256: `851bdc19d730ea63d7fec532fc1e3261f5f5204346e8490cf06c352e50f6441b`、robustness SHA256: `8707e248a42ad017df7702cf10379e66958eb4615ca0e64cc1846b802ad85113`。
- `results/run_start_manifest.json` の計算前hash、training/validation/selection/selected_final/finalのhash連鎖と内容整合を確認。最終JSON保存・研究runner終了0を開発担当から確認し、独立プロセスも終了0。独立結果JSON2件の最終存在を確認した。
- 頑健性対象は訓練/validation成績を見た後、CI結果を見る前に「計算済validation不合格も含む」と計画を明確化。更新計画を読んでから初実走し、対象/seed/回数を結果後変更していない。

## 独立再生

`independent/verify_replay.py` はOHLCからSMA/strict pivot/Wilder ATR/6フィルターを別計算し、旧独立cash再生を再利用する。
A/BのATRは初期14本平均から独立漸化式、Dは終値と直前3本安値を使用する。翌日価格はシグナル条件へ入れない。

- 380ケース、4,096取引観測、366,340個別MTM行、114集約曲線、450年別指標、1,965,274scalar照合一致。
- 計算済候補・期間終端ごとの161,600足・4,355信号観測、5,612 prefix一致。期間・候補間で重複する観測数であり、独立した標本数を示さない。
- 旧比較no_dow/baseline/buyhold計360 CSVがbyte一致。
- 1銘柄1保有、翌営業日始値、SL/TP対称1R、gap始値、同足両hit SL優先、entry日退出、保有中信号無視、費用込み全額数量、期末清算を全取引照合。
- 各10万円sleeve×10、JPY純損益/純PF/期待値を照合。初期資金をピークに含む引けMTM DD、年別は前年末MTMを起点、決済年別実現PFとMTM損益の違いを確認。
- 6訓練gate、risk_band検証gate、最大PF/少条件数/ID順選抜、selected_final空、reference固定3手法を再計算して一致。
- 4境界unittestも独立実行で成功、exit0。独立checker自体の最終exit0とJSON出力を確認。
- 未適格5候補の2020年以降、risk_bandの2023年以降を追加計算していない。参考枠はno_dow/baseline/buyholdのみ。

## 期間別結果

mainは片道0.1%、stressは片道0.2%。全額10sleeve初期100万円。期待値は決済純益の円平均、勝率ではない。
training=2017–2019、validation=2020–2022、final_confirmation=2023–2025、continuous=2017–2025。

|段階/条件|取引|純PF|純損益 円|期待値 円/件|DD%|費用2倍純益 円|
|---|---:|---:|---:|---:|---:|---:|
|training/trend_strength|99|0.8755|-29,866.45|-301.68|6.60|-49,192.76|
|training/shallow_pullback|136|0.9726|-8,282.93|-60.90|8.50|-34,500.42|
|training/strong_rejection|123|0.9852|-4,532.79|-36.85|9.41|-28,409.50|
|training/risk_band|97|1.2755|42,176.44|434.81|2.99|21,982.55|
|training/trend_shallow|88|1.0105|2,065.83|23.48|5.85|-15,588.62|
|training/trend_risk|52|0.9286|-6,650.85|-127.90|2.43|-16,901.08|
|training/no_dow|166|1.0740|29,256.10|176.24|11.28|-4,090.01|
|validation/risk_band|82|0.9963|-499.50|-6.09|3.55|-17,102.47|
|reference_validation/no_dow|164|1.1474|69,728.91|425.18|11.02|36,738.44|
|reference_final_confirmation/no_dow|172|1.4183|199,766.67|1,161.43|5.86|158,303.33|
|reference_continuous/no_dow|499|1.2971|422,727.02|847.15|14.20|292,315.28|


新6候補はtraining50件/PF1.1/純益正/DD20%以下/stress純益正を要求。risk_band以外はPF未達、trend_shallowは通常微益だがstress赤字。
risk_bandはtraining全条件を満たしたもののvalidationの件数/PF/利益/stress利益で不合格。最終候補なしを保存し、候補の最終期間は未計算。
no_dowは前実験学習で基準未達の固定比較対象。後期・連続に利益があっても今回6候補の採用成功を意味しない。

## risk_band銘柄別・通常コスト

|risk_band段階|銘柄|取引|PF|純益 円|期待値 円/件|DD%|
|---|---|---:|---:|---:|---:|---:|
|training|7203.T|11|4.2261|19,886.49|1,807.86|4.12|
|training|6758.T|12|1.5641|11,200.43|933.37|14.45|
|training|8306.T|8|0.6617|-4,086.85|-510.86|9.24|
|training|9432.T|14|1.7019|11,235.79|802.56|7.27|
|training|9984.T|5|5.5773|14,417.79|2,883.56|6.73|
|training|6501.T|8|0.6178|-8,457.66|-1,057.21|16.79|
|training|6861.T|11|1.0352|797.42|72.49|8.90|
|training|8035.T|9|0.5422|-10,498.45|-1,166.49|14.90|
|training|8058.T|13|1.5031|8,875.02|682.69|11.32|
|training|4502.T|6|0.8859|-1,193.53|-198.92|10.15|
|validation|7203.T|11|0.6024|-8,914.76|-810.43|13.09|
|validation|6758.T|7|1.2138|2,624.71|374.96|8.67|
|validation|8306.T|11|0.7220|-5,784.65|-525.88|9.85|
|validation|9432.T|18|2.7035|27,362.02|1,520.11|13.06|
|validation|9984.T|1|0.0000|-1,491.10|-1,491.10|1.49|
|validation|6501.T|3|2.2655|3,461.04|1,153.68|4.39|
|validation|6861.T|5|0.1918|-6,845.10|-1,369.02|6.85|
|validation|8035.T|5|0.7727|-2,807.55|-561.51|6.40|
|validation|8058.T|8|1.1019|1,519.25|189.91|9.24|
|validation|4502.T|13|0.5840|-9,623.35|-740.26|17.06|


全候補/参考・全費用・全期間の銘柄別PF/純益/期待値/DD、年別値は `independent/replay_verification.json` の `metrics` に保存し照合済み。公式CSVは `results/<stage>/<cost>/<candidate>/`。
小さい母数の高勝率・PF infinity等を採用根拠にしていない。

## ブロックブートストラップ

11群（6訓練候補、no_dowの4期間、risk_band検証）を対象に、3連続月/6連続月ブロックを各2,000回、seed20260926で再標本。各抽出月indexを全10銘柄・同月列の全候補へ共通適用する。
月中およびブロック内の同時変動を保持するが、長期依存は保証しない。月境界の状態を再売買しない既存経路に条件付けた統計である。

月次リターンは月末合算MTM/前月末合算MTM−1（初月は初期100万円）。PFは決済月に属する費用後正/負の金額の合計比。共通月vectorを抽出するため銘柄相関を壊さない。
非循環moving blocksで開始位置0..n−blockから一様抽出しnか月になるまで連結、余りは切る。percentileは昇順配列の位置(n−1)pを線形補間、損失0ならPF∞、損益両0なら未定義として有効数を併記。本実走のPF未定義/∞標本は0。

|対象|月次平均% 3か月block CI|PF 3か月block CI|月次平均% 6か月block CI|PF 6か月block CI|
|---|---:|---:|---:|---:|
|reference_continuous/no_dow|0.026 ～ 0.680|1.010 ～ 1.696|0.003 ～ 0.672|0.994 ～ 1.653|
|reference_final_confirmation/no_dow|0.047 ～ 1.086|1.011 ～ 2.127|0.111 ～ 0.995|1.050 ～ 1.995|
|reference_validation/no_dow|-0.463 ～ 0.985|0.691 ～ 2.021|-0.333 ～ 1.032|0.781 ～ 2.010|
|training/no_dow|-0.392 ～ 0.544|0.671 ～ 1.660|-0.414 ～ 0.510|0.670 ～ 1.657|
|training/risk_band|-0.093 ～ 0.363|0.820 ～ 2.204|-0.074 ～ 0.372|0.836 ～ 2.324|
|training/shallow_pullback|-0.341 ～ 0.279|0.645 ～ 1.481|-0.315 ～ 0.306|0.682 ～ 1.523|
|training/strong_rejection|-0.372 ～ 0.313|0.618 ～ 1.552|-0.363 ～ 0.343|0.665 ～ 1.624|
|training/trend_risk|-0.142 ～ 0.173|0.518 ～ 1.971|-0.144 ～ 0.167|0.552 ～ 2.031|
|training/trend_shallow|-0.236 ～ 0.233|0.627 ～ 1.612|-0.252 ～ 0.272|0.644 ～ 1.726|
|training/trend_strength|-0.311 ～ 0.201|0.565 ～ 1.448|-0.288 ～ 0.217|0.638 ～ 1.482|
|validation/risk_band|-0.238 ～ 0.299|0.518 ～ 2.183|-0.181 ～ 0.300|0.602 ～ 2.318|


全6訓練候補の平均月次return CIは0を、PF CIは1を含む。risk_bandの学習利益だけでは確かな優位性を示さない。
参考no_dow連続は3か月blockのPF下限1.010に対し6か月blockでは0.994で1をまたぐ。単一の有利なブロック長を選ばない。
95%は指定percentile区間のラベルであり、将来黒字確率や真の未使用検証の代わりではない。多重比較調整なし、過去候補/条件探索あり、相場分布変化も未保証。有意なedge発見と主張しない。[探索とブートストラップの原研究](https://www.fmg.ac.uk/sites/default/files/2020-11/dp303.pdf)。

## 銘柄集中・除外・費用分岐

Top1/Top3は黒字銘柄の正の純益合計を分母にした寄与率で、全体純益を分母にしない。赤字株の損失はJSONへ全件併記。
1株除外は10通りの9sleeve/90万円、再配分・再学習なし。最良集合を銘柄採用に使わない。
1bps=0.01%。既定片道0.1%=10bps、stress0.2%=20bps。

|対象|最大寄与株|Top1/Top3%|HHI|1株除外黒字組数|1株除外最悪純益 円|損益分岐 片道bps|
|---|---|---:|---:|---:|---:|---:|
|reference_continuous/no_dow|6501.T|51.23/79.55|0.3171|10/10|158,923.22|46.743|
|reference_final_confirmation/no_dow|6501.T|34.84/77.25|0.2284|10/10|116,377.71|61.880|
|reference_validation/no_dow|6501.T|53.54/77.12|0.3334|9/10|-1,968.47|31.542|
|training/no_dow|8058.T|35.56/84.33|0.2568|10/10|6,479.07|18.755|
|training/risk_band|7203.T|29.94/68.57|0.2119|10/10|22,289.96|31.133|
|training/shallow_pullback|8058.T|21.06/58.41|0.1743|4/10|-18,479.56|6.898|
|training/strong_rejection|8306.T|37.40/75.71|0.2347|3/10|-21,611.42|8.130|
|training/trend_risk|6758.T|41.18/83.95|0.2911|2/10|-19,144.32|3.574|
|training/trend_shallow|6758.T|31.19/80.25|0.2404|5/10|-9,032.80|11.160|
|training/trend_strength|8035.T|36.06/80.72|0.2619|0/10|-37,424.62|—|
|validation/risk_band|9432.T|78.25/95.66|0.6296|6/10|-27,861.52|9.703|


risk_band検証の最大黒字寄与78.25%は利益の集中を示す。10株合算が赤字でも、負け株除外で黒字になる組があるだけで適格にしない。
no_dow連続は全1株除外10組で黒字だが、最大1株が黒字株利益合計の51.23%を占める。この診断もreferenceを採用へ昇格しない。
損益分岐が—のtrend_strength訓練は費用0でも赤字で、非負費用の解がない。

費用分岐は `100000 × product(exit/entry) × ((1-c)/(1+c))^trade_count` を各株で計算して合算。
費用がシグナル・約定価格を変えないモデルに限定した正確な式で、通常/2倍費用計220sleeveの保存最終資金へ一致を確認。
c=0〜片道1%の単調低下を検査後60回二分探索、根では残差1e−6円未満。0でも赤字/0だけ収支均衡/1%超/取引なしを区別する。
3/6月の計4,000抽出配列、percentile端点、合成取引の費用根を事前self-checkしexit0。実データ11群・110除外集合・22分布×2,000抽出を完了、exit0。

## 制約・未実装コスト

全2017–2025は既閲覧。risk_bandは既閲覧学習結果からの仮説、今回検証は新候補の段階管理であり真のholdoutではない。
SMA/ATR/pivot/RRのパラメータ近傍探索は未実施。今回6条件差・3/6月block・費用分岐/費用2倍・銘柄除外が診断範囲。
Yahoo後方調整、Sonyスピンオフ復元不可、2株包絡合成修復、現在存続大型株の生存/選択バイアスを継承。9/7株品質診断もclean認証ではない。
普通配当・税・金利・現物配分なし。包括費用率は実測手数料/滑りではなく、滑りで価格経路が変わること、寄付競合、板、値幅制限で執行不能、最小呼値、100株単元は未実装。端株調整数量による研究値で実口座収益ではない。
今回新規Jev/API呼出しなし。前実験のHTTPErrorを自動再送していない。

## 再現と引継ぎ

workspace rootから。公式runner再現は既存結果を保つ別outputへ。独立2scriptは正式resultsを読み、independent出力だけを更新する。

```powershell
python -m unittest discover -s tests -p test_tamukai_stocks_deep.py -v
python scripts/research_tamukai_stocks_deep.py --output agent_runs/tamukai_stocks_deep_20260926/reproduction
python agent_runs/tamukai_stocks_deep_20260926/independent/verify_replay.py
python agent_runs/tamukai_stocks_deep_20260926/independent/robustness.py
```

- 担当/次担当: 独立検証 → 主担当/品質監査。
- 所有変更: 本validation.md、independent/{verify_replay.py,replay_verification.json,robustness.py,robustness.json}と自身のPython cacheのみ。戦略/基準/データ変更なし。
- 判定: 6候補不採用、学習改善は検証に続かなかった。固定referenceに利益はあるが本実験採用対象でない。
- 引渡し可能: 限定データ上の記述研究と頑健性診断。最終候補研究合格/実運用承認/Pine移植の根拠には渡さない。
