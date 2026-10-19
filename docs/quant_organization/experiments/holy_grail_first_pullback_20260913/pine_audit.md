# 聖杯 研究用Pine 独立品質監査

- 実験ID / 担当 / 次担当: `holy_grail_first_pullback_20260913` / quant_auditor / 研究責任者・Pine担当。
- 監査日: 2026-09-14 JST。
- 状態: `DELIVERABLE_RESEARCH_ONLY / TV_UNVERIFIED`。再監査でPA01の価格表示遅延とPA02の未解決参照は解消。PA03の終了時刻到達足における既存注文約定も対応表へ明記済み。末尾の最終確認を現在の判定とする。
- 権限: 不採用後のユーザー明示依頼による研究用Pine出力の監査。charterの合格戦略用移植と区別する。研究採用・実運用承認を変更しない。
- 編集: この pine_audit.md のみ。戦略、Pine、テスト、対応表、原データへの編集なし。
- 実注文・外部公開・TradingView操作: なし。

## 入力識別子

初回監査時のSHA256：

|入力|SHA256|
|---|---|
|scripts/tradingview/holy_grail_first_pullback_rr1_research.pine|73883fbec5d912ed2760b2f1e886c3890392a36f43ed2ac2c79559aedc79980b|
|tests/test_holy_grail_first_pullback_pine.py|e44cf3feef1cd2d205aa2d5b59d1409cd432df644d99eacfe15e3cdfa7d00364|
|同実験pine_mapping.md|aa4fb734098c173c6868f14e109e1b1ba6f9d4ecd0cb5a89465f47f9bea8c9de|

同実験hypothesis/protocol、凍結Python研究実装、validation、charterも照合。Pythonの不採用判定は `VERIFIED_REJECTED_TRAINING_ONLY`、2019年以降の研究成績未評価を保持する。

## 重大度付き所見

### PA01 — Medium — 約定価格とEntry/TP表示が足確定まで不一致

Pine初回版81–91行はfill callbackで `strategy.position_avg_price` を取得し、実entryからtargetPriceを再計算する。一方193–208行のline/label更新は `if closedDecision` の内側。closedDecisionはfill callbackを明示的に除外するため、リアルタイム足途中のgap約定時には実entryと実TPが変わっても、Entryラベルは注文trigger、TPラベルは仮1Rのまま次の通常確定足計算まで残る。H4では最大4時間近い遅延があり得る。

これはソースの制御フローから確認した不備であり、TradingViewで実際の遅延を観測した結果ではない。注文管理から分離した描画更新をfill callbackでも行い、シグナル状態を二重更新しない構成を推奨する。mappingの「約定後は実約定価格から更新」という説明と表示タイミングを合わせること。

### PA02 — Low — 存在しない比較サンプルへの参照

pine_mapping.md初回版42行は「主担当作成の同ディレクトリの比較サンプルを参照」と記載するが、監査時の `rg --files docs/quant_organization/experiments/holy_grail_first_pullback_20260913` には該当ファイルがない。比較サンプルを保存して具体的なリンクを付けるか、未作成であることを明記する必要がある。

### PA03 — Medium / 開示済み制約 — Python約定との完全一致は不可

対応表はSL側始値での即時注文取消、同足SL優先、entry前SL接触の保守的損失化、有利TP gap上限、研究境界清算を完全再現できないと説明している。配信OHLC/時間帯/mintick、保有日数近似、gross Testerと補助費用後Rも区別されている。これらは開示されたモデル差であり、凍結Pythonと同じPF・勝率になるとの主張は不可。

終了入力によるpending取消も終値計算まで実行されないため、終了時刻に入った足の途中で既存注文が先に約定する場合がある。終了入力を厳密な最終約定時刻と解釈しないこと。現在の名称は「新規停止」であり保有強制清算は実装していない。

### PA04 — Medium / 未確認 — callback順序と描画の実機証拠なし

ポジション/closedtrades差分とvarip lastDecisionBarにより、同じ足のsignal状態を二重更新しない構造は確認できる。ローカルテストはPineコンパイラやbroker emulatorを実行しないため、実際の歴史足・リアルタイム足の全callback順序で毎足の必要な状態遷移が漏れず実行されること、ARM/1st/Setup出力が保持されること、描画rollbackとの整合は未確認。

公式[Execution model](https://www.tradingview.com/pine-script-docs/language/execution-model/)と[Strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/)を2026-09-14に確認。fillによる複数回実行とrollback、varipの保持、broker emulatorの足内推定は実機照合を必要とする根拠になる。静的テスト通過から非リペイント・全取引一致を保証しない。

## 条件対応の確認

|監査項目|確認結果|
|---|---|
|EMA/ADX|EMA20、TR/DMのindex1..14 Wilder seed、ADXのDX14..27 seedを狙った実装。チャート開始が違えばPythonと指標履歴も異なると開示。Pineの実数値実行は未確認|
|episode|ADX30上抜け、DI優勢、終値のEMA側、ADX25未満/DI優勢喪失reset、arm足除外、250足warmupを対応|
|first touch|最初の接触でspentを更新し、その後にaway/終値方向/空きposition判定。無効初回・保有見送りでも消費|
|構造SL|anchor翌足からtouchまでのmin/max、同値極値は最新anchor、touch評価後anchor更新を対応|
|因果性|request.security/pivot/先読み参照なし。確定足でstop注文を生成、process_orders_on_close=false。fill callbackは保有管理に限定|
|注文3足|signal後3観測足の約定機会の後に取消する条件。callback実行順序の実機確認は残る|
|実entry基準RR1|fill callbackの平均約定価格から固定SL距離を計算、targetを同距離に設定。100%決済、部分/追随/建値移動なし|
|決済足|lastExitBarで再発注禁止。episodeと生setupの更新は保有と独立させる設計|
|価格表示|Entry/SL/TPの価格文字列、仮TPと実TPの区別、120注文既定/150注文上限の履歴保持あり。ただし初回版はPA01の更新遅延|
|研究用状態|strategyタイトル・冒頭コメント・右上表で研究用/不採用/TV_UNVERIFIEDを表示。全注文disable_alert=true。口座/webhook連携なし|
|費用表示|Testerは初期設定gross、補助表は等Rの費用後集計。Tester側費用変更は表が自動検出しないと文書開示|

## ローカル実行

監査者が以下を実行：

```powershell
python -m pytest tests/test_holy_grail_first_pullback_pine.py tests/test_holy_grail_first_pullback.py -q
```

結果: **25 passed in 0.18s / exit 0**。内訳は研究19件とPine関連6件。Pine関連は構造文字列、初回権利消費、実entry基準RR1、価格ラベル、費用区別、および別Python実装によるstreaming anchorと凍結Pythonの20×600合成足照合。

Pine実行・コンパイル・チャート表示・TradingView明細再現の証拠ではない。PA01/PA02を検出するテストは初回版にはない。

## 引渡し

初回監査はPA01/PA02を差戻し、PA03/PA04を確認待ちとして残す。修正後も `REJECTED_TRAINING_ONLY / TV_UNVERIFIED` の研究用コードとしてのみ引き渡せる。実機のコンパイル・歴史足/リアルタイムcallback・gap約定後の価格表示・履歴保持の確認が残る。

## 2026-09-14 修正版再監査

主担当からPA01/PA02の修正完了を受け、修正版Pine・テスト・対応表を再読し、同じpytestコマンドを監査者自身が実行した。結果は **27 passed in 0.20s / exit 0**（研究19件＋Pine関連8件）。描画更新経路と参照先存在確認の2テストが追加されている。

|修正版入力|SHA256|
|---|---|
|scripts/tradingview/holy_grail_first_pullback_rr1_research.pine|2360362c8471509372bcf94e6d39f3e89b757f3ba04fb68b06df3454671dcf70|
|tests/test_holy_grail_first_pullback_pine.py|1d8c0a00f5c5effd2d948e2020eea675335c1cca0e2d20fb379abe871d767119|
|同実験pine_mapping.md|549c4e1fd60e77f580f8a3067bb63206fae1f9e583952b244a7e82361d51b3b4|

- **PA01解消（静的確認）**: 描画ブロックは修正版199行からglobal scopeへ移動。fill callbackによるentryPrice/targetPrice更新の後、closedDecisionの真偽に関係なくline/labelへ反映する。描画ブロックにepisode更新・spent更新・新規発注はなく、二重状態更新を追加していない。Pineで実際のリアルタイム表示を観測したという意味ではない。
- **PA02解消**: 対応表の存在しない比較サンプル参照は削除。実在するvalidation.mdと `agent_runs/holy_grail_first_pullback_20260913/completed/h1_first__training__EURUSD__fixed_1p8.json` への手動照合案内に置換され、監査者も両ファイルの存在を確認した。
- **凍結Pythonへの影響なし**: completed/code_input_hashes.jsonの8ファイルをGet-FileHashで再計算し、全一致（終了コード0）。研究戦略・条件・結果の凍結を維持している。
- **PA03に残る文書差**: 対応表は終了入力の新規停止・未約定取消と保有継続を説明しているが、終了時刻到達足の途中で既存pendingが先に約定し得ることは明記していない。初回監査の指摘は現行コードにも当てはまる。終了入力を厳密な最終約定時刻と誤読しないよう明記を依頼済み。
- **PA04継続**: callback順序・rollback・コンパイル・チャート表示・取引明細の実機確認は未実施。27テストでこれらを保証しない。

再監査判定: PA01/PA02に関するコード・参照修正は受入可。終了時刻の制約を添えた `REJECTED_TRAINING_ONLY / TV_UNVERIFIED` の研究用下書きとして引渡し可能。対応表の補足前に、厳密な期間終端約定やPython成績の再現を主張してはならない。

### 最終確認 — 終了時刻の開示を補完

責任者が対応表34行へ、endTime到達足でも取消は通常終値計算時であり、その前に既存stop注文が約定し得ること、endTimeは厳密な最終約定時刻ではないことを追記した。監査者が記述を再読し、現行コードの制約を十分に開示していると確認した。

最終pine_mapping.md SHA256: `7abcb79fc0da2e0994a3a3f774c1f3a99979b42ad0278dbb47e5b77124a10dc1`。Pine・テストの識別子は上記修正版表のまま。対応表変更後、同一pytestコマンドを実行し **27 passed in 0.17s / exit 0**。

最終判定は **DELIVERABLE_RESEARCH_ONLY / TV_UNVERIFIED**。PA01/PA02の差戻し理由とPA03の追加開示依頼は解消。残るPA03のemulator/配信/費用/期間境界差とPA04の実機未確認は、開示済み制約として引き渡す。研究採用は引き続き `REJECTED_TRAINING_ONLY`。Pineコンパイル成功・描画成功・全明細一致・実運用承認を主張しない。
