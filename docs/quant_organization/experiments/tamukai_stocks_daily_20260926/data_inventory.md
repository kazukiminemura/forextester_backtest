# 日本大型株日足データ台帳

実験ID: `tamukai_stocks_daily_20260926`。データ担当調査日: 2026-09-26。
状態: **DATA_READY_WITH_QUALIFICATIONS**。売買条件・成績・採用可否を判定する文書ではない。

## 入力と適用可能期間

ユーザーが日本大型株10銘柄を指定したため、今回の株式研究ではYahoo Finance chart日足を使用する。
最初に `HistoryRepository` と `C:\ForexTester6\data\History` を調査した。
`#AAPL` 等の海外株はあるが今回の日本10銘柄はなく、既存Forex Tester履歴は変更していない。
現在存続する大型株の便宜標本であり、当時の時価総額ランキングや退場銘柄を含む母集団ではない。生存者選択の偏りがある。

主担当が保存した `agent_runs/tamukai_stocks_daily_20260926/data/<symbol>.json` を入力識別子とする。
取得URL形式は `https://query1.finance.yahoo.com/v8/finance/chart/<symbol>?period1=1388534400&period2=1767225600&interval=1d&events=div%2Csplits`、User-Agentは `Mozilla/5.0`。
APIは無料で試験取得できたが、永続提供・契約上のSLA・将来同じ応答の再取得は保証されない。

全10銘柄に2014-01-06〜2025-12-30の生データ各2,953件がある。
初期想定2015〜2025は、全銘柄に共通する2015-12-25/2016-07-11の実営業日欠測が見つかったため、成績計算前に評価開始を2017年へ縮小した。
**評価可能な共通期間は2017-01-04〜2025-12-30、各2,198営業日。ウォームアップは2016-07-12以降のみ。**
これより前の価格を指標状態へ混入させないこと。

|銘柄|会社|生件数|評価期間有効件数|OHLC包絡異常|既知の追加制約|
|---|---|---:|---:|---|---|
|7203.T|トヨタ自動車|2953|2198|0|なし（全項目保証ではない）|
|6758.T|ソニーグループ|2953|2198|0|2025-09-29現物配当・スピンオフの価格調整|
|8306.T|三菱UFJ FG|2953|2198|2022-05-17 1件|派生系列の合成修復が必要|
|9432.T|NTT|2953|2198|0|なし（全項目保証ではない）|
|9984.T|ソフトバンクグループ|2953|2198|0|なし（全項目保証ではない）|
|6501.T|日立製作所|2953|2198|0|なし（全項目保証ではない）|
|6861.T|キーエンス|2953|2198|0|なし（全項目保証ではない）|
|8035.T|東京エレクトロン|2953|2198|2022-05-17 1件|派生系列の合成修復が必要|
|8058.T|三菱商事|2953|2198|0|なし（全項目保証ではない）|
|4502.T|武田薬品工業|2953|2198|0|なし（全項目保証ではない）|

全銘柄の年別有効件数は2017:247、2018:245、2019:241、2020:242、2021:245、2022:244、2023:246、2024:245、2025:243。
Yahoo metadataの `firstTradeDate` は全銘柄2014年より前で、実データも2014年からある。
このフィールドはデータ提供開始日の可能性があり、会社の正式上場日や期間中の組織再編の一次資料全件確認とは扱わない。

## 全件検査と欠損

保存済10 JSONの全29,530レコードを走査した。端点だけのサンプル検査ではない。
同一銘柄内のtimestamp重複0、逆順0、OHLCのnull/非有限/非正値0。
`low <= open,close <= high` を満たさないものは前述の2レコード。
各銘柄の日付集合は完全一致。ただし市場日程照合を別途行うまでは、それだけで無欠損とはいえない。

全銘柄共通でvolume=0の24行がある。うち22日は祝日・年末年始等の非営業日ダミー。
残る2015-12-25と2016-07-11は営業日だがOHLC同値・出来高0であり、利用可能な売買バーと扱わない。
24行を派生CSVから除外し、原JSONには保持する。売買停止や欠測を一般にvolume=0だけで区別できるわけではない。

日付検査は[内閣府の祝日一覧とCSV](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html)を読み、土日、1月1〜3日、12月31日を除く方式。
[JPX休業日資料](https://www.jpx.co.jp/corporate/about-jpx/calendar/)と、[2020-10-01の終日売買停止の公式資料](https://www.jpx.co.jp/corporate/research-study/system-failure/nlsgeu00000525ve-att/siryo_japanese_20210325.pdf)を根拠に同障害日も除外した。
2014〜2025の期待営業日2,931日に対しpositive-volume日は2,929日で、差は上記2営業日のみ。
**2017〜2025の2,198日は、この日程モデルと全10銘柄で欠損0・余剰0。**
全期間の銘柄別臨時売買停止公告や各足の取引所原票との全件照合までは実施していない。

## 価格・時間・コストの根拠

- 全10銘柄metadataは `currency=JPY`, `exchangeName=JPX`, `exchangeTimezoneName=Asia/Tokyo`。株式価格のクオート通貨は日本円。
- Unix timestampをUTCの瞬間として解釈し、Asia/Tokyoへ変換した日付を営業日とする。全29,530行のラベルは09:00 JST。UTC日足へ再集約しない。日足OHLC全体が09:00に既知という意味ではなく、確定後に使用する。
- Yahoo日足のquote OHLCを利用し、`adjclose/close` 比率をOHLCへ乗算しない。[Yahooのhistorical表記](https://finance.yahoo.com/quote/%5EN225/history/?frequency=1d)ではCloseは分割調整、Adj Closeは分割・配当等調整。普通配当込み総収益とは呼ばない。
- 価格は日足の取引価格系列でありBid/Askではない。板、スプレッド、寄付約定の待ち行列、ストップ高安での執行可能性は記録されていない。
- protocolで指定する片道0.1%（stress 0.2%）は手数料・スリッページ等を一括した研究上の仮定で、実測スプレッドや特定証券会社料金ではない。原データからの費用推定ではない。
- FXのpip定義・FX lot_sizeは適用しない。[JPX資料](https://www.jpx.co.jp/equities/trading/domestic/03.html)による100株単元統一は2018-10-01。株価帯別tick、過去単元、分割前の株数は今回の比例・端株モデルで再現しない。調整後の端株数量による円損益は100株単元での実約定再現ではない。
- 普通配当、税、金利、企業行動の現物受領・換金は別途再現されていない。特にSonyは下記の追加制約がある。

## 分割・異常ギャップ

生JSONのevents.splitsには、7203:2021-09-29 5:1、6758:2024-09-27 5:1、9432:2015-06-26 2:1/2019-12-27 2:1/2023-06-29 25:1、9984:2019-06-25 2:1/2025-12-29 4:1、6501:2018-09-26 1:5/2024-06-27 5:1、6861:2017-01-18 2:1/2019-11-19 2:1、8035:2023-03-30 3:1、8058:2023-12-28 3:1がある。8306と4502には当該期間内eventなし。
全イベント日で前日終値→当日始値は±2%以内であり、分割比率そのままの未調整断層は見つからなかった。
この検査はイベント列との整合検査であり、全イベントの会社一次資料照合や欠落イベントの不存在証明ではない。
全件の前日終値→当日始値の絶対20%超は8306の2025-04-07（約-20.98%）、9984の2020-03-24（約+20.80%）のみ。大幅変動として報告し、機械的な補正・削除はしない。これらの値の取引所原票検証は未実施。

## 2件のOHLC合成修復

|銘柄/日付|Yahoo原値|派生系列の必要修復|二次情報との照合|
|---|---|---|---|
|8306.T/2022-05-17|L717.2000122070312, C717.0999755859375|LをCまで拡張|みんかぶO738.0/H739.3/L717.1/C717.1|
|8035.T/2022-05-17|H19333.333984375, C19346.666015625|HをCまで拡張|みんかぶ分割前O57320/H58040/L56560/C58040、3分割換算でH=C19346.6667|

二次資料: [8306当日表](https://minkabu.jp/stock/8306/daily_bar?page=54)、[8035当日表](https://minkabu.jp/stock/8035/daily_bar?page=54&selected_platform=pc)。
query2.finance.yahoo.comでも同じ異常が再現し、独立ソースとは扱わない。Stooq CSVはブラウザ検証HTMLが返り、価格データを取得できなかった。
修復は根拠のない丸めではなく、原始値・終値を包む派生系列の **synthetic normalization** として主担当が固定したもの。
二次資料と方向・修復値は一致するが、取引所原票による正確性保証ではない。出来高もYahooと二次資料で異なる（8306:64,714,400対72,451,500、8035:2,355,300対分割前904,400×3）。
OHLC整合だけ通れば全原値が正しいとはいえない。原JSONを変更せず、派生CSVとmanifestに原値・修復値を明示すること。

## Sony現物配当

[Sony公式](https://www.sony.com/en/SonyInfo/IR/news/20250903_02E.pdf)は2025-09-29を金融子会社株の現物配当権利落ち日、10月1日を交付日とする。
Yahooの2025-09-26 raw closeは4231.19921875、open4350.306640625、翌29日はopen4230/close4268。
同一日の[二次価格表](https://96ut.com/stock/jikei.php?code=6758&year=2025)では9月26日はopen4529/close4405、9月29日はYahooと同値。
単なるtick丸めではない遡及調整が混在している強い証拠がある。raw eventsには2025-09-29普通配当12.5のみ、対応するsplit eventなし。調整係数の完全な算定根拠は未確認。
したがって10銘柄集計を厳密なsplit-only純価格収益と断定できない。主担当指定により10銘柄を参考集計として保ち、Sony除外9銘柄、Sony/8306/8035除外7銘柄を同一条件の感度確認に使える。
7銘柄は「既知調整問題3銘柄除外」であり、全価格の正確性や投資可能性を保証するquality-clean認証ではない。

## 閲覧状況と未確認事項

今回2014〜2025の全価格レコードと品質統計を機械走査した。戦略成績をデータ担当は算出していない。
過去の別チャット等での同期間の閲覧・探索状況は不明であり、未使用holdoutとは保証しない。
2017〜2019/2020〜2022/2023〜2025の区分があっても、それだけで独立未使用データになるものではない。
全10銘柄の正式上場日・全企業行動・全足取引所原票・板/実約定・過去の単元/呼値・出来高調整仕様は未確認。

## 原JSONのSHA256

```text
4502.T a5d4baa36f2aa18d2e7f6ef4c8bb212368df0088f2bce68e07ae7d62b92a3728
6501.T 40b64e55f9020c5642152f24e937f89abeb68ba1e260bea5d6e38de38439b47c
6758.T 2c12a6a7d3d555e4d5401cc70df321b5e5810d70678600b4cb98cec925c0c995
6861.T 0a46c67d0f3949dcb4479c34421702d468dab52f6d1ae0218f8928a8172add5a
7203.T aca4f188dafa8cf8593c8937b0379167708c180eb4658a20b99f8978c3d408df
8035.T bfe44d95193aa40d301d773efb0b7b91e3fd175fb0088a94b9c4aa3790978597
8058.T 662e4f805fc4a8e1e8461128d003d7086076911c9ec77824441a09401a8bfaf6
8306.T 4148f32bfc4f612b720c792ed92a90b46f2db6fc1271724356f8fefc7fafb218
9432.T 1364fa24e5fb82f1f9ac94502c10d9dc20c2ab3150d72008109ad1825db22498
9984.T 0574ced67c0e4471c5d188e5fcac5ebab7457d235d1e167a24f8c019457fc840
```

## 再現コマンド

主担当が保存した派生CSVも全23,140行を検査済み。各銘柄2,314行（2016-07-12〜2025-12-30、うち評価2,198行）、OHLC包絡違反0。
`data/manifest.json` はraw/CSVのhashと品質処理を記録している。CSVのSHA256は以下。

```text
4502.T 4a11585725fcf488f5a4ce20e2d6492c8273a2cb2e8c74eb36502471a91c72aa
6501.T 47fd60ca582c5429479daf463e1d1e349bc9ab5aa8589e92d695943e72c47a53
6758.T c8c6ba3f0be91879b3d4a899fda0dfc64583145970a2cf2755f51997ebb533be
6861.T d06587f8fe32cbc09db7686e9113602d17fc999d57f3b90319004f7d44858470
7203.T 0ab55ff8cf84f91e685a9d58ec29b2b421ca6c516c9e12aa7a90bc5e5f9199e8
8035.T 6fe3115a5aefebbafe3483128fa03dacdd85f768559725f75a05599b9522907b
8058.T 01f819aa243cfc45f92734500a493050b864ff5a01c793be6f193b97636da855
8306.T 4f6a43484c1494b97cb07f0762f5d6b5afc8531436a09f389fcc0f57383fde1f
9432.T 58d1637f106d3dd90bc26eb6dcd5d879854d074861fe53a0e73d94a0362ecdbb
9984.T 954672eb1b8f0ffd5d7202401303eae6a7857d0712c021c0b87cc274b9177ec4
```

workspace rootからPowerShellで実行。原JSONは読取専用。実行exit 0を確認済み。

```powershell
@'
import json, math, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
sets=[]
for f in sorted(Path('agent_runs/tamukai_stocks_daily_20260926/data').glob('*.json')):
    if f.name == 'manifest.json':
        continue
    b=f.read_bytes(); a=json.loads(b)['chart']['result'][0]
    ts=a['timestamp']; q=a['indicators']['quote'][0]
    ds=[datetime.fromtimestamp(t,timezone(timedelta(hours=9))).date().isoformat() for t in ts]
    assert len(ts)==len(set(ts)) and all(x<y for x,y in zip(ts,ts[1:]))
    invalid=[]
    for i,d in enumerate(ds):
        o,h,l,c=[q[k][i] for k in ('open','high','low','close')]
        assert all(v is not None and math.isfinite(v) and v>0 for v in (o,h,l,c))
        if not (l<=o<=h and l<=c<=h): invalid.append(d)
    selected={d for i,d in enumerate(ds) if d>='2017-01-01' and q['volume'][i]>0}
    sets.append(selected)
    print(f.stem,len(ts),len(selected),invalid,hashlib.sha256(b).hexdigest())
assert all(s==sets[0] for s in sets)
assert len(sets[0])==2198
print('Common dates',min(sets[0]),max(sets[0]))
'@ | python -
```

calendar検査は上記に続けて実行可能（祝日CSVを再取得するので将来変更される可能性あり）。

```powershell
@'
import csv,io,json,urllib.request
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
raw=urllib.request.urlopen('https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv').read().decode('cp932')
holidays={datetime.strptime(r[0],'%Y/%m/%d').date() for r in list(csv.reader(io.StringIO(raw)))[1:] if r and r[0]}
expected=set(); d=date(2017,1,1)
while d<date(2026,1,1):
    if d.weekday()<5 and d not in holidays and (d.month,d.day) not in [(1,1),(1,2),(1,3),(12,31)] and d!=date(2020,10,1):
        expected.add(d)
    d+=timedelta(days=1)
for f in Path('agent_runs/tamukai_stocks_daily_20260926/data').glob('*.T.json'):
    a=json.loads(f.read_text())['chart']['result'][0]; v=a['indicators']['quote'][0]['volume']
    ds={datetime.fromtimestamp(t,timezone(timedelta(hours=9))).date() for i,t in enumerate(a['timestamp']) if v[i]>0}
    ds={d for d in ds if date(2017,1,1)<=d<date(2026,1,1)}
    assert ds==expected,(f.name,expected-ds,ds-expected)
print('Calendar match',len(expected))
'@ | python -
```

## 引継ぎ

- 次担当: 主担当・研究実装・独立検証。
- 変更したファイル: この `data_inventory.md` のみ。raw/CSV/コードはデータ担当の編集対象外。
- 検証できた事項: 上記保存JSON全件の順序・重複・価格有限性・OHLC包絡・営業日・分割イベント周辺。
- 次工程に渡してよい範囲: 2017〜2025の条件付き記述研究。原データ保存、2件合成修復記録、Sony・2異常銘柄の感度集計と制約開示を要する。
- 実注文: なし。
