from types import SimpleNamespace
import numpy as np
from simple_rr_signals import candidates,signals


def data(n=400):
    rng=np.random.default_rng(42); c=100+np.cumsum(rng.normal(0,.25,400))
    return SimpleNamespace(close=c[:n],high=c[:n]+.02,low=c[:n]-.02,
        atr=np.ones(n)*.2,htf_trend=np.ones(n),ema_cache={},roll_cache={})


def test_budget():
    c=candidates()
    assert len(c)==18 and len({p['name'] for p in c})==18
    assert {p['reward_risk'] for p in c}=={1.3,1.4,1.5}


def test_simple_signals_causal_and_rr_independent():
    count=0
    for spec in [p for p in candidates() if p['family']!='compression_expansion']:
        full=signals(data(),spec); count+=np.count_nonzero(full)
        np.testing.assert_array_equal(signals(data(300),spec),full[:300])
        changed=data(); changed.close[300:]+=100
        np.testing.assert_array_equal(signals(changed,spec)[:300],full[:300])
        np.testing.assert_array_equal(signals(data(),{**spec,'reward_risk':9}),full)
        assert not np.any(full[:208]) and not np.any(full==-1)
    assert count>0


def test_short_rules_are_mirrored_long_rules():
    for spec in [p for p in candidates() if p['family']!='compression_expansion']:
        long_data=data(); short_data=data()
        short_data.close=200-long_data.close
        short_data.high=200-long_data.low
        short_data.low=200-long_data.high
        short_data.htf_trend=-long_data.htf_trend
        np.testing.assert_array_equal(signals(short_data,spec),-signals(long_data,spec))
