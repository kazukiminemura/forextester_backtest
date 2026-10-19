"""Causal boundary checks for favorable limit order timing."""
import json

import numpy as np
import pytest

from scripts.research_bb3_context_retest import SPEC, simulate_limit


def setup():
    f = np.zeros((8, 15))
    f[:, :10] = [100, 103, 99, 101, 110, 125, 95, 2, 105, 90]
    f[0, :4] = [98, 100, 94, 98]
    f[1, :4] = [98, 100, 96, 99]  # signal close99 -> limit98 at k=.5
    return f, np.arange(8, dtype=np.int64) * 300


def run(f, t, fraction=.5, ttl=3, tick=.001):
    return simulate_limit(f, t, 0, 2400, 1., 1.4, fraction, ttl, tick)


def test_limit_cannot_fill_on_signal_bar():
    f, t = setup()
    trades, d = run(f, t)
    assert len(trades) == 0 and d[2] == 0 and d[7] == 1
    assert d[11] == 1  # expires without fill despite signal low96


def test_gap_improved_entry_allows_samebar_target():
    f, t = setup()
    f[2, :4] = [97, 112, 96, 111]
    trades, d = run(f, t)
    assert trades[0, 3:8].tolist() == [2, 2, 97, 110, 110]
    assert trades[0, 8] == pytest.approx(11.6)
    assert d[12] == 1 and d[10] == 0


def test_intrabar_limit_target_ambiguity_does_not_book_samebar_exit():
    f, t = setup()
    f[2, :4] = [100, 112, 97, 100]
    f[2, 4] = 109  # affects next bar only
    f[3, :4] = [100, 111, 99, 108]
    trades, d = run(f, t)
    assert trades[0, 3:8].tolist() == [2, 3, 98, 109, 109]
    assert d[10] == 1 and d[13] == 1


def test_open_target_cancels_before_intrabar_limit_touch():
    f, t = setup()
    f[2, :4] = [111, 112, 97, 100]
    trades, d = run(f, t)
    assert len(trades) == 0 and d[2] == 0 and d[11] == 1


def test_current_bar_cancellation_never_erases_earlier_limit_fill():
    f, t = setup()
    f[2, :4] = [100, 103, 97, 101]
    f[2, 12] = 1
    _, d = run(f, t)
    assert d[2] == 1 and d[11] == 0


def test_close_cancellation_applies_before_future_bar_fill():
    f, t = setup()
    f[2, 10] = 1
    f[3, :4] = [100, 103, 97, 101]
    _, d = run(f, t)
    assert d[2] == 0 and d[11] == 1


def test_ttl_last_bar_is_still_live():
    f, t = setup()
    f[3, :4] = [100, 103, 97, 101]
    _, d2 = run(f, t, ttl=2)
    assert d2[2] == 1
    f[3, 2] = 99
    f[4, 2] = 97
    _, d2 = run(f, t, ttl=2)
    _, d3 = run(f, t, ttl=3)
    assert d2[2] == 0 and d3[2] == 1


def test_limit_rounding_is_away_from_market_both_sides():
    f, t = setup()
    f[1, 7] = 1.7  # raw98.15 -> tick.1 ->98.1
    f[2, :4] = [100, 103, 98.12, 101]
    _, d = run(f, t, tick=.1)
    assert d[2] == 0
    f[2, 2] = 98.09
    _, d = run(f, t, tick=.1)
    assert d[3] == pytest.approx(98.1)
    g = f.copy()
    for a, b in ((0, 0), (1, 2), (2, 1), (3, 3), (4, 4), (5, 6), (6, 5), (8, 9), (9, 8)):
        g[:, a] = 400 - f[:, b]
    _, d = run(g, t, tick=.1)
    assert d[2] == -1 and d[3] == pytest.approx(301.9)


def test_finite_frozen_space():
    p = json.loads(SPEC.read_text(encoding='utf-8'))
    assert len(p['search_space']) == p['candidate_budget'] == 7
    assert len(p['symbols']) == 9
    assert 'floor' in p['price_quantization'] and 'ceil' in p['price_quantization']
