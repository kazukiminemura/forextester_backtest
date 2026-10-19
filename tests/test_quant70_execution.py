"""Independent synthetic execution and frozen-gate checks; no real history loads."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import research_quant70 as research  # noqa: E402


START = datetime(2020, 1, 1)
PROTOCOL = json.loads((research.EXPERIMENT / "protocol.json").read_text(encoding="utf-8"))


def bars(ohlc, spread=0.2, times=None):
    values = np.asarray(ohlc, dtype=float)
    return SimpleNamespace(
        times=times or [START + timedelta(minutes=15*i) for i in range(len(values))],
        open=values[:, 0], high=values[:, 1], low=values[:, 2], close=values[:, 3],
        atr=np.ones(len(values)), spread=spread,
    )


def run(data, directions=None, start=START, end=None, **kwargs):
    directions = np.asarray(directions if directions is not None else [1]+[0]*(len(data.times)-1))
    return research.simulate(data, directions, "TEST", start,
                             end or data.times[-1]+timedelta(minutes=15), pip=1.0, **kwargs)


def test_buy_uses_ask_and_entry_slippage_then_exact_rr1_order_distances():
    trade, = run(bars([[100, 100.5, 99.5, 100], [100, 103, 99, 101]]))
    assert trade.entry == pytest.approx(100.3)
    assert trade.stop == 98
    assert trade.target == pytest.approx(102.6)
    assert trade.target-trade.entry == pytest.approx(trade.entry-trade.stop)
    assert trade.exit == pytest.approx(102.5)
    assert trade.net_r == pytest.approx(2.2/2.3)
    assert trade.reason == "target"


def test_sell_uses_bid_entry_and_ask_barriers_with_both_slippages():
    trade, = run(bars([[100, 100.5, 99.5, 100], [100, 101, 97.3, 98]]), [-1, 0])
    assert trade.entry == pytest.approx(99.9)
    assert trade.stop == pytest.approx(102.2)
    assert trade.target == pytest.approx(97.6)
    assert trade.exit == pytest.approx(97.7)
    assert trade.net_r == pytest.approx(2.2/2.3)
    assert trade.reason == "target"


def test_short_bid_touch_does_not_count_when_ask_has_not_reached_target():
    trade, = run(bars([[100, 100.5, 99.5, 100], [100, 101, 97.5, 99]]), [-1, 0])
    assert trade.reason == "period_end"  # Bid 97.5 is below TP; ask 97.7 is above it.


@pytest.mark.parametrize("direction", [1, -1])
def test_dual_touch_uses_stop_and_reports_ambiguity(direction):
    trade, = run(bars([[100, 100.5, 99.5, 100], [100, 104, 96, 100]]), [direction, 0])
    assert trade.reason == "stop"
    assert trade.ambiguous
    assert trade.net_r < -1  # Adverse exit slippage is charged to a stop too.


@pytest.mark.parametrize("direction, gap, expected_exit", [(1, 96, 95.9), (-1, 104, 104.3)])
def test_stop_gap_fills_actual_open_side_plus_exit_slippage(direction, gap, expected_exit):
    data = bars([[100, 100.5, 99.5, 100], [100, 100.5, 99.5, 100],
                 [gap, gap+0.5, gap-0.5, gap]])
    trade, = run(data, [direction, 0, 0])
    assert trade.reason == "stop_gap"
    assert trade.exit == pytest.approx(expected_exit)
    assert trade.net_r < -1.5


@pytest.mark.parametrize("direction, gap", [(1, 104), (-1, 96)])
def test_target_gap_is_capped_at_limit_before_adverse_exit_slippage(direction, gap):
    data = bars([[100, 100.5, 99.5, 100], [100, 100.5, 99.5, 100],
                 [gap, gap+0.5, gap-0.5, gap]])
    trade, = run(data, [direction, 0, 0])
    assert trade.reason == "target_gap"
    assert trade.exit == pytest.approx(trade.target-direction*0.1)
    assert 0 < trade.net_r < 1


def test_opening_target_gap_is_resolved_before_later_same_bar_stop_touch():
    trade, = run(bars([[100, 100.5, 99.5, 100], [100, 101, 99, 100],
                      [104, 105, 96, 100]]))
    assert trade.reason == "target_gap"
    assert trade.net_r > 0


def test_next_observed_bar_with_missing_interval_is_not_an_entry():
    data = bars([[100, 101, 99, 100], [100, 104, 96, 100]],
                times=[START, START+timedelta(minutes=30)])
    assert run(data) == []


def test_nonpositive_entry_to_stop_risk_is_skipped():
    assert run(bars([[100, 101, 99, 100], [97, 97.5, 96.5, 97]])) == []


def test_period_end_position_is_closed_with_costs_and_future_cannot_change_it():
    data = bars([[100, 101, 99, 100], [100, 101, 99, 100],
                 [100, 101, 99, 100.5], [100, 110, 90, 100]])
    end = START+timedelta(minutes=45)
    trade, = run(data, [1, 0, 0, 0], end=end)
    assert trade.reason == "period_end"
    assert trade.exit_time == data.times[2].isoformat()
    assert trade.exit == pytest.approx(100.4)
    assert trade.net_r == pytest.approx(0.1/2.3)
    data.high[3], data.low[3] = 200, 1
    assert run(data, [1, 0, 0, 0], end=end) == [trade]
    summary = research.stats([trade], 1)
    assert summary["trades"] == summary["forced_period_exits"] == 1
    assert summary["net_win_rate_pct"] == 100
    assert summary["normal_exit_win_rate_pct"] is None


def test_no_signal_from_prior_period_and_no_entry_outside_current_period():
    data = bars([[100, 101, 99, 100]]*4)
    assert run(data, [1, 0, 0, 0], start=data.times[1]) == []
    assert run(data, [0, 0, 1, 0], end=data.times[3]) == []


def test_no_overlapping_position_or_exit_bar_signal_reuse():
    data = bars([[100, 101, 99, 100], [100, 101, 99, 100],
                 [100, 103, 99, 100], [100, 101, 99, 100], [100, 103, 99, 100]])
    trades = run(data, [1, 1, 1, 1, 0])
    assert len(trades) == 2
    assert [t.signal_time for t in trades] == [data.times[0].isoformat(), data.times[3].isoformat()]
    assert trades[0].exit_time < trades[1].entry_time


def trade(result, minute, symbol="TEST"):
    time = (START+timedelta(minutes=minute)).isoformat()
    return research.Trade(symbol, time, time, time, 1, 100, 98, 102, 100, result, "stop", False)


def test_stats_net_win_rate_includes_breakeven_and_pf_uses_amounts():
    summary = research.stats([trade(2, 15), trade(-0.5, 30), trade(0, 45)], 1)
    assert summary["net_win_rate_pct"] == pytest.approx(100/3)
    assert summary["profit_factor"] == 4
    assert summary["expectancy_r"] == 0.5
    assert summary["realized_drawdown_pct"] == 0.125
    assert summary["wilson_95_lower_pct"] < summary["net_win_rate_pct"]


def test_stats_drawdown_follows_exit_order_not_input_order():
    summary = research.stats([trade(-3, 45), trade(-1, 15), trade(2, 30)], 1)
    assert summary["realized_drawdown_pct"] == 0.75


def pass_gate():
    summary = {"trades": 400, "net_win_rate_pct": 70, "profit_factor": 1.5,
               "expectancy_r": 0.1, "trades_per_month": 4,
               "realized_drawdown_pct": 10}
    pairs = {f"PAIR{i}": {"trades": 30, "net_r": 1} for i in range(11)}
    return summary, pairs


def test_exact_frozen_gate_boundaries_pass():
    summary, pairs = pass_gate()
    assert research.rejection_reasons(summary, pairs, "train", PROTOCOL["gates"]) == []


@pytest.mark.parametrize("field,value,reason", [
    ("trades", 399, "取引数不足"),
    ("net_win_rate_pct", 69.999, "コスト後勝率70%未達"),
    ("profit_factor", 1.49, "PF1.5未達または評価不能"),
    ("profit_factor", None, "PF1.5未達または評価不能"),
    ("expectancy_r", 0, "期待値が正ではない"),
    ("trades_per_month", 2.99, "月平均取引数不足"),
    ("realized_drawdown_pct", 10.01, "決済損益DD超過"),
])
def test_each_scalar_gate_rejects_independently(field, value, reason):
    summary, pairs = pass_gate()
    summary[field] = value
    assert research.rejection_reasons(summary, pairs, "train", PROTOCOL["gates"]) == [reason]


def test_pair_count_and_breadth_gates_reject_even_if_aggregate_is_good():
    summary, pairs = pass_gate()
    pairs["PAIR0"]["trades"] = 19
    for i in range(4):
        pairs[f"PAIR{i}"]["net_r"] = 0
    assert research.rejection_reasons(summary, pairs, "train", PROTOCOL["gates"]) == ["通貨別母数不足", "利益通貨数不足"]


@pytest.mark.parametrize("mutation,match", [
    (lambda d: setattr(d, "spread", -1), "spread"),
    (lambda d: d.high.__setitem__(1, 90), "OHLC"),
    (lambda d: d.times.__setitem__(1, d.times[0]), "duplicate"),
    (lambda d: d.times.__setitem__(1, d.times[1]+timedelta(minutes=1)), "unaligned"),
])
def test_quality_rejects_invalid_input(mutation, match):
    data = bars([[100, 101, 99, 100]]*3)
    mutation(data)
    with pytest.raises(ValueError, match=match):
        research.quality(data, START, START+timedelta(hours=1))


def test_quality_rejects_interior_weeklong_gaps_and_hash_changes():
    data = bars([[100, 101, 99, 100]]*3)
    first = research.quality(data, START, START+timedelta(hours=1))
    data.close[1] += 0.1
    assert research.quality(data, START, START+timedelta(hours=1))["sha256"] != first["sha256"]
    data.times[-1] += timedelta(days=8)
    with pytest.raises(ValueError, match="interior"):
        research.quality(data, START, data.times[-1])


@dataclass
class Metadata:
    commission_per_lot: float = 0.0


@pytest.mark.parametrize("commission", [0.0, 1.0])
def test_main_preserves_confirmation_boundary_and_rejects_unverified_commission(tmp_path, monkeypatch, commission):
    protocol = deepcopy(PROTOCOL)
    protocol["candidate_budget"], protocol["symbols"] = 1, ["EURUSD"]
    experiment = tmp_path/"experiment"
    experiment.mkdir()
    (experiment/"protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
    points = [datetime(2010, 1, 1), datetime(2018, 12, 31),
              datetime(2019, 1, 1), datetime(2022, 12, 31)]
    data = bars([[100, 101, 99, 100]]*4, times=points)
    data.minutes = np.zeros(4, dtype=np.int8)
    data.htf_trend = np.zeros(4, dtype=np.int8)
    loads = []

    def prepare(repository, symbol, end, timeframe):
        loads.append(end)
        return data

    monkeypatch.setattr(research, "EXPERIMENT", experiment)
    monkeypatch.setattr(research, "candidates", lambda: [{"name": "fixed", "family": "test"}])
    monkeypatch.setattr(research, "HistoryRepository", lambda _: SimpleNamespace(metadata=lambda _: Metadata(commission)))
    monkeypatch.setattr(research, "_prepare", prepare)
    monkeypatch.setattr(research, "quality", lambda *args: {})
    monkeypatch.setattr(research, "signals", lambda *args: np.zeros(4, dtype=np.int8))
    out = tmp_path/"result"
    monkeypatch.setattr(sys, "argv", ["research_quant70.py", "--output", str(out)])
    if commission:
        with pytest.raises(ValueError, match="commission"):
            research.main()
        assert (out/"failure.json").exists()
        assert not (out/"results.json").exists()
        assert not (out/"trades.jsonl").exists()
        return
    assert research.main() == 0
    result = json.loads((out/"results.json").read_text(encoding="utf-8"))
    assert result["status"] == "REJECTED"
    assert not result["confirmation_evaluated"]
    assert len(loads) == 1 and loads[0] < datetime(2023, 1, 1)
    assert set(result["records"][0]["periods"]) == {"train", "validation"}
