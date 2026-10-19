"""Confirmed-close failure detection; execution is always on the following open."""


def defensive_exit(bars, entry_index, side, atr, spread, level, baseline, mode):
    """Keep fixed barriers; replace an exit only after an earlier confirmed trigger.

    baseline is (exit_index, reward_r, reason, late). Its stop-first processing
    already proves every bar before exit_index survived the original barriers.
    """
    if mode == "baseline" or baseline is None:
        return baseline
    kind, length = mode.rsplit("_", 1)
    length = int(length)
    if kind not in ("failed", "stalled") or length < 1:
        raise ValueError(mode)
    first = bars[entry_index]
    risk, slip = 1.5 * atr, .1 * spread
    entry = first.open + (spread if side == 1 else 0) + side * slip
    stop, target = entry - side * risk, entry + side * 2 * risk
    deadline = first.time.replace(hour=20, minute=0, second=0)
    for j in range(entry_index, baseline[0]):
        close = bars[j].close + (spread if side == -1 else 0)
        age = j - entry_index + 1
        failed = age <= length and side * (bars[j].close - level) < 0
        stalled = age >= length and side * (close - entry) < 0
        if not (failed if kind == "failed" else stalled):
            continue
        nxt = bars[j + 1]
        if nxt.time >= deadline:
            return baseline
        op = nxt.open + (spread if side == -1 else 0)
        if side * (op - target) >= 0:
            price, reason = target, "target"
        elif side * (op - stop) <= 0:
            price, reason = op - side * slip, "stop"
        else:
            price, reason = op - side * slip, "defense"
        return j + 1, side * (price - entry) / risk, reason, 0
    return baseline
