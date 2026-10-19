"""Frozen BB-context timing study; raw-chart-price accounting mirrors the Pine.

Not a broker emulator, profit guarantee, or independent adoption approval.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from numba import njit

from forextester_backtest import HistoryRepository

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/quant_organization/experiments/bb3_context_timing_20260909/protocol.json"
OUT = ROOT / "agent_runs/bb3_context_timing_20260909"
EPOCH = datetime(1970, 1, 1)  # arithmetic reference only: source timezone is unknown
TRADE_COLUMNS = ["side", "prep_index", "signal_index", "entry_index", "exit_index",
                 "entry", "exit", "target_at_exit", "net_pips"]


def timestamp(value):
    return int((datetime.fromisoformat(value) - EPOCH).total_seconds())


@njit(cache=True)
def features(ohlc, times, pip, tick):
    """Columns O,H,L,C,SMA,upper,lower,priorATR,priorHigh,priorLow,
    buyExplained,sellExplained,buyWick,sellWick,gap. ATR uses Wilder SMA seed.
    Four independent memories are updated on every confirmed bar.
    """
    n = len(ohlc)
    f = np.full((n, 15), np.nan)
    f[:, :4] = ohlc
    tr = np.empty(n)
    atr = np.full(n, np.nan)
    started = np.full(4, -1, dtype=np.int64)
    levels = np.full(4, np.nan)
    step = max(tick, math.floor(50 * pip / tick + .5) * tick)
    for i in range(n):
        op, hi, lo, cl = ohlc[i]
        prev = ohlc[i - 1, 3] if i else cl
        tr[i] = max(hi - lo, abs(hi - prev), abs(lo - prev))
        if i == 13:
            atr[i] = np.mean(tr[:14])
        elif i > 13:
            atr[i] = (atr[i - 1] * 13 + tr[i]) / 14
        if i >= 19:
            closes = ohlc[i - 19:i + 1, 3]
            mid = np.mean(closes)
            dev = np.sqrt(np.mean((closes - mid) ** 2))
            f[i, 4:7] = (mid, mid + 3 * dev, mid - 3 * dev)
        if i:
            f[i, 7] = atr[i - 1]
            f[i, 8] = np.max(ohlc[max(0, i - 12):i, 1])
            f[i, 9] = np.min(ohlc[max(0, i - 12):i, 2])
        gap = i > 0 and times[i] - times[i - 1] > 300
        f[i, 14] = 1.0 if gap else 0.0
        impulse = tr[i] >= f[i, 7] * 1.5
        up_round = (math.floor(prev / step) + 1) * step
        down_round = (math.ceil(prev / step) - 1) * step
        triggers = (cl > f[i, 8] and impulse, cl < f[i, 9] and impulse,
                    hi >= up_round and cl > up_round and impulse,
                    lo <= down_round and cl < down_round and impulse)
        broken = (f[i, 8], f[i, 9], up_round, down_round)
        for k in range(4):
            upward = k % 2 == 0
            reclaimed = cl <= levels[k] if upward else cl >= levels[k]
            if gap or reclaimed or (started[k] >= 0 and i - started[k] > 3):
                started[k] = -1
                levels[k] = np.nan
            if triggers[k]:
                started[k] = i
                levels[k] = broken[k]
        f[i, 10] = 1.0 if started[1] >= 0 or started[3] >= 0 else 0.0
        f[i, 11] = 1.0 if started[0] >= 0 or started[2] >= 0 else 0.0
        body = max(abs(cl - op), tick)
        buy_wick, sell_wick = min(op, cl) - lo, hi - max(op, cl)
        f[i, 12] = 1.0 if lo <= f[i, 6] and hi > lo and buy_wick >= 2 * body and buy_wick >= .5 * (hi - lo) else 0.0
        f[i, 13] = 1.0 if hi >= f[i, 5] and hi > lo and sell_wick >= 2 * body and sell_wick >= .5 * (hi - lo) else 0.0
    return f


@njit(cache=True)
def timing_allowed(f, i, prep, side, mode, distance, cost, pip):
    op, _, _, cl = f[i, :4]
    if not (cl > f[i, 6] and cl < f[i, 5]):
        return False
    if mode == 1 and not (side * (cl - op) > 0 and side * (cl - f[i - 1, 3]) > 0):
        return False
    if mode == 2 and not (cl > f[i - 1, 1] if side == 1 else cl < f[i - 1, 2]):
        return False
    if mode == 3 and not (cl > f[prep, 1] if side == 1 else cl < f[prep, 2]):
        return False
    return side * (f[i, 4] - cl) / pip >= distance * cost


@njit(cache=True)
def simulate(f, times, start, end, pip, cost, mode=0, expiry=3, distance=0.0):
    """Return trade matrix and diagnostics. No forced close is added to PF.

    Default exit has no stop. Timing is the ONLY parameterized strategy rule.
    diagnostics: open_net, MTM_drawdown, open_side, entry, last_close,
    pending_side, prep_count, signal_count, open_entry_index, target_next_bar.
    """
    trades = np.empty((len(f), 9))
    count = 0
    side = pending = armed = 0
    prep = signal = entry_i = -1
    entry = target = np.nan
    prep_count = signal_count = 0
    realized = peak = dd = 0.0
    last_close = np.nan
    for i in range(len(f)):
        if times[i] < start or times[i] >= end:
            continue
        op, hi, lo, cl, mid, upper, lower = f[i, :7]
        last_close = cl
        exited = False
        if side == 0 and pending != 0 and i > signal:
            side, pending = pending, 0
            entry, entry_i = op, i
        if side != 0:
            gap_target = op >= target if side == 1 else op <= target
            hit_target = hi >= target if side == 1 else lo <= target
            fill = op if gap_target else target if hit_target else np.nan
            if not np.isnan(fill):
                net = side * (fill - entry) / pip - cost
                trades[count] = (float(side), float(prep), float(signal), float(entry_i), float(i), entry, fill, target, net)
                count += 1
                realized += net
                side, exited = 0, True
                entry = target = np.nan
            else:
                target = mid
        equity = realized + (side * (cl - entry) / pip - cost if side else 0.0)
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
        ready = side == 0 and pending == 0 and not exited and not np.isnan(mid) and upper > mid and not np.isnan(f[i, 7]) and not np.isnan(f[i, 8])
        touch_buy, touch_sell = lo <= lower, hi >= upper
        if not ready or f[i, 14] != 0:
            armed = 0
        cancelled = False
        selected = 0
        if ready and armed != 0:
            explained = f[i, 10] if armed == 1 else f[i, 11]
            wick = f[i, 12] if armed == 1 else f[i, 13]
            center_passed = cl >= mid if armed == 1 else cl <= mid
            opposite = touch_sell if armed == 1 else touch_buy
            cancelled = explained != 0 or wick != 0 or i - prep > expiry or center_passed or opposite
            if not cancelled and i > prep and timing_allowed(f, i, prep, armed, mode, distance, cost, pip):
                selected = armed
            if cancelled or selected != 0:
                armed = 0
        if ready and armed == 0 and not cancelled and selected == 0 and (touch_buy or touch_sell):
            explained = f[i, 10] if touch_buy else f[i, 11]
            wick = f[i, 12] if touch_buy else f[i, 13]
            if not (touch_buy and touch_sell) and explained == 0 and wick == 0:
                armed = 1 if touch_buy else -1
                prep = i
                prep_count += 1
        if selected:
            pending, signal, target = selected, i, mid
            signal_count += 1
    open_net = side * (last_close - entry) / pip - cost if side else 0.0
    return trades[:count], np.array([open_net, dd, side, entry, last_close, pending, prep_count, signal_count, entry_i, target])


def stats(trades, diagnostics):
    values = trades[:, 8]
    gp, gl = math.fsum(values[values > 0]), -math.fsum(values[values < 0])
    net = gp - gl
    return {"trades": len(values), "wins": int(np.sum(values > 0)),
            "win_rate_pct": 100 * int(np.sum(values > 0)) / len(values) if len(values) else None,
            "average_pips": net / len(values) if len(values) else None,
            "profit_factor": gp / gl if gl else None, "gross_profit_pips": gp,
            "gross_loss_pips": gl, "net_pips": net,
            "open_net_pips": float(diagnostics[0]), "net_plus_open_pips": net + float(diagnostics[0]),
            "bar_close_mtm_drawdown_pips": float(diagnostics[1]),
            "open_side": int(diagnostics[2]), "pending_side": int(diagnostics[5]),
            "preparations": int(diagnostics[6]), "signals": int(diagnostics[7])}


def aggregate(rows):
    gp = math.fsum(r["gross_profit_pips"] for r in rows)
    gl = math.fsum(r["gross_loss_pips"] for r in rows)
    return {"trades": sum(r["trades"] for r in rows), "wins": sum(r["wins"] for r in rows),
            "gross_profit_pips": gp, "gross_loss_pips": gl, "profit_factor": gp / gl if gl else None,
            "net_pips": gp - gl, "open_net_pips": math.fsum(r["open_net_pips"] for r in rows),
            "net_plus_open_pips": math.fsum(r["net_plus_open_pips"] for r in rows),
            "positive_pairs": sum(r["net_pips"] > 0 for r in rows)}


def eligible_train(summary):
    return all(s["net_pips"] > 0 and s["net_plus_open_pips"] > 0 and s["trades"] >= 40 and s["positive_pairs"] >= 6
               for s in summary.values())


def gate(summary):
    checks = {}
    for cost, periods in summary.items():
        for period, s in periods.items():
            checks[f"{cost}.{period}.net"] = s["net_pips"] > 0
            checks[f"{cost}.{period}.net_plus_open"] = s["net_plus_open_pips"] > 0
        for period, min_count in (("continuous", 100), ("final_confirmation", 30)):
            s = periods[period]
            checks[f"{cost}.{period}.count"] = s["trades"] >= min_count
            checks[f"{cost}.{period}.positive_pairs"] = s["positive_pairs"] >= 6
    return checks


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    dump(output / "protocol.json", protocol)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
              (SPEC, Path(__file__), ROOT / "scripts/tradingview/bb3_context_pf_indicator.pine", ROOT / "src/forextester_backtest/data.py")}
    dump(output / "code_hashes.json", hashes)
    repo, inputs, manifests = HistoryRepository(), {}, []
    for symbol in protocol["symbols"]:
        print("Loading", symbol, flush=True)
        file = repo.root / symbol / "Bars.dat"
        before = {"size": file.stat().st_size, "mtime_ns": file.stat().st_mtime_ns}
        meta = repo.metadata(symbol)
        if meta.commission_per_lot != 0:
            raise ValueError("Nonzero metadata commission is not supported")
        bars = list(repo.bars(symbol, datetime(2023, 8, 1), datetime(2026, 9, 8) - timedelta(microseconds=1), "5m"))
        times = np.array([int((b.time - EPOCH).total_seconds()) for b in bars], dtype=np.int64)
        ohlc = np.array([(b.open, b.high, b.low, b.close) for b in bars])
        if not np.all(np.isfinite(ohlc)) or np.any(ohlc <= 0) or np.any(np.diff(times) <= 0):
            raise ValueError("Invalid OHLC or ordering")
        if np.any(ohlc[:, 1] < np.maximum(ohlc[:, 0], ohlc[:, 3])) or np.any(ohlc[:, 2] > np.minimum(ohlc[:, 0], ohlc[:, 3])):
            raise ValueError("Inconsistent OHLC")
        if times[0] > timestamp("2023-09-08") or times[-1] < timestamp("2026-09-01") or np.any(times % 300):
            raise ValueError("Period coverage or 5m alignment")
        pip, tick = (.01 if symbol.endswith("JPY") else .0001), 10.0 ** -meta.decimals
        f = features(ohlc, times, pip, tick)
        after = {"size": file.stat().st_size, "mtime_ns": file.stat().st_mtime_ns}
        if before != after:
            raise ValueError("History changed during read")
        np.savez_compressed(output / f"{symbol}_features.npz", times=times, features=f)
        manifests.append({"symbol": symbol, "metadata": asdict(meta), "before": before, "after": after,
                          "bars": len(bars), "first": bars[0].time.isoformat(), "last": bars[-1].time.isoformat(),
                          "gap_count": int(np.sum(np.diff(times) > 300)), "pip": pip, "tick": tick,
                          "time_ohlc_sha256": hashlib.sha256(times.tobytes() + ohlc.tobytes()).hexdigest()})
        inputs[symbol] = (f, times, pip, {"fixed_1p4": 1.4, "metadata_spread_plus_0p2": meta.spread_price / pip + .2})
    dump(output / "data_manifest.json", manifests)
    results, summaries = [], {}
    candidates = protocol["search_space"]

    def run_period(candidate, period, bounds):
        collected = {}
        for symbol, (f, times, pip, costs) in inputs.items():
            for cost_name, cost in costs.items():
                trades, diagnostic = simulate(f, times, timestamp(bounds[0]), timestamp(bounds[1]), pip, cost,
                                              candidate["mode"], candidate["expiry"], candidate["distance_cost_multiple"])
                name = f"{candidate['id']}__{period}__{symbol}__{cost_name}"
                np.savez_compressed(output / (name + ".npz"), trades=trades, diagnostic=diagnostic)
                s = stats(trades, diagnostic)
                results.append({"candidate": candidate["id"], "period": period, "symbol": symbol,
                                "cost_case": cost_name, "cost_pips": cost, "artifact": name + ".npz", **s})
                collected.setdefault(cost_name, []).append(s)
        return {cost: aggregate(rows) for cost, rows in collected.items()}

    # Selection is serialized BEFORE validation or final simulations.
    for candidate in candidates:
        training = run_period(candidate, "training", protocol["periods"]["training"])
        summaries[candidate["id"]] = {cost: {"training": s} for cost, s in training.items()}
        print("TRAIN", candidate["id"], json.dumps(training), flush=True)
    eligible = [c for c in candidates if c["id"] != "baseline" and eligible_train({k: v["training"] for k, v in summaries[c["id"]].items()})]
    eligible.sort(key=lambda c: (-min(v["training"]["net_pips"] for v in summaries[c["id"]].values()), c["id"]))
    selected = eligible[0]["id"] if eligible else None
    dump(output / "selection_before_validation.json", {"selected": selected, "eligible_train": [c["id"] for c in eligible], "training_summaries": summaries})
    # Only preselected candidate + baseline see validation/final outcomes.
    for candidate in (c for c in candidates if c["id"] in ("baseline", selected)):
        for period, bounds in {**{k: v for k, v in protocol["periods"].items() if k != "training"},
                               "continuous": ["2023-09-08", "2026-09-08"]}.items():
            for cost, s in run_period(candidate, period, bounds).items():
                summaries[candidate["id"]][cost][period] = s
        print("COMPLETE", candidate["id"], flush=True)
    checks = gate(summaries[selected]) if selected else {}
    result = {"status": "GATES_PASSED_REQUIRES_INDEPENDENT_VALIDATION" if selected and all(checks.values()) else "REJECTED",
              "selected": selected, "checks": checks, "trade_columns": TRADE_COLUMNS,
              "summaries": summaries, "rows": results, "live_approved": False,
              "limits": "Previously viewed data; equal-pip research score is NOT account-currency profit; TV_UNVERIFIED"}
    dump(output / "results.json", result)
    print("RESULT_JSON=" + json.dumps({"status": result["status"], "selected": selected, "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
