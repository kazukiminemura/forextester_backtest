# 保存時計の追加調査

調査日: 2026-10-07 JST。担当: quant_data。
状態: `NEEDS_CLOCK_EVIDENCE / SCOPED_SAFE_CHECKS_EXHAUSTED`。

追加の限定読取では、History保存時計を確定する新しい証拠は見つからなかった。
公式標準GMT+0とローカルproject設定の調査は前回で完了しているため再実行せず、今回は原History周辺の未確認の小ファイル・import記録の有無だけを調べた。
既存630ケース、独立監査、data_inventory.md、data_clock_evidence.json、manifestは変更・再実行していない。

## 今回確認した範囲

Windows PowerShellの `Get-ChildItem -LiteralPath ... -Force` で、次の限定ディレクトリを棚卸しした。隠し項目も対象だが再帰走査ではない。

|場所|今回の現物確認|
|---|---|
|`C:/ForexTester6/data`|直下はHistory/Import/News/Testingの4ディレクトリ。直下ファイル0。|
|`C:/ForexTester6/data/History`|30銘柄ディレクトリとbrokers.txt 1ファイル（111,319 bytes）。|
|`C:/ForexTester6/data/Import`|隠し項目を含め0件。import由来・Shift・DSTの小ファイルはない。|
|対象7通貨のHistoryディレクトリ|それぞれBars.dat/info.dat/ticks.datの3ファイルだけ。追加ログ・設定・子ディレクトリなし。|

対象7通貨: USDJPY/EURUSD/GBPUSD/AUDUSD/NZDUSD/AUDJPY/NZDJPY。
info.datは前回全7読取済み（320 bytes、AUDJPY/NZDJPYのみ321 bytes）なので内容読取を繰り返していない。Bars.datとticks.datの内容も今回再走査していない。

唯一のHistory直下ファイルbrokers.txtについては、既存調査では配信一覧だったため、今回は時計項目の存在だけを限定確認した。
ヘッダーはBrokerName/BrokerID/Symbol/SymbolID/StartDate/EndDate/DataTypeで時計項目なし。
本文に対する単語境界付き `clock|timezone|timeshift|DST|GMT|UTC` の検索は0件。
本文を出力せず、一致行数・時計語のみを返す方法を使用した。秘密・認証情報は表示していない。
このファイルは取得可能な配信の一覧であり、保存済み各履歴の時差・import由来を保証するものではない。

Newsは履歴時計のimport記録を目的としたフォルダーではないため走査していない。Testingは現projectの派生データで、原Historyの時計保証の根拠にはならないため、ファイル内容を走査していない。
レジストリ・home・ディスク全体・実行バイナリを調べていない。確認範囲に新たなclockログは存在せず、推測によるUTC認定はしていない。

## 残る必要証拠

データ担当の今回の安全な限定読取は完了した。`SCOPED_SAFE_CHECKS_EXHAUSTED` は上記範囲についての状態であり、コンピュータ上の全証拠が存在しないという意味ではない。

次に必要なのは、Forex TesterのData Centerで対象通貨のHistory/ダウンロード済みデータ情報に表示される **Time zone / Timeshiftの画像**。
import履歴なら、追加で元データの時計基準とimport時のShift/DST設定が必要。表示された現在値だけで過去の混在importがないことや2020–2025年の歴史的DSTを自動保証しない。
native UI操作は利用できないため、今回この画面を実確認したとは報告しない。

前回の公式根拠は [Data Center](https://desktop.forextester.com/datacenter) のTimeshift表示・標準GMT+0と、[project設定](https://desktop.forextester.com/newproject) のTimezone/DST変更機能である。今回これらを再取得していない。標準仕様とローカル保存時計を区別する。

時計未確定の状態を維持する。既存のGMT0/2/3/9の感度ケースをJST実測に昇格させない。時計証拠が得られた場合も、この追調査だけを根拠に新ケース追加や採用変更はしない。

## 再現コマンド・終了コード

以下の読取確認はすべて終了コード0。初回の表形式表示でSymbol列が省略されたため、構造化JSON表示で再確認した。

```powershell
foreach ($clockDir in @('C:/ForexTester6/data','C:/ForexTester6/data/History','C:/ForexTester6/data/Import')) {
    Get-ChildItem -LiteralPath $clockDir -Force | Select-Object Name,Mode,Length
}
foreach ($clockSymbol in @('USDJPY','EURUSD','GBPUSD','AUDUSD','NZDUSD','AUDJPY','NZDJPY')) {
    Get-ChildItem -LiteralPath ('C:/ForexTester6/data/History/' + $clockSymbol) -Force |
        Select-Object @{Name='Symbol';Expression={$clockSymbol}},Name,Length |
        ConvertTo-Json -Compress
}
$clockMatches = Select-String -LiteralPath 'C:/ForexTester6/data/History/brokers.txt' `
    -Pattern '\b(clock|timezone|timeshift|DST|GMT|UTC)\b' -AllMatches
[pscustomobject]@{
    ClockMatchLines=@($clockMatches).Count
    ClockTokens=@($clockMatches | ForEach-Object {$_.Matches.Value})
} | ConvertTo-Json -Compress
```

次担当: 研究責任者。今回の成果物は本書のみ。原履歴変更、外部代替・再取得、有料API、追加バックテスト、Pine変更、注文は行っていない。
