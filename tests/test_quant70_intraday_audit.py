"""Independent causal and selection-boundary tests; no market-history reruns."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

from quant70_intraday_signals import candidates, comparators, daily_context, signals
from research_quant70_intraday import context_effect
from verify_quant70_intraday_results import improves


def data_for(times):
    n = len(times)
    c = np.full(n, 100.0)
    return SimpleNamespace(times=times, open=c.copy(), high=c+1, low=c-1,
                           close=c.copy(), atr=np.full(n, 1.0),
                           htf_trend=np.ones(n, dtype=np.int8),
                           minutes=np.asarray([t.minute for t in times]))


def full_days(n=23):
    return data_for([datetime(2020, 1, 1)+timedelta(minutes=15*i) for i in range(96*n)])


def cut(data, stop):
    return SimpleNamespace(**{k: v[:stop].copy() if isinstance(v, np.ndarray) else v[:stop]
                             for k, v in vars(data).items()})


def test_daily_high_low_include_only_observed_bars_and_reset_at_midnight():
    data = full_days(2)
    data.high[10], data.low[12] = 110, 90
    ctx = daily_context(data)
    assert ctx['day_high'][9] == 101
    assert ctx['day_high'][10] == 110
    assert ctx['day_low'][11] == 99
    assert ctx['day_low'][12] == 90
    assert ctx['day_high'][96] == 101 and ctx['day_low'][96] == 99
    assert ctx['previous_high'][96] == 110 and ctx['previous_low'][96] == 90
    assert np.isnan(ctx['previous_high'][:96]).all()


def test_adr_uses_twenty_completed_days_and_never_today():
    data = full_days(23)
    for day in range(23):
        data.high[day*96:(day+1)*96] = 101+day
    ctx = daily_context(data)
    assert np.isnan(ctx['adr20'][:20*96]).all()
    assert np.all(ctx['adr20'][20*96:21*96] == np.mean(np.arange(2, 22)))
    assert ctx['adr20'][21*96] == np.mean(np.arange(3, 23))
    changed = deepcopy(data)
    changed.high[20*96+95] = 999
    ctx_changed = daily_context(changed)
    np.testing.assert_equal(ctx_changed['adr20'][:21*96], ctx['adr20'][:21*96])
    assert ctx_changed['adr20'][21*96] != ctx['adr20'][21*96]


def test_previous_day_does_not_bridge_weekends_or_incomplete_dates():
    friday = datetime(2020, 1, 3)
    monday = datetime(2020, 1, 6)
    times = [friday+timedelta(minutes=15*i) for i in range(96)]
    times += [monday+timedelta(minutes=15*i) for i in range(96)]
    data = data_for(times)
    assert np.isnan(daily_context(data)['previous_high'][96:]).all()
    data = full_days(3)
    keep = np.arange(len(data.times)) != 96+30
    data = SimpleNamespace(**{k: v[keep] if isinstance(v, np.ndarray) else [t for t, use in zip(v, keep) if use]
                              for k, v in vars(data).items()})
    ctx = daily_context(data)
    assert ctx['valid_day'][96+29]
    assert not ctx['valid_day'][96+30:191].any()
    assert ctx['valid_day'][191:].all()
    assert np.isnan(ctx['previous_high'][191:]).all()


def test_incomplete_days_are_excluded_from_adr_count():
    data = full_days(22)
    keep = np.arange(len(data.times)) != 8*96+33
    data = SimpleNamespace(**{k: v[keep] if isinstance(v, np.ndarray) else [t for t, use in zip(v, keep) if use]
                              for k, v in vars(data).items()})
    ctx = daily_context(data)
    assert np.isnan(ctx['adr20'][20*96-1])
    assert ctx['adr20'][21*96-1] == 2


def test_opening_range_is_hidden_until_four_and_resets_next_date():
    data = full_days(2)
    data.high[15], data.low[15] = 108, 92
    data.high[16] = 140
    ctx = daily_context(data)
    assert np.isnan(ctx['opening_high'][:16]).all()
    assert ctx['opening_high'][16] == 108 and ctx['opening_low'][16] == 92
    assert ctx['opening_high'][95] == 108
    assert np.isnan(ctx['opening_high'][96:112]).all()
    assert ctx['opening_high'][112] == 101


@pytest.mark.parametrize('stop', [20*96, 20*96+1, 20*96+16, 20*96+17, 21*96, 21*96+45])
def test_appending_future_does_not_change_any_context_or_signal(stop):
    data = full_days(23)
    rng = np.random.default_rng(90171)
    data.close[:] += rng.normal(0, 0.5, len(data.times))
    data.high[:] = np.maximum(data.open, data.close)+0.2
    data.low[:] = np.minimum(data.open, data.close)-0.2
    for day in range(20):
        data.high[day*96+40] = 105
        data.low[day*96+50] = 95
    data.close[20*96:] += 3
    data.open[20*96:] = data.close[20*96:]-0.1
    data.high[20*96:] = data.close[20*96:]+0.2
    data.low[20*96:] = data.close[20*96:]-0.3
    shorter = cut(data, stop)
    data.ema_cache = {}
    shorter.ema_cache = {}
    for field, values in daily_context(shorter).items():
        np.testing.assert_equal(values, daily_context(data)[field][:stop], err_msg=field)
    observed = 0
    for spec in candidates()+comparators():
        all_signals = signals(data, spec)
        observed += np.count_nonzero(all_signals)
        np.testing.assert_equal(signals(shorter, spec), all_signals[:stop], err_msg=spec['name'])
    assert observed > 0, 'causal check must include nonempty signals'


@pytest.mark.parametrize('candidate,control,expected', [
    ((70, .1), (69, .09), True), ((70, .1), (70, .09), False),
    ((70, .1), (69, .1), False), ((70, .1), (71, .09), False),
    ((70, .1), (69, .2), False), ((70, None), (69, .1), False),
    ((70, .1), (69, None), False), ((70, None), (69, None), False),
])
def test_comparison_gate_requires_both_strict_improvements(candidate, control, expected):
    a = dict(zip(('net_win_rate_pct', 'expectancy_r'), candidate))
    b = dict(zip(('net_win_rate_pct', 'expectancy_r'), control))
    assert context_effect(a, b)['passes'] is expected
    assert improves(a, b) is expected


def test_runner_cannot_select_passing_comparators_when_candidates_fail_effect(monkeypatch, tmp_path):
    import research_quant70_intraday as runner

    @dataclass
    class Metadata:
        commission_per_lot: float = 0.0

    class Repository:
        def __init__(self, *args):
            pass

        def metadata(self, symbol):
            return Metadata()

    prepared = data_for([datetime(2010, 1, 1), datetime(2018, 12, 31),
                         datetime(2019, 1, 1), datetime(2022, 12, 31)])
    calls = []

    def prepare(repository, symbol, end, timeframe):
        calls.append(end)
        return prepared

    summary = {'net_win_rate_pct': 80, 'expectancy_r': .6, 'profit_factor': 4,
               'wilson_95_lower_pct': 75, 'trades': 1000}
    monkeypatch.setattr(runner, 'HistoryRepository', Repository)
    monkeypatch.setattr(runner, '_prepare', prepare)
    monkeypatch.setattr(runner, 'quality', lambda *args: {})
    monkeypatch.setattr(runner, 'signals', lambda data, spec, **kwargs: np.zeros(4))
    monkeypatch.setattr(runner, 'simulate', lambda *args: [])
    monkeypatch.setattr(runner, 'stats', lambda *args: summary.copy())
    monkeypatch.setattr(runner, 'rejection_reasons', lambda *args: [])
    output = tmp_path/'run'
    monkeypatch.setattr(sys, 'argv', ['runner', '--output', str(output)])
    assert runner.main() == 0
    import json
    result = json.loads((output/'results.json').read_text(encoding='utf-8'))
    assert result['qualified_count'] == 0 and result['selected'] is None
    assert not result['confirmation_evaluated']
    assert len(calls) == 11 and all(t < datetime(2023, 1, 1) for t in calls)
    controls = [r for r in result['records'] if not r['candidate'].get('selectable', False)]
    assert len(controls) == 13 and all(not any(r['rejections'].values()) for r in controls)
