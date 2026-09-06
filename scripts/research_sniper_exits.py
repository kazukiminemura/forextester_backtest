"""Fixed gold entry signals; select exits by development PF, not win rate."""
import hashlib
import itertools
import json
from datetime import datetime, timedelta

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.sniper import SniperReplay
from research_sniper_daytrade import ROOT, SOURCE, PERIODS, outcome, evaluate


def main():
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    meta = repo.metadata("XAUUSD")
    assert meta.commission_per_lot == 0
    source = SOURCE.read_text(encoding="utf-8")
    bars = list(_aggregate_bars(repo.bars("XAUUSD", datetime(2009, 1, 1), datetime(2026, 7, 17, 23, 59, 59), "5m"), timedelta(hours=1)))
    replay = SniperReplay(source, 10**-meta.decimals, 60)
    signals = []
    for i, bar in enumerate(bars[:-1]):
        side = replay.update_signals(bar)
        entry = bars[i+1]
        if side and replay.ta.adx >= 25 and entry.time == bar.time+timedelta(hours=1) and 6 <= entry.time.hour < 16 and bar.time.year >= 2010:
            signals.append((i+1, side, replay.ta.a))

    def simulate(target, hours, spread_multiplier=1):
        rows = []
        for i, side, atr in signals:
            trade = outcome(bars, i, side, atr, meta.spread_price*spread_multiplier, 60, target, hours)
            if trade is None:
                continue
            j, reward, reason, late = trade
            rows.append((i, j, bars[j].time.year, reward, 25, 55, 0, bars[i].time.hour, late, reason == "target", meta.spread_price/atr, reason == "time"))
        return np.asarray(rows, dtype=float).reshape((-1, 12))

    # Twelve predeclared exits. Entry, stop, session and admission rules stay fixed.
    candidates, datasets = [], {}
    for target, hours in itertools.product((.75, 1.5, 3), (1, 2, 4, None)):
        rows = simulate(target, hours)
        datasets[(target, hours)] = rows
        dev = evaluate({"XAUUSD": rows[rows[:, 2] <= 2022]}, (25, 100, 100, (6, 16)))["periods"][:2]
        candidates.append(dict(target_atr=target, hold_hours=hours, train=dev[0], validation=dev[1]))
    eligible = [c for c in candidates if c["train"]["n"] >= 250 and c["validation"]["n"] >= 100]
    if not eligible:
        raise ValueError("No exit has sufficient development trades")
    chosen = max(eligible, key=lambda c: (min(c["train"]["pf"] or 0, c["validation"]["pf"] or 0), c["validation"]["mean_r"]))
    final = evaluate({"XAUUSD": datasets[(chosen["target_atr"], chosen["hold_hours"])]}, (25, 100, 100, (6, 16)))["periods"]
    baseline = evaluate({"XAUUSD": datasets[(3, 4)]}, (25, 100, 100, (6, 16)))["periods"]
    previous = json.loads((ROOT / "scripts/sniper_xauusd_daytrade_results.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == previous["source_sha256"]
    for actual, expected in zip(baseline, previous["results"]):
        for key in actual:
            assert np.isclose(actual[key], expected[key]), (key, actual, expected)
    stress = evaluate({"XAUUSD": simulate(chosen["target_atr"], chosen["hold_hours"], 2)}, (25, 100, 100, (6, 16)))["periods"]
    gates = [m["n"] >= n and (m["pf"] or 0) >= 1.2 and m["mean_r"] > 0 for m,n in zip(final,(250,100,50,50))]
    result = dict(selected=chosen, results=final, baseline=baseline, doubled_spread=stress,
                  candidates_development_only=candidates, gates=gates, adopted=all(gates),
                  source_sha256=previous["source_sha256"], signal_count=len(signals))
    path = ROOT / "scripts/sniper_exit_results.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    hold = f"{chosen['hold_hours']}時間" if chosen["hold_hours"] else "保存時刻20時"
    lines = ["# 金の出口改善検証", "", "入口は既存の1時間足・ADX25以上・保存時刻06〜16時に固定。SL1.5ATR。利確幅0.75 / 1.5 / 3ATRと1 / 2 / 4時間 / 当日20時決済の12条件を比較。", "",
             f"開発期間のPFから選択：利確{chosen['target_atr']}ATR、{hold}で時間決済。", "",
             "| 決済期間 | 件数 | 勝率 | PF | 平均R | 元の出口PF | スプレッド2倍PF |", "|---|---:|---:|---:|---:|---:|---:|"]
    for (a,b),m,base,s in zip(PERIODS,final,baseline,stress):
        lines.append(f"| {a}–{b} | {m['n']} | {m['win_rate']:.2f}% | {m['pf']:.3f} | {m['mean_r']:+.4f} | {base['pf']:.3f} | {s['pf']:.3f} |")
    lines += ["", f"採用判定：{'数値基準通過' if all(gates) else '未達・不採用'}。Pineの条件は変更していない。", "",
              "## 条件選択に使った期間の比較", "", "| 利確ATR | 時間決済 | 2013–2018 PF | 2019–2022 PF |", "|---|---|---:|---:|"]
    for c in candidates:
        lines.append(f"| {c['target_atr']} | {str(c['hold_hours'])+'時間' if c['hold_hours'] else '20時'} | {c['train']['pf']:.3f} | {c['validation']['pf']:.3f} |")
    lines += ["", "2018年まで・2019〜2022年のPFの低い方が最大の条件を選び、その1条件を2023年以降で評価。後半の結果で選び直さない。"
              "採用には全4期間でPF1.2以上・平均Rプラス、件数250 / 100 / 50 / 50以上が必要。今回は勝率70%を採用条件にせず、損益を優先した。", "",
              "金の履歴は2013年5月〜2026年7月17日。SL優先、ギャップ約定、固定スプレッドと成行スリッページ、遅延決済を含む。"
              "出口変更後にポジションの重複を再判定するため、採用取引は出口ごとに異なる。元の出口の再計算と以前の結果の一致を確認。", "",
              "後半期間は以前の集計で見ているため完全な未見データではない。1時間OHLC内のTP/SL同時到達はSL優先であり、実際の到達順は未確認。"
              "この検証だけで入口に優位性がないと断定することも、将来利益を保証することもできない。", "",
              "[共通執行条件](sniper_daytrade_protocol.md)", ""]
    (ROOT / "docs/sniper_exit_results.md").write_text("\n".join(lines), encoding="utf-8")
    print("RESULT_JSON", path)
    print(json.dumps(dict(selected=chosen, results=final, adopted=all(gates)), ensure_ascii=False))


if __name__ == "__main__":
    main()
