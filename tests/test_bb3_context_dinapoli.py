"""DMA displacement, strict confirmation and no-profit-padding checks."""
import json

import numpy as np
import pytest

from scripts.research_bb3_context_dinapoli import (SPEC, displaced_sma3, dma_allows,
                                                 improvement_checks, simulate_dma)
from scripts.research_bb3_context_center5 import simulate_center


def setup():
    f = np.zeros((8, 15))
    f[:, :10] = [100, 103, 96, 99, 110, 125, 95, 2, 105, 90]
    f[0, :4] = [98, 100, 94, 98]
    return f, np.arange(8, dtype=np.int64) * 300, np.full(8, 98.)


def run(f, t, dma, mode):
    return simulate_dma(f, t, dma, 0, 2400, 1., 1.4, mode)


def test_sma3_displaced3_uses_three_completed_older_closes():
    close = np.arange(12, dtype=float)
    dma = displaced_sma3(close)
    assert np.isnan(dma[:5]).all()
    assert dma[5] == 1 and dma[6] == 2 and dma[11] == 7
    changed = close.copy()
    changed[6:] = 999
    np.testing.assert_array_equal(displaced_sma3(changed)[:9], dma[:9])


@pytest.mark.parametrize('side', [1, -1])
def test_side_filter_is_strict(side):
    f, _, dma = setup()
    f[1, 3] = 99
    dma[1] = 99
    assert not dma_allows(f, dma, 1, side, 1)
    f[1, 3] += side
    assert dma_allows(f, dma, 1, side, 1)
    f[1, 3] -= 2 * side
    assert not dma_allows(f, dma, 1, side, 1)


@pytest.mark.parametrize('side', [1, -1])
def test_cross_uses_previous_dma_and_allows_previous_equality(side):
    f, _, dma = setup()
    dma[0:2] = [100, 101]
    f[0, 3] = 100
    f[1, 3] = 101 + side
    assert dma_allows(f, dma, 1, side, 2)
    f[0, 3] = 100 + side
    assert not dma_allows(f, dma, 1, side, 2)


@pytest.mark.parametrize('side', [1, -1])
def test_slope_requires_favorable_price_and_strict_dma_slope(side):
    f, _, dma = setup()
    dma[0:2] = [100, 100]
    f[1, 3] = 100 + 2 * side
    assert not dma_allows(f, dma, 1, side, 3)
    dma[1] += side
    assert dma_allows(f, dma, 1, side, 3)
    f[1, 3] = dma[1]
    assert not dma_allows(f, dma, 1, side, 3)


def test_dma_rejection_cancels_preparation_and_samebar_rearming():
    f, t, dma = setup()
    dma[1] = 100
    f[1, 2] = 94
    trades, d = run(f, t, dma, 1)
    assert len(trades) == 0 and d[6] == 1 and d[7] == 0 and d[11] == 1


def test_center_distance_cancel_precedes_dma_and_minimum_is_three():
    f, t, dma = setup()
    f[1, 4] = 102  # exactly3 pips passes, unlike prior5 threshold
    _, d = run(f, t, dma, 1)
    assert d[7] == 1
    f[1, 4] = 101
    dma[1] = 100
    _, d = run(f, t, dma, 1)
    assert d[7] == 0 and d[10] == 1 and d[11] == 0


def test_baseline_min3_matches_current_center_simulator_exactly():
    f, t, dma = setup()
    f[2, :5] = [100, 115, 99, 114, 120]
    actual, d = run(f, t, dma, 0)
    baseline, ref = simulate_center(f, t, 0, 2400, 1., 1.4, 3.)
    np.testing.assert_array_equal(actual, baseline)
    np.testing.assert_array_equal(d[:11], ref)
    assert actual[0, 3:8].tolist() == [2, 2, 100, 110, 110]


@pytest.mark.parametrize('mode', [0, 1, 2, 3])
def test_dma_filter_prefix_does_not_read_future(mode):
    f, t, dma = setup()
    dma[0:3] = [98, 98.5, 99]
    f[2, :5] = [100, 115, 99, 114, 120]
    actual, _ = run(f, t, dma, mode)
    prefix, _ = run(f[:5], t[:5], dma[:5], mode)
    np.testing.assert_array_equal(prefix, actual[actual[:, 4] < 5])


def gate_inputs(trades=100, win=70., pf=.9, avg=-.1, pairs=6):
    baseline = {'cost': {'segment1': {'trades': 400, 'win_rate_pct': 60., 'profit_factor': .8, 'average_pips': -.2}}}
    candidate = {'cost': {'segment1': {'trades': trades, 'win_rate_pct': win, 'profit_factor': pf, 'average_pips': avg}}}
    b = [{'period': 'segment1', 'cost_case': 'cost', 'symbol': str(i), 'trades': 40, 'win_rate_pct': 60.} for i in range(9)]
    c = [{**r, 'trades': 10, 'win_rate_pct': 70. if i < pairs else 50.} for i, r in enumerate(b)]
    return candidate, baseline, c, b


def test_winrate_improvement_is_not_profitability_or_sparse_win_padding():
    checks, _ = improvement_checks(*gate_inputs(), 'segment1')
    assert all(checks.values())  # PF below1 and negative average can improve, but do not imply profit
    checks, _ = improvement_checks(*gate_inputs(trades=99), 'segment1')
    assert not checks['cost.segment1.sample_retained']
    checks, _ = improvement_checks(*gate_inputs(pf=.7), 'segment1')
    assert not checks['cost.segment1.pf_not_lower']
    checks, _ = improvement_checks(*gate_inputs(avg=-.3), 'segment1')
    assert not checks['cost.segment1.average_not_lower']
    checks, _ = improvement_checks(*gate_inputs(pairs=5), 'segment1')
    assert not checks['cost.segment1.six_pairs_winrate_up']


def test_exact_four_candidates_and_preselection_profit_requirement():
    p = json.loads(SPEC.read_text(encoding='utf-8'))
    assert len(p['search_space']) == p['candidate_budget'] == 4
    assert 'BEFORE later simulations' in p['training_selection']
    assert 'closed net>0 AND net+open>0' in p['profit_requirement']
    assert 'no fallback' in p['training_selection']
