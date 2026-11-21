# 独立検証

全5通貨・3期間の48,436取引を別実装で再計算した。ウォームアップ込み53,259件の全シグナル列と、全取引のシグナル時刻、約定時刻、決済時刻、方向、Entry・SL・TP・Exit価格、費用前後Rを突合せ、不一致0件。R計算の浮動小数点差は最大8.881784197001252e-16。各区分の入力M1スライスSHA256も15件すべて一致した。

デフォルトOnly Wicks、Swings=5、15分足スイープ逆張り・翌実在足始値・SLヒゲ先・TP全決済1Rの追加売買契約で、費用前勝率49.76%、往復1pip後46.28%、費用後PF_R 0.450だった。15区分すべてで費用後平均Rが負。記述統計を再現確認済みとし、今回の売買契約の採用は不採用とする。

## 検証結果

勝率は金銭損益が正の決済件数を分母全件で割った。経済的建値としてabs(R)≤1e-10を数値丸めし、費用後439件の建値は勝ちの分子に含めない。独立コードの`net_wins`は浮動小数点をそのまま比較する診断値で、正式集計には`economic_net_wins`を使う。TPを保存価格の桁数に丸め、同一価格の高安到達が二進浮動小数点で取りこぼされる問題を修正してから最終結果を照合した。

| 通貨 | 期間 | 取引数 | 費用前勝率 | 費用後勝率 | 費用後PF_R | 平均netR | 最大実現DD_R |
|---|---|---:|---:|---:|---:|---:|---:|
| USDJPY | 2017-2019 | 3,364 | 51.75% | 48.25% | 0.491 | -0.353 | 1189.97 |
| USDJPY | 2020-2022 | 3,336 | 49.79% | 45.80% | 0.439 | -0.413 | 1380.48 |
| USDJPY | 2023-2025 | 3,252 | 47.20% | 45.73% | 0.532 | -0.321 | 1044.05 |
| EURUSD | 2017-2019 | 3,465 | 49.15% | 44.76% | 0.407 | -0.451 | 1563.22 |
| EURUSD | 2020-2022 | 3,423 | 50.63% | 46.86% | 0.455 | -0.394 | 1350.30 |
| EURUSD | 2023-2025 | 3,383 | 49.36% | 44.52% | 0.383 | -0.492 | 1663.67 |
| GBPUSD | 2017-2019 | 3,539 | 50.10% | 47.61% | 0.528 | -0.320 | 1133.28 |
| GBPUSD | 2020-2022 | 3,486 | 49.66% | 47.65% | 0.541 | -0.309 | 1080.51 |
| GBPUSD | 2023-2025 | 3,480 | 50.34% | 47.61% | 0.469 | -0.383 | 1341.67 |
| AUDUSD | 2017-2019 | 3,478 | 48.85% | 43.53% | 0.340 | -0.539 | 1875.30 |
| AUDUSD | 2020-2022 | 3,575 | 50.97% | 47.44% | 0.455 | -0.396 | 1417.21 |
| AUDUSD | 2023-2025 | 3,512 | 49.94% | 45.07% | 0.367 | -0.508 | 1782.95 |
| USDCHF | 2017-2019 | 2,189 | 48.01% | 45.32% | 0.475 | -0.368 | 813.22 |
| USDCHF | 2020-2022 | 2,212 | 49.46% | 47.69% | 0.530 | -0.314 | 697.11 |
| USDCHF | 2023-2025 | 2,742 | 50.44% | 46.54% | 0.431 | -0.425 | 1165.75 |

M1同分でSL・TP両到達590件はSLを先にした。SLギャップ1,922件は実在M1始値、TPギャップ1,983件は指値価格で決済した。期末清算3件を全取引に含めた。1取引の初期価格リスクを1Rとし、異なるクオート通貨の金額を合算していない。最大実現DDは決済損益を積み上げたRで、含み損・残高複利運用のDDは対象外。

往復2pipの追加感度計算では全15区分のPF_Rが0.129〜0.305に低下した。Swingsやエントリー条件の探索は候補予算1の記述実験のため実施していない。

## 仕様・先読み・制約

1. ピボットは左右5本、右側5本が確定したバーで登録した。同値の極値は右端優先。未確定上位足は利用していない。スイープは高安の厳密な貫通とレベル内への終値復帰で判定した。
2. 2000本超のレベルはそのバーの判定後に削除した。1レベル1回のスイープ、同方向の複数レベルは1件へ統合、両方向同時は見送りとした。最終コードのOnly Wicksで一度使ったレベルを即削除する簡略化は、以後のシグナルが出ない原版のwic状態と同値。
3. 実在M1を1本以上含む15分バケットを使用し、次の実在15分バケットの最初のM1始値で約定する。週末・休場を跨ぐことがある。M1未記録中の価格経路と同分内の順序は観測できない。
4. 保存時刻のタイムゾーンとBid/Ask種別は未確認。固定往復1pipは保存設定のspread 1.1〜1.5pipより低い費用シナリオ。変動spread、追加滑り、手数料、資金調達費は計算に加えていない。
5. 2017〜2019、2020〜2022、2023〜2025は既に研究で閲覧された履歴。独立再実装は同一市場履歴の再現確認であり、期間区分の独立性や未閲覧性を保証するものではない。原版ロジックは公開Pineミラーと作者の説明を参照し、TradingView上の現行コード・チャートとのバー単位突合せは未実施。

原典説明と公開コードの参照先は以下。

- [作者のTradingView公開ページ](https://jp.tradingview.com/script/JRqryeJ5-Liquidity-Sweeps-LuxAlgo/)
- [LuxAlgo名義Pineコードの公開ミラー](https://indie-script.github.io/indicators/Liquidity%20Sweeps/Liquidity%20Sweeps.pinescript5)

## 入出力識別子と引継ぎ

| 対象 | SHA256 |
|---|---|
| 研究コード | `fa0308b881819589e59a90af546fda944fdeb84334096f508d1f6bb5ad4d7468` |
| protocol.json | `67e2f1916af803e38a23881c9b672f022da1552f3c66944457c84da4038cb788` |
| results.json | `8c5bf5cd53931f187a4d3ce636143d48ec9ca643905f5fe0102555f329c53b75` |
| trades.csv.gz | `ee71ec40f73554652be29e4c16e2eadb7c7aeb70f0ba467f1057e1f0919f837c` |

研究コードと仕様の実測SHAはresults.json記録値と一致した。再現コードは以下に保存した。PowerShellでPythonコードブロックを抽出し `python -` に渡して実行する。全15区分の再計算・全件照合は終了コード0。コードブロックに `python -m ruff check --stdin-filename validation_luxalgo.py -` を実行し、最終結果はAll checks passed。品質監査担当へ数値と制約を引き継ぐ。

```powershell
$validationText = Get-Content -Raw -Encoding utf8 docs/quant_organization/experiments/luxalgo_sweeps_m15_20261120/validation.md
$validationCode = [regex]::Match($validationText, '(?s)```python\r?\n(.*?)```').Groups[1].Value
$validationCode | python -m ruff check --stdin-filename validation_luxalgo.py -
$validationCode | python -
```

## 再現コード

次のコードをこのファイルから抽出してPython標準入力で実行する。研究実装の読取・集約・シグナル・約定関数は呼び出さない。

```python
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys

import numpy as np


def stamp(text):
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


def independent(symbol, year):
    source = Path('C:/ForexTester6/data/History') / symbol / 'Bars.dat'
    begin, finish = stamp(f'{year}-01-01'), stamp(f'{year + 3}-01-01')
    with source.open('rb') as stream:
        count = struct.unpack('<I', stream.read(4))[0]
    slots = (source.stat().st_size - 4) // 48
    if not 0 < count <= slots:
        raise ValueError('Source header requires separate prefix validation')
    raw = np.memmap(source, dtype='<f8', mode='r', offset=4, shape=(count, 6))
    a, b = np.searchsorted(raw[:, 0], [(begin - 60 * 86400) / 86400 + 25569,
                                     finish / 86400 + 25569])
    used = raw[a:b]
    times = np.rint((used[:, 0] - 25569) * 86400).astype(np.int64)
    prices = np.asarray(used[:, [1, 3, 4, 2]])
    buckets = times // 900 * 900
    starts = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
    ends = np.r_[starts[1:], len(times)]
    highs = np.maximum.reduceat(prices[:, 1], starts)
    lows = np.minimum.reduceat(prices[:, 2], starts)
    closes = prices[ends - 1, 3]
    high_levels, low_levels = [], []
    signals = np.zeros(len(starts), dtype=np.int8)
    both = 0
    for bar in range(len(starts)):
        pivot = bar - 5
        if pivot >= 5:
            if highs[pivot] >= highs[pivot - 5:pivot].max() and highs[pivot] > highs[pivot + 1:bar + 1].max():
                high_levels.append([pivot, highs[pivot], False])
            if lows[pivot] <= lows[pivot - 5:pivot].min() and lows[pivot] < lows[pivot + 1:bar + 1].min():
                low_levels.append([pivot, lows[pivot], False])
        bearish, bullish = False, False
        keep = []
        for pivot, value, taken in high_levels:
            if closes[bar] > value:
                continue
            if not taken and highs[bar] > value and closes[bar] < value:
                bearish, taken = True, True
            if bar - pivot <= 2000:
                keep.append([pivot, value, taken])
        high_levels = keep
        keep = []
        for pivot, value, taken in low_levels:
            if closes[bar] < value:
                continue
            if not taken and lows[bar] < value and closes[bar] > value:
                bullish, taken = True, True
            if bar - pivot <= 2000:
                keep.append([pivot, value, taken])
        low_levels = keep
        if bullish and bearish:
            both += int(times[starts[bar]] >= begin)
        else:
            signals[bar] = int(bullish) - int(bearish)
    rows = []
    busy_until = -1
    pip = .01 if symbol.endswith('JPY') else .0001
    for bar in np.flatnonzero(signals):
        if bar + 1 == len(starts) or buckets[starts[bar]] < begin:
            continue
        if times[ends[bar] - 1] < busy_until:
            continue
        entry_index = starts[bar + 1]
        entry = prices[entry_index, 0]
        side = int(signals[bar])
        stop = lows[bar] if side == 1 else highs[bar]
        risk = side * (entry - stop)
        if risk <= 0:
            continue
        target = round(entry + side * risk, 3 if symbol.endswith('JPY') else 5)
        exit_index = len(times) - 1
        exit_price = prices[exit_index, 3]
        reason = 'period_end'
        ambiguous = False
        for minute in range(entry_index, len(times)):
            opened, high, low, _ = prices[minute]
            stop_open = side * (opened - stop) <= 0
            target_open = side * (opened - target) >= 0
            stop_hit = low <= stop if side == 1 else high >= stop
            target_hit = high >= target if side == 1 else low <= target
            if stop_open:
                exit_index, exit_price, reason = minute, opened, 'stop_gap'
                break
            if target_open:
                exit_index, exit_price, reason = minute, target, 'target_gap'
                break
            if stop_hit or target_hit:
                ambiguous = bool(stop_hit and target_hit)
                exit_index = minute
                exit_price = stop if stop_hit else target
                reason = 'stop' if stop_hit else 'target'
                break
        busy_until = int(times[exit_index])
        gross_r = side * (exit_price - entry) / risk
        rows.append(dict(symbol=symbol, signal_time=int(buckets[starts[bar]]),
                         entry_time=int(times[entry_index]), exit_time=busy_until,
                         side=side, entry=entry, stop=stop, target=target,
                         exit=exit_price, gross_r=gross_r,
                         net_r=gross_r - pip / risk, reason=reason, ambiguous=ambiguous))
    net = np.array([row['net_r'] for row in rows])
    gross = np.array([row['gross_r'] for row in rows])
    net2 = 2 * net - gross
    curve = np.r_[0., net.cumsum()]
    summary = dict(symbol=symbol, period=f'{year}-{year + 2}', trades=len(rows),
                   raw_slice_sha256=hashlib.sha256(memoryview(used)).hexdigest(),
                   gross_wins=int((gross > 0).sum()), net_wins=int((net > 0).sum()),
                   gross_win_rate=float((gross > 0).mean()), net_win_rate=float((net > 0).mean()),
                   net_pf=float(net[net > 0].sum() / -net[net < 0].sum()),
                   economic_net_wins=int((net > 1e-10).sum()),
                   economic_net_breakevens=int((abs(net) <= 1e-10).sum()),
                   max_realized_dd_r=float((np.maximum.accumulate(curve) - curve).max()),
                   mean_net_r=float(net.mean()), total_net_r=float(net.sum()),
                   net_pf_2pip=float(net2[net2 > 0].sum() / -net2[net2 < 0].sum()),
                   two_sided_bars=both, ambiguous=int(sum(row['ambiguous'] for row in rows)))
    return rows, summary, signals, times, starts, prices


result = Path('agent_runs/luxalgo_sweeps_m15_20261120/trades.csv.gz')
with gzip.open(result, 'rt', encoding='utf-8-sig', newline='') as stream:
    research = list(csv.DictReader(stream))
with result.with_name('results.json').open(encoding='utf-8-sig') as stream:
    research_summary = json.load(stream)
sys.path.insert(0, 'src')
implementation = importlib.import_module('scripts.research_luxalgo_sweeps_m15')

total_rows, total_signals, max_difference, mismatches = 0, 0, 0., 0
for symbol in ['USDJPY', 'EURUSD', 'GBPUSD', 'AUDUSD', 'USDCHF']:
    for year in [2017, 2020, 2023]:
        rows, summary, signals, times, starts, prices = independent(symbol, year)
        expected_signals = []
        for bar in np.flatnonzero(signals):
            if bar + 1 == len(starts):
                continue
            side = int(signals[bar])
            stop = (prices[starts[bar]:starts[bar + 1], 2].min() if side == 1
                    else prices[starts[bar]:starts[bar + 1], 1].max())
            expected_signals.append((int(times[starts[bar + 1]]), side, float(stop),
                                     int(times[starts[bar]] // 900 * 900)))
        actual_signals, _ = implementation.wick_signals(implementation.aggregate_m15(times, prices))
        assert expected_signals == actual_signals
        total_signals += len(expected_signals)
        other = [r for r in research if r['symbol'] == symbol
                 and r['phase'] == f'{year}-{year + 2}']
        other.sort(key=lambda r: r['entry_time'])
        assert len(rows) == len(other)
        record = next(r for r in research_summary['records']
                      if r['symbol'] == symbol and r['phase'] == summary['period'])
        assert summary['raw_slice_sha256'] == record['inputs']['raw_slice_sha256']
        for row, observed in zip(rows, other, strict=True):
            for key in ['signal_time', 'entry_time', 'exit_time']:
                mismatches += int(row[key] != stamp(observed[key]))
            mismatches += int(row['side'] != int(observed['side']))
            for key in ['entry', 'stop', 'target', 'exit', 'gross_r', 'net_r']:
                difference = abs(row[key] - float(observed[key]))
                max_difference = max(max_difference, difference)
                mismatches += int(difference > 1e-10)
        total_rows += len(rows)
        print(json.dumps(summary), flush=True)
print(json.dumps(dict(compared_rows=total_rows, compared_signals=total_signals, mismatches=mismatches,
                      max_absolute_difference=max_difference)), flush=True)
assert mismatches == 0
```
