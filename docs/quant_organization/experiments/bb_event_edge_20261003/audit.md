# BBイベント研究・品質監査

2026-10-03。担当は開発者・独立検証者とは別の品質監査担当。カスタム設定の自動読込確認とは扱わず、割り当てられた監査指示および `charter.md` に基づく。監査担当の編集範囲は本書と `data_inventory.md` のみ。

最終状態: **`AUDITED_REJECTED_DESCRIPTIVE`**。計算・独立検証の証拠を照合し、不採用研究として引渡し可。3候補の採用/Pine移植/実運用を承認しない。

## 事前監査

状態: `PREREVIEW_STAGE_A_ACCEPTABLE_PENDING_FINAL_EVIDENCE`。Stage A結果は未閲覧。DRAFT仕様を読み、以下の理由によりStage A凍結を妨げる重大事項なしと主担当へ報告した。

- BB20/3σ・片側touch・12本予約・1/3/6/12本（主6本）の候補数と主評価を固定。
- 起点とcontrol選択は過去/確定情報だけ。controlは13本以上過去、最新1件で、将来の成功/失敗やgapで置き換えない。ATR比較は過去288本中央値と固定比率0.75/1.5。
- 非選択/未対応/欠測を記録し、control再利用を認めて数を表示する。共同月bootstrapは通貨間同時ショックを同じ月内に保つ。
- 中央線の移動と価格の実際の順行を別記し、動く中央線の事後接触を過去に約定可能だった利確として扱わない。
- ±1ATR到達は記述量。gap時の -1/+1 を実現Rと呼ばない。RR1約定評価は条件付きStage Bの別工程。
- 2020–2025既閲覧を明記し、gate不通過でStage Bを行わない。両期間とも固定方式で報告する。

実行前の明確化として、calendar monthをYYYY-MMとすること、source時計bucketを市場セッションと呼ばないこと、moving-contact displacementの算式、部分欠損M1を含むM5の制約を研究担当へ通知した。これは採用閾値変更の要求ではない。

## 解釈上の注意

Stage A gateは平均回帰の追加研究へ進む機械的screenで、費用後収益基準ではない。費用後感応度が負でも統計screenが通る余地はある。中心接触や正の差を、採用可能な売買戦略・独立した因果効果・実運用承認へ昇格しない。

月単位bootstrapは月内のcontrol再利用・同期性を保つが、月をまたぐ系列依存や全ての交絡を解消しない。イベント方向を過去controlへ付ける比較は観測上の比較であり、ランダム化実験ではない。

## Stage A実走後の照合と所見

Stage A実走manifestは開始 `2026-10-03T05:44:52.512981+00:00`、終了 `2026-10-03T05:45:11.034991+00:00`。仕様はその前の主担当/独立検証/品質監査のレビューを経てSPEC_FROZEN。

- protocol SHA256: `2e47941a0d983b3b8921b930cda2f4973331e284836ba307e5462286613444bb`
- 実走Stage A source SHA256: `1ed3fddd5c96a1fa5f5de6ac3fed5c3363654dc8041e8c93cb8a29c698c5afe2`
- tests SHA256: `dd576091a4ec88118662d1ad481acc0f28d01028af40e3d565f383a6d2e30518`
- results SHA256: `da5957cd2420f494c6559e02589bf105add9536ef2d6a754c8a1471024c2b1c4`

上記とsource_manifest SHAを監査担当が再照合。runnerへのStage B追加後は現行runner hashが変わるため、Aの再現コードは `agent_runs/bb_event_edge_20261003/source_stage_a.py` とし、保存snapshotのhashがA実走manifestと一致することを確認した。A results/manifestをB実走用に改変しない。

監査担当のStage A behavior test実行は `python -m pytest tests/test_bb_event_edge.py -q`、7 passed、終了コード0。全ケース独立再計算の証拠は検証担当から受領後に照合する。

### P2: 対照との差は独立した予測力の証明ではない

controlの方向は後に生じたevent方向を引き継ぐ。6本control観測窓がeventのBB20算出窓と重なる例は **31,489 / 53,437（58.93%）**、全6本が算出窓内に含まれる例は31,013件。監査担当が保存indexを別集計した。イベント前の値動きと後の方向付けによりcontrolが負方向へ偏る可能性があり、これを因果効果や独立した前向き売買優位性の証拠と解釈しない。事前仕様違反ではなく、結果後にcontrolやgateは変更しない。

対応するpaired event単体の6本gross平均は2020–2022が+0.19997pip、2023–2025が+0.45968pip。仮定1pip控除の観測感応度は−0.80003/−0.54032pipである。差のCIが正でも経済性の合格ではないという事前の解釈制約を適用する。

## Stage B事前監査

`protocol_stage_b.json` のDRAFTをB損益実走前に読んだ。Stage Aの数値gate通過を前提とした3方式・RR1・全起点台帳・両3年flat book・1/1.2pip・別途固定された進展screenは整合し、実行を妨げる重大事項なし。

実装時はorigin所属期間でsignalsを絞り、2022末起点の遅いconfirmationを次bookへ持ち越さないよう研究担当へ通知した。各armはsignal時中央線をtargetに固定するので、比較は待機とtarget更新を含む政策の差であり、待機時間単独の因果効果とはしない。

## 最終監査

Stage B実走manifestは開始 `2026-10-03T05:49:53.816753+00:00`、終了 `2026-10-03T05:50:39.295469+00:00`。A/B共に研究担当から正常終了コード0の引継ぎを受領し、final result `complete=true`・final timestampを実ファイルで確認した。

|対象|SHA256|
|---|---|
|Stage B protocol|fe630f09a035bb563b43cbb2da91e885774bdcf14a3970bbfc8c0a4573438715|
|Stage B runner|f12c577067fcd9935f8b2eed2fc6aa6c6bffbdcc98e1015a57a248a43b65b002|
|共有約定engine|413de50927bca3090c472894ece2b72db599f108982a11fa7d4dc0b53f6ba16a|
|Stage B tests|f96d854daeef63f5a4dae000d61e76e327cc01ff7ac8d692cbff8b1ce8e00793|
|Stage B results|b6cb8898ea9951b74f33c8e8e71325ff7e0361d9996025ec189bbf358e7503d2|

監査担当が現在ファイルを再hashし、全て実走manifestと一致。Stage A result hashも不変。Stage B追加後のbehavior testsは11 passed・終了コード0。

独立検証担当のA成果物 `verification_result.json` / `verification_secondary.json` / `validation.md` を照合し、56,212起点・対照、5,846,048観測数値、28prefix、3区分のCI/gate、450,695追加項目の一致を確認した。これは独立担当の再現実行結果との照合であり、監査担当自身が全A経路をさらに再実行したとの主張ではない。

監査担当自身はBの84ケース・125,046取引観測について、保存価格からdirectional損益・1/1.2pip控除・R換算・RR1対称幅を別式で再計算し、全件一致を確認した。全起点台帳のID重複なし、no-entryのgross/netゼロ、closed+open合計とsummaryの一致も確認（終了コード0）。同一取引の2コスト条件を含む観測数であり、125,046独立取引とは呼ばない。

Stage Bの全3armは両期間とも費用後赤字、利益通貨0/7、経済screen全不通過。待機価値screenも2比較とも不通過。待機による原点当たり損失縮小だけを正の期待値の発見とは扱わない。最長保有3,474本のためswap未計上などの制約は継承する。

Bの独立全経路検証は終了コード0。`verification_stage_b.json`・`verification_stage_b_totals.json` と最終 `validation.md` を照合した。84ケース、103,300候補、125,046決済観測、337,272起点台帳行、18,834,138個別MTM行、28prefix、12合算MTM、待機差の共同月CIが一致。補足62,619項目は集計PF/勝率/status/費用差/全18年別帰属行などを照合する。検証script hash `95144e3a48e6d1771acad476c8aa666d2d8eeb3cee178eb0f7a0684b37dff26e` と対象results hashの一致も監査担当が確認した。

監査自身の別集計でも12集約のPF_R/勝率/利益通貨数/status/maxhold/open件数および2待機screenが一致した。統合文書 `docs/bb_event_edge_20261003.md` の数値・因果表現・旧Pineとの差を読み、PFを「1回あたり」としない軽微表現を主担当へ伝達し、修正引継ぎを受けた。

### 引渡し判定

- 計算再現性: 確認済み。重大な仕様不一致・未来参照・損益会計漏れの未解決所見なし。
- 研究結論: 全3候補と全2待機価値比較が固定基準不通過。**不採用**を保持。
- P2の対照交絡は報告済みの推論上の制約。結果後の調整で隠さず、統計screen通過を収益性や因果識別に読み替えない。
- 新規実験は別仕様/別IDで検討する。本実験の不採用結果を保存して終了し、今後の条件再探索を本監査から自動開始しない。
- 監査所有成果物: 本書および `data_inventory.md`。次担当: 主研究責任者（台帳と統合報告）。

実注文・有料AI呼出し・外部公開・Git公開: なし。
