# OpenAI Codex 用 運用指示書（`.codex/AGENTS.md`）

このファイルは、**OpenAI Codex でこのリポジトリを扱うとき**の詳細な運用指示である。
上位規約は リポジトリ直下の [`AGENTS.md`](../AGENTS.md)。矛盾する場合は直下の `AGENTS.md` を優先する。

> 読込に関する注意（2026-10-19 実測）:
> - **DSH（DeepSeek Harness）**: 本ファイルは**ネスト指示として実際に読込まれ、
>   `.codex` 配下の作業に適用される**ことを実測で確認した（セッション中に追加指示として注入された）。
>   ただし適用範囲は `.codex` 配下にスコープされ、リポジトリ全体の作業には及ばない。
> - **OpenAI Codex CLI**: リポジトリ直下の `AGENTS.md` が自動読込の対象である。
>   本ファイルがネスト指示として自動読込されるかは**未確認**（Codexでの実測がない）。
> - したがって、**全作業に効かせたい規約はルート `AGENTS.md` に書き**、
>   本ファイルは Codex 向け運用マニュアル／詳細版として扱う。
>   ルート `AGENTS.md` の「カスタム役割を選べない環境ではTOMLの `developer_instructions` を
>   通常のサブエージェントへ渡す」という委任ルールと併用する。

最終更新: 2026-10-19。

## 1. このプロジェクトの目的

このPCの Forex Tester 6 履歴（`C:\ForexTester6\data\History`）から**新しい売買ロジックを構築し、
独立検証し、事前基準を満たしたものだけを TradingView 用 Pine Script として引き渡す**。
**実口座への自動売買・口座接続・外部公開・常時実行は範囲外**。

## 2. 開発方針（全タスク共通）

1. 実装の前に**計画**を立て、本当にそれが必要かを吟味してから着手する。
2. **SOLID原則**に沿い、戦略判断・データアクセス・約定・集計を分離する。
3. ユーザーが気づいていない点（仕様欠陥・未確認事項・危険な前提）を**先に指摘**する。
4. AI判断を伴う設計では先に [`.agents/skills/typesafe-ai/SKILL.md`](../.agents/skills/typesafe-ai/SKILL.md) を読む。
   ただし**売買条件・価格計算・損益・PFなど明示的なルールと計算は決定的なコードに残す**。
   AIの確率を勝率と同一視せず、採用前に独立した期間・通貨で検証する。
5. スキル導入だけを根拠に、外部APIへの市場データ送信・有料推論・実注文を開始しない。

## 3. クオンツAI組織 — Codex での起動方法

### 3.1 役割と固定モデル

| 役割ID | ポジション | モデル / reasoning |
|---|---|---|
| `quant_director` | 研究責任者・統括（主担当が兼務） | `gpt-6.1-sol` / high |
| `quant_data` | データ品質・台帳 | `gpt-6.1-sol` / high |
| `quant_researcher` | 仮説・Python実装 | `gpt-6.1-sol` / high |
| `quant_validator` | 独立検証（別実装） | `gpt-6.1-sol` / high |
| `quant_auditor` | 品質監査・引渡し判定 | `gpt-6.1-sol` / high |
| `quant_pine` | TradingView移植 | `gpt-6.1-sol` / high |
| `quant_git_publish` | 指定パスのみ commit/push | `gpt-6.1-sol` / medium |

**権限・モデル・課金設定を勝手に変更しない。**

### 3.2 Codex 固有の設定（このPC: CLI 0.144.5）

- 最新資料の `agents.enabled` は**読込エラーになる**ため使わない。
  代わりに `.codex/config.toml` の**明示的な役割登録**（`[agents.quant_*]` と `config_file`）と
  **`max_threads = 3`** を用いる。最新資料のフィールドをそのまま追加しない。
- 設定は `.codex/agents/quant_*.toml`。Codex がプロジェクト設定を読込む際に検出される。
- **既存セッションへのホットリロードは未確認**。役割が見えない場合は
  **新しいセッションでこのプロジェクトを開く**。
- カスタム役割を選べない実行環境では、**該当TOMLの `developer_instructions` を読み、
  通常のサブエージェントへ担当指示として渡す**。
  その場合「カスタム設定の自動読込が確認済み」とは**報告しない**。
- 設定ファイルは**担当の定義であり自動スケジューラではない**。無人常時運転は設定していない。

### 3.3 起動の指示例

> クオンツAI組織で研究を開始。研究責任者がデータ担当と開発担当へ委任し、
> ローカルForex Tester履歴を使う実験計画を固定してから新規戦略を実装・検証してください。
> 独立検証で合格したものだけTradingViewへ移植し、監査結果とともに報告してください。

### 3.4 編成の上限と独立性

- **主担当を含め同時4エージェントまで**（主担当1＋子担当3）。6役は常時起動ではない。
- **開発者 ≠ 検証者 ≠ 監査者**。ロジック開発者に自己承認させない。
- **1ファイルの編集者は1名**。共有ディレクトリで同じ実装を並行編集しない。
- サブエージェントを増やしても**統計的な独立性は増えない**。独立性は「別実装・別期間・別通貨」で確保する。
- 役割境界は**指示による運用上の分離**であり、OSレベルのアクセス制御ではない。

## 4. 工程と状態

```
DATA_READY → SPEC_FROZEN → IMPLEMENTED → VALIDATED / REJECTED
   → PINE_CREATED → TV_VERIFIED / TV_UNVERIFIED → DELIVERED
例外: FAILED（実行エラー） / NEEDS_EVIDENCE（情報不足）
```

- `REJECTED`（不採用）・`FAILED`・`NEEDS_EVIDENCE` を混同しない。**不採用も成果物として保存**。
- **組織構築の完了は、戦略の VALIDATED を意味しない。**
- `TV_UNVERIFIED` を「確認済み」と呼ばない。ローカルの文字列テストは Pine のコンパイル確認ではない。
- 実口座・公開・定期実行はこの工程に含めない。

## 5. 実験前に固定するもの（`protocol.json`）

実験ごとに `docs/quant_organization/experiments/<id>/` を作り、
`hypothesis.md`・`protocol.json`・`validation.md`・`audit.md`（必要なら `results.md`）を残す。
数値結果や明細は `agent_runs/<id>/`（gitignore）に置き、文書から相対参照する。

[`templates/protocol.json`](../docs/quant_organization/templates/protocol.json) を複製し、**nullのまま実走しない**。

- 期待値の源泉、反証条件、最も単純な比較対照
- 通貨・時間足・確定足/上位足の使用・エントリー・**全決済RR1.0**（ユーザーが変えない限り）
- 元データの位置・期間・時刻基準・価格種別・欠損の扱い
- 学習/検証/最終確認期間と**既閲覧状況**（真の未使用かは別に記録）
- 候補数・探索範囲・終了条件（**採用が出るまで無制限に再探索しない**）
- 取引数・コスト後PF・期待値・最大DDなどの**数値ゲート**と通貨横断の判定方法
- スプレッド・手数料・スリッページ・スワップ・口座通貨/資金量・約定順序

### 5.1 ゲートを書くときの必須事項（2026-10-19 の実例から）

`gap_fill_m5_20261019` で、**分母や対象期間を書かなかったため合否が読み方で反転し得る**ことが判明した。次回以降は必ず:

1. **比率ゲートは分母を明記**する（例:「閾値以上の全事象（未決着を含む）を分母とする」）。
2. **通貨別ゲートは対象期間を明記**する（全期間pooled か 期間別か）。
3. **部分バケット等の非一様性の扱いを事前固定**する（除外するか層別するか）。
4. **対照は独立性のあるもの**にする（鏡像の恒等式は独立証拠にならない）。
5. 証拠ディレクトリには**コードSHAと入力SHA**を残し、**現行ファイルとの同一性検査**を工程に入れる。
6. 基準は新規研究の前に責任者が根拠とともに決める。過去の `agents.py` の PF1.2 等を無条件に流用しない。
7. 落ちた戦略を改善するときは**新しい実験ID**を使い、既に見たデータを未使用扱いしない。

## 6. 引継ぎと報告

すべての担当は [`templates/handoff.md`](../docs/quant_organization/templates/handoff.md) の形式で、
**入力識別子・出力場所・実行コマンドと終了コード・検証済み事項・不確実性・次の担当**を報告する。

- 数値は**実ファイルを根拠**にする。記憶や途中ログを現在の実行結果として書かない。
- 責任者が [`board.md`](../docs/quant_organization/board.md) を更新し、依存工程の完了前に次へ渡さない。
- 状態語彙（未検証/不採用/研究合格/実行失敗）を正確に使い、**採用を成果目標にしない**。

## 7. データ

- 主データ源は `C:\ForexTester6\data\History`。`HistoryRepository` を優先し、**元ファイルを書き換えない**。
  外部データで無断代替しない。
- 全件を検査していない場合は**サンプル検査と明記**する。時刻を根拠なくUTC扱いしない。
- 株式研究は保存済みスナップショットを再利用する（`data/stocks/README.md` と manifest を先に確認。
  `python scripts/stock_data_cache.py` で SHA256 を検証）。**毎回再ダウンロードしない**。
- 既閲覧期間と未使用期間を区別し、不明なら「未使用」と保証しない。

## 8. Git公開（`quant_git_publish`）

- ユーザーが **`git commit and push` を明示したときだけ**動く。PRは作成しない。
- `git status`・対象差分・ブランチ・upstream を確認し、**対象パスを明確にする**。
- 混在ワークツリーでは **`git add -A` を使わず、明示されたパスだけを `git add --` でstage**する。
- `cached name-status` と `cached diff/check` で範囲を検証し、変更に対応するテストを実行して結果を報告する。
- push後は **local HEAD と remote ref のSHA一致**と `git status` を確認し、残った対象外変更を明記する。
- **履歴の書換え・force push・`reset --hard`・対象外ファイルの削除はしない。**
- 対象やブランチが判断できない場合は、確認できる範囲を調べてから**簡潔に質問**する。

## 9. 禁止事項（全役共通）

- 実注文、口座接続、外部公開、常時実行、無人スケジューリングの新規開始
- 有料推論・外部APIへの市場データ送信（ユーザーの明示承認なし）
- 成績を見た後の基準緩和・閾値追加・期間変更・都合の良い分母/期間の選択
- 検証者・監査者による戦略コードや採用基準の書き換え
- 元データ（Forex Tester履歴・保存スナップショット）の上書き

## 10. 実行環境の確認（着手前）

- Python依存は環境ごとに異なる。最初に `python -c "import numpy, numba, pandas"` で確認する。
  失敗した場合の手順は [`../docs/quant_organization/local_environment.md`](../docs/quant_organization/local_environment.md)。
- テストは「変更に対応する範囲」を実行し、**終了コードを報告**する。環境要因の失敗は
  変更起因の失敗と**分けて**報告する。

## 11. 参照

- 上位規約: [`../AGENTS.md`](../AGENTS.md)
- 運営規約: [`../docs/quant_organization/charter.md`](../docs/quant_organization/charter.md)
- 作業台帳: [`../docs/quant_organization/board.md`](../docs/quant_organization/board.md)
- 編成表: [`../docs/quant_organization/organization.md`](../docs/quant_organization/organization.md)
- 役割定義: `agents/quant_*.toml`（このディレクトリ） / 登録: `config.toml`
- 環境: [`../docs/quant_organization/local_environment.md`](../docs/quant_organization/local_environment.md)
