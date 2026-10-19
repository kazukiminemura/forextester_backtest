import numpy as np
import pytest

from scripts import research_bb_confirm_rr_extend as m


def fixture():
    f = np.zeros((7, 15), dtype=float)
    f[:, :4] = [100, 100.2, 99.8, 100]
    f[:, 4], f[:, 5], f[:, 6] = 100, 101, 99
    f[:, 7:10] = 1
    f[:, 10:14] = 0
    times = np.arange(7, dtype=np.int64) * 300
    # Buy setup: band touch -> directional inside-band confirmation -> strict later break.
    f[1, 2], f[1, 6] = 98.5, 99
    f[2, :4] = [99.0, 99.5, 98.9, 99.4]
    f[2, 4:7] = [100, 101, 99]
    f[3, :4] = [99.4, 100.1, 99.2, 99.9]
    f[3, 4:7] = [100, 101, 99]
    f[4, :4] = [99.9, 100.2, 99.5, 100.0]
    f[4, 4:7] = [100, 101, 99]
    # For this direct extractor fixture, avoid additional bands and context triggers.
    return f, times


def test_rr_tick_rounding_fixed_stop_and_extended_target_both_sides():
    for side in (1, -1):
        entry, center, pip, tick = 100.0, 100.05 if side == 1 else 99.95, .01, .001
        previous = None
        for rr in (1.0, 1.25, 1.5):
            stop, target, risk_pips, actual_rr, risk_ticks, reward_ticks = m.target_stop(entry, center, side, pip, tick, rr)
            assert risk_ticks == 50
            assert risk_pips == pytest.approx(5.0)
            assert actual_rr >= rr
            assert side * (entry - stop) == pytest.approx(.05)
            if previous is not None:
                assert stop == previous[0]
                assert side * (target - entry) >= side * (previous[1] - entry)
            previous = stop, target


def test_target_stop_rejects_wrong_side_and_invalid_rr():
    assert m.target_stop(100.0, 99.0, 1, .01, .001, 1.0) is None
    with pytest.raises(ValueError):
        m.replay(np.zeros((1, 15)), np.array([0]), .01, .001, 0, 300, 2.0, 1.0)


def test_signal_extractor_emits_only_strict_later_break_candidate():
    f, times = fixture()
    signals = m.baseline_signals(f, times, 0, 2100, .01, .001)
    assert all(s["index"] > 0 for s in signals)
    for signal in signals:
        assert signal["side"] in (-1, 1)
        assert signal["reference"] > 0
        assert np.isfinite(signal["center"])


def forced_signal(monkeypatch):
    monkeypatch.setattr(m, "baseline_signals", lambda *args: [{
        "index": 0, "side": 1, "reference": 99.9, "center": 100.05,
        "room_center": 100.05,
    }])


def test_replay_fixed_stop_and_target_extension_changes_hit(monkeypatch):
    f, times = fixture()
    forced_signal(monkeypatch)
    f[0, :4] = [100, 100.01, 99.99, 100]
    f[1, :4] = [100, 100.01, 99.99, 100]
    f[2, :4] = [100, 100.06, 99.99, 100.02]
    f[3, :4] = [100, 100.02, 99.90, 100]
    low, _ = m.replay(f, times, .01, .001, 0, 2100, 1.0, 0.0)
    high, _ = m.replay(f, times, .01, .001, 0, 2100, 1.5, 0.0)
    assert low and high
    assert low[0]["stop"] == high[0]["stop"]
    assert low[0]["target"] < high[0]["target"]
    assert low[0]["exit_reason"] == "target"
    assert high[0]["exit_reason"] == "stop"


def test_dual_touch_is_stop_first_and_cost_subtracted_once(monkeypatch):
    f, times = fixture()
    forced_signal(monkeypatch)
    f[0, :4] = [100, 100.01, 99.99, 100]
    f[1, :4] = [100, 100.2, 99.8, 100]
    trades, _ = m.replay(f, times, .01, .001, 0, 2100, 1.0, 1.2)
    assert trades[0]["exit_reason"] == "stop"
    assert trades[0]["both_hit"] is True
    assert trades[0]["net_pips"] == pytest.approx(trades[0]["gross_pips"] - 1.2)


def test_gap_exit_fills_actual_open(monkeypatch):
    f, times = fixture()
    forced_signal(monkeypatch)
    f[0, :4] = [100, 100.01, 99.99, 100]
    f[1, :4] = [99.9, 100.0, 99.8, 99.95]
    trades, _ = m.replay(f, times, .01, .001, 0, 2100, 1.0, 1.0)
    assert trades[0]["exit_reason"] == "gap_stop"
    assert trades[0]["exit"] == pytest.approx(99.0)


def test_open_trade_mark_includes_cost_without_forced_close(monkeypatch):
    f, times = fixture()
    forced_signal(monkeypatch)
    f[0, :4] = [100, 100.01, 99.99, 100]
    f[1:, :4] = [100, 100.01, 99.99, 100]
    trades, diag = m.replay(f, times, .01, .001, 0, 2100, 1.0, 1.0)
    assert trades == []
    assert diag["open_side"] == 1
    assert diag["open_net_pips"] == pytest.approx(-1.0)
