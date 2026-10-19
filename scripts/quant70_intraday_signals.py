"""Frozen source-calendar intraday hypotheses; execution belongs to the runner."""
from __future__ import annotations

from collections import deque
from itertools import product

import numpy as np

from quant70_signals import WARMUP_BARS, _past
from research_strict_rr_portfolio import Prepared, _ema


def candidates() -> list[dict]:
    rows = []
    for family, parameter, values in (
        ("day_pullback", "min_displacement_adr", (0.20, 0.40)),
        ("previous_day_failed_break", "penetration_atr", (0.0, 0.10)),
        ("opening_range_retest", "touch_atr", (0.0, 0.10)),
    ):
        for value, budget in product(values, (0.70, 0.90)):
            rows.append({
                "name": f"{family}_{parameter}{value:.2f}_budget{budget:.2f}",
                "family": family, "timeframe": "15m", "stop_atr": 2.0,
                "selectable": True, parameter: value, "max_range_adr": budget,
            })
    return rows


def comparators() -> list[dict]:
    return [{**row, "name": "ablation_" + row["name"],
             "comparison_of": row["name"], "selectable": False,
             "remove_day_state": True} for row in candidates()]


def daily_context(data: Prepared) -> dict[str, np.ndarray]:
    """Causal state on naive source dates; never reuse incomplete daily levels.

    15m aggregates do not certify completeness of their constituent M1 bars.
    A complete day here means all 96 aligned, valid 15m OHLC bars are present.
    """
    n = len(data.times)
    names = ("day_open", "day_high", "day_low", "previous_high", "previous_low",
             "adr20", "opening_high", "opening_low")
    out = {name: np.full(n, np.nan) for name in names}
    out["valid_day"] = np.zeros(n, dtype=bool)
    out["day_id"] = np.empty(n, dtype=np.int64)
    out["minute"] = np.empty(n, dtype=np.int64)
    for i, stamp in enumerate(data.times):
        if stamp.tzinfo is not None or stamp.minute % 15 or stamp.second or stamp.microsecond:
            raise ValueError("Expected naive aligned source 15m timestamps")
        if i and stamp <= data.times[i - 1]:
            raise ValueError("Source timestamps must be strictly increasing")
        out["day_id"][i] = stamp.date().toordinal()
        out["minute"][i] = stamp.hour * 60 + stamp.minute
    if not n:
        return out
    o, h, l, c = data.open, data.high, data.low, data.close
    valid_ohlc = (np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c)
                  & (l > 0) & (h >= np.maximum(o, c)) & (l <= np.minimum(o, c)))
    boundaries = np.r_[0, np.flatnonzero(np.diff(out["day_id"])) + 1, n]
    completed_ranges: deque[float] = deque(maxlen=20)
    previous_id, previous_high, previous_low = -1, np.nan, np.nan
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        day_id = int(out["day_id"][start])
        block = slice(start, end)
        aligned = out["minute"][block] == np.arange(end - start) * 15
        intact = np.logical_and.accumulate(aligned & valid_ohlc[block])
        out["valid_day"][block] = intact
        out["day_open"][block] = o[start] if aligned[0] and valid_ohlc[start] else np.nan
        out["day_high"][block] = np.maximum.accumulate(h[block])
        out["day_low"][block] = np.minimum.accumulate(l[block])
        if previous_id == day_id - 1:
            out["previous_high"][block] = previous_high
            out["previous_low"][block] = previous_low
        if len(completed_ranges) == 20:
            out["adr20"][block] = sum(completed_ranges) / 20
        if end - start > 16 and intact[15]:
            available = slice(start + 16, end)
            out["opening_high"][available] = np.max(h[start:start + 16])
            out["opening_low"][available] = np.min(l[start:start + 16])
        # Register only after assigning this day's state; no current-day ADR.
        if end - start == 96 and intact[-1]:
            previous_id = day_id
            previous_high, previous_low = float(np.max(h[block])), float(np.min(l[block]))
            completed_ranges.append(previous_high - previous_low)
        else:
            previous_id, previous_high, previous_low = day_id, np.nan, np.nan
    return out


def _retest(data: Prepared, ctx: dict, tolerance: float) -> tuple[np.ndarray, np.ndarray]:
    c, o, h, l, atr = data.close, data.open, data.high, data.low, data.atr
    upper, lower, days = ctx["opening_high"], ctx["opening_low"], ctx["day_id"]
    # At 04:00 the boundary first becomes known. Previous 03:45 close can be
    # compared against the now-completed opening range without future access.
    break_long = (c > upper) & (_past(c) <= upper) & (_past(days) == days)
    break_short = (c < lower) & (_past(c) >= lower) & (_past(days) == days)
    pending_long, pending_short = np.zeros(c.size, bool), np.zeros(c.size, bool)
    held_long, held_short = np.ones(c.size, bool), np.ones(c.size, bool)
    for age in range(1, 5):
        same_day = _past(days, age) == days
        held_long &= (_past(c, age) > upper) & same_day
        held_short &= (_past(c, age) < lower) & same_day
        pending_long |= (_past(break_long, age) == 1) & held_long
        pending_short |= (_past(break_short, age) == 1) & held_short
    long_signal = (pending_long & (l <= upper + tolerance * atr)
                   & (l >= upper - 0.25 * atr) & (c > upper) & (c > o))
    short_signal = (pending_short & (h >= lower - tolerance * atr)
                    & (h <= lower + 0.25 * atr) & (c < lower) & (c < o))
    return long_signal, short_signal


def signals(data: Prepared, candidate: dict, context: dict | None = None) -> np.ndarray:
    if candidate["timeframe"] != "15m" or candidate["stop_atr"] != 2.0:
        raise ValueError("Frozen experiment requires 15m and stop_atr=2.0")
    ctx = daily_context(data) if context is None else context
    c, h, l, atr = data.close, data.high, data.low, data.atr
    day_open, adr = ctx["day_open"], ctx["adr20"]
    valid = (ctx["valid_day"] & np.isfinite(adr) & (adr > 0)
             & np.isfinite(atr) & (atr > 0)
             & (ctx["minute"] >= 120) & (ctx["minute"] < 1200))
    valid[:WARMUP_BARS] = False
    remove_state = candidate.get("remove_day_state", False)
    budget = ctx["day_high"] - ctx["day_low"] <= adr * candidate["max_range_adr"]
    long_state, short_state = budget & (c > day_open), budget & (c < day_open)
    family = candidate["family"]
    if family == "day_pullback":
        if 20 not in data.ema_cache:
            data.ema_cache[20] = _ema(c, 20)
        ema = data.ema_cache[20]
        long_signal = (_past(c) <= _past(ema)) & (c > ema)
        short_signal = (_past(c) >= _past(ema)) & (c < ema)
        threshold = adr * candidate["min_displacement_adr"]
        long_state &= c - day_open >= threshold
        short_state &= day_open - c >= threshold
    elif family == "previous_day_failed_break":
        upper, lower = ctx["previous_high"], ctx["previous_low"]
        span = h - l
        clv = np.divide(c - l, span, out=np.full(c.size, np.nan), where=span > 0)
        penetration = atr * candidate["penetration_atr"]
        long_signal = (l < lower - penetration) & (c > lower) & (c < upper) & (clv >= 0.70)
        short_signal = (h > upper + penetration) & (c < upper) & (c > lower) & (clv <= 0.30)
        long_state = budget & (c < day_open) & (day_open - ctx["day_low"] >= 0.20 * adr)
        short_state = budget & (c > day_open) & (ctx["day_high"] - day_open >= 0.20 * adr)
    elif family == "opening_range_retest":
        long_signal, short_signal = _retest(data, ctx, candidate["touch_atr"])
    else:
        raise ValueError(f"Unknown frozen candidate family: {family}")
    if not remove_state:
        long_signal &= long_state
        short_signal &= short_state
    result = np.zeros(c.size, dtype=np.int8)
    result[valid & (data.htf_trend == 1) & long_signal] = 1
    result[valid & (data.htf_trend == -1) & short_signal] = -1
    return result
