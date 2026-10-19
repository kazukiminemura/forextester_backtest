from datetime import timedelta
from dataclasses import replace
import numpy as np
import pytest
from forextester_backtest.models import Bar
import research_bb3_mean_reversion as model


def test_bands_population_std_and_prefix():
    close=np.arange(50,dtype=float)
    mid,upper,lower=model.bands(close)
    assert np.isnan(mid[18])
    assert mid[19]==pytest.approx(9.5)
    assert upper[19]==pytest.approx(9.5+3*np.std(np.arange(20)))
    for a,b in zip(model.bands(close[:30]),(mid,upper,lower)):
        np.testing.assert_allclose(a,b[:30])


def fixture(monkeypatch,short=False):
    bars=[Bar(model.END-timedelta(minutes=5*(23-i)),100,100,100,100,1) for i in range(23)]
    bars[20]=replace(bars[20],open=97,high=97,low=96,close=96)
    bars[21]=replace(bars[21],open=96,high=100,low=95.8,close=99)
    if short:
        bars=[replace(b,open=200-b.open,high=200-b.low,low=200-b.high,close=200-b.close) for b in bars]
    monkeypatch.setattr(model,'bands',lambda c:(np.full(len(c),100.),np.full(len(c),103.),np.full(len(c),97.)))
    return bars


@pytest.mark.parametrize('short',[False,True])
def test_next_open_center_costs_and_stop_first(monkeypatch,short):
    bars=fixture(monkeypatch,short)
    rows,_=model.simulate(bars,.01,None)
    t=rows[0]; d=-1 if short else 1
    assert t['entry_time']==bars[21].time.isoformat()
    assert t['reason']=='center'
    assert t['exit']==pytest.approx(100+(.01 if short else 0)-d*.001)
    assert t['net_pips']==pytest.approx(d*(t['exit']-t['entry'])/.01)
    import json
    json.dumps(model.stats(rows),allow_nan=False)
    rows,_=model.simulate(bars,.01,5)
    assert rows[0]['reason']=='stop' and rows[0]['ambiguous']
    assert rows[0]['net_pips']==pytest.approx(-5.1)


def test_period_end_loss_not_discarded(monkeypatch):
    bars=fixture(monkeypatch)
    bars[21]=replace(bars[21],high=96.1,low=95.8,close=96)
    bars[22]=replace(bars[22],open=96,high=96,low=95,close=95)
    rows,_=model.simulate(bars,.01,None)
    assert len(rows)==1 and rows[0]['reason']=='period_end'
    assert rows[0]['net_pips']<0


def test_moving_center_can_exit_at_loss(monkeypatch):
    bars=fixture(monkeypatch)
    bars[21]=replace(bars[21],high=96.1,low=95.8,close=96)
    bars[22]=replace(bars[22],open=95.5,high=96,low=95,close=95.5)
    mid=np.full(23,100.); mid[21]=95.4
    monkeypatch.setattr(model,'bands',lambda c:(mid,np.full(23,103.),np.full(23,97.)))
    rows,_=model.simulate(bars,.01,None)
    assert rows[0]['reason']=='center_gap' and rows[0]['net_pips']<0
