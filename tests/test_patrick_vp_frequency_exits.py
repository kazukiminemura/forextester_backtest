"""Exercise Patrick partial-limit and fixed-time decisions at M1 boundaries."""

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backtest_patrick_vp_frequency_exits as study


def make_trade(entered, closed, reason, side=1, quote=6.0):
    entry, stop, target = 10.0, 10.0 - 4.0 * side, 10.0 + 4.0 * side
    row = np.zeros(17)
    row[:7] = entered, closed, side, entry, stop, target, quote
    row[15:17] = reason, 5.0
    return row


@pytest.mark.parametrize(
    "reason, second_bar, closed_offset, expected",
    [
        (5, [11.0, 14.0, 6.0, 12.0], 120, 0),
        (5, [12.0, 14.0, 6.0, 12.0], 120, 60),
        (6, [11.0, 14.0, 9.0, 12.0], 120, 120),
        (3, [15.0, 16.0, 14.0, 15.0], 60, 60),
        (1, [15.0, 16.0, 14.0, 15.0], 60, 0),
    ],
)
def test_halfway_respects_open_and_intraminute_order(reason, second_bar, closed_offset, expected):
    entered = study.base.stamp("2024-01-07T23:15")
    times = np.array([entered, entered + 60])
    prices = np.array([[10.0, 11.0, 9.0, 10.0], second_bar])
    trade = make_trade(entered, entered + closed_offset, reason)
    at, price = study.halfway_exit(times, prices, trade, .01)
    assert at == (entered + expected if expected else 0)
    if expected:
        assert price == 12.0
    else:
        assert np.isnan(price)


def test_short_halfway_checks_ask_and_honors_entry_minute_stop():
    entered = study.base.stamp("2024-01-07T23:15")
    times = np.arange(entered, entered + 180, 60)
    trade = make_trade(entered, entered + 120, 4, side=-1, quote=14)
    prices = np.array([[10.0, 11.0, 7.9, 9.0], [9.0, 14.0, 7.0, 8.0], [7.0, 7.0, 7.0, 7.0]])
    assert study.halfway_exit(times, prices, trade, .2)[0] == 0
    prices[0, 2] = 7.8
    assert study.halfway_exit(times, prices, trade, .2) == (entered + 60, 8.0)


def test_time_exit_uses_real_same_day_open_and_original_close_priority():
    entered = study.base.stamp("2024-01-07T23:15")
    exact_jst17 = study.base.stamp("2024-01-08T08:00")
    next_local_day = study.base.stamp("2024-01-08T15:03")
    times = np.array([entered, exact_jst17 + 180, next_local_day])
    prices = np.array([[10.0, 11.0, 9.0, 10.0], [9.0, 11.0, 7.0, 10.0], [15.0, 16.0, 14.0, 15.0]])
    trade = make_trade(entered, next_local_day, 4, side=-1, quote=14)
    assert study.session_exit(times, prices, trade, .2) == (exact_jst17 + 180, 9.2)
    trade[1], trade[15] = exact_jst17 + 180, 2
    assert study.session_exit(times, prices, trade, .2)[0] == 0
    trade[1] = next_local_day + 60
    assert study.session_exit(times[[0, 2]], prices[[0, 2]], trade, .2)[0] == 0


def test_conditional_partial_only_checks_first_bar_and_accounts_for_costs():
    entered = study.base.stamp("2024-01-07T23:15")
    exact_jst17 = study.base.stamp("2024-01-08T08:00")
    times = np.array([entered, exact_jst17, exact_jst17 + 60])
    trade = make_trade(entered, exact_jst17 + 120, 4)
    prices = np.array([[10.0, 10.1, 9.0, 10.0], [10.02, 10.2, 10.0, 10.1], [9.1, 9.2, 9.0, 9.0]])
    result = study.partial_exits(times, prices, np.array([trade]), .1, False)
    assert result[3, 0, 0] == exact_jst17
    assert result[3, 0, 2] < 0
    prices[1, 0] = 10.04
    result = study.partial_exits(times, prices, np.array([trade]), .1, False)
    assert result[2, 0, 0] == exact_jst17
    assert result[3, 0, 0] == 0


def test_blends_both_legs_at_entry_risk_and_groups_same_time_drawdown():
    original = make_trade(60, 180, 4).reshape(1, 17)
    original[0, 7:13] = [-.8, -4.0, -4.0, 100.0, -.8, 99.2]
    events = np.array([[180, 12.0, .4]])
    np.testing.assert_array_equal(study.combine_legs(original, events, 1.0, fraction=0), original)
    combined = study.combine_legs(original, events, 1.0)
    assert combined[0, 7] == pytest.approx(-.2)
    assert combined[0, 11] == pytest.approx(-.2)
    assert combined[0, 12] == pytest.approx(99.8)
    realized = study.realized_events(combined, events, original)
    assert study.event_drawdown(realized) == pytest.approx(.2)
