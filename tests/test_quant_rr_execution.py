from datetime import datetime,timedelta
from types import SimpleNamespace
import numpy as np
import pytest
from quant_rr_execution import simulate
from research_quant70 import simulate as original


@pytest.mark.parametrize('seed',range(10))
def test_rr_one_matches_frozen_engine(seed):
    rng=np.random.default_rng(seed); n=300
    prices=100+np.cumsum(rng.normal(0,.2,n))
    data=SimpleNamespace(times=[datetime(2024,1,1)+timedelta(minutes=15*i) for i in range(n)],
                         open=prices,close=prices+rng.normal(0,.03,n),high=prices+.4,low=prices-.4,
                         atr=np.full(n,.15),spread=.014)
    directions=rng.choice([-1,0,1],n)
    args=(data,directions,'AUDJPY',data.times[0],data.times[-1]+timedelta(minutes=15),.01)
    assert simulate(*args,reward_risk=1)==original(*args)
    for t in simulate(*args):
        assert abs(t.target-t.entry)==pytest.approx(1.5*abs(t.entry-t.stop))


@pytest.mark.parametrize('direction',[1,-1])
def test_target_is_replayed_not_scaled_profit(direction):
    data=SimpleNamespace(times=[datetime(2024,1,1)+timedelta(minutes=15*i) for i in range(3)],
        open=np.array([100.,100.,100.]),close=np.array([100.,100.,100.]),
        high=np.array([100.,102.1,100.]),low=np.array([100.,99.9,97.9]) if direction==1 else np.array([100.,97.9,100.]),
        atr=np.ones(3),spread=0.)
    if direction==-1: data.high=np.array([100.,100.1,102.1])
    args=(data,np.array([direction,0,0]),'AUDJPY',data.times[0],datetime(2024,1,2),.01)
    assert simulate(*args,slip_pips=0,reward_risk=1)[0].reason=='target'
    assert simulate(*args,slip_pips=0,reward_risk=1.5)[0].reason=='stop'


@pytest.mark.parametrize('ratio',[0,-1,float('nan'),float('inf')])
def test_invalid_ratio(ratio):
    with pytest.raises(ValueError): simulate(None,None,None,None,None,None,reward_risk=ratio)
