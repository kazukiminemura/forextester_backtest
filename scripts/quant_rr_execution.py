"""Reward-risk parameterization of the frozen quant70 execution engine."""
from datetime import timedelta
import math
import numpy as np
from research_quant70 import Trade

def simulate(data, directions, symbol, start, end, pip, slip_pips=0.1, spread_scale=1.0, reward_risk=1.5):
    """One position per pair; no signal or position may cross a split."""
    if not math.isfinite(reward_risk) or reward_risk <= 0:
        raise ValueError("reward_risk must be finite and positive")
    spread = data.spread * spread_scale
    slip = pip * slip_pips
    times = data.times
    active = np.asarray([start <= t < end for t in times])
    eligible = np.flatnonzero(active & (directions != 0) & np.isfinite(data.atr))
    final_indices = np.flatnonzero(active)
    if not final_indices.size:
        return []
    last = int(final_indices[-1])
    trades = []
    next_signal = 0
    for raw in eligible:
        i = int(raw)
        if i < next_signal or i + 1 > last:
            continue
        j = i + 1
        if times[j] - times[i] != timedelta(minutes=15):
            continue
        direction = int(directions[i])
        if direction not in (-1, 1):
            raise ValueError('invalid direction')
        entry = float(data.open[j] + (spread if direction == 1 else 0) + direction * slip)
        stop = float(data.close[i] - direction * 2 * data.atr[i] + (spread if direction == -1 else 0))
        risk = direction * (entry - stop)
        if not math.isfinite(risk) or risk <= 0:
            continue
        target = entry + direction * risk * reward_risk
        ambiguous = False
        for k in range(j, last + 1):
            ask = spread if direction == -1 else 0
            opening = float(data.open[k] + ask)
            high, low = float(data.high[k] + ask), float(data.low[k] + ask)
            stop_gap = direction * (opening - stop) <= 0
            tp_gap = direction * (opening - target) >= 0
            hit_stop = low <= stop if direction == 1 else high >= stop
            hit_target = high >= target if direction == 1 else low <= target
            ambiguous = hit_stop and hit_target
            if stop_gap:
                price, reason = opening, 'stop_gap'
            elif tp_gap:
                price, reason = target, 'target_gap'
            elif hit_stop:
                price, reason = stop, 'stop'
            elif hit_target:
                price, reason = target, 'target'
            elif k == last:
                price, reason = float(data.close[k] + ask), 'period_end'
            else:
                continue
            price -= direction * slip
            net_r = direction * (price - entry) / risk
            trades.append(Trade(symbol, times[i].isoformat(), times[j].isoformat(),
                                times[k].isoformat(), direction, entry, stop, target,
                                price, net_r, reason, ambiguous))
            next_signal = k + 1  # No reuse of an exit bar as a new signal.
            break
    return trades

