"""Synthetic boundary checks; these never inspect historical profitability."""
import numpy as np
import pytest

from scripts.research_bb3_jev_engine import candidates, round_tick, simulate


def fixture(n=9, side=1):
    f = np.zeros((n, 15))
    f[:, :10] = [100, 100.02, 99.98, 100, 100.20, 101, 99.9, .1, 102, 98]
    f[0, :4] = [100, 100.01, 99.8, 99.85]  # touch
    f[1, :4] = [99.9, 100.05, 99.85, 100]  # directional recovery
    f[2, :4] = [100, 100.06, 99.9, 99.95]  # wick break, closes below threshold
    if side == -1:
        f[:, :4] = np.column_stack((200-f[:, 0], 200-f[:, 2], 200-f[:, 1], 200-f[:, 3]))
        f[:, 4:7] = np.column_stack((200-f[:, 4], 200-f[:, 6], 200-f[:, 5]))
        f[:, 8:10] = np.column_stack((200-f[:, 9], 200-f[:, 8]))
    return f, np.arange(n, dtype=np.int64)*300


def run(f, times, signals=None, **kwargs):
    if signals is None:
        signals = candidates(f, times, .01, .001)
    return simulate(f, times, .01, .001, signals, start=0, end=100000, **kwargs)


@pytest.mark.parametrize("side", [1, -1])
def test_three_separate_stages_original_wick_entry(side):
    f, times = fixture(side=side)
    result = candidates(f, times, .01, .001)
    assert len(result) == 1
    assert [result[0][k] for k in ("prep_index", "confirmed_index", "index", "side")] == [0, 1, 2, side]
    assert result[0]["target"] == pytest.approx(100.2 if side == 1 else 99.8)
    assert result[0]["reference"] == pytest.approx(100.051 if side == 1 else 99.949)


@pytest.mark.parametrize("column,value", [(2, 99.79), (10, 1), (12, 1), (1, 101)])
def test_cancel_has_priority_and_cannot_rearm(column, value):
    f, times = fixture()
    f[2, column] = value
    assert candidates(f, times, .01, .001) == []


def test_gap_cancels_even_if_gap_feature_stale():
    f, times = fixture()
    times[2:] += 300
    assert candidates(f, times, .01, .001) == []


def test_invalidating_extreme_before_confirmation_cancels():
    f, times = fixture()
    f[1, 2] = 99.79
    assert candidates(f, times, .01, .001) == []


def test_strict_break_expiry_and_failed_room_consumption():
    f, times = fixture()
    f[2, 1] = f[1, 1]
    assert candidates(f, times, .01, .001) == []
    f[3, 1] = 100.06
    assert candidates(f, times, .01, .001, expiry=2) == []
    assert candidates(f, times, .01, .001, expiry=3)[0]["index"] == 3
    f[2, 1] = 100.06
    f[1, 4] = 100.07  # prior-center room too small; no later retry
    assert candidates(f, times, .01, .001) == []


def test_current_target_distinct_from_prior_candidate_center():
    f, times = fixture()
    f[2, 4] = 100.3005
    assert candidates(f, times, .01, .001)[0]["target"] == pytest.approx(100.301)
    assert round_tick(100.1235, .001) == pytest.approx(100.124)


@pytest.mark.parametrize("side", [1, -1])
def test_rr1_stop_first_costs_and_zero_win(side):
    f, times = fixture(side=side)
    f[3, 1:3] = [100.3, 99.7]
    result = run(f, times)
    t = result["trades"][0]
    assert t["entry_index"] == t["exit_index"] == 3
    assert t["exit_reason"] == "stop"
    assert t["net_pips"] == pytest.approx(-21)
    assert t["net_r"] == pytest.approx(-1.05)
    assert result["summary"]["wins"] == 0


@pytest.mark.parametrize("rr", [1., 1.3, 1.5])
def test_tick_rounding_conservative_risk_rr(rr):
    f, times = fixture()
    f[3, 1] = 100.21
    t = run(f, times, rr=rr)["trades"][0]
    assert t["target"] == pytest.approx(100.2)
    assert t["risk_pips"] + 1e-8 >= 20 / rr
    assert t["effective_rr"] <= rr + 1e-8
    assert t["net_pips"] == pytest.approx(19)


def test_delayed_execution_uses_original_target_and_next_next_open():
    f, times = fixture()
    f[3, 4] = 100.7
    f[4, 0] = 100.10
    f[4, 1] = 100.21
    t = run(f, times, entry_delay=2)["trades"][0]
    assert t["entry_index"] == 4
    assert t["target"] == pytest.approx(100.2)
    assert t["entry"] == pytest.approx(100.1)


@pytest.mark.parametrize("side", [1, -1])
def test_rr1_stop_uses_exact_unrounded_pine_formula(side):
    f, times = fixture(side=side)
    entry = 100.00037 if side == 1 else 99.99963
    f[3, 0] = entry
    f[3, 1:3] = [100.3, 99.7]
    t = run(f, times, rr=1.)["trades"][0]
    assert t["stop"] == 2 * entry - t["target"]
    assert abs(t["stop"] / .001 - round(t["stop"] / .001)) > .01
    assert t["exit"] == t["stop"]


def test_r_profit_factor_uses_r_not_pips():
    f, times = fixture()
    signals = candidates(f, times, .01, .001)
    signals.append(dict(signals[0], index=4, target=100.1))
    f[3, 1] = 100.3  # First wins 19 pips / 20-pip risk.
    f[5, 2] = 99.8  # Second loses 11 pips / 10-pip risk.
    summary = run(f, times, signals)["summary"]
    assert summary["gross_profit_r"] == pytest.approx(.95)
    assert summary["gross_loss_r"] == pytest.approx(1.1)
    assert summary["profit_factor_r"] == pytest.approx(.95/1.1)
    assert summary["profit_factor"] == pytest.approx(19/11)


@pytest.mark.parametrize("delay", [1, 2])
def test_entry_gap_and_room_rejected(delay):
    f, times = fixture()
    signals = candidates(f, times, .01, .001)
    times[3:] += 300
    result = run(f, times, signals, entry_delay=delay)
    assert result["summary"]["rejected_entry_gap"] == 1
    f, times = fixture()
    f[2+delay, 0] = 100.19
    result = run(f, times, signals, entry_delay=delay)
    assert result["summary"]["rejected_entry_room"] == 1


def test_open_gap_stop_not_stop_price_and_one_position():
    f, times = fixture()
    signals = candidates(f, times, .01, .001)
    signals.append(dict(signals[0], index=3))  # ignored while position remains open
    f[4, :4] = [99.6, 99.65, 99.5, 99.6]
    result = run(f, times, signals)
    assert len(result["trades"]) == 1
    assert result["trades"][0]["exit"] == 99.6
    assert result["trades"][0]["exit_reason"] == "gap_stop"
    assert result["summary"]["occupied_candidates"] == 1


def test_allowed_false_missing_and_true_and_open_not_a_win():
    f, times = fixture()
    for gate in (set(), {}, {2: False}):
        assert run(f, times, allowed=gate)["summary"]["accepted_candidates"] == 0
    a = run(f, times, allowed={2})
    b = run(f, times, allowed={2: True})
    assert a["summary"] == b["summary"]
    assert a["summary"]["trades"] == 0
    assert a["summary"]["open_side"] == 1
    assert a["summary"]["open_net_pips"] == pytest.approx(-1)
    assert a["summary"]["bar_close_mtm_drawdown_r"] == pytest.approx(.05)


def test_empty_interval_and_prefix_invariance():
    f, times = fixture()
    full_candidates = candidates(f, times, .01, .001)
    full = run(f, times, full_candidates)
    for n in range(1, len(f)+1):
        prefix = candidates(f[:n], times[:n], .01, .001)
        assert prefix == [s for s in full_candidates if s["index"] < n]
        result = run(f[:n], times[:n], prefix)
        np.testing.assert_array_equal(result["mtm"], full["mtm"][:n])
    empty = simulate(f, times, .01, .001, full_candidates, start=99999, end=100000)
    assert empty["summary"]["trades"] == 0
    assert empty["mtm"].shape == (0, 2)


def test_invalid_inputs_fail_closed():
    f, times = fixture()
    with pytest.raises(ValueError):
        run(f, times, rr=2)
    with pytest.raises(ValueError):
        run(f, times, cost_pips=-1)
    times[3] = times[2]
    with pytest.raises(ValueError):
        candidates(f, times, .01, .001)
