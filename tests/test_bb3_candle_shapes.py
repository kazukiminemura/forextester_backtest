"""Frozen candle decisions, occupancy, execution and selection boundaries."""
import json

import numpy as np
import pytest

from scripts.research_bb3_candle_shapes import SPEC, gates, shape_allowed, simulate_shapes
from scripts.research_bb3_context_center5 import simulate_center
from scripts.research_bb3_context_timing import features


def fixture():
    f = np.zeros((8, 15))
    f[:, :10] = [98, 103, 96, 99, 110, 125, 95, 2, 105, 90]
    f[0, :4] = [99, 100, 94, 98]
    f[1, :4] = [97, 100, 96, 99]
    f[2, :4] = [100, 115, 99, 114]
    return f, np.arange(8, dtype=np.int64) * 300


def mirror(f):
    g = f.copy()
    for a, b in ((0, 0), (1, 2), (2, 1), (3, 3), (4, 4), (5, 6), (6, 5), (8, 9), (9, 8)):
        g[:, a] = 400 - f[:, b]
    g[:, [10, 11, 12, 13]] = f[:, [11, 10, 13, 12]]
    return g


@pytest.mark.parametrize('mode', [1, 2, 3, 4])
def test_doji_zero_range_wrong_body_rejected(mode):
    f, _ = fixture()
    for candle in ([99, 100, 98, 99], [99, 99, 99, 99], [100, 101, 96, 99]):
        f[1, :4] = candle
        assert not shape_allowed(f, 1, 1, mode)
        assert not shape_allowed(mirror(f), 1, -1, mode)


@pytest.mark.parametrize('mode, candle, expected', [
    (1, [10, 20, 0, 13], True), (1, [10, 20, 0, 12.99], False),
    (2, [3, 20, 0, 13], True), (2, [3.01, 20, 0, 13], False),
    (3, [98, 100, 96, 99], True), (3, [98.01, 100, 96, 99], False),
    (4, [98, 101, 96, 100], False), (4, [98, 101, 96, 100.01], True),
])
def test_shape_thresholds_and_short_symmetry(mode, candle, expected):
    f, _ = fixture()
    f[1, :4] = candle
    assert shape_allowed(f, 1, 1, mode) == expected
    assert shape_allowed(mirror(f), 1, -1, mode) == expected


def test_engulf_requires_opposite_previous_body():
    f, _ = fixture()
    f[0, :4] = [98, 100, 94, 99]
    assert not shape_allowed(f, 1, 1, 3)
    f[0, 3] = f[0, 0]
    assert not shape_allowed(f, 1, 1, 3)


def test_failure_cancels_and_cannot_rearm_same_bar_or_wait():
    f, t = fixture()
    f[1, :4] = [100, 103, 94, 99]  # fail body, same-side repeated touch
    trades, d = simulate_shapes(f, t, 0, 2400, 1., 1.4, 1)
    assert len(trades) == 0 and d[6] == 1 and d[7] == 0 and d[11] == 1


def test_fresh_setup_after_rejection_changes_occupancy_not_postfilter():
    f, t = fixture()
    f[1, :4] = [100, 103, 94, 99]
    f[2, :4] = [98, 100, 94, 98]
    f[3, :4] = [97, 100, 96, 99]
    f[4, :4] = [100, 115, 99, 114]
    trades, d = simulate_shapes(f, t, 0, 2400, 1., 1.4, 1)
    baseline, _ = simulate_center(f, t, 0, 2400, 1., 1.4, 3.)
    assert d[6] == 2 and d[11] == 1
    assert trades[0, 1:5].tolist() == [2, 3, 4, 4]
    assert baseline[0, 1:5].tolist() == [0, 1, 2, 4]


@pytest.mark.parametrize('mode', range(5))
def test_next_available_open_no_cost_geometry_effect(mode):
    f, t = fixture()
    f[1, :4] = [97, 103, 96, 102]  # all four pass
    f[2, :4] = [112, 115, 110, 113]  # adverse open gap beyond center
    t[2:] += 3600
    f[2, 14] = 1
    trades, _ = simulate_shapes(f, t, 0, 10000, 1., 1.4, mode)
    costly, _ = simulate_shapes(f, t, 0, 10000, 1., 2., mode)
    short, _ = simulate_shapes(mirror(f), t, 0, 10000, 1., 1.4, mode)
    assert trades[0, 1:7].tolist() == [0, 1, 2, 2, 112, 112]
    assert trades[0, 8] == pytest.approx(-1.4)
    np.testing.assert_array_equal(trades[:, :8], costly[:, :8])
    np.testing.assert_allclose(short[:, 8], trades[:, 8])


@pytest.mark.parametrize('mode', range(5))
def test_baseline_exact_and_feature_and_execution_prefix_causality(mode):
    rng = np.random.default_rng(1234)
    close = 100 + np.cumsum(rng.normal(0, .08, 12000))
    op = np.r_[close[0], close[:-1]]
    ohlc = np.column_stack([op, np.maximum(op, close) + .02, np.minimum(op, close) - .02, close])
    times = np.arange(len(close), dtype=np.int64) * 300
    f = features(ohlc, times, .01, .001)
    full, diag = simulate_shapes(f, times, 0, 5_000_000, .01, 1.4, mode)
    if mode == 0:
        old, old_diag = simulate_center(f, times, 0, 5_000_000, .01, 1.4, 3.)
        np.testing.assert_array_equal(full, old)
        np.testing.assert_array_equal(diag[:11], old_diag)
    for n in (4000, 8000):
        prefix_f = features(ohlc[:n], times[:n], .01, .001)
        np.testing.assert_array_equal(prefix_f, f[:n])
        prefix, _ = simulate_shapes(prefix_f, times[:n], 0, 5_000_000, .01, 1.4, mode)
        np.testing.assert_array_equal(prefix, full[full[:, 4] < n])


def test_selection_gates_require_both_costs_and_strict_profit():
    protocol = json.loads(SPEC.read_text())
    base = dict(trades=1000, win_rate_pct=60., profit_factor=.8)
    good = dict(trades=300, win_rate_pct=62., profit_factor=1., net_plus_open_pips=1., positive_pairs=5)
    baseline = {'1.4': base, '2.0': base}
    candidate = {'1.4': good, '2.0': good}
    assert all(gates(candidate, baseline, 'training', protocol).values())
    candidate['2.0'] = {**good, 'net_plus_open_pips': 0.}
    assert not all(gates(candidate, baseline, 'training', protocol).values())
    candidate['2.0'] = {**good, 'trades': 299}
    assert not all(gates(candidate, baseline, 'training', protocol).values())


def test_closed_win_count_excludes_open_trade_no_forced_close():
    f, t = fixture()
    f[2:, :4] = [99, 103, 96, 100]
    trades, d = simulate_shapes(f, t, 0, 2400, 1., 1.4, 1)
    assert len(trades) == 0 and d[2] == 1 and d[0] == pytest.approx(-.4)
