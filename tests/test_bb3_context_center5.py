"""Current Pine center-distance cancellation and fixed profit-check scope."""
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research_bb3_context_center5 import SPEC, simulate_center
from scripts.research_bb3_context_timing import features, simulate


def setup():
    f = np.zeros((8, 15))
    f[:, :10] = [100, 103, 96, 99, 110, 125, 95, 2, 105, 90]
    f[0, :4] = [98, 100, 94, 98]
    return f, np.arange(8, dtype=np.int64) * 300


def run(f, t, minimum=5):
    return simulate_center(f, t, 0, 2400, 1., 1.4, minimum)


def test_failed_distance_cancels_instead_of_waiting():
    f, t = setup()
    f[1, :4] = [106, 109, 96, 108]  # only2 pips to center
    trades, d = run(f, t)
    assert len(trades) == 0 and d[7] == 0 and d[10] == 1
    _, d0 = run(f, t, 0)
    assert d0[7] == 1


def test_failed_candidate_cannot_rearm_on_same_touch_bar():
    f, t = setup()
    f[1, :4] = [106, 109, 94, 108]  # repeat same-side touch is not a new prep
    _, d = run(f, t)
    assert d[6] == 1 and d[7] == 0 and d[10] == 1


def test_fresh_later_touch_can_prepare_after_distance_cancellation():
    f, t = setup()
    f[1, :4] = [106, 109, 94, 108]
    f[2, 2] = 94
    _, d = run(f, t)
    assert d[6] == 2 and d[7] == 1 and d[10] == 1


@pytest.mark.parametrize('distance,expected', [(5., 1), (5. - .5e-9, 1), (5. - 2e-9, 0)])
def test_one_nanopip_tolerance_matches_pine(distance, expected):
    f, t = setup()
    f[1, 4] = 99 + distance
    _, d = run(f, t)
    assert d[7] == expected


def test_confirmed_signal_next_open_dynamic_target_order():
    f, t = setup()
    f[2, :5] = [100, 115, 99, 114, 120]
    trades, _ = run(f, t)
    assert trades[0, :8].tolist() == [1, 0, 1, 2, 2, 100, 110, 110]
    assert trades[0, 8] == pytest.approx(8.6)


def test_five_pip_signal_room_does_not_guarantee_positive_gap_entry():
    f, t = setup()
    f[2, :4] = [112, 115, 110, 113]
    t[2:] += 3600
    f[2, 14] = 1
    trades, _ = simulate_center(f, t, 0, 10000, 1., 1.4, 5)
    assert trades[0, 5] == trades[0, 6] == 112
    assert trades[0, 8] == pytest.approx(-1.4)


def test_short_direction_is_symmetric():
    f, t = setup()
    f[2, :5] = [100, 115, 99, 114, 120]
    g = f.copy()
    for a, b in ((0, 0), (1, 2), (2, 1), (3, 3), (4, 4), (5, 6), (6, 5), (8, 9), (9, 8)):
        g[:, a] = 400 - f[:, b]
    trades, _ = run(g, t)
    assert trades[0, 0] == -1 and trades[0, 8] == pytest.approx(8.6)


def test_minzero_exactly_reproduces_original_and_prefix_is_causal():
    rng = np.random.default_rng(512)
    close = 100 + np.cumsum(rng.normal(0, .02, 3000))
    op = np.r_[close[0], close[:-1]]
    ohlc = np.column_stack([op, np.maximum(op, close) + .01, np.minimum(op, close) - .01, close])
    times = np.arange(len(close), dtype=np.int64) * 300
    f = features(ohlc, times, .01, .001)
    actual, d = simulate_center(f, times, 0, 1_000_000, .01, 1.4, 0)
    reference, old = simulate(f, times, 0, 1_000_000, .01, 1.4)
    np.testing.assert_array_equal(actual, reference)
    np.testing.assert_array_equal(d[:10], old)
    for minimum in (0, 5):
        full, _ = simulate_center(f, times, 0, 1_000_000, .01, 1.4, minimum)
        prefix, _ = simulate_center(f[:2300], times[:2300], 0, 1_000_000, .01, 1.4, minimum)
        np.testing.assert_array_equal(prefix, full[full[:, 4] < 2300])


def test_open_pnl_separate_no_forced_end_exit():
    f, t = setup()
    trades, d = run(f, t)
    assert len(trades) == 0 and d[2] == 1 and d[0] == pytest.approx(-2.4)


def test_current_pine_contract_and_fixed_cutoff_protocol():
    p = json.loads(SPEC.read_text(encoding='utf-8'))
    source = (Path(__file__).resolve().parents[1] / p['pine_source']).read_text(encoding='utf-8')
    assert 'float minCenterPips = input.float(5.0,' in source
    assert 'armed * (basis - close) / pipSize + 1e-9 < minCenterPips' in source
    assert 'if reason != "" or signalSide != 0' in source
    assert len(p['search_space']) == p['candidate_budget'] == 2
    assert p['periods']['continuous'] == ['2023-09-08', '2026-08-31']
    assert 'no optimization' in p['evaluation_type']
