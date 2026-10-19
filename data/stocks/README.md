# 保存済み株価データ

今後の株式検証は保存済みデータを優先する。再取得や自動更新は行わない。

検証結果は[株式ダッシュボード](../../docs/stock_dashboard.md)で閲覧できる。

## 日本大型株10銘柄・Yahoo日足

保存先: `data/stocks/yahoo/jp_largecap10_20260926/`

- 7203 / 6758 / 8306 / 9432 / 9984 / 6501 / 6861 / 8035 / 8058 / 4502（すべて `.T`）
- 元JSON: 各2,953行、2014-01-06〜2025-12-30。
- 検証用CSV: 各2,314行、2016-07-12〜2025-12-30。評価可能範囲は2017年以降、以前はウォームアップ。
- `manifest.json`: 取得日時、出典、期間、raw/CSVのSHA256、除外行、2件の補正履歴。
- 元実験のスナップショットから21ファイルをそのまま複製。元実験の入力・結果は保持。

```powershell
# 初回は元実験から保存。以後はネット接続なしで整合性を検査する。
python scripts/stock_data_cache.py

# 保存データを検証へ明示的に渡し、新しい結果フォルダーへ保存する。
python scripts/research_tamukai_stocks_daily.py --data-dir data/stocks/yahoo/jp_largecap10_20260926 --output agent_runs/tamukai_stocks_daily_cached_replay/results
```

検査で欠損・ハッシュ不一致が出たら停止する。自動再取得や上書き補修はしない。
今後作る株式検証もこの保存先を既定入力として利用する。期間や銘柄を拡張する場合は新しい識別名で別保存し、既存スナップショットを変更しない。

元データにも品質制約がある。Sonyの2025年スピンオフ調整は未解明、8306/8035の2022-05-17高安は二次資料と照合して合成修復済み。配当込み総収益ではない。
詳細: [データ台帳](../../docs/quant_organization/experiments/tamukai_stocks_daily_20260926/data_inventory.md)。

株価ファイルはローカル保存され、Git管理から除外している。別PCへ移す際はこのフォルダーもコピーする。保存スクリプトとこの案内はGit管理対象。
