import json
import numpy as np
import pytest

from scripts.research_holy_grail_first_pullback import (
    DailyData, aggregate, indicators, generate_setups, entry_fill, exit_fill,
    simulate, timestamp, baseline_gate, SPEC,
)


def fixture():
    bars = np.array([[11, 12, 11, 11.5], [12, 13, 11, 12], [11, 12, 9, 11],
                     [11, 12, 11, 11.5], [11, 12, 9, 11], [11, 12, 11, 11.5],
                     [11, 12, 9, 11], [11, 12, 11, 11.5]], dtype=float)
    f = {"ema": np.full(8, 10.), "adx": np.array([29,31,32,32,32,32,32,32.]),
         "plus": np.full(8, 40.), "minus": np.full(8, 10.)}
    return bars, f


def test_first_touch_consumed_and_repeated_baseline():
    bars, f = fixture()
    first, _, events = generate_setups(bars, f, 0, 8, True, .1, 1)
    repeat, _, _ = generate_setups(bars, f, 0, 8, False, .1, 1)
    assert list(first)==[2]
    assert list(repeat)==[2,4,6]
    assert sum(x["event"]=="first_touch_consumed" for x in events)==1


def test_invalid_first_touch_cannot_be_replaced():
    bars, f = fixture()
    bars[2,3] = 9.5
    setups, _, _ = generate_setups(bars, f, 0, 8, True, .1, 1)
    assert not setups


def test_continuous_contact_is_not_repeat_signal():
    bars, f = fixture()
    bars[3] = [11,12,9,11]
    setups, _, _ = generate_setups(bars, f, 0, 8, False, .1, 1)
    assert 3 not in setups and 4 not in setups


def test_arm_bar_cannot_signal_and_no_prior_episode_at_phase_start():
    bars, f = fixture()
    bars[1,2]=9
    setups, _, _ = generate_setups(bars, f, 0, 8, True, .1, 1)
    assert 1 not in setups
    setups, _, _ = generate_setups(bars, f, 3, 8, True, .1, 1)
    assert not setups


def test_reset_and_new_cross_required():
    bars, f = fixture()
    f["adx"][3:6] = [24,29,31]
    setups, resets, _ = generate_setups(bars, f, 0, 8, True, .1, 1)
    assert resets=={3} and list(setups)==[2,6]


def test_di_tie_resets_before_touch():
    bars, f = fixture()
    f["plus"][2]=10
    setups, resets, _ = generate_setups(bars, f, 0, 8, True, .1, 1)
    assert 2 in resets and not setups


def test_warmup_enforced():
    bars, f = fixture()
    assert not generate_setups(bars, f, 0, 8, True, .1, 250)[0]


def test_structure_stop_includes_entire_pullback():
    bars, f = fixture()
    bars[2] = [11,12,8,9]
    f["ema"][2]=7  # no EMA touch, though structure low is8
    bars[3]=[11,12,11,11.5]
    bars[4]=[11,12,9,11]
    setups, _, _ = generate_setups(bars, f, 0, 8, True, .1, 1)
    assert setups[4]["stop"]==pytest.approx(7.9)
    assert setups[4]["pullback_start_index"]==2


def test_short_is_mirror_of_long():
    bars, f = fixture()
    mirrored = 30-bars[:,[0,2,1,3]]
    sf = {**f, "ema":30-f["ema"], "plus":f["minus"], "minus":f["plus"]}
    long = generate_setups(bars,f,0,8,True,.1,1)[0][2]
    short = generate_setups(mirrored,sf,0,8,True,.1,1)[0][2]
    assert short["direction"]==-1
    assert short["trigger"]==pytest.approx(30-long["trigger"])
    assert short["stop"]==pytest.approx(30-long["stop"])


def test_indicator_prefix_and_seeds():
    x=np.arange(100,dtype=float)+100
    bars=np.column_stack((x,x+1,x-1,x+.5))
    f=indicators(bars)
    assert np.isnan(f["adx"][:27]).all() and f["adx"][27]==pytest.approx(100)
    assert f["ema"][0]==100.5
    for k in (28,40,80):
        prefix=indicators(bars[:k])
        for key in f:
            np.testing.assert_allclose(prefix[key],f[key][:k],equal_nan=True)
    flat=indicators(np.full((40,4),10.))
    assert np.all(flat["adx"][27:]==0)


def test_signal_prefix_invariance():
    bars,f=fixture()
    full=generate_setups(bars,f,0,8,False,.1,1)[0]
    for k in range(2,9):
        prefix=generate_setups(bars[:k],{a:b[:k] for a,b in f.items()},0,k,False,.1,1)[0]
        assert prefix=={i:s for i,s in full.items() if i<k}


def test_aggregate_observed_buckets_without_interpolation():
    times=np.array([0,60,3660,10800])
    bars=np.array([[1,2,.5,1.5],[1.5,3,1,2],[2,4,1,3],[3,4,2,3.]])
    data=aggregate(times,bars,60)
    assert data.dates.tolist()==[0,3600,10800]
    assert data.counts.tolist()==[2,1,1]
    np.testing.assert_allclose(data.ohlc[0],[1,3,.5,2])


def test_order_gap_fill_and_cancel():
    order={"direction":1,"trigger":12.,"stop":9.}
    assert entry_fill(order,[13,14,12,13])==("fill",13.,True)
    assert entry_fill(order,[8,14,7,12])[0]=="cancel"
    assert entry_fill(order,[10,11,9.5,10])[0]=="wait"


def test_stop_before_target_and_favorable_gap_capped():
    p={"direction":1,"stop":9.,"target":13.}
    assert exit_fill(p,[11,14,8,12])[1]=="both_stop_first"
    assert exit_fill(p,[8,14,7,12])[:2]==(8.,"stop_gap")
    assert exit_fill(p,[14,15,13,14])[:2]==(13.,"target_gap_capped")
    assert exit_fill(p,[11,14,8,12],True)[1]=="both_stop_first"


def data_fixture(bars):
    dates=timestamp("2010-01-01")+np.arange(len(bars))*3600
    return DailyData(dates,bars,dates,dates+3540,np.full(len(bars),60))


def test_next_bar_rr_one_and_cost():
    bars,f=fixture()
    bars[3]=[13,14,12,13]  # adverse entry gap, target17.1, fixed stop8.9
    bars[4]=[13,18,12,17]
    data=data_fixture(bars)
    trades,_,_=simulate(data,f,{"minutes":60,"first_only":True},data.dates[0],data.dates[-1]+3600,1.,.1,.2,0.,1)
    t=trades[0]
    assert t["entry_index"]==3 and t["signal_index"]==2
    assert t["entry"]==13 and t["gross_r"]==pytest.approx(1.)
    assert t["net_r"]==pytest.approx(1-.2/4.1)
    assert t["signal_timestamp"]<=t["entry_timestamp"]


def test_three_bar_expiry_and_consumption():
    bars,f=fixture()
    bars[3:]=[11,12,10.5,11]
    data=data_fixture(bars)
    trades,_,d=simulate(data,f,{"minutes":60,"first_only":True},data.dates[0],data.dates[-1]+3600,1.,.1,0.,0.,1)
    assert not trades
    expiry=[e for e in d["orders"] if e["event"]=="expired"]
    assert expiry==[{"signal_index":2,"index":5,"event":"expired"}]


def test_reset_at_close_does_not_retroactively_cancel_fill():
    bars,f=fixture()
    bars[3]=[13,14,12,13]
    f["plus"][3]=5
    data=data_fixture(bars)
    trades,_,d=simulate(data,f,{"minutes":60,"first_only":True},data.dates[0],data.dates[-1]+3600,1.,.1,0.,0.,1)
    assert trades and trades[0]["entry_index"]==3
    assert any(e["event"]=="reset" and e["index"]==3 for e in d["episodes"])


def test_baseline_improvement_must_be_strict_in_both_metrics():
    summary={"pf":1.2,"profit_r":12,"average_net_r":.1}
    decision={"passed":True,"failures":[]}
    assert not baseline_gate(summary,summary,decision)["passed"]
    assert baseline_gate(summary,{**summary,"pf":1.1,"average_net_r":.09},decision)["passed"]


def test_protocol_budget_and_rr1():
    p=json.loads(SPEC.read_text(encoding="utf-8"))
    assert len(p["search_space"])==4
    assert sum(c["eligible"] for c in p["search_space"])==2
    assert p["exit_rules"]["reward_risk_ratio"]==1
    assert p["exit_rules"]["full_exit"] is True
