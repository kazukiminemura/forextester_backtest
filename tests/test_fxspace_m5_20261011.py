import numpy as np
from scripts import research_fxspace_m5_20261011 as m


def scenario_fixture(monkeypatch, higher_direction=1, reverse_at=None):
    """Supply already-warmed causal frame states; test only the new scenario layer."""
    class FixedFrame:
        def __init__(self, seconds, tick):
            self.seconds=seconds;self.trend=-1 if seconds==300 else higher_direction
            self.atr=2.
            self.highs=[dict(price=101.,known=0)]
            self.lows=[dict(price=99.,known=0)]
            self.lines=[dict(price=104.,known=0,strength=1)]
        def push(self,t,p,valid=True):
            if self.seconds==300:
                self.trend=(-1 if t<300 or (reverse_at is not None and t>=reverse_at) else 1)
            else:self.trend=higher_direction
        def acceleration(self,d):return 0
    monkeypatch.setattr(m.base,'Frame',FixedFrame)
    p=np.array([[100,101,99.9,100.5],[100.5,101.6,100.4,101.5],
                [101.5,101.6,100.8,101.],[101.,101.2,100.4,100.5],
                [100.5,101.8,100.4,101.6],[101.6,101.8,101.4,101.7]],float)
    t=np.arange(len(p))*300
    return dict(times=t,prices=p,complete=np.ones(len(p),bool),starts_at_open=np.ones(len(p),bool),observed_open_times=t.copy())


def test_main_requires_separate_pullback_bars_after_direct(monkeypatch):
    d=scenario_fixture(monkeypatch)
    s=m.signals(d,.01,0,1800)
    assert np.flatnonzero(s['sides'][1]).tolist()==[1]
    assert np.flatnonzero(s['sides'][0]).tolist()==[4]
    assert s['scenario_times'][0,4]==600
    assert s['targets'][0,4]==s['targets'][1,1]==103.8
    assert s['stops'][0,4]==s['stops'][1,1]==98.8


def test_context_off_keeps_solo_without_h1_condition(monkeypatch):
    d=scenario_fixture(monkeypatch,higher_direction=-1)
    s=m.signals(d,.01,0,1800)
    assert not np.any(s['sides'][:2])
    assert np.flatnonzero(s['sides'][2]).tolist()==[4]
    assert np.flatnonzero(s['sides'][3]).tolist()==[1]
    assert s['diagnostics'][0,8]==1


def test_touch_cancels_before_recovery_can_emit(monkeypatch):
    d=scenario_fixture(monkeypatch)
    d['prices'][4,2]=98.
    s=m.signals(d,.01,0,1800)
    assert not np.any(s['sides'][[0,2]])
    assert np.count_nonzero(s['sides'][[1,3]])==2


def test_gap_and_opposite_reversal_cancel(monkeypatch):
    d=scenario_fixture(monkeypatch,reverse_at=900)
    s=m.signals(d,.01,0,1800)
    assert not np.any(s['sides'][[0,2]])
    d=scenario_fixture(monkeypatch)
    d['complete'][3]=False
    s=m.signals(d,.01,0,1800)
    assert not np.any(s['sides'][[0,2]])


def test_phase_start_never_reuses_prior_reversal(monkeypatch):
    d=scenario_fixture(monkeypatch)
    s=m.signals(d,.01,600,1800)
    assert not np.any(s['sides'])


def test_same_support_cannot_reenter_after_another_reversal(monkeypatch):
    d=scenario_fixture(monkeypatch)
    frame=m.base.Frame
    class Repeat(frame):
        def push(self,t,p,valid=True):
            super().push(t,p,valid)
            if self.seconds==300 and t==600:self.trend=-1
    monkeypatch.setattr(m.base,'Frame',Repeat)
    s=m.signals(d,.01,0,1800)
    assert np.flatnonzero(s['sides'][3]).tolist()==[1]
    assert s['diagnostics'][1,7]==1


def test_expiry_allows_twelfth_but_not_thirteenth_bar(monkeypatch):
    d=scenario_fixture(monkeypatch)
    d['prices']=np.vstack((d['prices'][:2],np.tile([101.,101.2,100.8,101.1],(13,1))))
    t=np.arange(15)*300
    d.update(times=t,complete=np.ones(15,bool),starts_at_open=np.ones(15,bool),observed_open_times=t.copy())
    full=m.signals(d,.01,0,4500)
    prefix=m.signals({k:v[:14] for k,v in d.items()},.01,0,4200)
    assert prefix['diagnostics'][1,4]==0 and full['diagnostics'][1,4]==1


def test_new_signal_prefix_is_causal_with_nonzero_signals(monkeypatch):
    d=scenario_fixture(monkeypatch)
    full=m.signals(d,.01,0,1800)
    prefix=m.signals({k:v[:5] for k,v in d.items()},.01,0,1500)
    assert np.count_nonzero(prefix['sides'])==4
    for k in full:
        if k!='diagnostics':np.testing.assert_equal(full[k][:,:5],prefix[k])


def test_new_configuration_budget_and_execution_identity():
    assert len(m.ARMS)==4 and len(m.CONTROLS)==2
    assert m.simulate is m.base.simulate
