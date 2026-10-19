import json

import numpy as np
import pytest

from scripts import research_btc_bb_allhours as r


ZERO = dict(spread=0., fee=0., slippage=0., funding_rate=0.)


def signal(when=0, side=1, risk=10., center=0.):
    return dict(index=1, origin=0, origin_time=when-600, signal_time=when,
                signal_bar=when-300, side=side, close=100., target_center=center, risk_price=risk)


def test_complete_aggregation_does_not_impute():
    times = np.delete(np.arange(600, dtype=np.int64)*60, 7)
    prices = np.tile([100., 101., 99., 100.], (len(times), 1))
    mt, f = r.features(times, prices)
    assert 300 not in mt
    assert len(mt) == 119
    assert np.isnan(f[:19, 4]).all()
    assert f[19, 4] == 100.


def test_ask_bracket_and_no_cost_ratio_filter():
    cost = dict(spread=6., fee=.001, slippage=.001, funding_rate=.0004)
    buy = r.order_at_open(signal(side=1, risk=0., center=108.), 100., 10000., cost)
    sell = r.order_at_open(signal(side=-1, risk=0., center=92.), 100., 10000., cost)
    assert buy["entry"] == pytest.approx(106.106)
    assert sell["entry"] == pytest.approx(99.9)
    assert sell["target"] == 98.
    for s, order in ((1,buy),(-1,sell)):
        assert s*(order["target"]-order["entry"]) == pytest.approx(s*(order["entry"]-order["stop"]))
        assert order["estimated_cost_ratio"] > .15
        assert order["quantity"]*order["entry"] <= 10000.
        assert order["quantity"]*order["estimated_stop_loss_per_btc"] <= 25.+1e-10
    assert r.order_at_open(signal(risk=0., center=105.), 100., 10000., cost) is None


@pytest.mark.parametrize("side", [1,-1])
def test_both_hit_stop_first_and_gap_target_capped(side):
    prices = np.array([[100., 120., 80., 100.], [100., 101., 99., 100.]])
    stop, target = (90.,110.) if side == 1 else (110.,90.)
    assert r.find_exit(prices, 0, stop, target, side, 0.) == (0, stop, "stop")
    prices[0] = [120.,125.,115.,120.] if side == 1 else [80.,85.,75.,80.]
    assert r.find_exit(prices, 0, stop, target, side, 0.) == (0, target, "target_gap")
    prices[0] = [80.,85.,75.,80.] if side == 1 else [120.,125.,115.,120.]
    assert r.find_exit(prices, 0, stop, target, side, 0.) == (0, prices[0,0], "stop_gap")


def test_short_immediate_spread_stop():
    cost = dict(ZERO, spread=6.)
    order = r.order_at_open(signal(side=-1, risk=2.), 100., 10000., cost)
    prices = np.array([[100.,101.,99.,100.]])
    assert r.find_exit(prices,0,order["stop"],order["target"],-1,6.) == (0,106.,"stop_gap")


def test_funding_causal_max_and_elapsed_blocks():
    times = np.array([0,60,86400,86460], dtype=np.int64)
    prices = np.array([[100,110,90,100],[100,105,90,100],[100,120,90,100],[100,200,90,100]],dtype=float)
    cost = dict(ZERO,spread=5.,funding_rate=.0004)
    actual = r.funding_series(times,prices,2.,cost)
    assert actual == pytest.approx([0.,.092,.100,.328])
    assert np.array_equal(actual[:3],r.funding_series(times[:3],prices[:3],2.,cost))


@pytest.mark.parametrize("side", [1,-1])
def test_cfd_accounting_and_m5_cooldown(side):
    times = np.arange(11,dtype=np.int64)*60
    prices = np.tile([100.,101.,99.,100.],(len(times),1))
    prices[1] = [100.,111.,99.,110.] if side == 1 else [100.,101.,89.,90.]
    prices[6] = prices[1]
    result = r.simulate(times,prices,[signal(0,side),signal(120,side),signal(300,side)],ZERO,0,660)
    assert len(result["trades"]) == 2
    assert result["decisions"][1]["reason"] == "occupied_or_exit_bucket"
    assert result["trades"][0]["net_pnl"] == pytest.approx(25.)
    assert result["summary"]["ending_equity"] == pytest.approx(10050.0625)
    assert result["equity"][-1] == result["summary"]["ending_equity"]


def test_book_boundary_missing_minute_forced_end_and_funding():
    times = np.array([300,360,480],dtype=np.int64)
    prices = np.tile([100.,101.,99.,100.],(3,1))
    cost = dict(ZERO,fee=.001,funding_rate=.0004)
    result = r.simulate(times,prices,[signal(300),signal(600)],cost,300,600)
    assert len(result["trades"]) == 1
    trade = result["trades"][0]
    assert trade["reason"] == "period_end"
    assert trade["holding_missing_minutes"] == 1
    assert trade["funding"] > 0
    assert trade["net_pnl"] == pytest.approx(-trade["entry_fee"]-trade["exit_fee"]-trade["funding"])
    assert len(result["decisions"]) == 1
    missing = r.simulate(times,prices,[signal(420)],cost,300,600)
    assert missing["decisions"][0]["reason"] == "missing_entry_minute"


def test_entry_minute_funding_zero_despite_exit_high():
    times = np.array([0],dtype=np.int64)
    prices = np.array([[100.,200.,80.,100.]])
    result = r.simulate(times,prices,[signal()],dict(ZERO,funding_rate=.1),0,60)
    assert result["trades"][0]["funding"] == 0


def test_daily_zeros_missing_and_partial_are_separate():
    times = np.r_[np.arange(1440)*60,86400+np.arange(60)*60].astype(np.int64)
    mt = np.r_[np.arange(288)*300,86400+np.arange(12)*300].astype(np.int64)
    trades = [dict(entry_time=86400)]
    result = r.daily_metrics(times,mt,trades,0,3*86400)
    assert result["primary"]["days"] == 1 and result["primary"]["zero_pct"] == 100.
    assert result["entries_complete"] == 0 and result["entries_partial"] == 1
    assert result["missing_days"] == 1 and result["partial_days"] == 1
    assert result["complete_fraction"] == pytest.approx(1/3)


def test_reversal_reservation_cancel_and_mirror():
    times = np.arange(40,dtype=np.int64)*300
    f = np.tile([100.,101.,99.,100.,100.,110.,90.,2.],(40,1))
    f[0,2] = 89.
    f[1,:4] = [95.,101.,90.,100.]
    f[2,2] = 88.  # Reserved; cannot become a new origin.
    f[13,1] = 111.
    f[14,:4] = [105.,110.,99.,100.]
    f[26,2] = 89.
    f[27,:4] = [90.,100.,88.,99.]  # New extreme cancels before bullish confirmation.
    signals, episodes, _ = r.signals_from_features(times,f)
    assert [e["origin"] for e in episodes] == [0,13,26]
    assert [s["side"] for s in signals["baseline_bb_reversal"]] == [1,-1]
    assert episodes[-1]["status"] == "extreme_cancelled"
    gap_times = times.copy(); gap_times[1:] += 300
    _, gaps, _ = r.signals_from_features(gap_times,f)
    assert gaps[0]["status"] == "gap_cancelled"


def test_h1_availability_and_invalid_latest_hour():
    times = np.arange(27*12,dtype=np.int64)*300
    close = 100.+np.arange(len(times))*.1
    f = np.column_stack([close]*4)
    directions,_ = r.h1_direction(f,times)
    assert directions[24*12+10] == 0
    assert directions[24*12+11] == 1
    keep = np.arange(len(times)) != 25*12+3
    broken,hourly = r.h1_direction(f[keep],times[keep])
    assert np.isnan(hourly["close"][25])
    assert broken[np.flatnonzero(times[keep] == 26*3600)[0]] == 0


def test_frozen_budget_and_proxy_contract():
    protocol = json.loads((r.DOC/"protocol.json").read_text(encoding="utf-8"))
    assert protocol["candidate_budget"]["total_cases"] == 27
    assert protocol["cost_and_fill_model"]["scenarios"]["normal"]["fee"] == 0
    assert protocol["cost_and_fill_model"]["scenarios"]["stress"]["funding_rate"] == .0008
    assert protocol["acceptance_gates"]["adoption"] is False


def test_nonpositive_or_nonfinite_order_inputs_rejected():
    for equity in (0., -100., np.inf, np.nan):
        assert r.order_at_open(signal(),100.,equity,ZERO) is None
    assert r.order_at_open(signal(),np.nan,10000.,ZERO) is None
    assert r.order_at_open(signal(risk=np.inf),100.,10000.,ZERO) is None
    assert r.order_at_open(signal(),100.,10000.,dict(ZERO,fee=-1.)) is None


def test_negative_equity_not_floored_no_synthetic_margin_call():
    times = np.array([0,86460,86700],dtype=np.int64)
    prices = np.array([[100.,101.,99.,100.],[100.,1e10,99.,100.],[100.,101.,99.,100.]])
    result = r.simulate(times,prices,[signal(0),signal(86700)],dict(ZERO,funding_rate=.1),0,87000)
    assert result["trades"][0]["reason"] == "target"
    assert result["summary"]["ending_equity"] < 0
    assert result["summary"]["max_drawdown_pct"] > 100
    assert result["decisions"][-1]["reason"] == "invalid_price_or_equity"
