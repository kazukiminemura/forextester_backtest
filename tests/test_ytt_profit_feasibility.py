import numpy as np

from scripts.research_ytt_profit_feasibility import (
    actual_open_times, aggregate, fill_bar, metrics, monthly, previous_htf, signals, simulate, states,
)


def test_complete_aggregation_does_not_hide_missing_children():
    t = np.array([0, 300, 600, 900, 1500, 1800, 2100, 2400])
    p = np.column_stack((np.ones(8)*10, np.ones(8)*11, np.ones(8)*9, np.ones(8)*10))
    complete = np.ones(8, bool)
    complete[-1] = False
    times, _, valid, at_open, observed = aggregate(t, p, complete, 900)
    assert times.tolist() == [0, 900, 1800]
    assert valid.tolist() == [True, False, False]
    assert at_open.all()
    assert observed.tolist() == [0, 900, 1800]


def test_pivots_delayed_and_ties_choose_last_equal():
    h = np.array([1, 3, 3, 2, 1, 1, 1], float)
    p = np.column_stack((np.zeros(7), h, -h, np.zeros(7)))
    s = states(p)
    assert np.isnan(s["high"][:4]).all()
    assert s["new_high"][4] and s["high"][4] == 3
    assert not s["new_high"][5]
    # Every prefix gives the same past states: future bars cannot confirm early.
    for end in range(1, 8):
        for key, values in states(p[:end]).items():
            np.testing.assert_array_equal(values, s[key][:end])


def test_htf_availability_uses_m15_start_not_close():
    m = np.array([10*3600+45*60, 11*3600])
    ht = np.array([9*3600, 10*3600])
    assert previous_htf(m, ht, np.array([-1, 1]), 3600).tolist() == [-1, 1]


def test_unaligned_break_consumes_and_new_same_price_pivot_resets():
    close = np.array([9, 11, 9, 11, 9, 11], float)
    p = np.column_stack((close, close+1, close-1, close))
    s = dict(high=np.ones(6)*10, low=np.ones(6)*5,
             new_high=np.array([0, 0, 0, 0, 1, 0], bool), new_low=np.zeros(6, bool))
    side, stop, levels = signals(p, s, np.array([0, -1, 1, 1, 1, 1]), np.ones(6), .1)
    assert side[0].tolist() == [0, 0, 0, 0, 0, 1]
    assert side[1].tolist() == [0, 1, 0, 0, 0, 1]
    assert stop[0, 5] == 4.9 and levels[0, 5] == 10


def test_fill_order_gaps_and_both_touch():
    assert fill_bar(100, 102, 98, 100, 1, 99, 101) == (99, "sl")
    assert fill_bar(98, 102, 97, 100, 1, 99, 101) == (98, "sl_gap")
    assert fill_bar(103, 104, 102, 103, 1, 99, 101) == (101, "tp_gap_capped")
    assert fill_bar(100, 102, 98, 100, -1, 101, 99) == (101, "sl")


def fixture(times, prices, side, stops):
    n = len(times)
    return (np.array(times), np.array(prices, float), np.ones(n, bool), np.ones(n, bool),
            np.array(side), np.array(stops, float), np.ones(n)*100)


def test_next_open_cost_and_cash_sizing():
    args = fixture([0, 900], [[100, 100, 100, 100], [100, 102, 99.5, 101]], [1, 0], [99, 0])
    rows, _, account = simulate(*args, 0, 1800, .1, cash=True)
    assert rows[0]["qty"] == 4000
    assert rows[0]["entry_time"] == 900
    assert abs(rows[0]["net_r"]-.9) < 1e-12
    assert account["net_yen"] == 3600


def test_absolute_stop_catches_gap_and_blocks_all_future_entries():
    args = fixture([0, 900, 1800, 2700, 3600],
        [[100, 100, 100, 100], [100, 100.1, 99.9, 100], [70, 71, 69, 70],
         [100, 102, 99.5, 101], [100, 102, 99.5, 101]], [1, 0, 1, 1, 0], [99, 0, 99, 99, 0])
    rows, _, account = simulate(*args, 0, 4500, .1, cash=True)
    assert len(rows) == 1
    assert account["stopped"] and account["final_equity_yen"] < 900000
    assert rows[0]["reason"] == "sl_gap"  # gap overshoot of ordinary SL also stops account


def test_data_gap_does_not_exit_at_previous_close_and_caps_profit():
    args = fixture([0, 900, 2700], [[100]*4, [100, 100.1, 99.9, 100], [104, 104, 103, 103]], [1, 0, 0], [99, 0, 0])
    rows, _, _ = simulate(*args, 0, 3600, .1)
    assert rows[0]["exit_time"] == 2700
    assert rows[0]["exit_price"] == 101
    assert rows[0]["reason"] == "data_gap_tp_capped"


def test_incomplete_entry_bar_not_lookahead_filtered():
    args = list(fixture([0, 900, 1800], [[100]*4, [100, 100.2, 99.8, 100.1], [100]*4], [1, 0, 0], [99, 0, 0]))
    args[2][1] = False
    rows, _, _ = simulate(*args, 0, 2700, .1)
    assert len(rows) == 1 and rows[0]["reason"] == "incomplete_bar_close"
    assert rows[0]["incomplete_bars"] == 1


def test_scheduled_daily_close_not_last_observed_bar():
    args = fixture([84600, 85500, 86400], [[100]*4, [100, 100.2, 99.8, 100.1], [100]*4], [1, 0, 0], [99, 0, 0])
    rows, _, _ = simulate(*args, 0, 87300, .1)
    assert rows[0]["reason"] == "daily_close" and rows[0]["exit_time"] == 86400


def test_cost_adjusted_metrics_and_empty_months():
    rows = [dict(net_r=x, incomplete_bars=0) for x in [1, -1, -.2]]
    assert abs(metrics(rows)["pf"]-1/1.2) < 1e-12
    result = monthly([], 0, 5097600, cash=True, curve=np.empty((0, 2)))
    assert [x["month"] for x in result] == ["1970-01", "1970-02"]
    assert all(x["pnl_yen"] == 0 for x in result)


def test_intrabar_account_floor_stops_at_absolute_equity_and_quantity_cap():
    n = 60
    args = fixture(np.arange(n)*900, [[100, 100.2, 98, 99]]*n, [1]*n, [99]*n)
    rows, _, account = simulate(*args, 0, n*900, .1, cash=True)
    assert account["stopped"] and abs(account["final_equity_yen"]-900000) < 1e-7
    assert rows[-1]["reason"] == "account_floor"
    assert len(rows) < n-1
    args = fixture([0, 900], [[1000]*4, [1000, 1001, 1000, 1001]], [1, 0], [999.999, 0])
    rows, _, _ = simulate(*args, 0, 1800, .001, cash=True)
    assert rows[0]["qty"] == 25000


def test_gap_exit_uses_observed_open_time_and_month_phase():
    args = list(fixture([0, 900, 2700], [[100]*4, [100, 100.1, 99.9, 100], [104, 104, 103, 103]], [1, 0, 0], [99, 0, 0]))
    args[3][-1] = False
    rows, _, _ = simulate(*args, 0, 3600, .1, observed_open_times=np.array([0, 900, 3000]))
    assert rows[0]["exit_time"] == 3000
    boundary = 31*86400
    base = dict(net_r=1, incomplete_bars=0, exit_time=boundary)
    result = monthly([dict(**base, reason="daily_close"), dict(**base, reason="sl_gap")], 0, 59*86400)
    assert [r["trades"] for r in result] == [1, 1]


def test_missing_first_m1_is_not_treated_as_exact_bucket_open():
    observed, exact = actual_open_times(np.array([60, 120, 900, 960, 1860]), np.array([0, 900, 1800]))
    assert observed.tolist() == [60, 900, 1860]
    assert exact.tolist() == [False, True, False]
    args = list(fixture([0, 900], [[100]*4, [100, 102, 100, 101]], [1, 0], [99, 0]))
    args[3][-1] = False
    rows, _, account = simulate(*args, 0, 1800, .1, observed_open_times=np.array([0, 960]))
    assert rows == [] and account["skipped"]["missing_entry"] == 1
