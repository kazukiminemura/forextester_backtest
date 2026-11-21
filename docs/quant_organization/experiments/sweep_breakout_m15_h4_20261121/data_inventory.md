# スイープ後ブレイクのM15・H4データ台帳

2026年11月21日 JSTに、`C:/ForexTester6/data/History` の5通貨の保存M1を読取検査した。2015-01-01以上2026-01-01未満、ウォームアップを含む全20,415,837本で、重複、逆順、分境界ずれ、非有限・非正価格、OHLC内部不整合は0本。入力ファイル全10件のSHA256は前回の[データ台帳](../luxalgo_sweeps_m15_20261120/data_inventory.md)と一致した。

## 範囲と集約足

`HistoryRepository().summary(symbol)` で有効レコード数を取得し、原 `Bars.dat` を読取専用の `numpy.memmap` で開いて全件検査した。時刻はOLE日付、続く5列はOpen、Close、High、Low、volume。最寄り整数秒へ丸めて保存暦の00時を起点に集約した。保存タイムゾーンは未確定。

| 通貨 | 対象M1 | M15 | 部分M15 | H4 | 部分H4 | 60秒超の間隔数 |
|---|---:|---:|---:|---:|---:|---:|
| USDJPY | 4,097,053 | 274,227 | 8,601 | 17,723 | 4,363 | 11,994 |
| EURUSD | 4,095,407 | 274,168 | 9,016 | 17,719 | 4,320 | 12,734 |
| GBPUSD | 4,098,946 | 274,162 | 6,386 | 17,718 | 3,418 | 9,153 |
| AUDUSD | 4,088,725 | 273,797 | 8,475 | 17,700 | 3,612 | 12,603 |
| USDCHF | 4,035,706 | 269,784 | 2,868 | 17,513 | 2,307 | 3,783 |

対象範囲の最初のM1はUSDJPY・EURUSD・GBPUSD・AUDUSDが2015-01-01 22:00、USDCHFが同23:01。最後はいずれも2025-12-31 21:58。保存全体の端点と銘柄設定は前回台帳を引き継ぎ、今回の検査範囲は上表の2015〜2025年とした。未記録時間には週末・休場が含まれ、営業日カレンダーとの照合は行っていない。最大観測間隔はUSDJPY・EURUSD・GBPUSDが4,321分、AUDUSDが4,325分、USDCHFが4,931分。

| 通貨 | 2015〜2016年ウォームアップM1 | 2017〜2019年M1 | 2020〜2022年M1 | 2023〜2025年M1 |
|---|---:|---:|---:|---:|
| USDJPY | 746,453 | 1,117,839 | 1,116,071 | 1,116,690 |
| EURUSD | 745,996 | 1,118,799 | 1,115,368 | 1,115,244 |
| GBPUSD | 747,276 | 1,118,751 | 1,117,866 | 1,115,053 |
| AUDUSD | 747,403 | 1,117,092 | 1,114,786 | 1,109,444 |
| USDCHF | 731,483 | 1,097,421 | 1,100,214 | 1,106,588 |

## H4の保存時刻アンカーとTradingView

M15は保存日付の00・15・30・45分、H4は保存日付の00・04・08・12・16・20時を始点とする。部分足は、M15ならM1が15本未満、H4なら240本未満、または予定先頭分から始まらないバケット。観測0本のバケットは作らず、欠けた分を補間しない。研究仕様は非空の部分足を含め、15分と4時間をそれぞれ独立して評価する。

TradingViewで同じ通貨コードを表示しても、価格配信元、セッション、夏時間、4時間足の取引所・ブローカー時刻の区切りが一致する保証はない。チャートの表示タイムゾーンを変えただけでは4時間足の区切りは揃わない。今回のH4結果は保存時刻00時アンカーによる集約に対応する。TradingViewのH4と同一バー系列であるという確認は行っていない。

独立集約と `HistoryRepository.bars` の照合はサンプル検査。各通貨の2015-01-01〜2015-01-08、2025-12-25〜2026-01-01を使い、M1合計59,072本からM15合計4,027本、H4合計275本を作った。20通貨期間時間足区間の時刻・OHLC・volumeはすべて一致した。全2015〜2025年の集約をRepositoryと突き合わせた検査は行っていない。

## 価格品質と費用

各通貨の対象全件で、非有限・非正価格、HighがOpen/Closeを下回る、LowがOpen/Closeを上回る、HighがLowを下回る行は0本。volumeの非有限・ゼロは0本、負volumeはUSDJPY5、EURUSD12、GBPUSD3、AUDUSD6、USDCHF0の合計26本。今回の条件は出来高を使わない。

| 通貨 | 保存decimals | 1 pip価格幅 | 設定spread pips | lot size | 損益のクオート通貨 |
|---|---:|---:|---:|---:|---|
| USDJPY | 3 | 0.01 | 1.2 | 100,000 | JPY |
| EURUSD | 5 | 0.0001 | 1.1 | 100,000 | USD |
| GBPUSD | 5 | 0.0001 | 1.4 | 100,000 | USD |
| AUDUSD | 5 | 0.0001 | 1.2 | 100,000 | USD |
| USDCHF | 5 | 0.0001 | 1.5 | 100,000 | CHF |

根拠は `HistoryRepository.metadata` が読む `info.dat`。全通貨の `Broker=Advanced Data Feed`、`ApplyCommission=0`、`CommPerLot=0.00`、`SwapLong=0.0000`、`SwapShort=0.0000`。保存設定から当時の実約定コストは確定できない。往復固定1 pipは今回の研究シナリオで、設定spreadよりも小さい。M1にBid/Askフラグはなく、価格種別も未確定。

USDCHFは今回の2015〜2025年M1全4,035,706本中2,446,476本でOpen=High=Low=Close。前回監査では2017〜2025年の61.66%が単一価格、2017〜2023年の全件が整数pip刻み、同保存時刻のtickとM1が一致しないサンプルを確認した。[前回の監査](../luxalgo_sweeps_m15_20261120/audit.md)

M1の高安の情報量に制約があるため、5通貨を固定した本集計に加え、USDCHFを除く4通貨の感度集計を確認する。原データは書き換えず、価格情報の修復や別配信元への差替えは行っていない。

## 入力同一性と再現

Bars.datとinfo.datのSHA256は前回データ台帳の10件と全一致した。入力の保存範囲、通貨設定、元ファイルの同一性は前回台帳を参照できる。2015〜2025年は以前の研究で参照済みであり、3期間の区分を真の未使用データとは保証できない。

下記コードをプロジェクト直下のPowerShellで `@'` と `'@ | python -B -` で挟むと全件品質・部分足数・SHA同一性を再現できる。検査の終了コードは0。元のBars.dat、ticks.dat、info.datへの書込みは行っていない。

```python
from datetime import datetime
import hashlib
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, "src")
from forextester_backtest.data import HistoryRepository, OLE_EPOCH

repository = HistoryRepository()
previous = Path("docs/quant_organization/experiments/luxalgo_sweeps_m15_20261120/data_inventory.md")
fingerprints = previous.read_text(encoding="utf-8")
for symbol in ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF"]:
    count = repository.summary(symbol).bar_count
    raw = np.memmap(repository.root / symbol / "Bars.dat", dtype="<f8", mode="r",
                    offset=4, shape=(count, 6))
    bounds = [(datetime(year, 1, 1) - OLE_EPOCH).total_seconds() / 86400
              for year in (2015, 2026)]
    first, last = np.searchsorted(raw[:, 0], bounds)
    records = raw[first:last]
    seconds = np.rint((records[:, 0] - 25569) * 86400).astype(np.int64)
    assert np.all(np.diff(seconds) > 0) and np.all(seconds % 60 == 0)
    assert np.isfinite(records[:, :5]).all() and (records[:, 1:5] > 0).all()
    assert (records[:, 3] >= np.maximum(records[:, 1], records[:, 2])).all()
    assert (records[:, 4] <= np.minimum(records[:, 1], records[:, 2])).all()
    assert (records[:, 3] >= records[:, 4]).all()
    print(symbol, "M1", len(records))
    for duration in (900, 14400):
        buckets = seconds // duration * duration
        starts = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
        ends = np.r_[starts[1:], len(records)]
        complete = (ends - starts == duration // 60) & (seconds[starts] == buckets[starts])
        print("duration", duration, "bars", len(starts), "partial", int((~complete).sum()))
    for name in ("Bars.dat", "info.dat"):
        with (repository.root / symbol / name).open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assert digest in fingerprints
        print(name, digest)
```

埋込コードを抽出した `ruff check --stdin-filename data_inventory.py -` は合格。同じ埋込コードの実行は終了コード0で表の件数と全10SHA一致を再現した。引継ぎ先は研究責任者と独立検証担当。実走後の入力スライス、時間足ごとの保存時刻アンカー、費用、USDCHF除外感度を監査する。
