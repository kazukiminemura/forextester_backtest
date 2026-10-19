"""Causal waiting transitions, deadline boundaries and unchanged baseline."""
import json

import numpy as np
import pytest

from scripts.research_bb3_context_dinapoli_wait import SPEC, simulate_wait
from scripts.research_bb3_context_center5 import simulate_center


def setup(side=1):
    f = np.zeros((12, 15))
    f[:, :10] = [100, 103, 96, 99, 110, 125, 95, 2, 105, 90]
    f[0, :4] = [98, 100, 94, 98]
    dma = np.full(12, 101.)
    if side == -1:
        old = f.copy()
        for j in (0, 3, 4, 8, 9):
            f[:, j] = 200 - old[:, j]
        f[:, 1], f[:, 2] = 200 - old[:, 2], 200 - old[:, 1]
        f[:, 5], f[:, 6] = 200 - old[:, 6], 200 - old[:, 5]
        dma = 200 - dma
    return f, np.arange(12, dtype=np.int64) * 300, dma


def run(f, times, dma, wait=3):
    return simulate_wait(f, times, dma, 0, 99999, 1., 1.4, wait)


@pytest.mark.parametrize('side', [1, -1])
@pytest.mark.parametrize('ttl', [3, 6])
def test_last_permitted_bar_recovers_and_next_open_enters(side, ttl):
    f, t, dma = setup(side)
    signal = 1 + ttl
    dma[signal] = f[signal, 3] - side
    _, d = run(f, t, dma, ttl)
    assert d[11:14].tolist() == [1, 1, 0]
    assert d[8] == signal + 1 and d[7] == 1 and d[2] == side
    assert d[6] == 1  # no duplicate setup


@pytest.mark.parametrize('ttl', [3, 6])
def test_after_deadline_cancels_before_confirmation(ttl):
    f, t, dma = setup()
    dma[2 + ttl] = 98
    _, d = run(f, t, dma, ttl)
    assert d[7] == 0 and d[13] == 1 and d[23] == 1


@pytest.mark.parametrize('column,reason', [(14,17),(10,18),(12,19)])
def test_gap_explained_wick_cancel_before_recovery_no_samebar_rearm(column, reason):
    f, t, dma = setup()
    f[2, column] = 1
    f[2, 2] = 94  # eligible new touch prohibited on cancellation bar
    dma[2] = 98
    _, d = run(f, t, dma)
    assert d[6] == 1 and d[7] == 0 and d[reason] == 1


def test_distance_cancel_even_outside_band_and_dma_favorable():
    f, t, dma = setup()
    f[2, 3:7] = [109,110,108,95]  # above band, not yet center, below min3
    dma[2] = 98
    _, d = run(f, t, dma)
    assert d[7] == 0 and d[10] == 1 and d[22] == 1


def test_outside_band_only_waits_and_same_side_retouch_does_not_extend():
    f, t, dma = setup()
    f[2, 2:4] = [93,94]
    dma[2] = 90  # favorable but not inside; cannot signal
    dma[3] = 98
    _, d = run(f, t, dma)
    assert d[8] == 4 and d[11:14].tolist() == [1,1,0]
    assert d[15] == 1


def test_terminal_waiting_preserved_without_forced_trade():
    f, t, dma = setup()
    trades, d = run(f[:3], t[:3], dma[:3])
    assert len(trades) == 0 and d[14:16].tolist() == [1,1]


def test_baseline_matches_min3_and_favorable_dma_is_immediate():
    f, t, dma = setup()
    f[2, :5] = [100,115,99,114,120]
    actual, d = run(f, t, dma, 0)
    ref, rd = simulate_center(f,t,0,99999,1.,1.4,3.)
    np.testing.assert_array_equal(actual,ref)
    np.testing.assert_array_equal(d[:11],rd)
    dma[1] = 98
    actual, d = run(f,t,dma)
    assert actual[0, 1:5].tolist() == [0,1,2,2]
    assert d[11:14].tolist() == [0,0,0]


@pytest.mark.parametrize('wait', [0,3,6])
def test_prefix_no_future_fill(wait):
    f,t,dma = setup()
    dma[3] = 98
    f[5,1] = 115
    full,_ = run(f,t,dma,wait)
    short,_ = run(f[:6],t[:6],dma[:6],wait)
    np.testing.assert_array_equal(short,full[full[:,4] < 6])


def test_frozen_three_cases_only_and_profit_is_separate():
    p = json.loads(SPEC.read_text(encoding='utf8'))
    assert p['candidate_budget'] == len(p['search_space']) == 3
    assert [c['wait_bars'] for c in p['search_space']] == [0,3,6]
    assert 'closed net>0 AND net+open>0' in p['profit_requirement']
    assert 'BEFORE later simulations' in p['training_selection']
