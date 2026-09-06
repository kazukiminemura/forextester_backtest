"""Causal breakout confirmations and explicitly ordered trade-management variants."""
import numpy as np

from .gold_signals import signals

ENTRY_MODES = ("direct", "impulse", "first_break", "retest3", "retest6")
EXIT_MODES = ("fixed1R", "fixed2R", "breakeven", "half1R", "half1R_breakeven")


def entry_signals(frame, dates, mode):
    raw = signals(frame, "breakout55")
    if mode == "direct":
        return raw
    previous = np.r_[0, raw[:-1]]
    if mode == "first_break":
        return np.where(raw != previous, raw, 0)
    op, hi, lo, close, atr = (frame[k].to_numpy() for k in ("open", "high", "low", "close", "atr"))
    if mode == "impulse":
        body = raw * (close-op)
        location = np.divide(np.where(raw == 1, close-lo, hi-close), hi-lo,
                             out=np.zeros(len(raw)), where=hi>lo)
        return np.where((body >= .5*atr) & (location >= .75), raw, 0)
    if mode not in ("retest3", "retest6"):
        raise ValueError(mode)
    wait = 3 if mode == "retest3" else 6
    highs, lows = frame.prior_high55.to_numpy(), frame.prior_low55.to_numpy()
    fast, slow = frame.ema50.to_numpy(), frame.ema200.to_numpy()
    result = np.zeros(len(raw), dtype=int)
    pending, born, level = 0, 0, 0.0
    for i in range(200, len(raw)):
        if pending:
            if i-born > wait or dates[i] != dates[born] or pending*(close[i]-level) < -.5*atr[i]:
                pending = 0
            else:
                trend = pending*(fast[i]-slow[i]) > 0 and pending*(slow[i]-slow[i-5]) > 0 and pending*(close[i]-slow[i]) > 0
                touch = lo[i] <= level+.25*atr[i] if pending == 1 else hi[i] >= level-.25*atr[i]
                recovered = pending*(close[i]-level) > 0 and pending*(close[i]-op[i]) > 0
                if trend and touch and recovered:
                    result[i] = pending
                    pending = 0
                    continue
        if not pending and raw[i] and raw[i] != previous[i]:
            pending, born = int(raw[i]), i
            level = highs[i] if pending == 1 else lows[i]
    return result


def managed_outcome(bars, entry_index, side, atr, spread, mode):
    """Stop-first; any new breakeven stop becomes active on the following bar."""
    if mode not in ("breakeven", "half1R", "half1R_breakeven"):
        raise ValueError(mode)
    first = bars[entry_index]
    slip, risk = .1*spread, 1.5*atr
    entry = first.open + (spread if side == 1 else 0) + side*slip
    stop, first_target, final_target = entry-side*risk, entry+side*risk, entry+side*2*risk
    deadline = first.time.replace(hour=20, minute=0, second=0)
    remaining, booked, reached_first = 1.0, 0.0, False
    partial = mode.startswith("half1R")
    breakeven = "breakeven" in mode
    for j in range(entry_index, len(bars)):
        bar = bars[j]
        offset = spread if side == -1 else 0
        op, hi, lo = bar.open+offset, bar.high+offset, bar.low+offset
        at_deadline = bar.time >= deadline
        stop_hit = side*(op-stop) <= 0 if at_deadline else (lo <= stop if side == 1 else hi >= stop)
        target_hit = side*(op-final_target) >= 0 if at_deadline else (hi >= final_target if side == 1 else lo <= final_target)
        first_hit = side*(op-first_target) >= 0 if at_deadline else (hi >= first_target if side == 1 else lo <= first_target)
        price, reason = None, ""
        if stop_hit:
            price = ((min(op,stop) if side == 1 else max(op,stop)) if not at_deadline else op)-side*slip
            reason = "stop"
        elif target_hit:
            if partial and not reached_first:
                booked += .5
                remaining = .5
            price, reason = final_target, "target"
        else:
            if first_hit and not reached_first:
                reached_first = True
                if partial:
                    booked += .5
                    remaining = .5
                if breakeven:
                    stop = entry
            if at_deadline:
                price, reason = op-side*slip, "time"
        if price is not None:
            reward = booked + remaining*side*(price-entry)/risk
            return j, reward, reason, int(bar.time > deadline or bar.time.date() != first.time.date())
    return None
