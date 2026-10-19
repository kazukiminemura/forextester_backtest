# 品質監査: 株式押し目3候補とJev結果評価

実験ID: `tamukai_stocks_jev_20260926`。監査日: 2026-09-26。
担当の編集対象は `data_inventory.md` と本書のみ。戦略、成績、APIコード、選抜記録は変更していない。

確定判定: **AUDITED_REJECTED_TRAINING_ONLY_DATA_LIMITED / JEV_FAILED_NO_SELECTION**。
数値研究の不採用結果と、外部AI評価が取得できなかった事実を分けた限定引渡しは可能。Jevによる結果評価まで含む依頼の全面完了とは判定しない。

## 所見

1. **高・依頼の一部未完了: Jevの判断は得られていない。** 保存 `jev_training_601649e779fd637cea0c0ed9e636cdf81d407745a949c07683743370919b361b.json` は `valid=false`、`error_type=HTTPError`、response/usageなし。selection.jsonは存在しない。Jevが棄却を判断した、confidenceを返した、評価完了したとは報告できない。初回POSTの保存記録にはHTTP statusがなく、後続GET確認の403と初回POST原因を同一と断定しない。
2. **高・研究不採用: 3候補全てが学習gateを不通過。** `training.json` のeligibleは空。no_dowは通常PF1.073977<1.1、stress純益−4,090.01円。他2候補は通常費用から純益負。Jevの回答有無にかかわらず、候補を後期計算へ進めないのが事前仕様どおり。閾値変更や次善候補へのfallbackは認めない。
3. **高・データの既知制約: DATA_LIMITEDかつ全期間既閲覧。** 保存raw/CSVは前研究と同一。Sony分離調整未解明、2件合成高安補正、現在大型株の生存/選択バイアスを継承。2017–2025は前研究で既閲覧なので、後期を未使用holdoutと呼べない。9/7銘柄除外診断でこれら全てが解消されるわけではない。
4. **中・モデルの意味/実約定制約。** Jev Choiceの確率/confidenceは選択肢間の判断であり、将来利益や売買勝率の検証結果ではない。0.8は未校正の進行制限として明記済み。各10万円端株・売買代金片道0.1%/0.2%・配当税金利なし、100株単元/呼値/約定不能未再現も継承する。
5. **低・失敗費用は不明。** 送信前の引当1回 `$0.002752512`（200円/USDで約0.5505024円）が保持されている。response usageがないので実課金0円とは断定できない。上限2回の保守引当約1.1010048円は2円以内。旧実験のquotaを変更せず、新台帳で管理される。
6. **低・Jev入力圧縮は訓練後の変更。** 初回dry-run上限超過でstress銘柄別/品質診断年別等を省略した経緯を `jev_plan.md` に記録。候補/数値gate/判定質問/0.8条件に変更はなく、結果元ファイルは保存。今回全候補不適格かつAPI失敗のため、この入力圧縮が後期選抜を変えた証拠はない。

## 仕様・工程確認

- baselineは旧runnerを再利用し選抜不可。no_dowはDow条件除去だけ、prior_day_breakoutは突破高値を前日に変更だけ、sma63_trendはDowをSMA21>SMA63へ置換だけ。3案上限を維持。
- trainingは2019年末でバーを切断してから信号計算。2020以降の価格ファイル自体はhash/全体入力検査のため読むが、後期信号/損益をtraining集計へ混ぜない。
- 学習gateは50件/PF1.1/純益正/DD20%以内。後期は旧100件等の基準。前回と異なる学習screening条件は新実験の結果前protocolに固定され、実走開始hashと現在hashが一致。
- 翌観測営業日寄付、前3本SL、全決済RR1、窓優先、両到達SL優先、同足決済、区間末清算、1銘柄1保有、費用/MTMは旧実装を再利用。
- 選抜はtraining hash・候補enum・selector=jev・適格gateを確認。noneなら後期データ計算前にreturn。現時点でselection.json/evaluation.json/evaluationディレクトリはなく、新候補の後期計算を確認していない。
- Jevは研究集計の評価用で、売買ループには呼ばない。要求/応答/失敗保存、排他lock、事前引当、phase毎1attempt、合計2attempt、自動再送なし。失敗記録の再利用も例外停止。
- API判定はモデル/質問集合/Choice型/確率有限性と範囲/和/選択最大値/usageを検証し、低confidence・不適格はnone。今回有効応答がないため実機でこれらが受理できるかは未確認。

TypeSafeスキルに従って現行[API](https://docs.typesafe.ai/api)、[モデル料金・文脈上限](https://docs.typesafe.ai/models)、[confidence](https://docs.typesafe.ai/confidence)を2026-09-26に参照。入力$0.042/Mtoken・出力無料、総64k/state+最長質問32k、選択分布由来のconfidenceを確認した。学習集計に対するAPI契約と予算の監査に用い、売買利益の裏付けには用いていない。

## 監査担当の実行確認

- 保存データraw10/CSV10/manifestのhashを前回と照合。全23,140 CSV行のOHLC/正出来高/日付を再検査してexit 0。詳細は[data_inventory.md](data_inventory.md)。
- `python -m pytest -q tests/test_stock_jev_judge.py tests/test_tamukai_stocks_jev.py tests/test_tamukai_stocks_daily.py`：12 passed、exit 0。実APIを呼ばないテストで型不正、gate非上書き、API失敗引当/再送抑止、未来prefix、既存会計境界を確認。
- 保存trainingから現judgeのrequestを再構成し、失敗記録のrequest全体と完全一致。23,048 bytes、SHA256 `601649e779fd637cea0c0ed9e636cdf81d407745a949c07683743370919b361b`。台帳1行と同じhash、引当額一致、response/選抜/後期出力なしを確認（exit 0）。監査からAPI追加送信なし。
- training開始/完了は2026-09-26 06:33:26 UTC。API送信予約は06:35:13 UTC。訓練結果後に集計を送る時系列に一致。
- protocol SHA256 `d88d9150078bddfbf58705e42f1a480517176eca7863ac200cac5feb7fec4bf4`、training SHA256 `0da06299f6053cc8441c1bdc1e0b30f6cca48d1c58fdc0d61585c9c008cb3533`。
- 研究runner SHA256 `3c1267a497d5ddf40848720da18b2c7ada56cdf54e7c09e57782f1b40c114b50`。初回送信前judge SHA256 `3df1ec36fbd5eec7407c9fecd8181b030d3c88ceedc92de9098ab0b7e4893ff5`、judge tests `9ccc70d5b7c1b46ba6955b0ea2356708c6c40f810c240e64f9208416748d4caf`。jev_planの識別子と現在ファイル一致。
- 独立検証担当の `independent/verify_training.py` 全文を読んだ後、監査でも再実行。監査の編集責任を守るため `Path.write_text` を実行中だけmockして結果JSONへの書込みを抑止し、計算したresultと既存 `training_verification.json` の完全一致を追加確認した。100ケース・876取引観測・73,300個別MTM行・30集約・90年別・394,178 scalar・1,398 prefix・921信号・旧80CSV byte一致、exit 0。876/921は条件/費用間重複を含む。
- `validation.md`、`docs/tamukai_stocks_jev.md`、boardの当該実験欄と数値/条件/失敗状態を照合。3案全不適格・API未評価・実課金不明・後期未開始・DATA_LIMITED・既閲覧の記載に整合を確認。ダッシュボード実画面は主担当の確認報告であり、この監査担当による独立UI実確認は行っていない。

## 引渡し範囲

独立検証と主報告の照合は完了。数値研究の不採用結果とJev評価失敗の証拠は引渡し可。研究の会計再現を阻むコード不一致は認めず、候補追加や採否閾値変更は要求しない。

APIの有効評価なし、後期未計算、Pine未作成、TradingView実機未確認、実運用未承認。Jevを使った評価まで完了したという依頼完了表現は不可。APIアクセス復旧および既定の1phase1attempt停止方針を変更する再試行判断は責任者・ユーザーへ返し、監査から再送しない。データの真の未使用性・取引所原票・実際の単元/板/約定は引き続き未確認。
