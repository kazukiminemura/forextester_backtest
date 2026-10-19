"""Frozen BTC spot-long RR1 research; local Forex Tester prices, no orders.

Data access, causal signals, fills/accounting, and reporting are separate functions.
Run --prepare-only first. Numerical evaluation requires a frozen protocol.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forextester_backtest.data import HistoryRepository  # noqa: E402

EXPERIMENT = "btc_spot_rr1_20261007"
DOC = ROOT / "docs/quant_organization/experiments" / EXPERIMENT
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
NORMAL_COST = {"spread": 60.643, "fee": .001, "slippage": .0001}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def epoch(value):
    """Naive storage clock encoded as epoch seconds; does not assert UTC."""
    return int(np.datetime64(value, "s").astype(np.int64))


def iso(value):
    return str(np.datetime64(int(value), "s"))


def load_history(protocol, output=OUTPUT):
    """Read only valid records; preserve source and verify audited SHA256."""
    repo = HistoryRepository(protocol["history_directory"])
    path = repo.root / "BTCUSD/Bars.dat"
    before = (path.stat().st_size, path.stat().st_mtime_ns)
    actual_sha = sha256(path)
    if actual_sha != protocol["data_manifest"]["bars_sha256"]:
        raise ValueError("Bars.dat differs from the audited snapshot")
    count = repo.summary("BTCUSD").bar_count
    raw = np.memmap(path, dtype="<f8", mode="r", offset=4, shape=(count, 6))
    seconds = (raw[:, 0] - 25569.0) * 86400.0
    times = np.rint(seconds).astype(np.int64)
    if np.max(np.abs(seconds - times)) > .01:
        raise ValueError("Unexpected non-second timestamp")
    prices = np.asarray(raw[:, [1, 3, 4, 2]]).copy()  # OCHL -> OHLC
    if (np.any(np.diff(times) <= 0) or np.any(times % 60)
            or not np.all(np.isfinite(prices)) or np.any(prices <= 0)
            or np.any(prices[:, 1] < np.max(prices[:, [0, 2, 3]], axis=1))
            or np.any(prices[:, 2] > np.min(prices[:, [0, 1, 3]], axis=1))):
        raise ValueError("Input failed M1 chronology/OHLC checks")
    if before != (path.stat().st_size, path.stat().st_mtime_ns):
        raise ValueError("Source changed during reading")
    output.mkdir(parents=True, exist_ok=True)
    cache = output / "btc_m1.npz"
    if not cache.exists():
        np.savez_compressed(cache, time=times, prices=prices)
    else:
        with np.load(cache) as saved:
            if not (np.array_equal(saved["time"], times)
                    and np.array_equal(saved["prices"], prices)):
                raise ValueError("Existing cache differs; refusing overwrite")
    manifest = {"source": str(path), "source_sha256": actual_sha,
                "source_size": before[0], "source_mtime_ns": before[1],
                "valid_count": count, "cache_sha256": sha256(cache),
                "first": iso(times[0]), "last": iso(times[-1]),
                "schema": "time=int64 storage-clock epoch seconds; prices=float64 OHLC",
                "timezone": "unknown; no UTC or named session inference"}
    (output / "input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return times, prices


def aggregate_complete(times, prices, seconds):
    """Only complete, aligned buckets. Never impute missing minutes."""
    buckets = times // seconds * seconds
    starts = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
    ends = np.r_[starts[1:], len(times)]
    complete = ((ends - starts == seconds // 60)
                & (times[starts] == buckets[starts])
                & (times[ends - 1] == buckets[starts] + seconds - 60))
    bars = np.column_stack((prices[starts, 0], np.maximum.reduceat(prices[:, 1], starts),
                            np.minimum.reduceat(prices[:, 2], starts), prices[ends - 1, 3]))
    return buckets[starts][complete], bars[complete]


def average(values, length, alpha):
    """SMA seed after length complete bars, then EMA or Wilder recurrence."""
    result = np.full(len(values), np.nan)
    if len(values) >= length:
        result[length - 1] = np.mean(values[:length])
        for i in range(length, len(values)):
            result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def indicators(prices):
    previous = np.r_[prices[0, 3], prices[:-1, 3]]
    tr = np.maximum(prices[:, 1] - prices[:, 2],
                    np.maximum(abs(prices[:, 1] - previous), abs(prices[:, 2] - previous)))
    return average(prices[:, 3], 20, 2 / 21), average(tr, 14, 1 / 14)


def generate_signals(times, prices):
    htime, hourly = aggregate_complete(times, prices, 3600)
    qtime, fourhour = aggregate_complete(times, prices, 14400)
    ema20, atr14 = indicators(hourly)
    ema50 = average(fourhour[:, 3], 50, 2 / 51)
    ema200 = average(fourhour[:, 3], 200, 2 / 201)
    signals = []
    for i in range(22, len(htime)):
        if htime[i] - htime[i - 3] != 10800:
            continue
        prior = hourly[i - 3:i]
        touch = np.any((prior[:, 2] <= ema20[i - 3:i]) & (ema20[i - 3:i] <= prior[:, 1]))
        if not (touch and hourly[i, 3] > np.max(prior[:, 1]) and hourly[i, 3] > ema20[i]):
            continue
        available = int(htime[i] + 3600)
        j = int(np.searchsorted(qtime + 14400, available, side="right") - 1)
        trend = (j >= 199 and available - (qtime[j] + 14400) < 14400
                 and fourhour[j, 3] > ema200[j] and ema50[j] > ema200[j]
                 and ema50[j] > ema50[j - 3])
        signals.append({"signal_time": available, "signal_bar": int(htime[i]),
                        "close": float(hourly[i, 3]),
                        "stop": float(np.min(hourly[i - 3:i + 1, 2]) - .1 * atr14[i]),
                        "atr14": float(atr14[i]), "ema20": float(ema20[i]),
                        "trend": bool(trend), "higher_available": int(qtime[j] + 14400) if j >= 0 else 0})
    return signals


def order_request(signal, cash, cost, risk_fraction=.0025, gate_cost=None):
    """All trading decisions and requested quantity use the signal close."""
    close, stop = signal["close"], signal["stop"]
    risk = close - stop
    gate = NORMAL_COST if gate_cost is None else gate_cost
    estimated_cost = gate["spread"] + 2 * close * (gate["fee"] + gate["slippage"])
    if stop <= 0 or risk <= 0 or estimated_cost / risk > .15:
        return None
    entry = (close + cost["spread"]) * (1 + cost["slippage"])
    stopped = stop * (1 - cost["slippage"])
    loss = entry - stopped + cost["fee"] * (entry + stopped)
    quantity = min(cash * risk_fraction / loss, cash / (entry * (1 + cost["fee"])))
    return {"quantity_requested": quantity, "estimated_entry": entry,
            "estimated_loss_per_btc": loss, "estimated_cost_ratio": estimated_cost / risk}


def find_exit(prices, entry_index, stop, target):
    """Bracket active from entry M1; stop wins unresolved same-minute ties."""
    tail = prices[entry_index:]
    hits = np.flatnonzero((tail[:, 2] <= stop) | (tail[:, 1] >= target))
    if not len(hits):
        return len(prices) - 1, float(prices[-1, 3]), "period_end"
    index = entry_index + int(hits[0])
    open_, high, low, _ = prices[index]
    if open_ <= stop:
        return index, float(open_), "stop_gap"
    if open_ >= target:
        return index, target, "target_gap"
    if low <= stop:
        return index, stop, "stop"
    return index, target, "target"


def trade_summary(trades):
    pnl = np.array([t["net_pnl"] for t in trades], dtype=float)
    win, loss = float(pnl[pnl > 0].sum()), float(-pnl[pnl < 0].sum())
    return {"trades": len(trades), "wins": int(np.sum(pnl > 0)),
            "win_rate": float(np.mean(pnl > 0)) if len(pnl) else 0.,
            "net_pnl": float(pnl.sum()), "gross_profit": win, "gross_loss": loss,
            "profit_factor": win / loss if loss else None,
            "mean_pnl": float(pnl.mean()) if len(pnl) else 0.,
            "mean_net_r": float(np.mean([t["net_r"] for t in trades])) if trades else 0.,
            "forced_closes": sum(t["reason"] == "period_end" for t in trades),
            "gap_exposed": sum(t["gap_exposed"] for t in trades)}


def simulate(times, prices, signals, cost, start, end, arm="trend", initial_cash=10000., gate_cost=None):
    begin, finish = np.searchsorted(times, [start, end])
    times, prices = times[begin:finish], prices[begin:finish]
    if not len(times):
        raise ValueError("No M1 observations in period")
    equity = np.full(len(times), initial_cash)
    cash, cursor, last_exit_hour = initial_cash, 0, -1
    trades, decisions = [], []
    for signal in signals:
        when = signal["signal_time"]
        if not start <= when < end:
            continue
        decision = {"signal_time": when, "allowed": False, "reason": "", "arm": arm}
        decisions.append(decision)
        if arm == "trend" and not signal["trend"]:
            decision["reason"] = "higher_timeframe"
            continue
        index = int(np.searchsorted(times, when))
        if index >= len(times) or times[index] != when:
            decision["reason"] = "missing_entry_minute"
            continue
        if index < cursor or when // 3600 <= last_exit_hour:
            decision["reason"] = "position_or_exit_hour"
            continue
        request = order_request(signal, cash, cost, gate_cost=gate_cost)
        if request is None:
            decision["reason"] = "signal_cost_or_risk"
            continue
        entry = (float(prices[index, 0]) + cost["spread"]) * (1 + cost["slippage"])
        stop = signal["stop"]
        if entry <= stop:
            decision["reason"] = "invalid_bracket_at_fill"
            continue
        quantity = min(request["quantity_requested"], cash / (entry * (1 + cost["fee"])))
        target = 2 * entry - stop
        exit_index, raw_exit, reason = find_exit(prices, index, stop, target)
        exit_price = raw_exit * (1 - cost["slippage"])
        buy_fee, sell_fee = quantity * entry * cost["fee"], quantity * exit_price * cost["fee"]
        net = quantity * (exit_price - entry) - buy_fee - sell_fee
        after_buy = cash - quantity * entry - buy_fee
        equity[cursor:index] = cash
        equity[index:exit_index + 1] = after_buy + quantity * prices[index:exit_index + 1, 3] * (1 - cost["slippage"]) * (1 - cost["fee"])
        cash_before = cash
        cash += net
        equity[exit_index] = cash
        cursor = exit_index + 1
        last_exit_hour = int(times[exit_index] // 3600)
        diffs = np.diff(times[index:exit_index + 1])
        gaps = diffs[diffs > 60]
        gross_risk = quantity * (entry - stop)
        stop_fill = stop * (1 - cost["slippage"])
        actual_loss = quantity * (entry - stop_fill) + quantity * cost["fee"] * (entry + stop_fill)
        trade = {**signal, **request, "entry_time": int(times[index]), "exit_time": int(times[exit_index]),
                 "entry": entry, "stop": stop, "target": target, "raw_exit": raw_exit,
                 "exit": exit_price, "quantity": quantity, "cash_capped": quantity < request["quantity_requested"],
                 "buy_fee": buy_fee, "sell_fee": sell_fee, "gross_pnl": quantity * (exit_price - entry),
                 "net_pnl": net, "net_r": net / gross_risk,
                 "initial_price_risk": gross_risk, "actual_stop_loss_with_cost": actual_loss,
                 "actual_risk_fraction": actual_loss / cash_before,
                 "cash_before": cash_before, "cash_after": cash, "reason": reason,
                 "gap_exposed": bool(len(gaps)), "holding_gap_count": len(gaps),
                 "holding_missing_minutes": int(np.sum(gaps // 60 - 1)),
                 "signal_to_open_gap": float(prices[index, 0]) - signal["close"],
                 "entry_index": index, "exit_index": exit_index}
        trades.append(trade)
        decision.update(allowed=True, reason="filled")
    equity[cursor:] = cash
    peaks = np.maximum.accumulate(np.r_[initial_cash, equity])
    drawdown = (peaks - np.r_[initial_cash, equity]) / peaks
    summary = trade_summary(trades)
    summary.update(initial_cash=initial_cash, final_cash=cash, return_pct=(cash / initial_cash - 1) * 100,
                   max_drawdown_pct=float(np.max(drawdown)) * 100,
                   max_drawdown_basis="all observed M1 closes, liquidation-value equity",
                   signals=len(decisions), holding_gap_count=sum(t["holding_gap_count"] for t in trades),
                   holding_missing_minutes=sum(t["holding_missing_minutes"] for t in trades),
                   no_gap_trades_descriptive=trade_summary([t for t in trades if not t["gap_exposed"]]),
                   bracket_exits=trade_summary([t for t in trades if t["reason"] != "period_end"]),
                   period_end_exits=trade_summary([t for t in trades if t["reason"] == "period_end"]))
    years = range(int(iso(times[0])[:4]), int(iso(times[-1])[:4]) + 1)
    yearly = {}
    for year in years:
        selected = [t for t in trades if iso(t["exit_time"]).startswith(str(year))]
        a, b = np.searchsorted(times, [epoch(f"{year}-01-01"), epoch(f"{year + 1}-01-01")])
        before = initial_cash if a == 0 else float(equity[a - 1])
        after = float(equity[b - 1]) if b > a else before
        yearly[str(year)] = {**trade_summary(selected), "mtm_change": after - before}
    summary["yearly_exit_year"] = yearly
    return trades, times, equity, decisions, summary


def write_csv(path, rows, fields=None):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or (list(rows[0]) if rows else ["empty"]))
        writer.writeheader()
        writer.writerows(rows)


def run(protocol, times, prices, output):
    signals = generate_signals(times, prices)
    write_csv(output / "signals.csv", signals)
    results = {}
    for period, bounds in protocol["periods"].items():
        for arm in ("trend", "baseline"):
            for cost_name, cost in protocol["cost_and_fill_model"]["scenarios"].items():
                key = f"{period}_{arm}_{cost_name}"
                trades, tm, eq, decisions, summary = simulate(times, prices, signals, cost,
                                                            epoch(bounds[0]), epoch(bounds[1]), arm)
                folder = output / key
                folder.mkdir(exist_ok=True)
                write_csv(folder / "trades.csv", trades)
                write_csv(folder / "decisions.csv", decisions)
                sample = set((np.r_[np.flatnonzero(np.diff(tm // 3600)), len(tm) - 1]).tolist())
                sample.update(t["entry_index"] for t in trades)
                sample.update(t["exit_index"] for t in trades)
                write_csv(folder / "equity.csv", [{"time": int(tm[i]), "equity": float(eq[i])} for i in sorted(sample)])
                results[key] = summary
                print(f"Completed {key}", flush=True)
    gates = {}
    for period in ("validation", "final_confirmation"):
        normal, stress = results[f"{period}_trend_normal"], results[f"{period}_trend_stress"]
        gates[period] = {"trades_ge_100": normal["trades"] >= 100,
                         "net_positive": normal["net_pnl"] > 0,
                         "pf_ge_1_1": normal["profit_factor"] is not None and normal["profit_factor"] >= 1.1,
                         "dd_le_20pct": normal["max_drawdown_pct"] <= 20,
                         "stress_net_positive": stress["net_pnl"] > 0}
    report = {"experiment_id": EXPERIMENT, "cases": results, "research_screen": gates,
              "research_screen_pass": all(all(g.values()) for g in gates.values()),
              "adoption_approved": False,
              "limitations": protocol["limitations"],
              "protocol_sha256": sha256(DOC / "protocol.json"), "code_sha256": sha256(__file__)}
    (output / "results.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"RESULT_JSON={output / 'results.json'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    protocol = json.loads((DOC / "protocol.json").read_text(encoding="utf-8"))
    if not args.prepare_only and protocol["status"] != "SPEC_FROZEN":
        raise SystemExit("Freeze protocol before computing any result")
    times, prices = load_history(protocol, args.output)
    if args.prepare_only:
        print(f"DATA_READY={args.output / 'input_manifest.json'}")
    else:
        run(protocol, times, prices, args.output)


if __name__ == "__main__":
    main()
