from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from quant70_intraday_signals import candidates, comparators, daily_context, signals, _retest


START = 21 * 96


def prepared():
    n = 22 * 96
    close = np.full(n, 100.0)
    high, low = np.full(n, 105.0), np.full(n, 95.0)
    high[START:], low[START:] = 100.1, 99.9
    return SimpleNamespace(times=[datetime(2025, 1, 1) + timedelta(minutes=15*i) for i in range(n)],
                           open=close.copy(), close=close, high=high, low=low,
                           atr=np.ones(n), htf_trend=np.ones(n, np.int8), ema_cache={})


def subset(data, indices):
    result = deepcopy(data)
    result.times = [data.times[i] for i in indices]
    for key in ("open", "high", "low", "close", "atr", "htf_trend"):
        setattr(result, key, getattr(data, key)[indices])
    result.ema_cache = {}
    return result


def example(family):
    data = prepared()
    if family == "day_pullback":
        data.close[START+1:] = data.open[START+1:] = 103.0
        data.high[START+1:], data.low[START+1:] = 103.1, 102.9
        data.close[START+39], data.low[START+39] = 102.0, 101.9
        data.open[START+40] = 102.0
        data.low[START+40] = 101.9
        point = START + 40
    elif family == "previous_day_failed_break":
        point = START + 40
        data.open[point], data.high[point], data.low[point], data.close[point] = 95.1, 95.6, 94.8, 95.5
    else:
        data.high[START:START+16], data.low[START:START+16] = 100.5, 99.5
        point = START + 17
        data.open[point-1], data.high[point-1], data.low[point-1], data.close[point-1] = 100, 101.3, 99.9, 101.2
        data.open[point], data.high[point], data.low[point], data.close[point] = 100.6, 101, 100.4, 100.9
    spec = next(c for c in candidates() if c["family"] == family)
    return data, spec, point


def test_fixed_budget_pairing_and_comparator_exclusion():
    rows, controls = candidates(), comparators()
    assert len(rows) == len(controls) == 12
    assert len({c["name"] for c in rows + controls}) == 24
    assert all(c["timeframe"] == "15m" and c["stop_atr"] == 2 for c in rows + controls)
    assert all(c["selectable"] for c in rows)
    assert all(not c["selectable"] and c["comparison_of"] == r["name"] for c, r in zip(controls, rows))
    assert all(sum(c["family"] == f for c in rows) == 4 for f in {c["family"] for c in rows})


@pytest.mark.parametrize("family", ["day_pullback", "previous_day_failed_break", "opening_range_retest"])
def test_each_family_positive_example_htf_filter_and_price_mirror(family):
    data, spec, point = example(family)
    result = signals(data, spec)
    assert result.dtype == np.int8
    assert result[point] == 1
    mirrored = deepcopy(data)
    mirrored.high, mirrored.low = 200-data.low, 200-data.high
    mirrored.open, mirrored.close = 200-data.open, 200-data.close
    mirrored.htf_trend *= -1
    mirrored.ema_cache = {}
    np.testing.assert_array_equal(signals(mirrored, spec), -result)
    for state in (0, -1):
        data.htf_trend[point] = state
        assert signals(data, spec)[point] == 0


def test_prefix_and_changed_future_same_day_are_invariant_with_actual_signals():
    observed = 0
    for family in {row["family"] for row in candidates()}:
        data, _, point = example(family)
        prefix = subset(data, np.arange(point + 1))
        changed = deepcopy(data)
        changed.close[point+1:] += 20
        changed.open[point+1:] += 20
        changed.high[point+1:] += 20
        changed.low[point+1:] -= 20
        for spec in [c for c in candidates()+comparators() if c["family"] == family]:
            full_signal = signals(data, spec)
            observed += np.count_nonzero(full_signal)
            np.testing.assert_array_equal(signals(prefix, spec), full_signal[:point+1])
            np.testing.assert_array_equal(signals(changed, spec)[:point+1], full_signal[:point+1])
    assert observed > 0


def test_daily_levels_reset_complete_prior_calendar_only_and_exclude_current_adr():
    data = prepared()
    data.high[START+30] = 200
    ctx = daily_context(data)
    assert np.isnan(ctx["adr20"][20*96-1])
    assert ctx["adr20"][20*96] == 10
    assert ctx["adr20"][START+30] == 10
    assert ctx["day_high"][START+29] == 100.1
    assert ctx["day_high"][START+30] == 200
    assert ctx["previous_high"][START] == 105
    # A full missing calendar day cannot be replaced by the last observed day.
    dropped = subset(data, np.r_[np.arange(20*96), np.arange(START, len(data.times))])
    assert np.isnan(daily_context(dropped)["previous_high"][-1])
    # An incomplete previous day also cannot contribute daily levels.
    dropped = subset(data, np.delete(np.arange(len(data.times)), START-10))
    assert np.isnan(daily_context(dropped)["previous_high"][-1])


def test_missing_midnight_and_intraday_gap_are_conservative_without_past_rewrite():
    data, spec, point = example("previous_day_failed_break")
    missing_open = subset(data, np.delete(np.arange(len(data.times)), START))
    assert not signals(missing_open, spec)[START:].any()
    missing_later = subset(data, np.delete(np.arange(len(data.times)), point+1))
    assert signals(missing_later, spec)[point] == 1
    assert not daily_context(missing_later)["valid_day"][point+1:].any()
    data.high[point+1] = np.nan
    ctx = daily_context(data)
    assert ctx["valid_day"][point]
    assert not ctx["valid_day"][point+1:].any()


def test_opening_levels_available_after_completion_and_retest_not_breakout_bar():
    data, spec, point = example("opening_range_retest")
    ctx = daily_context(data)
    assert np.isnan(ctx["opening_high"][START+15])
    assert ctx["opening_high"][START+16] == 100.5
    assert signals(data, spec)[point-1] == 0
    assert signals(data, spec)[point] == 1
    # Breakout cannot carry its pending state into another source date.
    ctx["day_id"][point:] += 1
    assert not _retest(data, ctx, 0)[0][point]
    # A close back inside invalidates that breakout before a later retest.
    data.close[point], data.low[point] = 100.4, 100.3
    data.open[point+1], data.high[point+1], data.low[point+1], data.close[point+1] = 100.6, 101, 100.4, 100.9
    assert signals(data, spec)[point+1] == 0


def test_ablation_removes_day_state_but_preserves_trigger_and_data_gates():
    data, spec, point = example("previous_day_failed_break")
    control = next(c for c in comparators() if c["comparison_of"] == spec["name"])
    data.high[START+20] = 104  # Uses more than 70% ADR by the sweep bar.
    assert signals(data, spec)[point] == 0
    assert signals(data, control)[point] == 1
    data.atr[point] = 0
    assert signals(data, control)[point] == 0


def test_explicit_context_matches_and_invalid_spec_or_timestamps_fail():
    data, spec, _ = example("day_pullback")
    np.testing.assert_array_equal(signals(data, spec), signals(data, spec, daily_context(data)))
    with pytest.raises(ValueError, match="15m"):
        signals(data, {**spec, "timeframe": "5m"})
    with pytest.raises(ValueError, match="Unknown"):
        signals(data, {**spec, "family": "missing"})
    data.times[-1] = data.times[-2]
    with pytest.raises(ValueError, match="increasing"):
        daily_context(data)
