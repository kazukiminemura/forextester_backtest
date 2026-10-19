# 品質監査

実験ID: `yosuga_daily_time_20261006`。担当: `quant_auditor`。
状態: `AUDITED_REJECTED_DESCRIPTIVE`。不採用研究として引渡し可。研究合格・Pine作成・TradingView実機確認・実運用承認ではない。
編集責任は本書のみ。戦略、基準、旧結果、原データを変更していない。

## 事前仕様レビュー

`charter.md`、`board.md`、本実験の `protocol.json`、`hypothesis.md`、`data_inventory.md`、初期 `validation.md` と途中runnerを照合した。

1. 固定4方式、7通貨、既存M15/M5エントリーと全決済RR1の保持、閾値探索なしが明記されている。前日・直近1時間の方向効率は追加研究仮説で、原典全体の再現とは呼ばない。
2. 日次効率の数式、直前カレンダー日、保存時計00:00境界、品質5条件と日跨ぎ拒否は相互に整合する。前日欠落時に金曜へ置き換えない。許容欠損は完全日保証ではなく、未観測高安の影響が残る。
3. 時間状態は信号足確定までの12本連続・完全M5。費用/初期リスク比を信号終値と実入場始値でそれぞれ判定する。ストレスでは取引母集団・保有競合が変わり得ることを報告する必要がある。
4. 2020–2022だけで最大1方式を選抜し、後期は固定した記述診断とする。全期間既閲覧、真のholdoutなし、選抜なしなら最終確認null。後期の好成績から選び直す設計ではない。
5. 保有中の出口をgateで止めない。既存SL優先・ギャップ始値・期末決済・費用・欠損保有診断を維持する。Pineは合格後の別工程で、今回未作成。

## 事前所見と保留

- **高 / 実走前に解消**: 初回途中runnerは全期間を計算した後に学習選抜していた。完成版はtrain集約直後に `training_selection.json` とSHAを保存し、その後に後期を再生する。実ファイルの保存時刻も学習選抜14:24:23.357 UTC、最初の後期取引ファイル14:24:23.546 UTCの順。`selected=null` と `final_confirmation=null` を確認した。
- **低 / 診断範囲の限定を明記**: protocol `acceptance_gates` の後期screen文言に対し、実装は全方式の後期metricsを保存する一方、後期screenを学習選抜済み方式だけに限定する。今回は選抜0なので `later_descriptive_screens={}`。未選抜方式の後期screenは未作成であり、全案の後期採否を実行済みとは呼ばない。学習不採用・採用0の判定は変わらない。実走後にprotocolや基準を書き換えていない。
- **研究上の制約**: 保存時計のoffset/DST、実測quote側、歴史的spread/slippage/swap、閾値感度、真の未使用評価は未確認。データ担当の21件SHA照合と原Bars stat照合は区別し、今回の原Bars全bytes再検証と呼ばない。

## 実行・証拠照合

監査側で以下を実行した。戦略や検証成績の変更はしていない。

1. `python -m pytest tests/test_yosuga_daily_time.py tests/test_yosuga_channel.py -q`：29件成功、終了コード0。日跨ぎ・週末・品質境界・未来不変性・売り鏡像・entry足complete非参照・保有継続・gap・同足SL優先・期末を含む。
2. protocol、runner、tests、旧runner、旧tests、data manifest、mask manifestの凍結SHAを実ファイルと照合。run manifest/result/selectionのSHAも一致。凍結以降の条件変更は認めない。
3. 168ケース・24集約を読取り、取引からnetR/grossR/pips、ケースから全通貨集計・件数・取引日/観測日・利益通貨数の **672数値** を別計算し一致。終了コード0。
4. 旧baseline **42ケース** の取引JSON・候補ledgerの内容が旧 `pullback_rr1` と完全一致。MTM配列も全要素同一。これは今回監査側で再実行した照合。
5. 独立検証成果物 `agent_runs/yosuga_daily_time_20261006/independent/verification.json` と `synthetic_checks.json` の完了結果を照合。検証器と旧独立referenceの実ファイルSHAも一致。独立担当の実走は168ケース・875取引観測・2,280候補ledger行・7通貨3,182,106 M5・168 prefix・24集約/CI/選抜が `ALL_MATCH`。別の合成96ケースも `ALL_MATCH`。875件は方式・費用間の重複を含む。独立担当による再現と監査側の672数値/42ケース照合を区別する。

再現コマンド：

```powershell
python scripts/research_yosuga_daily_time.py --output agent_runs/yosuga_daily_time_20261006/<fresh-directory>
python scripts/verify_yosuga_daily_time_20261006.py --synthetic
python scripts/verify_yosuga_daily_time_20261006.py
```

本実走は `completed/run_manifest.json` に開始2026-10-06 14:23:37 UTC、完了14:24:41 UTC、168ケースと結果SHAを保存。研究責任者・独立検証担当が終了コード0を確認。監査側は本戦略の全実走を重複起動せず、完了成果物と独立証拠を検査した。

|識別子|SHA256|
|---|---|
|protocol|`817b5a7edf75079fbbf4c5db940de1a2ae128dbcb0b392e7af04f89c3098bb86`|
|runner|`b61c6622a2f7f5414e2a350d1677ffee2dba4760dd5477c11b24e94b636236cd`|
|tests|`589b320d65cfb0c0fd47a391448a112ff81063305f31b516770c795cb18322f9`|
|results|`c9b0b48b36fcd4b81bc86afbe3013e7ef3e4f38da39c8b36149e5c024c1e9cf8`|
|independent verifier|`87b2f2edf3bfa0d0470df98dfe45ec15c064bbf2e4c5f13cfdb66b1027e6b6b9`|

## 結果判定と解釈

学習2020–2022の通常費用では、日次35件/PF_R 0.741、時間状態51件/0.714、併用14件/0.764。3候補とも件数100未満、netR負、全7採用条件不通過。学習選抜0、後期からの選び直し0は事前条件どおり。

2025の併用は3件/PF_R 1.564/+0.634Rだが、1.5倍費用では取引列が2件へ変わり−0.335R。件数不足・既閲覧・学習不採用を覆す証拠ではない。取引を減らすだけの総損失減少を期待値改善とは呼ばない。

休止理由は候補signalに対して最初に該当した理由の集計で、全時刻のoff比率や複数要因の重複件数ではない。`trading_days` は実際に新規約定した日でgate許可日ではない。`observed_days` はM5が1本以上存在する保存時計日（2025合算313日）で、日曜部分日も含み得る。市場営業日や日本時間の営業日数と表示しない。

確定ピボット・M15構造の実装は旧凍結runnerを再利用し、今回baseline全件一致を確認。独立検証の候補は旧独立検証済み信号との照合であり、今回新たに原M1から全pivot/候補を別実装再構築したとは主張しない。

## 引渡し判定

**不採用研究として引渡し可。未解消の重大実装不一致なし。** 日/時間の新規取引gateは実装・境界検証・独立再現済み。採用0を維持し、本実験のPine移植・Pine対応表・TradingView確認は作成対象にならない。既存Pineへ反映済みとも呼ばない。

真の未使用期間、実時差/DST、実測費用、欠損中の価格、閾値感度、原典の裁量全体は未確認。次担当は研究責任者による不採用結果・限界の統合引渡し。実注文・外部公開・実運用承認なし。
