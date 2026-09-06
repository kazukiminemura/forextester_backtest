"""Predeclared, cost-aware daytrade filter study; never tunes on evaluation years."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.sniper import SniperReplay
from research_sniper_vip import SYMBOLS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tradingview/sniper_vip_pro_reconstruction.pine"
OUT = ROOT / "scripts/sniper_daytrade_cache"
FRAMES = (5, 15, 30, 60)
PERIODS = ((2010, 2018), (2019, 2022), (2023, 2024), (2025, 2026))
# Freeze this search before reading evaluation results. No per-symbol selection.
RULES = list(itertools.product((18, 25, 35), (65, 75, 100), (1, 2, 100), ((6, 16), (8, 12), (12, 16))))


def outcome(bars, entry_index, side, atr, spread, minutes, target_atr=3, hold_hours=4):
    """Bid OHLC, constant ask spread, stop-first ambiguity, adverse market slippage."""
    first = bars[entry_index]
    slip = spread * 0.1
    entry = first.open + (spread if side == 1 else 0) + side * slip
    stop, target = entry - side * 1.5 * atr, entry + side * target_atr * atr
    deadline = first.time.replace(hour=20, minute=0, second=0) if hold_hours is None else first.time + timedelta(hours=hold_hours)
    for j in range(entry_index, len(bars)):
        bar = bars[j]
        offset = spread if side == -1 else 0
        op, hi, lo = bar.open + offset, bar.high + offset, bar.low + offset
        if bar.time >= deadline:
            if side * (op - target) >= 0:
                price, reason = target, "target"
            elif side * (op - stop) <= 0:
                price, reason = op - side * slip, "stop"
            else:
                price, reason = op - side * slip, "time"
        elif (lo <= stop if side == 1 else hi >= stop):
            price = (min(op, stop) if side == 1 else max(op, stop)) - side * slip
            reason = "stop"
        elif (hi >= target if side == 1 else lo <= target):
            price, reason = target, "target"
        else:
            continue
        return j, side * (price - entry) / (1.5 * atr), reason, int(bar.time > deadline or bar.time.date() != first.time.date())
    return None


def generate(symbol):
    source = SOURCE.read_text(encoding="utf-8")
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    meta = repo.metadata(symbol)
    if meta.commission_per_lot:
        raise ValueError("Commission conversion must be implemented before using this instrument")
    base = list(repo.bars(symbol, datetime(2009, 1, 1), datetime(2026, 7, 17, 23, 59, 59), "5m"))
    files = []
    for minutes in FRAMES:
        bars = base if minutes == 5 else list(_aggregate_bars(base, timedelta(minutes=minutes)))
        replay = SniperReplay(source, 10 ** -meta.decimals, minutes)
        rows = []
        for i, bar in enumerate(bars[:-1]):
            side = replay.update_signals(bar)
            next_bar = bars[i + 1]
            if not side or bar.time.year < 2010 or next_bar.time != bar.time + timedelta(minutes=minutes):
                continue
            if not 6 <= next_bar.time.hour < 16:
                continue
            ta = replay.ta
            result = outcome(bars, i + 1, side, ta.a, meta.spread_price, minutes)
            if result is None:
                continue
            j, reward, reason, late = result
            # Assign by exit year so a label cannot leak across the development boundary.
            rows.append((i + 1, j, bars[j].time.year, reward, ta.adx,
                         ta.r if side == 1 else 100 - ta.r,
                         side * (bar.close - ta.e) / ta.a,
                         next_bar.time.hour, late, int(reason == "target"),
                         meta.spread_price / ta.a, int(reason == "time")))
        path = OUT / f"{symbol}_{minutes}.npz"
        np.savez_compressed(path, rows=np.asarray(rows, dtype=float).reshape((-1, 12)))
        files.append(str(path))
        print(f"CANDIDATES {symbol} {minutes}m {len(rows)}", flush=True)
    return files


def selected(rows, rule):
    adx, rsi, distance, hours = rule
    mask = ((rows[:, 4] >= adx) & (rows[:, 5] <= rsi) & (rows[:, 6] <= distance)
            & (rows[:, 7] >= hours[0]) & (rows[:, 7] < hours[1]))
    # Re-run position admission after filtering; skipped trades must not suppress new entries.
    result = []
    exit_index, last_entry = -1, -100
    for row in rows[mask]:
        if row[0] > exit_index and row[0] - last_entry >= 5:
            result.append(row)
            exit_index, last_entry = row[1], row[0]
    return np.asarray(result).reshape((-1, 12))


def metrics(rows):
    r = rows[:, 3]
    gains, losses = float(r[r > 0].sum()), float(-r[r < 0].sum())
    return dict(n=len(r), wins=int((r > 0).sum()), win_rate=float((r > 0).mean() * 100) if len(r) else None,
                pf=gains / losses if losses else None, mean_r=float(r.mean()) if len(r) else None,
                total_r=float(r.sum()), target_hits=int(rows[:, 9].sum()), timed_exits=int(rows[:, 11].sum()),
                late_exits=int(rows[:, 8].sum()))


def evaluate(data, rule):
    admitted = {symbol: selected(rows, rule) for symbol, rows in data.items()}
    all_rows = np.concatenate(list(admitted.values()))
    periods = [metrics(all_rows[(all_rows[:, 2] >= a) & (all_rows[:, 2] <= b)]) for a, b in PERIODS]
    per_symbol = {s: [metrics(rows[(rows[:, 2] >= a) & (rows[:, 2] <= b)]) for a, b in PERIODS] for s, rows in admitted.items()}
    return dict(periods=periods, per_symbol=per_symbol)


def write_report(result):
    chosen = result["selected"]
    lines = ["# SNIPER デイトレード改善の実測結果", "",
             ("数値上の採用基準を通過。Pineへの反映は別途検証が必要。" if result["adopted"] else
              "目標の約70%には未達。採用基準を通過しなかったため、Pineの売買条件には反映していない。"), "",
             f"探索：{result['search_count']}候補。件数・銘柄数基準を満たす候補：{result['eligible_count']}。"
             f"条件作成・選択の両期間でPF1.2以上かつ平均損益プラス：{result['profitable_development_count']}候補。", "",
             f"条件作成・選択期間から選んだ候補：{chosen['minutes']}分足、ADX下限{chosen['rule'][0]}、"
             f"方向別RSI上限{chosen['rule'][1]}、EMA距離上限{chosen['rule'][2]}ATR、"
             f"保存時刻{chosen['rule'][3][0]:02d}:00〜{chosen['rule'][3][1]:02d}:00未満にエントリー。", "",
             "| 決済期間 | 件数 | 勝率（コスト後） | PF | 平均R | TP3到達件数 | 時間決済 | 遅延等 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for (a, b), m in zip(PERIODS, result["result"]["periods"]):
        lines.append(f"| {a}–{b} | {m['n']:,} | {m['win_rate']:.2f}% | {m['pf']:.3f} | {m['mean_r']:+.4f} | {m['target_hits']:,} | {m['timed_exits']:,} | {m['late_exits']} |")
    lines += ["", "2026年は7月17日まで。遅延等はデータ欠損等で予定4時間を超えた、または日付をまたいだ決済。損益から除外していない。", "",
              "## 時間足別の基準条件", "", "以下はADX18、RSI/EMA追加制限なし、06〜16時エントリーの基準条件。条件選択後の参考比較であり、後半期間から時間足を再選択していない。", "",
              "| 時間足 | 2019–2022 勝率 / PF | 2023–2024 勝率 / PF | 2025–2026 勝率 / PF |",
              "|---|---:|---:|---:|"]
    for frame, baseline in result["baselines"].items():
        cells = [f"{m['win_rate']:.2f}% / {m['pf']:.3f}（{m['n']:,}件）" for m in baseline["periods"][1:]]
        lines.append(f"| {frame}分 | " + " | ".join(cells) + " |")
    lines += ["", "## 読み方", "",
              "勝率は時間決済も含む損益プラスの割合。従来のTP到達率とは定義が異なるため、数字が上がっても改善とは判断できない。"
              "PF1未満は損失合計が利益合計を上回る状態。採用の判定は全期間の件数・勝率・PF・平均損益で行う。", "",
              "利確3ATR・損切り1.5ATRを維持し、次足始値の約定、設定スプレッド、片道スプレッドの10%の不利な成行スリッページ、4時間の時間決済を加えた独立した検証。"
              "原作者の非公開ロジックやTradingView実機の成績を示すものではない。", "",
              "[検証条件と制約](sniper_daytrade_protocol.md) / [全銘柄・全期間の結果](../scripts/sniper_daytrade_results.json)", "",
              f"Pine SHA-256: `{result['source_sha256']}`", ""]
    (ROOT / "docs/sniper_daytrade_results.md").write_text("\n".join(lines), encoding="utf-8")


def analyze():
    candidates, baselines = [], {}
    for minutes in FRAMES:
        data = {s: np.load(OUT / f"{s}_{minutes}.npz")["rows"] for s in SYMBOLS}
        baselines[str(minutes)] = evaluate(data, (18, 100, 100, (6, 16)))
        # Only train/validation rows enter the search; later years are evaluated after selection.
        development = {s: rows[rows[:, 2] <= 2022] for s, rows in data.items()}
        for rule in RULES:
            result = evaluate(development, rule)
            train, val = result["periods"][:2]
            coverage = sum(x[1]["n"] >= 20 for x in result["per_symbol"].values())
            if train["n"] >= 500 and val["n"] >= 200 and coverage >= 6:
                candidates.append(dict(minutes=minutes, rule=rule, train=train, validation=val))
    # Profitability in both development periods takes precedence over raw win rate.
    profitable = [c for c in candidates if all(c[k]["mean_r"] > 0 and (c[k]["pf"] or 0) >= 1.2 for k in ("train", "validation"))]
    ranking = sorted(profitable or candidates, key=lambda c: (min(c["train"]["win_rate"], c["validation"]["win_rate"]), c["validation"]["mean_r"]), reverse=True)
    chosen = ranking[0]
    data = {s: np.load(OUT / f"{s}_{chosen['minutes']}.npz")["rows"] for s in SYMBOLS}
    final = evaluate(data, chosen["rule"])
    gates = [m["n"] >= count and (m["win_rate"] or 0) >= 68 and (m["pf"] or 0) >= 1.2 and m["mean_r"] > 0
             for m, count in zip(final["periods"], (500, 200, 100, 100))]
    result = dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  search_count=len(RULES) * len(FRAMES), eligible_count=len(candidates), profitable_development_count=len(profitable),
                  periods=PERIODS, selected=chosen, result=final, adopted=all(gates), gates=gates,
                  development_top10=ranking[:10], baselines=baselines)
    path = ROOT / "scripts/sniper_daytrade_results.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(result)
    print("RESULT_JSON " + str(path), flush=True)
    print(json.dumps(dict(selected=chosen, periods=final["periods"], adopted=all(gates)), ensure_ascii=False), flush=True)


def main():
    OUT.mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=3) as pool:
        for task in as_completed([pool.submit(generate, s) for s in SYMBOLS]):
            task.result()
    analyze()


if __name__ == "__main__":
    main()
