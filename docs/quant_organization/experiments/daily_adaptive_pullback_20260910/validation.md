# 月次通貨選択を加えた追試

状態: `REJECTED_BY_FROZEN_GATES`、training選抜0、後半損益未計算。固定全通貨の押戻りより成績が悪化した。独立照合判定はaudit.mdを参照する。

## 結果

第一実験で合算利益のあったpullback05を固定し、過去確定shadow成績による月次top5通貨を追随した。新規候補は24/36/60暦月の3つだけ。第一の学習結果を見た事後的な追試であり、真の未使用評価ではない。

primaryは往復固定1.8pips＋保有0.2pip/暦日。全15通貨の価格母集団、2010–2018年、共通250足warmup。actual最多5ポジション、各構成通貨最多3。

|規則|取引数|勝率%|gross PF|primary PF|net R|日次MTM DD R|利益/出場通貨|metadata+.4 PF|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|固定全通貨pullback05比較|706|40.23|1.1452|1.0652|+25.71|43.48|9/15|1.0645|
|月次・直近24か月|214|36.45|0.9605|0.8949|-13.56|25.36|7/15|0.8940|
|月次・直近36か月|216|36.57|0.9950|0.9275|-9.31|22.34|5/14|0.9265|
|月次・直近60か月|212|36.79|1.0298|0.9536|-5.79|19.74|6/14|0.9525|

60か月はDD20R以下だがPF・期待値・利益通貨の過半数・学習3区分利益を満たさない。24/36か月はDDも不合格。全3候補とも両primary費用で損失、採用対象なし。

## 何が起きたか

元のshadow706件に対して、月次選択で除いたのは488/487/490件、最多保有または構成通貨の枠で除いたのは4/3/4件。固定全通貨よりDDは減ったが、勝率・平均R・PFも悪化した。事前仮説である「過去に向いた通貨が翌月以降にも向く」という持続性は、この有限な規則では確認できなかった。個別通貨の後付け採用や、良かった月だけを選ぶ操作は行っていない。

|学習区分|24か月net R / MTM増分|36か月net R / MTM増分|60か月net R / MTM増分|
|---|---:|---:|---:|
|2010–2012|-11.87 / -11.87|-11.87 / -11.87|-11.87 / -11.87|
|2013–2015|+8.79 / +8.60|+1.01 / +3.23|+3.12 / +3.53|
|2016–2018|-10.48 / -10.29|+1.55 / -0.67|+2.95 / +2.54|

60か月の保有費用なしはPF1.0096/+1.16R、primary0.2pip/日でPF0.9536/−5.79R、1pip/日でPF0.7591/−33.60R。費用に耐える余裕がない。24/36か月の1pip/日もPF0.7257/0.7527で損失。最大保有は全候補31観測足。実際の通貨別・曜日別スワップは未確認で、研究費用モデルの結果である。

## 証拠と引継ぎ

freeze UTC `2026-09-10T00:51:05.941760+00:00`。`agent_runs/daily_adaptive_pullback_20260910/completed/code_input_hashes.json` に今回仕様/実装と第一固定仕様/実装、日足入力のhashを結果前に保存。第一結果の比較値は全く同じ+25.710512098259443Rを再計算した。

実行コマンド:

```
python -m pytest tests/test_daily_adaptive_pullback.py tests/test_daily_edge_reset.py -q
python -m scripts.research_daily_adaptive_pullback
```

いずれもexit0。関連32tests（第一19＋第二13）通過。月初cutoff、lookback暦月、未確定/期末shadow除外、将来損益変更不変、8件/平均正/同値順、同時exit前処理、日中出口まで枠保有、構成通貨数、phase開始前entry除外、actual MTM等を確認。

再現用（未実行）の新規出力先コマンド:

```
python -m scripts.research_daily_adaptive_pullback --output agent_runs/daily_adaptive_pullback_20260910/reproduction
```

- 実験ID / 担当 / 次担当: daily_adaptive_pullback_20260910 / 研究開発 / 独立検証。
- 状態: IMPLEMENTED、学習実走不採用、独立監査待ち。
- 入力: 第一pullback05仮説/規則と15通貨日足、今回protocol/hypothesis、結果前hash。
- 編集: scripts/research_daily_adaptive_pullback.py、tests/test_daily_adaptive_pullback.py、今回hypothesis.md/protocol.json/validation.md、今回agent_runs内だけ。第一成果物不変。
- 成果物: completed/results.json、shadow30JSON、actual90JSON・1,284取引明細（二費用重複を含む）、90equity、6aggregate equity、324月次選抜記録、2,118入場判断記録、選抜空のselection_before_validation.json。
- 検証事項: actual判断は月初cutoff以前のshadowのみ、同時入場順と枠管理は時刻基準、skipはshadowルールを変えない。正式な全件再現は独立担当へ。
- 不採用理由: 全3候補両費用で赤字、利益通貨過半数なし、学習初期区分赤字。月次選択で固定全通貨より期待値が悪化。
- 未確認: 実ブローカーswap、保存価格のbid/ask、TZ、日中DD、口座通貨換算。母集団通貨は相関している。
- 次工程: 独立照合のみ。追加3候補の最終予算を完了し、基準や選抜規則を再変更しない。Pineへ渡せる合格候補なし。
- 実注文: なし。
