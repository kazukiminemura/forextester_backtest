import numpy as np
import pytest
from scripts import research_fxspace_proxy_20261011 as m


def bars(prices, times=None, complete=None):
    p=np.array(prices,float);n=len(p)
    t=np.arange(n,dtype=np.int64)*300 if times is None else np.array(times,np.int64)
    c=np.ones(n,bool) if complete is None else np.array(complete,bool)
    return dict(times=t,prices=p,complete=c,starts_at_open=np.ones(n,bool),observed_open_times=t.copy())


def emitted(data, side=1, stop=99., target=102., index=0):
    n=len(data['times'])
    s={key:np.zeros((2,n)) for key in ('stops','targets','thresholds','scenario_times','support_times','acceleration','strength','sides')}
    s['sides'][0,index]=side;s['stops'][0,index]=stop;s['targets'][0,index]=target
    return s


def test_resample_keeps_incomplete_bucket_and_ohlc():
    d=bars([[1,3,0,2],[2,4,1,3],[3,5,2,4],[4,6,3,5]],times=[0,300,600,1200])
    t,p,c=m.aggregate(d,900)
    np.testing.assert_array_equal(t,[0,900])
    np.testing.assert_array_equal(p,[[1,5,0,4],[4,6,3,5]])
    assert c.tolist()==[True,False]


def test_pivot_requires_two_future_bars_and_strict_ties():
    f=m.Frame(300,.01)
    for i,hi in enumerate([2,3,5,4]): f.push(i*300,[1,hi,0,1])
    assert not f.highs
    f.push(1200,[1,3,0,1])
    assert f.highs[-1]['origin']==600 and f.highs[-1]['known']==1500
    g=m.Frame(300,.01)
    for i,hi in enumerate([2,3,5,5,3]):g.push(i*300,[1,hi,0,1])
    assert not g.highs


def test_gap_does_not_form_pivot_across_missing_bar():
    f=m.Frame(300,.01)
    for t,hi in zip([0,300,600,1200,1500],[2,3,5,4,3]):f.push(t,[1,hi,0,1])
    assert not f.highs


def test_nearest_line_not_strongest_and_transitive_cluster_latest():
    a=[dict(price=101.,known=1,strength=1),dict(price=103.,known=2,strength=2)]
    assert m.nearest_obstacle(a,100.,1,.1)['price']==101.
    a=[dict(price=x,known=k,strength=1) for x,k in [(101.,1),(101.09,3),(101.18,2)]]
    assert m.nearest_obstacle(a,100.,1,.1)['price']==101.09


def test_counter_recovery_requires_sequence_and_first_recovery_is_final():
    counter,decision=m.counter_recovery(0,1,100,99,101,98)
    assert (counter,decision)==(1,None)
    assert m.counter_recovery(counter,1,99,102,101,98)==(0,None)
    counter,_=m.counter_recovery(counter,1,99,98,100,97)
    assert counter==2
    assert m.counter_recovery(counter,1,98,99,100,97)==(0,False)
    assert m.counter_recovery(counter,1,98,101,100,97)==(0,True)
    assert m.counter_recovery(counter,-1,101,98,102,99)==(0,True)


def test_rr_is_rechecked_at_actual_next_open_and_target_never_stretched():
    d=bars([[100,100.1,99.9,100],[101,103,100.5,102]])
    s=emitted(d,target=102.)
    rows,_,info=m.simulate(d,s,0,1.5,0,600,.01,.01)
    assert rows==[] and info['skipped']['insufficient_room']==1
    d['prices'][1]=[100,103,99.5,102]
    rows,_,_=m.simulate(d,s,0,1.5,0,600,.01,.01)
    assert rows[0]['target']==102. and rows[0]['planned_rr']==2.


def test_sl_first_and_cost_at_exit():
    d=bars([[100,100.1,99.9,100],[100,103,98,101]])
    rows,_,_=m.simulate(d,emitted(d),0,1.5,0,600,.1,.1)
    assert rows[0]['reason']=='sl'
    assert rows[0]['net_r']==pytest.approx(-1.1)


def test_no_gap_entry_or_before_phase_signal():
    d=bars([[100,100.1,99.9,100],[100,101,99.5,100]],times=[0,600])
    rows,_,info=m.simulate(d,emitted(d),0,1.5,0,900,.01,.01)
    assert not rows and info['skipped']['missing_entry']==1
    d=bars([[100,100.1,99.9,100],[100,103,99.5,102]])
    rows,_,_=m.simulate(d,emitted(d),0,1.5,300,600,.01,.01)
    assert not rows


def test_holding_gap_uses_observed_time_and_caps_positive_fill():
    d=bars([[100,100.1,99.9,100],[100,100.5,99.5,100],[105,106,104,105]],times=[0,300,1200])
    d['observed_open_times'][2]=1260;d['starts_at_open'][2]=False
    rows,_,_=m.simulate(d,emitted(d),0,1.5,0,1500,.01,.01)
    assert rows[0]['exit_price']==102 and rows[0]['exit_time']==1260
    d['prices'][2]=[95,96,94,95]
    rows,_,_=m.simulate(d,emitted(d),0,1.5,0,1500,.01,.01)
    assert rows[0]['exit_price']==95 and rows[0]['exit_time']==1260


def test_max_48_bars_and_daily_entry_block():
    d=bars([[100,100.1,99.9,100]]*52)
    rows,_,_=m.simulate(d,emitted(d),0,1.5,0,15600,.01,.01)
    assert rows[0]['reason']=='max_48_bars' and rows[0]['exit_time']==14700
    d=bars([[100,100.1,99.9,100]]*2,times=[85800,86100])
    rows,_,info=m.simulate(d,emitted(d),0,1.5,85800,86400,.01,.01)
    assert not rows and info['skipped']['daily_cutoff']==1


def test_incomplete_bar_keeps_observed_protection():
    d=bars([[100,100.1,99.9,100],[100,103,99.5,101]],complete=[True,False])
    rows,_,_=m.simulate(d,emitted(d),0,1.5,0,600,.01,.01)
    assert rows[0]['reason']=='tp' and rows[0]['incomplete_bars']==1


def test_cash_halts_without_reset_after_gap_below_floor():
    d=bars([[100,100.1,99.9,100],[100,100.5,99.5,100],[50,51,49,50],[100,103,99.5,102]],times=[0,300,1200,1500])
    s=emitted(d);s['sides'][0,2]=1;s['stops'][0,2]=99;s['targets'][0,2]=102
    rows,curve,info=m.simulate(d,s,0,1.5,0,1800,.01,.01,cash=True)
    assert len(rows)==1 and info['stopped'] and info['final_equity_yen']<900000
    assert curve[-1,1]==info['final_equity_yen']


def test_signal_prefix_unchanged_by_future_data():
    x=np.arange(900)
    close=100+.005*x+np.sin(x/8)+2*np.sin(x/65)
    d=bars(np.column_stack((close-.05,close+.12,close-.12,close)))
    full=m.signals(d,.001,9000,270000)
    short={key:value[:600] for key,value in d.items()}
    prefix=m.signals(short,.001,9000,180000)
    for key in full:
        if key!='diagnostics':np.testing.assert_equal(full[key][:,:600],prefix[key])
