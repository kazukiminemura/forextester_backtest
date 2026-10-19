"""Behavior boundaries for fixed spot-long RR1; synthetic prices only."""
import numpy as np
import pytest

from scripts import research_btc_spot_rr1 as b

ZERO = {"spread": 0., "fee": 0., "slippage": 0.}


def signal(time=0, close=100., stop=90.):
    return dict(signal_time=time, signal_bar=time-3600, close=close, stop=stop,
                trend=True, atr14=1., ema20=99., higher_available=0)


def run(prices, signals=None, times=None, cost=ZERO, **kwargs):
    prices = np.array(prices, dtype=float)
    times = np.arange(len(prices), dtype=np.int64)*60 if times is None else np.array(times)
    return b.simulate(times, prices, signals or [signal()], cost, int(times[0]), int(times[-1]+60),
                      gate_cost=ZERO, **kwargs)


def trend_data(hours=1000):
    times = np.arange(hours*60, dtype=np.int64)*60
    close = 1000 + np.arange(len(times))//60
    prices = np.column_stack((close-.5, close+.1, close-15., close))
    return times, prices


def test_complete_buckets_do_not_fill_missing_minutes():
    t = np.arange(120, dtype=np.int64)*60
    p = np.tile([100, 102, 98, 101], (120, 1))
    ht, hp = b.aggregate_complete(np.delete(t, 23), np.delete(p, 23, axis=0), 3600)
    assert ht.tolist() == [3600]
    assert hp.tolist() == [[100, 102, 98, 101]]


def test_ema_and_wilder_have_sma_seed_and_known_recurrence():
    vals = np.array([1., 2., 3., 8.])
    ema = b.average(vals, 3, .5)
    wilder = b.average(vals, 3, 1/3)
    assert np.isnan(ema[:2]).all()
    assert ema[2:].tolist() == [2., 5.]
    assert wilder[-1] == pytest.approx(4.)


def test_signals_are_causal_and_four_hour_close_available_at_boundary():
    t, p = trend_data()
    full = b.generate_signals(t, p)
    partial = b.generate_signals(t[:900*60], p[:900*60])
    assert partial == [s for s in full if s["signal_time"] <= 900*3600]
    assert any(s["trend"] for s in partial)
    boundary = next(s for s in full if s["signal_time"] == 800*3600)
    assert boundary["higher_available"] == boundary["signal_time"]
    assert boundary["trend"]


def test_missing_hour_excludes_four_bar_signal_window_and_stale_htf():
    t, p = trend_data()
    keep = ~((t >= 800*3600) & (t < 808*3600))
    sig = b.generate_signals(t[keep], p[keep])
    assert not any(800*3600 < s["signal_time"] < 812*3600 for s in sig)
    # One missing minute excludes its 4h bucket but other complete 1h bars survive.
    keep = t != 804*3600
    sig = b.generate_signals(t[keep], p[keep])
    at_boundary = next(s for s in sig if s["signal_time"] == 809*3600)
    assert not at_boundary["trend"]  # prior complete 4h close is five hours old


def test_stop_tie_and_known_target_open_gap_order():
    assert b.find_exit(np.array([[100., 115., 85., 105.]]), 0, 90., 110.) == (0, 90., "stop")
    assert b.find_exit(np.array([[115., 120., 85., 105.]]), 0, 90., 110.) == (0, 110., "target_gap")
    assert b.find_exit(np.array([[85., 115., 80., 105.]]), 0, 90., 110.) == (0, 85., "stop_gap")


def test_entry_includes_costs_rr_is_actual_entry_and_fees_count_once():
    cost = dict(spread=1., fee=.01, slippage=.001)
    trades, _, equity, _, summary = run([[100, 101, 95, 100], [103, 120, 95, 119]], cost=cost)
    tr = trades[0]
    assert tr["entry"] == pytest.approx(101*1.001)
    assert tr["target"] - tr["entry"] == pytest.approx(tr["entry"]-tr["stop"])
    assert tr["exit"] == pytest.approx(tr["target"]*.999)
    expected = tr["quantity"]*(tr["exit"]-tr["entry"])-tr["buy_fee"]-tr["sell_fee"]
    assert tr["net_pnl"] == pytest.approx(expected)
    assert equity[-1] == pytest.approx(10000+expected)
    assert summary["final_cash"] == pytest.approx(equity[-1])


def test_quantity_is_signal_fixed_with_fill_cash_cap():
    tr = run([[200000, 200001, 199999, 200000]], cost=ZERO)[0][0]
    assert tr["quantity_requested"] == pytest.approx(2.5)
    assert tr["quantity"] == pytest.approx(.05)
    assert tr["cash_capped"]
    assert tr["actual_risk_fraction"] > .0025


def test_normal_and_stress_use_same_normal_cost_signal_qualification():
    s = signal(close=10000, stop=9000)
    normal = b.order_request(s, 10000, b.NORMAL_COST)
    stress = b.order_request(s, 10000, dict(spread=1000, fee=.1, slippage=.1))
    assert normal is not None and stress is not None
    assert normal["estimated_cost_ratio"] == stress["estimated_cost_ratio"]
    assert stress["quantity_requested"] < normal["quantity_requested"]
    assert b.order_request(signal(close=10000, stop=9900), 10000, ZERO) is None


def test_missing_exact_entry_minute_expires_order():
    result = run([[100, 102, 99, 101], [100, 102, 99, 101]],
                 times=[0, 120], signals=[signal(time=60)])
    assert result[0] == []
    assert result[3][0]["reason"] == "missing_entry_minute"


def test_holding_gap_stop_fills_at_observed_open_and_marks_missing():
    tr = run([[100, 105, 95, 101], [80, 120, 75, 90]], times=[0, 600])[0][0]
    assert tr["reason"] == "stop_gap"
    assert tr["exit"] == 80
    assert tr["holding_gap_count"] == 1
    assert tr["holding_missing_minutes"] == 9
    assert tr["gap_exposed"]


def test_same_hour_reentry_blocked_and_next_hour_allowed():
    result = run([[100, 111, 99, 110]]*3, times=[0, 60, 3600],
                 signals=[signal(0), signal(60), signal(3600)])
    assert [t["entry_time"] for t in result[0]] == [0, 3600]
    assert result[3][1]["reason"] == "position_or_exit_hour"


def test_period_end_force_exit_is_separate_and_next_run_starts_flat():
    args = [[100, 105, 95, 103], [104, 106, 100, 105]]
    first = run(args)
    second = run(args)
    assert first[0][0]["reason"] == "period_end"
    assert first[4]["period_end_exits"]["trades"] == 1
    assert first[4]["bracket_exits"]["trades"] == 0
    assert second[0][0]["cash_before"] == 10000


def test_minute_close_drawdown_includes_open_position():
    result = run([[100, 103, 95, 96], [96, 110, 95, 105]])
    assert result[4]["max_drawdown_pct"] == pytest.approx(.1)
    assert result[4]["net_pnl"] > 0


def test_baseline_only_removes_trend_filter():
    s = signal()
    s["trend"] = False
    assert run([[100, 111, 99, 105]], signals=[s], arm="trend")[0] == []
    assert len(run([[100, 111, 99, 105]], signals=[s], arm="baseline")[0]) == 1


def test_invalid_bracket_is_rejected_without_buying():
    result = run([[80, 85, 70, 80]])
    assert not result[0]
    assert result[3][0]["reason"] == "invalid_bracket_at_fill"
    assert result[4]["final_cash"] == 10000
