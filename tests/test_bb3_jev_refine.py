"""Synthetic checks only: deterministic filters and selection-before-evaluation."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import research_bb3_jev_refine as m


def scenario(side=1):
    f = np.zeros((10, 15))
    f[:, :10] = [100, 100.1, 99.95, 100.08, 100.2, 101, 99, .2, 102, 98]
    f[0, 4], f[3, 4], f[6, 4] = 100.4, 100.2, 100.1
    if side == -1:
        f[:, :4] = np.column_stack((200-f[:, 0], 200-f[:, 2], 200-f[:, 1], 200-f[:, 3]))
        f[:, 4] = 200-f[:, 4]
    s = dict(index=6, side=side, threshold=100.05 if side == 1 else 99.95,
             target=100.2 if side == 1 else 99.8, prep_index=4, confirmed_index=5)
    return f, [s]


@pytest.mark.parametrize("side", [1, -1])
def test_cumulative_filters_accept_both_directions_and_prefix(side):
    f, signals = scenario(side)
    for p in m.POLICIES:
        assert m.policy_signals(f, signals, p) == signals
        assert m.policy_signals(f[:7], signals, p) == signals
    assert m.entry_room("close_hold") == 3
    assert m.entry_room("room5") == m.entry_room("deceleration") == 5


@pytest.mark.parametrize("side", [1, -1])
def test_strict_close_hold_and_directional_body(side):
    f, signals = scenario(side)
    f[6, 3] = signals[0]["threshold"]
    assert m.policy_signals(f, signals, "close_hold") == []
    f, signals = scenario(side)
    f[6, 0] = f[6, 3]
    assert m.policy_signals(f, signals, "close_hold") == []


def test_acceleration_and_tr_boundaries():
    f, signals = scenario()
    f[6, 4] = 99.99
    assert m.policy_signals(f, signals, "room5") == signals
    assert m.policy_signals(f, signals, "deceleration") == []
    f, signals = scenario()
    f[6, 1], f[6, 2], f[5, 3] = 100.5, 100.0, 100.0
    f[6, 7] = .5/1.5
    assert m.policy_signals(f, signals, "deceleration") == signals
    f[6, 1] += .001
    assert m.policy_signals(f, signals, "deceleration") == []


def test_true_range_uses_previous_close_and_missing_history_fails():
    f, signals = scenario()
    f[5, 3] = 99
    assert m.policy_signals(f, signals, "deceleration") == []
    f, signals = scenario()
    f[3, 4] = np.nan
    assert m.policy_signals(f, signals, "deceleration") == []
    assert m.policy_signals(f, [dict(signals[0], index=5)], "deceleration") == []


def training_totals():
    return {m.arm_name(p, rr, 1.0): {"2023": dict(trades=30, average_r=.1)}
            for p in m.POLICIES for rr in m.RRS}


def test_training_selection_count_ties_and_no_later_period_dependency():
    t = training_totals()
    assert m.select_training(t)["arm"] == "close_hold_rr1.0_cost1.0"
    t["room5_rr1.5_cost1.0"]["2023"]["average_r"] = .2
    assert m.select_training(t)["policy"] == "room5"
    t["room5_rr1.5_cost1.0"]["2023"]["trades"] = 29
    assert m.select_training(t)["policy"] == "close_hold"
    for row in t.values():
        row["2023"]["trades"] = 29
    assert m.select_training(t) is None


def test_arms_exact_budget_and_r_pf():
    assert len(m.arms()) == 12
    assert sum(p in m.POLICIES for p, _ in m.arms()) == 9
    a = m.aggregate([dict(net_pips=19, net_r=.95), dict(net_pips=-11, net_r=-1.1)])
    assert a["profit_factor_r"] == pytest.approx(.95/1.1)
    assert a["profit_factor"] == pytest.approx(19/11)


def test_combined_curve_is_causal_and_accounts_for_absent_pair():
    timeline = np.array([0, 1, 2, 3, 4])
    equity = np.zeros(5)
    m.add_curve(equity, timeline, np.array([[1, 5], [3, -2]]))
    np.testing.assert_array_equal(equity, [0, 5, 5, -2, -2])
    m.add_curve(equity, timeline, np.empty((0, 2)))
    np.testing.assert_array_equal(equity, [0, 5, 5, -2, -2])


def test_report_freezes_selection_before_later_simulations(tmp_path, monkeypatch):
    times = np.array([span[0] for key, span in m.periods().items() if key != "all"])
    f = np.zeros((3, 15))
    calls = []
    def fake_simulate(*args, **kwargs):
        assert kwargs["entry_delay"] == 1
        assert "allowed" not in kwargs
        is_training = kwargs["start"] == m.START and kwargs["end"] == m.periods()["2023"][1]
        if not is_training:
            selection = json.loads((tmp_path/"selection.json").read_text())
            assert selection["later_periods_simulated"] is False
            assert all(set(v) == {"2023"} for v in selection["training_totals"].values())
        calls.append(is_training)
        return dict(trades=[], mtm=np.empty((0, 2)), summary=dict(
            open_net_r=0, net_plus_open_r=0, open_net_pips=0, net_plus_open_pips=0))
    monkeypatch.setattr(m, "simulate", fake_simulate)
    result = m.report({"SYNTHETIC": (f, times, .01, .001, [])}, {}, tmp_path)
    assert calls[:24] == [True]*24
    assert not any(calls[24:])
    assert result["model_trade_calls"] == result["model_trade_cache_reads"] == 0
    assert result["complete"] is True
    assert result["selected_from_2023"] is None
    assert not result["numeric_gates_pass"]
    assert len(calls) == 96


def test_no_model_import_cache_or_trade_gate_in_runner():
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "from research_bb3_jev import" not in source
    assert "responses/" not in source and "validate_cached" not in source
    assert "allowed=" not in source and "urllib" not in source


def test_room_checked_at_actual_next_open_not_signal_close():
    f, signals = scenario()
    times = np.arange(len(f))*300
    f[7, 0] = 100.16  # Four pips remain to target; prior signal close leaves 12.
    f[7, 1], f[7, 2], f[7, 3] = 100.18, 100.15, 100.16
    f[8:, :4] = [100.16, 100.18, 100.15, 100.16]
    for p, expected in (("close_hold", 1), ("room5", 0)):
        result = m.simulate(f, times, .01, .001, m.policy_signals(f, signals, p),
                            start=0, end=100000, min_center_pips=m.entry_room(p), entry_delay=1)
        assert result["summary"]["open_side"] == expected


def test_atomic_json_retries_temporary_windows_reader_lock(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    original = Path.replace
    calls, waits = [], []
    def transient(source, target):
        calls.append((source, target))
        if len(calls) == 1:
            raise PermissionError("synthetic brief reader lock")
        return original(source, target)
    monkeypatch.setattr(Path, "replace", transient)
    monkeypatch.setattr(m.time, "sleep", waits.append)
    m.write_json(path, {"completed": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"completed": 1}
    assert len(calls) == 2 and waits == [.05]
    assert not path.with_suffix(".json.tmp").exists()


def test_atomic_json_persistent_permission_error_is_not_silenced(tmp_path, monkeypatch):
    calls, waits = [], []
    def denied(source, target):
        calls.append(target)
        raise PermissionError("synthetic persistent denial")
    monkeypatch.setattr(Path, "replace", denied)
    monkeypatch.setattr(m.time, "sleep", waits.append)
    with pytest.raises(PermissionError):
        m.write_json(tmp_path / "progress.json", {"completed": 1})
    assert len(calls) == 10 and waits == [.05]*9
