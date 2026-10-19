"""Bounded loss diagnosis and development-only selection for the exact Gold Confirm."""
import csv
import hashlib
import json
from datetime import datetime, timedelta

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.gold_signals import features
from forextester_backtest.gold_refinement import entry_signals
from forextester_backtest.gold_loss_defense import defensive_exit
from forextester_backtest.sniper import Technicals
from research_sniper_daytrade import ROOT, PERIODS, outcome, selected, metrics

RULE = (18, 100, 100, (6, 16))
MODES = ("baseline", "failed_1", "failed_2", "failed_3", "stalled_3", "stalled_6",
         "body_max_2", "body_max_3", "adx_rising", "adx_max_40", "distance_max_4", "distance_max_6")


def summary(rows):
    result = metrics(rows)
    rewards = rows[:, 3]
    equity = np.r_[0, rewards.cumsum()]
    result.update(losses=int((rewards < 0).sum()),
                  max_drawdown_r=float(np.max(np.maximum.accumulate(equity) - equity)))
    return result


def period_stats(rows):
    return [summary(rows[(rows[:, 2] >= a) & (rows[:, 2] <= b)]) for a, b in PERIODS]


def main():
    protocol = dict(modes=MODES, periods=PERIODS, minimum_counts=[250, 100, 50, 50],
                    selection="Maximum minimum development PF, then validation mean R; counts required",
                    adoption="PF > 1 and mean R > 0 every period, development PF improves in both periods, doubled spread total R improves",
                    previously_inspected_evaluation=True, no_reselection=True,
                    unchanged="XAUUSD 1H, next open, 06-16, 20 exit, 5-bar cooldown, TP 3ATR SL 1.5ATR",
                    failed="Close back inside original 55-bar boundary within first N bars; next open exit",
                    stalled="Negative liquidation P/L at a close after N bars; next open exit")
    (ROOT / "scripts/gold_loss_protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    meta = repo.metadata("XAUUSD")
    assert meta.commission_per_lot == 0
    print("Loading XAUUSD 1H", flush=True)
    bars = list(_aggregate_bars(repo.bars("XAUUSD", datetime(2009, 1, 1), datetime(2026, 7, 17, 23, 59, 59), "5m"), timedelta(hours=1)))
    frame = features(bars)
    ta = Technicals(dict(atrLength=14, emaLength=200, rsiLength=14, dmiLength=14, stFactor=3))
    adx = []
    for b in bars:
        ta.update(b)
        adx.append(ta.adx)
    sides = entry_signals(frame, [b.time.date() for b in bars], "impulse")
    indexes = [k for k in np.flatnonzero(sides) if k + 1 < len(bars) and bars[k].time.year >= 2010
               and bars[k + 1].time == bars[k].time + timedelta(hours=1)
               and 6 <= bars[k + 1].time.hour < 16 and adx[k] >= 18]
    details, raw = {}, {}
    for multiplier in (1, 2):
        data = {mode: [] for mode in MODES}
        for k in indexes:
            i, side, atr = k + 1, int(sides[k]), frame.atr.iloc[k]
            spread = meta.spread_price * multiplier
            base = outcome(bars, i, side, atr, spread, 60, 3, None)
            if base is None:
                raise ValueError("Unresolved trade")
            level = frame.prior_high55.iloc[k] if side == 1 else frame.prior_low55.iloc[k]
            body = side * (bars[k].close - bars[k].open) / atr
            distance = side * (bars[k].close - frame.ema50.iloc[k]) / atr
            if multiplier == 1:
                j, reward, reason, _ = base
                entry = bars[i].open + (spread if side == 1 else 0) + side * spread * .1
                # Excursions include full hourly exit bar and are descriptive bounds only.
                path = bars[i:j + 1] if reason != "time" else bars[i:j]
                highs = [b.high + (spread if side == -1 else 0) for b in path] + [bars[j].open + (spread if side == -1 else 0)]
                lows = [b.low + (spread if side == -1 else 0) for b in path] + [bars[j].open + (spread if side == -1 else 0)]
                mfe = (max(highs) - entry if side == 1 else entry - min(lows)) / (1.5 * atr)
                details[i] = dict(entry_time=bars[i].time.isoformat(), exit_time=bars[j].time.isoformat(),
                                  side="BUY" if side == 1 else "SELL", reward_r=reward, reason=reason,
                                  hour=bars[i].time.hour, adx=adx[k], body_atr=body, distance_atr=distance,
                                  mfe_hourly_bound_r=max(0, mfe), holding_bars=j-i+1)
            for mode in MODES:
                allowed = {"body_max_2": body <= 2, "body_max_3": body <= 3,
                           "adx_rising": adx[k] > adx[k-1], "adx_max_40": adx[k] <= 40,
                           "distance_max_4": distance <= 4, "distance_max_6": distance <= 6}.get(mode, True)
                if not allowed:
                    continue
                result = defensive_exit(bars, i, side, atr, spread, level, base, mode) if mode.startswith(("failed_", "stalled_")) else base
                j, reward, reason, late = result
                data[mode].append((i, j, bars[j].time.year, reward, 25, 55, 0, bars[i].time.hour,
                                   late, reason == "target", spread / atr, reason == "time"))
        raw[multiplier] = {mode: selected(np.asarray(rows, dtype=float).reshape((-1, 12)), RULE) for mode, rows in data.items()}
    baseline = raw[1]["baseline"]
    previous = json.loads((ROOT / "scripts/gold_pf_refinement_results.json").read_text(encoding="utf-8"))
    for m, expected in zip(period_stats(baseline), previous["results"]):
        for key, value in expected.items():
            assert np.isclose(m[key], value), (key, m[key], value)
    candidates = []
    for mode in MODES[1:]:
        dev = period_stats(raw[1][mode][raw[1][mode][:, 2] <= 2022])[:2]
        candidates.append(dict(mode=mode, development=dev))
    eligible = [c for c in candidates if c["development"][0]["n"] >= 250 and c["development"][1]["n"] >= 100]
    chosen = max(eligible, key=lambda c: (min(m["pf"] or 0 for m in c["development"]), c["development"][1]["mean_r"])) if eligible else None
    candidate = raw[1][chosen["mode"]] if chosen else baseline
    stats, base_stats = period_stats(candidate), period_stats(baseline)
    gates = [m["n"] >= n and (m["pf"] or 0) > 1 and m["mean_r"] > 0 for m, n in zip(stats, protocol["minimum_counts"])]
    dev_improved = all(stats[i]["pf"] > base_stats[i]["pf"] for i in (0, 1))
    cost_improved = chosen is not None and summary(raw[2][chosen["mode"]])["total_r"] > summary(raw[2]["baseline"])["total_r"]
    admitted = [details[int(row[0])] for row in baseline]
    csv_path = ROOT / "scripts/gold_loss_trades.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(admitted[0]))
        writer.writeheader()
        writer.writerows(admitted)
    groups = {}
    for field in ("side", "reason", "hour"):
        groups[field] = {}
        for value in sorted({d[field] for d in admitted}):
            mask = np.array([d[field] == value for d in admitted])
            groups[field][str(value)] = summary(baseline[mask])
    losses = [d for d in admitted if d["reward_r"] < 0]
    loss_reasons = {r: dict(n=sum(d["reason"] == r for d in losses), loss_r=-sum(d["reward_r"] for d in losses if d["reason"] == r)) for r in ("stop", "time")}
    result = dict(protocol=protocol, baseline_verified=True, bars=len(bars), spread=meta.spread_price,
                  first_bar=bars[0].time.isoformat(), last_bar=bars[-1].time.isoformat(),
                  baseline=base_stats, baseline_total=summary(baseline), baseline_double=period_stats(raw[2]["baseline"]),
                  candidates=candidates, selected=chosen, result=stats, result_total=summary(candidate),
                  doubled_spread=period_stats(raw[2][chosen["mode"]]) if chosen else None,
                  gates=gates, development_improved=dev_improved, doubled_spread_improved=cost_improved,
                  adopted=bool(chosen and all(gates) and dev_improved and cost_improved), groups=groups,
                  loss_reasons=loss_reasons, source_sha256=hashlib.sha256((ROOT / "scripts/tradingview/gold_breakout55_pf_refined.pine").read_bytes()).hexdigest())
    path = ROOT / "scripts/gold_loss_results.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESULT_JSON", path, flush=True)
    print(json.dumps({k: result[k] for k in ("selected", "result", "baseline_total", "result_total", "loss_reasons", "adopted")}), flush=True)


if __name__ == "__main__":
    main()
