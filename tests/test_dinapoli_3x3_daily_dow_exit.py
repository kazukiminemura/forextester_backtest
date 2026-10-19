"""Behavioral tests for causal Dow pivots, arming, next-open exits and selection."""
import json

import numpy as np
import pytest

from scripts import research_dinapoli_3x3_daily_dow_exit as r


def pivot_fixture():
    ohlc = np.tile([4., 5., 3., 4.], (26, 1))
    ohlc[[3, 9, 15], 1] = [10, 12, 11]
    ohlc[[6, 12, 18], 2] = [1, 2, 0]
    return ohlc


@pytest.mark.parametrize("length", [2, 3])
def test_pivots_confirm_after_right_bars_and_mixed_relation_keeps_state(length):
    states, events = r.dow_states(pivot_fixture(), length)
    assert not states[:12+length].any()
    assert states[12+length] == 1
    assert states[15+length] == 1  # lower high alone is not a completed down trend
    assert states[18+length] == -1
    np.testing.assert_array_equal(events[:, 0] - events[:, 1], length)
    assert events[:, 1].tolist() == [3, 6, 9, 12, 15, 18]


def test_strict_pivot_rejects_equal_neighbor():
    ohlc = pivot_fixture()
    ohlc[4, 1] = 10
    states, events = r.dow_states(ohlc, 2)
    assert 3 not in events[events[:, 2] == 1, 1]
    assert 4 not in events[events[:, 2] == 1, 1]
    assert not states[:17].any()


@pytest.mark.parametrize("length", [2, 3])
def test_future_prefix_and_price_mirror_preserve_causality_and_symmetry(length):
    data = pivot_fixture()
    states, events = r.dow_states(data, length)
    for end in range(1, len(data)+1):
        prefix, pevents = r.dow_states(data[:end], length)
        np.testing.assert_array_equal(prefix, states[:end])
        np.testing.assert_array_equal(pevents, events[events[:, 0] < end])
    mirror = np.column_stack((20-data[:, 0], 20-data[:, 2], 20-data[:, 1], 20-data[:, 3]))
    np.testing.assert_array_equal(r.dow_states(mirror, length)[0], -states)


def test_simultaneous_high_low_pivots_update_atomically():
    data = np.tile([5., 6., 4., 5.], (15, 1))
    data[[3, 9], 1] = [10, 11]
    data[[3, 9], 2] = [1, 2]
    states, events = r.dow_states(data, 2)
    assert events[:, 0].tolist() == [5, 5, 11, 11]
    assert states[10] == 0 and states[11] == 1


@pytest.mark.parametrize("direction,stop,bar,pending,expected", [
    (1, 9, [8, 20, 7, 10], True, (8., "stop_gap")),
    (-1, 11, [12, 13, 1, 10], True, (12., "stop_gap")),
    (1, 9, [11, 20, 8, 10], True, (11., "dow_next_open")),
    (-1, 11, [9, 12, 1, 10], True, (9., "dow_next_open")),
    (1, 9, [10, 20, 9, 15], False, (9., "stop")),
    (1, 9, [10, 100, 9.5, 15], False, None),
])
def test_open_events_precede_intraday_range_and_no_tp(direction, stop, bar, pending, expected):
    assert r.dow_exit_fill(direction, stop, bar, pending) == expected


def fixture(monkeypatch, states, signals=None, source=None, stop=8):
    n = len(states)
    source = np.tile([10., 11., 9., 10.], (n, 1)) if source is None else np.asarray(source, dtype=float)
    signals = [1] + [0] * (n-1) if signals is None else signals
    dates = r.base.timestamp("2024-01-01") + np.arange(n) * r.base.DAY
    data = r.base.DailyData(dates, source, dates, dates+r.base.DAY-60, np.full(n, 1440))
    monkeypatch.setattr(r.base, "generate_signals", lambda *args: (np.asarray(signals), np.full(n, stop), np.zeros(n, dtype=int)))
    monkeypatch.setattr(r, "dow_states", lambda *args: (np.asarray(states), np.empty((0, 4))))
    return data


def run(data, end=None, direction=1):
    candidate = {"id": "test", "kind": "double_repo", "thrust": 8, "expiry": 8, "exit": "dow", "pivot": 2}
    return r.simulate(data, candidate, data.dates[0], end if end is not None else data.dates[-1]+r.base.DAY, 1, .1)


def test_preexisting_opposite_state_does_not_trigger_exit(monkeypatch):
    data = fixture(monkeypatch, [-1, -1, -1, -1])
    trades, diagnostics, _ = run(data)
    assert trades == [] and diagnostics["open_count"] == 1
    assert not diagnostics["open_position"]["dow_armed"]


def test_arming_then_reversal_exits_next_open_not_pivot_or_signal_close(monkeypatch):
    data = fixture(monkeypatch, [-1, -1, 1, 1, -1, -1])
    data.ohlc[5] = [12, 20, 7, 13]  # later low hits SL but open exit already occurred
    trades, diagnostics, _ = run(data)
    assert len(trades) == 1 and not diagnostics["open_count"]
    trade = trades[0]
    assert trade["entry_index"] == 1 and trade["dow_armed_index"] == 2
    assert trade["dow_signal_index"] == 4 and trade["exit_index"] == 5
    assert trade["exit_price"] == 12 and trade["reason"] == "dow_next_open"
    assert trade["net_r"] == pytest.approx(.95)
    assert trade["dow_signal_available_timestamp"] <= trade["exit_raw_first_timestamp"]


def test_entry_day_can_arm_and_short_is_symmetric(monkeypatch):
    data = fixture(monkeypatch, [1, -1, 1, 1], signals=[-1, 0, 0, 0], stop=12)
    data.ohlc[3] = [8, 13, 7, 8]
    trades, _, _ = run(data)
    assert trades[0]["dow_armed_index"] == 1
    assert trades[0]["dow_signal_index"] == 2 and trades[0]["exit_index"] == 3
    assert trades[0]["net_r"] == pytest.approx(.95)


def test_initial_sl_precedes_close_reversal_and_exit_day_signal_ignored(monkeypatch):
    data = fixture(monkeypatch, [1, 1, -1, -1], signals=[1, 0, 1, 0])
    data.ohlc[2] = [10, 11, 7, 9]
    trades, diagnostics, _ = run(data)
    assert len(trades) == 1 and trades[0]["reason"] == "stop"
    assert trades[0]["exit_index"] == 2 and diagnostics["ignored_signals"] == 1
    assert diagnostics["pending_dow_exit_at_end"] == 0


def test_pending_reversal_at_boundary_stays_open(monkeypatch):
    data = fixture(monkeypatch, [1, 1, -1, -1])
    trades, diagnostics, equity = run(data, data.dates[3])
    assert trades == [] and diagnostics["open_count"] == 1
    assert diagnostics["pending_dow_exit_at_end"] == 1
    assert diagnostics["open_net_r"] == pytest.approx(-.05)
    assert r.base.summarize(trades, diagnostics, equity)["boundary_force_close_sensitivity"]["trades"] == 1


def test_gap_beyond_initial_sl_cancels_entry(monkeypatch):
    data = fixture(monkeypatch, [1, 1, -1])
    data.ohlc[1] = [7, 9, 6, 8]
    trades, diagnostics, _ = run(data)
    assert trades == [] and diagnostics["cancelled_at_open"] == 1 and not diagnostics["open_count"]


def test_selection_uses_worst_cost_pf_then_average_then_dd_then_id():
    totals, decisions = {}, {}
    for cid, pf, avg, dd in (("a", 1.2, .1, 10), ("b", 1.3, .1, 10), ("c", 1.3, .2, 10), ("d", 1.3, .2, 9), ("e", 1.3, .2, 9), ("f", 2, 1, 1)):
        totals[cid] = {"training": {case: {"pf": pf, "average_net_r": avg, "closed_drawdown_r": dd} for case in ("one", "two")}}
        decisions[cid] = {"training": {case: {"passed": cid != "f"} for case in ("one", "two")}}
    assert r.select_training(totals, decisions) == "d"
    totals["d"]["training"]["two"]["pf"] = 1.25
    assert r.select_training(totals, decisions) == "e"
    assert r.select_training(totals, {}) is None


def test_protocol_no_null_finite_candidates_and_user_exit_override():
    protocol = json.loads(r.SPEC.read_text(encoding="utf-8"))
    r.no_nulls(protocol)
    assert len(protocol["search_space"]) == 6
    assert sum(c["eligible"] for c in protocol["search_space"]) == 4
    assert protocol["exit_rules"]["full_exit"]
    assert protocol["acceptance_gates"]["training"]["minimum_profitable_symbols"] == 10
    with pytest.raises(ValueError, match="null"):
        r.no_nulls({"missing": None})
