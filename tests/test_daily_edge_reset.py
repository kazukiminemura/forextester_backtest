import copy
import numpy as np
import pytest

from scripts import research_daily_edge_reset as r


def data(n=280):
    dates = np.arange(n)*r.DAY+r.timestamp("2010-01-01")
    bars = np.tile([100., 101., 99., 100.], (n, 1))
    return r.DailyData(dates, bars, dates+60, dates+86340, np.full(n, 1440))


def candidate(family="trend", holding=120):
    return {"id": "test", "family": family, "parameter": 20 if family=="trend" else 1., "exit_window": 10, "holding": holding}


def position(d=1, queued="", target=106.):
    return {"direction": d, "stop": 98. if d==1 else 102., "target": target, "queued_exit": queued}


@pytest.mark.parametrize("d,bar,expected", [(1,[97.,110.,95.,100.],97.),(-1,[103.,110.,95.,100.],103.)])
def test_adverse_gap_is_open(d,bar,expected):
    assert r.bar_fill(position(d,target=106. if d==1 else 94.), np.array(bar)) == (expected,"stop_gap",True)


def test_both_intrabar_stop_first():
    assert r.bar_fill(position(), np.array([100.,107.,97.,105.])) == (98.,"both_stop_first",False)


def test_favorable_gap_capped():
    assert r.bar_fill(position(), np.array([108.,110.,100.,109.])) == (106.,"target_gap_capped",True)


def test_scheduled_open_exit_precedes_later_stop():
    assert r.bar_fill(position(queued="holding_limit"), np.array([100.,107.,97.,105.])) == (100.,"holding_limit",True)


def test_open_stop_gap_precedes_scheduled_exit():
    assert r.bar_fill(position(queued="holding_limit"), np.array([97.,107.,95.,105.])) == (97.,"stop_gap",True)


def test_carry_ceil_calendar_days():
    assert r.charged_days(0,0)==0
    assert r.charged_days(0,1)==1
    assert r.charged_days(0,r.DAY)==1
    assert r.charged_days(0,r.DAY+1)==2
    assert r.charged_days(0,3*r.DAY+1)==4


def test_feature_prefix_no_future_and_prior_channel():
    d=data(280)
    d.ohlc[270:,1]=500.
    full=r.features(d.ohlc)
    short=r.features(d.ohlc[:260])
    for key in full:
        np.testing.assert_allclose(full[key][:260],short[key],equal_nan=True)
    assert full["high20"][270]==101.
    assert full["high20"][271]==500.
    assert np.isnan(full["atr"][18])
    assert full["atr"][19]==2.


def test_breakout_next_open_and_boundary_cost(monkeypatch):
    d=data(255)
    d.ohlc[250:]=[102.,103.,101.,102.]
    monkeypatch.setattr(r,"signal",lambda o,f,c,i: 1 if i==249 else 0)
    trades,eq=r.simulate(d,r.features(d.ohlc),candidate(),d.dates[0],d.dates[-1]+r.DAY,.01,1.8)
    t=trades[0]
    assert t["entry_index"]==250 and t["entry"]==102.
    assert t["reason"]=="period_boundary" and t["exit_index"]==254
    assert t["risk"]==4. and t["carry_days"]==5
    assert t["net_r"]==pytest.approx(-(1.8+.2*5)*.01/4.)
    assert eq[-1,2]==pytest.approx(t["net_r"])


def test_warmup_suppresses_all_early_signals(monkeypatch):
    d=data(249)
    monkeypatch.setattr(r,"signal",lambda *a: pytest.fail("called before warmup"))
    trades,_=r.simulate(d,r.features(d.ohlc),candidate(),d.dates[0],d.dates[-1]+r.DAY,.01,1.8)
    assert not trades


def test_holding_count_next_open(monkeypatch):
    d=data(270)
    monkeypatch.setattr(r,"signal",lambda o,f,c,i: 1 if i==249 else 0)
    trades,_=r.simulate(d,r.features(d.ohlc),candidate(holding=3),d.dates[0],d.dates[-1]+r.DAY,.01,1.8)
    assert trades[0]["entry_index"]==250
    assert trades[0]["exit_index"]==253 and trades[0]["reason"]=="holding_limit"
    assert trades[0]["holding_bars"]==4


def test_trailing_not_applied_retroactively(monkeypatch):
    d=data(254)
    d.ohlc[250]=[100.,110.,99.,109.]
    d.ohlc[251]=[109.,111.,108.,110.]
    d.ohlc[252]=[100.,110.,99.,105.]
    monkeypatch.setattr(r,"signal",lambda o,f,c,i: 1 if i==249 else 0)
    f=r.features(d.ohlc)
    trades,_=r.simulate(d,f,candidate(),d.dates[0],d.dates[-1]+r.DAY,.01,1.8)
    assert trades[0]["exit_index"]==252
    assert trades[0]["reason"]=="stop_gap"
    assert trades[0]["exit_price"]==100.


def test_pure_directional_rules():
    d=data(280); f=r.features(d.ohlc)
    d.ohlc[250,3]=103.
    assert r.signal(d.ohlc,f,candidate(),250)==1
    d.ohlc[250,3]=97.
    assert r.signal(d.ohlc,f,candidate(),250)==-1


def test_pullback_needs_long_term_trend_and_recovery():
    d=data(); f=r.features(d.ohlc); c=candidate("pullback")
    f["sma200"][230]=90.; f["sma200"][250]=95.
    d.ohlc[249,3]=97.; d.ohlc[250,3]=99.
    assert r.signal(d.ohlc,f,c,250)==1
    f["sma200"][230]=96.
    assert r.signal(d.ohlc,f,c,250)==0
    f["sma200"][230]=90.; d.ohlc[250,3]=97.
    assert r.signal(d.ohlc,f,c,250)==0


def test_range_requires_flat_regime_and_mean_exit():
    d=data(); f=r.features(d.ohlc); c=candidate("range")
    d.ohlc[249,3]=97.; d.ohlc[250,3]=99.
    assert r.signal(d.ohlc,f,c,250)==1
    f["sma100"][250]=102.
    assert r.signal(d.ohlc,f,c,250)==0
    d.ohlc[250,3]=100.
    assert r.close_decision(d.ohlc,f,c,250,{"direction":1,"entry_index":250})=="mean_recovered"


def test_baseline_requires_cross_not_level():
    d=data(); f=r.features(d.ohlc); c=candidate("baseline")
    d.ohlc[249,3]=100.; d.ohlc[250,3]=101.
    assert r.signal(d.ohlc,f,c,250)==1
    d.ohlc[249,3]=101.
    assert r.signal(d.ohlc,f,c,250)==0


def test_mtm_drawdown_has_initial_zero():
    assert r.mtm_dd([-2.,1.,-3.,2.])==4.


def test_positive_closed_can_fail_mtm_gate():
    protocol={"acceptance_gates":{"validation":{"minimum_trades":75,"minimum_pf":1.1,"minimum_profitable_symbols":10},"maximum_aggregate_daily_mtm_drawdown_r":40,"maximum_single_symbol_daily_mtm_drawdown_r":20}}
    summary={"trades":100,"pf":1.2,"profit_r":120.,"average_net_r":.2,"profitable_symbols":12,"mtm_drawdown_r":41,"max_single_symbol_mtm_drawdown_r":10}
    assert r.gate(summary,"validation",protocol)=={"passed":False,"failures":["mtm_dd"]}


def test_intraday_stop_charges_exit_day_and_no_same_day_reentry(monkeypatch):
    d=data(254)
    d.ohlc[250]=[100.,101.,95.,100.]
    monkeypatch.setattr(r,"signal",lambda o,f,c,i: 1)
    trades,_=r.simulate(d,r.features(d.ohlc),candidate(),d.dates[0],d.dates[-1]+r.DAY,.01,1.8)
    assert trades[0]["reason"]=="stop" and trades[0]["carry_days"]==1
    assert trades[1]["entry_index"]==252
