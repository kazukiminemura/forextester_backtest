# 円クロス・直近3か月の候補探索

対象: 2026-06-08〜2026-09-07（保存時刻）。AUDJPY / CHFJPY / EURJPY / GBPJPY / NZDJPY。サブエージェント不使用。
固定36候補（基本24＋当日状態12）、RR1全決済、ATR2、15分足・確定4時間足、固定スプレッド＋片道0.1pip滑り。
結論: 合算・個別とも事前の候補抽出基準通過0件。GBPJPYに75%の小標本はあるが12件のみ。全候補・全通貨を調べた後の高成績であり、将来の勝率を示さない。

## 主要結果

- 合算最高: 前日高安の抜け失敗、penetration 0.10 ATR、当日レンジ上限0.70 ADR。28勝/49件=57.14%、PF1.319、+6.733R。取引数75未満・勝率70%未達・PF1.5未達・最終月損失。
- 個別最高: GBPJPY、前日高安の抜け失敗、penetration 0.00 ATR、上限0.70 ADR。9勝/12件=75.00%、PF2.973、+5.946R。最低30件・各月10件の基準未達。Wilson95%下限46.77%（多重比較調整なし）。
- 個別30件以上の最高: AUDJPY、EMA20回復、押し深さ0.50 ATR・伸び上限1.00 ATR。45勝/76件=59.21%、PF1.388、+12.497R。70%とPF1.5未達。

## GBPJPY 75%候補の月別エントリー群

|期間|件数|勝率|PF|損益R|
|---|---:|---:|---:|---:|
|6/8〜7/7|2|100.00%|損失なし・評価不能|1.992|
|7/8〜8/7|7|57.14%|1.322|0.969|
|8/8〜9/7|3|100.00%|損失なし・評価不能|2.984|

月区切りで強制決済せず、エントリー日時で分類した最終損益。月次口座損益ではない。

## 全36候補（5通貨合算）

|候補|件数|勝率|PF|平均R|
|---|---:|---:|---:|---:|
|previous_day_failed_break_penetration_atr0.10_budget0.70|49|57.14%|1.319|0.1374|
|previous_day_failed_break_penetration_atr0.00_budget0.70|54|55.56%|1.236|0.1055|
|ema_reclaim_e20_d0.25_x0.50|319|49.22%|0.950|-0.0260|
|ema_reclaim_e20_d0.25_x1.00|404|49.01%|0.944|-0.0291|
|compression_expansion_l8_r0.70_b0.10|39|48.72%|0.938|-0.0318|
|previous_day_failed_break_penetration_atr0.10_budget0.90|70|48.57%|0.933|-0.0349|
|previous_day_failed_break_penetration_atr0.00_budget0.90|75|48.00%|0.911|-0.0464|
|ema_reclaim_e20_d0.50_x0.50|278|47.48%|0.885|-0.0613|
|ema_reclaim_e20_d0.50_x1.00|368|47.01%|0.871|-0.0695|
|compression_expansion_l8_r0.70_b0.00|43|46.51%|0.850|-0.0807|
|ema_reclaim_e40_d0.25_x1.00|308|46.10%|0.837|-0.0892|
|ema_reclaim_e40_d0.25_x0.50|244|44.67%|0.788|-0.1193|
|ema_reclaim_e40_d0.50_x1.00|264|43.94%|0.774|-0.1275|
|day_pullback_min_displacement_adr0.20_budget0.70|94|43.62%|0.754|-0.1413|
|day_pullback_min_displacement_adr0.20_budget0.90|119|42.86%|0.734|-0.1547|
|ema_reclaim_e40_d0.50_x0.50|200|42.50%|0.730|-0.1565|
|range_sweep_l16_p0.00_c0.60|644|42.24%|0.718|-0.1649|
|range_sweep_l16_p0.10_c0.60|555|41.80%|0.705|-0.1737|
|range_sweep_l16_p0.00_c0.80|422|41.71%|0.703|-0.1752|
|range_sweep_l32_p0.10_c0.60|401|41.65%|0.703|-0.1750|
|range_sweep_l32_p0.00_c0.60|479|41.54%|0.699|-0.1776|
|opening_range_retest_touch_atr0.00_budget0.90|58|41.38%|0.687|-0.1874|
|range_sweep_l32_p0.00_c0.80|303|40.92%|0.680|-0.1914|
|range_sweep_l16_p0.10_c0.80|340|40.00%|0.653|-0.2117|
|opening_range_retest_touch_atr0.00_budget0.70|50|40.00%|0.647|-0.2165|
|range_sweep_l32_p0.10_c0.80|246|39.43%|0.640|-0.2204|
|opening_range_retest_touch_atr0.10_budget0.90|93|38.71%|0.618|-0.2374|
|day_pullback_min_displacement_adr0.40_budget0.70|19|36.84%|0.563|-0.2843|
|opening_range_retest_touch_atr0.10_budget0.70|82|36.59%|0.564|-0.2808|
|compression_expansion_l8_r0.90_b0.10|306|35.95%|0.550|-0.2903|
|compression_expansion_l8_r0.90_b0.00|325|35.69%|0.544|-0.2959|
|compression_expansion_l16_r0.70_b0.00|32|34.38%|0.508|-0.3250|
|compression_expansion_l16_r0.90_b0.10|235|31.91%|0.459|-0.3718|
|compression_expansion_l16_r0.90_b0.00|251|31.87%|0.457|-0.3732|
|compression_expansion_l16_r0.70_b0.10|29|31.03%|0.445|-0.3853|
|day_pullback_min_displacement_adr0.40_budget0.90|34|26.47%|0.352|-0.4847|

## 個別上位10件（小標本を含む）

|候補|通貨|件数|勝率|PF|
|---|---|---:|---:|---:|
|previous_day_failed_break_penetration_atr0.10_budget0.70|GBPJPY|12|75.00%|2.973|
|previous_day_failed_break_penetration_atr0.00_budget0.70|GBPJPY|12|75.00%|2.973|
|previous_day_failed_break_penetration_atr0.10_budget0.90|GBPJPY|15|66.67%|1.982|
|previous_day_failed_break_penetration_atr0.00_budget0.90|GBPJPY|15|66.67%|1.982|
|opening_range_retest_touch_atr0.10_budget0.90|CHFJPY|22|63.64%|1.733|
|opening_range_retest_touch_atr0.10_budget0.70|CHFJPY|18|61.11%|1.555|
|previous_day_failed_break_penetration_atr0.10_budget0.70|AUDJPY|10|60.00%|1.482|
|previous_day_failed_break_penetration_atr0.00_budget0.70|AUDJPY|10|60.00%|1.482|
|ema_reclaim_e20_d0.50_x1.00|AUDJPY|76|59.21%|1.388|
|compression_expansion_l8_r0.70_b0.10|GBPJPY|17|58.82%|1.415|

## 検証と制約

実走exit0、DESCRIPTIVE_COMPLETE。7,832保存明細の幾何・順序確認と別計算式による全通貨/全月集計が一致。53テスト通過。コードハッシュと凍結プロトコル一致、Bars.dat属性の実行前後一致。
7,832件には類似候補間の重複取引があり、独立標本数とはみなさない。単独担当での別計算式照合であり、別担当による監査ではない。
候補・通貨・期間は既閲覧で、同じ期間で選んだ成績。事後の期間選択と36×5比較を含む。合格しても未使用期間による検証ではない。
固定スプレッド、スワップ未反映、実際の約定滑り・変動スプレッド未再現。DDは初期資金0.25%固定リスクの決済損益で含み損を含まない。15分OHLC品質検査は全構成1分足の無欠損を保証しない。時刻は保存時刻00時区切りでJSTとは未確認。
本期間で追加調整はしない。Pine移植・実運用・注文・Git公開なし。

実行: PYTHONPATH=src;scripts、python scripts/research_jpy_recent3m.py（既存出力がある場合上書きせず停止）。照合: python scripts/verify_jpy_recent3m.py。
証拠: agent_runs/quant70_jpy_recent3m_20260908/ の protocol.json、results.json、trades.jsonl、independent_formula_verification.json、data_manifest.json、code_hashes.json、source_before.json、source_after.json。
