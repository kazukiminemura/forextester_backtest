"""Synthetic preregistration checks, never optimized on historical profits."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research_bb_alternatives import bands, execute, reentry_signals, wm_signals


def wm_fixture(side=1):
    close = np.array([100, 99, 98, 99, 100, 101, 100, 99, 97, 98, 99, 102, 102, 102.])
    f = np.zeros((len(close), 15))
    f[:, :4] = np.column_stack((close, close+.1, close-.1, close))
    bb = np.tile([100, 104, 96.], (len(close), 1))
    bb[2] = [100, 104, 99]
    if side == -1:
        f[:, :4] = np.column_stack((200-f[:, 0], 200-f[:, 2], 200-f[:, 1], 200-f[:, 3]))
        bb = np.column_stack((200-bb[:, 0], 200-bb[:, 2], 200-bb[:, 1]))
    return f, np.arange(len(close), dtype=np.int64)*300, bb


def test_bands_population_and_warmup():
    close = np.arange(30.)
    bb = bands(close)
    assert np.isnan(bb[:19]).all()
    assert bb[19, 0] == np.mean(close[:20])
    assert bb[19, 1] == pytest.approx(np.mean(close[:20])+2*np.std(close[:20]))
    for n in range(20, len(close)):
        np.testing.assert_array_equal(bb[:n], bands(close[:n]))


@pytest.mark.parametrize("side", [1, -1])
def test_reentry_uses_two_consecutive_closed_bars_and_no_candle_filter(side):
    f = np.zeros((3, 15))
    f[:, 3] = [98, 100, 100]
    f[:, 0] = 102  # bearish recovery allowed
    bb = np.tile([100, 101, 99.], (3, 1))
    if side == -1:
        f[:, 3] = 200-f[:, 3]
    ts = np.arange(3)*300
    assert reentry_signals(f, ts, bb, .01) == [dict(index=1, side=side, target=100.)]
    ts[1:] += 300
    assert reentry_signals(f, ts, bb, .01) == []


@pytest.mark.parametrize("side", [1, -1])
def test_wm_confirmed_pivots_and_neckline(side):
    f, ts, bb = wm_fixture(side)
    ss = wm_signals(f, ts, bb, .01)
    assert len(ss) == 1
    s = ss[0]
    assert [s[k] for k in ("first", "second", "confirmed", "index", "side")] == [2, 8, 10, 11, side]
    assert s["neckline"] == pytest.approx(101.1 if side == 1 else 98.9)
    assert s["stop_anchor"] == pytest.approx(96.89 if side == 1 else 103.11)
    assert "target" not in s


def test_wm_prefix_invariance_and_no_future_target_in_candidates():
    f, ts, bb = wm_fixture()
    full = wm_signals(f, ts, bb, .01)
    for n in range(1, len(f)+1):
        assert wm_signals(f[:n], ts[:n], bb[:n], .01) == [s for s in full if s["index"] < n]
    f[12:, 0] += 50
    assert wm_signals(f, ts, bb, .01) == full


def test_wm_break_can_be_on_confirmation_close_but_not_earlier():
    f, ts, bb = wm_fixture()
    f[10, :4] = [102, 102.1, 101.9, 102]
    assert wm_signals(f, ts, bb, .01)[0]["index"] == 10
    assert wm_signals(f[:10], ts[:10], bb[:10], .01) == []


@pytest.mark.parametrize("bar", [9, 10, 11])
def test_wm_cancel_precedes_break_in_confirmation_or_signal_bars(bar):
    f, ts, bb = wm_fixture()
    f[bar, 2] = 96.8
    assert wm_signals(f, ts, bb, .01) == []


def test_wm_gap_resets_pattern():
    f, ts, bb = wm_fixture()
    ts[6:] += 300
    assert wm_signals(f, ts, bb, .01) == []


def test_wm_requires_strict_pivot_inside_second_and_rebound():
    for modification in ("tie", "outside", "no_rebound"):
        f, ts, bb = wm_fixture()
        if modification == "tie":
            f[3, 3] = f[2, 3]
        elif modification == "outside":
            bb[8, 2] = 97
        else:
            bb[3:8, 0] = 103
        assert wm_signals(f, ts, bb, .01) == []


def test_wm_expiry_sixty_bars():
    f, ts, bb = wm_fixture()
    f = np.concatenate((f[:6], np.tile(f[6], (61, 1)), f[6:]))
    bb = np.concatenate((bb[:6], np.tile(bb[6], (61, 1)), bb[6:]))
    ts = np.arange(len(f))*300
    assert wm_signals(f, ts, bb, .01) == []


@pytest.mark.parametrize("side", [1, -1])
def test_wm_fill_rr1_and_sl_first_uses_actual_open(side):
    f, ts, bb = wm_fixture(side)
    signals = wm_signals(f, ts, bb, .01)
    f[12, :4] = [102, 109, 96, 102] if side == 1 else [98, 104, 91, 98]
    t = execute(f, ts, .01, .01, signals, "wm", 1., 0, 99999)["trades"][0]
    assert t["entry_index"] == 12
    assert t["stop"] == pytest.approx(signals[0]["stop_anchor"])
    assert t["target"] == pytest.approx(2*t["entry"]-t["stop"])
    assert t["effective_rr"] == pytest.approx(1.)
    assert t["exit_reason"] == "stop"
    assert t["net_r"] == pytest.approx(-1-1/t["risk_pips"])
    assert "target" not in signals[0]


@pytest.mark.parametrize("kind", ["gap", "wrong_side", "smallrisk"])
def test_wm_rejects_gap_wrongside_or_tiny_risk(kind):
    f, ts, bb = wm_fixture()
    signals = wm_signals(f, ts, bb, .01)
    if kind == "gap":
        ts[12:] += 300
    else:
        f[12, 0] = signals[0]["stop_anchor"] + (-.1 if kind == "wrong_side" else .02)
    result = execute(f, ts, .01, .01, signals, "wm", 1., 0, 99999)
    assert result["trades"] == []
    assert result["summary"]["open_side"] == 0
    assert result["summary"]["rejected_entry_gap" if kind == "gap" else "rejected_entry_room"] == 1


def test_annual_flat_does_not_carry_previous_pending_and_end_no_futurefill():
    f, ts, bb = wm_fixture()
    signals = wm_signals(f, ts, bb, .01)
    assert execute(f, ts, .01, .01, signals, "wm", 1., ts[12], 99999)["summary"]["accepted_candidates"] == 0
    assert execute(f, ts, .01, .01, signals, "wm", 1., 0, ts[12])["summary"]["pending_side"] == 1
