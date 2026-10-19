"""Frozen, causal 15-minute signal hypotheses for experiment quant70_20260908.

This module makes no execution or profitability decisions. Every nonzero signal
is observed at the source bar close and requires an already confirmed 4H trend.
"""

from __future__ import annotations

from itertools import product

import numpy as np

from research_strict_rr_portfolio import Prepared, _atr, _ema, _rolling_previous


WARMUP_BARS = 208


def candidates() -> list[dict]:
    """Return the complete 24-candidate search space, in a stable order."""
    rows = []
    for length, depth, extension in product((20, 40), (0.25, 0.50), (0.50, 1.00)):
        rows.append({
            "name": f"ema_reclaim_e{length}_d{depth:.2f}_x{extension:.2f}",
            "family": "ema_reclaim", "stop_atr": 2.0, "timeframe": "15m",
            "ema_length": length, "pullback_bars": 8,
            "min_depth_atr": depth, "max_extension_atr": extension,
            "ema_slope_bars": 4,
        })
    for lookback, penetration, location in product((16, 32), (0.0, 0.10), (0.60, 0.80)):
        rows.append({
            "name": f"range_sweep_l{lookback}_p{penetration:.2f}_c{location:.2f}",
            "family": "range_sweep", "stop_atr": 2.0, "timeframe": "15m",
            "lookback": lookback, "min_penetration_atr": penetration,
            "min_close_location": location,
        })
    for lookback, compression, buffer in product((8, 16), (0.70, 0.90), (0.0, 0.10)):
        rows.append({
            "name": f"compression_expansion_l{lookback}_r{compression:.2f}_b{buffer:.2f}",
            "family": "compression_expansion", "stop_atr": 2.0,
            "timeframe": "15m", "lookback": lookback,
            "max_atr_ratio": compression, "breakout_buffer_atr": buffer,
            "min_expansion_atr": 1.25, "slow_atr_length": 56,
        })
    return rows


def _past(values: np.ndarray, bars: int = 1) -> np.ndarray:
    result = np.full(values.size, np.nan)
    result[bars:] = values[:-bars]
    return result


def _range(data: Prepared, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    if lookback not in data.roll_cache:
        data.roll_cache[lookback] = (
            _rolling_previous(data.high, lookback, True),
            _rolling_previous(data.low, lookback, False),
        )
    return data.roll_cache[lookback]


def signals(data: Prepared, candidate: dict) -> np.ndarray:
    """Return -1/0/+1 decisions; never inspect subsequent bars or trade labels.

    Caller supplies chronological 15m Prepared data. The 4H state must have
    been mapped by _confirmed_four_hour_trend, as done by _prepare.
    """
    if candidate["timeframe"] != "15m" or candidate["stop_atr"] != 2.0:
        raise ValueError("Frozen experiment requires 15m and stop_atr=2.0")
    close, high, low, atr = data.close, data.high, data.low, data.atr
    valid = (
        np.isfinite(close) & np.isfinite(high) & np.isfinite(low)
        & np.isfinite(data.open) & np.isfinite(atr) & (atr > 0)
        & (high >= low)
    )
    valid[:WARMUP_BARS] = False
    family = candidate["family"]
    if family == "ema_reclaim":
        length = candidate["ema_length"]
        if length not in data.ema_cache:
            data.ema_cache[length] = _ema(close, length)
        ema = data.ema_cache[length]
        previous_ema = _past(ema)
        previous_close = _past(close)
        old_ema = _past(ema, candidate["ema_slope_bars"])
        scale = np.where(atr > 0, atr, np.nan)
        long_depth = _rolling_previous((ema - low) / scale, candidate["pullback_bars"], True)
        short_depth = _rolling_previous((high - ema) / scale, candidate["pullback_bars"], True)
        extension = atr * candidate["max_extension_atr"]
        long_signal = (
            (previous_close <= previous_ema) & (close > ema)
            & (close - ema <= extension) & (ema > old_ema)
            & (long_depth >= candidate["min_depth_atr"])
        )
        short_signal = (
            (previous_close >= previous_ema) & (close < ema)
            & (ema - close <= extension) & (ema < old_ema)
            & (short_depth >= candidate["min_depth_atr"])
        )
    elif family == "range_sweep":
        upper, lower = _range(data, candidate["lookback"])
        penetration = atr * candidate["min_penetration_atr"]
        span = high - low
        location = np.divide(close - low, span, out=np.full(close.size, np.nan), where=span > 0)
        long_signal = (
            (low < lower - penetration) & (close > lower) & (close < upper)
            & (location >= candidate["min_close_location"])
        )
        short_signal = (
            (high > upper + penetration) & (close < upper) & (close > lower)
            & (location <= 1.0 - candidate["min_close_location"])
        )
    elif family == "compression_expansion":
        upper, lower = _range(data, candidate["lookback"])
        slow_length = candidate["slow_atr_length"]
        if slow_length not in data.atr_cache:
            data.atr_cache[slow_length] = _atr(high, low, close, slow_length)
        previous_atr = _past(atr)
        previous_slow = _past(data.atr_cache[slow_length])
        compression = (
            (previous_slow > 0)
            & (previous_atr <= previous_slow * candidate["max_atr_ratio"])
        )
        previous_close = _past(close)
        true_range = np.maximum(high - low, np.maximum(abs(high - previous_close), abs(low - previous_close)))
        expansion = true_range >= previous_atr * candidate["min_expansion_atr"]
        buffer = atr * candidate["breakout_buffer_atr"]
        long_signal = compression & expansion & (close > upper + buffer)
        short_signal = compression & expansion & (close < lower - buffer)
    else:
        raise ValueError(f"Unknown frozen candidate family: {family}")
    result = np.zeros(close.size, dtype=np.int8)
    result[valid & (data.htf_trend == 1) & long_signal] = 1
    result[valid & (data.htf_trend == -1) & short_signal] = -1
    return result
