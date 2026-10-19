from datetime import datetime, timedelta

import pytest

from forextester_backtest.models import Bar
from forextester_backtest.sniper_defense import defensive_outcome


def bar(i, op=100, hi=100.2, lo=99.8):
    return Bar(datetime(2020, 1, 1, 8)+timedelta(hours=i), op, hi, lo, op, 1)


def test_tp1_breakeven_waits_for_next_bar_and_charges_cost():
    assert defensive_outcome([bar(0, hi=101.2, lo=99), bar(1, hi=103.2, lo=100.1)], 0, 1, 1, 0, 'breakeven_tp1')[1] == 2
    r = defensive_outcome([bar(0, hi=101.5), bar(1, op=100.11)], 0, 1, 1, .1, 'breakeven_tp1')
    assert r[1] == pytest.approx(-.01/1.5)


def test_half_tp1_is_one_third_r_and_remainder_can_lose():
    result = defensive_outcome([bar(0, hi=101.1), bar(1, lo=98)], 0, 1, 1, 0, 'half_tp1')
    assert result[1] == pytest.approx(1/3-.5)
    result = defensive_outcome([bar(0, hi=104)], 0, 1, 1, 0, 'half_tp1')
    assert result[1] == pytest.approx(1/3+1)


@pytest.mark.parametrize('side', [-1, 1])
def test_stop_first_before_any_partial_tp(side):
    r = defensive_outcome([bar(0, hi=104, lo=96)], 0, side, 1, 0, 'half_tp1_breakeven')
    assert r[1:3] == (-1, 'stop')


def test_four_hour_deadline_uses_open_not_future_extremes():
    r = defensive_outcome([bar(0), bar(4, op=100.5, hi=104, lo=96)], 0, 1, 1, 0, 'half_tp1_breakeven')
    assert r[1:3] == (1/3, 'time')
