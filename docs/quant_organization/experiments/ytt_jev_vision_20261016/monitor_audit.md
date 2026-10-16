# 5分ごとの画面撮影・Jev通知 独立監査

2026-10-16。品質監査担当。最終状態: **AUDITED_MONITOR_PROTOTYPE_LIMITED**。限定プロトタイプとして引渡し可。研究合格・利益改善・実運用承認は含まない。

## 監査範囲

ユーザーがブラウザの画面共有対象を指定し、5分ごとに撮影したチャートをJevへ送って買い/売り候補を通知する機能。監査担当は本書と `tests/test_ytt_jev_monitor.py` のみを編集し、有料API・通知配信・注文を実行しない。

既存 core `scripts/ytt_jev_vision.py` SHA256 `a8e4116a7dfafad836300eb5becacbb8872b94002c5cecb5f2d6b3c3836b595e` と固定3円共有予算を継承する。前回1件の予約0.5505024円を保持し、新しい予算を作り直さない。

## 対象境界

1. 開始/停止/画面共有終了/pagehide/非同期許可の競合。停止後に送信・表示・通知を復活させない。
2. 二重開始・重複タイマー・処理中の次回送信・スリープ後の過去回数まとめ送信を抑止。
3. 通知権限拒否・非対応時の画面表示、重複通知、期限切れ通知、予算/通信異常時の停止。
4. 画面共有元の扱い、metadata allowlist、既存予算と秘密保護、前回記録との取り違え。
5. ローカル偽API/偽ブラウザの試験と、実ブラウザの許可・継続取得・OS通知確認を区別する。

## 一次資料

MDN [getDisplayMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)、[Notification.requestPermission](https://developer.mozilla.org/en-US/docs/Web/API/Notification/requestPermission_static)、[MediaStreamTrack ended](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/ended_event) を確認。画面共有はユーザー操作から都度許可が必要であり、共有候補の指定は強制的な対象制限ではない。通知のdefault/deniedは許可済みとして扱わない。

## 初期判定

実装受領前。自動撮影・実通知確認済み、常時稼働中、研究合格、利益改善、実運用承認とは報告しない。

## 最終確認

`docs/ytt_jev_monitor_20261016.md` と実装を照合した。主担当の実機確認で共有元がwindowとして返る制約が判明し、browser/windowを許可して送信前プレビュー確認を必須化。monitor（デスクトップ全体）と不明な共有元は拒否する。共有プレビュー中はまだJevへ送信しない。ユーザーが確認したチャートの画像だけを送る設計であり、共有後のウィンドウ内容変更や口座情報の不在を自動保証するものではない。

### 独立実行結果

```text
python -m pytest tests/test_ytt_jev_vision.py tests/test_ytt_jev_vision_audit.py tests/test_ytt_jev_vision_app.py tests/test_ytt_jev_monitor.py -q
54 passed in 8.34s
exit 0
```

新監査17件は Node VM の偽DOM・偽画面共有・偽時計・偽通知・偽API、および一時loopback HTTPサーバで実行。実画面取得や外部API課金は監査担当から行っていない。

1. 共有許可待ち停止、二重開始、応答待ち停止、停止後の再開と旧応答破棄、共有解除、pagehideで送信/通知の復活を抑止した。
2. windowの共有プレビュー確認までAPI呼出0。停止後/再開後の古い確認callbackもAPI呼出0。確認中の銘柄/時間足入力は無効化される。
3. 同一方向の連続通知抑止、様子見後の再通知、通知権限拒否の画面fallback、期限切れ通知抑止、無料通知テストAPI呼出0、許可待ちpagehide後の通知0を確認した。
4. 処理中に次の送信を予約せず、スリープ後のまとめ送信なし。正常応答完了から300秒後に次回を予約する。最終予算回とAPI異常で停止する。
5. サーバーのsource allowlist、monitorのbrowser_capture記録、300秒未満の監視再送拒否、手動/監視の同時推論拒否、旧予約引継ぎ、ledger不整合時の残回数0を確認した。

### 指摘の処置

**P1・解消**: 初期UIの「撮影時刻+300秒」とサーバーの「HTTP開始から300秒」が異なり、通信遅延差で正常な2回目が429停止する可能性があった。UIを応答完了後300秒へ変更し、テストで一致を確認した。

共有対象・送信前確認の変更は実機の互換性問題に対応したもので、利益や分類結果に合わせた閾値変更ではない。core、Jevモデル、確率/鮮度の判定、固定3円予算は前回と同じ。未解消の重大な停止・予算・HTTP境界の実装不一致は認めない。

### 保存された監視開始時の実API 1件

主担当の実機実行 `agent_runs/ytt_jev_vision_20261016/85f0c0f3545b4689afd096bae95b3629/` を独立読取検算した。原画像・加工画像のSHA、送信base64、metadata、固定questions、モデル、予約fingerprint/receipt、応答と最終結果が一致。検算 `MONITOR_FIRST_CAPTURE_INDEPENDENT_MATCH` / exit 0。

- 撮影: `2026-10-16T00:57:02.914Z`、USDJPY・5分足、判断15分、provenance `browser_capture`。
- 結果: **hold / insufficient_visible_evidence / evaluated**。画像を視認し、YTTは「見送り・参考帯なし／データ更新待ち」と表示され、新規成立の根拠不足を確認した。
- input 5,251 / output 134。単価0.042 USD/Mtoken・200円/USDの管理換算は **0.0441084円相当**。実請求額ではない。
- 既存1件を含む台帳は2予約、**1.1010048円**。この確認時点で**残り3回**。既存100円承認や今回3円枠のリセット・拡張なし。
- result SHA256: `f387f290d5d4705a0be1ae59c4ba5bc67d7b343e8ea22e59d448712db57ce349`。

主担当からの最終実機報告では、共有元のTradingViewタブが閉じて共有終了を検知し、監視は安全に停止した。監査担当自身がそのブラウザ操作を再実行したわけではない。

### 最終識別子

|対象|SHA256|
|---|---|
|scripts/ytt_jev_vision.py|a8e4116a7dfafad836300eb5becacbb8872b94002c5cecb5f2d6b3c3836b595e|
|scripts/ytt_jev_vision_app.py|466812c992b3ae2e4fe697ae360f6fb866acd63b15e9cb7a6a61d435913058a6|
|scripts/ytt_jev_vision_app.html|cd730a67f89248b9dee73ae1b91a971a036781a97d11f5e925c3e2452fc92e28|
|scripts/start_ytt_jev_monitor.cmd|ff72a658f6fc95bd849cd7a256e458af3c15487095bedacc0c78d7c1c1f652a2|
|tests/test_ytt_jev_monitor.py|985603f71519f69ef215d48e17edf3c34866dc2b061a6f96003c51d140932401|

## 引渡し範囲と未確認

手動共有・プレビュー確認から監視開始時の画像取得/保存/API判定までの限定接続証拠を確認した。5分後の実ブラウザによる2回目の自動送信、OS通知の実受信、音声、長時間/バックグラウンド/スリープ復帰の実機挙動は未確認。これらの一部の分岐は偽環境テストで確認したが、実機確認済みと同一視しない。

買い/売り画像分類の精度、取引勝率・RR・利益改善、PineへのAI条件移植、発注・実運用承認は対象外。今回の実応答は様子見1件であり、候補通知による売買の有効性は証明していない。
