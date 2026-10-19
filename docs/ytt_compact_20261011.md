# YTT統合版の簡略化

入力はユーザー添付の「貼り付けたテキスト.txt」。正規化した内容は `scripts/tradingview/yosuga_ytt_watchlist_unified.pine` と一致する。
成果物は `scripts/tradingview/yosuga_ytt_compact.pine`。元ファイルは編集していない。

## 変更

- 1,052行から861行（18.2%削減）。UTF-8・LF換算74,525 bytesから59,066 bytes（20.7%削減）。
- YTT固定設定で到達しない末尾のBB通貨スキャナーを削除。チャートのBB・仮想取引集計・通知は保持。
- 高安・方向判定の重複を `f_state()` へ統合。
- 表の繰り返し書式を `f_cell()` へ統合。各セルの値、色、背景、文字サイズは比較確認。
- 使用されない関数・変数を削除。

全input宣言、水平線・チャネル・過去Entryの描画呼び出し、売買条件、BB約定・集計処理、alertを保持した。改行の短縮のみで可読性を落とす圧縮は行っていない。

## 検証

`python -m pytest tests/test_ytt_compact.py tests/test_ytt_watchlist.py tests/test_yosuga_ytt_combined.py -q`: 11 passed。
生成は `python -m scripts.simplify_ytt_pine` で再現できる。

2026-10-11 JST、TradingViewで「YTT 簡略版 20261011」として別名・非公開保存し、コンパイルとOANDA:EURUSD・5分足への追加に成功。
エディターから全文をコピーし、ローカル成果物との一致を確認した。
簡略版単独のチャートで水平線・チャネル・BB・過去YTT Entryの描画を確認した。画像は `artifacts/ytt_compact_20261011/eurusd_5m.png`。
追加した検証用インジケーターはチャートから外し、既存インジケーターを復元した。保存済みの簡略版は残している。

今回は読みやすさの改修であり、損益の改善を検証したものではない。市場休場中のため、スキャナーはデータ更新待ちを表示しており、18銘柄全体のリアルタイム通知や全時間足での同値性は実機検証していない。
