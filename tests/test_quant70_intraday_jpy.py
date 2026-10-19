"""Guard the fixed JPY universe, unchanged rules, and selection boundary."""
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from verify_quant70_intraday_jpy import EXPECTED_SYMBOLS, EXPERIMENT, verify_protocol


def protocol():
    return json.loads((EXPERIMENT/'protocol.json').read_text(encoding='utf-8'))


def test_jpy_protocol_preserves_original_gates_and_execution():
    frozen = protocol()
    verify_protocol(frozen)
    assert frozen['symbols'] == EXPECTED_SYMBOLS
    assert frozen['gates']['min_positive_pairs'] == 3


@pytest.mark.parametrize('symbol', ['USDJPY', 'NZDJPY', 'EURUSD'])
def test_protocol_rejects_out_of_universe_or_insufficient_history(symbol):
    changed = protocol()
    changed['symbols'].append(symbol)
    with pytest.raises(AssertionError, match='JPY cross universe'):
        verify_protocol(changed)


@pytest.mark.parametrize('field,value', [
    ('net_win_rate_pct', 60), ('min_validation_trades', 100),
    ('min_positive_pairs', 2), ('profit_factor', 1.2),
])
def test_protocol_rejects_relaxed_gates(field, value):
    changed = protocol()
    changed['gates'][field] = value
    with pytest.raises(AssertionError, match='gate drift'):
        verify_protocol(changed)


@pytest.mark.parametrize('field,value', [
    ('reward_risk_ratio', 2), ('slippage_pips_each_side', 0), ('full_exit', False),
])
def test_protocol_rejects_execution_drift(field, value):
    changed = protocol()
    changed['execution'][field] = value
    with pytest.raises(AssertionError, match='execution drift'):
        verify_protocol(changed)


def test_jpy_runner_reuses_fixed_signal_and_execution_engines():
    import research_quant70_intraday as parent
    import research_quant70_intraday_jpy as runner
    for name in ('candidates', 'comparators', 'signals', 'daily_context',
                 'simulate', 'stats', 'quality', 'rejection_reasons', 'context_effect'):
        assert getattr(runner, name) is getattr(parent, name)


def data_for(times):
    n = len(times)
    c = np.full(n, 100.0)
    return SimpleNamespace(times=times, open=c.copy(), high=c+1, low=c-1,
                           close=c.copy(), atr=np.full(n, 1.0),
                           htf_trend=np.ones(n, dtype=np.int8),
                           minutes=np.asarray([t.minute for t in times]))


def test_jpy_runner_does_not_inspect_later_periods_when_candidates_fail(monkeypatch, tmp_path):
    import research_quant70_intraday_jpy as runner

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
    assert len(calls) == 4 and all(t < datetime(2023, 1, 1) for t in calls)
    controls = [r for r in result['records'] if not r['candidate'].get('selectable', False)]
    assert len(controls) == 13 and all(not any(r['rejections'].values()) for r in controls)
