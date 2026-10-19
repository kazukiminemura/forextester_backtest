"""Behavior checks for observation timing, selection and joint resampling."""
import numpy as np

from scripts.research_bb_event_edge import bootstrap, censor_reason, episode_ledger, measure, observe, select_events, stage_b_signals
from scripts.research_bb3_jev_engine import simulate


def fixture(n=400):
    start = int(np.datetime64("2020-01-01", "s").astype(int))
    times = start + np.arange(n,dtype=np.int64)*300
    f = np.zeros((n,15))
    f[:,:8] = [100,100.2,99.8,100,100,103,97,1]
    return f,times


def test_origins_cooldown_dual_touch_and_historical_control():
    f,times = fixture()
    f[[310,315,324],2] = 96
    f[340,1:3] = [104,96]
    origins,sides,controls,counts = select_events(f,times)
    np.testing.assert_array_equal(origins,[310,324])
    np.testing.assert_array_equal(sides,[1,1])
    np.testing.assert_array_equal(controls,[297,311])
    assert counts["reserved_touch_bars"] == 1
    assert counts["both_side_touch_bars"] == 1
    f[325:,:4] *= 2
    after = select_events(f,times)
    np.testing.assert_array_equal(after[0][:2],origins)
    np.testing.assert_array_equal(after[2][:2],controls)


def test_invalid_prior_window_is_not_hidden_by_positive_median():
    f,times = fixture()
    f[30,7] = 0
    f[310,2] = 96
    assert len(select_events(f,times)[0]) == 0


def test_next_open_origin_and_same_bar_adverse_first():
    f,times = fixture(20)
    f[0,4] = 101
    f[1,:5] = [100,102,98,100.5,100.4]
    out = observe(f,times,0,1,1,times[-1]+300)
    assert out[0] == .5 and out[2] == 2 and out[3] == 2
    assert out[4] == 1 and out[5] == 1 and out[10] == -1
    # A later opening gap already beyond TP precedes the adverse intrabar wick.
    f[1,:4] = [100,100.2,99.8,100]
    f[2,:4] = [102,103,98,100]
    assert observe(f,times,0,1,3,times[-1]+300)[10] == 1


def test_moving_center_can_touch_without_positive_close_displacement():
    f,times = fixture(20)
    f[0,4] = 102
    f[1,:5] = [100,100.1,99.5,99.8,99.9]
    out = observe(f,times,0,1,1,times[-1]+300)
    assert out[4] == 0 and out[5] == 1 and out[7] < 0 and out[8] < 0 and out[9] == 1


def test_censoring_preserves_origin_and_never_substitutes_control():
    f,times = fixture(40)
    times[17:] += 300
    event,control,er,cr = measure(f,times,np.array([25]),np.array([1]),np.array([14]),.01)
    assert np.isfinite(event[0,2,0]) and np.isnan(control[0,2]).all()
    assert er[0,2] == 0 and cr[0,2] == 4
    assert censor_reason(times,-1,6,times[-1]+1) == 1
    assert censor_reason(times,39,6,times[-1]+1) == 2
    assert censor_reason(times,20,6,times[26]) == 3


def test_sell_is_mirror_and_own_atr_normalizes():
    f,times = fixture(20)
    f[0,7] = 2
    f[1,:4] = [100,101,98,99]
    out = observe(f,times,0,-1,1,times[-1]+1)
    assert out[0] == 1 and out[1] == .5 and out[2] == 1 and out[3] == .5


def test_month_bootstrap_keeps_cluster_and_event_weights():
    months = np.array([600,600,601])
    result = bootstrap(months,np.array([1.,1.,-1.]),np.array([600,601]))
    assert result["ci95"] == [-1.,1.]
    assert result["leave_one_month_out_min"] == -1.
    assert result["months"][0]["n"] == 2


def test_stage_b_confirmation_later_close_break_and_cancel_priority():
    f,times=fixture(20)
    f[0,2]=97
    f[1,:4]=[99,100.5,98,100]
    f[2,:4]=[100,101,99,100.5]  # equality is not a breakout
    f[3,:4]=[100,102,99,101]
    signals,_=stage_b_signals(f,times,np.array([0]),np.array([1]),.01)
    assert [s["index"] for s in signals["reversal_close_next_open"]]==[1]
    assert [s["index"] for s in signals["breakout_close_next_open"]]==[3]
    f[3,2]=96
    signals,reasons=stage_b_signals(f,times,np.array([0]),np.array([1]),.01)
    assert not signals["breakout_close_next_open"]
    assert reasons["breakout_close_next_open"][0]=="extreme_cancel"
    assert len(signals["reversal_close_next_open"])==1


def test_stage_b_expiry_and_gap_cancel():
    f,times=fixture(20)
    f[12,3]=100.1
    signals,reasons=stage_b_signals(f,times,np.array([0]),np.array([1]),.01)
    assert not signals["reversal_close_next_open"]
    assert reasons["reversal_close_next_open"][0]=="expired"
    times[1:]+=300
    assert stage_b_signals(f,times,np.array([0]),np.array([1]),.01)[1]["reversal_close_next_open"][0]=="gap_cancel"


def test_episode_ledger_keeps_occupied_and_room_rejections_as_zero():
    f,times=fixture(40)
    f[[0,13],4]=104
    f[20,1]=105
    origins=np.array([0,13,26])
    signals,reasons=stage_b_signals(f,times,origins,np.ones(3,dtype=int),.01)
    arm="touch_next_open"
    sim=simulate(f,times,1.,.01,signals[arm],start=int(times[0]),end=int(times[-1]+300),cost_pips=1.)
    ledger=episode_ledger(f,times,origins,signals[arm],reasons[arm],sim,1.,times[0],times[-1]+300)
    assert [r["status"] for r in ledger]==["closed","occupied","entry_room"]
    assert ledger[0]["net_r"]==.75 and ledger[0]["gross_r"]==1
    assert ledger[1]["net_r"]==ledger[2]["net_r"]==0


def test_episode_ledger_period_signal_does_not_enter_next_book():
    f,times=fixture(20)
    f[10,4]=104
    signal=dict(index=10,side=1,origin=9,target=104.)
    sim=simulate(f,times,1.,.01,[signal],start=times[0],end=times[10],cost_pips=1.)
    rows=episode_ledger(f,times,np.array([9]),[signal],{9:"signal"},sim,1.,times[0],times[10])
    assert rows[0]["status"]=="signal_after_period_end" and rows[0]["net_r"]==0
