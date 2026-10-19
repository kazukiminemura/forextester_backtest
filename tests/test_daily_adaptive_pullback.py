import copy
import numpy as np
import pytest
from scripts import research_daily_adaptive_pullback as r


def data(n=4):
    dates=np.arange(n)*r.base.DAY+r.base.timestamp("2010-01-01")
    bars=np.tile([100.,101.,99.,100.],(n,1))
    return r.base.DailyData(dates,bars,dates+60,dates+86340,np.full(n,1440))


def protocol(max_positions=5,max_currency=3):
    return {"monthly_selection":{"minimum_trades":8,"top":5},"capacity":{"maximum_positions":max_positions,"maximum_positions_per_constituent_currency":max_currency}}


def trade(entry=100,exit=200,net=1.,reason="target",date="2013-01-02T00:00:00"):
    return {"entry_timestamp":entry,"exit_exposure_timestamp":exit,"net_r":net,"reason":reason,"entry_date":date}


def test_month_subtract_handles_year_and_leap():
    assert r.month_lower("2024-02",24)==r.base.timestamp("2022-02-01")
    assert r.month_lower("2024-01",60)==r.base.timestamp("2019-01-01")


def test_selection_strict_cutoff_and_boundary_exclusion():
    cutoff=r.base.timestamp("2013-01-01")
    past=[trade(exit=cutoff-100-i) for i in range(8)]
    shadow={"AUDUSD":past+[trade(exit=cutoff,net=10000.),trade(exit=cutoff-1,net=10000.,reason="period_boundary")],"EURUSD":[trade(exit=cutoff-100-i,net=-1.) for i in range(10)]}
    choices=r.monthly_choices(shadow,{"2013-01":cutoff},24,protocol())
    assert choices["2013-01"]["selected"]==["AUDUSD"]
    stat=choices["2013-01"]["stats"][0]
    assert stat["trades"]==8 and stat["score"]==pytest.approx(8/18)


def test_future_pnl_mutation_does_not_change_month_selection():
    cutoff=r.base.timestamp("2013-01-01")
    shadow={"AUDUSD":[trade(exit=cutoff-100-i) for i in range(8)]+[trade(exit=cutoff+100,net=-100.)]}
    expected=r.monthly_choices(shadow,{"2013-01":cutoff},24,protocol())
    shadow["AUDUSD"][-1]["net_r"]=1e9
    assert r.monthly_choices(shadow,{"2013-01":cutoff},24,protocol())==expected


def test_min_eight_and_positive_mean_required():
    cutoff=r.base.timestamp("2013-01-01")
    shadow={"AUDUSD":[trade(exit=cutoff-100-i) for i in range(7)],"EURUSD":[trade(exit=cutoff-100-i,net=0.) for i in range(8)]}
    assert not r.monthly_choices(shadow,{"2013-01":cutoff},24,protocol())["2013-01"]["selected"]


def test_ties_alphabetical_top_five():
    cutoff=r.base.timestamp("2013-01-01")
    symbols=["USDJPY","USDCAD","NZDUSD","GBPUSD","EURUSD","AUDUSD"]
    shadow={s:[trade(exit=cutoff-100-i) for i in range(8)] for s in symbols}
    assert r.monthly_choices(shadow,{"2013-01":cutoff},24,protocol())["2013-01"]["selected"]==sorted(symbols)[:5]


def choices(symbols):
    return {"2013-01":{"cutoff":0,"selected":symbols}}


def test_same_time_exit_releases_before_entry():
    shadow={"AUDUSD":[trade(entry=100,exit=200)],"EURUSD":[trade(entry=200,exit=300)]}
    accepted,logs=r.select_entries(shadow,choices(list(shadow)),r.base.timestamp("2013-01-01"),r.base.timestamp("2013-02-01"),protocol(1))
    assert len(accepted)==2 and [x["positions_before"] for x in logs]==[0,0]


def test_intraday_unknown_exit_still_occupies_slot():
    shadow={"AUDUSD":[trade(entry=100,exit=250)],"EURUSD":[trade(entry=200,exit=300)]}
    accepted,logs=r.select_entries(shadow,choices(list(shadow)),r.base.timestamp("2013-01-01"),r.base.timestamp("2013-02-01"),protocol(1))
    assert accepted=={"AUDUSD:0"} and logs[-1]["reason"]=="position_capacity"


def test_constituent_limit_counts_gross_and_same_time_symbol_order():
    shadow={s:[trade()] for s in ["USDJPY","GBPUSD","EURUSD","AUDUSD"]}
    accepted,logs=r.select_entries(shadow,choices(list(shadow)),r.base.timestamp("2013-01-01"),r.base.timestamp("2013-02-01"),protocol())
    assert accepted=={"AUDUSD:0","EURUSD:0","GBPUSD:0"}
    assert logs[-1]["reason"]=="currency_capacity"


def test_entry_future_profit_does_not_influence_capacity():
    shadow={"AUDUSD":[trade()],"EURUSD":[trade()]}
    expected=r.select_entries(shadow,choices(list(shadow)),r.base.timestamp("2013-01-01"),r.base.timestamp("2013-02-01"),protocol(1))
    shadow["EURUSD"][0]["net_r"]=1e20
    assert r.select_entries(shadow,choices(list(shadow)),r.base.timestamp("2013-01-01"),r.base.timestamp("2013-02-01"),protocol(1))==expected


def test_monthly_calendar_uses_raw_sunday_for_monday_month():
    d=data(2)
    monday=r.base.timestamp("2016-02-01")
    d.dates[:]=[monday,monday+r.base.DAY]
    d.first[:]=[monday-3600,monday+r.base.DAY]
    cal=r.monthly_calendar({"AUDUSD":(d,)},monday,monday+2*r.base.DAY)
    assert cal=={"2016-02":monday-3600}


def test_before_phase_shadow_entry_not_opened_midtrade():
    shadow={"AUDUSD":[trade(date="2012-12-31T00:00:00",exit=1000)]}
    accepted,logs=r.select_entries(shadow,choices(list(shadow)),r.base.timestamp("2013-01-01"),r.base.timestamp("2013-02-01"),protocol())
    assert not accepted and not logs


def test_actual_equity_matches_subset_and_carry():
    d=data(4)
    t={"entry_index":0,"exit_index":2,"entry_timestamp":int(d.first[0]),"entry":100.,"risk":4.,"direction":1,"net_r":-.006}
    eq=r.actual_equity(d,[t],d.dates[0],d.dates[-1]+r.base.DAY,.01,1.8)
    assert eq[0,2]==pytest.approx(-.005)
    assert eq[1,2]==pytest.approx(-.0055)
    assert eq[2,2]==pytest.approx(-.006)
    assert eq[3,2]==pytest.approx(-.006)


def test_strict_profitable_majority():
    p={"acceptance_gates":{"validation":{"minimum_trades":30,"minimum_pf":1.1},"maximum_daily_mtm_drawdown_r":20,"minimum_active_symbols":5}}
    s={"trades":50,"pf":1.2,"profit_r":10,"average_net_r":.1,"mtm_drawdown_r":10,"active_symbols":6,"profitable_symbols":3}
    assert r.gate(s,"validation",p)=={"passed":False,"failures":["profitable_majority"]}
