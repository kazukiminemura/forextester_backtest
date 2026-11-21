# 15分足スイープ検証の監査

2026年11月20日 JSTに、TPを価格桁へ正規化して再実行した最終出力を監査した。取引CSV48,436件と研究結果JSONの632項目、取引ごとの損益式242,180項目、原M1の入力スライスSHA256全15区分が一致した。USDCHFの原M1には高安の情報量とtick整合性に制約があるため、主要表示には他4通貨を使い、5通貨の保存データ上の集計も参照できる形が適切。

## 照合した成果物

| 成果物 | SHA256 |
|---|---|
| `agent_runs/luxalgo_sweeps_m15_20261120/trades.csv.gz` | `ee71ec40f73554652be29e4c16e2eadb7c7aeb70f0ba467f1057e1f0919f837c` |
| `agent_runs/luxalgo_sweeps_m15_20261120/results.json` | `8c5bf5cd53931f187a4d3ce636143d48ec9ca643905f5fe0102555f329c53b75` |
| `scripts/research_luxalgo_sweeps_m15.py` | `fa0308b881819589e59a90af546fda944fdeb84334096f508d1f6bb5ad4d7468` |
| `protocol.json` | `67e2f1916af803e38a23881c9b672f022da1552f3c66944457c84da4038cb788` |

コード・protocolの実測SHAはJSON内の識別子と一致。入力はJSONの `record_start` 以上 `record_end_exclusive` 未満を原 `Bars.dat` から再読込してSHA256を計算し、ウォームアップを含む15区分すべてで一致した。検証の実行終了コードは0。

CSVから研究側の集計関数を呼ばずに、全体、3期間、5通貨、15通貨期間区分を再集計した。件数、決済理由、費用前後の勝敗・建値・勝率・建値込み勝率・PF_R・合計R・平均R・実現最大DD_R・合計pipsが632項目で一致した。数値照合の許容差は相対1e-10または絶対1e-7。

各取引の `risk_pips`、`gross_pips`、`net_pips = gross_pips - 1`、`gross_r = gross_pips / risk_pips`、`net_r = net_pips / risk_pips` も全48,436件、242,180項目で一致した。TPの価格桁正規化による再実行前の速報は今回の監査対象から更新済み。

## CSVの再集計結果

| 対象 | 件数 | 費用前勝率 | 費用後勝率 | 費用後建値込み勝率 | 費用後PF_R |
|---|---:|---:|---:|---:|---:|
| USDJPY・EURUSD・GBPUSD・AUDUSD | 41,293 | 49.8244% | 46.2427% | 46.9813% | 0.446087 |
| 上記4通貨 2017〜2019年 | 13,846 | 49.9494% | 46.0277% | 46.8439% | 0.435702 |
| 上記4通貨 2020〜2022年 | 13,820 | 50.2677% | 46.9537% | 47.6556% | 0.471444 |
| 上記4通貨 2023〜2025年 | 13,627 | 49.2478% | 45.7401% | 46.4372% | 0.431995 |
| USDCHFを含む5通貨 | 48,436 | 49.7605% | 46.2838% | 47.1901% | 0.450027 |

主要4通貨の内訳は費用後19,095勝、21,893敗、305建値。5通貨は22,418勝、25,579敗、439建値。勝敗判定はR損益が1e-10を超えれば勝ち、絶対値1e-10以下を建値とする。全決済を分母とし、建値込み勝率では建値を分子にも加える。PF_Rは正のR総和を負のR総和の絶対値で割り、建値込み表示によって変更しない。

これは今回固定した次足エントリー・スイープ極値SL・全利確1R・往復固定1 pipの売買契約による集計。保存設定のspreadは通貨別1.1〜1.5 pipsで、固定1 pipの実約定再現性は未確認。各トレードを初期リスク1Rで等重みとするPF_Rであり、一定lot口座通貨への換算は行っていない。保存日時を暦の区切りに用い、タイムゾーンは未確定。

## USDCHFの原データ制約

対象期間のM1全件を追加検査した。

| 通貨 | M1件数 | O=H=L=Cの件数 | 同率 | 全OHLCが整数pip刻みの件数 | 同率 |
|---|---:|---:|---:|---:|---:|
| USDJPY | 3,350,600 | 42,884 | 1.2799% | 6,682 | 0.1994% |
| EURUSD | 3,349,411 | 41,918 | 1.2515% | 8,179 | 0.2442% |
| GBPUSD | 3,351,670 | 36,373 | 1.0852% | 7,024 | 0.2096% |
| AUDUSD | 3,341,322 | 47,501 | 1.4216% | 8,474 | 0.2536% |
| USDCHF | 3,304,223 | 2,037,485 | 61.6631% | 2,808,419 | 84.9948% |

USDCHFの2017〜2023年はすべてのM1で全OHLCが整数pip刻み。2021年は367,036本中356,635本が単一価格で97.1662%。この価格精度と高安の情報量はinfo.datの5桁設定だけでは把握できない。

極端値の確認例はUSDCHFの2021-09-14保存時刻10:30買い。Entry 0.9214、SL 0.9213、TP 0.9215に対して、10:31の原M1はOpen=High=Low=Close=0.9200で、ストップギャップ扱いの費用前−14R、費用後−15Rとなる。同じ保存時刻10:30以上10:32以下の原tickは25件、Bid最小0.92205・最大0.92214で、M1価格と一致しなかった。この1区間のtick照合はサンプル検査で、履歴全体の時刻対応や不一致原因は未確定。

OHLC内部整合性の合格だけでは、この種の価格情報量やtickとの不一致を検出できない。USDCHFのM1高安から得た約定・勝率は保存データ上の参考値として扱う。主要4通貨の集計は同じ凍結条件・同じCSVから通貨だけを抽出した補助集計で、成績によるパラメータ再調整は行っていない。

## 狭い損切り幅と表示の留意点

5通貨全体の初期リスク中央値は4.0 pips、最小は約0.1 pip、1 pip未満は2,668件。0.1 pipリスクに1 pipを控除すると費用が10Rとなるため、損切り時の費用後−11Rは損益式と整合する。費用前プラスから費用後マイナスへ移る取引は1,245件。極端なR損失の一部はこの固定費用と狭い初期リスクに由来する。

同一M1でSLとTPの両方に触れた決済は5通貨590件、主要4通貨561件で、いずれも凍結仕様のSL優先。足内の真の順序はM1のOHLCだけから確定できない。部分15分足と休場をまたぐ次の観測始値を使用している。過去に使用した期間を再検証しており、真の未使用期間とは保証できない。

## 再現手順と引継ぎ

全件の約定・信号独立再現は[独立検証](validation.md)を参照。この監査はCSV集計・損益式・入力同一性と原データ極端値の照合を担当した。TradingViewチャート上の全スイープとの一致は未確認。

次のコードをPowerShellの `@'` と `'@ | python -B -` で挟むと、研究側の集計関数を使わず632項目を再照合できる。

```python
from collections import Counter
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np

directory = Path("agent_runs/luxalgo_sweeps_m15_20261120")
reported = json.loads((directory / "results.json").read_text(encoding="utf-8"))
with gzip.open(directory / "trades.csv.gz", "rt", encoding="utf-8") as stream:
    trades = list(csv.DictReader(stream))


def calculate(rows):
    output = dict(trades=len(rows), exit_reasons=dict(Counter(row["reason"] for row in rows)))
    for prefix in ("gross", "net"):
        values = np.array([float(row[prefix + "_r"]) for row in rows])
        wins = int((values > 1e-10).sum())
        breakevens = int((abs(values) <= 1e-10).sum())
        curve = np.r_[0., values.cumsum()]
        output[prefix] = dict(
            wins=wins, losses=len(values) - wins - breakevens, breakevens=breakevens,
            win_rate=wins / len(values),
            win_rate_including_breakevens=(wins + breakevens) / len(values),
            pf_r=float(values[values > 1e-10].sum() / -values[values < -1e-10].sum()),
            total_r=float(values.sum()), mean_r=float(values.mean()),
            max_realized_dd_r=float((np.maximum.accumulate(curve) - curve).max()),
            total_pips=sum(float(row[prefix + "_pips"]) for row in rows),
        )
    return output


def compare(actual, expected):
    count = 0
    for key, value in actual.items():
        if isinstance(value, dict):
            count += compare(value, expected[key])
        else:
            count += 1
            if isinstance(value, (int, float)):
                assert math.isclose(value, expected[key], rel_tol=1e-10, abs_tol=1e-7)
            else:
                assert value == expected[key]
    return count


checks = compare(calculate(trades), reported["overall"])
for phase, expected in reported["by_phase"].items():
    checks += compare(calculate([row for row in trades if row["phase"] == phase]), expected)
for symbol, expected in reported["by_symbol"].items():
    checks += compare(calculate([row for row in trades if row["symbol"] == symbol]), expected)
for record in reported["records"]:
    subset = [row for row in trades
              if row["symbol"] == record["symbol"] and row["phase"] == record["phase"]]
    checks += compare(calculate(subset), record["metrics"])
print(json.dumps(dict(compared_fields=checks, mismatches=0)))
print(json.dumps(calculate([row for row in trades if row["symbol"] != "USDCHF"])))
```

監査担当の編集範囲は本 `audit.md`。埋込コードを抽出した `ruff check --stdin-filename audit.py -` は全件合格、同じ埋込コードの実行は終了コード0で632項目が一致した。研究責任者へ、主要表示に4通貨を使う理由、5通貨の参考集計、費用と建値の定義を引き継ぐ。
