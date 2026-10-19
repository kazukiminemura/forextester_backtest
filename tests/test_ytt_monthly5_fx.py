import numpy as np

from scripts import research_ytt_monthly5_fx as research
from scripts import research_ytt_profit_feasibility as core


def test_weekly_calendar_observed_bars_accept_weekend_closure_and_monday_anchor():
    t = np.array([core.epoch(x) for x in ["2020-01-03T22:00", "2020-01-05T22:00", "2020-01-06T00:00"]])
    p = np.array([[100, 103, 99, 101], [101, 104, 100, 102], [103, 105, 102, 104]], float)
    labels, bars, quality = research.calendar_bars(t, p, np.array([True, False, True]), 604800, research.MONDAY_ANCHOR)
    assert labels.tolist() == [core.epoch("2019-12-30"), core.epoch("2020-01-06")]
    assert bars[0].tolist() == [100, 104, 99, 102]
    assert quality[0]["observed_calendar_days"] == 2
    assert quality[0]["unobserved_calendar_days"] == 5
    assert quality[0]["complete_m5_ratio"] == .5
    assert quality[0]["within_observed_day_missing_m5"] == 0


def test_calendar_quality_distinguishes_within_day_gap_from_unobserved_day():
    t = np.array([0, 600, 86400])
    p = np.tile([100, 101, 99, 100], (3, 1))
    _, _, q = research.calendar_bars(t, p, np.ones(3, bool), 86400)
    assert q[0]["within_observed_day_missing_m5"] == 1
    assert q[0]["unobserved_calendar_days"] == 0


def test_weekly_context_uses_previous_ended_period_and_requires_both_pivots():
    t = np.array([core.epoch("2019-12-23"), core.epoch("2019-12-30")])
    state = dict(direction=np.array([-1, 1]), high=np.array([110, 110]), low=np.array([90, 90]))
    entry = np.array([core.epoch("2020-01-05T23:45"), core.epoch("2020-01-06")])
    d, ready = research.context(entry, t, state, 604800, research.MONDAY_ANCHOR)
    assert d.tolist() == [-1, 1] and ready.all()
    state["low"] = np.array([np.nan, 90])
    d, ready = research.context(entry, t, state, 604800, research.MONDAY_ANCHOR)
    assert d.tolist() == [0, 1] and ready.tolist() == [False, True]


def test_h1_mapping_enters_only_at_next_hour_open_and_rejects_missing_actual_open():
    times = np.arange(10*3600, 12*3600, 900)
    side, stop, level = research.map_signals(times, np.array([10*3600]), 3600,
                                            np.array([1]), np.array([99]), np.array([100]))
    assert np.flatnonzero(side).tolist() == [3]
    prices = np.tile([100, 102, 99.5, 101], (len(times), 1)).astype(float)
    exact = np.ones(len(times), bool)
    rows, _, _ = core.simulate(times, prices, exact, exact, side, stop, level, times[0], times[-1]+900, .1)
    assert len(rows) == 1 and rows[0]["entry_time"] == 11*3600
    exact[4] = False
    rows, _, _ = core.simulate(times, prices, np.ones(len(times), bool), exact, side, stop, level,
                               times[0], times[-1]+900, .1, observed_open_times=times+np.where(exact, 0, 60))
    assert rows == []


def test_h1_mapping_does_not_carry_event_across_missing_next_execution_bar():
    times = np.array([10*3600, 10*3600+900, 10*3600+1800, 10*3600+2700, 11*3600+900])
    side, stop, level = research.map_signals(times, np.array([10*3600]), 3600, np.array([1]), np.array([99]), np.array([100]))
    prices = np.tile([100, 102, 99.5, 101], (len(times), 1)).astype(float)
    rows, _, _ = core.simulate(times, prices, np.ones(len(times), bool), np.ones(len(times), bool), side, stop, level,
                              times[0], times[-1]+900, .1)
    assert rows == []


def test_geometric_arithmetic_best_removed_and_fixed_yen_are_distinct():
    curve = np.array([[core.epoch("2020-02-01"), 1_100_000], [core.epoch("2020-03-01"), 990_000]], float)
    months = research.monthly_account([], curve, core.epoch("2020-01-01"), core.epoch("2020-03-01"))
    summary = research.return_summary(months)
    assert abs(summary["arithmetic_monthly_return"]) < 1e-12
    assert abs(summary["geometric_monthly_return"]-(.99**.5-1)) < 1e-12
    assert abs(summary["geometric_without_one_best_month"]+.1) < 1e-12
    assert not summary["every_month_reaches_5_percent"]
    assert summary["ratio_months_reaching_5_percent"] == .5
    # A fixed 50,000 gain on 2,000,000 is only 2.5%, not a 5% month.
    curve = np.array([[core.epoch("2020-02-01"), 2_000_000], [core.epoch("2020-03-01"), 2_050_000]], float)
    mm = research.monthly_account([], curve, core.epoch("2020-01-01"), core.epoch("2020-03-01"))
    assert mm[1]["reaches_fixed_50000"] and not mm[1]["reaches_5_percent"]


def test_early_stop_is_not_reset_in_later_period_and_zero_months_remain():
    start, end = core.epoch("2020-01-01"), core.epoch("2026-01-01")
    curve = np.array([[core.epoch("2020-02-01"), 900_000], [end, 900_000]], float)
    months = research.monthly_account([], curve, start, end)
    account = dict(stopped=True, stop_time_source="2020-01-15T12:00:00")
    later = research.account_window([], months, curve, account, core.epoch("2023-01-01"), end)
    assert len(months) == 72 and later["months"] == 36
    assert later["starting_equity_yen"] == later["ending_equity_yen"] == 900_000
    assert later["geometric_monthly_return"] == 0 and later["net_yen"] == 0
    assert later["halted_by_period_end"]
    assert not research.normal_account_gate(later)["no_stop"]
    assert later["max_consecutive_months_below_5_percent"] == 36


def test_yen_pf_differs_from_equal_r_pf_and_undefined_does_not_pass():
    start, end = core.epoch("2020-01-01"), core.epoch("2020-02-01")
    rows = [dict(exit_time=start+900, reason="sl", pnl_yen=100, net_r=2, incomplete_bars=0),
            dict(exit_time=start+1800, reason="sl", pnl_yen=-50, net_r=-2, incomplete_bars=0)]
    curve = np.array([[end, 1_000_050]], float)
    account = dict(stopped=False, stop_time_source="")
    months = research.monthly_account(rows, curve, start, end)
    report = research.account_window(rows, months, curve, account, start, end)
    assert report["pf_jpy"] == 2 and core.metrics(rows)["pf"] == 1
    empty = research.account_window([], months, curve, account, start, end)
    assert empty["pf_jpy"] is None and not research.normal_account_gate(empty)["pf_jpy"]


def test_nonpositive_equity_is_undefined_for_geometric_goal():
    start, end = core.epoch("2020-01-01"), core.epoch("2020-03-01")
    curve = np.array([[core.epoch("2020-02-01"), -100], [end, -100]], float)
    mm = research.monthly_account([], curve, start, end)
    summary = research.return_summary(mm)
    assert mm[1]["monthly_return"] is None
    assert summary["geometric_monthly_return"] is None and summary["arithmetic_monthly_return"] is None


def test_month_end_close_and_month_start_gap_have_separate_attribution():
    boundary = core.epoch("2020-02-01")
    rows = [dict(exit_time=boundary, reason="daily_close"), dict(exit_time=boundary, reason="sl_gap")]
    assert research.in_period(rows, core.epoch("2020-01-01"), boundary) == [rows[0]]
    assert research.in_period(rows, boundary, core.epoch("2020-03-01")) == [rows[1]]


def test_stop_exactly_at_period_boundary_obeys_close_or_open_phase():
    start, boundary = core.epoch("2020-01-01"), core.epoch("2021-01-01")
    curve = np.array([[boundary, 900000]], float)
    account = dict(stopped=True, stop_time_source="2021-01-01T00:00:00")
    for reason, expected in [("account_floor", True), ("account_floor_gap", False)]:
        rows = [dict(exit_time=boundary, reason=reason, pnl_yen=-100000)]
        mm = research.monthly_account(rows, curve, start, boundary)
        summary = research.account_window(rows, mm, curve, account, start, boundary)
        assert summary["halted_by_period_end"] is expected


def test_consecutive_unmet_months_resets_only_on_actual_five_percent_month():
    months = [dict(monthly_return=r, reaches_5_percent=r is not None and r >= .05,
                   reaches_fixed_50000=False) for r in [.01, .02, .05, 0, -.02, None]]
    assert research.return_summary(months)["max_consecutive_months_below_5_percent"] == 3
