"""Exact DMA difference ordering, strict zero and unchanged signal timing."""
import json

import numpy as np
import pytest

from scripts.research_bb3_context_dinapoli_deceleration import SPEC, acceleration_allows, simulate_dma
from scripts.research_bb3_context_center5 import simulate_center


@pytest.mark.parametrize('side', [1,-1])
def test_adverse_velocity_deceleration_without_price_side_gate(side):
    dma = side * np.array([103.,101.,100.])
    assert acceleration_allows(dma,2,side,1)
    assert acceleration_allows(dma,2,side,2)
    dma = side * np.array([103.,102.,100.])
    assert not acceleration_allows(dma,2,side,1)
    assert not acceleration_allows(dma,2,side,2)


@pytest.mark.parametrize('side', [1,-1])
def test_constant_adverse_speed_fails_and_favorable_speed_passes_relaxed(side):
    dma = side * np.array([103.,102.,101.])
    assert not acceleration_allows(dma,2,side,1)
    assert not acceleration_allows(dma,2,side,2)
    dma = side * np.array([100.,102.,103.])
    assert not acceleration_allows(dma,2,side,1)
    assert acceleration_allows(dma,2,side,2)


def test_exact_zero_boundaries_and_missing_values():
    dma = np.array([100.,100.,100.])
    assert not acceleration_allows(dma,2,1,1)
    assert acceleration_allows(dma,2,1,2)
    for j in range(3):
        bad = dma.copy()
        bad[j] = np.nan
        assert not acceleration_allows(bad,2,1,1)
        assert not acceleration_allows(bad,2,1,2)
    assert acceleration_allows(np.array([np.nan]),0,1,0)


def test_difference_of_differences_exact_evaluation_and_no_epsilon():
    dma = np.array([1.,1.,np.nextafter(1.,2.)])
    assert acceleration_allows(dma,2,1,1)
    assert not acceleration_allows(dma,2,-1,1)
    for triple in ([1.1,1.2,1.3],[200.001,200.002,200.003],[1e-10,1e-10,2e-10]):
        values = np.array(triple)
        expected = (values[2]-values[1])-(values[1]-values[0]) > 0
        assert acceleration_allows(values,2,1,1) == expected


def setup():
    f = np.zeros((12,15))
    f[:,:10] = [100,103,96,99,110,125,95,2,105,90]
    f[3,:4] = [98,100,94,98]
    dma = np.full(12,100.)
    dma[2:5] = [103,101,100]
    return f,np.arange(12,dtype=np.int64)*300,dma


def run(f,t,dma,mode):
    return simulate_dma(f,t,dma,0,99999,1.,1.4,mode)


@pytest.mark.parametrize('mode',[1,2])
def test_filter_does_not_delay_entry(mode):
    f,t,dma = setup()
    f[5,:5] = [100,115,99,114,120]
    trades,d = run(f,t,dma,mode)
    assert trades[0,1:5].tolist() == [3,4,5,5]
    assert d[11] == 0


def test_failure_cancels_without_samebar_rearm_or_later_retry():
    f,t,dma = setup()
    dma[2:5] = [103,102,100]
    f[4,2] = 94
    trades,d = run(f,t,dma,1)
    assert len(trades) == 0 and d[6] == 1 and d[7] == 0 and d[11] == 1


def test_min3_distance_checked_before_dma():
    f,t,dma = setup()
    f[4,4] = 101
    dma[4] = np.nan
    _,d = run(f,t,dma,1)
    assert d[10] == 1 and d[11] == 0


def test_baseline_exact_and_no_extra_restriction():
    f,t,dma = setup()
    f[5,:5] = [100,115,99,114,120]
    actual,d = run(f,t,dma,0)
    expected,ed = simulate_center(f,t,0,99999,1.,1.4,3.)
    np.testing.assert_array_equal(actual,expected)
    np.testing.assert_array_equal(d[:11],ed)


@pytest.mark.parametrize('mode',[0,1,2])
def test_prefix(mode):
    f,t,dma = setup()
    f[5,1] = 115
    full,_ = run(f,t,dma,mode)
    short,_ = run(f[:7],t[:7],dma[:7],mode)
    np.testing.assert_array_equal(short,full[full[:,4]<7])


def test_three_frozen_rules_no_extra_thresholds():
    p=json.loads(SPEC.read_text(encoding='utf8'))
    assert p['candidate_budget']==len(p['search_space'])==3
    assert 'no epsilon' in p['numeric_boundary']
    assert 'difference-of-differences' in p['numeric_boundary']
    assert 'closed net>0 AND net+open>0' in p['profit_requirement']
