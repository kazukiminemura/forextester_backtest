# Liquidity Sweeps 15分足のデータ台帳

2026年11月20日 JSTに、データ品質担当が `C:/ForexTester6/data/History` の5通貨を読取検査した。2017年1月1日以上2026年1月1日未満の保存M1全16,697,226本を検査し、重複、逆順、非有限価格、非正価格、OHLC不整合、分境界ずれはすべて0本だった。この範囲は価格を使用する記述的検証に利用できる。保存時刻のタイムゾーン、M1のBid/Ask種別、欠落時間中の値動きには未確認事項がある。

## 入力と検査範囲

`HistoryRepository().summary(symbol)` と `.metadata(symbol)` で有効レコード数、保存端点、銘柄設定を取得した。`Bars.dat` はヘッダ4バイトに続くlittle-endianの6 doublesで、列順は時刻、Open、Close、High、Low、volume。取得した有効レコード数を上限とする読取専用 `numpy.memmap` を使い、対象期間の全レコードを検査した。ヘッダの後ろに存在する未使用領域は価格データに含めない。2017年より前と2026年の価格品質は今回の全件検査の対象外。

| 通貨 | 保存M1全件数 | 保存開始 | 保存終了 | 対象期間M1 |
|---|---:|---|---|---:|
| USDJPY | 8,534,100 | 2003-05-06 00:00 | 2026-09-07 23:59 | 3,350,600 |
| EURUSD | 8,567,792 | 2003-05-06 00:00 | 2026-09-07 23:59 | 3,349,411 |
| GBPUSD | 8,680,197 | 2003-05-06 00:00 | 2026-09-07 23:59 | 3,351,670 |
| AUDUSD | 6,286,639 | 2009-10-01 00:00 | 2026-09-07 23:59 | 3,341,322 |
| USDCHF | 9,226,394 | 2001-01-02 23:01 | 2026-09-07 23:59 | 3,304,223 |

対象期間の初回はEURUSDが2017-01-01 22:00、USDJPY・GBPUSD・AUDUSDが同22:04、USDCHFが2017-01-02 07:01。末尾はいずれも2025-12-31 21:58。これらは保存時刻そのものを記載している。

| 通貨 | 2017〜2019年M1 | 2020〜2022年M1 | 2023〜2025年M1 |
|---|---:|---:|---:|
| USDJPY | 1,117,839 | 1,116,071 | 1,116,690 |
| EURUSD | 1,118,799 | 1,115,368 | 1,115,244 |
| GBPUSD | 1,118,751 | 1,117,866 | 1,115,053 |
| AUDUSD | 1,117,092 | 1,114,786 | 1,109,444 |
| USDCHF | 1,097,421 | 1,100,214 | 1,106,588 |

## 欠落時間と15分集約

OLE時刻を最寄り整数秒へ丸めた。丸め前との差は最大0.0000002385秒、丸め後の秒は全件で60の倍数だった。保存日付の00分、15分、30分、45分を起点として、始値は最初、高値は最大、安値は最小、終値は最後、volumeは合計とする。存在するM1から集約し、観測が0本のバケットは生成しない。

| 通貨 | 60秒超の間隔数 | 端点間の未記録分数 | 最大間隔 分 | 存在するM15 | M1が15本未満のM15 |
|---|---:|---:|---:|---:|---:|
| USDJPY | 10,831 | 1,381,235 | 4,321 | 224,373 | 7,764 |
| EURUSD | 11,215 | 1,382,428 | 4,321 | 224,314 | 7,882 |
| GBPUSD | 8,679 | 1,380,165 | 4,321 | 224,308 | 6,071 |
| AUDUSD | 12,190 | 1,390,513 | 4,325 | 223,943 | 8,206 |
| USDCHF | 3,339 | 1,427,075 | 4,931 | 220,937 | 2,593 |

未記録分数には週末と休場が含まれる。取引時間表との照合は行っていないため、営業中の欠損件数は未確定。部分バケットは1〜14本のM1を含む。価格を補間しない場合でも、部分バケットの採否と次足エントリー時の時間隔を実験仕様に記録する必要がある。

独立集約と `HistoryRepository.bars(..., timeframe="15m")` の照合はサンプル検査。各通貨の2017-01-01〜2017-01-08と2025-12-25〜2026-01-01の10区間、M1合計64,737本、M15合計4,432本について時刻・OHLC・volumeが全件一致した。対象期間の全M15との照合は実施していない。

## 価格・出来高・費用設定

各通貨とも価格4列の非有限・非正価格、HighがOpen/Closeを下回る、LowがOpen/Closeを上回る、HighがLowを下回るレコードは0本。volumeの非有限・ゼロは0本。負volumeはUSDJPY5、EURUSD12、GBPUSD3、AUDUSD6、USDCHF0の合計26本。出来高を使う条件を追加する場合は採否の仕様が必要。

| 通貨 | decimals | 1 pipの価格幅 | 設定spread pips | lot size | 損益のクオート通貨 |
|---|---:|---:|---:|---:|---|
| USDJPY | 3 | 0.01 | 1.2 | 100,000 | JPY |
| EURUSD | 5 | 0.0001 | 1.1 | 100,000 | USD |
| GBPUSD | 5 | 0.0001 | 1.4 | 100,000 | USD |
| AUDUSD | 5 | 0.0001 | 1.2 | 100,000 | USD |
| USDCHF | 5 | 0.0001 | 1.5 | 100,000 | CHF |

根拠は各 `info.dat` の `decimals`、`spread`、`lot`、`BaseCurrency` と `LotCurrency` および `InstrumentMetadata.pnl_currency` の6文字FX通貨コード処理。1 pipは10 pointsとして計算した。全通貨の `Broker=Advanced Data Feed`、`ApplyCommission=0`、`CommPerLot=0.00`、`SwapLong=0.0000`、`SwapShort=0.0000`。これらは保存設定であり、2017〜2025年の実約定コスト履歴は未確認。往復固定1.0 pipを研究で使用する場合は、設定spreadよりも低い独立シナリオとして明示する。

M1レコードにBid/Askフラグはなく、価格種別をファイル構造から確定できない。tickファイルの存在と端点は `summary` で確認したが、tickの全件品質、M1との価格一致、過去の変動spreadは今回の検査対象外。保存日時にタイムゾーン情報はなく、UTCまたはJSTへの換算は今回行っていない。

## 入力識別子

SHA256は2026年11月20日にファイル全体を読んで算出した。

| 通貨 | Bars.dat SHA256 | info.dat SHA256 |
|---|---|---|
| USDJPY | `31fc474177e6b2235dbd6a46760d5f428d53de3bc864120677647f651b1828a7` | `cea2c8b470c145f236577f466937e8c5b04a17960ac5a4f281769338b65b38c4` |
| EURUSD | `a7c97f167fb1b0bb016872f73796d1870b68286395b9a5818a797301065d016c` | `2bf533cbaad2715e47cdb477de21c3e894bf61430a7d6ee82130f9f54fe31541` |
| GBPUSD | `573be0820fb6ea2147266084bbec85bb3824b0a7e0eb9032edf10bf4d3d3d601` | `fd4a6244c76ef686a52e43d9f773b77354e506fbbd8adadc08f2b81dc8dfdf31` |
| AUDUSD | `1bbe99afea80fb4dc0c70086907d7475f66b73e8d66a41e04df54fe7dc4bd59d` | `0492503e1636a40759b41fbabf638d2de18432bfee41027ac1f2b5ae7ffc2278` |
| USDCHF | `9ab6652ea1561439c660e348a690d98807e35c399d208b5111029fa03a411fc5` | `34465f07cd3b9546d2a9986e0352e2fdc2db4b19b1e1a68b1c73a88442d58d57` |

過去の[Patrickデータ台帳](../patrick_vp_frequency_exits_20261118/data_inventory.md)にも5通貨を含む2017〜2025年の参照が記録されている。3年区分を分けても、真の未使用期間とは保証できない。

## 再現コマンドと引継ぎ

プロジェクト直下のPowerShellで、下記Pythonコードを `@'` と `'@ | python -B -` で挟んで実行する。今回の全件検査とサンプル集約照合はいずれも終了コード0。担当変更は本Markdownだけで、Pythonソースの変更は0ファイル。

```python
import hashlib
import json
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, "src")
from forextester_backtest.data import HistoryRepository, OLE_EPOCH

repository = HistoryRepository()
for symbol in ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF"]:
    summary = repository.summary(symbol)
    path = repository.root / symbol / "Bars.dat"
    raw = np.memmap(path, dtype="<f8", mode="r", offset=4,
                    shape=(summary.bar_count, 6))
    bounds = [(datetime(year, 1, 1) - OLE_EPOCH).total_seconds() / 86400
              for year in (2017, 2026)]
    first, last = np.searchsorted(raw[:, 0], bounds)
    records = raw[first:last]
    seconds = np.rint((records[:, 0] - 25569) * 86400).astype(np.int64)
    differences = np.diff(seconds)
    prices = records[:, 1:5]
    starts = np.r_[0, np.flatnonzero(np.diff(seconds // 900)) + 1]
    counts = np.diff(np.r_[starts, len(records)])
    result = {
        "symbol": symbol,
        "m1": len(records),
        "duplicate": int(np.count_nonzero(differences == 0)),
        "reversed": int(np.count_nonzero(differences < 0)),
        "off_minute": int(np.count_nonzero(seconds % 60)),
        "nonfinite_price": int(np.count_nonzero(~np.isfinite(prices).all(axis=1))),
        "nonpositive_price": int(np.count_nonzero((prices <= 0).any(axis=1))),
        "bad_ohlc": int(np.count_nonzero(
            (records[:, 3] < np.maximum(records[:, 1], records[:, 2]))
            | (records[:, 4] > np.minimum(records[:, 1], records[:, 2]))
            | (records[:, 3] < records[:, 4]))),
        "nonfinite_volume": int(np.count_nonzero(~np.isfinite(records[:, 5]))),
        "negative_volume": int(np.count_nonzero(records[:, 5] < 0)),
        "zero_volume": int(np.count_nonzero(records[:, 5] == 0)),
        "gaps": int(np.count_nonzero(differences > 60)),
        "absent_minutes": int(np.sum(differences // 60 - 1)),
        "max_gap_minutes": float(differences.max() / 60),
        "m15": len(starts),
        "partial_m15": int(np.count_nonzero(counts < 15)),
    }
    for name in ["Bars.dat", "info.dat"]:
        with (repository.root / symbol / name).open("rb") as stream:
            result[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    print(json.dumps(result))
```

引継ぎ先は研究責任者と独立検証担当。部分15分足、観測間隔をまたぐ約定、価格種別、費用シナリオを検証仕様と照合する。戦略成績と採用判定はこの台帳の対象外。
