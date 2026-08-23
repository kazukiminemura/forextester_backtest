from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_4h_wall_breakout import (  # noqa: E402
    Candidate,
    FourHourWalls,
    _break_signals,
    _stats,
)
from research_strict_rr_portfolio import Prepared  # noqa: E402


def _prepared() -> Prepared:
    close = np.asarray([9.5, 9.8, 10.2, 10.4])
    return Prepared(
        times=[datetime(2025, 1, 1) + timedelta(minutes=15 * i) for i in range(4)],
        years=np.asarray([2025] * 4),
        hours=np.zeros(4),
        minutes=np.asarray([0, 15, 30, 45]),
        weekdays=np.zeros(4),
        open=close.copy(),
        high=close + 0.1,
        low=close - 0.1,
        close=close,
        atr=np.ones(4),
        spread=0.01,
        atr_cache={},
        ema_cache={},
        roll_cache={},
        band_cache={},
        rsi_cache={},
        session_high=np.full(4, np.nan),
        session_low=np.full(4, np.nan),
        previous_day_high=np.full(4, np.nan),
        previous_day_low=np.full(4, np.nan),
        htf_trend=np.ones(4),
        ltf_last_high=np.full(4, np.nan),
        ltf_previous_high=np.full(4, np.nan),
        ltf_last_low=np.full(4, np.nan),
        ltf_previous_low=np.full(4, np.nan),
        ltf_last_high_age=np.zeros(4, dtype=np.int32),
        ltf_last_low_age=np.zeros(4, dtype=np.int32),
    )


def test_break_signal_requires_close_cross_in_trend_direction() -> None:
    data = _prepared()
    walls = FourHourWalls(
        trend=np.ones(4, dtype=np.int8),
        high=np.full(4, 10.0),
        low=np.full(4, 8.0),
    )
    indices, directions = _break_signals(data, walls, 0.0)
    assert indices.tolist() == [2]
    assert directions.tolist() == [1]


def test_candidate_grid_values_and_rr_stats_are_explicit() -> None:
    candidate = Candidate(pivot_bars=5, break_buffer_atr=0.05, stop_atr=1.5)
    assert candidate.pivot_bars == 5
    empty = _stats([], 12)
    assert empty["trades"] == 0
    assert empty["profit_factor"] is None
    assert empty["expectancy_r"] == 0.0
