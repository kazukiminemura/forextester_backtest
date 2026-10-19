"""Behavior tests for timing study, not a TradingView runtime verification."""
import json

import numpy as np
import pytest

from scripts.research_bb3_context_timing import SPEC, features, simulate, timing_allowed


def fixture_bars(n=8):
    f = np.zeros((n, 15))
    f[:, :10] = [98, 101, 96, 99, 110, 125, 95, 2, 105, 90]
    f[0, 2] = 94
    times = np.arange(n, dtype=np.int64) * 300
    return f, times


def test_baseline_next_open_and_previous_confirmed_target():
    f, times = fixture_bars()
    f[2, :5] = [100, 115, 99, 114, 120]
    trades, d = simulate(f, times, 0, 2400, 1.0, 1.4)
    assert len(trades) == 1
    assert trades[0, :5].tolist() == [1, 0, 1, 2, 2]
    assert trades[0, 5:8].tolist() == [100, 110, 110]
    assert trades[0, 8] == pytest.approx(8.6)
    assert d[0] == 0


def test_pending_entry_survives_missing_bar():
    f, times = fixture_bars()
    times[2:] += 3600
    f[2, 14] = 1
    f[2, 0:3] = [112, 114, 111]
    trades, _ = simulate(f, times, 0, 10000, 1.0, 1.4)
    assert trades[0, 5] == trades[0, 6] == 112
    assert trades[0, 8] == pytest.approx(-1.4)


def test_gap_discards_preparation_but_not_flat_new_touch():
    f, times = fixture_bars()
    f[1, 14] = 1
    trades, d = simulate(f, times, 0, 2400, 1.0, 1.4)
    assert len(trades) == 0 and d[7] == 0
    f[1, 2] = 94
    _, d = simulate(f, times, 0, 2400, 1.0, 1.4)
    assert d[7] == 1


def test_long_wick_and_impulse_cancel_preparation():
    for column in (10, 12):
        f, times = fixture_bars()
        f[1, column] = 1
        trades, d = simulate(f, times, 0, 2400, 1.0, 1.4)
        assert len(trades) == 0 and d[7] == 0


def test_no_forced_close_enters_pf_and_open_cost_once():
    f, times = fixture_bars()
    trades, d = simulate(f, times, 0, 2400, 1.0, 1.4)
    assert len(trades) == 0
    assert d[2] == 1
    assert d[0] == pytest.approx(99 - 98 - 1.4)


def test_short_is_symmetric_and_exit_bar_cannot_rearm():
    f, times = fixture_bars()
    f[2, :5] = [100, 115, 99, 114, 120]
    # Mirror every price around 200; swap high/low, upper/lower and prior extrema.
    g = f.copy()
    for a, b in ((0, 0), (1, 2), (2, 1), (3, 3), (4, 4), (5, 6), (6, 5), (8, 9), (9, 8)):
        g[:, a] = 400 - f[:, b]
    g[2, 1] = g[2, 5] + 1  # same exit candle also touches upper band
    trades, d = simulate(g, times, 0, 2400, 1.0, 1.4)
    assert len(trades) == 1 and trades[0, 0] == -1
    assert trades[0, 8] == pytest.approx(8.6)
    assert d[6] == 1


def test_preparation_expiry_is_after_inclusive_last_bar():
    f, times = fixture_bars()
    f[1:4, 3] = 99  # mode1 waits because close equals previous close
    f[4, 3] = 100
    _, d3 = simulate(f, times, 0, 2400, 1.0, 1.4, mode=1, expiry=3)
    _, d6 = simulate(f, times, 0, 2400, 1.0, 1.4, mode=1, expiry=6)
    assert d3[7] == 0 and d6[7] == 1


def test_reversal_and_previous_extreme_are_strict():
    f, _ = fixture_bars()
    f[1, 3] = 99
    assert not timing_allowed(f, 1, 0, 1, 1, 0, 1.4, 1)
    f[1, 3] = 100
    assert timing_allowed(f, 1, 0, 1, 1, 0, 1.4, 1)
    assert not timing_allowed(f, 1, 0, 1, 2, 0, 1.4, 1)
    f[1, 3] = 101
    assert not timing_allowed(f, 1, 0, 1, 2, 0, 1.4, 1)
    f[1, 3] = 102
    assert timing_allowed(f, 1, 0, 1, 2, 0, 1.4, 1)


def test_distance_is_based_on_signal_not_future_open():
    f, _ = fixture_bars()
    f[1, 3] = 106
    assert timing_allowed(f, 1, 0, 1, 0, 2, 1.4, 1)
    assert not timing_allowed(f, 1, 0, 1, 0, 3, 1.4, 1)


def test_atr_wilder_seed_and_features_prefix_invariance():
    rng = np.random.default_rng(771)
    close = 150 + np.cumsum(rng.normal(0, .02, 100))
    op = np.r_[close[0], close[:-1]]
    ohlc = np.column_stack([op, np.maximum(op, close) + .01, np.minimum(op, close) - .01, close])
    times = np.arange(len(close), dtype=np.int64) * 300
    f = features(ohlc, times, .01, .001)
    np.testing.assert_allclose(f[:70], features(ohlc[:70], times[:70], .01, .001), equal_nan=True)
    tr = ohlc[:, 1] - ohlc[:, 2]
    assert np.isnan(f[13, 7])
    assert f[14, 7] == pytest.approx(tr[:14].mean())
    assert f[15, 7] == pytest.approx((tr[:14].mean() * 13 + tr[14]) / 14)


def test_protocol_finite_scope_and_no_stop_default():
    p = json.loads(SPEC.read_text(encoding="utf-8"))
    assert len(p["search_space"]) == p["candidate_budget"] == 12
    assert len(p["symbols"]) == 9
    assert p["exit_rules"]["stop"] == "disabled as existing default"
    assert "training only" in p["selection"]
    assert "NOT untouched" in p["final_period_prior_exposure"]
