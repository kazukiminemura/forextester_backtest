# YTT Jev 画像判断補助・独立監査

2026-10-16。品質監査担当。最終判定: **AUDITED_DELIVERABLE_PROTOTYPE_LIMITED / 実運用・収益性採用なし**。

## 対象と境界

よすが式チャートのスクリーンショットを、Jev 1.14 系で買い・売り・様子見に分類するオンデマンド試作。主担当が UI、開発担当が画像処理・API・費用台帳を所有し、監査担当は本書と監査専用テストのみを編集する。推論API、有料実行、秘密値取得、口座操作を監査担当は実施しない。

`charter.md`、`board.md`、TypeSafe skill、旧 `ytt_jev_20261010/audit.md` と protocol を読取確認した。旧実験の管理費用 23.8829052 円と累積無効応答 3 件による停止は引き継ぐ。今回の画像試作は別目的であり、旧バッチ再開や承認 100 円のリセットを認めない。

## 一次資料

2026-10-16 に [Images](https://docs.typesafe.ai/images)、[HTTP API](https://docs.typesafe.ai/api)、[Choice](https://docs.typesafe.ai/primitives/choice)、[Models](https://docs.typesafe.ai/models) を読取確認。

画像入力は公式に prototype 向けとされ、専用ヘッダーが必要。PNG/JPEG、各辺 280–1568 px 等の制限を事前確認する。Choice は全選択肢の有限確率分布と選択結果の整合が必要で、AI の選択確率は取引勝率ではない。

## 受領後の監査項目

1. 古い画像、未来時刻、未確認の撮影時刻、5分チャートと15分判断の不一致、未確定足・過去Entry・突破済を新規シグナルと混同しない。
2. 既定 dry-run、明示 live、固定した追加 3 円上限、送信前永続予約・排他、失敗予約保持、出力先変更や再起動による予算リセット拒否。
3. 異常分布・choice 不整合・モデル相違・タイムアウト・処理中の画像期限切れは様子見。自動再試行を行わない。
4. loopback 限定、Host/Origin/CSRF 検査、アップロード上限、任意パス読取拒否、キーのサーバ側保持、外部送信画像の事前確認。
5. コード識別子、テスト結果、保存された限定実API結果、UIの状態と制約表示を照合する。

## 現時点の引渡し

実装の監査前。研究合格、利益改善、Pine移植、TradingView実機確認、実運用承認はいずれも認定しない。画像撮影時刻が現在でも、過去へスクロールしたチャートである可能性は残るため、画面内の最新確定足と時刻・銘柄・時間足が不明な場合を扱う必要がある。

## 実装受領後の独立検査

監査は `tests/test_ytt_jev_vision_audit.py` と `tests/test_ytt_jev_vision_app.py` を追加した。後者は 127.0.0.1 の一時 HTTP サーバだけを起動し、API 部分を偽関数へ置換する。画像は合成白画像、キーは固定偽文字列、予算は pytest 一時ディレクトリ。外部推論の呼出はない。

実行:

```text
python -m pytest tests/test_ytt_jev_vision.py tests/test_ytt_jev_vision_audit.py tests/test_ytt_jev_vision_app.py -q
36 passed in 5.91s
exit 0
```

開発側 21 件、監査側 15 件。timestamp 不正・画像期限・15分以外の判断時間足・不確かな新規成立・方向と理由の矛盾・NaN/型/モデル/最大確率との不整合を様子見にし、新規送信や自動再試行を抑止することを確認。異常応答を保存できない場合も予約が残る。別 output 7 回から外部相当呼出は最大 5 回。偽キーが保存JSONへ出ない。

HTTP 側は不正 Host/Origin/CSRF/Content-Type を拒否。cross-site config GET、任意ファイルパス、未知 endpoint、過大 Content-Length、不正base64、boolean 以外の live は呼出なし。出力ディレクトリはサーバが生成し、送信metadataの余計な秘密項目を除去する。

### 指摘と修正

1. **P1・解消**: 初期実装の ledger 単独欠落による予算再作成。固定予算ディレクトリ内の予約 receipt と journal の全件一致を送信前に要求する修正を確認。中断時の片側のみ記録も不一致として停止する。全証跡を意図的に削除する操作への耐性は保証しない。
2. **P1・主要経路解消**: 判定中に画像や銘柄を変更すると以前の応答が新プレビューに表示された。UI の全入力ロック、貼付拒否、判定後の入力変更による無効化を読取確認。**P2・再確認待ち**: FileReader 複数完了の順序逆転による画像取り違えを主担当へ返却。
3. **P2・解消**: API 復帰時の時刻検証が固定開始時刻を再利用。終了時にclockを読み、期限超過をholdへ戻す実行テスト成功。
4. **P2・解消**: 大きな圧縮画像のデコード前制限、HTTP redirect 拒否、手動timestampのprovenance追加を読取確認。元画像上限20M pixels / 最大辺8192、送信画像最大辺1568。APIキーは環境/Windows user environmentからサーバ側取得、ブラウザに返さない。

### 識別子（36 tests 実行時）

|対象|SHA256|
|---|---|
|scripts/ytt_jev_vision.py|a8e4116a7dfafad836300eb5becacbb8872b94002c5cecb5f2d6b3c3836b595e|
|scripts/ytt_jev_vision_app.py|78fd3dda6e7b315b0196b6a68cebf093e673c0ce85999d4009a000cf56056dc5|
|scripts/ytt_jev_vision_app.html|47607bfa5f6472b4f6637f9a9d287ffc499ad0198bb24b2443e3c4e49d471e08|
|tests/test_ytt_jev_vision.py|e8437bdb6cb6c4d04fb5a404e73575ae4467189d88b6f1f40d1f777e14fb0d76|
|tests/test_ytt_jev_vision_audit.py|42cb5cce8c8e05d0976a69b77201fd338212ecbc332df6393ff64ce0d6faa349|
|tests/test_ytt_jev_vision_app.py|3a558f0e2d8f55736fa10f6dd0f8cb95421ab50bc0170fcc0411ea2aec58f386|

## 残る適用限界

チャートの最新時刻・15分確定・上位足一致の読取りは Jev の意味判断に依存する。メタデータ時刻やサイズの検査は画像内容の真実性を保証しない。confidence .6 / probability .8 は試作の表示条件で、取引成果に対して検証された閾値ではない。buy/sell が出ることもその正しさや期待利益の証明ではない。

本件は画像分類補助の実装監査であり、約定・TP/SL・ギャップ・holdout・収益性の研究を実施していない。Pine変更、PineからAPIへの直接接続、注文、常時監視はない。最終引渡しには主担当が保存する固定仕様とUI/限定API結果を別途照合する。

## 最終限定監査

`protocol.json` と `docs/ytt_jev_vision_20261016.md` を受領した。protocol は初回 smoke 後の記録であることを明記し、事前凍結した収益研究とは扱っていない。APIを行った core SHA は監査時の `a8e4116a...b595e` と同じで、閾値変更はない。独立した hypothesis.md / validation.md の分割はないが、同内容と実行証拠を統合文書および本監査に置く限定UI試作として確認した。

### UI修正と最終試験

FileReader の世代番号チェック、前回結果の非同期復元が新しい画像選択を上書きしないチェック、結果対象銘柄・時間足の明示を読取確認。前回記録 GET は再推論せず、期限切れ表示はクライアントで様子見となる。HTTP `/api/latest` の空状態・保存結果/画像の復元・cross-site拒否・API呼出0の独立テストを追加。

最終コマンドは上記と同じ、**37 passed in 6.46s / exit 0**（開発21、独立16）。監査担当はブラウザを直接操作していないため、入力ロック・世代競合・期限切れの画面上の全遷移は読取確認の範囲。HTTP経路は実際の一時loopbackサーバで確認した。

最終変更対象SHA:

|対象|SHA256|
|---|---|
|scripts/ytt_jev_vision_app.py|e9a983caa0da1ec6283061e13d6ee1c7071313bb50ce7d4009b1de7a8b7dc83e|
|scripts/ytt_jev_vision_app.html|60bcb04bb1c9dbd4d36b4ce4c8a6aa72a03d9bf403764e6c4d7268f451442798|
|tests/test_ytt_jev_vision_app.py|57eab27e052905f0084ac7740ce6e0f72e9a971ebce213480a7906162ff27d6f|

core・他テストは前掲SHAと同一。P1/P2の実装所見は解消し、未解消の重大な契約・予算・HTTP境界不一致は認めない。

### 保存済み実API 1件の独立照合

主担当の保存物 `agent_runs/ytt_jev_vision_20261016/9b6c8326457945ffb77e8fc0148f5d30/` の原画像・送信画像・要求・応答・結果・予約・receiptを読取照合。監査担当の追加API呼出なし。独自Python検算は `INDEPENDENT_SMOKE_AUDIT_MATCH` / exit 0。

1. 要求stateは画像参照とallowlist metadataのみ。元画像/送信画像SHA、要求base64の復号バイト、固定questions、要求/応答モデル、fingerprintと予約receiptが一致。
2. 画像を視認し、OANDA USDJPY・5分足・YTT表示を確認。画面内に準備・突破済み等があり、15分の表示は「見送り・参考帯なし／データ更新待ち」。この画像から今の新規買い/売りを断定する根拠は不足している。
3. 応答actionは hold (.98)、readable .03 / new_signal .05。最終 `hold / insufficient_visible_evidence / evaluated` と一致。これは1件の不成立画像に対する接続・抑制確認であり、成立画像の買い/売り分類精度の確認ではない。
4. input 4,053 / output 134。入力単価 .042 USD/Mtoken・200円/USD の独自Decimal計算は **0.0340452円相当**。予約台帳は1件 **0.5505024円** を保持し、精算して追加回数を増やしていない。旧training_resultsの管理値 **23.8829052円** を現物確認。合計管理額は **24.4334076円**、旧停止バッチ再開なし。
5. result SHA256: `49243407823e7e19adb791e0aefa70abd45cf1ae99321ecbf3c93048884f1cbd`。

実装と説明が一致する手動画像判断プロトタイプとして引渡し可。現在の市場データの正確性、正しい成立画像の検出率、勝率/RR/利益改善、研究合格、Pine連携、実運用承認は未認定。次の工程は、時点固定した画像と実際のシグナル正解を用いた独立な分類評価であり、今回の1件を利益実証として扱わない。
