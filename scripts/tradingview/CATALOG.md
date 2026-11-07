# Pine用途別カタログ

この一覧にはローカルの未コミットPine・研究資料も含みます。一部のリンク先はGitHubでは未公開です。今回の整理コミットは索引と重複モデルの削除に限定し、Pine本体の変更は含めていません。

2026-11-06棚卸し。**Pine本体36本（indicator31・strategy5）**を、用途と派生関係で案内する。「入口」はファイルを見つけるための区分であり、利益・実運用の合格を意味しない。

## 最初に開く：Patrick H4_7D

- [逆方向・推定費用が損切り幅の10%以下](patrick_vp_jst_reverse_cost10_indicator.pine)：追加H4値幅制限なし、元TP・SLの価格を交換。Forex Testerの2017～2019年では通常PF_R 0.946で未採用。[仕様と動作確認](../../docs/quant_organization/experiments/patrick_reverse_cost10_pine_20261107/README.md)

最新の作業入口は [patrick_vp_jst_weekly_indicator.pine](patrick_vp_jst_weekly_indicator.pine)。日本時間08:00判定・08:15仮想約定、過去7暦日内で開始・完了した確定H4形と、前週／前々週のVAH・VALを使う。全通貨対応だが、他通貨の頻度・収益を検証済みとは扱わない。

**研究用の独自M1仮想エンジンを持つindicatorであり、標準Strategy Testerや実注文ではない。新H4_7D条件の経済性は未検証。** 旧E24_OFFの週平均やPFを新版へ転用しない。

- [導入・H4一週間仕様](../../docs/quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/pine_h4_week_mapping.md)
- [独立検証・実機確認範囲](../../docs/quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/pine_h4_week_validation.md)
- [品質監査](../../docs/quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/pine_h4_week_audit.md)

棚卸し時の最新版SHA256は `dc31af681b043540f8566b02f41921ec925a9606b4955b46c54e026b32b2f0f9`。将来改版時は対応する検証記録の識別子も確認する。

## YTT分析・監視：8本

YTT公式内部仕様の完全再現や、採用済み自動売買システムではない。用途の違う表示版・取得予算版を、ファイル名が似ている理由だけで削除しない。

| ファイル | 区分・用途 | 関連資料 |
|---|---|---|
| [yosuga_ytt_entry_band.pine](yosuga_ytt_entry_band.pine) | **参考帯を使う入口**。簡略統合版にエントリー参考帯を追加 | [参考帯の仕様・実機確認範囲](../../docs/ytt_entry_band_20261013.md) |
| [yosuga_ytt_compact.pine](yosuga_ytt_compact.pine) | **簡略統合版の入口**。入力・描画・判定を保った簡略化成果物 | [簡略化と検証](../../docs/ytt_compact_20261011.md) |
| [yosuga_ytt_watchlist_unified.pine](yosuga_ytt_watchlist_unified.pine) | 18銘柄統合。監視範囲A9/B9/全18を選ぶ取得上限ガード付き | [監視範囲・プラン上限](../../docs/yosuga_ytt_watchlist.md) |
| [yosuga_ytt_watchlist_a.pine](yosuga_ytt_watchlist_a.pine) | **A/B分割運用のA**。価格描画と前半9銘柄 | [A/Bを使う理由](../../docs/yosuga_ytt_watchlist.md) |
| [yosuga_ytt_watchlist_b.pine](yosuga_ytt_watchlist_b.pine) | **A/B分割運用のB**。後半9銘柄一覧。単体で価格描画を持たない | [A/Bを使う理由](../../docs/yosuga_ytt_watchlist.md) |
| [yosuga_ytt_combined.pine](yosuga_ytt_combined.pine) | 高安・チャネル・監視・BB反転の統合系。派生元として保持 | [統合版の導入](../../docs/yosuga_ytt_combined.md) |
| [yosuga_ytt_assistant.pine](yosuga_ytt_assistant.pine) | 分析補助単体。高安・チャネル・手動価格・理論数量 | [分析補助](../../docs/yosuga_ytt_assistant.md) |
| [yosuga_ytt_fx_scanner.pine](yosuga_ytt_fx_scanner.pine) | 候補一覧単体。高安・チャネルは描画しない | [専用スキャナー](../../docs/yosuga_ytt_fx_scanner.md) |

生成関係：`build_ytt_combined_pine.py`は統合版、`build_ytt_watchlist_pine.py`はA/B/統合監視版、`simplify_ytt_pine.py`は簡略版、`build_ytt_entry_band.py`は参考帯版を生成する。A/Bのファイル名は動的生成されるため、固定文字列の参照件数が0でも未使用とは限らない。全18同時監視とA/B分割は取得上限が異なるため、導入資料に従う。

## よすが・田向・相場の壁：7本

| ファイル | 用途・保持理由 | 関連資料 |
|---|---|---|
| [tamukai_pair_signal_indicator.pine](tamukai_pair_signal_indicator.pine) | 田向式のペア別押し目レンジ・15分RR1。旧来の導入入口 | [既存導入・表示説明](README.md#追加方法) |
| [yosuga_15m_4h_trade_journal.pine](yosuga_15m_4h_trade_journal.pine) | 確定4H方向と15分エントリー・取引評価。研究用 | [仕様・不採用の扱い](../../docs/yosuga_15m_4h_trade_journal.md) |
| [yosuga_4h_1h_acceleration_channel.pine](yosuga_4h_1h_acceleration_channel.pine) | 4H/1Hの方向・加速減速・平行チャネル・優先順位を表示 | [表示・制約](README.md#よすが式-4h1h-加速減速平行チャネル) |
| [yosuga_5m_rebuilt_indicator.pine](yosuga_5m_rebuilt_indicator.pine) | 4H/15m/5mの再構築版。別時間足の研究派生 | [再構築仕様](../../docs/yosuga_5m_rebuild.md) |
| [yosuga_dow_expectancy_indicator.pine](yosuga_dow_expectancy_indicator.pine) | Pine v5のMTF・期待値表示系。別モデル/表示履歴として保持 | [役割・研究との区別](../../docs/quant_organization/experiments/yosuga_regime_20261031/implementation_review.md) |
| [yosuga_tamukai_pullback_research.pine](yosuga_tamukai_pullback_research.pine) | Pine v5のYosuga×Tamukai押し目研究。研究用の別条件 | [既存系統の区別](../../docs/quant_organization/experiments/yosuga_regime_20261031/implementation_review.md) |
| [market_wall_4h_channel_15m.pine](market_wall_4h_channel_15m.pine) | 4Hの壁・チャネルと15分RR1を組み合わせた別表示系 | [既存説明](README.md) |

これらは同一コードのコピーではない。時間足、状態判定、表示、仮想取引の定義が異なるため、どれか1本だけ残す整理は行わない。

## 2026固定ML：Pine2本・モデル正本2件

| ファイル | 用途 | 関連資料 |
|---|---|---|
| [strict_rr_ml_15m_strategy_2026.pine](strict_rr_ml_15m_strategy_2026.pine) | **4H整合付き共有MLの入口**。名前にstrategyとあるが実体はindicator | [4H共有ML仕様](../../docs/strict_rr_ml_4h_strategy.md) |
| [shared_feature_entry_logic.pine](shared_feature_entry_logic.pine) | 固定11通貨のコンパクトML候補表示・仮想RR1集計 | [既存コンパクトML説明](README.md#コンパクトmlエントリー) |
| [compact_ml_4h_model_2026.json](compact_ml_4h_model_2026.json) | 4H整合あり・しきい値0.485のモデル設定正本。複数の凍結protocolが参照 | [固定モデル研究のprotocol](../../docs/quant_organization/experiments/pf15_compact_ml_extension_20261103/protocol.json) |
| [compact_ml_model_2026.json](compact_ml_model_2026.json) | しきい値0.487、4H整合フラグなしの別設定。exporterの既定出力 | [生成コード](../export_compact_entry_pine.py) |

両モデル設定は完全重複ではない。モデル年2026を永久に使える仕様と解釈せず、資料の適用年・配信元・対象通貨・検証範囲を確認する。

旧名`strict_rr_ml_model_2026.json`は`compact_ml_4h_model_2026.json`と57475bytes・SHA256 `a7a8b7441623d8ff7e4c8f39b33869552b1458f2ea213ae17b4da95164a8e4ab`で完全一致する重複。正本への入口を上記2件に統一し、未参照の旧名は今回削除した。既存protocolが参照する`compact_ml_4h_model_2026.json`は保持する。

## ボリンジャー±3σ：4本

| ファイル | 用途 | 関連資料 |
|---|---|---|
| [bb3_context_pf_indicator.pine](bb3_context_pf_indicator.pine) | 文脈フィルターと独自PF表示。研究protocolからの参照あり | [既存一覧](README.md)・[中心位置研究](../../docs/quant_organization/experiments/bb3_context_center5_20260909/protocol.json) |
| [bb3_context_setup.pine](bb3_context_setup.pine) | 準備・見送り・裁量候補の表示 | [既存一覧](README.md) |
| [bb3_context_strategy.pine](bb3_context_strategy.pine) | native Strategyでの検証用。indicator版と約定機構が異なる | [既存一覧](README.md) |
| [bb3_reversal_confirmation_indicator.pine](bb3_reversal_confirmation_indicator.pine) | 反転確認・候補表示の研究版 | [BB見直し研究](../../docs/quant_organization/experiments/bb_reconsider_20261001/protocol.json) |

## その他のFX・金・日足：7本

| ファイル | 用途・状態の区別 | 関連資料 |
|---|---|---|
| [gold_breakout55_pf_refined.pine](gold_breakout55_pf_refined.pine) | **金55本突破の固定ルール入口**。実データの利益保証ではない | [売買ロジック](../../docs/gold_breakout55_logic.md)・[既存検証](../../docs/gold_pf_refinement_results.md) |
| [gold_breakout55_pf_candidate.pine](gold_breakout55_pf_candidate.pine) | 同家族の比較研究候補。refinedと別条件なので保持 | [既存検証](../../docs/gold_pf_refinement_results.md) |
| [turtle_trading_strategy.pine](turtle_trading_strategy.pine) | 日足System1/2の独立Strategy。増し玉・実決済集計を持つ | [導入と近似の限界](README.md#タートルトレーディング日足) |
| [sniper_vip_pro_reconstruction.pine](sniper_vip_pro_reconstruction.pine) | Sniper機能再構成・独自ロジック。公式システムの完全再現ではない | [再構成仕様](../../docs/sniper_vip_pro_reconstruction.md) |
| [dominant_wave_entry_indicator.pine](dominant_wave_entry_indicator.pine) | 支配波1-2-3の描画・シグナル。多くの比較研究の参照元 | [仕様照合記録](../../docs/quant_organization/dominant_wave_range_spec_review_20261106.md) |
| [holy_grail_first_pullback_rr1_indicator.pine](holy_grail_first_pullback_rr1_indicator.pine) | 聖杯初押しRR1のindicator研究版。不採用表示を維持 | [indicator対応](../../docs/quant_organization/experiments/holy_grail_first_pullback_20260913/indicator_mapping.md) |
| [holy_grail_first_pullback_rr1_research.pine](holy_grail_first_pullback_rr1_research.pine) | 同仮説のnative Strategy研究版。indicatorとの比較保存 | [Pine移植対応](../../docs/quant_organization/experiments/holy_grail_first_pullback_20260913/pine_mapping.md) |

## 株式・形状可視化：research内7本

`research/`は保管場所の区分であり、「それ以外は採用済み」という意味ではない。

| ファイル | 用途・状態の区別 | 関連資料 |
|---|---|---|
| [head_shoulders_patterns.pine](research/head_shoulders_patterns.pine) | 三尊/逆三尊の形状描画。売買注文の実装ではない | [描画仕様](../../docs/head_shoulders_drawing.md) |
| [head_shoulders_relaxed2_patterns.pine](research/head_shoulders_relaxed2_patterns.pine) | 緩和2研究の形状描画。元の検出条件との比較を保持 | [緩和2Pine仕様](../../docs/head_shoulders_relaxed2_pine.md) |
| [stock_monthly_sma10_indicator.pine](research/stock_monthly_sma10_indicator.pine) | 月次10か月SMAのindicator版。Strategyとは役割が違う | [月次SMA研究用Pine](../../docs/stock_monthly_sma10_pine.md) |
| [stock_monthly_sma10_strategy.pine](research/stock_monthly_sma10_strategy.pine) | 同仮説のnative Strategy下書き。経済性不採用の研究記録を維持 | [仕様・検証範囲](../../docs/stock_monthly_sma10_pine.md) |
| [tamukai_stocks_no_dow_rr1_indicator.pine](research/tamukai_stocks_no_dow_rr1_indicator.pine) | **日本株no_dow研究の現行入口**。日足の仮想Entry/TP/SL表示 | [indicatorへの変更理由](../../docs/tamukai_stocks_no_dow_pine.md) |
| [tamukai_stocks_no_dow_rr1_strategy.pine](research/tamukai_stocks_no_dow_rr1_strategy.pine) | 比較保存。既存資料では配列範囲外の報告があり、使用対象はindicator版 | [旧Strategyの問題と制約](../../docs/tamukai_stocks_no_dow_pine.md) |
| [pf15_us_8k_price_drift_replay.pine](research/pf15_us_8k_price_drift_replay.pine) | **確定済み取引の再生用**。SEC判定や新規シグナルをTVで再実行するものではない | [忠実移植に不足する入力](../../docs/quant_organization/experiments/pf15_us_8k_price_drift_20261104/pine_feasibility.md) |

## 整理時に守ること

1. Pine本体36本に完全一致の重複はない。家族名、同じタイトル、生成物という理由だけで削除しない。
2. model正本、生成スクリプトの入力、既存tests/docsの参照、実験protocol/manifestのSHA証拠を保つ。ファイルを物理移動すると相対パスや封印参照が壊れるため、この整理ではカタログで導線を作る。
3. 比較用・不採用の研究版は「不要」と同一視しない。とくにnative Strategyと独自indicator、実取引の再生と新規判定は別機能。
4. TradingViewでのコンパイル/表示、Pythonとの取引列照合、経済性合格は別の状態。各ファイルの対応資料で確認する。
5. 未参照のように見えるファイルでも、Pineエディタへ手動貼り付ける利用や動的生成先がある。削除は厳密重複・一時生成物の証拠と整理manifestを根拠にする。
