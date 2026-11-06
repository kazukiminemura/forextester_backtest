# 研究・検証結果・Pineの総合入口

このガイドはローカル作業フォルダー全体の索引です。未コミットの研究やGit管理対象外の`agent_runs/`も掲載しているため、一部リンクはローカル環境専用です。今回の整理コミットは索引・README・除外設定と重複モデル削除に限定しています。

目的別に次の一覧から探せます。再現性のため、研究スクリプトと凍結された結果の元パスは維持しています。

| 探すもの | 入口 | 保存場所 |
|---|---|---|
| Python研究・バックテスト・独立検証 | [研究スクリプト一覧](../scripts/README.md) | `scripts/` |
| 仕様・結果・監査・取引明細 | [研究結果一覧](research_results.md) | `docs/quant_organization/experiments/` と `agent_runs/` |
| TradingViewへ貼り付けるPine | [Pine一覧](../scripts/tradingview/CATALOG.md) | `scripts/tradingview/` |
| 研究の進捗・判定 | [作業台帳](quant_organization/board.md) | `docs/quant_organization/` |
| 今回の削除・移動・確認内容 | [整理記録](repository_cleanup_20261106.md) | 2026-11-06の整理 |

## この会話のPatrick手法

- **現在のPine**：[patrick_vp_jst_weekly_indicator.pine](../scripts/tradingview/patrick_vp_jst_weekly_indicator.pine)。H4_7D、全通貨、08:00日本判定、既存08:15仮想約定。今日/保有中と過去の表示・個別切替付き。
- **現在の仕様**：[H4_7D対応表](quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/pine_h4_week_mapping.md)、[今日/過去の表示検証](quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/pine_today_history_validation.md)。標準Strategy Testerではなく独自仮想集計です。
- **旧Python研究**：[初版](quant_organization/experiments/patrick_vp_jst_20261106/report.md) → [レンジ緩和](quant_organization/experiments/patrick_vp_jst_range2_20261106/report.md) → [週頻度研究](quant_organization/experiments/patrick_vp_jst_weekly_20261106/report.md) → [E24_OFF](quant_organization/experiments/patrick_vp_jst_weekly_expiry_20261106/report.md)。比較・不採用の記録を保存しています。
- **判定の区別**：旧E24_OFFの頻度・損益を現行H4_7Dへ流用しません。現行条件の収益性・全通貨の頻度は未検証です。

## 保存ルール

1. 原データ・取得manifest・SHA・凍結仕様・取引台帳・監査・不採用結果は保持します。
2. `scripts/`の研究コードと`agent_runs/`の生成結果を区別し、再現時は元パスを使います。類似名だけでは削除しません。
3. 単発の手動CSV出力は`agent_runs/manual_exports/`へ保存します。過去のルートCSVは`agent_runs/legacy_root_exports_20261106/`です。
4. `__pycache__`・pytest/ruffキャッシュと、終了済みのUI搬送helperは再現の入力ではありません。今回削除した対象と根拠は整理記録に残しています。

株価スナップショットの扱いは[data/stocks/README.md](../data/stocks/README.md)、研究の担当・引継ぎは[運営規約](quant_organization/charter.md)を参照してください。
