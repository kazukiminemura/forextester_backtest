# 円クロスPF探索・3年間検証

期間: 2023-09-08以上2026-09-08未満（最終日2026-09-07、保存時刻）。サブエージェント不使用。
前回と完全に同じ216条件（36ロジック×6時間帯）、5通貨AUDJPY・CHFJPY・EURJPY・GBPJPY・NZDJPY。勝率70%条件なし。
RR1全決済、15分足、確定4時間足方向、ATR2、固定スプレッドと片道0.1pip滑りを維持。
結論: 前回のAUDJPYの2候補は3年PF1.5に未達。全216条件でも個別30件以上の最高PFは1.449。全安定性条件の通過0件。

## 前回の候補の期間比較

|AUDJPY候補|3か月PF|3年件数|3年勝率|3年PF|3年損益R|
|---|---:|---:|---:|---:|---:|
|range_sweep_l32_p0.00_c0.60__16_24|1.752|294|54.08%|1.151|20.752|
|ema_reclaim_e20_d0.25_x1.00__00_08|1.549|397|45.34%|0.820|-39.388|

## 同候補の1年ごとの比較

毎年9月8日を区切りとしたエントリー群。年末で強制決済せず、各群の取引の最終損益を集計する。年次口座損益ではない。

|候補|期間|件数|勝率|PF|損益R|
|---|---|---:|---:|---:|---:|
|range_sweep_l32_p0.00_c0.60__16_24|2023/9/8〜2024/9/7|92|47.83%|0.906|-4.563|
|range_sweep_l32_p0.00_c0.60__16_24|2024/9/8〜2025/9/7|109|56.88%|1.303|14.348|
|range_sweep_l32_p0.00_c0.60__16_24|2025/9/8〜2026/9/7|93|56.99%|1.263|10.967|
|ema_reclaim_e20_d0.25_x1.00__00_08|2023/9/8〜2024/9/7|138|39.13%|0.635|-30.856|
|ema_reclaim_e20_d0.25_x1.00__00_08|2024/9/8〜2025/9/7|117|45.30%|0.819|-11.654|
|ema_reclaim_e20_d0.25_x1.00__00_08|2025/9/8〜2026/9/7|142|51.41%|1.045|3.122|

レンジ抜け失敗は後の2年で利益が残ったが各年PF1.5未達。EMA20回復は最初の2年が赤字。短期の良さは3年全体のPF1.5として再現しなかった。

## 個別30件以上のPF上位15条件

|条件|通貨|件数|勝率|PF|
|---|---|---:|---:|---:|
|compression_expansion_l8_r0.90_b0.00__08_16|EURJPY|79|59.49%|1.449|
|compression_expansion_l8_r0.90_b0.10__08_16|EURJPY|77|57.14%|1.316|
|compression_expansion_l16_r0.90_b0.10__08_16|EURJPY|56|57.14%|1.313|
|compression_expansion_l16_r0.90_b0.00__08_16|EURJPY|58|56.90%|1.301|
|range_sweep_l32_p0.10_c0.60__16_24|AUDJPY|238|56.72%|1.280|
|day_pullback_min_displacement_adr0.40_budget0.70__all|EURJPY|32|56.25%|1.274|
|day_pullback_min_displacement_adr0.20_budget0.70__00_08|GBPJPY|81|55.56%|1.241|
|day_pullback_min_displacement_adr0.40_budget0.90__08_16|EURJPY|45|60.00%|1.238|
|range_sweep_l32_p0.10_c0.80__16_24|AUDJPY|143|55.94%|1.232|
|opening_range_retest_touch_atr0.00_budget0.90__00_08|CHFJPY|69|55.07%|1.214|
|range_sweep_l32_p0.00_c0.80__16_24|EURJPY|177|55.37%|1.208|
|day_pullback_min_displacement_adr0.40_budget0.90__00_12|CHFJPY|31|54.84%|1.205|
|opening_range_retest_touch_atr0.00_budget0.90__12_24|AUDJPY|60|55.00%|1.186|
|day_pullback_min_displacement_adr0.20_budget0.90__00_08|GBPJPY|92|54.35%|1.182|
|opening_range_retest_touch_atr0.10_budget0.90__16_24|AUDJPY|33|54.55%|1.177|

## PF1.5以上の小標本（個別通貨）

以下13条件はすべて30件未満。3年に期間を延ばしても件数のない条件では高PFが生じるため、そのまま採用しない。

|条件|通貨|件数|PF|
|---|---|---:|---:|
|compression_expansion_l8_r0.70_b0.00__08_16|GBPJPY|6|4.954|
|compression_expansion_l8_r0.70_b0.10__08_16|GBPJPY|6|4.954|
|compression_expansion_l16_r0.70_b0.00__08_16|GBPJPY|5|3.962|
|compression_expansion_l16_r0.70_b0.10__08_16|GBPJPY|5|3.962|
|compression_expansion_l8_r0.70_b0.00__08_16|AUDJPY|5|3.950|
|compression_expansion_l8_r0.70_b0.10__08_16|AUDJPY|4|2.966|
|compression_expansion_l16_r0.70_b0.00__08_16|AUDJPY|4|2.962|
|day_pullback_min_displacement_adr0.40_budget0.70__00_12|EURJPY|14|2.477|
|day_pullback_min_displacement_adr0.40_budget0.70__08_16|EURJPY|21|1.981|
|day_pullback_min_displacement_adr0.40_budget0.70__00_08|EURJPY|3|1.980|
|compression_expansion_l16_r0.70_b0.10__08_16|AUDJPY|3|1.978|
|compression_expansion_l8_r0.70_b0.00__08_16|NZDJPY|3|1.966|
|compression_expansion_l8_r0.70_b0.10__08_16|NZDJPY|3|1.966|

## 合算の比較

|件数条件|最高条件|件数|勝率|PF|
|---|---|---:|---:|---:|
|0件以上|compression_expansion_l8_r0.70_b0.10__08_16|17|70.59%|2.373|
|75件以上|range_sweep_l32_p0.10_c0.60__16_24|1250|52.00%|1.041|
|900件以上|range_sweep_l32_p0.10_c0.60__16_24|1250|52.00%|1.041|

## 検証証拠・制約

実走exit0、DESCRIPTIVE_COMPLETE。56テスト通過。296,191保存明細を再読込して、別計算式による全216条件の通貨/合算/月/年指標と抽出判定が一致。RR1・コスト後R・時計条件・次足・期間境界・非重複を確認。
候補・時間帯・銘柄・執行条件は前回プロトコルと一致。凍結コード指紋と文書プロトコル一致、Bars.datの実行前後属性一致。
月平均頻度を維持する候補抽出の総数下限は12倍（合算900、個別360）。毎月10件以上かつ利益、PF1.5、期待値正、決済DD10%以下を要求。これはPF1.5の数値達成とは別の安定性条件。30件以上の参考順位も併記して総数変更に結果を隠さない。
全期間既閲覧で真の未使用ホールドアウトではない。216条件×5通貨の多重比較と重複取引を含み、296,191独立標本とはみなさない。別担当の独立監査ではなく単独担当の別式照合。
固定スプレッド、スワップ未反映、変動スプレッド・実際の約定滑り未再現。コストストレス試験未実施。DDは初期資金0.25%固定リスクの決済損益のみで含み損は含まない。15分OHLC検査は全構成1分足の無欠損を保証しない。保存時刻のタイムゾーン/DSTは銘柄別未確認でJSTとは呼ばない。
追加の条件調整・Pine移植・実注文・Git公開なし。

成果物: agent_runs/quant_pf15_jpy_three_year_20260908/{protocol.json,results.json,trades.jsonl,verification.json,code_hashes.json,data_manifest.json,source_before.json,source_after.json}。
再現: PYTHONPATH=src;scripts を設定し python scripts/research_jpy_pf15_three_year.py（既存出力は上書きせず停止）。照合: python scripts/verify_jpy_pf15_three_year.py。
