# クオンツAI組織 編成表（Organization Chart & Roster）

最終更新: 2026-10-19。目的・規約の本体は [charter.md](charter.md)、作業台帳は [board.md](board.md)、
役割定義は [`.codex/agents/quant_*.toml`](../../.codex/agents/) を参照。本ファイルは**編成（誰が・何を・どこまで）**の一枚物。

## 1. 目的

このPCのForex Tester履歴から**新しい売買ロジックを構築し、独立検証し、基準を満たしたものだけを
TradingView用Pine Scriptとして引き渡す**。実口座への自動売買・外部公開・常時実行は範囲外。

## 2. 組織図

```
                    ユーザー（オーナー）
                          │ 目的・制約・予算
                          ▼
        ┌─────────────────────────────────────────────┐
        │  研究責任者 / 指揮官  quant_director          │  ← 主エージェントが兼務
        │  計画・実験条件の凍結・台帳・統合報告・采配      │
        └───┬─────────┬─────────┬─────────┬───────────┘
            │         │         │         │
   ┌────────▼──┐ ┌────▼─────┐ ┌─▼────────┐ ┌▼──────────┐
   │ quant_data│ │quant_    │ │quant_    │ │quant_     │
   │ データ品質 │ │researcher│ │validator │ │auditor    │
   │ 台帳・指紋 │ │仮説・実装 │ │独立再現   │ │証拠監査    │
   └───────────┘ └──────────┘ └──────────┘ └───────────┘
                                        ┌───────────────┐
   合格時のみ ─────────────────────────▶│ quant_pine    │
                                        │ TradingView移植│
                                        └───────────────┘
   明示依頼時のみ ─────────────────────▶┌───────────────┐
                                        │quant_git_     │
                                        │publish        │
                                        └───────────────┘

   独立性: 開発者 ≠ 検証者 ≠ 監査者（自己承認の禁止）
   同時枠: 主担当を含め最大4エージェント（主担当1＋子担当3）
```

## 3. ベンチ入り（7役）

| # | 役割ID | ポジション | 規定モデル | 主な成果物 | 判断権限 | 編集してよい範囲 |
|---|---|---|---|---|---|---|
| 1 | `quant_director` | 指揮官／研究責任者 | gpt-6.1-sol (high) | `board.md`、統合報告 `docs/<id>.md`、`protocol.json` | 担当割当・工程移動・凍結 | 上記＋自身の計画文書 |
| 2 | `quant_data` | データ品質 | gpt-6.1-sol (high) | `experiments/<id>/data_inventory.md`、入力SHA・ギャップ母集団 | 利用可能性の報告 | 自分の台帳と読取スクリプトのみ |
| 3 | `quant_researcher` | ロジック開発 | gpt-6.1-sol (high) | `hypothesis.md`、`scripts/research_<id>.py`、`tests/test_<id>.py` | 学習範囲内の設計 | 上記3点のみ |
| 4 | `quant_validator` | 独立検証 | gpt-6.1-sol (high) | `validation.md`、別実装 `scripts/validate_<id>.py`、突合JSON | 未検証/不採用/研究合格 | 上記のみ（戦略は書き換えない） |
| 5 | `quant_auditor` | 品質監査 | gpt-6.1-sol (high) | `audit.md`（重大度付き所見・引渡し判定） | 不備による差戻し | 監査文書のみ |
| 6 | `quant_pine` | TradingView移植 | gpt-6.1-sol (high) | `scripts/tradingview/*.pine`、導入手順、仕様対応表 | 凍結仕様の忠実移植 | Pineと手順書のみ |
| 7 | `quant_git_publish` | Git公開（交代専門） | **gpt-6.1-sol (medium)** | 指定パスだけのcommit/push、SHA一致確認 | 対象範囲のstage可否 | リポジトリ操作のみ（`git add -A`禁止） |

**禁止事項（全役共通）**: 実注文・口座接続・外部公開・常時実行・有料推論の新規開始。
検証者と監査者に戦略や基準を書き換えさせない。**採用数を成果目標にしない。**

## 4. 先発オーダーと交代（段階起動）

| 打順 | 担当 | 初回タスク | 完了条件 |
|---|---|---|---|
| 1 | director | 目的・制約の固定、事前ゲートの決定、凍結 | `protocol.json` に `frozen_at` |
| 2 | quant_data | 期間・件数・欠損・時刻基準・入力SHA、母集団 | `data_inventory.md` ＋再現コマンド |
| 3 | quant_researcher | 反証可能な仮説→実装→境界テスト→実走 | `hypothesis.md`・テスト緑・`results` |
| 4 | quant_validator | 研究コード非依存の別実装で再計算・ゲート再判定 | `validation.md`（一致/不一致一覧） |

**交代**: ①検証完了 → **auditor** 起動（引渡し判定）／②研究合格時のみ **pine** 起動（TV実機確認）／
③「git commit and push」明示時のみ **git_publish** 起動。

## 5. 工程と状態語彙

```
DATA_READY → SPEC_FROZEN → IMPLEMENTED → VALIDATED / REJECTED
             → PINE_CREATED → TV_VERIFIED / TV_UNVERIFIED → DELIVERED

例外: FAILED（実行エラー） / NEEDS_EVIDENCE（情報不足）
```

- `REJECTED` と `FAILED` と `NEEDS_EVIDENCE` を混同しない。**不採用も成果物**として保存する。
- 組織構築完了は、戦略の `VALIDATED` を意味しない。
- `TV_UNVERIFIED` を「確認済み」と呼ばない。

## 6. 采配ルール（固定）

1. **実験前に固定**: 仮説・対照・通貨・期間・足・エントリー・出口（既定RR1.0全決済）・費用・候補数・
   数値ゲートを `protocol.json` に書き、nullのまま実走しない。
2. **結果を見て基準を下げない／候補を増やさない**。追加が必要なら**新しい実験ID**。
3. **分母・期間・閾値の「読み方」まで凍結文に書く**（2026-10-19 の `gap_fill_m5_20261019` で
   分母未定義・期間未定義により合否が反転し得ることが判明。charter の申し送りを参照）。
4. **引継ぎは `templates/handoff.md` 形式**（入力識別子・出力場所・実行コマンド・終了コード・不確実性）。
5. **同一ファイルの編集者は1名**。共有ディレクトリで同じ実装を並行編集しない。
6. **証拠にはコードSHAと入力SHAを残す**（証拠ディレクトリのコード同一性検査を含む）。

## 7. 実行環境の現実（DSH / このセッション）

| 項目 | 実態 |
|---|---|
| カスタム役割 | `.codex/agents/*.toml` は自動読込されない → **TOMLの `developer_instructions` を通常サブエージェントへ担当指示として渡す** |
| モデル固定 | 現行指定は全7役 `gpt-6.1-sol`（クオンツ6役high、Git公開medium）。当セッションの主担当も `gpt-6.1-sol` へ切替済み。過去のギャップ研究はユーザー指定の `deepseek-v4.1-flash` で実行した履歴として保持する。設定変更は既存の子セッションへの反映や各役の起動成功を保証しない。 |
| Python実行 | `python` 既定は依存なし。`PYTHONPATH` に Store版サイトパッケージを足す（[local_environment.md](local_environment.md)） |
| テスト | `tmp_path` はsandboxで失敗。`capsys`／インメモリで書く |
| Git公開 | GCMの対話認証は不可 → `gh` のキーリングトークン＋（sandbox下では名前付きパイプ許可）で push |

## 8. 現在の編成状況（2026-10-19）

| 枠 | 担当 | 状態 |
|---|---|---|
| 指揮官 | director（主エージェント） | 稼働 |
| 2番 | quant_data | 完了（台帳・入力SHA・ギャップ13,894件を全件走査で確定） |
| 3番 | quant_researcher | 完了（`hypothesis.md` 159行・実装1,806行・テスト68件緑） |
| 4番 | quant_validator | 完了（別実装・7,293項目一致／不一致0、仕様欠陥4件を指摘） |
| 控え | quant_auditor / quant_pine / quant_git_publish | 待機（未起動。合格なしのためpine/auditorは不要、git_publishは公開時に稼働） |

**直近の試合** `gap_fill_m5_20261019`（週末・休場ギャップの全埋め先行率）:
**REJECTED_AT_STAGE_A**。母集団ゲート通過（X=10pipsで4,443件）、全埋め先行率 pooled 0.5132 が
事前基準0.60に届かず、凍結仕様どおり Stage B（コスト後PF）へ進めず。統合報告 [../gap_fill_m5_20261019.md](../gap_fill_m5_20261019.md)。

## 9. 参照

- 規約: [charter.md](charter.md) ／ 台帳: [board.md](board.md) ／ 環境: [local_environment.md](local_environment.md)
- 役割定義: `.codex/agents/quant_{director,data,researcher,validator,auditor,pine,git_publish}.toml`
- テンプレート: [templates/protocol.json](templates/protocol.json) ／ [templates/handoff.md](templates/handoff.md)
- 初回監査: [organization_audit.md](organization_audit.md) ／ データ初期調査: [data_inventory.md](data_inventory.md)

本表は編成の記録であり、戦略の収益性・Pine動作・実運用を保証しない。
