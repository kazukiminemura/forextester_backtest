"""Fixed BTCUSD CFD-proxy research. No orders; execution requires prior freeze."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.research_btc_spot_rr1 import aggregate_complete, indicators, epoch, iso, sha256, write_csv
from scripts.research_bb_night_rr1 import prior_efficiency, h1_direction

ID = "btc_bb_allhours_20261007"
DOC = ROOT / "docs/quant_organization/experiments" / ID
OUT = ROOT / "agent_runs" / ID
ARMS = ("baseline_bb_reversal", "range_bb", "trend_reclaim")


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def features(times, prices):
    mt, bars = aggregate_complete(times, prices, 300)
    close = pd.Series(bars[:, 3])
    mid = close.rolling(20).mean().to_numpy()
    sd = close.rolling(20).std(ddof=0).to_numpy()
    _, atr = indicators(bars)
    prior = np.r_[np.nan, atr[:-1]]
    return mt, np.column_stack((bars, mid, mid + 3 * sd, mid - 3 * sd, prior))


def signals_from_features(times, f):
    """All decisions use confirmed bars; quotes/fees belong to execution only."""
    efficiency = prior_efficiency(f[:, 3], times)
    direction, hourly = h1_direction(f, times)
    baseline, episodes, trend = [], [], []
    next_origin = 0
    for i in range(len(times)):
        if i < next_origin or not np.isfinite(f[i, 4:7]).all():
            continue
        lower, upper = f[i, 2] <= f[i, 6], f[i, 1] >= f[i, 5]
        if lower == upper:
            continue
        side = 1 if lower else -1
        next_origin = i + 13
        episode = dict(origin=i, origin_time=int(times[i]), side=side, status="expired", signal_index=-1)
        for j in range(i + 1, min(i + 12, len(times))):
            if times[j] - times[j - 1] != 300:
                episode["status"] = "gap_cancelled"
                break
            if (side == 1 and f[j, 2] < f[i, 2]) or (side == -1 and f[j, 1] > f[i, 1]):
                episode["status"] = "extreme_cancelled"
                break
            if side * (f[j, 3] - f[j, 0]) > 0 and f[j, 6] < f[j, 3] < f[j, 5]:
                baseline.append(dict(index=j, origin=i, origin_time=int(times[i]),
                    signal_time=int(times[j] + 300), signal_bar=int(times[j]), side=side,
                    close=float(f[j, 3]), target_center=float(f[j, 4]), risk_price=0.))
                episode.update(status="confirmed", signal_index=j)
                break
        episodes.append(episode)
    for i in range(1, len(times)):
        side = int(direction[i])
        if not side or times[i] - times[i - 1] != 300 or not np.isfinite(f[[i-1, i], 4]).all():
            continue
        if not np.isfinite(f[i, 7]) or f[i, 7] <= 0:
            continue
        if side * (f[i-1, 3] - f[i-1, 4]) <= 0 and side * (f[i, 3] - f[i, 4]) > 0:
            trend.append(dict(index=i, origin=i, origin_time=int(times[i]),
                signal_time=int(times[i] + 300), signal_bar=int(times[i]), side=side,
                close=float(f[i, 3]), target_center=0., risk_price=float(1.5 * f[i, 7])))
    filtered = [s for s in baseline if np.isfinite(efficiency[s["origin"]]) and efficiency[s["origin"]] <= .30]
    return dict(zip(ARMS, (baseline, filtered, trend))), episodes, hourly


def order_at_open(signal, bid, equity, cost):
    side, spread, slip, fee = signal["side"], cost["spread"], cost["slippage"], cost["fee"]
    if not np.isfinite([bid, equity, spread, slip, fee, signal["risk_price"], signal["target_center"]]).all() or equity <= 0:
        return None
    entry = (bid + (spread if side == 1 else 0)) * (1 + side * slip)
    target = (entry + side * signal["risk_price"] if signal["risk_price"] > 0
              else signal["target_center"] + (spread if side == -1 else 0))
    risk = side * (target - entry)
    stop = entry - side * risk
    if not np.isfinite([entry, target, stop, risk]).all() or risk <= 0 or min(entry, target, stop) <= 0:
        return None
    stopped = stop * (1 - side * slip)
    loss = side * (entry - stopped) + fee * (entry + stopped)
    if not np.isfinite(loss) or loss <= 0:
        return None
    quantity = min(equity * .0025 / loss, equity / entry)
    if not np.isfinite(quantity) or quantity <= 0:
        return None
    estimated_cost = spread + 2 * entry * (fee + slip)
    return dict(entry=float(entry), stop=float(stop), target=float(target), price_risk=float(risk),
        quantity=float(quantity), estimated_stop_loss_per_btc=float(loss),
        estimated_cost_ratio=float(estimated_cost / risk), margin_reserved=float(quantity * entry),
        notional_capped=bool(equity / entry < equity * .0025 / loss))


def find_exit(prices, entry_index, stop, target, side, spread):
    """Scan small chunks, with the bid/ask side and M1 conservative tie policy."""
    for start in range(entry_index, len(prices), 512):
        chunk = prices[start:start + 512]
        low, high = chunk[:, 2], chunk[:, 1]
        if side == -1:
            low, high = low + spread, high + spread
        hits = np.flatnonzero((low <= stop) | (high >= target)) if side == 1 else np.flatnonzero((high >= stop) | (low <= target))
        if not len(hits):
            continue
        j = start + int(hits[0])
        open_, high, low, _ = prices[j] + (spread if side == -1 else 0)
        if side * (open_ - stop) <= 0:
            return j, float(open_), "stop_gap"
        if side * (open_ - target) >= 0:
            return j, float(target), "target_gap"
        if (side == 1 and low <= stop) or (side == -1 and high >= stop):
            return j, float(stop), "stop"
        return j, float(target), "target"
    return len(prices) - 1, float(prices[-1, 3] + (spread if side == -1 else 0)), "period_end"


def funding_series(times, prices, quantity, cost):
    elapsed = times - times[0]
    blocks = (elapsed + 86399) // 86400
    return blocks * cost["funding_rate"] * quantity * np.maximum.accumulate(prices[:, 1] + cost["spread"])


def trade_summary(trades):
    pnl = np.asarray([t["net_pnl"] for t in trades], dtype=float)
    positive, negative = float(pnl[pnl > 0].sum()), float(-pnl[pnl < 0].sum())
    return dict(closed=len(trades), wins=int((pnl > 0).sum()),
        win_rate=float(np.mean(pnl > 0)) if len(pnl) else None,
        net_pnl=float(pnl.sum()), profit_factor=positive/negative if negative else None,
        gross_profit=positive, gross_loss=negative,
        mean_pnl=float(np.mean(pnl)) if len(pnl) else None,
        mean_net_r=float(np.mean([t["net_r"] for t in trades])) if trades else None,
        gross_fill_pnl=float(sum(t["gross_pnl"] for t in trades)),
        raw_bid_gross_pnl=float(sum(t["raw_bid_gross_pnl"] for t in trades)),
        fees=float(sum(t["entry_fee"] + t["exit_fee"] for t in trades)),
        funding=float(sum(t["funding"] for t in trades)),
        total_model_cost=float(sum(t["raw_bid_gross_pnl"] - t["net_pnl"] for t in trades)),
        forced_closes=sum(t["reason"] == "period_end" for t in trades),
        gap_exposed=sum(t["gap_exposed"] for t in trades),
        next_day_exits=sum(t["exit_time"]//86400 > t["entry_time"]//86400 for t in trades),
        max_holding_minutes=max((t["holding_minutes"] for t in trades), default=0),
        realized_losses_above_budget=sum(t["net_pnl"] < -.0025*t["equity_before"]-1e-9 for t in trades))


def simulate(times, prices, signals, cost, start, end, initial_equity=10000.):
    begin, finish = np.searchsorted(times, [start, end])
    times, prices = times[begin:finish], prices[begin:finish]
    if not len(times):
        raise ValueError("No M1 observations inside period")
    curve = np.full(len(times), initial_equity)
    balance, cursor, last_exit_bucket = initial_equity, 0, -1
    trades, decisions = [], []
    for signal in signals:
        when = signal["signal_time"]
        if not start <= when < end:
            continue
        j = int(np.searchsorted(times, when))
        decision = dict(signal_time=when, signal_index=signal["index"], side=signal["side"], reason="")
        if j >= len(times) or times[j] != when:
            decision["reason"] = "missing_entry_minute"
        elif j < cursor or when//300 <= last_exit_bucket:
            decision["reason"] = "occupied_or_exit_bucket"
        else:
            order = order_at_open(signal, prices[j, 0], balance, cost)
            if order is None:
                decision["reason"] = "invalid_price_or_equity"
            else:
                decision["reason"] = "filled"
                side, qty, entry = signal["side"], order["quantity"], order["entry"]
                k, raw_exit_side, reason = find_exit(prices, j, order["stop"], order["target"], side, cost["spread"])
                exit_price = raw_exit_side * (1 - side * cost["slippage"])
                entry_fee, exit_fee = qty * entry * cost["fee"], qty * exit_price * cost["fee"]
                funding = funding_series(times[j:k+1], prices[j:k+1], qty, cost)
                marks = (prices[j:k+1, 3] + (cost["spread"] if side == -1 else 0)) * (1 - side * cost["slippage"])
                curve[cursor:j] = balance
                curve[j:k+1] = balance + side*qty*(marks-entry) - entry_fee - qty*marks*cost["fee"] - funding
                gross = side * qty * (exit_price-entry)
                net = gross - entry_fee - exit_fee - funding[-1]
                before = balance
                balance += net
                curve[k] = balance
                deltas = np.diff(times[j:k+1])
                raw_bid_exit = raw_exit_side - (cost["spread"] if side == -1 else 0)
                trades.append(dict(**signal, **order, entry_time=int(times[j]), exit_time=int(times[k]),
                    entry_index=j, exit_index=k, exit=float(exit_price), raw_exit_side=float(raw_exit_side),
                    raw_bid_entry=float(prices[j, 0]), raw_bid_exit=float(raw_bid_exit), reason=reason,
                    equity_before=float(before), equity_after=float(balance), entry_fee=float(entry_fee), exit_fee=float(exit_fee),
                    funding=float(funding[-1]), gross_pnl=float(gross), net_pnl=float(net),
                    raw_bid_gross_pnl=float(side*qty*(raw_bid_exit-prices[j, 0])),
                    net_r=float(net/(qty*order["price_risk"])),
                    planned_stop_loss_fraction=float(qty*order["estimated_stop_loss_per_btc"]/before),
                    gap_exposed=bool(np.any(deltas > 60)), holding_gap_count=int(np.sum(deltas > 60)),
                    holding_missing_minutes=int(np.sum(deltas//60-1)), holding_minutes=int((times[k]-times[j])//60)))
                cursor, last_exit_bucket = k+1, int(times[k]//300)
        decisions.append(decision)
    curve[cursor:] = balance
    peaks = np.maximum.accumulate(np.r_[initial_equity, curve])[1:]
    drawdown = (peaks-curve)/peaks
    summary = trade_summary(trades)
    summary.update(initial_equity=initial_equity, ending_equity=float(balance), return_pct=float(100*(balance/initial_equity-1)),
        max_drawdown_pct=float(100*np.max(drawdown)), m1_marks=len(times),
        long=trade_summary([t for t in trades if t["side"] == 1]), short=trade_summary([t for t in trades if t["side"] == -1]),
        decisions=dict(Counter(d["reason"] for d in decisions)))
    years = times.astype("datetime64[s]").astype("datetime64[Y]").astype(int)+1970
    previous = initial_equity
    yearly = {}
    for year in np.unique(years):
        last = float(curve[np.flatnonzero(years == year)[-1]])
        subset = [t for t in trades if int(iso(t["exit_time"])[:4]) == year]
        yearly[str(year)] = dict(**trade_summary(subset), mtm_change=last-previous)
        previous = last
    summary["yearly"] = yearly
    return dict(times=times, equity=curve, trades=trades, decisions=decisions, summary=summary)


def frequency(counts):
    return dict(days=len(counts), mean=float(np.mean(counts)) if len(counts) else None,
        median=float(np.median(counts)) if len(counts) else None,
        zero_pct=float(100*np.mean(counts == 0)) if len(counts) else None,
        two_plus_pct=float(100*np.mean(counts >= 2)) if len(counts) else None,
        two_to_three_pct=float(100*np.mean((counts >= 2)&(counts <= 3))) if len(counts) else None,
        above_three_pct=float(100*np.mean(counts > 3)) if len(counts) else None)


def daily_metrics(times, m5times, trades, start, end):
    days = np.arange(start//86400, end//86400, dtype=np.int64)
    m1count = np.diff(np.searchsorted(times, np.r_[days, days[-1]+1]*86400))
    m5count = np.diff(np.searchsorted(m5times, np.r_[days, days[-1]+1]*86400))
    counts = Counter(t["entry_time"]//86400 for t in trades)
    entries = np.array([counts[int(d)] for d in days])
    complete, partial, missing = m1count == 1440, (m1count > 0)&(m1count < 1440), m1count == 0
    rows = [dict(date=str(np.datetime64(int(d), "D")), observed_m1=int(n), complete_m5=int(m),
                 status="complete" if n == 1440 else "partial" if n else "missing", entries=int(e))
            for d,n,m,e in zip(days,m1count,m5count,entries)]
    return dict(primary=frequency(entries[complete]), all_calendar_lower_bound=frequency(entries),
        m5_observed=frequency(entries[m5count > 0]), partial=frequency(entries[partial]),
        calendar_days=len(days), complete_days=int(complete.sum()), partial_days=int(partial.sum()), missing_days=int(missing.sum()),
        complete_fraction=float(complete.mean()), entries_complete=int(entries[complete].sum()),
        entries_partial=int(entries[partial].sum()), entries_missing=int(entries[missing].sum()), daily=rows)


def screen(normal, stress):
    stats, coverage = normal["summary"], normal["frequency"]
    freq = coverage["primary"]
    economics = dict(net_positive=stats["net_pnl"] > 0, pf_ge_1_2=stats["profit_factor"] is not None and stats["profit_factor"] >= 1.2,
        stress_positive=stress["summary"]["net_pnl"] > 0, dd_le_20=stats["max_drawdown_pct"] <= 20, closed_ge_200=stats["closed"] >= 200)
    quality = dict(complete_days_ge_100=coverage["complete_days"] >= 100, coverage_ge_80pct=coverage["complete_fraction"] >= .8)
    activity = dict(mean_ge_2=freq["mean"] is not None and freq["mean"] >= 2,
        zero_le_40pct=freq["zero_pct"] is not None and freq["zero_pct"] <= 40,
        two_plus_ge_50pct=freq["two_plus_pct"] is not None and freq["two_plus_pct"] >= 50)
    return dict(economics=economics, data_quality=quality, activity=activity,
        research_screen=all(economics.values()) and all(quality.values()) and all(activity.values()),
        over_three_per_day=freq["mean"] is not None and freq["mean"] > 3, adoption=False)


def frozen_inputs(protocol):
    paths = [DOC/"protocol.json", DOC/"hypothesis.md", DOC/"data_inventory.md", Path(__file__), ROOT/"tests/test_btc_bb_allhours.py",
        ROOT/"scripts/research_btc_spot_rr1.py", ROOT/"scripts/research_bb_night_rr1.py",
        ROOT/protocol["data_manifest"]["cache"], ROOT/protocol["data_manifest"]["evidence"]]
    return {str(p.relative_to(ROOT)): sha256(p) for p in paths}


def run(freeze=False):
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN":
        raise ValueError("Protocol must be approved and frozen before results")
    OUT.mkdir(parents=True, exist_ok=True)
    hashes = frozen_inputs(protocol)
    manifest_path = OUT/"freeze_manifest.json"
    if freeze:
        if manifest_path.exists():
            raise ValueError("Refusing to replace existing freeze manifest")
        save_json(manifest_path, dict(frozen_at=datetime.now(timezone.utc).isoformat(), inputs=hashes))
    else:
        if json.loads(manifest_path.read_text(encoding="utf-8"))["inputs"] != hashes:
            raise ValueError("Frozen inputs changed")
    cache = ROOT/protocol["data_manifest"]["cache"]
    if sha256(cache) != protocol["data_manifest"]["cache_sha256"]:
        raise ValueError("Cache SHA differs")
    with np.load(cache) as data:
        times, prices = data["time"], data["prices"]
    mt, f = features(times, prices)
    signals, episodes, hourly = signals_from_features(mt, f)
    np.savez_compressed(OUT/"features.npz", time=mt, features=f)
    np.savez_compressed(OUT/"hourly.npz", **hourly)
    write_csv(OUT/"episodes.csv", episodes)
    for arm in ARMS:
        write_csv(OUT/f"signals_{arm}.csv", signals[arm])
    cases = {}
    for arm in ARMS:
        cases[arm] = {}
        for period, bounds in protocol["periods"].items():
            start, end = map(epoch, bounds)
            cases[arm][period] = {}
            for name, cost in protocol["cost_and_fill_model"]["scenarios"].items():
                result = simulate(times, prices, signals[arm], cost, start, end)
                daily = daily_metrics(times, mt, result["trades"], start, end)
                directory = OUT/arm/period/name
                directory.mkdir(parents=True, exist_ok=True)
                write_csv(directory/"trades.csv", result["trades"])
                write_csv(directory/"decisions.csv", result["decisions"])
                write_csv(directory/"daily.csv", daily.pop("daily"))
                np.savez_compressed(directory/"equity.npz", time=result["times"], equity=result["equity"])
                cases[arm][period][name] = dict(summary=result["summary"], frequency=daily)
                print(arm, period, name, result["summary"]["closed"], flush=True)
    gates = {}
    for arm in ARMS:
        by_period = {p:screen(cases[arm][p]["normal"], cases[arm][p]["stress"]) for p in protocol["periods"]}
        gates[arm] = dict(periods=by_period, training_and_validation_screen=all(by_period[p]["research_screen"] for p in ("training", "validation")), adoption=False)
    results = dict(experiment_id=ID, cases=cases, gates=gates, adoption=False, provenance="CFD_PROXY_NOT_GMO_REPLAY",
        input_hashes=hashes, candidate_counts={k:len(v) for k,v in signals.items()}, episodes=len(episodes), m5_bars=len(mt))
    save_json(OUT/"results.json", results)
    print("RESULT_JSON="+str(OUT/"results.json"), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-and-run", action="store_true")
    args = parser.parse_args()
    run(args.freeze_and_run)
