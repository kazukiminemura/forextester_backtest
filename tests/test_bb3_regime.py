"""Confirmed-time regime features and fixed BB state-machine behavior."""
import json

import numpy as np
import pytest

from scripts.research_bb3_regime import (
    SPEC, atr_series, comparison_gates, regime_allowed, regime_features, simulate_regime,
)
from scripts.research_bb3_candle_shapes import simulate_shapes
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


def market(n=1500):
    t = np.arange(n, dtype=np.int64) * 300
    rng = np.random.default_rng(71)
    cl = 100 + np.cumsum(rng.normal(0, .05, n))
    op = np.r_[cl[0], cl[:-1]]
    f = features(np.column_stack([op, np.maximum(op, cl) + .02, np.minimum(op, cl) - .02, cl]), t, .01, .001)
    return f, t


def test_hour_alignment_available_at_exact_close_not_before():
    f, t = market(300)
    r, h = regime_features(f, t)
    assert len(h) == 25 and np.isnan(r[10, 3]) and r[11, 3] == 3600
    assert r[22, 3] == 3600 and r[23, 3] == 7200
    assert h[0, 1:5].tolist() == [f[0, 0], max(f[:12, 1]), min(f[:12, 2]), f[11, 3]]
    assert np.isnan(r[274, 0])  # only22 complete hours
    assert r[275, 0] == h[22, 7]
    assert h[22, 7] == pytest.approx((np.mean(h[3:23, 4]) - np.mean(h[:20, 4])) / h[22, 5])


def test_incomplete_hour_not_fabricated_and_stale_rejects():
    f, t = market(360)
    keep = np.ones(len(t), dtype=bool)
    keep[24 * 12 + 3] = False
    g, times = f[keep], t[keep]
    r, h = regime_features(g, times)
    assert 25 * 3600 not in h[:, 0]
    last_before = np.where(times == 25 * 3600 - 600)[0][0]
    exactly_stale = np.where(times == 25 * 3600 - 300)[0][0]
    assert not np.isnan(r[last_before, 0])
    assert np.isnan(r[exactly_stale, 0])
    assert not regime_allowed(r, exactly_stale, 1, 1)
    fresh = np.where(times == 26 * 3600 - 300)[0][0]
    assert not np.isnan(r[fresh, 0]) and r[fresh, 3] == 26 * 3600


def test_misaligned_complete_count_does_not_create_hour():
    f, t = market(48)
    r, h = regime_features(f, t + 1)
    assert len(h) == 0 and np.all(np.isnan(r[:, 0]))


def test_volatility_excludes_current_from100bar_denominator():
    f, t = market(350)
    r, _ = regime_features(f, t)
    atr, tr = atr_series(f[:, :4])
    assert np.isnan(r[112, 1])
    assert r[113, 1] == pytest.approx(atr[113] / np.mean(atr[13:113]))
    for i in (113, 220, 349):
        assert r[i, 1] == pytest.approx(atr[i] / np.mean(atr[i - 100:i]))
        assert r[i, 2] == pytest.approx(tr[i] / atr[i - 1])


def test_wilder_atr_seed_and_gap_in_true_range():
    ohlc = np.tile([10., 11., 9., 10.], (16, 1))
    ohlc[14:] += 10
    atr, tr = atr_series(ohlc)
    assert np.isnan(atr[12]) and atr[13] == 2
    assert tr[14] == 11 and atr[14] == pytest.approx((2 * 13 + 11) / 14)


@pytest.mark.parametrize('slope,side,allowed', [(-.25, 1, False), (-.2499, 1, True), (.25, -1, False), (.2499, -1, True), (-.5, -1, True), (.5, 1, True)])
def test_trend_inclusive_strong_thresholds(slope, side, allowed):
    r = np.array([[slope, 1., 1., 3600.]])
    assert regime_allowed(r, 0, side, 1) == allowed


@pytest.mark.parametrize('ratio,impulse,allowed', [(.5, 2.5, True), (2., 2.5, True), (.4999, 1., False), (2.0001, 1., False), (1., 2.5001, False), (np.nan, 1., False), (1., np.nan, False)])
def test_volatility_boundaries_and_h1_independence(ratio, impulse, allowed):
    r = np.array([[np.nan, ratio, impulse, np.nan]])
    assert regime_allowed(r, 0, 1, 2) == allowed
    assert not regime_allowed(r, 0, 1, 3)


def test_future_changes_do_not_rewrite_confirmed_regimes():
    f, t = market()
    r, h = regime_features(f, t)
    for n in (311, 600, 1001):
        prefix, hours = regime_features(f[:n], t[:n])
        np.testing.assert_array_equal(prefix, r[:n])
        np.testing.assert_array_equal(hours, h[h[:, 0] <= t[n - 1] + 300])
        changed = f.copy()
        changed[n:, :4] += 100
        future, _ = regime_features(changed, t)
        np.testing.assert_array_equal(future[:n], r[:n])


@pytest.mark.parametrize('shape', [0, 3])
@pytest.mark.parametrize('mode', [0, 1, 2, 3])
def test_baseline_prefix_causality_and_direction_symmetry(shape, mode):
    f, t = market(6000)
    r, _ = regime_features(f, t)
    full, diag = simulate_regime(f, r, t, 0, 3_000_000, .01, .4, shape, mode)
    if mode == 0:
        old, olddiag = simulate_shapes(f, t, 0, 3_000_000, .01, .4, shape)
        np.testing.assert_array_equal(full, old)
        np.testing.assert_array_equal(diag[:12], olddiag)
    n = 3501
    prefix, _ = simulate_regime(f[:n], r[:n], t[:n], 0, 3_000_000, .01, .4, shape, mode)
    np.testing.assert_array_equal(prefix, full[full[:, 4] < n])
    reverse_r = r.copy()
    reverse_r[:, 0] *= -1
    short, _ = simulate_regime(mirror(f), reverse_r, t, 0, 3_000_000, .01, .4, shape, mode)
    np.testing.assert_array_equal(short[:, :5], full[:, :5] * [-1, 1, 1, 1, 1])
    np.testing.assert_allclose(short[:, 8], full[:, 8], atol=1e-10)


@pytest.mark.parametrize('shape', [0, 3])
def test_regime_failure_cancels_no_samebar_rearm_but_new_setup_possible(shape):
    f, t = fixture()
    f[1, 2] = 94
    f[2, :4] = [99, 100, 94, 98]
    f[3, :4] = [97, 100, 96, 99]
    f[4, :4] = [100, 115, 99, 114]
    r = np.tile([0., 1., 1., 0.], (len(f), 1))
    r[1, 0] = -.25
    trades, d = simulate_regime(f, r, t, 0, 2400, 1., .2, shape, 1)
    assert d[6] == 2 and d[12] == 1 and trades[0, 1:5].tolist() == [2, 3, 4, 4]


def test_gates_compare_matching_baseline_every_year_both_costs():
    protocol = json.loads(SPEC.read_text())
    annual = {str(y): dict(net_pips=1., win_rate_pct=70.) for y in (2023, 2024, 2025)}
    base = dict(trades=1000, win_rate_pct=70., profit_factor=1.1, net_pips=100., net_plus_open_pips=100., positive_pairs=4, annual=annual)
    good = {**base, 'trades': 300, 'win_rate_pct': 72., 'profit_factor': 1.2, 'net_pips': 101.}
    baseline = {'normal': base, 'stress': base}
    candidate = {'normal': good, 'stress': good}
    assert all(comparison_gates(candidate, baseline, protocol).values())
    candidate['stress'] = {**good, 'annual': {**annual, '2024': {'net_pips': 0., 'win_rate_pct': 70.}}}
    assert not all(comparison_gates(candidate, baseline, protocol).values())
