from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from quant70_signals import candidates, signals  # noqa: E402
from research_strict_rr_portfolio import _atr  # noqa: E402


def prepared(close=None):
    close = np.full(260, 100.0) if close is None else np.asarray(close, dtype=float)
    high, low = close + 0.5, close - 0.5
    atr = _atr(high, low, close)
    return SimpleNamespace(
        close=close, open=close.copy(), high=high, low=low, atr=atr,
        htf_trend=np.ones(close.size, dtype=np.int8),
        ema_cache={}, atr_cache={14: atr}, roll_cache={},
    )


def candidate_for(family):
    return next(row for row in candidates() if row["family"] == family)


def test_search_space_is_fixed_unique_and_rr_one_stop_spec():
    rows = candidates()
    assert len(rows) == len({row["name"] for row in rows}) == 24
    for family in ("ema_reclaim", "range_sweep", "compression_expansion"):
        assert sum(row["family"] == family for row in rows) == 8
    assert all(row["stop_atr"] == 2.0 and row["timeframe"] == "15m" for row in rows)
    rows[0]["stop_atr"] = 999
    assert candidates()[0]["stop_atr"] == 2.0


def test_sweep_uses_previous_range_and_requires_confirmed_direction():
    data = prepared()
    data.low[240] = 98.0
    data.close[240] = 100.3
    candidate = candidate_for("range_sweep")
    assert signals(data, candidate)[240] == 1
    for state in (0, -1):
        data.htf_trend[240] = state
        assert signals(data, candidate)[240] == 0
    data.htf_trend[240] = 1
    data.close[240] = 100.6  # Beyond the prior upper bound is not a reclaim.
    assert signals(data, candidate)[240] == 0


def test_sweep_short_is_price_mirror_of_long():
    data = prepared()
    data.low[240], data.close[240] = 98.0, 100.3
    mirrored = deepcopy(data)
    mirrored.high, mirrored.low = 200 - data.low, 200 - data.high
    mirrored.close, mirrored.open = 200 - data.close, 200 - data.open
    mirrored.htf_trend *= -1
    candidate = candidate_for("range_sweep")
    np.testing.assert_array_equal(signals(mirrored, candidate), -signals(data, candidate))


def test_ema_reclaim_waits_for_close_recross():
    data = prepared(100 + np.arange(260) * 0.03)
    data.close[239] -= 0.7
    data.low[238:240] -= 0.8
    candidate = candidate_for("ema_reclaim")
    result = signals(data, candidate)
    assert result[239] == 0
    assert result[240] == 1


def test_compression_is_previous_bar_and_expansion_is_current_bar():
    data = prepared()
    data.atr[:] = 0.6
    data.atr_cache[56] = np.ones(260)
    data.high[240], data.close[240] = 103.0, 102.0
    data.atr[240] = 1.5  # Current expansion need not still be compressed.
    candidate = candidate_for("compression_expansion")
    assert signals(data, candidate)[240] == 1
    data.atr[239] = 0.8
    assert signals(data, candidate)[240] == 0


def test_warmup_zero_range_and_invalid_atr_are_not_signals():
    data = prepared()
    data.low[200], data.close[200] = 98.0, 100.3
    candidate = candidate_for("range_sweep")
    assert not signals(data, candidate)[:208].any()
    data.high[240] = data.low[240] = data.close[240] = 100
    assert signals(data, candidate)[240] == 0
    data.low[250], data.close[250] = 98.0, 100.3
    for invalid in (np.nan, 0.0, -1.0):
        data.atr[250] = invalid
        assert signals(data, candidate)[250] == 0


def test_all_candidates_are_invariant_to_appended_future_bars():
    rng = np.random.default_rng(20260908)
    close = 100 + np.cumsum(rng.normal(0, 0.20, 900))
    full = prepared(close)
    short = prepared(close[:600])
    observed = 0
    for candidate in candidates():
        full_result = signals(full, candidate)
        np.testing.assert_array_equal(signals(short, candidate), full_result[:600])
        observed += np.count_nonzero(full_result)
    assert observed > 0  # The causal check must not pass only on empty signals.


def test_invalid_spec_and_unknown_family_fail_explicitly():
    candidate = candidate_for("range_sweep")
    with pytest.raises(ValueError, match="15m"):
        signals(prepared(), {**candidate, "timeframe": "5m"})
    with pytest.raises(ValueError, match="Unknown"):
        signals(prepared(), {**candidate, "family": "unknown"})
