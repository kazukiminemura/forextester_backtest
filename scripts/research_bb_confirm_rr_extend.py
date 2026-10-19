"""Finite fixed-risk/farther-target BB confirmation experiment; no live approval."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from research_bb3_context_timing import SPEC as BASE_SPEC, timestamp, timing_allowed  # noqa: E402

EXPERIMENT = "bb_confirm_rr_extend_20261008"
SPEC = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
OUT = ROOT / "agent_runs" / EXPERIMENT
CACHE = ROOT / "agent_runs/bb3_context_timing_20260909/completed"
RR_VALUES = (1.0, 1.25, 1.5)
COSTS = {"fixed_1p0": 1.0, "fixed_1p2": 1.2}
PERIODS = {
    "training": ("2023-09-08", "2024-09-08"),
    "validation": ("2024-09-08", "2025-09-08"),
    "final_descriptive": ("2025-09-08", "2026-09-08"),
    "continuous_descriptive": ("2023-09-08", "2026-09-08"),
}


def dump(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def target_stop(entry: float, center: float, side: int, pip: float, tick: float, rr: float):
    """Hold stop distance at entry-to-center; extend target from actual fill."""
    signed_risk = side * (center - entry)
    if not math.isfinite(signed_risk) or signed_risk <= 0:
        return None
    risk_ticks = max(1, math.ceil(signed_risk / tick - 1e-10))
    risk = risk_ticks * tick
    reward_ticks = max(1, math.ceil(rr * risk_ticks - 1e-10))
    stop = entry - side * risk
    target = entry + side * reward_ticks * tick
    actual_rr = reward_ticks / risk_ticks
    if actual_rr + 1e-10 < rr or actual_rr >= rr + 1 / risk_ticks + 1e-9:
        raise AssertionError("tick-rounded RR outside declared interval")
    return stop, target, risk / pip, actual_rr, risk_ticks, reward_ticks


def baseline_signals(f, times, start, end, pip, tick):
    """Emit the exact mode=0/expiry=3 signal stream used by frozen simulator.

    Setup state evolves over the whole available prefix; the position remains
    flat for this signal extraction, so its signals do not depend on RR outcomes.
    The simulator-owned transition function is intentionally called rather than
    maintaining a subtly different duplicate implementation.
    """
    result = []
    side = 0
    prepared = confirmed = -1
    threshold = cancel = math.nan
    first_period_i = int(np.searchsorted(times, start, side="left"))
    for i, row in enumerate(f):
        op, hi, lo, cl, mid, upper, lower = row[:7]
        if i < first_period_i:
            # Preserve only an in-progress setup at the period boundary; no
            # pre-period signal can become a period trade.
            pre_ready = (np.isfinite(mid) and upper > mid and np.isfinite(row[7])
                         and np.isfinite(row[8]))
            if not pre_ready or row[14] != 0:
                side, prepared, confirmed = 0, -1, -1
                threshold = cancel = math.nan
            elif side:
                explained = row[10] if side == 1 else row[11]
                wick = row[12] if side == 1 else row[13]
                opposite = hi >= upper if side == 1 else lo <= lower
                invalid = lo < cancel if side == 1 else hi > cancel
                center_passed = cl >= mid if side == 1 else cl <= mid
                if explained != 0 or wick != 0 or opposite or invalid or center_passed or i - prepared > 3:
                    side, prepared, confirmed = 0, -1, -1
                    threshold = cancel = math.nan
                elif confirmed < 0 and i > prepared and timing_allowed(f, i, prepared, side, 0, 0.0, 0.0, pip):
                    confirmed = i
                    threshold = hi if side == 1 else lo
            else:
                buy, sell = lo <= lower, hi >= upper
                if buy or sell:
                    explained = row[10] if buy else row[11]
                    wick = row[12] if buy else row[13]
                    if not (buy and sell) and explained == 0 and wick == 0:
                        side, prepared = (1 if buy else -1), i
                        cancel = lo if side == 1 else hi
            continue
        ready = (np.isfinite(mid) and upper > mid
                 and np.isfinite(row[7]) and np.isfinite(row[8]))
        touch_buy, touch_sell = lo <= lower, hi >= upper
        if not ready or row[14] != 0:
            side, prepared, confirmed = 0, -1, -1
            threshold = cancel = math.nan
        cancelled = False
        selected = 0
        if ready and side != 0:
            explained = row[10] if side == 1 else row[11]
            wick = row[12] if side == 1 else row[13]
            opposite = touch_sell if side == 1 else touch_buy
            cancelled = (explained != 0 or wick != 0 or i - prepared > 3 or opposite)
            if not cancelled:
                if confirmed >= 0 and i > confirmed:
                    broken = hi > threshold if side == 1 else lo < threshold
                    if broken:
                        reference = max(op, threshold + tick) if side == 1 else min(op, threshold - tick)
                        room = side * (f[i - 1, 4] - reference) / pip
                        if math.isfinite(room) and room + 1e-9 >= 3.0:
                            result.append({"index": i, "side": side, "reference": reference,
                                           "center": math.floor(mid / tick + .5) * tick,
                                           "room_center": float(f[i - 1, 4])})
                        selected = side  # first strict break consumes setup, even if room fails
                elif confirmed < 0 and i > prepared and timing_allowed(f, i, prepared, side, 0, 0.0, 0.0, pip):
                    confirmed = i
                    threshold = hi if side == 1 else lo
            if cancelled or selected != 0:
                side, prepared, confirmed = 0, -1, -1
                threshold = cancel = math.nan
        if ready and side == 0 and not cancelled and selected == 0 and (touch_buy or touch_sell):
            explained = row[10] if touch_buy else row[11]
            wick = row[12] if touch_buy else row[13]
            if not (touch_buy and touch_sell) and explained == 0 and wick == 0:
                side = 1 if touch_buy else -1
                prepared = i
                cancel = lo if side == 1 else hi
    return [s for s in result if start <= times[s["index"]] < end]


def replay(f, times, pip, tick, start, end, rr, cost):
    """Replay the frozen signal stream with a fixed center-distance stop."""
    if rr not in RR_VALUES or not math.isfinite(cost) or cost < 0:
        raise ValueError("unsupported RR or cost")
    start_i, end_i = np.searchsorted(times, [start, end])
    signals = baseline_signals(f, times, start, end, pip, tick)
    by_index = {s["index"]: s for s in signals}
    trades = []
    position = pending = None
    ignored = room_reject = risk_reject = gap_stop = gap_target = both_hit = 0
    closed_net_r = closed_net_pips = 0.0
    peak_r = drawdown_r = 0.0
    open_mark_r = open_mark_pips = 0.0
    last_close = math.nan

    for i in range(start_i, end_i):
        op, hi, lo, cl = map(float, f[i, :4])
        last_close = cl
        exited = False

        # Entry at next available bar, matching frozen baseline timing semantics.
        if pending is not None and i > pending["index"]:
            signal = pending
            pending = None
            center = signal["center"]
            room_center = signal.get("room_center", center)
            room = signal["side"] * (room_center - op) / pip
            if room <= 0 or room + 1e-9 < 3.0:
                room_reject += 1
            else:
                bracket = target_stop(op, center, signal["side"], pip, tick, rr)
                if bracket is None:
                    risk_reject += 1
                else:
                    stop, target, risk_pips, actual_rr, risk_ticks, reward_ticks = bracket
                    position = {"side": signal["side"], "signal_index": signal["index"],
                                "entry_index": i, "entry": op, "signal_center": center,
                                "stop": stop, "target": target, "risk_pips": risk_pips,
                                "actual_rr": actual_rr, "risk_ticks": risk_ticks,
                                "reward_ticks": reward_ticks}

        if position is not None:
            p = position
            side = p["side"]
            stop_gap = op <= p["stop"] if side == 1 else op >= p["stop"]
            target_gap = op >= p["target"] if side == 1 else op <= p["target"]
            if stop_gap:
                exit_price, reason, both = op, "gap_stop", False
                gap_stop += 1
            elif target_gap:
                exit_price, reason, both = op, "gap_target", False
                gap_target += 1
            else:
                stop_hit = lo <= p["stop"] if side == 1 else hi >= p["stop"]
                target_hit = hi >= p["target"] if side == 1 else lo <= p["target"]
                both = bool(stop_hit and target_hit)
                both_hit += int(both)
                if stop_hit:
                    exit_price, reason = p["stop"], "stop"
                elif target_hit:
                    exit_price, reason = p["target"], "target"
                else:
                    exit_price, reason = None, ""
            if exit_price is not None:
                gross_pips = side * (exit_price - p["entry"]) / pip
                net_pips = gross_pips - cost
                gross_r = gross_pips / p["risk_pips"]
                net_r = net_pips / p["risk_pips"]
                trades.append({**p, "exit_index": i, "exit": exit_price,
                               "gross_pips": gross_pips, "net_pips": net_pips,
                               "gross_r": gross_r, "net_r": net_r,
                               "exit_reason": reason, "both_hit": both,
                               "cost_pips": cost})
                closed_net_r += net_r
                closed_net_pips += net_pips
                position = None
                exited = True

        if position is not None:
            p = position
            open_mark_pips = p["side"] * (cl - p["entry"]) / pip - cost
            open_mark_r = open_mark_pips / p["risk_pips"]
        else:
            open_mark_pips = open_mark_r = 0.0
        equity = closed_net_r + open_mark_r
        peak_r = max(peak_r, equity)
        drawdown_r = max(drawdown_r, peak_r - equity)

        if i in by_index:
            if position is not None or pending is not None or exited:
                ignored += 1
            else:
                pending = by_index[i]

    open_side = position["side"] if position is not None else 0
    net_plus_open_r = closed_net_r + open_mark_r
    net_plus_open_pips = closed_net_pips + open_mark_pips
    return trades, {
        "signal_count": len(signals), "signals_ignored_occupied_or_exit_bar": ignored,
        "entry_room_rejected": room_reject, "risk_rejected": risk_reject,
        "gap_stop": gap_stop, "gap_target": gap_target, "both_hit_bars": both_hit,
        "open_side": open_side, "open_net_pips": open_mark_pips, "open_net_r": open_mark_r,
        "closed_net_pips": closed_net_pips, "closed_net_r": closed_net_r,
        "net_plus_open_pips": net_plus_open_pips, "net_plus_open_r": net_plus_open_r,
        "bar_close_mtm_drawdown_r": drawdown_r,
    }


def summarize(trades, diag):
    values = np.asarray([t["net_r"] for t in trades], dtype=float)
    pips = np.asarray([t["net_pips"] for t in trades], dtype=float)
    gp = math.fsum(float(v) for v in values if v > 0)
    gl = -math.fsum(float(v) for v in values if v < 0)
    return {
        "trades": len(trades), "wins": int(np.sum(pips > 1e-9)),
        "win_rate_pct": float(100 * np.mean(pips > 1e-9)) if len(pips) else None,
        "net_pips": math.fsum(float(v) for v in pips),
        "average_net_r": math.fsum(float(v) for v in values) / len(values) if len(values) else None,
        "profit_factor_r": gp / gl if gl else None,
        "gross_profit_r": gp, "gross_loss_r": gl,
        "target_exits": sum(t["exit_reason"] in ("target", "gap_target") for t in trades),
        "stop_exits": sum(t["exit_reason"] in ("stop", "gap_stop") for t in trades),
        **diag,
    }


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Refuse to overwrite non-empty output: {OUT}")
    protocol = json.loads(SPEC.read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN_BEFORE_OUTCOMES":
        raise ValueError("Protocol is not frozen")
    if protocol["candidate_budget"] != len(RR_VALUES) or tuple(protocol["exit_rules"]["gross_rr_candidates"]) != RR_VALUES:
        raise ValueError("Protocol candidate set differs from runner")
    manifest_path = ROOT / protocol["data_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inputs = {}
    input_hashes = {}
    for item in manifest:
        symbol = item["symbol"]
        if symbol not in protocol["symbols"]:
            continue
        path = CACHE / f"{symbol}_features.npz"
        if not path.exists():
            raise FileNotFoundError(path)
        digest = file_sha(path)
        if item.get("feature_file_sha256") and digest != item["feature_file_sha256"]:
            raise ValueError(f"feature cache SHA mismatch: {symbol}")
        with np.load(path, allow_pickle=False) as z:
            f, times = z["features"], z["times"]
        if f.ndim != 2 or f.shape[1] != 15 or len(f) != len(times):
            raise ValueError(f"bad feature shape: {symbol}")
        if not np.isfinite(f[:, :4]).all() or np.any(np.diff(times) <= 0):
            raise ValueError(f"invalid OHLC/time: {symbol}")
        if np.any(f[:, 1] < np.maximum(f[:, 0], f[:, 3])) or np.any(f[:, 2] > np.minimum(f[:, 0], f[:, 3])):
            raise ValueError(f"inconsistent OHLC: {symbol}")
        pip = .01 if symbol.endswith("JPY") else .0001
        tick = 10.0 ** -int(item["metadata"]["values"]["decimals"])
        inputs[symbol] = f, times, pip, tick
        input_hashes[str(path.relative_to(ROOT))] = digest
    if set(inputs) != set(protocol["symbols"]):
        raise ValueError("not all protocol symbols have caches")

    OUT.mkdir(parents=True, exist_ok=True)
    dump(OUT / "protocol.json", protocol)
    dump(OUT / "run_manifest.json", {
        "protocol_sha256": file_sha(SPEC), "base_protocol_sha256": file_sha(BASE_SPEC),
        "runner_sha256": file_sha(Path(__file__)),
        "base_runner_sha256": file_sha(Path(__file__).with_name("research_bb3_context_timing.py")),
        "pine_sha256": file_sha(ROOT / "scripts/tradingview/bb3_context_pf_indicator.pine"),
        "manifest_sha256": file_sha(manifest_path), "features_sha256": input_hashes,
        "live_approved": False,
    })
    rows = []
    for period, (start_s, end_s) in PERIODS.items():
        start, end = timestamp(start_s), timestamp(end_s)
        for rr in RR_VALUES:
            for symbol, (f, times, pip, tick) in inputs.items():
                for cost_name, cost in COSTS.items():
                    trades, diag = replay(f, times, pip, tick, start, end, rr, cost)
                    trade_file = f"{period}__rr{rr}__{symbol}__{cost_name}.jsonl"
                    with (OUT / trade_file).open("w", encoding="utf-8") as stream:
                        for trade in trades:
                            stream.write(json.dumps(trade, allow_nan=False) + "\n")
                    rows.append({"period": period, "rr": rr, "symbol": symbol,
                                 "cost_case": cost_name, "cost_pips": cost,
                                 "trade_file": trade_file, **summarize(trades, diag)})
            print(f"COMPLETED period={period} rr={rr}", flush=True)
    dump(OUT / "results.json", {
        "status": "DESCRIPTIVE_RR_COMPARISON_COMPLETE",
        "candidate_rr": RR_VALUES, "costs": COSTS,
        "periods": PERIODS, "rows": rows,
        "live_approved": False, "pine_changed": False,
        "note": "All dates previously viewed; not a virgin holdout. Cross-currency aggregate is descriptive only.",
    })
    print("RESULT_JSON=" + str(OUT / "results.json"), flush=True)


if __name__ == "__main__":
    main()
