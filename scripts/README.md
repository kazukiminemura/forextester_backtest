# Pythonスクリプト案内

この一覧はローカル作業フォルダー全体の索引です。未コミットの研究コード・仕様も含むため、GitHub上では一部リンクの実体が未公開です。今回の整理コミットに、これらの研究コードは含めていません。

研究系列と役割から既存スクリプトを探すための索引です。2026-11-06時点の `scripts/**/*.py` 全294本を掲載しています。Pine本体は [TradingView案内](tradingview/README.md)、研究の採否は [実験記録](../docs/quant_organization/experiments/) と [研究台帳](../docs/quant_organization/board.md) を確認してください。

## 使い方と保存方針

1. 下の研究系列から対象を探し、実験の `protocol.json`・`hypothesis.md`・`validation.md`・`audit.md` で入力、再現コマンド、終了状態、採否を確認します。役割欄は用途の案内で、独立検証合格や収益性を示すものではありません。
2. 研究・探索、replay、独立検証・照合、入力準備、生成・表示ツールを分けて使います。似た名前でも期間、対象、条件、費用、実行段階が異なるため、重複や不要物とは扱いません。不採用の結果も研究証拠として保持します。
3. 実行は個別に依頼されたときだけ行います。一覧の一括実行はしません。入力準備には外部取得、研究には長時間計算、出力には既存ファイル更新を伴うものがあります。必要な依存関係は対象スクリプトと既存の再現手順を確認します。
4. この整理では元の物理パスを維持します。スクリプト間import、`Path(__file__)` からの相対参照、テスト、protocol内パス、凍結済みSHAを保つためです。結果の数値・取引一覧・ソース控えは `agent_runs/<実験ID>/`、説明と判定は `docs/quant_organization/experiments/<実験ID>/` を参照します。

## Patrick：4段階の経済検証とH4_7Dの区別

|段階|実験記録|Python入口|意味|
|---|---|---|---|
|初回v1|[patrick_vp_jst_20261106](../docs/quant_organization/experiments/patrick_vp_jst_20261106/)|[backtest_patrick_vp_jst.py](backtest_patrick_vp_jst.py)|日本08時・保存volume代理・ニュース除外なしの固定検証。対象データではsetup・取引ゼロ。|
|range2|[patrick_vp_jst_range2_20261106](../docs/quant_organization/experiments/patrick_vp_jst_range2_20261106/)|[backtest_patrick_vp_jst_range2.py](backtest_patrick_vp_jst_range2.py)|レンジ上限だけ1→2ATRへ変更。setupは増加したが約定ゼロ。|
|weekly|[patrick_vp_jst_weekly_20261106](../docs/quant_organization/experiments/patrick_vp_jst_weekly_20261106/)|[backtest_patrick_vp_jst_weekly.py](backtest_patrick_vp_jst_weekly.py)|20候補を学習期間の頻度だけで共通選抜。L9_marketは各通貨の学習平均週1〜2回に未達。|
|weekly_expiry|[patrick_vp_jst_weekly_expiry_20261106](../docs/quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/)|[backtest_patrick_vp_jst_weekly_expiry.py](backtest_patrick_vp_jst_weekly_expiry.py)|追加9候補からE24_OFFを頻度だけで選抜。頻度目標達成と経済性を分離し、経済性は不採用として保存。|

現在の [Patrick Pine](tradingview/patrick_vp_jst_weekly_indicator.pine) は **H4_7D** です。確定H4の形を開始時刻から過去7暦日で考慮し、前週・2週前の週VPを使います。旧E24_OFFの24時間条件と異なるため、上記4段階の経済結果・頻度を新版へ転用しません。表示と実機確認は [H4_7D対応表](../docs/quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/pine_h4_week_mapping.md) と [検証記録](../docs/quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/pine_h4_week_validation.md) を参照してください。独自のM1シミュレーションを行うindicatorであり、標準Strategy Testerと同一ではありません。旧Pine控え・旧テストの参照先も再現用に保持します。

## 研究系列別一覧

ファイル名は実体への相対リンクです。系列内はファイル名順です。

### Patrick：週VP・日本08時（4本）

|スクリプト|役割|
|---|---|
|[backtest_patrick_vp_jst.py](backtest_patrick_vp_jst.py)|固定仕様の検証ランナー|
|[backtest_patrick_vp_jst_range2.py](backtest_patrick_vp_jst_range2.py)|固定仕様の検証ランナー|
|[backtest_patrick_vp_jst_weekly.py](backtest_patrick_vp_jst_weekly.py)|固定仕様の検証ランナー|
|[backtest_patrick_vp_jst_weekly_expiry.py](backtest_patrick_vp_jst_weekly_expiry.py)|固定仕様の検証ランナー|

### PF15：複数市場の固定実験（88本）

|スクリプト|役割|
|---|---|
|[export_pf15_us_8k_price_drift_pine.py](export_pf15_us_8k_price_drift_pine.py)|成果物出力|
|[prepare_pf15_binance_cm_liquidation_reversal_20261104.py](prepare_pf15_binance_cm_liquidation_reversal_20261104.py)|入力準備|
|[prepare_pf15_bybit_book_20261104.py](prepare_pf15_bybit_book_20261104.py)|入力準備|
|[prepare_pf15_bybit_dated_basis_20261104.py](prepare_pf15_bybit_dated_basis_20261104.py)|入力準備|
|[prepare_pf15_bybit_dated_basis_window_20261104.py](prepare_pf15_bybit_dated_basis_window_20261104.py)|入力準備|
|[prepare_pf15_bybit_funding_carry_20261104.py](prepare_pf15_bybit_funding_carry_20261104.py)|入力準備|
|[prepare_pf15_crypto_spot_cross_section_20261104.py](prepare_pf15_crypto_spot_cross_section_20261104.py)|入力準備|
|[prepare_pf15_crypto_spot_cross_section_minutes_20261104.py](prepare_pf15_crypto_spot_cross_section_minutes_20261104.py)|入力準備|
|[prepare_pf15_deribit_inverse_basis_20261104.py](prepare_pf15_deribit_inverse_basis_20261104.py)|入力準備|
|[prepare_pf15_etf_trend_prices_20261104.py](prepare_pf15_etf_trend_prices_20261104.py)|入力準備|
|[prepare_pf15_gold_silver_intraday_pair_20261104.py](prepare_pf15_gold_silver_intraday_pair_20261104.py)|入力準備|
|[prepare_pf15_us_10q_earnings_drift_20261104.py](prepare_pf15_us_10q_earnings_drift_20261104.py)|入力準備|
|[prepare_pf15_us_8k_price_drift_20261104.py](prepare_pf15_us_8k_price_drift_20261104.py)|入力準備|
|[replay_pf15_daily_failed_break_20261104.py](replay_pf15_daily_failed_break_20261104.py)|約定・判定の再現|
|[replay_pf15_executable_labels_20261104.py](replay_pf15_executable_labels_20261104.py)|約定・判定の再現|
|[replay_pf15_fx_cross_rank_20261103.py](replay_pf15_fx_cross_rank_20261103.py)|約定・判定の再現|
|[research_jpy_pf15_rr15_three_year.py](research_jpy_pf15_rr15_three_year.py)|研究・候補比較|
|[research_jpy_pf15_three_year.py](research_jpy_pf15_three_year.py)|研究・候補比較|
|[research_pf15_binance_cm_liquidation_reversal_20261104.py](research_pf15_binance_cm_liquidation_reversal_20261104.py)|研究・候補比較|
|[research_pf15_btc_funding_20261104.py](research_pf15_btc_funding_20261104.py)|研究・候補比較|
|[research_pf15_btc_weekly_momentum_20261104.py](research_pf15_btc_weekly_momentum_20261104.py)|研究・候補比較|
|[research_pf15_bybit_dated_basis_20261104.py](research_pf15_bybit_dated_basis_20261104.py)|研究・候補比較|
|[research_pf15_bybit_funding_carry_20261104.py](research_pf15_bybit_funding_carry_20261104.py)|研究・候補比較|
|[research_pf15_bybit_ofi_20261104.py](research_pf15_bybit_ofi_20261104.py)|研究・候補比較|
|[research_pf15_compact_ml_20261103.py](research_pf15_compact_ml_20261103.py)|研究・候補比較|
|[research_pf15_compact_ml_extension_20261103.py](research_pf15_compact_ml_extension_20261103.py)|研究・候補比較|
|[research_pf15_compact_ml_spread_gate_20261104.py](research_pf15_compact_ml_spread_gate_20261104.py)|研究・候補比較|
|[research_pf15_compact_ml_swap_20261103.py](research_pf15_compact_ml_swap_20261103.py)|研究・候補比較|
|[research_pf15_compact_ml_tick_execution_20261103.py](research_pf15_compact_ml_tick_execution_20261103.py)|研究・候補比較|
|[research_pf15_crypto_spot_cross_section_20261104.py](research_pf15_crypto_spot_cross_section_20261104.py)|研究・候補比較|
|[research_pf15_daily_channel_20261104.py](research_pf15_daily_channel_20261104.py)|研究・候補比較|
|[research_pf15_daily_failed_break_20261104.py](research_pf15_daily_failed_break_20261104.py)|研究・候補比較|
|[research_pf15_deribit_inverse_basis_20261104.py](research_pf15_deribit_inverse_basis_20261104.py)|研究・候補比較|
|[research_pf15_equity_shock_yen_20261104.py](research_pf15_equity_shock_yen_20261104.py)|研究・候補比較|
|[research_pf15_etf_trend_20261104.py](research_pf15_etf_trend_20261104.py)|研究・候補比較|
|[research_pf15_eurjpy_20261103.py](research_pf15_eurjpy_20261103.py)|研究・候補比較|
|[research_pf15_executable_labels_20261104.py](research_pf15_executable_labels_20261104.py)|研究・候補比較|
|[research_pf15_fx_cross_rank_20261103.py](research_pf15_fx_cross_rank_20261103.py)|研究・候補比較|
|[research_pf15_fx_fixing_20261103.py](research_pf15_fx_fixing_20261103.py)|研究・候補比較|
|[research_pf15_fx_policy_rate_20261103.py](research_pf15_fx_policy_rate_20261103.py)|研究・候補比較|
|[research_pf15_fx_round_break_20261104.py](research_pf15_fx_round_break_20261104.py)|研究・候補比較|
|[research_pf15_fx_weekly_momentum_20261103.py](research_pf15_fx_weekly_momentum_20261103.py)|研究・候補比較|
|[research_pf15_gold_macro_20261104.py](research_pf15_gold_macro_20261104.py)|研究・候補比較|
|[research_pf15_gold_real_yield_20261104.py](research_pf15_gold_real_yield_20261104.py)|研究・候補比較|
|[research_pf15_gold_silver_intraday_pair_20261104.py](research_pf15_gold_silver_intraday_pair_20261104.py)|研究・候補比較|
|[research_pf15_gold_silver_ratio_20261104.py](research_pf15_gold_silver_ratio_20261104.py)|研究・候補比較|
|[research_pf15_histdata_extension_20261103.py](research_pf15_histdata_extension_20261103.py)|研究・候補比較|
|[research_pf15_london_open_impulse_20261104.py](research_pf15_london_open_impulse_20261104.py)|研究・候補比較|
|[research_pf15_month_end_flow_20261104.py](research_pf15_month_end_flow_20261104.py)|研究・候補比較|
|[research_pf15_stock_52w_high_20261104.py](research_pf15_stock_52w_high_20261104.py)|研究・候補比較|
|[research_pf15_stock_gap_recovery_20261104.py](research_pf15_stock_gap_recovery_20261104.py)|研究・候補比較|
|[research_pf15_stock_intraday_reversal_20261104.py](research_pf15_stock_intraday_reversal_20261104.py)|研究・候補比較|
|[research_pf15_stock_low_vol_20261104.py](research_pf15_stock_low_vol_20261104.py)|研究・候補比較|
|[research_pf15_stock_turn_month_20261104.py](research_pf15_stock_turn_month_20261104.py)|研究・候補比較|
|[research_pf15_stock_volume_premium_20261104.py](research_pf15_stock_volume_premium_20261104.py)|研究・候補比較|
|[research_pf15_tick_liquidity_20261103.py](research_pf15_tick_liquidity_20261103.py)|研究・候補比較|
|[research_pf15_us_10q_earnings_drift_20261104.py](research_pf15_us_10q_earnings_drift_20261104.py)|研究・候補比較|
|[research_pf15_us_8k_price_drift_20261104.py](research_pf15_us_8k_price_drift_20261104.py)|研究・候補比較|
|[research_pf15_us_cpi_20261103.py](research_pf15_us_cpi_20261103.py)|研究・候補比較|
|[research_pf15_usd_residual_20261103.py](research_pf15_usd_residual_20261103.py)|研究・候補比較|
|[research_pf15_weekend_half_gap_20261103.py](research_pf15_weekend_half_gap_20261103.py)|研究・候補比較|
|[validate_pf15_binance_cm_liquidation_reversal_20261104.py](validate_pf15_binance_cm_liquidation_reversal_20261104.py)|独立検証用|
|[validate_pf15_btc_funding_20261104.py](validate_pf15_btc_funding_20261104.py)|独立検証用|
|[validate_pf15_btc_weekly_momentum_20261104.py](validate_pf15_btc_weekly_momentum_20261104.py)|独立検証用|
|[validate_pf15_bybit_dated_basis_20261104.py](validate_pf15_bybit_dated_basis_20261104.py)|独立検証用|
|[validate_pf15_bybit_funding_carry_20261104.py](validate_pf15_bybit_funding_carry_20261104.py)|独立検証用|
|[validate_pf15_bybit_ofi_20261104.py](validate_pf15_bybit_ofi_20261104.py)|独立検証用|
|[validate_pf15_crypto_spot_cross_section_20261104.py](validate_pf15_crypto_spot_cross_section_20261104.py)|独立検証用|
|[validate_pf15_daily_channel_20261104.py](validate_pf15_daily_channel_20261104.py)|独立検証用|
|[validate_pf15_daily_failed_break_20261104.py](validate_pf15_daily_failed_break_20261104.py)|独立検証用|
|[validate_pf15_daily_failed_break_validation_20261104.py](validate_pf15_daily_failed_break_validation_20261104.py)|独立検証用|
|[validate_pf15_deribit_inverse_basis_20261104.py](validate_pf15_deribit_inverse_basis_20261104.py)|独立検証用|
|[validate_pf15_equity_shock_yen_20261104.py](validate_pf15_equity_shock_yen_20261104.py)|独立検証用|
|[validate_pf15_etf_trend_20261104.py](validate_pf15_etf_trend_20261104.py)|独立検証用|
|[validate_pf15_fx_round_break_20261104.py](validate_pf15_fx_round_break_20261104.py)|独立検証用|
|[validate_pf15_gold_silver_intraday_pair_20261104.py](validate_pf15_gold_silver_intraday_pair_20261104.py)|独立検証用|
|[validate_pf15_gold_silver_ratio_20261104.py](validate_pf15_gold_silver_ratio_20261104.py)|独立検証用|
|[validate_pf15_london_open_impulse_20261104.py](validate_pf15_london_open_impulse_20261104.py)|独立検証用|
|[validate_pf15_stock_52w_high_20261104.py](validate_pf15_stock_52w_high_20261104.py)|独立検証用|
|[validate_pf15_stock_gap_recovery_20261104.py](validate_pf15_stock_gap_recovery_20261104.py)|独立検証用|
|[validate_pf15_stock_intraday_reversal_20261104.py](validate_pf15_stock_intraday_reversal_20261104.py)|独立検証用|
|[validate_pf15_stock_low_vol_20261104.py](validate_pf15_stock_low_vol_20261104.py)|独立検証用|
|[validate_pf15_stock_turn_month_20261104.py](validate_pf15_stock_turn_month_20261104.py)|独立検証用|
|[validate_pf15_stock_volume_premium_20261104.py](validate_pf15_stock_volume_premium_20261104.py)|独立検証用|
|[validate_pf15_us_10q_earnings_drift_20261104.py](validate_pf15_us_10q_earnings_drift_20261104.py)|独立検証用|
|[validate_pf15_us_8k_price_drift_20261104.py](validate_pf15_us_8k_price_drift_20261104.py)|独立検証用|
|[verify_jpy_pf15_rr15_three_year.py](verify_jpy_pf15_rr15_three_year.py)|再検証・照合用|
|[verify_jpy_pf15_three_year.py](verify_jpy_pf15_three_year.py)|再検証・照合用|

### Dominant Wave：波形・上位足・約定（34本）

|スクリプト|役割|
|---|---|
|[audit_dominant_wave_eurgbp_20261106.py](audit_dominant_wave_eurgbp_20261106.py)|監査用|
|[diagnose_dominant_wave_adaptive_prediction.py](diagnose_dominant_wave_adaptive_prediction.py)|診断・原因分析|
|[diagnose_dominant_wave_rrcost_failure.py](diagnose_dominant_wave_rrcost_failure.py)|診断・原因分析|
|[probe_dominant_wave_range_fidelity.py](probe_dominant_wave_range_fidelity.py)|診断・適合性確認|
|[research_dominant_wave_adaptive60.py](research_dominant_wave_adaptive60.py)|研究・候補比較|
|[research_dominant_wave_atrbar60.py](research_dominant_wave_atrbar60.py)|研究・候補比較|
|[research_dominant_wave_breakbar3.py](research_dominant_wave_breakbar3.py)|研究・候補比較|
|[research_dominant_wave_candle60.py](research_dominant_wave_candle60.py)|研究・候補比較|
|[research_dominant_wave_context60.py](research_dominant_wave_context60.py)|研究・候補比較|
|[research_dominant_wave_dailycontext60.py](research_dominant_wave_dailycontext60.py)|研究・候補比較|
|[research_dominant_wave_geometry60.py](research_dominant_wave_geometry60.py)|研究・候補比較|
|[research_dominant_wave_h1ny60.py](research_dominant_wave_h1ny60.py)|研究・候補比較|
|[research_dominant_wave_htf.py](research_dominant_wave_htf.py)|研究・候補比較|
|[research_dominant_wave_minute60.py](research_dominant_wave_minute60.py)|研究・候補比較|
|[research_dominant_wave_mlpre2017.py](research_dominant_wave_mlpre2017.py)|研究・候補比較|
|[research_dominant_wave_mltf_pre2017.py](research_dominant_wave_mltf_pre2017.py)|研究・候補比較|
|[research_dominant_wave_parentbudget60.py](research_dominant_wave_parentbudget60.py)|研究・候補比較|
|[research_dominant_wave_parenthtf60.py](research_dominant_wave_parenthtf60.py)|研究・候補比較|
|[research_dominant_wave_parentonly60.py](research_dominant_wave_parentonly60.py)|研究・候補比較|
|[research_dominant_wave_parentrr60.py](research_dominant_wave_parentrr60.py)|研究・候補比較|
|[research_dominant_wave_persistent60.py](research_dominant_wave_persistent60.py)|研究・候補比較|
|[research_dominant_wave_protected60.py](research_dominant_wave_protected60.py)|研究・候補比較|
|[research_dominant_wave_retest60.py](research_dominant_wave_retest60.py)|研究・候補比較|
|[research_dominant_wave_rr13.py](research_dominant_wave_rr13.py)|研究・候補比較|
|[research_dominant_wave_rr1_compare.py](research_dominant_wave_rr1_compare.py)|研究・候補比較|
|[research_dominant_wave_rrcost60.py](research_dominant_wave_rrcost60.py)|研究・候補比較|
|[research_dominant_wave_rrcost60_oos.py](research_dominant_wave_rrcost60_oos.py)|研究・候補比較|
|[research_dominant_wave_sessions60.py](research_dominant_wave_sessions60.py)|研究・候補比較|
|[research_dominant_wave_structure.py](research_dominant_wave_structure.py)|研究・候補比較|
|[research_dominant_wave_tickcontinuation60.py](research_dominant_wave_tickcontinuation60.py)|研究・候補比較|
|[research_dominant_wave_tickpullback60.py](research_dominant_wave_tickpullback60.py)|研究・候補比較|
|[research_dominant_wave_tickquality60.py](research_dominant_wave_tickquality60.py)|研究・候補比較|
|[research_dominant_wave_tickrr60.py](research_dominant_wave_tickrr60.py)|研究・候補比較|
|[research_dominant_wave_ticktrigger60.py](research_dominant_wave_ticktrigger60.py)|研究・候補比較|

### BB・BB3：バンド・相場環境（27本）

|スクリプト|役割|
|---|---|
|[bb3_jev_dashboard.py](bb3_jev_dashboard.py)|閲覧・判断支援UI|
|[diagnose_bb_opportunities.py](diagnose_bb_opportunities.py)|診断・原因分析|
|[report_bb3_gmo_three_year.py](report_bb3_gmo_three_year.py)|結果レポート生成|
|[report_bb3_pair_winrates.py](report_bb3_pair_winrates.py)|結果レポート生成|
|[research_bb3_candle_shapes.py](research_bb3_candle_shapes.py)|研究・候補比較|
|[research_bb3_context_center5.py](research_bb3_context_center5.py)|研究・候補比較|
|[research_bb3_context_dinapoli.py](research_bb3_context_dinapoli.py)|研究・候補比較|
|[research_bb3_context_dinapoli_deceleration.py](research_bb3_context_dinapoli_deceleration.py)|研究・候補比較|
|[research_bb3_context_dinapoli_wait.py](research_bb3_context_dinapoli_wait.py)|研究・候補比較|
|[research_bb3_context_exits.py](research_bb3_context_exits.py)|研究・候補比較|
|[research_bb3_context_retest.py](research_bb3_context_retest.py)|研究・候補比較|
|[research_bb3_context_structure_stop.py](research_bb3_context_structure_stop.py)|研究・候補比較|
|[research_bb3_context_timing.py](research_bb3_context_timing.py)|研究・候補比較|
|[research_bb3_jev.py](research_bb3_jev.py)|研究・候補比較|
|[research_bb3_jev_engine.py](research_bb3_jev_engine.py)|研究・候補比較|
|[research_bb3_jev_refine.py](research_bb3_jev_refine.py)|研究・候補比較|
|[research_bb3_mean_reversion.py](research_bb3_mean_reversion.py)|研究・候補比較|
|[research_bb3_regime.py](research_bb3_regime.py)|研究・候補比較|
|[research_bb_alternatives.py](research_bb_alternatives.py)|研究・候補比較|
|[research_bb_alternatives_sixyear.py](research_bb_alternatives_sixyear.py)|研究・候補比較|
|[research_bb_confirm_rr_extend.py](research_bb_confirm_rr_extend.py)|研究・候補比較|
|[research_bb_event_edge.py](research_bb_event_edge.py)|研究・候補比較|
|[research_bb_night_rr1.py](research_bb_night_rr1.py)|研究・候補比較|
|[research_btc_bb_allhours.py](research_btc_bb_allhours.py)|研究・候補比較|
|[review_bb3_code_with_jev.py](review_bb3_code_with_jev.py)|レビュー用|
|[review_bb_alternatives_with_jev.py](review_bb_alternatives_with_jev.py)|レビュー用|
|[verify_bb3_mean_reversion.py](verify_bb3_mean_reversion.py)|再検証・照合用|

### Yosuga：ダウ・時刻・入口条件（18本）

|スクリプト|役割|
|---|---|
|[diagnose_yosuga_context_coverage.py](diagnose_yosuga_context_coverage.py)|診断・原因分析|
|[research_yosuga_15m_entry_context.py](research_yosuga_15m_entry_context.py)|研究・候補比較|
|[research_yosuga_5m_market_sessions.py](research_yosuga_5m_market_sessions.py)|研究・候補比較|
|[research_yosuga_5m_time_filters.py](research_yosuga_5m_time_filters.py)|研究・候補比較|
|[research_yosuga_acceleration_entry.py](research_yosuga_acceleration_entry.py)|研究・候補比較|
|[research_yosuga_channel.py](research_yosuga_channel.py)|研究・候補比較|
|[research_yosuga_consistency_filters.py](research_yosuga_consistency_filters.py)|研究・候補比較|
|[research_yosuga_daily_time.py](research_yosuga_daily_time.py)|研究・候補比較|
|[research_yosuga_dow_filters.py](research_yosuga_dow_filters.py)|研究・候補比較|
|[research_yosuga_dow_htf_filter.py](research_yosuga_dow_htf_filter.py)|研究・候補比較|
|[research_yosuga_dow_pullback_entry.py](research_yosuga_dow_pullback_entry.py)|研究・候補比較|
|[research_yosuga_dow_rr_breakeven.py](research_yosuga_dow_rr_breakeven.py)|研究・候補比較|
|[research_yosuga_entry_timing_risk.py](research_yosuga_entry_timing_risk.py)|研究・候補比較|
|[research_yosuga_fxneo_continuation.py](research_yosuga_fxneo_continuation.py)|研究・候補比較|
|[research_yosuga_previous_day_break_entry.py](research_yosuga_previous_day_break_entry.py)|研究・候補比較|
|[research_yosuga_regime.py](research_yosuga_regime.py)|研究・候補比較|
|[research_yosuga_structure_switch.py](research_yosuga_structure_switch.py)|研究・候補比較|
|[verify_yosuga_daily_time_20261006.py](verify_yosuga_daily_time_20261006.py)|再検証・照合用|

### YTT：形・判断支援・Pine生成（12本）

|スクリプト|役割|
|---|---|
|[build_ytt_combined_pine.py](build_ytt_combined_pine.py)|Pine生成・加工|
|[build_ytt_entry_band.py](build_ytt_entry_band.py)|Pine生成・加工|
|[build_ytt_watchlist_pine.py](build_ytt_watchlist_pine.py)|Pine生成・加工|
|[research_ytt_jev.py](research_ytt_jev.py)|研究・候補比較|
|[research_ytt_monthly5_fx.py](research_ytt_monthly5_fx.py)|研究・候補比較|
|[research_ytt_profit_feasibility.py](research_ytt_profit_feasibility.py)|研究・候補比較|
|[research_ytt_shape_regime.py](research_ytt_shape_regime.py)|研究・候補比較|
|[simplify_ytt_pine.py](simplify_ytt_pine.py)|Pine加工|
|[verify_ytt_monthly5_fx.py](verify_ytt_monthly5_fx.py)|再検証・照合用|
|[verify_ytt_shape_regime.py](verify_ytt_shape_regime.py)|再検証・照合用|
|[ytt_jev_vision.py](ytt_jev_vision.py)|共通シグナル・補助部品|
|[ytt_jev_vision_app.py](ytt_jev_vision_app.py)|閲覧・判断支援UI|

### 株式・TOPIX・Tamukai（32本）

|スクリプト|役割|
|---|---|
|[diagnose_stock_pullbacks.py](diagnose_stock_pullbacks.py)|診断・原因分析|
|[diagnose_stock_trend_evidence.py](diagnose_stock_trend_evidence.py)|診断・原因分析|
|[export_stock_deep_dashboard.py](export_stock_deep_dashboard.py)|成果物出力|
|[fetch_tamukai_stock_data.py](fetch_tamukai_stock_data.py)|入力取得|
|[judge_stock_research_with_jev.py](judge_stock_research_with_jev.py)|AI判断支援|
|[prepare_topix100_2016_data.py](prepare_topix100_2016_data.py)|入力準備|
|[research_head_shoulders_stocks_daily.py](research_head_shoulders_stocks_daily.py)|研究・候補比較|
|[research_head_shoulders_stocks_relaxed.py](research_head_shoulders_stocks_relaxed.py)|研究・候補比較|
|[research_head_shoulders_stocks_relaxed2.py](research_head_shoulders_stocks_relaxed2.py)|研究・候補比較|
|[research_stock_cash_long_horizon.py](research_stock_cash_long_horizon.py)|研究・候補比較|
|[research_stock_crash_rebound.py](research_stock_crash_rebound.py)|研究・候補比較|
|[research_stock_rebound_atr_risk.py](research_stock_rebound_atr_risk.py)|研究・候補比較|
|[research_stock_rebound_regime.py](research_stock_rebound_regime.py)|研究・候補比較|
|[research_stock_relative_strength.py](research_stock_relative_strength.py)|研究・候補比較|
|[research_stock_specific.py](research_stock_specific.py)|研究・候補比較|
|[research_stock_trend_continuation.py](research_stock_trend_continuation.py)|研究・候補比較|
|[research_stock_trend_external.py](research_stock_trend_external.py)|研究・候補比較|
|[research_stock_trend_topix100.py](research_stock_trend_topix100.py)|研究・候補比較|
|[research_tamukai_stocks_daily.py](research_tamukai_stocks_daily.py)|研究・候補比較|
|[research_tamukai_stocks_deep.py](research_tamukai_stocks_deep.py)|研究・候補比較|
|[research_tamukai_stocks_jev.py](research_tamukai_stocks_jev.py)|研究・候補比較|
|[stock_dashboard.py](stock_dashboard.py)|閲覧・判断支援UI|
|[stock_data_cache.py](stock_data_cache.py)|保存データの取得・整合確認|
|[validate_stock_cash_long_horizon.py](validate_stock_cash_long_horizon.py)|独立検証用|
|[validate_stock_crash_rebound.py](validate_stock_crash_rebound.py)|独立検証用|
|[validate_stock_rebound_atr_risk.py](validate_stock_rebound_atr_risk.py)|独立検証用|
|[validate_stock_rebound_regime.py](validate_stock_rebound_regime.py)|独立検証用|
|[validate_stock_relative_strength.py](validate_stock_relative_strength.py)|独立検証用|
|[validate_stock_specific.py](validate_stock_specific.py)|独立検証用|
|[validate_stock_trend_continuation.py](validate_stock_trend_continuation.py)|独立検証用|
|[validate_stock_trend_external.py](validate_stock_trend_external.py)|独立検証用|
|[validate_stock_trend_topix100.py](validate_stock_trend_topix100.py)|独立検証用|

### Sniper：時間足・出口・損失分析（10本）

|スクリプト|役割|
|---|---|
|[report_sniper_losses.py](report_sniper_losses.py)|結果レポート生成|
|[research_sniper_daytrade.py](research_sniper_daytrade.py)|研究・候補比較|
|[research_sniper_defense.py](research_sniper_defense.py)|研究・候補比較|
|[research_sniper_exits.py](research_sniper_exits.py)|研究・候補比較|
|[research_sniper_losses.py](research_sniper_losses.py)|研究・候補比較|
|[research_sniper_purple.py](research_sniper_purple.py)|研究・候補比較|
|[research_sniper_rates.py](research_sniper_rates.py)|研究・候補比較|
|[research_sniper_single.py](research_sniper_single.py)|研究・候補比較|
|[research_sniper_timeframes.py](research_sniper_timeframes.py)|研究・候補比較|
|[research_sniper_vip.py](research_sniper_vip.py)|研究・候補比較|

### Quant70：日中足・通貨条件（9本）

|スクリプト|役割|
|---|---|
|[quant70_intraday_signals.py](quant70_intraday_signals.py)|共通シグナル・補助部品|
|[quant70_signals.py](quant70_signals.py)|共通シグナル・補助部品|
|[research_quant70.py](research_quant70.py)|研究・候補比較|
|[research_quant70_intraday.py](research_quant70_intraday.py)|研究・候補比較|
|[research_quant70_intraday_jpy.py](research_quant70_intraday_jpy.py)|研究・候補比較|
|[revalidate_quant70_jpy.py](revalidate_quant70_jpy.py)|再検証・照合用|
|[verify_quant70_intraday_jpy.py](verify_quant70_intraday_jpy.py)|再検証・照合用|
|[verify_quant70_intraday_results.py](verify_quant70_intraday_results.py)|再検証・照合用|
|[verify_quant70_results.py](verify_quant70_results.py)|再検証・照合用|

### 金・XAUUSD：PF・注文・損失分析（7本）

|スクリプト|役割|
|---|---|
|[optimize_xauusd.py](optimize_xauusd.py)|条件探索|
|[report_gold_pf_refinement.py](report_gold_pf_refinement.py)|結果レポート生成|
|[research_gold_limit_orders.py](research_gold_limit_orders.py)|研究・候補比較|
|[research_gold_losses.py](research_gold_losses.py)|研究・候補比較|
|[research_gold_minute_execution.py](research_gold_minute_execution.py)|研究・候補比較|
|[research_gold_pf.py](research_gold_pf.py)|研究・候補比較|
|[research_gold_pf_refinement.py](research_gold_pf_refinement.py)|研究・候補比較|

### 円通貨・USDJPY：個別比較（7本）

|スクリプト|役割|
|---|---|
|[optimize_jpy_crosses.py](optimize_jpy_crosses.py)|条件探索|
|[optimize_usdjpy.py](optimize_usdjpy.py)|条件探索|
|[research_ema50_usdjpy.py](research_ema50_usdjpy.py)|研究・候補比較|
|[research_jpy_pf15.py](research_jpy_pf15.py)|研究・候補比較|
|[research_jpy_recent3m.py](research_jpy_recent3m.py)|研究・候補比較|
|[verify_jpy_pf15.py](verify_jpy_pf15.py)|再検証・照合用|
|[verify_jpy_recent3m.py](verify_jpy_recent3m.py)|再検証・照合用|

### 機械学習・固定RR・Pine補助（10本）

|スクリプト|役割|
|---|---|
|[export_compact_entry_pine.py](export_compact_entry_pine.py)|成果物出力|
|[quant_rr_execution.py](quant_rr_execution.py)|共通シグナル・補助部品|
|[research_compact_pine_ml.py](research_compact_pine_ml.py)|研究・候補比較|
|[research_ml_strict_rr.py](research_ml_strict_rr.py)|研究・候補比較|
|[research_pine_vote_entry.py](research_pine_vote_entry.py)|研究・候補比較|
|[research_simple_rr13_15.py](research_simple_rr13_15.py)|研究・候補比較|
|[research_strict_rr_portfolio.py](research_strict_rr_portfolio.py)|研究・候補比較|
|[simple_rr_signals.py](simple_rr_signals.py)|共通シグナル・補助部品|
|[verify_simple_rr13_15.py](verify_simple_rr13_15.py)|再検証・照合用|
|[verify_strict_rr_ml_candidate.py](verify_strict_rr_ml_candidate.py)|再検証・照合用|

### その他の形・日足・市場環境・共通補助（36本）

|スクリプト|役割|
|---|---|
|[audit_bari_video_20261016.py](audit_bari_video_20261016.py)|監査用|
|[data_gap_fill_m5_ledger.py](data_gap_fill_m5_ledger.py)|データ台帳|
|[export_market_atlas_site.py](export_market_atlas_site.py)|成果物出力|
|[index_seasonality.py](index_seasonality.py)|季節性分析・表示|
|[render_logic_comparison_video.py](render_logic_comparison_video.py)|表示物生成|
|[research_4h_wall_breakout.py](research_4h_wall_breakout.py)|研究・候補比較|
|[research_4h_wall_retest.py](research_4h_wall_retest.py)|研究・候補比較|
|[research_alternative_logics.py](research_alternative_logics.py)|研究・候補比較|
|[research_bari_video_20261016.py](research_bari_video_20261016.py)|研究・候補比較|
|[research_btc_spot_rr1.py](research_btc_spot_rr1.py)|研究・候補比較|
|[research_classic_chart_patterns.py](research_classic_chart_patterns.py)|研究・候補比較|
|[research_daily_adaptive_pullback.py](research_daily_adaptive_pullback.py)|研究・候補比較|
|[research_daily_edge_reset.py](research_daily_edge_reset.py)|研究・候補比較|
|[research_dinapoli_3x3_daily.py](research_dinapoli_3x3_daily.py)|研究・候補比較|
|[research_dinapoli_3x3_daily_dow_exit.py](research_dinapoli_3x3_daily_dow_exit.py)|研究・候補比較|
|[research_estimated_tenzoko.py](research_estimated_tenzoko.py)|研究・候補比較|
|[research_flag_patterns.py](research_flag_patterns.py)|研究・候補比較|
|[research_fx_regime_event.py](research_fx_regime_event.py)|研究・候補比較|
|[research_fx_regime_switch.py](research_fx_regime_switch.py)|研究・候補比較|
|[research_fxspace_m5_20261011.py](research_fxspace_m5_20261011.py)|研究・候補比較|
|[research_fxspace_proxy_20261011.py](research_fxspace_proxy_20261011.py)|研究・候補比較|
|[research_gap_fill_m5.py](research_gap_fill_m5.py)|研究・候補比較|
|[research_geometric_chart_patterns.py](research_geometric_chart_patterns.py)|研究・候補比較|
|[research_head_shoulders.py](research_head_shoulders.py)|研究・候補比較|
|[research_head_shoulders_forex_daily.py](research_head_shoulders_forex_daily.py)|研究・候補比較|
|[research_holy_grail_first_pullback.py](research_holy_grail_first_pullback.py)|研究・候補比較|
|[research_intermarket_trend_filters.py](research_intermarket_trend_filters.py)|研究・候補比較|
|[research_new_logic_20261011.py](research_new_logic_20261011.py)|研究・候補比較|
|[research_pattern_market_environments.py](research_pattern_market_environments.py)|研究・候補比較|
|[research_textbook_retest_shapes.py](research_textbook_retest_shapes.py)|研究・候補比較|
|[research_triple_chart_patterns.py](research_triple_chart_patterns.py)|研究・候補比較|
|[validate_bari_video_20261016.py](validate_bari_video_20261016.py)|独立検証用|
|[validate_fxspace_m5_20261011.py](validate_fxspace_m5_20261011.py)|独立検証用|
|[validate_fxspace_proxy_20261011.py](validate_fxspace_proxy_20261011.py)|独立検証用|
|[validate_gap_fill_m5.py](validate_gap_fill_m5.py)|独立検証用|
|[validate_new_logic_20261011.py](validate_new_logic_20261011.py)|独立検証用|
