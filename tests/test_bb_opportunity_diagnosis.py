import numpy as np

from scripts.diagnose_bb_opportunities import diagnose, trade_stats


def sample():
    f = np.zeros((4,15))
    f[:,:4] = [[10,11,8,9],[9,11,8.5,10],[10,12,9,11],[11,16,10,15.5]]
    f[:,4:9] = [15,21,9,1,20]
    return f, np.arange(4)*300


def test_confirmation_requires_later_break_and_prefix_stability():
    f,t = sample()
    counts,signals = diagnose(f,t,1,.1,0,1200)
    assert counts['prepared'] == counts['confirmation_reached'] == counts['candidates'] == 1
    assert signals[0]['index'] == 2 and signals[0]['confirmed_index'] == 1
    assert diagnose(f[:2],t[:2],1,.1,0,1200)[1] == []
    assert diagnose(f[:3],t[:3],1,.1,0,1200)[1] == signals


def test_extreme_update_precedes_break_and_other_cancellations():
    f,t = sample()
    f[2,2],f[2,10] = 7,1
    counts,signals = diagnose(f,t,1,.1,0,1200)
    assert counts['cancel_extreme_update'] == 1
    assert counts.get('cancel_impulse',0) == 0
    assert counts['cancel_after_confirmation'] == 1 and signals == []


def test_breakout_room_failure_consumes_setup():
    f,t = sample()
    f[2,:4] = [13,14,12,13.2]
    counts,signals = diagnose(f,t,1,.1,0,1200)
    assert counts['breakout_room_rejected'] == 1 and signals == []


def test_gap_precedes_extreme_update():
    f,t = sample()
    t[2:] += 300
    f[2,2] = 7
    counts,_ = diagnose(f,t,1,.1,0,1500)
    assert counts['cancel_gap'] == 1 and counts.get('cancel_extreme_update',0) == 0


def test_cost_decomposition_and_rr_break_even():
    trades = [dict(risk_pips=4,net_pips=3,cost_pips=1,exit_reason='target'),
              dict(risk_pips=4,net_pips=-5,cost_pips=1,exit_reason='stop')]
    stats=trade_stats(trades)
    assert stats['gross_r'] == 0 and stats['net_r'] == -.5
    assert stats['cost_r'] == .5 and stats['mean_break_even_win_rate_pct'] == 62.5


def test_risk_buckets_ignore_float_noise_at_exact_pip_boundaries():
    trades = [dict(risk_pips=r,net_pips=1,cost_pips=1,exit_reason='target')
              for r in [4.9,5-1e-12,5,5+1e-12,9.9,10-1e-12,10]]
    stats = trade_stats(trades)
    assert stats['risk_below5_count'] == 1
    assert stats['risk_below10_count'] == 5
