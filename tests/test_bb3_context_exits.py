"""Causal stop/target behavior; not a Pine compiler or broker emulator."""
import json

import numpy as np
import pytest

from scripts.research_bb3_context_exits import (SPEC, bracket_fill, fixed_target,
                                               risk_distance, simulate_exits)


def setup():
    f = np.zeros((8, 15))
    f[:, :10] = [100, 103, 99, 101, 110, 125, 95, 2, 105, 90]
    f[0, :4] = [98, 100, 94, 98]
    f[1, :4] = [98, 100, 96, 99]
    return f, np.arange(8, dtype=np.int64) * 300


def run(f, times, limit=False, stop=1, rr=1.3, tick=.001):
    return simulate_exits(f, times, 0, 2400, 1., 1.4, tick, limit, stop, rr)


@pytest.mark.parametrize('side,op,hi,lo,target,stop,expected', [
    (1, 100, 108, 94, 106.5, 95, (95, True, True)),
    (-1, 100, 106, 92, 93.5, 105, (105, True, True)),
    (1, 93, 108, 92, 106.5, 95, (93, True, True)),
    (-1, 107, 108, 92, 93.5, 105, (107, True, True)),
    (1, 108, 109, 94, 106.5, 95, (108, False, True)),
    (-1, 92, 106, 91, 93.5, 105, (92, False, True)),
])
def test_bracket_open_then_intrabar_stop_priority(side, op, hi, lo, target, stop, expected):
    assert bracket_fill(side, op, hi, lo, target, stop) == expected


def test_risk_and_reward_tick_rounding():
    assert risk_distance(1, .01, 1, .001) == pytest.approx(.05)
    assert risk_distance(2, .0001, 1, .00001) == pytest.approx(.001)
    risk = risk_distance(3, 1, 1.71, .1)
    assert risk == pytest.approx(2.6)
    reward = fixed_target(100, 1, risk, 1.3, .1) - 100
    assert reward == pytest.approx(3.4)
    assert reward / risk >= 1.3 and reward - risk * 1.3 < .1


def test_market_entry_stop_exists_on_entry_bar_and_full_loss():
    f, t = setup()
    f[2, :4] = [100, 108, 94, 102]
    trades, d = run(f, t)
    assert trades[0, 3:10].tolist() == [2, 2, 100, 95, 106.5, -6.4, 95]
    assert trades[0, 14] == 1 and d[14] == 1


def test_atr_frozen_on_signal_not_fill_and_never_widened():
    f, t = setup()
    f[1, 7] = 2
    f[2:, 7] = 100
    f[3, :4] = [100, 103, 96, 99]
    trades, _ = run(f, t, stop=3)
    assert trades[0, 11:13].tolist() == [3, 2]
    assert trades[0, 9] == 97
    assert trades[0, 8] == pytest.approx(-4.4)


def test_fixed_rr_uses_actual_open_and_never_updates_to_center():
    f, t = setup()
    f[2, :4] = [112, 113, 111, 112]
    f[2, 4] = 100
    f[3:, :4] = [112, 119, 110, 118]
    f[3:, 4] = 99
    trades, _ = run(f, t)
    assert trades[0, 3:8].tolist() == [2, 3, 112, 118.5, 118.5]
    assert trades[0, 9:12].tolist() == [107, 118.5, 5]


def test_center_updates_only_after_bar_and_stop_stays_fixed():
    f, t = setup()
    f[2, :4] = [100, 103, 99, 100]
    f[2, 4] = 102
    trades, _ = run(f, t, rr=0)
    assert trades[0, 3:8].tolist() == [2, 3, 100, 102, 102]
    assert trades[0, 9:12].tolist() == [95, 110, 5]


def test_intrabar_limit_entry_suppresses_tp_but_keeps_sl():
    f, t = setup()
    f[2, :4] = [100, 108, 91, 99]  # limit97, SL92, TP103.5
    trades, d = run(f, t, limit=True)
    assert trades[0, 3:10].tolist() == [2, 2, 97, 92, 103.5, -6.4, 92]
    assert trades[0, 13:15].tolist() == [2, 1]
    assert d[10] == 1 and d[14] == 1


def test_limit_open_improvement_anchors_bracket_and_allows_target():
    f, t = setup()
    f[2, :4] = [96, 104, 94, 103]
    trades, _ = run(f, t, limit=True)
    assert trades[0, 3:8].tolist() == [2, 2, 96, 102.5, 102.5]
    assert trades[0, 9] == 91 and trades[0, 13] == 1


def test_short_limit_trade_is_symmetric():
    f, t = setup()
    f[2, :4] = [96, 104, 94, 103]
    g = f.copy()
    for a, b in ((0, 0), (1, 2), (2, 1), (3, 3), (4, 4), (5, 6), (6, 5), (8, 9), (9, 8)):
        g[:, a] = 400 - f[:, b]
    trades, _ = run(g, t, limit=True)
    assert trades[0, 0] == -1 and trades[0, 5] == 304
    assert trades[0, 6] == 297.5 and trades[0, 9] == 309
    assert trades[0, 8] == pytest.approx(5.1)


def test_no_forced_closing_and_open_cost_separate():
    f, t = setup()
    trades, d = run(f, t)
    assert len(trades) == 0 and d[2] == 1
    assert d[0] == pytest.approx(-.4)
    assert d[15] == 95 and d[16] == 5


def test_limit_pending_cancels_at_center_even_for_fixed_rr():
    f, t = setup()
    f[2, :4] = [111, 112, 94, 100]
    trades, d = run(f, t, limit=True)
    assert len(trades) == 0 and d[11] == 1 and d[2] == 0


def test_limit_delayed_entry_uses_original_signal_atr():
    f, t = setup()
    f[2:, 7] = 100
    f[3, :4] = [100, 102, 93, 98]
    trades, _ = run(f, t, limit=True, stop=3)
    assert trades[0, 3] == 3
    assert trades[0, 5] == 97 and trades[0, 9] == 94
    assert trades[0, 11:13].tolist() == [3, 2]


@pytest.mark.parametrize('limit,stop,rr', [(l, s, r) for l in (False, True) for s in (1, 2, 3) for r in (0, 1.3, 1.5)])
def test_closed_trades_unchanged_by_future_suffix(limit, stop, rr):
    f, t = setup()
    f[2, :4] = [96, 120, 90, 100]
    full, _ = run(f, t, limit=limit, stop=stop, rr=rr)
    partial, _ = run(f[:5], t[:5], limit=limit, stop=stop, rr=rr)
    np.testing.assert_array_equal(partial, full[full[:, 4] < 5])


def test_finite_user_approved_scope():
    p = json.loads(SPEC.read_text(encoding='utf-8'))
    assert len(p['search_space']) == p['candidate_budget'] == 19
    assert len(p['symbols']) == 9
    assert p['exit_rules']['full_exit'] and not p['exit_rules']['partial_exit']
    assert 'User explicitly approved' in p['authorization']
