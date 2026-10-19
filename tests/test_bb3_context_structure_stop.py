"""Frozen preparation stop tests, including adverse gaps and exact RR geometry."""
import json

import numpy as np
import pytest

from scripts.research_bb3_context_structure_stop import (SPEC, descriptive_stats,
                                                        simulate_structure_stop, structural_target)


def setup():
    f = np.zeros((8, 15))
    f[:, :10] = [100, 103, 99, 101, 110, 125, 95, 2, 105, 90]
    f[0, :4] = [98, 100, 94, 98]
    f[1, :4] = [98, 100, 96, 99]
    return f, np.arange(8, dtype=np.int64) * 300


def run(f, t, limit=False, buffer=.1, tick=.001):
    return simulate_structure_stop(f, t, 0, 2400, 1., 1.4, tick, limit, buffer)


def test_stop_includes_all_preparation_to_signal_bars_only():
    f, t = setup()
    f[1, :4] = [96, 99, 93, 94]  # no close-return, preparation survives
    f[2, :4] = [96, 100, 95, 99]
    f[3, :4] = [100, 102, 90, 95]  # entry-bar low90 must NOT widen SL
    trades, _ = run(f, t)
    assert trades[0, 1:5].tolist() == [0, 2, 3, 3]
    assert trades[0, 9] == pytest.approx(92.8)
    assert trades[0, 11] == pytest.approx(7.2)


def test_preparation_reset_removes_old_extreme():
    f, t = setup()
    f[0, 2] = 90
    f[1, 10] = 1
    f[2, :4] = [98, 100, 94, 98]
    f[3, :4] = [98, 100, 96, 99]
    f[4, :4] = [100, 103, 92, 95]
    trades, _ = run(f, t)
    assert trades[0, 1:5].tolist() == [2, 3, 4, 4]
    assert trades[0, 9] == pytest.approx(93.8)


def test_signal_atr_and_absolute_stop_not_changed_at_fill():
    f, t = setup()
    f[2:, 7] = 100
    f[3, :4] = [100, 103, 92, 95]
    trades, _ = run(f, t, buffer=.25)
    assert trades[0, 9] == pytest.approx(93.5)
    assert trades[0, 12] == 2


def test_known_invalid_limit_is_not_submitted():
    f, t = setup()
    f[1, 7] = 10  # limit89 lies below stop93
    trades, d = run(f, t, limit=True)
    assert len(trades) == 0 and d[20] == 1 and d[21] == 0
    assert d[5] == 0


@pytest.mark.parametrize('limit', [False, True])
def test_adverse_gap_is_counted_as_immediate_cost_loss(limit):
    f, t = setup()
    f[2, :4] = [90, 96, 89, 94]
    trades, d = run(f, t, limit=limit)
    assert len(trades) == 1
    assert trades[0, 3:7].tolist() == [2, 2, 90, 90]
    assert trades[0, 8] == pytest.approx(-1.4)
    assert np.isnan(trades[0, 7]) and np.isnan(trades[0, 10])
    assert trades[0, 11] < 0 and trades[0, 14] == 1
    assert d[21] == 1
    summary = descriptive_stats(trades, d, 1)
    assert summary['trades'] == 1 and summary['risk_trade_count'] == 0
    assert summary['average_risk_pips'] is None
    assert summary['net_pips'] == pytest.approx(-1.4)


def test_gap_limit_fill_anchors_target_to_actual_risk_without_moving_stop():
    f, t = setup()
    f[2, :4] = [96, 100, 95, 99]
    trades, _ = run(f, t, limit=True)
    assert trades[0, 5] == 96 and trades[0, 9] == pytest.approx(93.8)
    assert trades[0, 11] == pytest.approx(2.2)
    assert trades[0, 6] == pytest.approx(98.86)


def test_intrabar_limit_stop_is_live_and_target_not_credited():
    f, t = setup()
    f[2, :4] = [100, 110, 92, 99]
    trades, d = run(f, t, limit=True)
    assert trades[0, 5] == 97 and trades[0, 6] == pytest.approx(93.8)
    assert trades[0, 14] == 1 and d[10] == 1 and d[14] == 1


@pytest.mark.parametrize('side', [1, -1])
def test_non_grid_actual_entry_never_reduces_rr(side):
    entry, risk, tick = 100.0005, .0125, .001
    target = structural_target(entry, side, risk, tick)
    assert target / tick == pytest.approx(round(target / tick))
    reward = side * (target - entry)
    assert reward >= risk * 1.3 - 1e-12
    assert reward - risk * 1.3 < tick + 1e-12


def test_short_structural_geometry_is_symmetric():
    f, t = setup()
    f[2, :4] = [96, 100, 95, 99]
    g = f.copy()
    for a, b in ((0, 0), (1, 2), (2, 1), (3, 3), (4, 4), (5, 6), (6, 5), (8, 9), (9, 8)):
        g[:, a] = 400 - f[:, b]
    trades, _ = run(g, t, limit=True)
    assert trades[0, 0] == -1 and trades[0, 5] == 304
    assert trades[0, 9] == pytest.approx(306.2)
    assert trades[0, 6] == pytest.approx(301.14)


@pytest.mark.parametrize('limit,buffer', [(l, b) for l in (False, True) for b in (.1, .25)])
def test_prefix_invariance(limit, buffer):
    f, t = setup()
    f[2, :4] = [96, 120, 90, 99]
    full, _ = run(f, t, limit, buffer)
    prefix, _ = run(f[:5], t[:5], limit, buffer)
    np.testing.assert_array_equal(prefix, full[full[:, 4] < 5])


def test_protocol_six_cases_and_training_only_data_amendment():
    p = json.loads(SPEC.read_text(encoding='utf-8'))
    assert len(p['search_space']) == p['candidate_budget'] == 6
    assert 'training ONLY' in p['evaluation_access']
    assert 'Do NOT cancel adverse gap' in p['invalid_fill_rule']
    assert p['exit_rules']['reward_risk_ratio'] == 1.3
