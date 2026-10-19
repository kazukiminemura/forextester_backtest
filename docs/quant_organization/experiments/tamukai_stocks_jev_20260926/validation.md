# 独立検証: 田向式派生3候補・Jev評価

実験ID: `tamukai_stocks_jev_20260926`。検証日: 2026-09-26。

判定: **不採用（3候補とも訓練ゲート未達）／VERIFIED_REJECTED_TRAINING_ONLY_DATA_LIMITED**。
AI評価工程は別状態 **JEV_FAILED_NO_SELECTION**。JevはHTTPErrorで応答を返しておらず、AIがnoneやrejectを選択したとは報告しない。後期検証・Pine移植・実運用承認なし。

## 凍結入力と実行完了証拠

- 仕様 `hypothesis.md` / `protocol.json`。固定3候補+選抜不可のbaselineとbuyhold。訓練2017–2019、warmup2016-07-12以降。
- protocol SHA256: `d88d9150078bddfbf58705e42f1a480517176eca7863ac200cac5feb7fec4bf4`。
- runner SHA256: `3c1267a497d5ddf40848720da18b2c7ada56cdf54e7c09e57782f1b40c114b50`。
- training.json SHA256: `0da06299f6053cc8441c1bdc1e0b30f6cca48d1c58fdc0d61585c9c008cb3533`。
- 再利用baseline SHA256: `ea45264616f7f8f83f835571cd1fbd9f73e20560456b75f460e0ed2f3387c6b7`。前実験と不変。
- data manifest SHA256: `fdaf2c5e0d283d853cc295faf13cd031fbc2c03de3aa43e4301d32d83e12866b`。保存データ `data/stocks/yahoo/jp_largecap10_20260926/` は旧キャッシュと同一、10CSVのSHA256を独立再照合済み。詳細は[data_inventory.md](data_inventory.md)。
- 開始 `2026-09-26T06:33:26.110827+00:00`、終了 `2026-09-26T06:33:26.940645+00:00`。開始manifestは計算前のsource/protocol/test/data hashを保存、現在ファイルとtraining.jsonに一致。
- 開発実走 `RESULT_JSON=agent_runs/tamukai_stocks_jev_20260926/results/training.json` とプロセス終了0を確認。独立再計算も終了0、最終 `independent/training_verification.json` あり。途中ログのみを完了根拠にしていない。

## 独立確認

旧検証の独立replay/metricsを再利用し、候補シグナルのみ別実装を追加した。Ponytailに沿い、共通会計の再設計や候補追加は行わない。検証コードは売買runnerのsimulate/metricsを呼ばず、保存OHLCからシグナル・約定・数量・費用・全資金曲線を再生する。

- 訓練に切った日足のみで4条件の全921信号観測を独立一致。strict pivotは極値一意性、SMAはmath.fsumで算出。1,398 prefixで未来データ切断後も一致。921は候補間重複を含む。
- 100ケース（5手法×2費用×10株）、876取引観測、73,300個別MTM行、30集約曲線、90年別指標、394,178scalarが一致。
- 前実験trainingのbaseline/buyhold計80明細・MTM CSVはbyte一致。データ・会計変更による見かけの改善なし。
- 全候補の翌営業日始値、直前3日安値固定SL、建値から1R TP、始値<=SL見送り、entry日からの決済、gap始値優先、同日両hit SL優先、保有中信号無視、決済日引けからの翌日再注文、期末清算を照合。
- 各100,000円の独立sleeve、費用込み全額数量、両端代金比例費用、複利、初期残高をピークに含む引けMTM DDが一致。全JPYなので円損益の合算が可能。勝率は純益>0、建値を金銭利益にしていない。
- 年別MTM損益は前年末残高との差、PF/勝率は当年決済の純損益。年別DDは前年末を初期ピークとして照合。
- 数値ゲートを独立再計算しeligible=[]。baselineは選抜対象外。学習後のパラメータ変更なし。
- `test_tamukai_stocks_jev.py` の4testsを独立再実行して全成功（exit0）。不適格選択/hash不一致/選抜記録なしの後期開始を拒否するテストを含む。
- `results/evaluation/`、`results/evaluation.json`、`selection.json` は存在しない。2020年以降の新候補シグナル・損益は計算していない。

## 事前判定と結果

訓練の全10株通常費用について、50件以上・PF>=1.1・純益>0・DD<=20%をすべて要求する。
3候補とも件数/DDは通過するがPF未達。no_dowのみ通常費用の純益は正、費用2倍では負。
学習の最良候補だからという理由で閾値を緩めず、後期へ進めない。

main=片道0.1%、stress=片道0.2%。期待値は費用後円損益/決済件数であり将来収益予測ではない。

|候補|費用|取引|勝率%|純PF|純損益 円|期待値 円/件|DD%|
|---|---|---:|---:|---:|---:|---:|---:|
|baseline|main|54|48.15|0.7610|-30,014.82|-555.83|6.14|
|baseline|stress|54|48.15|0.6903|-40,308.32|-746.45|6.59|
|no_dow|main|166|54.22|1.0740|29,256.10|176.24|11.28|
|no_dow|stress|166|54.22|0.9899|-4,090.01|-24.64|12.66|
|prior_day_breakout|main|79|45.57|0.7538|-39,627.28|-501.61|6.56|
|prior_day_breakout|stress|79|45.57|0.6747|-54,607.19|-691.23|7.70|
|sma63_trend|main|129|51.94|0.9205|-24,236.13|-187.88|12.75|
|sma63_trend|stress|129|51.94|0.8425|-49,264.39|-381.89|13.75|


買持ち対照は通常費用純益+396,350.91円、DD30.41%、保有割合100%。baselineは7.38%、no_dowは30.64%、prior_day_breakoutは9.11%、sma63_trendは21.87%の銘柄日で保有。リスク/市場滞在時間が異なるため単純な同等リスク比較ではない。

## 訓練年別・通常費用

|候補|年|決済件数|純PF|MTM損益 円|実現損益 円|年内DD%|
|---|---|---:|---:|---:|---:|---:|
|no_dow|2017|56|1.6514|60,926.71|59,909.55|3.08|
|no_dow|2018|49|0.6025|-70,753.08|-69,735.92|9.54|
|no_dow|2019|61|1.3051|39,082.47|39,082.47|4.19|
|prior_day_breakout|2017|26|0.8742|-5,289.59|-5,754.77|2.42|
|prior_day_breakout|2018|23|0.5738|-27,112.79|-26,647.61|4.32|
|prior_day_breakout|2019|30|0.8628|-7,224.90|-7,224.90|2.35|
|sma63_trend|2017|46|1.4039|31,361.31|32,403.77|2.74|
|sma63_trend|2018|31|0.6399|-38,284.15|-39,326.61|7.03|
|sma63_trend|2019|52|0.8498|-17,313.29|-17,313.29|6.84|


2017–2019以外の期間成績は未検証。全2017–2025は前実験で既閲覧であり、今回候補の後期を未計算にしたことと真の未使用holdoutであることは異なる。

## 訓練銘柄別・通常費用

|候補|銘柄|取引|純PF|純損益 円|期待値 円/件|DD%|
|---|---|---:|---:|---:|---:|---:|
|no_dow|7203.T|15|1.1753|3,940.73|262.72|9.84|
|no_dow|6758.T|20|1.1036|5,568.02|278.40|20.81|
|no_dow|8306.T|15|1.0186|529.26|35.28|16.78|
|no_dow|9432.T|17|0.9298|-2,066.72|-121.57|15.57|
|no_dow|9984.T|19|0.7116|-22,305.69|-1,173.98|40.82|
|no_dow|6501.T|12|1.5340|15,539.47|1,294.96|21.24|
|no_dow|6861.T|19|1.3630|15,690.13|825.80|22.34|
|no_dow|8035.T|19|0.9974|-149.25|-7.86|35.56|
|no_dow|8058.T|14|2.2347|22,777.03|1,626.93|9.84|
|no_dow|4502.T|16|0.7046|-10,266.89|-641.68|26.01|
|prior_day_breakout|7203.T|6|0.4819|-6,810.98|-1,135.16|11.47|
|prior_day_breakout|6758.T|6|0.5352|-6,802.87|-1,133.81|13.45|
|prior_day_breakout|8306.T|10|1.1314|1,852.11|185.21|9.24|
|prior_day_breakout|9432.T|8|0.4891|-5,836.62|-729.58|7.89|
|prior_day_breakout|9984.T|8|0.5894|-9,693.53|-1,211.69|14.21|
|prior_day_breakout|6501.T|6|2.7576|12,147.92|2,024.65|5.03|
|prior_day_breakout|6861.T|7|1.2661|3,213.28|459.04|8.62|
|prior_day_breakout|8035.T|12|0.7143|-8,573.26|-714.44|23.55|
|prior_day_breakout|8058.T|8|0.2030|-15,214.74|-1,901.84|16.60|
|prior_day_breakout|4502.T|8|0.7548|-3,908.59|-488.57|10.65|
|sma63_trend|7203.T|10|0.7863|-4,064.71|-406.47|13.93|
|sma63_trend|6758.T|19|1.2487|11,188.90|588.89|20.83|
|sma63_trend|8306.T|12|1.1434|2,599.31|216.61|13.82|
|sma63_trend|9432.T|12|0.5121|-10,977.52|-914.79|16.74|
|sma63_trend|9984.T|13|0.8058|-9,210.64|-708.51|24.22|
|sma63_trend|6501.T|12|0.4898|-20,780.81|-1,731.73|31.03|
|sma63_trend|6861.T|11|0.8975|-2,996.60|-272.42|17.12|
|sma63_trend|8035.T|13|1.0899|3,425.70|263.52|20.24|
|sma63_trend|8058.T|12|1.5954|9,722.59|810.22|9.01|
|sma63_trend|4502.T|15|0.8887|-3,142.34|-209.49|20.14|


baseline・buyhold・費用2倍の銘柄別指標も `results/training.json` および `independent/training_verification.json` に保存し全件独立照合済み。小標本の高PF/高勝率を採用根拠としない。

## 品質除外診断

|候補|除外診断|通常純益 円 / PF|費用2倍純益 円 / PF|
|---|---|---:|---:|
|no_dow|exclude_sony|23,688.08 / 1.0693|-5,518.65 / 0.9842|
|no_dow|exclude_three_known_issues|23,308.06 / 1.0915|795.59 / 1.0031|
|prior_day_breakout|exclude_sony|-32,824.42 / 0.7756|-46,692.64 / 0.6940|
|prior_day_breakout|exclude_three_known_issues|-26,103.26 / 0.7446|-35,786.55 / 0.6648|
|sma63_trend|exclude_sony|-35,425.03 / 0.8636|-56,307.38 / 0.7892|
|sma63_trend|exclude_three_known_issues|-41,450.04 / 0.7963|-57,244.90 / 0.7259|


Sony除外9株は90万円、Sony/8306/8035除外7株は70万円、各sleeve10万円を維持し再配分なし。これらは事前固定したデータ品質診断で、銘柄選抜やclean-data保証ではない。

## Jev実行失敗の独立照合

保存 `jev_training_601649e779fd637cea0c0ed9e636cdf81d407745a949c07683743370919b361b.json` は `valid=false`、`error_type=HTTPError`、responseなし。
予約台帳はtrainingの1attemptのみ、同一request hash。canonical JSONからrequest hashを再計算し一致。
保存送信requestを現judgeのbuild_request(training.json)と比較して完全一致、訓練期間・年別/銘柄別要約だけで後期成績混入なし。
API呼出しは独立担当では行っていない。選択/評価を捏造するselection.jsonは作られていない。

- request SHA256: `601649e779fd637cea0c0ed9e636cdf81d407745a949c07683743370919b361b`。
- 送信サイズ: 23048 bytes（28,000上限内）。
- 引当: USD 0.0027525120000000004（200円/USD仮定で約0.5505円）。response/usageなしのため実課金額は不明。0円と断定しない。
- 型付き応答の成功、confidence閾値適用、Jev選抜は実サービスで未検証。数値研究の不採用とAPI失敗を区別する。
- TypeSafeスキルに従い、Choiceの選択肢確率/分布集中度を将来の取引勝率として扱わない。[Choice公式](https://docs.typesafe.ai/primitives/choice)、[Confidence公式](https://docs.typesafe.ai/confidence)。

## 未検証範囲・未実装コスト

感度確認は今回事前固定した3種類の条件変更と費用2倍に限定。SMA期間・pivot幅・RRなどの近傍パラメータ感度は未実施。
Sonyスピンオフ遡及調整、2銘柄OHLC合成修復、現在存続大型株の選択/生存バイアスを継承。元価格を取引所原票で全件保証していない。
配当・税・金利・現物分配の再現なし。手数料/滑りは包括代金率で、価格経路を変える滑り、板/寄付競合、ストップ高安で約定できない場合、呼値、100株単元は未実装。端株・連続調整株数の研究損益であり実口座収益ではない。

## 再現コマンド・引継ぎ

workspace rootから。既存訓練出力を保存し、再実行は別outputへ書く。API再送コマンドは含めない。

```powershell
python -m unittest discover -s tests -p test_tamukai_stocks_jev.py -v
python scripts/research_tamukai_stocks_jev.py --phase training --output agent_runs/tamukai_stocks_jev_20260926/reproduction
python agent_runs/tamukai_stocks_jev_20260926/independent/verify_training.py
```

独立checkerは正式resultsと失敗Jev証跡を照合して `independent/training_verification.json` を更新する。API接続なし。

- 次担当: 研究責任者/品質監査。
- 所有変更: 本validation.md、`agent_runs/tamukai_stocks_jev_20260926/independent/verify_training.py` と出力JSONのみ。
- 戦略・基準・共有データ変更なし。成果物最終存在と独立プロセスexit0確認済み。
- 引渡し可能: 全3候補訓練不採用の記述研究と、Jev失敗未選抜の事実。後期/Pine/実運用採用への根拠なし。

