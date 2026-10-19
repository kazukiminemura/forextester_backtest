"""Behavioral tests for availability, pattern state, fills and frozen selection gates."""
import json

import numpy as np
import pytest

from scripts import research_dinapoli_3x3_daily as r


def bars(close):
    close = np.asarray(close, dtype=float)
    return np.column_stack((close, close + .5, close - .5, close))


def candidate(n=8):
    return {"id": f"double_repo_{n}", "kind": "double_repo", "thrust": n, "expiry": n, "eligible": True}


def setup():
    close = np.full(50, 10.)
    close[24:32] = 11.
    close[32:34] = 9.
    close[34] = 11.
    close[35] = 9.
    return bars(close), np.full(50, 10.), np.ones(50)


def test_dma_is_three_period_sma_displaced_three_days():
    ohlc = bars(np.arange(1, 41))
    dma, atr = r.indicators(ohlc)
    assert np.isnan(dma[:5]).all()
    assert dma[5] == 2  # closes at 0,1,2, never at 3,4,5
    assert dma[6] == 3
    assert atr[13] == pytest.approx((1 + 13 * 1.5) / 14)
    changed = ohlc.copy()
    changed[20:] += 1000
    np.testing.assert_array_equal(r.indicators(changed)[0][:20], dma[:20])
    np.testing.assert_array_equal(r.indicators(changed)[1][:20], atr[:20])


def test_sunday_is_merged_with_monday_with_true_source_edges():
    times = np.array([r.timestamp(d) for d in ("2024-01-05T23:55:00", "2024-01-07T22:00:00", "2024-01-08T00:00:00", "2024-01-08T23:55:00", "2024-01-09T00:00:00")])
    data = r.aggregate_daily(times, bars([1, 2, 3, 4, 5]))
    assert [r.iso(t)[:10] for t in data.dates] == ["2024-01-05", "2024-01-08", "2024-01-09"]
    assert data.first[1] == times[1] and data.last[1] == times[3]
    np.testing.assert_array_equal(data.ohlc[1], [2, 4.5, 1.5, 4])
    np.testing.assert_array_equal(data.counts, [1, 3, 1])
    assert np.all(data.last[:-1] < data.first[1:])


def test_daily_aggregation_rejects_duplicate_or_unsorted_times():
    with pytest.raises(ValueError, match="strictly"):
        r.aggregate_daily(np.array([10, 10]), bars([1, 2]))


def test_double_repo_requires_thrust_then_cross_return_and_recross():
    ohlc, dma, atr = setup()
    side, stop, prep = r.generate_signals(ohlc, dma, atr, candidate(), 0, len(ohlc))
    assert np.flatnonzero(side).tolist() == [35]
    assert side[35] == -1 and prep[35] == 24
    assert stop[35] == pytest.approx(11.6)
    assert not r.generate_signals(ohlc, dma, atr, candidate(10), 0, len(ohlc))[0].any()


def test_buy_and_sell_patterns_are_symmetric():
    ohlc, dma, atr = setup()
    mirror = np.column_stack((20-ohlc[:, 0], 20-ohlc[:, 2], 20-ohlc[:, 1], 20-ohlc[:, 3]))
    side, stop, _ = r.generate_signals(mirror, 20-dma, atr, candidate(), 0, len(ohlc))
    assert side[35] == 1
    assert stop[35] == pytest.approx(8.4)


def test_equality_is_not_a_return_and_setup_expires():
    ohlc, dma, atr = setup()
    ohlc[34] = bars([10])[0]
    assert not r.generate_signals(ohlc, dma, atr, candidate(), 0, len(ohlc))[0].any()
    ohlc, dma, atr = setup()
    ohlc[34:41] = bars([9] * 7)
    ohlc[40] = bars([11])[0]
    ohlc[41] = bars([9])[0]
    assert not r.generate_signals(ohlc, dma, atr, candidate(), 0, len(ohlc))[0].any()


def test_expiry_inclusive_and_future_prefix_invariance():
    ohlc, dma, atr = setup()
    ohlc[34:40] = bars([9] * 6)
    ohlc[39] = bars([11])[0]
    ohlc[40] = bars([9])[0]
    full = r.generate_signals(ohlc, dma, atr, candidate(), 0, len(ohlc))
    assert full[0][40] == -1  # first 32 -> second 40, inclusive eight bars
    for end in range(30, len(ohlc)):
        prefix = r.generate_signals(ohlc[:end], dma[:end], atr[:end], candidate(), 0, end)
        for expected, actual in zip(full, prefix):
            np.testing.assert_array_equal(expected[:end], actual)


def test_setup_state_does_not_carry_across_evaluation_boundary():
    ohlc, dma, atr = setup()
    assert not r.generate_signals(ohlc, dma, atr, candidate(), 33, len(ohlc))[0].any()


@pytest.mark.parametrize("direction,bar,expected,reason", [
    (1, [10, 12, 8, 10], 9, "both_stop_first"),
    (-1, [10, 12, 8, 10], 11, "both_stop_first"),
    (1, [8, 12, 7, 10], 8, "stop_gap"),
    (-1, [12, 13, 8, 10], 12, "stop_gap"),
    (1, [12, 13, 8, 10], 11, "target_gap_capped"),
    (-1, [8, 12, 7, 10], 9, "target_gap_capped"),
])
def test_conservative_barrier_order(direction, bar, expected, reason):
    assert r.exit_fill(direction, 10, 10-direction, 10+direction, np.array(bar)) == (expected, reason)


def execution_fixture(monkeypatch, source, signals, stops):
    dates = r.timestamp("2024-01-01") + np.arange(len(source)) * r.DAY
    data = r.DailyData(dates, np.asarray(source, dtype=float), dates, dates + r.DAY - 60, np.full(len(source), 1440))
    monkeypatch.setattr(r, "generate_signals", lambda *args: (np.array(signals), np.array(stops), np.zeros(len(source), dtype=int)))
    return data


def test_next_open_sets_actual_rr_and_signal_cannot_trade_own_bar(monkeypatch):
    data = execution_fixture(monkeypatch, [[10, 100, 1, 10], [11, 13.5, 10, 12]], [1, 0], [9, np.nan])
    trades, diag, _ = r.simulate(data, candidate(), data.dates[0], data.dates[-1] + r.DAY, 1, .1)
    assert len(trades) == 1 and not diag["open_count"]
    t = trades[0]
    assert t["entry_index"] == 1 and t["signal_index"] == 0
    assert t["entry"] == 11 and t["target"] == 13 and t["stop"] == 9
    assert t["net_r"] == pytest.approx(.95)
    assert t["signal_raw_last_timestamp"] < t["entry_raw_first_timestamp"]


def test_gap_beyond_initial_stop_cancels_entry(monkeypatch):
    data = execution_fixture(monkeypatch, [[10, 11, 9, 10], [8, 9, 7, 8]], [1, 0], [9, np.nan])
    trades, diag, _ = r.simulate(data, candidate(), data.dates[0], data.dates[-1]+r.DAY, 1, 0)
    assert trades == [] and diag["cancelled_at_open"] == 1 and diag["open_count"] == 0


def test_boundary_keeps_open_trade_and_reports_force_close_sensitivity(monkeypatch):
    data = execution_fixture(monkeypatch, [[10, 11, 9, 10], [10, 10.5, 9.5, 10.2], [10, 20, 1, 10]], [1, 0, 0], [9, np.nan, np.nan])
    trades, diag, eq = r.simulate(data, candidate(), data.dates[0], data.dates[2], 1, .1)
    assert trades == [] and diag["open_count"] == 1
    assert diag["open_net_r"] == pytest.approx(.1)
    summary = r.summarize(trades, diag, eq)
    assert summary["trades"] == 0
    assert summary["boundary_force_close_sensitivity"]["trades"] == 1


def test_exit_day_signal_is_discarded_no_same_day_reentry(monkeypatch):
    data = execution_fixture(monkeypatch, [[10, 11, 9, 10], [10, 12, 9.5, 11], [11, 12, 10, 11]], [1, 1, 0], [9, 9, np.nan])
    trades, diag, _ = r.simulate(data, candidate(), data.dates[0], data.dates[-1]+r.DAY, 1, 0)
    assert len(trades) == 1 and diag["open_count"] == 0 and diag["ignored_signals"] == 1


def test_aggregate_drawdown_nets_same_date_exits_before_peak_update():
    trades = [{"net_r": -5., "net_pips": -5., "exit_trading_date": "2024-01-01"},
              {"net_r": 5., "net_pips": 5., "exit_trading_date": "2024-01-01"}]
    summary = r.summarize(trades, {"open_count": 0, "open_net_r": 0}, np.array([[1, 0, 0]]))
    assert summary["closed_drawdown_r"] == 0


def test_gate_requires_cost_profit_frequency_and_drawdown():
    protocol = json.loads(r.SPEC.read_text(encoding="utf-8"))
    gates = protocol["acceptance_gates"]
    summary = {**r.distribution([1] * 60 + [-1] * 40), "closed_drawdown_r": 21,
               "largest_single_symbol_closed_drawdown_r": 11, "profitable_symbols": 15}
    result = r.gate(summary, gates["training"], gates)
    assert result["failures"] == ["aggregate_drawdown", "single_symbol_drawdown"]
    summary.update(closed_drawdown_r=20, largest_single_symbol_closed_drawdown_r=10)
    assert r.gate(summary, gates["training"], gates)["passed"]
    summary["trades"] = 99
    assert "insufficient_trades" in r.gate(summary, gates["validation"], gates)["failures"]


def test_protocol_is_finite_frozen_and_matches_execution_defaults():
    protocol = json.loads(r.SPEC.read_text(encoding="utf-8"))
    assert protocol["status"] == "SPEC_FROZEN"
    assert len(protocol["search_space"]) == 3
    assert sum(c["eligible"] for c in protocol["search_space"]) == 2
    assert len(protocol["symbols"]) == 15
    assert protocol["exit_rules"]["reward_risk_ratio"] == 1
    assert protocol["exit_rules"]["full_exit"]
    assert protocol["cost_and_fill_model"]["swap_pips"] == 0
    assert protocol["periods"]["final_confirmation"][1] == "2026-08-31"

