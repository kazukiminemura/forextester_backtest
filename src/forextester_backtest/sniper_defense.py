"""TP1 protection with next-bar stop changes and cost-aware weighted exits."""
from datetime import timedelta

MODES = ('breakeven_tp1', 'half_tp1', 'half_tp1_breakeven')


def defensive_outcome(bars, entry_index, side, atr, spread, mode):
    if mode not in MODES:
        raise ValueError(mode)
    first = bars[entry_index]
    slip, risk = .1*spread, 1.5*atr
    entry = first.open + (spread if side == 1 else 0) + side*slip
    stop, tp1, target = entry-side*risk, entry+side*atr, entry+side*3*atr
    deadline = first.time+timedelta(hours=4)
    remaining, booked, reached = 1., 0., False
    partial, breakeven = mode.startswith('half'), 'breakeven' in mode
    for j in range(entry_index, len(bars)):
        bar = bars[j]
        offset = spread if side == -1 else 0
        op, hi, lo = bar.open+offset, bar.high+offset, bar.low+offset
        due = bar.time >= deadline
        stopped = side*(op-stop) <= 0 if due else (lo <= stop if side == 1 else hi >= stop)
        final_hit = side*(op-target) >= 0 if due else (hi >= target if side == 1 else lo <= target)
        first_hit = side*(op-tp1) >= 0 if due else (hi >= tp1 if side == 1 else lo <= tp1)
        price, reason = None, ''
        if stopped:
            price = (op if due else min(op, stop) if side == 1 else max(op, stop))-side*slip
            reason = 'stop'
        elif final_hit:
            if partial and not reached:
                booked, remaining = .5*atr/risk, .5
            price, reason = target, 'target'
        else:
            if first_hit and not reached:
                reached = True
                if partial:
                    booked, remaining = .5*atr/risk, .5
                if breakeven:
                    stop = entry  # Effective on the next bar, never retroactive.
            if due:
                price, reason = op-side*slip, 'time'
        if price is not None:
            reward = booked+remaining*side*(price-entry)/risk
            late = int(bar.time > deadline or bar.time.date() != first.time.date())
            return j, reward, reason, late
    return None
