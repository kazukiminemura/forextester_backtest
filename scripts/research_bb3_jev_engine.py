"""Frozen BB reversal candidates and independent, fixed-target RR accounting.

No model/network calls. The parent experiment supplies Jev's allowed-index set.
OHLC prices are chart prices, not executable bid/ask quotes; costs are explicit.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "agent_runs/bb3_gmo_2023_2025"
START = 1672531200  # 2023-01-01, arithmetic timestamp; source timezone unknown.
END = 1767225600  # 2026-01-01


def load_symbol(symbol, cache_dir=CACHE):
    """Reuse frozen, fully warmed M5 features; never modify source history."""
    with np.load(Path(cache_dir) / f"{symbol}_features.npz", allow_pickle=False) as z:
        f, times = z["features"].copy(), z["times"].copy()
    pip = .01 if symbol.endswith("JPY") else .0001
    tick = 10.0 ** -HistoryRepository().metadata(symbol).decimals
    _validate(f, times, pip, tick)
    return f, times, pip, tick


def _validate(f, times, pip, tick):
    if f.ndim != 2 or f.shape[1] != 15 or len(f) != len(times):
        raise ValueError("Expected aligned N x 15 features and N timestamps")
    if not (math.isfinite(pip) and math.isfinite(tick) and pip > 0 and tick > 0):
        raise ValueError("pip and tick must be positive and finite")
    if np.any(np.diff(times) <= 0) or not np.isfinite(f[:, :4]).all():
        raise ValueError("Nonfinite OHLC or unordered timestamps")


def round_tick(price, tick):
    """Pine math.round_to_mintick: halfway values round upward."""
    return math.floor(price / tick + .5) * tick


def candidates(f, times, pip, tick, *, expiry=12, min_center_pips=3.0):
    """Current Pine default state, independent of any hypothetical position.

    Touch -> later directional inside-band close -> later strict wick break.
    Cancellation wins, and a rejected/cancelled bar cannot re-arm immediately.
    Candidate room uses PRIOR center; trade target uses CURRENT closed center.
    """
    _validate(f, times, pip, tick)
    if expiry < 0 or min_center_pips < 0:
        raise ValueError("Negative candidate configuration")
    result = []
    side, prepared, confirmed = 0, -1, -1
    threshold = cancel = math.nan
    for i, row in enumerate(f):
        op, hi, lo, cl, mid, upper, lower = row[:7]
        ready = np.isfinite(row[[4, 5, 6, 7, 8]]).all() and upper > mid
        buy, sell = lo <= lower, hi >= upper
        consumed = False
        if side:
            invalid = lo < cancel if side == 1 else hi > cancel
            opposite = sell if side == 1 else buy
            blocked = row[10 if side == 1 else 11] != 0 or row[12 if side == 1 else 13] != 0
            gap = i > 0 and times[i] - times[i - 1] > 300
            consumed = not ready or gap or invalid or opposite or blocked or (expiry > 0 and i - prepared > expiry)
            if not consumed:
                if confirmed >= 0 and i > confirmed:
                    broken = hi > threshold if side == 1 else lo < threshold
                    if broken:
                        reference = max(op, threshold + tick) if side == 1 else min(op, threshold - tick)
                        room = side * (f[i - 1, 4] - reference) / pip
                        if math.isfinite(room) and room + 1e-9 >= min_center_pips:
                            result.append(dict(index=i, side=side, prep_index=prepared,
                                               confirmed_index=confirmed, target=round_tick(mid, tick),
                                               reference=float(reference), threshold=float(threshold),
                                               cancel_level=float(cancel)))
                        consumed = True  # First break consumes setup even when room fails.
                elif confirmed < 0 and i > prepared and side * (cl - op) > 0 and lower < cl < upper:
                    confirmed, threshold = i, hi if side == 1 else lo
            if consumed:
                side, prepared, confirmed = 0, -1, -1
                threshold = cancel = math.nan
        if not side and not consumed and ready and (buy or sell):
            blocked = row[10 if buy else 11] != 0 or row[12 if buy else 13] != 0
            if not (buy and sell) and not blocked:
                side, prepared = (1 if buy else -1), i
                cancel = lo if side == 1 else hi
    return result


def simulate(f, times, pip, tick, signals, *, allowed=None, rr=1.0,
             entry_delay=1, cost_pips=1.0, start=START, end=END,
             min_center_pips=3.0):
    """One position, original signal-close target; optional one-bar AI latency.

    ``allowed`` is a set or bool mapping of SIGNAL indices (missing means no).
    Signals during a position are ignored, not queued for a later free position.
    The 1.3/1.5 comparisons preserve target and reduce stop distance; tick rounding
    widens risk conservatively, so effective RR can be slightly below requested.
    Mark-to-market DD samples closes, not unknown intrabar price trajectories.
    """
    _validate(f, times, pip, tick)
    if rr not in (1.0, 1.3, 1.5) or entry_delay not in (1, 2):
        raise ValueError("Frozen experiment supports RR 1/1.3/1.5 and delay 1/2")
    if not math.isfinite(cost_pips) or cost_pips < 0 or min_center_pips < 0 or start >= end:
        raise ValueError("Invalid costs, room or interval")
    by_index = {int(s["index"]): s for s in signals}
    if len(by_index) != len(signals):
        raise ValueError("Duplicate candidate index")
    for index, s in by_index.items():
        if index < 0 or index >= len(f) or s["side"] not in (-1, 1) or not math.isfinite(s["target"]):
            raise ValueError("Invalid candidate")
    first, last = np.searchsorted(times, [start, end])
    trades, mtm = [], np.empty((last - first, 2), dtype=float)
    position = pending = None
    realized_pips = realized_r = peak_r = drawdown_r = 0.0
    rejected_room = rejected_gap = occupied = accepted = 0
    for j, i in enumerate(range(first, last)):
        op, hi, lo, cl = map(float, f[i, :4])
        if pending is not None and i == pending["index"] + entry_delay:
            s, pending = pending, None
            reward = s["side"] * (s["target"] - op)
            if np.any(np.diff(times[s["index"]:i + 1]) != 300):
                rejected_gap += 1
            elif reward <= 0 or reward / pip + 1e-9 < min_center_pips:
                rejected_room += 1
            else:
                raw_stop = op - s["side"] * reward / rr
                # RR1 mirrors Pine's unrounded floating-point expression exactly.
                stop = 2 * op - s["target"] if rr == 1.0 else (
                    math.floor(raw_stop / tick + 1e-8) if s["side"] == 1
                    else math.ceil(raw_stop / tick - 1e-8)) * tick
                risk = s["side"] * (op - stop) / pip
                position = dict(s, entry_index=int(i), entry_time=int(times[i]), entry=op,
                                stop=stop, risk_pips=risk, requested_rr=rr,
                                effective_rr=reward / pip / risk)
        if position is not None:
            p = position
            side, target, stop = p["side"], p["target"], p["stop"]
            stop_open = side * (op - stop) <= 0
            target_open = side * (op - target) >= 0
            stop_hit = lo <= stop if side == 1 else hi >= stop
            target_hit = hi >= target if side == 1 else lo <= target
            # ponytail: OHLC lacks path order; SL first until tick replay is requested.
            price = op if stop_open or target_open else stop if stop_hit else target if target_hit else None
            if price is not None:
                net = side * (price - p["entry"]) / pip - cost_pips
                net_r = net / p["risk_pips"]
                trades.append(dict(p, signal_time=int(times[p["index"]]), exit_index=int(i),
                                   exit_time=int(times[i]), exit=float(price), net_pips=net,
                                   net_r=net_r, cost_pips=cost_pips,
                                   exit_reason="gap_stop" if stop_open else "gap_target" if target_open
                                   else "stop" if stop_hit else "target"))
                realized_pips += net
                realized_r += net_r
                position = None
        open_pips = (position["side"] * (cl - position["entry"]) / pip - cost_pips) if position else 0.0
        open_r = open_pips / position["risk_pips"] if position else 0.0
        equity = realized_r + open_r
        peak_r = max(peak_r, equity)
        drawdown_r = max(drawdown_r, peak_r - equity)
        mtm[j] = (times[i], equity)
        if i in by_index:
            permitted = allowed is None or (bool(allowed.get(i, False)) if hasattr(allowed, "get") else i in allowed)
            if permitted:
                if position is not None or pending is not None:
                    occupied += 1
                else:
                    pending = by_index[i]
                    accepted += 1
    values = [t["net_pips"] for t in trades]
    gp = math.fsum(v for v in values if v > 0)
    gl = -math.fsum(v for v in values if v < 0)
    gp_r = math.fsum(t["net_r"] for t in trades if t["net_r"] > 0)
    gl_r = -math.fsum(t["net_r"] for t in trades if t["net_r"] < 0)
    open_pips = (position["side"] * (f[last - 1, 3] - position["entry"]) / pip - cost_pips) if position else 0.0
    open_r = open_pips / position["risk_pips"] if position else 0.0
    wins = sum(v > 1e-9 for v in values)
    summary = dict(trades=len(trades), wins=wins,
                   win_rate_pct=100 * wins / len(trades) if trades else None,
                   gross_profit_pips=gp, gross_loss_pips=gl, net_pips=realized_pips,
                   profit_factor=gp / gl if gl else None,
                   gross_profit_r=gp_r, gross_loss_r=gl_r,
                   profit_factor_r=gp_r / gl_r if gl_r else None,
                   average_pips=realized_pips / len(trades) if trades else None,
                   net_r=realized_r, average_r=realized_r / len(trades) if trades else None,
                   open_net_pips=float(open_pips), open_net_r=float(open_r),
                   net_plus_open_pips=float(realized_pips + open_pips),
                   net_plus_open_r=float(realized_r + open_r),
                   bar_close_mtm_drawdown_r=drawdown_r, open_side=position["side"] if position else 0,
                   pending_side=pending["side"] if pending else 0,
                   accepted_candidates=accepted, occupied_candidates=occupied,
                   rejected_entry_gap=rejected_gap, rejected_entry_room=rejected_room)
    return dict(trades=trades, summary=summary, mtm=mtm)
