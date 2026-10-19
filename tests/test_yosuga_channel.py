"""Behavior checks: delayed evidence, state ordering, fills and costs."""
import numpy as np

from scripts import research_yosuga_channel as y


def fixture(n=30):
    times = int(np.datetime64("2020-01-01", "s").astype(int))+np.arange(n, dtype=np.int64)*300
    return times, np.tile([100., 100.2, 99.8, 100.], (n, 1))


def signal(i=0, side=1, stop=99., target=103.):
    return dict(index=i, side=side, stop=stop, line_target=target, signal_time=0,
                setup_index=0, setup_level=100., retest_index=0, turn_index=0,
                pullback_origin=0, pullback_confirm=0, line_origin=0, line_confirm=0)


def sim(prices, arm="pullback_rr1", cost=.2, side=1, times=None, turns=None, complete=None):
    if times is None:
        times = fixture(len(prices))[0]
    turns = np.zeros(len(times)) if turns is None else turns
    s = signal(side=side, stop=99 if side == 1 else 101, target=103 if side == 1 else 97)
    return y.simulate(times, prices, [s], turns, 1., .01, arm, cost, times[0], times[-1]+300, complete)


def test_aggregate_requires_exact_m5_triplet_and_full_m1_mask():
    t, p = fixture(12)
    p[0:3] = [[100, 103, 99, 102], [102, 104, 98, 101], [101, 102, 97, 98]]
    t15, p15, ends = y.aggregate_m15(t, p)
    np.testing.assert_array_equal(p15[0], [100, 104, 97, 98])
    assert ends.tolist() == [2, 5, 8, 11]
    mask = np.ones(12, dtype=bool)
    mask[4] = False
    assert y.aggregate_m15(t, p, mask)[2].tolist() == [2, 8, 11]
    assert y.aggregate_m15(np.delete(t, 1), np.delete(p, 1, axis=0))[2].tolist() == [4, 7, 10]


def test_pivot_delay_strict_ties_gap_and_missing_reset():
    t, p = fixture(10)
    p[2, 1] = 102
    s = y.structure(t, p, 300)
    assert np.isnan(s["high"][3]) and s["high"][4] == 102
    p[4, 1] = 102
    assert np.isnan(y.structure(t, p, 300)["high"][4])
    p[4, 1] = 100.2
    missing = np.ones(10, dtype=bool)
    missing[3] = False
    assert np.isnan(y.structure(t, p, 300, missing)["high"][4])
    t[5:] += 300
    assert np.isnan(y.structure(t, p, 300)["high"][5])


def test_first_break_initializes_then_opposite_break_reverses():
    t, p = fixture(12)
    p[2, 1] = 102
    p[4, 2] = 98
    p[7] = [100, 103, 99, 102.5]
    p[8] = [102.5, 103, 97, 97.5]
    s = y.structure(t, p, 300)
    assert s["direction"][7] == 1 and s["turn"][7] == 0
    assert s["turn"][8] == -1 and s["broken"][8] == 98


def test_candidate_nearest_line_one_tick_inside_and_room():
    t, p = fixture()
    setup = dict(index=0, level=100., retest=1)
    item, reason = y.candidate(5, 1, 99, setup, 2, 3, 5, t, p, [(102., 0, 2), (103., 1, 3)], .01)
    assert reason == "signal" and item["line_target"] == 101.99
    assert y.candidate(5, 1, 99, setup, 2, 3, 5, t, p, [(101., 0, 2)], .01)[1] == "signal_line_room"


def test_signal_needs_later_pullback_not_turn_and_allows_confirmation_close(monkeypatch):
    t, p = fixture(30)
    p[12, 2] = 99.6  # turn-time low reference 99
    p[15] = [100, 100.4, 99.9, 100.3]  # breach prior high after pivot confirmation
    original = y.structure

    def prepared(times, prices, width, complete=None):
        s = original(times, prices, width, complete)
        for key in ("turn", "direction"):
            s[key][:] = 0
        for key in ("confirmed_high", "confirmed_low"):
            s[key][:] = -1
        if width == 900:
            s["confirmed_high"][1] = 0
            s["turn"][2] = 1
            s["broken"][2] = 100.
        else:
            s["turn"][10] = 1
            s["low"][10] = 99.
            s["confirmed_low"][14] = 12
        return s

    # Forward historical resistance for the modelled M15 pivot.
    p[0, 1] = 104
    monkeypatch.setattr(y, "structure", prepared)
    book, _, _ = y.signals(t, p, .01)
    assert [s["index"] for s in book["immediate_turn_rr1"]] == [10]
    assert [s["index"] for s in book["pullback_rr1"]] == [15]
    s = book["pullback_rr1"][0]
    assert s["pullback_origin"] == 12 and s["pullback_confirm"] == 14 and abs(s["stop"]-99.59) < 1e-10
    p[14, 3], p[14, 1] = 100.3, 100.4
    assert y.signals(t, p, .01)[0]["pullback_rr1"][0]["index"] == 14


def test_gap_stop_actual_loss_and_same_bar_stop_priority():
    t, p = fixture(5)
    p[2] = [98, 102, 97, 100]
    trade = sim(p)["trades"][0]
    assert trade["exit_reason"] == "gap_stop" and trade["gross_r"] == -2 and trade["net_r"] == -2.2
    p[2] = [100, 102, 98, 100]
    assert sim(p)["trades"][0]["exit_reason"] == "stop"
    p[2] = [102, 103, 98, 100]
    assert sim(p)["trades"][0]["exit_reason"] == "gap_target"


def test_next_open_gap_cancel_period_end_and_costs():
    t, p = fixture(5)
    p[-1, 3] = 100.1
    trade = sim(p)["trades"][0]
    assert trade["exit_reason"] == "period_end" and abs(trade["net_r"]+.1) < 1e-10
    assert trade["exit_time"] == t[-1]+300
    assert sim(p)["mtm"][-1, 1] == trade["net_r"]
    t[1:] += 300
    out = sim(p, times=t)
    assert out["ledger"][0]["status"] == "entry_gap" and not out["trades"]


def test_reversal_exit_next_open_precedes_later_intrabar_stop():
    t, p = fixture(5)
    turns = np.zeros(5)
    turns[1] = -1
    p[2] = [100.5, 102, 98, 99]
    out = sim(p, arm="pullback_line_exit", turns=turns)
    assert out["trades"][0]["exit"] == 100.5 and out["trades"][0]["exit_reason"] == "opposite_turn"
    assert sim(p, turns=turns)["trades"][0]["exit_reason"] == "stop"


def test_sell_mirror_missing_bar_exposure_and_carry_are_separate():
    t, p = fixture(6)
    p[-1] = [100, 100.1, 99, 99.2]
    mask = np.ones(6, dtype=bool)
    mask[2] = False
    out = sim(p, side=-1, complete=mask)
    trade = out["trades"][0]
    assert trade["exit_reason"] == "target" and abs(trade["net_r"]-.8) < 1e-9
    assert out["summary"]["trades_exposed_to_incomplete_m5"] == 1
    assert out["summary"]["carry_1pip_per_day_net_r"] < out["summary"]["net_r"]


def test_full_signal_prefix_invariance_including_missing_bars():
    t, p = fixture(900)
    rng = np.random.default_rng(62)
    close = 100+np.cumsum(rng.normal(0, .2, len(t)))
    op = np.r_[100, close[:-1]]
    p = np.column_stack((op, np.maximum(op, close)+rng.uniform(.01, .15, len(t)),
                         np.minimum(op, close)-rng.uniform(.01, .15, len(t)), close))
    mask = np.ones(len(t), dtype=bool)
    mask[[200, 505]] = False
    full, turns, _ = y.signals(t, p, .01, mask)
    for n in (199, 401, 607, 899):
        prefix, prefix_turns, _ = y.signals(t[:n], p[:n], .01, mask[:n])
        np.testing.assert_array_equal(turns[:n], prefix_turns)
        for arm in y.ARMS:
            assert prefix[arm] == [s for s in full[arm] if s["index"] < n]


def test_shared_month_bootstrap_and_curve_carry_forward():
    start = int(np.datetime64("2020-01-01", "s").astype(int))
    end = int(np.datetime64("2020-03-01", "s").astype(int))
    trades = [dict(entry_time=start, net_r=1), dict(entry_time=start, net_r=-1)]
    out = y.bootstrap_months(trades, start, end)
    assert out["ci95_mean_r"] == [0., 0.] and out["monthly_trades"] == [2, 0]
    curve = y.combine_curves([np.array([[1., 1.], [3., 2.]]), np.array([[2., -1.], [3., -2.]])])
    np.testing.assert_array_equal(curve[:, 1], [1, 0, 0])


def test_m1_mask_preserves_float_boundary_and_marks_missing_internal_minute(tmp_path):
    times, _ = fixture(2)
    minutes = times[0]+np.arange(10)*60
    minutes = np.delete(minutes, 7)
    raw = np.zeros((len(minutes), 6), dtype="<f8")
    raw[:, 0] = minutes/86400+25569
    raw[0, 0] = np.nextafter(raw[0, 0], -np.inf)
    path = tmp_path/"Bars.dat"
    path.write_bytes(len(raw).to_bytes(4, "little")+raw.tobytes())
    mask = y.m1_completeness(dict(raw_path=str(path), raw_sha256=y.digest(path)), times)
    assert mask.tolist() == [True, False]
