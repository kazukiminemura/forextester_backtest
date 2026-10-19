import numpy as np

from scripts.research_bb_night_rr1 import (book_bounds, execution_signals, h1_direction,
    in_night, night_coverage, night_metrics, prior_efficiency, research_gates, summarize_fills)
from scripts.research_bb3_jev_engine import simulate


def fixture(n=400):
    start=int(np.datetime64("2020-01-06T00:00","s").astype(int))
    times=start+np.arange(n)*300
    f=np.zeros((n,15)); f[:,:8]=[100,100.2,99.8,100,100,103,97,1]
    return f,times


def test_efficiency_excludes_origin_and_rejects_prior_gap():
    f,t=fixture(30)
    f[:,3]=np.arange(30)
    assert prior_efficiency(f[:,3],t)[13]==1
    f[13,3]=-1000
    assert prior_efficiency(f[:,3],t)[13]==1
    t[10:]+=300
    assert np.isnan(prior_efficiency(f[:,3],t)[13])
    assert prior_efficiency(np.ones(30),fixture(30)[1])[13]==0


def test_h1_requires_completed_hour_and_no_invalid_hour_backfill():
    f,t=fixture(27*12)
    f[:,3]=100+np.arange(len(f))/12
    direction,_=h1_direction(f,t)
    assert direction[25*12-2]==0
    assert direction[25*12-1]==1
    np.testing.assert_array_equal(h1_direction(f[:301],t[:301])[0],direction[:301])
    keep=np.arange(len(f))!=25*12+4
    damaged,_=h1_direction(f[keep],t[keep])
    assert damaged[np.searchsorted(t[keep],t[26*12-1])]==0
    assert len(h1_direction(f[:2],t[:2])[0])==2


def test_clock_entry_boundaries_and_period_shift():
    start=int(np.datetime64("2020-01-06T10:00","s").astype(int))
    np.testing.assert_array_equal(in_night(np.array([start-300,start,start+5*3600-300,start+5*3600]),0),[False,True,True,False])
    assert not in_night(start,2)
    a,b=book_bounds((2020,2023),0)
    assert np.datetime64(a,"s")==np.datetime64("2019-12-31T15:00")
    assert np.datetime64(b,"s")==np.datetime64("2022-12-31T15:00")


def test_execution_prices_atr_bracket_without_changing_signal():
    f,t=fixture(400)
    i=119  # 09:55 source, next entry19:00 assumedJST
    signal=dict(index=i,origin=i,side=1,risk_price=.05)
    original=signal.copy()
    orders=execution_signals([signal],f,t,t[0],t[-1]+300,0)
    assert len(orders)==1 and orders[0]["target"]==100.05
    assert signal==original and "target" not in signal
    f[i+1,0]=101
    assert execution_signals([signal],f,t,t[0],t[-1]+300,0)[0]["target"]==101.05
    signal["index"]=179  #14:55source next midnightJST
    assert execution_signals([signal],f,t,t[0],t[-1]+300,0)==[]


def test_coverage_zero_nights_partial_nights_and_dedup():
    _,t=fixture(3*288)
    complete=np.ones(len(t),dtype=bool)
    data={"a":dict(times=t,complete=complete),"b":dict(times=t,complete=complete)}
    coverage=night_coverage(data,(2020,2021),0)
    assert coverage["complete"].sum()==3
    entry=int(t[120])
    fills=[dict(entry_time=entry,exit_time=entry+300,exit_reason="target")]*2
    result=night_metrics(fills,coverage,0)
    assert result["primary"]["mean"]==2/3
    np.testing.assert_allclose(result["primary"]["zero_pct"],100*2/3)
    assert result["deduplicated"]["mean"]==1/3
    assert result["simultaneous_duplicate_entries"]==1
    data["b"]=dict(times=np.delete(t,121),complete=np.delete(complete,121))
    changed=night_metrics(fills,night_coverage(data,(2020,2021),0),0)
    assert changed["entries_on_complete_nights"]==0 and changed["entries_on_incomplete_nights"]==2


def test_midnight_gap_known_intrabar_uncertain_and_open_censored():
    _,t=fixture(288)
    data={"a":dict(times=t,complete=np.ones(len(t),dtype=bool))}
    entry=int(t[120]); midnight=int(t[180])
    fills=[dict(entry_time=entry,exit_time=midnight,exit_reason="gap_stop"),
           dict(entry_time=entry,exit_time=midnight,exit_reason="target"),
           dict(entry_time=entry,exit_time=midnight+300,exit_reason="stop"),
           dict(entry_time=entry,mark_time=midnight)]
    result=night_metrics(fills,night_coverage(data,(2020,2021),0),0)
    assert result["midnight_gap_exits"]==1
    assert result["strict_midnight_carry"]==1 and result["possible_midnight_carry"]==2
    assert result["midnight_right_censored"]==1


def test_fill_reconstruction_preserves_final_open_and_cost():
    f,t=fixture(40)
    signals=[dict(index=0,origin=0,side=1,target=104.)]
    sim=simulate(f,t,1.,.01,signals,start=t[0],end=t[-1]+300,cost_pips=1.)
    summary,fills,opened=summarize_fills(f,t,signals,sim,1.,t[0],t[-1]+300,1.)
    assert summary["entries"]==1 and opened["entry_index"]==1
    assert summary["cost_r"]==.25 and summary["gross_r"]==0
    assert len(fills)==1


def test_final_cache_signal_has_no_invented_nextopen():
    f,t=fixture(20)
    signals=[dict(index=19,origin=19,side=1,risk_price=.05)]
    assert execution_signals(signals,f,t,t[0],t[-1]+300,None)==[]


def test_frequency_screen_cannot_pass_on_few_complete_nights():
    base=dict(frequency=dict(primary=dict(mean=3,zero_pct=0,two_plus_pct=100),m5_complete_nights=99,weekday_nights=200),
        profit_factor_r=2,net_plus_open_r=10,positive_pairs=7,trades=300)
    gates=research_gates(base,dict(net_plus_open_r=5))
    assert not gates["coverage_nights"] and not gates["coverage_fraction"]


def test_fees_do_not_change_rr1_path_and_closed_cost_is_once():
    f,t=fixture(40)
    f[2,1]=105
    signals=[dict(index=0,origin=0,side=1,target=104.)]
    outputs=[simulate(f,t,1.,.01,signals,start=t[0],end=t[-1]+300,cost_pips=c) for c in (1.,1.2)]
    assert outputs[0]["trades"][0]["entry"]==outputs[1]["trades"][0]["entry"]
    assert outputs[0]["trades"][0]["exit"]==outputs[1]["trades"][0]["exit"]
    np.testing.assert_allclose(outputs[0]["trades"][0]["net_r"]-outputs[1]["trades"][0]["net_r"],.2/4)
