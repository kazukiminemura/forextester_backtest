# よすが式チャンネル再構築：品質監査

担当 quant_auditor。2026-10-03。最終判定 `VERIFIED_REJECTED_LIMITED_APPROXIMATION`。研究者・独立検証担当とは別担当で監査する。所有変更は本書と `agent_runs/yosuga_channel_20261003/audit/` のみ。

**引渡し可**：固定した3つの派生モデルについて、観測OHLCと明示した費用モデルによる不採用結果を渡せる。本人手法全体の優位性は、再現範囲と未使用評価の不足により判定保留。原典全体の否定・完全再現・研究合格・Pine出力済み・TradingView実機確認済み・実運用承認とは扱わない。

## 結果前監査

`charter.md`、本実験の出典台帳・`source_rules.json`・データ台帳・独立検証の事前確認、親統合文書を確認した。開発中初版を読んだが、その段階にはprotocol/hypothesis/テストが未完成で実走もしていない。初版と予定仕様の差を最終実装の欠陥とは扱わない。

この節は結果前の審査履歴。コード・仕様・入力の固定識別子、実走終了、独立再現証拠を照合するまで成績の正当性・優位性を承認しない方針で進めた。

最終案ready通知後、`protocol.json`、`hypothesis.md`、runner全体、11件の動作テストを再照合した。結果前の仕様固定へ進行可能。左右2本厳密pivot・右2本確定、同時高安pivot除外、初回crossで方向初期化、後の逆crossだけ転換、M15三本かつM1充足、ギャップreset、36本setup、96本line、転換後HL/LH、1tick内外、signal時とentry時の余地審査、翌open、保有中不完全足保持、SL優先、opening gapと逆転換marketの順序、期末全決済、metadata費用、等R・共通月bootstrap・7個のscreen条件は記載と整合する。監査担当実行 `python -m pytest tests/test_yosuga_channel.py -q` は **11 passed、exit 0**。実データ全再生の証明は独立検証待ち。

候補を共有するexit比較でも保有長によりoccupied除外が変わるため、約定集団は一致しない点はprotocolとhypothesisに明記済み。採否gateは両後期区分について件数100・PF_R1.10・平均netR正・共通月95%CI下限正・黒字通貨4/7・各一通貨除外netR正・1.5倍費用netR正。DDは報告指標で採用閾値ではない。既閲覧期間の記述的screenで実運用採用判定ではない。

結果前の追加所見 **P2（表記）**：`incomplete_m5_held` は存在するが内部M1が不足するM5だけを数える。丸ごと欠けたM5時間帯・週末gapの暴露件数ではない。次に観測したopenでgap約定は行うが、空白内の実経路は不明。protocolの欠損flag説明をこの範囲へ正確化するよう責任者へ通知した。パラメータ・成績を変える要求ではない。

**凍結確認**：上記P2表記は凍結protocolで修正済み。M1端点のOLE浮動小数誤差を1秒guard取得後の整数秒filterで処理する修正と回帰テストが成績閲覧前に追加された。最終12件を監査担当も再実行して **12 passed、exit 0**。`audit/freeze_hash_audit.json` で凍結protocolと6入力識別子の現物一致を確認。protocol SHA256 `1b243ff3d5704a72614b11daf9750e7821ac79c6f81f7593b43eab313d4050a1`、code `3cba558ad04c235e8517817eeea79c0af310bf284d1832113ae0dae0e1d915d8`、tests `3e511e3e3c28294868f3c7e80e07723decfbfad9c633bc40837b12bde0dc3ab7`。戦略結果に基づく条件変更はこの時点で確認されない。

## 原典と判断範囲

- **P1・適用範囲の制約**：研究対象は2022年基準のM15/M5順行・水平線・転換後押し目の数値化。2024年初動の建値なしを参照する。チャネル、上位足の全体認識、時間足選択、ライン削除・統合、逆行型、裁量的PAは未再現で、原典手法全体の肯定・否定へ一般化できない。現出典台帳・統合文書はこの制約を明記している。
- **P1・未使用評価なし**：2020–2025は既閲覧。期間分割は記述的な頑健性評価で、未使用holdoutとは呼べない。PASSでも実運用承認にはならない。
- **P2・費用と履歴の制約**：OHLCのBid/Askと時計基準、歴史的spread・滑り・swapは未確定。metadata spread/1.5倍と1pip/day感度は仮定であり実約定の再現ではない。異なる決済通貨は等R研究スコアで評価する。
- **P2・原典証拠の限界**：後年4動画は自動字幕中心で全図版を視認した証拠ではない。2022年PDFの62/71/76%はスイング到達率であり、今回の費用後取引勝率として使えない。

## 証拠確認

現source manifestを監査担当が再hashした結果は `agent_runs/yosuga_channel_20261003/audit/source_hash_audit.json`。初期の独立検証hashにはレンダリング更新前のPNG不一致が残るため、最終manifestとの一致を用いる。元PDFの同一性と図版生成時の更新は区別する。

## 実走・独立証拠の最終照合

`completed/run_manifest.json` の開始12:08:28 UTCはprotocol凍結21:08:11 JSTより後で、完了は12:09:30 UTC。protocol・code・testsのSHAは凍結時と一致。実走results SHA256は `b87da4a0a616301c9d68ee7e36d5ed58c35e05f5ff4cd0a6eb85ece1cff2ffa2`。実走exit 0は研究担当/責任者から受領し、完成manifest・results・126ケースを現物確認した。

監査担当が126ケースの1,908明細を読み、件数、netR合計、通貨別spread×倍率、各取引の `(gross_pips-cost_pips)/risk_pips` を再計算して一致。`audit/result_accounting_audit.json` へ保存した。実走後に条件や採否gateを変えた形跡は確認されない。

独立検証 `independent/verification.json` は **ALL_MATCH**。検証担当のexit 0報告を受領した。`verify.py` は戦略runnerをimportせず、原M1時刻の存在検索、別のM15時刻集約、ベクトルpivot抽出、方針別状態遷移、取引ごとのexit再生、MTM差分イベント合算、月weightによるbootstrapで照合している。確認数は7通貨、3,182,106 M5、1,019,022 M15、998候補signal、126ケース、1,908取引観測、18,834,138個別MTM行、18合算系列。signal/取引件数には3方式/2費用条件による重複を含む。

監査担当は検証scriptのSHA、結果ファイルのSHA、両結果のcases/totals/screensの3,960数値をさらに照合して一致した。比較許容は相対1e-10・絶対1e-9。証拠 `audit/independent_evidence_audit.json`。検証script SHA256 `e63d48914175388130558277c73cecece634d030882574d833c8520020f0837d`、verification SHA256 `f343a821b96b3e01426a9e5e2fa5bad74c224ba4d24dfe9ad87aa16cc1c26107`。

|監査項目|実装識別子|確認結果|
|---|---|---|
|確定足・高安遅延・M1充足|`m1_completeness` / `aggregate_m15` / `structure`|動作テストと独立全再生一致|
|原典と補完条件・候補消費|`signals` / `candidate`、protocol `structural_rules`|3方針固定、将来のpivot極値への遡及約定なし|
|翌open・gap・両到達・期末|`simulate` / `exit_fill`|gapは観測open、同足SL優先、逆転換market順序と期末決済一致|
|費用・通貨単位・保有罰則|`trade_metrics` / `simulate`|各spread控除、等R、swap感度別計算一致|
|MTM/DD・通貨横断・CI/gate|`combine_curves` / `bootstrap_months` / `run`|別実装一致、全3screen不通過|
|Pine対応表・実機確認|該当成果物なし|今回未移植。採用条件通過0のため不採用結果のみ引渡し|

## 経済判断と残る所見

通常費用の主モデルは2020–22が139件・PF_R0.576・−38.567R、2023–24が94件・PF_R0.670・−17.276R、2025が45件・PF_R0.390・−20.639R。補助・比較を含む全方式/全期間で通常費用後netRは負、1.5倍費用でも負。3方式とも両後期区分の固定screenを満たさない。2023–24の主モデル勝率55.32%を優位性の根拠にしない。費用前+9.742Rに対して費用27.018Rが発生している。

上記P1/P2制約は残るが、限定した不採用報告を阻害する未解決の実装欠陥は見つからなかった。推定利益の承認や本人全手法への一般化を阻止する制約として保持する。固定pivot/36本/96本の感度、tick/BidAsk/実際のswap、欠損内の価格経路、原典未再現部分、真の未使用データ、TradingView実機は未確認。親統合報告の数値と「限定派生3方式は不採用、本人全体は判定保留」の結論は証拠に整合する。

実走後の文書確認で `validation.md` の冒頭がPRE_RUNのままだったため、完了状態表示のP2として責任者へ更新を依頼し、最終版 `VERIFIED_REJECTED_DESCRIPTIVE_DATA_LIMITED` への更新と数値表を再確認した。**解消済み**。同文書は検証側初回assert失敗も記録している。保存protocolの再シリアライズによるbyte差を、元protocolのmanifest SHAと保存JSONの意味一致で検査する修正であり、戦略・成績・gateの事後変更ではない。

独立担当の追加診断では、通常費用で丸ごと欠けたM5間隔を保有して跨いだ取引が主4件・次ライン2件・転換直後8件と報告されている。主/次ラインの最小初期SL1.6pipに対し比較方式は0.1pipで、最大費用/riskは0.875R/14R。微小stopに対する費用集中を無視できない。この診断を根拠に閾値を後付けしておらず、限定的な不採用判定を維持している。

## 引継ぎ

入力：source/data/protocol/hypothesis、凍結runner/tests、completed全結果、独立verify.py/verification.json、親統合報告。出力：本書、audit配下のsource/freeze/result/independent各JSON。監査側のhash/会計/独立結果照合はPythonで実行し全exit 0、最終動作テスト12 passed。研究担当と独立検証担当から各本実走exit 0を受領。次担当は研究責任者。限定不採用結果と上記未確認範囲を併記して引き渡す。
