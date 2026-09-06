from datetime import datetime,timedelta

import pytest

from forextester_backtest.gold_limit import limit_trade
from forextester_backtest.models import Bar

BASE = datetime(2020,1,1,8)


def bar(minutes,op=100,hi=100.2,lo=99.8):
    return Bar(BASE+timedelta(minutes=minutes),op,hi,lo,op,1)


def trade(bars,side=1,anchored=False):
    return limit_trade(bars,[b.time for b in bars],BASE,side,1,100,0,.25,1,anchored)


def test_target_before_possible_fill_is_not_credited():
    result = trade([bar(0,hi=104,lo=99.5),bar(1),bar(720)])
    assert result["reason"] == "time"
    assert result["r"] == pytest.approx(.25/1.5)


def test_stop_after_limit_crossing_can_execute_in_fill_minute():
    result = trade([bar(0,lo=97)])
    assert result["reason"] == "stop"
    assert result["r"] == -1


def test_expiry_is_exclusive_and_no_fill_is_not_a_win():
    result = trade([bar(0,lo=99.9),bar(60,lo=99.5)])
    assert result["filled"] is False


def test_short_fill_and_target_are_symmetric():
    result = trade([bar(0,hi=100.5),bar(1,op=98,hi=98.1,lo=97)],side=-1)
    assert result["filled"]
    assert result["entry"] == 100.25
    assert result["reason"] == "target"
    assert result["r"] == 2


def test_reference_anchored_target_has_honest_fixed_atr_risk_unit():
    result = trade([bar(0,lo=99.5),bar(1,op=101,hi=103.1,lo=100.8)],anchored=True)
    assert result["r"] == pytest.approx(3.25/1.5)
