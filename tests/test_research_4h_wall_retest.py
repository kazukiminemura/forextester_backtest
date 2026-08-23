from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_4h_wall_breakout import FourHourWalls  # noqa: E402
from research_4h_wall_retest import (  # noqa: E402
    Candidate,
    _candidate_grid,
    _retest_signals,
    _simulate,
)
from research_strict_rr_portfolio import Prepared  # noqa: E402


def _prepared() -> Prepared:
    open_ = np.asarray([9.5, 9.8, 10.1, 10.3, 10.05, 10.22, 10.4])
    close = np.asarray([9.6, 9.9, 10.3, 10.2, 10.2, 10.35, 10.5])
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    return Prepared(
        times=[datetime(2025, 1, 1) + timedelta(minutes=15 * i) for i in range(7)],
        years=np.asarray([2025] * 7),
        hours=np.zeros(7),
        minutes=np.asarray([0, 15, 30, 45, 0, 15, 30]),
        weekdays=np.zeros(7),
        open=open_,
        high=high,
        low=low,
        close=close,
        atr=np.ones(7),
        spread=0.01,
        atr_cache={},
        ema_cache={},
        roll_cache={},
        band_cache={},
        rsi_cache={},
        session_high=np.full(7, np.nan),
        session_low=np.full(7, np.nan),
        previous_day_high=np.full(7, np.nan),
        previous_day_low=np.full(7, np.nan),
        htf_trend=np.ones(7),
        ltf_last_high=np.full(7, np.nan),
        ltf_previous_high=np.full(7, np.nan),
        ltf_last_low=np.full(7, np.nan),
        ltf_previous_low=np.full(7, np.nan),
        ltf_last_high_age=np.zeros(7, dtype=np.int32),
        ltf_last_low_age=np.zeros(7, dtype=np.int32),
    )


def test_retest_waits_for_bullish_reclaim_after_break() -> None:
    data = _prepared()
    walls = FourHourWalls(
        trend=np.ones(7, dtype=np.int8),
        high=np.full(7, 10.0),
        low=np.full(7, 8.0),
    )
    candidate = Candidate(3, 0.0, 8, 0.10, "retest")
    signals = _retest_signals(data, walls, candidate)
    assert [(signal.index, signal.direction, signal.wall) for signal in signals] == [
        (4, 1, 10.0)
    ]


def test_candidate_grid_has_all_48_explicit_combinations() -> None:
    candidates = _candidate_grid()
    assert len(candidates) == 48
    assert {candidate.stop_mode for candidate in candidates} == {"retest", "atr"}
    assert {candidate.retest_window_bars for candidate in candidates} == {8, 16, 32}


def test_candidate_grid_multiplies_friday_cutoff_variants() -> None:
    candidates = _candidate_grid((24, 12, 15, 18))
    assert len(candidates) == 192
    assert {candidate.friday_cutoff_hour for candidate in candidates} == {
        12,
        15,
        18,
        24,
    }


def test_friday_cutoff_blocks_only_late_friday_entry() -> None:
    data = _prepared()
    data.times = [
        datetime(2025, 1, 3, 11, 0) + timedelta(minutes=15 * i)
        for i in range(7)
    ]
    data.high[-1] = 11.0
    walls = FourHourWalls(
        trend=np.ones(7, dtype=np.int8),
        high=np.full(7, 10.0),
        low=np.full(7, 8.0),
    )
    blocked = Candidate(3, 0.0, 8, 0.10, "retest", 12)
    allowed = Candidate(3, 0.0, 8, 0.10, "retest", 24)
    assert _simulate("TEST", data, walls, blocked) == []
    assert len(_simulate("TEST", data, walls, allowed)) == 1
