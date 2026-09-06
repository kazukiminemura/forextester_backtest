"""Causal price-action candidates; independent of the proprietary Sniper product."""
import numpy as np
import pandas as pd

from .sniper import Technicals

FAMILIES = ("ema_reclaim", "pullback_break", "breakout20", "breakout55", "sweep20")


def features(bars):
    frame = pd.DataFrame({"open": [b.open for b in bars], "high": [b.high for b in bars],
                          "low": [b.low for b in bars], "close": [b.close for b in bars]})
    for length in (20, 50, 200):
        frame[f"ema{length}"] = frame.close.ewm(span=length, adjust=False).mean()
    ta = Technicals(dict(atrLength=14, emaLength=200, rsiLength=14, dmiLength=14, stFactor=3))
    atr = []
    for bar in bars:
        ta.update(bar)
        atr.append(ta.a)
    frame["atr"] = atr
    for length in (20, 55):
        frame[f"prior_high{length}"] = frame.high.shift(1).rolling(length).max()
        frame[f"prior_low{length}"] = frame.low.shift(1).rolling(length).min()
    return frame


def signals(frame, family):
    """Only current confirmed OHLC and prior bars; no pivots needing future bars."""
    c, h, lo = frame.close, frame.high, frame.low
    e20, e50, e200 = frame.ema20, frame.ema50, frame.ema200
    up = (e50 > e200) & (e200 > e200.shift(5)) & (c > e200)
    down = (e50 < e200) & (e200 < e200.shift(5)) & (c < e200)
    if family == "ema_reclaim":
        buy = up & (c > e20) & (c.shift(1) <= e20.shift(1))
        sell = down & (c < e20) & (c.shift(1) >= e20.shift(1))
    elif family == "pullback_break":
        buy = up & (lo.shift(1) <= e20.shift(1)) & (c > h.shift(1)) & (c > e20)
        sell = down & (h.shift(1) >= e20.shift(1)) & (c < lo.shift(1)) & (c < e20)
    elif family in ("breakout20", "breakout55"):
        length = 20 if family == "breakout20" else 55
        buy = up & (c > frame[f"prior_high{length}"])
        sell = down & (c < frame[f"prior_low{length}"])
    elif family == "sweep20":
        buy = up & (lo < frame.prior_low20) & (c > frame.prior_low20) & (c > frame.open)
        sell = down & (h > frame.prior_high20) & (c < frame.prior_high20) & (c < frame.open)
    else:
        raise ValueError(f"Unknown family: {family}")
    # Fixed warm-up, not selected using outcomes.
    ready = (np.arange(len(frame)) >= 200) & (frame.atr > 0)
    return np.where(ready & buy, 1, np.where(ready & sell, -1, 0))
