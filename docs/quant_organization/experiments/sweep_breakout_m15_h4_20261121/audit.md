# M15・H4スイープ後ブレイクの監査

2026年11月21日 JSTに実走成果物を監査した。取引CSV全30,854件から研究側の集計関数を呼ばず2,321項目を再集計し、全項目が一致した。取引の損益式154,270項目、原M1の5入力スライス、Pine・実装・依存4ファイルのSHA256も一致した。5通貨、USDCHFを除く4通貨の両方で、M15・H4の買い・売り・合計の費用後PF_Rは全6区分で1未満だった。

## 入力と成果物の同一性

| 成果物 | SHA256 |
|---|---|
| `agent_runs/sweep_breakout_m15_h4_20261121/trades.csv.gz` | `2a938f275c0d6308c2c47312d7d7b5e37a06a9014b4117c8eaf497f4ed03eb05` |
| `agent_runs/sweep_breakout_m15_h4_20261121/results.json` | `e3fe2709963778a17de4ac7d01deba184363ea083bc1941be96a30ac2fd83888` |
| `scripts/research_sweep_breakout_m15_h4.py` | `510c2f4636229468f4fafbe8725e8ca9f62f2bf6901d12091a662c7d4a4c1e44` |
| `protocol.json` | `8eea5c4fda3b3bcdf18e530cee671e525cbbb9eff17cc36a860c449feed17a62` |
| `scripts/tradingview/sweep_breakdown_levels_m15.pine` | `695ccb5812f53f552efc2509491f6ac0559930c5c9bcecddea2707198e2def62` |

実ファイルのSHA256は研究JSONと一致。依存の `research_luxalgo_sweeps_m15.py`、`research_fx65_pf15.py`、`research_dinapoli_3x3_daily.py`、`src/forextester_backtest/data.py` のSHA256もJSONの依存識別子に一致した。原 `Bars.dat` の `record_start` 以上 `record_end_exclusive` 未満を読取専用で再読込した5通貨のスライスSHA256が一致した。

再集計はM15・H4それぞれの買い・売り・合計、3期間、5通貨、USDCHF除外、10通貨時間足区分を対象にした。件数、決済理由、費用前後の勝敗・建値・勝率・建値込み勝率・PF_R・合計R・平均R・実現最大DD_R・合計pipsの2,321項目が一致。数値照合の許容差は相対1e-10または絶対1e-7。

各取引で初期リスク、費用前pips、`net_pips = gross_pips - 1`、`gross_r = gross_pips / risk_pips`、`net_r = net_pips / risk_pips` の5式を独立照合し、30,854件×5式の154,270項目が一致した。

独立検証成果物 `independent_results.json` の比較記録は30,854件、欠落0、追加0、差分0、最大絶対差3.552713678800501e-15。そこに保存された研究CSV・JSONのSHA256は上表の現成果物と一致した。[独立検証](validation.md)

## 全6区分の費用前後

5通貨はUSDJPY・EURUSD・GBPUSD・AUDUSD・USDCHF。各取引を初期リスク1Rで等重みとし、往復固定1 pipを控除した。

| 時間足・方向 | 件数 | 費用前勝率 | 費用後勝率 | 費用後建値込み勝率 | 費用後PF_R |
|---|---:|---:|---:|---:|---:|
| M15 買い | 14,649 | 47.1705% | 43.9689% | 44.7266% | 0.410029 |
| M15 売り | 14,204 | 48.1062% | 45.0014% | 45.9096% | 0.443155 |
| M15 合計 | 28,853 | 47.6311% | 44.4772% | 45.3090% | 0.425999 |
| H4 買い | 1,011 | 48.4669% | 48.3680% | 48.3680% | 0.786480 |
| H4 売り | 990 | 49.3939% | 49.1919% | 49.3939% | 0.813609 |
| H4 合計 | 2,001 | 48.9255% | 48.7756% | 48.8756% | 0.799692 |

M15の費用後は12,833勝、15,780敗、240建値。H4は976勝、1,023敗、2建値。R損益が1e-10超を勝ち、絶対値1e-10以下を建値とし、全決済を分母にする。建値込み表示は勝率の分子に建値を加える。PF_Rは経済損益の正R総和と負R総和の絶対値の比。

## USDCHF除外の感度

USDCHFのM1は単一価格や粗い価格刻みが多く、前回のサンプルで同保存時刻のtickと価格が一致しなかった。今回も原ファイルSHAは同一。[データ台帳](data_inventory.md)

| 4通貨の時間足・方向 | 件数 | 費用前勝率 | 費用後勝率 | 費用後建値込み勝率 | 費用後PF_R |
|---|---:|---:|---:|---:|---:|
| M15 買い | 12,454 | 47.3824% | 44.1063% | 44.6684% | 0.407191 |
| M15 売り | 12,009 | 47.9224% | 44.8164% | 45.4659% | 0.435665 |
| M15 合計 | 24,463 | 47.6475% | 44.4549% | 45.0599% | 0.420902 |
| H4 買い | 825 | 48.9697% | 48.8485% | 48.8485% | 0.807971 |
| H4 売り | 805 | 49.6894% | 49.6894% | 49.6894% | 0.831654 |
| H4 合計 | 1,630 | 49.3252% | 49.2638% | 49.2638% | 0.819503 |

4通貨M15の費用後は10,875勝、13,440敗、148建値。4通貨H4は803勝、827敗、建値0。USDCHF除外でも全6区分の費用後PF_Rは1未満。

## 3期間の照合

期間はエントリーの保存年月日で分けた。2015年から状態と建玉を継続し、3年境界でリセットしない。境界をまたいで決済した取引も元のエントリー期間へ含める。

| 5通貨の期間 | 時間足・方向 | 件数 | 費用前勝率 | 費用後勝率 | 費用後PF_R |
|---|---|---:|---:|---:|---:|
| 2017〜2019 | M15 買い | 4,736 | 47.1073% | 44.0034% | 0.403353 |
| 2017〜2019 | M15 売り | 4,615 | 47.5840% | 44.2687% | 0.422798 |
| 2017〜2019 | M15 合計 | 9,351 | 47.3425% | 44.1343% | 0.412796 |
| 2020〜2022 | M15 買い | 4,822 | 47.1589% | 44.5458% | 0.437521 |
| 2020〜2022 | M15 売り | 4,744 | 48.7563% | 45.7420% | 0.481983 |
| 2020〜2022 | M15 合計 | 9,566 | 47.9511% | 45.1390% | 0.458957 |
| 2023〜2025 | M15 買い | 5,091 | 47.2402% | 43.3903% | 0.391561 |
| 2023〜2025 | M15 売り | 4,845 | 47.9670% | 44.9742% | 0.427222 |
| 2023〜2025 | M15 合計 | 9,936 | 47.5946% | 44.1626% | 0.408634 |
| 2017〜2019 | H4 買い | 329 | 46.2006% | 46.2006% | 0.717348 |
| 2017〜2019 | H4 売り | 329 | 48.6322% | 48.6322% | 0.776088 |
| 2017〜2019 | H4 合計 | 658 | 47.4164% | 47.4164% | 0.746026 |
| 2020〜2022 | H4 買い | 323 | 51.7028% | 51.7028% | 0.898361 |
| 2020〜2022 | H4 売り | 317 | 50.1577% | 50.1577% | 0.847976 |
| 2020〜2022 | H4 合計 | 640 | 50.9375% | 50.9375% | 0.873256 |
| 2023〜2025 | H4 買い | 359 | 47.6323% | 47.3538% | 0.758086 |
| 2023〜2025 | H4 売り | 344 | 49.4186% | 48.8372% | 0.819377 |
| 2023〜2025 | H4 合計 | 703 | 48.5064% | 48.0797% | 0.787257 |

USDCHFを除いた4通貨の期間別合計も独立に再集計した。

| 4通貨の期間 | 時間足 | 件数 | 費用前勝率 | 費用後勝率 | 費用後PF_R |
|---|---|---:|---:|---:|---:|
| 2017〜2019 | M15 | 7,982 | 47.0684% | 43.7985% | 0.398299 |
| 2020〜2022 | M15 | 8,166 | 48.1019% | 45.2119% | 0.452183 |
| 2023〜2025 | M15 | 8,315 | 47.7571% | 44.3416% | 0.413798 |
| 2017〜2019 | H4 | 542 | 46.6790% | 46.6790% | 0.729746 |
| 2020〜2022 | H4 | 514 | 51.3619% | 51.3619% | 0.888124 |
| 2023〜2025 | H4 | 574 | 50.0000% | 49.8258% | 0.850669 |

## 極端値と適用範囲

M15の初期リスク中央値は4.3 pips、最小約0.1 pip、1 pip未満1,674件。H4の中央値は18.7 pips、最小約0.6 pip、1 pip未満3件。狭い初期リスクに対する固定1 pip費用はR損益への影響が大きい。

最悪の費用後損益はEURUSD M15買いの−25.4407R。保存時刻2022-02-25 21:30に1.12728でエントリーし、SL 1.12669、TP 1.12787。週末を越えた2022-02-27 22:00の原M1始値1.11237でストップギャップとなった。監査で同M1を再読込し、始値1.11237、高値1.11287、安値1.11225、終値1.11285を確認した。原データと約定規約が一致する極端値である。

SL・TPの両方へ同じM1で到達した決済はM15で338件、H4で2件。凍結仕様のSL優先を適用した。真の足内順序は未確認。M15で1件、H4で2件が3年の集計境界をまたいで決済した。保存2025年末の強制清算はH4で1件。

保存日時のタイムゾーンとM1価格のBid/Ask種別は未確定。H4は保存日付00時アンカーであり、TradingView配信元の4時間足との同一性は未確認。往復固定1 pipは設定spread 1.1〜1.5 pipsより低いシナリオ。実約定費用、追加の滑り、資金制約、スワップを含む口座損益への換算は対象外。過去に参照済みの期間を使う記述的検証である。

## 再現コードと引継ぎ

下記コードをプロジェクト直下でPowerShellの `@'` と `'@ | python -B -` で挟むと、CSVからJSONの2,321項目を再照合できる。研究の集計関数は呼び出さない。

```python
from collections import Counter
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np

directory = Path("agent_runs/sweep_breakout_m15_h4_20261121")
reported = json.loads((directory / "results.json").read_text(encoding="utf-8"))
with gzip.open(directory / "trades.csv.gz", "rt", encoding="utf-8") as stream:
    trades = list(csv.DictReader(stream))


def calculate(rows):
    result = dict(trades=len(rows), exit_reasons=dict(Counter(row["reason"] for row in rows)))
    for prefix in ("gross", "net"):
        values = np.array([float(row[prefix + "_r"]) for row in rows])
        wins = int((values > 1e-10).sum())
        breakevens = int((abs(values) <= 1e-10).sum())
        curve = np.r_[0., values.cumsum()]
        loss = -values[values < -1e-10].sum()
        result[prefix] = dict(
            wins=wins, losses=len(values) - wins - breakevens, breakevens=breakevens,
            win_rate=wins / len(values) if len(values) else None,
            win_rate_including_breakevens=(wins + breakevens) / len(values) if len(values) else None,
            pf_r=float(values[values > 1e-10].sum() / loss) if loss else None,
            total_r=float(values.sum()), mean_r=float(values.mean()) if len(values) else None,
            max_realized_dd_r=float((np.maximum.accumulate(curve) - curve).max()),
            total_pips=sum(float(row[prefix + "_pips"]) for row in rows),
        )
    return result


def compare(actual, expected):
    count = 0
    for key, value in actual.items():
        if isinstance(value, dict):
            count += compare(value, expected[key])
        else:
            count += 1
            if isinstance(value, (int, float)) and expected[key] is not None:
                assert math.isclose(value, expected[key], rel_tol=1e-10, abs_tol=1e-7)
            else:
                assert value == expected[key]
    return count


def compare_directions(rows, expected):
    count = 0
    for direction in ("all", "long", "short"):
        subset = [row for row in rows if direction == "all" or row["direction"] == direction]
        count += compare(calculate(subset), expected[direction])
    return count


checks = 0
for timeframe, expected in reported["by_timeframe"].items():
    subset = [row for row in trades if row["timeframe"] == timeframe]
    checks += compare_directions(subset, expected)
    checks += compare_directions([row for row in subset if row["symbol"] != "USDCHF"],
                                 expected["excluding_usdchf"])
    for phase, metrics in expected["by_phase"].items():
        checks += compare_directions([row for row in subset if row["phase"] == phase], metrics)
    for symbol, metrics in expected["by_symbol"].items():
        checks += compare_directions([row for row in subset if row["symbol"] == symbol], metrics)
for record in reported["records"]:
    subset = [row for row in trades
              if row["symbol"] == record["symbol"] and row["timeframe"] == record["timeframe"]]
    checks += compare_directions(subset, record["metrics"])
print(json.dumps(dict(compared_fields=checks, mismatches=0, trades=len(trades))))
```

埋込コードを抽出した `ruff check --stdin-filename audit.py -` は合格。同じコードの実行は終了コード0で2,321項目が一致した。監査担当の編集範囲は本 `audit.md` と `data_inventory.md`。研究責任者へ、6区分の照合一致、USDCHF除外感度、H4時刻アンカー、固定費用と初期リスクの関係を引き継ぐ。
