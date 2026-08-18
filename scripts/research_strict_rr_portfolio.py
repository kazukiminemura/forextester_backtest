"""Search new 5/15/30-minute portfolio strategies under strict RR 1:1 gates."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository

SYMBOLS = (
    "AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "USDCHF", "USDJPY",
    "AUDJPY", "CHFJPY", "EURCHF", "GBPCHF", "GBPJPY",
)
PERIODS = {
    "train_2010_2018": (2010, 2018, 108),
    "validation_2019_2022": (2019, 2022, 48),
    "holdout_2023_2024": (2023, 2024, 24),
    "true_oos_2025_2026": (2025, 2026, 19),
}


@dataclass(frozen=True, slots=True)
class Candidate:
    family: str
    timeframe: str = "30m"
    lookback: int = 16
    stop_atr: float = 1.0
    session_start: int = 6
    session_end: int = 16
    range_end: int = 6
    trend_fast: int = 80
    trend_slow: int = 200
    require_trend: bool = True
    buffer_atr: float = 0.0
    cooldown_bars: int = 0
    one_signal_per_day: bool = False
    band_length: int = 20
    band_deviation: float = 2.0
    rsi_length: int = 14
    rsi_threshold: float = 30.0
    entry_ema: int = 20
    atr_slow_length: int = 56
    compression_ratio: float = 0.8
    pullback_lookback: int = 8
    strength_threshold: float = 2.0
    invert_signal: bool = False
    signal_interval_minutes: int = 0
    atr_length: int = 14
    pivot_left: int = 3
    pivot_right: int = 3
    pa_min_score: int = 1
    zone_atr: float = 0.35
    swing_buffer_atr: float = 0.15
    max_risk_atr: float = 2.5
    trigger_break: bool = False
    ema_side_filter: bool = True
    max_trades_per_day: int = 0
    loss_cooldown_bars: int = 0


@dataclass(frozen=True, slots=True)
class RTrade:
    symbol: str
    entry_time: datetime
    result_r: float
    ambiguous_bar: bool = False


@dataclass(slots=True)
class Prepared:
    times: list[datetime]
    years: np.ndarray
    hours: np.ndarray
    minutes: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    atr: np.ndarray
    spread: float
    atr_cache: dict[int, np.ndarray]
    ema_cache: dict[int, np.ndarray]
    roll_cache: dict[int, tuple[np.ndarray, np.ndarray]]
    band_cache: dict[tuple[int, float], tuple[np.ndarray, np.ndarray]]
    rsi_cache: dict[int, np.ndarray]
    session_high: np.ndarray
    session_low: np.ndarray
    previous_day_high: np.ndarray
    previous_day_low: np.ndarray
    htf_trend: np.ndarray
    ltf_last_high: np.ndarray
    ltf_previous_high: np.ndarray
    ltf_last_low: np.ndarray
    ltf_previous_low: np.ndarray
    ltf_last_high_age: np.ndarray
    ltf_last_low_age: np.ndarray


def _is_pivot(
    values: np.ndarray, confirm_index: int, left: int, right: int, maximum: bool
) -> tuple[int, float] | None:
    pivot_index = confirm_index - right
    if pivot_index < left:
        return None
    start = pivot_index - left
    stop = pivot_index + right + 1
    window = values[start:stop]
    value = float(values[pivot_index])
    extreme = float(np.max(window) if maximum else np.min(window))
    if value != extreme or np.count_nonzero(window == value) != 1:
        return None
    return pivot_index, value


def _pivot_context(
    high: np.ndarray, low: np.ndarray, left: int, right: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    size = high.size
    last_high = np.full(size, np.nan)
    previous_high = np.full(size, np.nan)
    last_low = np.full(size, np.nan)
    previous_low = np.full(size, np.nan)
    high_age = np.full(size, np.iinfo(np.int32).max, dtype=np.int32)
    low_age = np.full(size, np.iinfo(np.int32).max, dtype=np.int32)
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for index in range(size):
        high_pivot = _is_pivot(high, index, left, right, True)
        low_pivot = _is_pivot(low, index, left, right, False)
        if high_pivot is not None:
            highs.append(high_pivot)
        if low_pivot is not None:
            lows.append(low_pivot)
        if highs:
            last_high[index] = highs[-1][1]
            high_age[index] = index - highs[-1][0]
        if len(highs) >= 2:
            previous_high[index] = highs[-2][1]
        if lows:
            last_low[index] = lows[-1][1]
            low_age[index] = index - lows[-1][0]
        if len(lows) >= 2:
            previous_low[index] = lows[-2][1]
    return last_high, previous_high, last_low, previous_low, high_age, low_age


def _confirmed_interval_context(
    times: list[datetime],
    high: np.ndarray,
    low: np.ndarray,
    interval_minutes: int,
    left: int,
    right: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return completed higher-interval pivots mapped onto each source bar."""
    if not times:
        empty = np.zeros(0)
        empty_age = np.zeros(0, dtype=np.int32)
        return empty, empty, empty, empty, empty_age, empty_age
    starts: list[datetime] = []
    highs: list[float] = []
    lows: list[float] = []
    group_for_bar = np.empty(len(times), dtype=np.int32)
    for index, time in enumerate(times):
        minute = (time.minute // interval_minutes) * interval_minutes
        start = time.replace(minute=minute, second=0, microsecond=0)
        if not starts or start != starts[-1]:
            starts.append(start)
            highs.append(float(high[index]))
            lows.append(float(low[index]))
        else:
            highs[-1] = max(highs[-1], float(high[index]))
            lows[-1] = min(lows[-1], float(low[index]))
        group_for_bar[index] = len(starts) - 1

    source_high = np.asarray(highs)
    source_low = np.asarray(lows)
    group_last_high = np.full(len(starts), np.nan)
    group_previous_high = np.full(len(starts), np.nan)
    group_last_low = np.full(len(starts), np.nan)
    group_previous_low = np.full(len(starts), np.nan)
    group_high_age = np.full(len(starts), np.iinfo(np.int32).max, dtype=np.int32)
    group_low_age = np.full(len(starts), np.iinfo(np.int32).max, dtype=np.int32)
    pivot_highs: list[tuple[int, float]] = []
    pivot_lows: list[tuple[int, float]] = []
    bars_per_interval = max(
        1,
        round(
            interval_minutes
            / max(1, int((times[1] - times[0]).total_seconds() // 60))
        ) if len(times) > 1 else 1,
    )
    for group_index in range(len(starts)):
        confirmed_index = group_index - 1
        if confirmed_index >= 0:
            high_pivot = _is_pivot(
                source_high, confirmed_index, left, right, True
            )
            low_pivot = _is_pivot(
                source_low, confirmed_index, left, right, False
            )
            if high_pivot is not None:
                pivot_highs.append(high_pivot)
            if low_pivot is not None:
                pivot_lows.append(low_pivot)
        if pivot_highs:
            group_last_high[group_index] = pivot_highs[-1][1]
            group_high_age[group_index] = (
                group_index - pivot_highs[-1][0]
            ) * bars_per_interval
        if len(pivot_highs) >= 2:
            group_previous_high[group_index] = pivot_highs[-2][1]
        if pivot_lows:
            group_last_low[group_index] = pivot_lows[-1][1]
            group_low_age[group_index] = (
                group_index - pivot_lows[-1][0]
            ) * bars_per_interval
        if len(pivot_lows) >= 2:
            group_previous_low[group_index] = pivot_lows[-2][1]
    return (
        group_last_high[group_for_bar],
        group_previous_high[group_for_bar],
        group_last_low[group_for_bar],
        group_previous_low[group_for_bar],
        group_high_age[group_for_bar],
        group_low_age[group_for_bar],
    )


def _confirmed_four_hour_trend(
    times: list[datetime], high: np.ndarray, low: np.ndarray
) -> np.ndarray:
    """Map confirmed 4H Dow state to lower bars without using the open 4H candle."""
    if not times:
        return np.zeros(0, dtype=np.int8)
    group_starts: list[datetime] = []
    group_highs: list[float] = []
    group_lows: list[float] = []
    group_for_bar = np.empty(len(times), dtype=np.int32)
    for index, time in enumerate(times):
        start = time.replace(hour=(time.hour // 4) * 4, minute=0, second=0, microsecond=0)
        if not group_starts or start != group_starts[-1]:
            group_starts.append(start)
            group_highs.append(float(high[index]))
            group_lows.append(float(low[index]))
        else:
            group_highs[-1] = max(group_highs[-1], float(high[index]))
            group_lows[-1] = min(group_lows[-1], float(low[index]))
        group_for_bar[index] = len(group_starts) - 1

    htf_high = np.asarray(group_highs)
    htf_low = np.asarray(group_lows)
    states = np.zeros(len(group_starts), dtype=np.int8)
    highs: list[float] = []
    lows: list[float] = []
    trend = 0
    for group_index in range(len(group_starts)):
        # group_index is the newly opened candle. Only group_index - 1 and
        # earlier are confirmed and may update the state used by this candle.
        confirmed_index = group_index - 1
        if confirmed_index >= 0:
            high_pivot = _is_pivot(htf_high, confirmed_index, 2, 2, True)
            low_pivot = _is_pivot(htf_low, confirmed_index, 2, 2, False)
            if high_pivot is not None:
                highs.append(high_pivot[1])
            if low_pivot is not None:
                lows.append(low_pivot[1])
            if len(highs) >= 2 and len(lows) >= 2:
                if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                    trend = 1
                elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                    trend = -1
        states[group_index] = trend
    return states[group_for_bar]


def _ema(values: np.ndarray, length: int) -> np.ndarray:
    out = np.full(values.size, np.nan)
    if values.size < length:
        return out
    current = float(np.mean(values[:length]))
    out[length - 1] = current
    alpha = 2.0 / (length + 1)
    for index in range(length, values.size):
        current += alpha * (float(values[index]) - current)
        out[index] = current
    return out


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 14) -> np.ndarray:
    tr = high - low
    if close.size > 1:
        tr[1:] = np.maximum(
            tr[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1]))
        )
    out = np.full(close.size, np.nan)
    if close.size < length:
        return out
    current = float(np.mean(tr[:length]))
    out[length - 1] = current
    for index in range(length, close.size):
        current = (current * (length - 1) + float(tr[index])) / length
        out[index] = current
    return out


def _bands(values: np.ndarray, length: int, deviation: float) -> tuple[np.ndarray, np.ndarray]:
    total = np.cumsum(np.insert(values, 0, 0.0))
    squared = np.cumsum(np.insert(values * values, 0, 0.0))
    mean = np.full(values.size, np.nan)
    std = np.full(values.size, np.nan)
    sums = total[length:] - total[:-length]
    sums_sq = squared[length:] - squared[:-length]
    mean[length - 1:] = sums / length
    variance = np.maximum(sums_sq / length - (sums / length) ** 2, 0.0)
    std[length - 1:] = np.sqrt(variance)
    return mean - std * deviation, mean + std * deviation


def _rsi(values: np.ndarray, length: int) -> np.ndarray:
    out = np.full(values.size, np.nan)
    if values.size <= length:
        return out
    changes = np.diff(values, prepend=values[0])
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    avg_gain = float(np.mean(gains[1:length + 1]))
    avg_loss = float(np.mean(losses[1:length + 1]))
    for index in range(length, values.size):
        if index > length:
            avg_gain = (avg_gain * (length - 1) + float(gains[index])) / length
            avg_loss = (avg_loss * (length - 1) + float(losses[index])) / length
        out[index] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def _rolling_previous(values: np.ndarray, length: int, maximum: bool) -> np.ndarray:
    out = np.full(values.size, np.nan)
    queue: deque[int] = deque()
    for index in range(values.size):
        while queue and queue[0] < index - length:
            queue.popleft()
        if queue:
            out[index] = values[queue[0]]
        while queue and ((values[queue[-1]] <= values[index]) if maximum else (values[queue[-1]] >= values[index])):
            queue.pop()
        queue.append(index)
    return out


def _session_ranges(times: list[datetime], high: np.ndarray, low: np.ndarray, end_hour: int) -> tuple[np.ndarray, np.ndarray]:
    upper = np.full(high.size, np.nan)
    lower = np.full(low.size, np.nan)
    current_day = None
    day_high = -np.inf
    day_low = np.inf
    for index, time in enumerate(times):
        if time.date() != current_day:
            current_day = time.date()
            day_high = -np.inf
            day_low = np.inf
        if time.hour < end_hour:
            day_high = max(day_high, float(high[index]))
            day_low = min(day_low, float(low[index]))
        elif np.isfinite(day_high):
            upper[index] = day_high
            lower[index] = day_low
    return upper, lower


def _previous_day_levels(
    times: list[datetime], high: np.ndarray, low: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    upper = np.full(high.size, np.nan)
    lower = np.full(low.size, np.nan)
    current_day = None
    day_high = -np.inf
    day_low = np.inf
    previous_high = np.nan
    previous_low = np.nan
    for index, time in enumerate(times):
        if time.date() != current_day:
            if current_day is not None:
                previous_high = day_high
                previous_low = day_low
            current_day = time.date()
            day_high = -np.inf
            day_low = np.inf
        upper[index] = previous_high
        lower[index] = previous_low
        day_high = max(day_high, float(high[index]))
        day_low = min(day_low, float(low[index]))
    return upper, lower


def _prepare(repository: HistoryRepository, symbol: str, end: datetime, timeframe: str) -> Prepared:
    bars = list(repository.bars(symbol, datetime(2010, 1, 1), end, timeframe))
    times = [bar.time for bar in bars]
    high = np.asarray([bar.high for bar in bars], dtype=float)
    low = np.asarray([bar.low for bar in bars], dtype=float)
    close = np.asarray([bar.close for bar in bars], dtype=float)
    session_high, session_low = _session_ranges(times, high, low, 6)
    previous_day_high, previous_day_low = _previous_day_levels(times, high, low)
    atr = _atr(high, low, close)
    (
        ltf_last_high,
        ltf_previous_high,
        ltf_last_low,
        ltf_previous_low,
        ltf_last_high_age,
        ltf_last_low_age,
    ) = _confirmed_interval_context(times, high, low, 15, 2, 2)
    return Prepared(
        times=times,
        years=np.asarray([time.year for time in times]),
        hours=np.asarray([time.hour for time in times]),
        minutes=np.asarray([time.minute for time in times]),
        open=np.asarray([bar.open for bar in bars], dtype=float),
        high=high,
        low=low,
        close=close,
        atr=atr,
        spread=repository.metadata(symbol).spread_price,
        atr_cache={14: atr},
        ema_cache={},
        roll_cache={},
        band_cache={},
        rsi_cache={},
        session_high=session_high,
        session_low=session_low,
        previous_day_high=previous_day_high,
        previous_day_low=previous_day_low,
        htf_trend=_confirmed_four_hour_trend(times, high, low),
        ltf_last_high=ltf_last_high,
        ltf_previous_high=ltf_previous_high,
        ltf_last_low=ltf_last_low,
        ltf_previous_low=ltf_previous_low,
        ltf_last_high_age=ltf_last_high_age,
        ltf_last_low_age=ltf_last_low_age,
    )


def _signals(data: Prepared, candidate: Candidate) -> np.ndarray:
    if candidate.trend_fast not in data.ema_cache:
        data.ema_cache[candidate.trend_fast] = _ema(data.close, candidate.trend_fast)
    if candidate.trend_slow not in data.ema_cache:
        data.ema_cache[candidate.trend_slow] = _ema(data.close, candidate.trend_slow)
    fast = data.ema_cache[candidate.trend_fast]
    slow = data.ema_cache[candidate.trend_slow]
    trend_slope_bars = {"5m": 48, "15m": 16, "30m": 8}[candidate.timeframe]
    long_trend = (fast > slow) & (fast > np.roll(fast, trend_slope_bars))
    short_trend = (fast < slow) & (fast < np.roll(fast, trend_slope_bars))
    session = (data.hours >= candidate.session_start) & (data.hours < candidate.session_end)
    if candidate.signal_interval_minutes:
        session &= data.minutes % candidate.signal_interval_minutes == 0
    previous_close = np.roll(data.close, 1)
    direction = np.zeros(data.close.size, dtype=np.int8)

    if candidate.family == "trend_breakout":
        if candidate.lookback not in data.roll_cache:
            data.roll_cache[candidate.lookback] = (
                _rolling_previous(data.high, candidate.lookback, True),
                _rolling_previous(data.low, candidate.lookback, False),
            )
        upper, lower = data.roll_cache[candidate.lookback]
        long_signal = session & (data.close > upper) & (previous_close <= upper)
        short_signal = session & (data.close < lower) & (previous_close >= lower)
    elif candidate.family == "range_reclaim":
        if candidate.lookback not in data.roll_cache:
            data.roll_cache[candidate.lookback] = (
                _rolling_previous(data.high, candidate.lookback, True),
                _rolling_previous(data.low, candidate.lookback, False),
            )
        upper, lower = data.roll_cache[candidate.lookback]
        long_signal = session & (data.low < lower) & (data.close > lower)
        short_signal = session & (data.high > upper) & (data.close < upper)
    elif candidate.family in ("session_breakout", "session_fade"):
        upper = data.session_high
        lower = data.session_low
        buffer = data.atr * candidate.buffer_atr
        if candidate.family == "session_breakout":
            long_signal = session & (data.close > upper + buffer) & (previous_close <= upper + buffer)
            short_signal = session & (data.close < lower - buffer) & (previous_close >= lower - buffer)
        elif candidate.family == "session_fade":
            long_signal = session & (data.low < lower - buffer) & (data.close > lower)
            short_signal = session & (data.high > upper + buffer) & (data.close < upper)
    elif candidate.family == "bollinger_reversion":
        key = (candidate.band_length, candidate.band_deviation)
        if key not in data.band_cache:
            data.band_cache[key] = _bands(data.close, *key)
        lower, upper = data.band_cache[key]
        previous_lower = np.roll(lower, 1)
        previous_upper = np.roll(upper, 1)
        long_signal = session & (previous_close < previous_lower) & (data.close >= lower)
        short_signal = session & (previous_close > previous_upper) & (data.close <= upper)
    elif candidate.family == "rsi_reversion":
        if candidate.rsi_length not in data.rsi_cache:
            data.rsi_cache[candidate.rsi_length] = _rsi(data.close, candidate.rsi_length)
        rsi = data.rsi_cache[candidate.rsi_length]
        previous_rsi = np.roll(rsi, 1)
        long_signal = session & (previous_rsi < candidate.rsi_threshold) & (rsi >= candidate.rsi_threshold)
        upper_threshold = 100.0 - candidate.rsi_threshold
        short_signal = session & (previous_rsi > upper_threshold) & (rsi <= upper_threshold)
    elif candidate.family == "ema_pullback":
        if candidate.entry_ema not in data.ema_cache:
            data.ema_cache[candidate.entry_ema] = _ema(data.close, candidate.entry_ema)
        entry_ema = data.ema_cache[candidate.entry_ema]
        long_signal = session & (previous_close <= np.roll(entry_ema, 1)) & (data.close > entry_ema)
        short_signal = session & (previous_close >= np.roll(entry_ema, 1)) & (data.close < entry_ema)
    elif candidate.family in ("daily_level_fade", "daily_level_breakout"):
        upper = data.previous_day_high
        lower = data.previous_day_low
        buffer = data.atr * candidate.buffer_atr
        if candidate.family == "daily_level_fade":
            long_signal = session & (data.low < lower - buffer) & (data.close > lower)
            short_signal = session & (data.high > upper + buffer) & (data.close < upper)
        else:
            long_signal = session & (data.close > upper + buffer) & (previous_close <= upper + buffer)
            short_signal = session & (data.close < lower - buffer) & (previous_close >= lower - buffer)
    elif candidate.family in ("impulse_continue", "impulse_fade"):
        body = data.close - data.open
        large_up = body >= data.atr * candidate.buffer_atr
        large_down = -body >= data.atr * candidate.buffer_atr
        if candidate.family == "impulse_continue":
            long_signal = session & large_up
            short_signal = session & large_down
        else:
            long_signal = session & large_down
            short_signal = session & large_up
    elif candidate.family == "compression_breakout":
        if candidate.lookback not in data.roll_cache:
            data.roll_cache[candidate.lookback] = (
                _rolling_previous(data.high, candidate.lookback, True),
                _rolling_previous(data.low, candidate.lookback, False),
            )
        if candidate.atr_slow_length not in data.atr_cache:
            data.atr_cache[candidate.atr_slow_length] = _atr(
                data.high, data.low, data.close, candidate.atr_slow_length
            )
        upper, lower = data.roll_cache[candidate.lookback]
        slow_atr = data.atr_cache[candidate.atr_slow_length]
        compressed = np.roll(data.atr, 1) <= (
            np.roll(slow_atr, 1) * candidate.compression_ratio
        )
        long_signal = session & compressed & (data.close > upper) & (previous_close <= upper)
        short_signal = session & compressed & (data.close < lower) & (previous_close >= lower)
    elif candidate.family == "pullback_breakout":
        if candidate.entry_ema not in data.ema_cache:
            data.ema_cache[candidate.entry_ema] = _ema(data.close, candidate.entry_ema)
        if candidate.lookback not in data.roll_cache:
            data.roll_cache[candidate.lookback] = (
                _rolling_previous(data.high, candidate.lookback, True),
                _rolling_previous(data.low, candidate.lookback, False),
            )
        pullback_key = -candidate.pullback_lookback
        if pullback_key not in data.roll_cache:
            data.roll_cache[pullback_key] = (
                _rolling_previous(data.high, candidate.pullback_lookback, True),
                _rolling_previous(data.low, candidate.pullback_lookback, False),
            )
        upper, lower = data.roll_cache[candidate.lookback]
        pullback_high, pullback_low = data.roll_cache[pullback_key]
        entry_ema = data.ema_cache[candidate.entry_ema]
        long_signal = (
            session & (pullback_low <= entry_ema) &
            (data.close > upper) & (previous_close <= upper)
        )
        short_signal = (
            session & (pullback_high >= entry_ema) &
            (data.close < lower) & (previous_close >= lower)
        )
    elif candidate.family == "yosuga_pa":
        if candidate.entry_ema not in data.ema_cache:
            data.ema_cache[candidate.entry_ema] = _ema(
                data.close, candidate.entry_ema
            )
        entry_ema = data.ema_cache[candidate.entry_ema]
        previous_open = np.roll(data.open, 1)
        previous_high = np.roll(data.high, 1)
        previous_low = np.roll(data.low, 1)
        body = np.maximum(np.abs(data.close - data.open), data.atr * 0.05)
        upper_wick = data.high - np.maximum(data.open, data.close)
        lower_wick = np.minimum(data.open, data.close) - data.low
        long_lower = (lower_wick >= body * 1.5) & (lower_wick >= data.atr * 0.25)
        long_upper = (upper_wick >= body * 1.5) & (upper_wick >= data.atr * 0.25)
        bull_engulf = (
            (data.close > data.open)
            & (previous_close < previous_open)
            & (data.close >= previous_open)
            & (data.open <= previous_close)
        )
        bear_engulf = (
            (data.close < data.open)
            & (previous_close > previous_open)
            & (data.close <= previous_open)
            & (data.open >= previous_close)
        )
        bull_score = long_lower.astype(np.int8) + bull_engulf.astype(np.int8)
        bear_score = long_upper.astype(np.int8) + bear_engulf.astype(np.int8)
        tolerance = data.atr * candidate.zone_atr
        fresh_low = data.ltf_last_low_age <= candidate.pullback_lookback
        fresh_high = data.ltf_last_high_age <= candidate.pullback_lookback
        at_support = (
            (np.abs(data.low - data.ltf_last_low) <= tolerance)
            | ((data.low <= entry_ema + tolerance) & (data.close >= entry_ema))
        )
        at_resistance = (
            (np.abs(data.high - data.ltf_last_high) <= tolerance)
            | ((data.high >= entry_ema - tolerance) & (data.close <= entry_ema))
        )
        long_trigger = (
            data.close > previous_high
            if candidate.trigger_break
            else np.ones(data.close.size, dtype=bool)
        )
        short_trigger = (
            data.close < previous_low
            if candidate.trigger_break
            else np.ones(data.close.size, dtype=bool)
        )
        long_signal = (
            session
            & (data.htf_trend == 1)
            & (data.ltf_last_low > data.ltf_previous_low)
            & fresh_low
            & at_support
            & (bull_score >= candidate.pa_min_score)
            & long_trigger
        )
        short_signal = (
            session
            & (data.htf_trend == -1)
            & (data.ltf_last_high < data.ltf_previous_high)
            & fresh_high
            & at_resistance
            & (bear_score >= candidate.pa_min_score)
            & short_trigger
        )
    elif candidate.family == "yosuga_sweep":
        if candidate.entry_ema not in data.ema_cache:
            data.ema_cache[candidate.entry_ema] = _ema(
                data.close, candidate.entry_ema
            )
        entry_ema = data.ema_cache[candidate.entry_ema]
        previous_high = np.roll(data.high, 1)
        previous_low = np.roll(data.low, 1)
        fresh_low = data.ltf_last_low_age <= candidate.pullback_lookback
        fresh_high = data.ltf_last_high_age <= candidate.pullback_lookback
        reclaimed_support = (
            (data.low < data.ltf_last_low)
            & (data.close > data.ltf_last_low)
            & (data.close > data.open)
        )
        rejected_resistance = (
            (data.high > data.ltf_last_high)
            & (data.close < data.ltf_last_high)
            & (data.close < data.open)
        )
        long_trigger = (
            data.close > previous_high
            if candidate.trigger_break
            else np.ones(data.close.size, dtype=bool)
        )
        short_trigger = (
            data.close < previous_low
            if candidate.trigger_break
            else np.ones(data.close.size, dtype=bool)
        )
        long_ema_ok = (
            data.close >= entry_ema
            if candidate.ema_side_filter
            else np.ones(data.close.size, dtype=bool)
        )
        short_ema_ok = (
            data.close <= entry_ema
            if candidate.ema_side_filter
            else np.ones(data.close.size, dtype=bool)
        )
        long_signal = (
            session
            & (data.htf_trend == 1)
            & (data.ltf_last_low > data.ltf_previous_low)
            & fresh_low
            & reclaimed_support
            & long_trigger
            & long_ema_ok
        )
        short_signal = (
            session
            & (data.htf_trend == -1)
            & (data.ltf_last_high < data.ltf_previous_high)
            & fresh_high
            & rejected_resistance
            & short_trigger
            & short_ema_ok
        )
    elif candidate.family == "yosuga_15m":
        if candidate.entry_ema not in data.ema_cache:
            data.ema_cache[candidate.entry_ema] = _ema(
                data.close, candidate.entry_ema
            )
        if candidate.lookback not in data.roll_cache:
            data.roll_cache[candidate.lookback] = (
                _rolling_previous(data.high, candidate.lookback, True),
                _rolling_previous(data.low, candidate.lookback, False),
            )
        pullback_key = -candidate.pullback_lookback
        if pullback_key not in data.roll_cache:
            data.roll_cache[pullback_key] = (
                _rolling_previous(data.high, candidate.pullback_lookback, True),
                _rolling_previous(data.low, candidate.pullback_lookback, False),
            )
        entry_ema = data.ema_cache[candidate.entry_ema]
        upper, lower = data.roll_cache[candidate.lookback]
        pullback_high, pullback_low = data.roll_cache[pullback_key]
        structure_up = (
            (data.ltf_last_high > data.ltf_previous_high)
            & (data.ltf_last_low > data.ltf_previous_low)
        )
        structure_down = (
            (data.ltf_last_high < data.ltf_previous_high)
            & (data.ltf_last_low < data.ltf_previous_low)
        )
        aligned_up = (fast > slow) & (data.close > fast)
        aligned_down = (fast < slow) & (data.close < fast)
        recent_low = data.ltf_last_low_age <= candidate.pullback_lookback
        recent_high = data.ltf_last_high_age <= candidate.pullback_lookback
        long_signal = (
            session
            & (data.htf_trend == 1)
            & aligned_up
            & structure_up
            & recent_low
            & (pullback_low <= entry_ema + data.atr * candidate.zone_atr)
            & (data.close > upper)
            & (previous_close <= upper)
        )
        short_signal = (
            session
            & (data.htf_trend == -1)
            & aligned_down
            & structure_down
            & recent_high
            & (pullback_high >= entry_ema - data.atr * candidate.zone_atr)
            & (data.close < lower)
            & (previous_close >= lower)
        )
    else:
        raise ValueError(f"unknown family: {candidate.family}")
    if candidate.require_trend:
        long_signal &= long_trend
        short_signal &= short_trend
    if candidate.invert_signal:
        long_signal, short_signal = short_signal, long_signal
    direction[long_signal] = 1
    direction[short_signal] = -1
    direction[: max(candidate.trend_slow, candidate.lookback) + 8] = 0
    if candidate.one_signal_per_day:
        last_day = None
        for index in np.flatnonzero(direction):
            day = data.times[int(index)].date()
            if day == last_day:
                direction[index] = 0
            else:
                last_day = day
    return direction


def _simulate(
    symbol: str,
    data: Prepared,
    candidate: Candidate,
    directions: np.ndarray | None = None,
) -> list[RTrade]:
    if directions is None:
        directions = _signals(data, candidate)
    signal_indices = np.flatnonzero(directions)
    trades: list[RTrade] = []
    cursor = 0
    last_loss_exit = -1_000_000
    daily_entries: dict[object, int] = {}
    while cursor < signal_indices.size:
        signal_index = int(signal_indices[cursor])
        entry_index = signal_index + 1
        if candidate.atr_length not in data.atr_cache:
            data.atr_cache[candidate.atr_length] = _atr(
                data.high, data.low, data.close, candidate.atr_length
            )
        stop_atr = data.atr_cache[candidate.atr_length]
        if entry_index >= data.close.size or not np.isfinite(stop_atr[signal_index]):
            break
        if signal_index - last_loss_exit <= candidate.loss_cooldown_bars:
            cursor += 1
            continue
        entry_day = data.times[entry_index].date()
        if (
            candidate.max_trades_per_day > 0
            and daily_entries.get(entry_day, 0) >= candidate.max_trades_per_day
        ):
            cursor += 1
            continue
        direction = int(directions[signal_index])
        if candidate.family == "yosuga_sweep" and direction == 1:
            entry = float(data.open[entry_index] + data.spread)
            stop = float(
                data.low[signal_index]
                - stop_atr[signal_index] * candidate.swing_buffer_atr
            )
            risk = entry - stop
            target = entry + risk
        elif candidate.family == "yosuga_sweep":
            entry = float(data.open[entry_index])
            stop = float(
                data.high[signal_index]
                + stop_atr[signal_index] * candidate.swing_buffer_atr
                + data.spread
            )
            risk = stop - entry
            target = entry - risk
        elif candidate.family in ("yosuga_pa", "yosuga_15m") and direction == 1:
            entry = float(data.open[entry_index] + data.spread)
            stop = float(
                data.ltf_last_low[signal_index]
                - stop_atr[signal_index] * candidate.swing_buffer_atr
            )
            risk = entry - stop
            target = entry + risk
        elif candidate.family in ("yosuga_pa", "yosuga_15m"):
            entry = float(data.open[entry_index])
            stop = float(
                data.ltf_last_high[signal_index]
                + stop_atr[signal_index] * candidate.swing_buffer_atr
                + data.spread
            )
            risk = stop - entry
            target = entry - risk
        elif direction == 1:
            entry = float(data.open[entry_index] + data.spread)
            stop = float(data.close[signal_index] - stop_atr[signal_index] * candidate.stop_atr)
            risk = entry - stop
            target = entry + risk
        else:
            entry = float(data.open[entry_index])
            stop = float(data.close[signal_index] + stop_atr[signal_index] * candidate.stop_atr + data.spread)
            risk = stop - entry
            target = entry - risk
        if (
            risk <= 0
            or (
                candidate.family in ("yosuga_pa", "yosuga_sweep", "yosuga_15m")
                and risk > stop_atr[signal_index] * candidate.max_risk_atr
            )
        ):
            cursor += 1
            continue
        daily_entries[entry_day] = daily_entries.get(entry_day, 0) + 1
        exit_index = entry_index
        while exit_index < data.close.size:
            if direction == 1:
                hit_stop = data.low[exit_index] <= stop
                hit_target = data.high[exit_index] >= target
            else:
                hit_stop = data.high[exit_index] + data.spread >= stop
                hit_target = data.low[exit_index] + data.spread <= target
            if hit_stop or hit_target:
                trades.append(
                    RTrade(
                        symbol,
                        data.times[entry_index],
                        -1.0 if hit_stop else 1.0,
                        hit_stop and hit_target,
                    )
                )
                if hit_stop:
                    last_loss_exit = exit_index
                break
            exit_index += 1
        cursor = int(
            np.searchsorted(signal_indices, exit_index + 1 + candidate.cooldown_bars)
        )
    return trades


def _currency_strength_scores(
    prepared: dict[str, Prepared], lookback: int
) -> dict[str, np.ndarray]:
    timestamp_arrays = {
        symbol: np.asarray(data.times, dtype="datetime64[us]")
        for symbol, data in prepared.items()
    }
    common_times = timestamp_arrays[SYMBOLS[0]]
    for symbol in SYMBOLS[1:]:
        common_times = np.intersect1d(
            common_times, timestamp_arrays[symbol], assume_unique=True
        )
    common_indices = {
        symbol: np.searchsorted(timestamp_arrays[symbol], common_times)
        for symbol in SYMBOLS
    }
    currencies = sorted({currency for symbol in SYMBOLS for currency in (symbol[:3], symbol[3:])})
    sums = {currency: np.zeros(common_times.size) for currency in currencies}
    counts = {currency: 0 for currency in currencies}
    contributions: dict[str, np.ndarray] = {}
    for symbol in SYMBOLS:
        data = prepared[symbol]
        previous = np.roll(data.close, lookback)
        normalized_return = np.log(data.close / previous) / np.maximum(
            data.atr / data.close, 1e-12
        )
        normalized_return[:lookback] = np.nan
        contributions[symbol] = normalized_return[common_indices[symbol]]
        base, quote = symbol[:3], symbol[3:]
        sums[base] += np.nan_to_num(contributions[symbol])
        sums[quote] -= np.nan_to_num(contributions[symbol])
        counts[base] += 1
        counts[quote] += 1
    scores = {}
    for symbol, contribution in contributions.items():
        base, quote = symbol[:3], symbol[3:]
        if counts[base] > 1:
            base_strength = (
                sums[base] - np.nan_to_num(contribution)
            ) / (counts[base] - 1)
        else:
            base_strength = sums[base]
        if counts[quote] > 1:
            quote_strength = (
                sums[quote] + np.nan_to_num(contribution)
            ) / (counts[quote] - 1)
        else:
            quote_strength = sums[quote]
        aligned_score = base_strength - quote_strength
        full_score = np.full(prepared[symbol].close.size, np.nan)
        full_score[common_indices[symbol]] = aligned_score
        full_score[:lookback] = np.nan
        scores[symbol] = full_score
    return scores


def _currency_strength_signals(
    prepared: dict[str, Prepared], candidate: Candidate, scores: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    output = {}
    for symbol, data in prepared.items():
        score = scores[symbol]
        previous_score = np.roll(score, 1)
        session = (data.hours >= candidate.session_start) & (data.hours < candidate.session_end)
        long_signal = session & (score >= candidate.strength_threshold) & (
            previous_score < candidate.strength_threshold
        )
        short_signal = session & (score <= -candidate.strength_threshold) & (
            previous_score > -candidate.strength_threshold
        )
        if candidate.invert_signal:
            long_signal, short_signal = short_signal, long_signal
        if candidate.require_trend:
            if candidate.trend_fast not in data.ema_cache:
                data.ema_cache[candidate.trend_fast] = _ema(data.close, candidate.trend_fast)
            if candidate.trend_slow not in data.ema_cache:
                data.ema_cache[candidate.trend_slow] = _ema(data.close, candidate.trend_slow)
            fast = data.ema_cache[candidate.trend_fast]
            slow = data.ema_cache[candidate.trend_slow]
            long_signal &= fast > slow
            short_signal &= fast < slow
        direction = np.zeros(data.close.size, dtype=np.int8)
        direction[long_signal] = 1
        direction[short_signal] = -1
        direction[: max(candidate.trend_slow, candidate.lookback) + 8] = 0
        output[symbol] = direction
    return output


def _stats(trades: list[RTrade], start_year: int, end_year: int, months: int) -> dict[str, float | int | None]:
    rows = [trade for trade in trades if start_year <= trade.entry_time.year <= end_year]
    wins = sum(trade.result_r > 0 for trade in rows)
    losses = sum(trade.result_r < 0 for trade in rows)
    ambiguous = int(sum(bool(trade.ambiguous_bar) for trade in rows))
    return {
        "trades": len(rows), "wins": wins,
        "win_rate": wins / len(rows) * 100 if rows else 0.0,
        "profit_factor": wins / losses if losses else None,
        "expectancy_r": sum(trade.result_r for trade in rows) / len(rows) if rows else 0.0,
        "trades_per_month": len(rows) / months,
        "ambiguous_bars": ambiguous,
        "ambiguous_rate": ambiguous / len(rows) * 100 if rows else 0.0,
    }


def _passes(stats: dict[str, float | int | None]) -> bool:
    return (
        float(stats["profit_factor"] or 0.0) >= 1.15
        and float(stats["expectancy_r"]) > 0
        and float(stats["trades_per_month"]) >= 3.0
    )


def _candidates(timeframe: str, families: str) -> list[Candidate]:
    multiplier = {"5m": 6, "15m": 2, "30m": 1}[timeframe]
    if families == "yosuga-fifteen-minute":
        if timeframe != "15m":
            raise ValueError("yosuga-fifteen-minute family requires --timeframe 15m")
        return [
            Candidate(
                "yosuga_15m",
                timeframe="15m",
                lookback=lookback,
                session_start=start,
                session_end=end,
                trend_fast=20,
                trend_slow=50,
                require_trend=False,
                entry_ema=20,
                atr_length=14,
                pullback_lookback=pullback,
                zone_atr=zone,
                swing_buffer_atr=buffer,
                max_risk_atr=2.5,
                cooldown_bars=4,
                max_trades_per_day=3,
                loss_cooldown_bars=loss_cooldown,
            )
            for lookback, (start, end), pullback, zone, buffer, loss_cooldown in product(
                (3, 5),
                ((6, 16), (6, 20)),
                (8, 16),
                (0.20, 0.40),
                (0.10, 0.20),
                (4, 8),
            )
        ]
    if families == "yosuga-five-minute":
        if timeframe != "5m":
            raise ValueError("yosuga-five-minute family requires --timeframe 5m")
        return [
            Candidate(
                "yosuga_pa",
                timeframe="5m",
                session_start=start,
                session_end=end,
                require_trend=False,
                entry_ema=150,
                atr_length=42,
                pullback_lookback=pullback,
                pa_min_score=pa_score,
                zone_atr=zone,
                swing_buffer_atr=buffer,
                max_risk_atr=2.5,
                trigger_break=trigger,
                cooldown_bars=12,
            )
            for (start, end), pullback, pa_score, zone, buffer, trigger in product(
                ((6, 16), (6, 20)),
                (24, 48),
                (1, 2),
                (0.25, 0.50),
                (0.10, 0.20),
                (False, True),
            )
        ]
    if families == "yosuga-sweep":
        if timeframe != "5m":
            raise ValueError("yosuga-sweep family requires --timeframe 5m")
        return [
            Candidate(
                "yosuga_sweep",
                timeframe="5m",
                session_start=start,
                session_end=end,
                require_trend=False,
                entry_ema=150,
                atr_length=42,
                pullback_lookback=pullback,
                swing_buffer_atr=buffer,
                max_risk_atr=max_risk,
                trigger_break=trigger,
                ema_side_filter=ema_filter,
                cooldown_bars=12,
            )
            for (start, end), pullback, buffer, max_risk, trigger, ema_filter in product(
                ((6, 16), (6, 20)),
                (24, 48),
                (0.10, 0.20),
                (1.5, 2.5),
                (False, True),
                (False, True),
            )
        ]
    if families == "five-minute":
        if timeframe != "5m":
            raise ValueError("five-minute family requires --timeframe 5m")
        return [
            Candidate(
                "pullback_breakout", timeframe="5m",
                lookback=lookback, stop_atr=stop,
                session_start=start, session_end=end, require_trend=True,
                entry_ema=entry_ema, pullback_lookback=pullback,
                trend_fast=240, trend_slow=600,
                cooldown_bars=12, signal_interval_minutes=60,
                atr_length=168,
            )
            for lookback, stop, (start, end), entry_ema, pullback in product(
                (12, 24), (0.75, 1.25), ((0, 24), (6, 20)),
                (48, 96), (24, 48),
            )
        ]
    if families == "five-minute-reclaim":
        if timeframe != "5m":
            raise ValueError("five-minute-reclaim family requires --timeframe 5m")
        return [
            Candidate(
                "range_reclaim", timeframe="5m",
                lookback=lookback, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                trend_fast=240, trend_slow=600,
                cooldown_bars=12, signal_interval_minutes=60,
                atr_length=168,
            )
            for lookback, stop, (start, end), trend in product(
                (12, 24, 48), (0.5, 0.75, 1.0, 1.25),
                ((0, 24), (6, 20)), (False, True),
            )
        ]
    if families == "five-minute-invert":
        if timeframe != "5m":
            raise ValueError("five-minute-invert family requires --timeframe 5m")
        return [
            Candidate(
                "range_reclaim", timeframe="5m",
                lookback=lookback, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                trend_fast=240, trend_slow=600,
                cooldown_bars=12, signal_interval_minutes=60,
                atr_length=168, invert_signal=True,
            )
            for lookback, stop, (start, end), trend in product(
                (12, 24, 48), (0.5, 0.75, 1.0, 1.25),
                ((0, 24), (6, 20)), (False, True),
            )
        ]
    if families == "strength":
        return [
            Candidate(
                "currency_strength", timeframe=timeframe,
                lookback=lookback * multiplier, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                trend_fast=80 * multiplier, trend_slow=200 * multiplier,
                strength_threshold=threshold, cooldown_bars=16 * multiplier,
                invert_signal=invert,
            )
            for lookback, stop, (start, end), trend, threshold, invert in product(
                (16, 32, 64), (1.25, 2.0), ((6, 20),),
                (False, True), (3.0, 6.0, 9.0), (False, True),
            )
        ]
    if families == "continuation":
        rows = [
            Candidate(
                "compression_breakout", timeframe=timeframe,
                lookback=lookback * multiplier, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                trend_fast=80 * multiplier, trend_slow=200 * multiplier,
                atr_slow_length=slow_length * multiplier,
                compression_ratio=ratio, cooldown_bars=8 * multiplier,
            )
            for lookback, stop, (start, end), trend, slow_length, ratio in product(
                (8, 16), (0.75, 1.25), ((0, 24), (6, 20)),
                (False, True), (56,), (0.7, 0.9),
            )
        ]
        rows.extend(
            Candidate(
                "pullback_breakout", timeframe=timeframe,
                lookback=lookback * multiplier, stop_atr=stop,
                session_start=start, session_end=end, require_trend=True,
                entry_ema=entry * multiplier,
                pullback_lookback=pullback * multiplier,
                trend_fast=80 * multiplier, trend_slow=200 * multiplier,
                cooldown_bars=8 * multiplier,
            )
            for lookback, stop, (start, end), entry, pullback in product(
                (4, 8), (0.75, 1.25), ((0, 24), (6, 20)),
                (20, 40), (8,),
            )
        )
        return rows
    if families == "structure":
        rows = [
            Candidate(
                family, timeframe=timeframe, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                buffer_atr=buffer, trend_fast=80 * multiplier,
                trend_slow=200 * multiplier, one_signal_per_day=True,
            )
            for family, stop, (start, end), trend, buffer in product(
                ("daily_level_fade", "daily_level_breakout"),
                (0.75, 1.25), ((6, 16), (6, 20)), (False, True), (0.0, 0.1),
            )
        ]
        rows.extend(
            Candidate(
                family, timeframe=timeframe, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                buffer_atr=threshold, trend_fast=80 * multiplier,
                trend_slow=200 * multiplier, cooldown_bars=8 * multiplier,
            )
            for family, stop, (start, end), trend, threshold in product(
                ("impulse_continue", "impulse_fade"),
                (0.75, 1.25), ((6, 16), (6, 20)), (False, True), (1.0, 1.5),
            )
        )
        return rows
    if families == "reversion":
        rows = [
            Candidate(
                "bollinger_reversion", timeframe=timeframe, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                band_length=length, band_deviation=deviation,
                trend_fast=80 * multiplier, trend_slow=200 * multiplier,
                cooldown_bars=8 * multiplier,
            )
            for stop, (start, end), trend, length, deviation in product(
                (0.75, 1.25), ((0, 24), (6, 20)), (False, True),
                (20 * multiplier, 40 * multiplier), (1.5, 2.0),
            )
        ]
        rows.extend(
            Candidate(
                "rsi_reversion", timeframe=timeframe, stop_atr=stop,
                session_start=start, session_end=end, require_trend=trend,
                rsi_threshold=threshold, trend_fast=80 * multiplier,
                trend_slow=200 * multiplier, cooldown_bars=8 * multiplier,
            )
            for stop, (start, end), trend, threshold in product(
                (0.75, 1.25), ((0, 24), (6, 20)), (False, True), (25.0, 30.0)
            )
        )
        rows.extend(
            Candidate(
                "ema_pullback", timeframe=timeframe, stop_atr=stop,
                session_start=start, session_end=end, require_trend=True,
                entry_ema=entry * multiplier, trend_fast=80 * multiplier,
                trend_slow=200 * multiplier, cooldown_bars=8 * multiplier,
            )
            for stop, (start, end), entry in product(
                (0.75, 1.25), ((0, 24), (6, 20)), (10, 20, 40)
            )
        )
        return rows
    rows = [
        Candidate(
            "trend_breakout", timeframe=timeframe,
            lookback=lookback,
            stop_atr=stop,
            session_start=start,
            session_end=end,
            trend_fast=fast,
            trend_slow=slow,
            cooldown_bars=cooldown,
        )
        for lookback, stop, (start, end), (fast, slow), cooldown in product(
            (16, 32),
            (0.75, 1.25),
            ((0, 24), (6, 16)),
            ((80, 200), (160, 400)),
            (0, 16),
        )
    ]
    rows.extend(
        Candidate(
            family,
            stop_atr=stop,
            require_trend=trend,
            buffer_atr=buffer,
            one_signal_per_day=True,
        )
        for family, stop, trend, buffer in product(
            ("session_breakout", "session_fade"), (0.75, 1.25), (False, True), (0.0, 0.1)
        )
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--output", type=Path, default=Path("scripts/strict_rr_portfolio_results.json"))
    parser.add_argument("--timeframe", choices=("5m", "15m", "30m"), default="30m")
    parser.add_argument(
        "--symbols", nargs="+", choices=SYMBOLS, default=list(SYMBOLS),
        help="検証対象（省略時は固定11通貨）",
    )
    parser.add_argument(
        "--families",
        choices=(
            "breakout", "reversion", "structure", "continuation", "strength",
            "five-minute", "five-minute-reclaim", "five-minute-invert",
            "yosuga-five-minute",
            "yosuga-sweep",
            "yosuga-fifteen-minute",
        ),
        default="breakout",
    )
    args = parser.parse_args()
    selected_symbols = tuple(args.symbols)
    if args.families == "strength" and selected_symbols != SYMBOLS:
        parser.error("strength は固定11通貨すべてを指定してください")
    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    prepared = {}
    for symbol in selected_symbols:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, args.timeframe)

    results = []
    candidates = _candidates(args.timeframe, args.families)
    strength_cache: dict[int, dict[str, np.ndarray]] = {}
    for index, candidate in enumerate(candidates, 1):
        signal_map = None
        if candidate.family == "currency_strength":
            if candidate.lookback not in strength_cache:
                strength_cache[candidate.lookback] = _currency_strength_scores(
                    prepared, candidate.lookback
                )
            signal_map = _currency_strength_signals(
                prepared, candidate, strength_cache[candidate.lookback]
            )
        trades = [
            trade
            for symbol in selected_symbols
            for trade in _simulate(
                symbol, prepared[symbol], candidate,
                None if signal_map is None else signal_map[symbol],
            )
        ]
        periods = {name: _stats(trades, start, finish, months) for name, (start, finish, months) in PERIODS.items()}
        symbol_periods = {
            symbol: {
                name: _stats(
                    [trade for trade in trades if trade.symbol == symbol],
                    start,
                    finish,
                    months,
                )
                for name, (start, finish, months) in PERIODS.items()
            }
            for symbol in selected_symbols
        }
        prequalified = _passes(periods["train_2010_2018"]) and _passes(periods["validation_2019_2022"])
        passes_all = prequalified and all(_passes(stats) for stats in periods.values())
        results.append({
            "config": asdict(candidate),
            "prequalified": prequalified,
            "passes_all": passes_all,
            "periods": periods,
            "symbol_periods": symbol_periods,
        })
        print(f"{index}/{len(candidates)} {candidate.family} pre={prequalified} all={passes_all}", file=sys.stderr, flush=True)
    results.sort(key=lambda row: (
        row["prequalified"],
        min(float(row["periods"][name]["profit_factor"] or 0.0) for name in ("train_2010_2018", "validation_2019_2022")),
        min(float(row["periods"][name]["expectancy_r"]) for name in ("train_2010_2018", "validation_2019_2022")),
    ), reverse=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"RESULTS={len(results)} PRE={sum(row['prequalified'] for row in results)} PASS={sum(row['passes_all'] for row in results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
