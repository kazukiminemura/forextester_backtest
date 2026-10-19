# 日足キャッシュ再利用の確認

- 実験: daily_adaptive_pullback_20260910。担当: 主担当による再利用識別子確認。
- 入力: `agent_runs/dinapoli_3x3_daily_20260909/completed/` の15通貨日足NPZ。
- 現在確認: 第一実験 `agent_runs/daily_edge_reset_20260910/completed/code_input_hashes.json` の `inputs` に記録された15 NPZ SHA256と、`sha256` の5依存ファイルについて、PowerShell `Get-FileHash -Algorithm SHA256` で全件一致。終了コード0。
- 元M1の今回の再集約監査は `../daily_edge_reset_20260910/data_inventory.md` の担当証拠を引き継ぐ。15通貨66,096日足の全5配列一致が確認されている。本書の再確認自体はファイルhash比較であり、別のM1再集約を行ったものではない。
- 期間は2009-10-01から2026-08-28、Sundayを翌Mondayへ統合。2026-08-31のGBPJPY桁異常前で打切り。全候補250観測本の共通warmup。2010年初期の取引不足を保持する。
- 実際の時間帯、Bid/Ask系列種別、日次・方向別スワップは未確認。固定・metadataスプレッド、滑り、0.2pip/暦日保有費用はいずれも研究上の仮定。口座換算損益ではなく初期Rの研究尺度。
- 第一の学習結果を閲覧してpullback05を選んだ追試である。月次選択が因果的でも、設計段階の学習期間への選択バイアスは消えない。2019年以降も他研究で既閲覧のため未使用保証はない。
- 原履歴と旧成果物は読み取り専用。次担当は研究開発・独立検証。
