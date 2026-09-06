from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

from forextester_backtest.models import Bar

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("daytrade", SCRIPTS / "research_sniper_daytrade.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
BASE = datetime(2020, 1, 1, 8)


def bar(i, op=100, hi=100.2, lo=99.8, close=100):
    return Bar(BASE + timedelta(minutes=15 * i), op, hi, lo, close, 1)


def test_long_and_short_stop_first_and_spread():
    for side in (1, -1):
        result = study.outcome([bar(0, hi=105, lo=95)], 0, side, 1, 0.1, 15)
        assert result[2] == "stop"
        assert result[1] == pytest.approx(-1 - 0.01 / 1.5)


def test_time_exit_charges_spread_and_two_market_slippages():
    result = study.outcome([bar(0), bar(16)], 0, 1, 1, 0.1, 15)
    assert result[2] == "time"
    assert result[1] == pytest.approx(-0.12 / 1.5)
    assert result[3] == 0


def test_gap_stop_uses_worse_open():
    result = study.outcome([bar(0), bar(1, op=95, hi=95.2, lo=94.8)], 0, 1, 1, 0, 15)
    assert result[1] == pytest.approx(-5 / 1.5)


def test_deadline_gap_respects_resting_target():
    result = study.outcome([bar(0), bar(16, op=104, hi=104.2, lo=103.8)], 0, 1, 1, 0, 15)
    assert result[1:3] == (2, "target")


def test_deadline_gap_respects_resting_stop():
    result = study.outcome([bar(0), bar(16, op=95, hi=95.2, lo=94.8)], 0, 1, 1, 0, 15)
    assert result[1] == pytest.approx(-5 / 1.5)
    assert result[2] == "stop"


def test_exit_target_parameter_preserves_risk_unit():
    result = study.outcome([bar(0, hi=101)], 0, 1, 1, 0, 15, target_atr=.75)
    assert result[1:3] == (.5, "target")


def test_one_hour_and_end_of_day_deadlines():
    bars = [bar(0), bar(4), bar(16), bar(48)]
    short = study.outcome(bars, 0, 1, 1, 0, 15, hold_hours=1)
    day = study.outcome(bars, 0, 1, 1, 0, 15, hold_hours=None)
    assert short[0] == 1
    assert day[0] == 3
    assert short[2] == day[2] == "time"


def test_late_exit_retained_and_marked():
    result = study.outcome([bar(0), bar(100)], 0, 1, 1, 0, 15)
    assert result[3] == 1


def test_unfinished_trade_not_a_loss():
    assert study.outcome([bar(0)], 0, 1, 1, 0, 15) is None


def test_filter_replays_admission_instead_of_filtering_existing_trades():
    rows = np.array([[1, 20, 2020, -1, 19, 55, 1, 8, 0, 0, .1, 0],
                     [6, 10, 2020, 2, 30, 55, 1, 8, 0, 1, .1, 0],
                     [10, 15, 2020, 2, 30, 55, 1, 8, 0, 1, .1, 0]], dtype=float)
    selected = study.selected(rows, (25, 100, 100, (6, 16)))
    assert selected[:, 0].tolist() == [6]
