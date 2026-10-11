import numpy as np

from scripts import research_new_logic_20261011 as study


def fixture(n=22):
    times = np.arange(n)*900+study.core.epoch("2020-01-02T00:00")
    prices = np.tile([100., 100.2, 99.8, 100.], (n, 1))
    data = dict(times=times, prices=prices, complete=np.ones(n, bool), starts_at_open=np.ones(n, bool), observed_open_times=times.copy())
    sig = dict(sides=np.zeros((4, n), np.int8), stops=np.full((4, n), np.nan), atrs=np.full((4, n), np.nan), rooms=np.full((4, n), np.nan), thresholds=np.full((4, n), np.nan))
    sig["sides"][0, 0], sig["stops"][0, 0], sig["atrs"][0, 0], sig["thresholds"][0, 0] = 1, 99., 1., 99.9
    return data, sig


def replay(data, sig, rr=1, cash=False, start=None):
    return study.simulate(data, sig, 0, rr, data["times"][0] if start is None else start, data["times"][-1]+900, .02, .02, cash)


def test_next_open_and_exact_rr_with_same_bar_sl_priority():
    d, s = fixture()
    d["prices"][1] = [100., 103., 98., 101.]
    rows, _, _ = replay(d, s, rr=2)
    assert len(rows) == 1 and rows[0]["entry_time"] == d["times"][1]
    assert rows[0]["target"] == 102. and rows[0]["exit_price"] == 99. and rows[0]["reason"] == "sl"


def test_max_16_bars_and_no_prephase_entry():
    d, s = fixture()
    rows, _, _ = replay(d, s)
    assert rows[0]["reason"] == "max_16_bars"
    assert rows[0]["exit_time"] == d["times"][16]+900
    assert replay(d, s, start=d["times"][1])[0] == []


def test_missing_actual_open_cancels_entry():
    d, s = fixture()
    d["starts_at_open"][1] = False
    rows, _, account = replay(d, s)
    assert rows == [] and account["skipped"]["missing_entry"] == 1


def test_open_price_cost_floor_and_room_are_causal_common_rr():
    d, s = fixture()
    d["prices"][1, 0] = 99.1
    rows, _, info = replay(d, s)
    assert not rows and info["skipped"]["cost_floor"] == 1
    d["prices"][1, 0] = 100.
    s["rooms"][0, 0] = 101.5
    for rr in (1., 1.5, 2.):
        rows, _, info = replay(d, s, rr)
        assert not rows and info["skipped"]["insufficient_room"] == 1


def test_tp_gap_is_capped_and_adverse_gap_not_capped():
    d, s = fixture()
    d["prices"][2] = [103., 104., 102., 103.]
    assert replay(d, s)[0][0]["exit_price"] == 101.
    d["prices"][2] = [98., 99., 97., 98.]
    assert replay(d, s)[0][0]["exit_price"] == 98.


def test_incomplete_bar_exposure_is_reported():
    d, s = fixture()
    d["complete"][2] = False
    row = replay(d, s)[0][0]
    assert row["reason"] == "incomplete_bar_close" and row["incomplete_bars"] == 1


def test_cash_quantity_and_gap_floor_halt():
    d, s = fixture()
    d["prices"][2] = [50., 51., 49., 50.]
    rows, _, account = replay(d, s, cash=True)
    assert rows[0]["qty"] == 4000.
    assert account["stopped"] and account["final_equity_yen"] < 900000


def box_fixture():
    d, _ = fixture(40)
    d["prices"][:] = [100., 101., 99., 100.]
    d["prices"][26] = [100., 103., 100., 102.]
    d["prices"][27] = [101.2, 102., 100.9, 101.8]
    return d


def test_retest_has_delay_and_frozen_atr():
    d = box_fixture()
    s = study.signals(d["times"], d["prices"], d["complete"], .001, d["times"][0], d["times"][-1]+900)
    assert s["sides"][1, 26] == 1 and s["sides"][0, 26] == 0
    assert s["sides"][0, 27] == 1 and s["atrs"][0, 27] == s["atrs"][1, 26]
    assert s["stops"][0, 27] == 100.899


def test_gap_cancels_pending_and_future_cannot_change_prefix():
    d = box_fixture()
    d["times"][27:] += 900
    s = study.signals(d["times"], d["prices"], d["complete"], .001, d["times"][0], d["times"][-1]+900)
    assert s["sides"][0, 27] == 0
    d = box_fixture()
    full = study.signals(d["times"], d["prices"], d["complete"], .001, d["times"][0], d["times"][-1]+900)
    prefix = study.signals(d["times"][:28], d["prices"][:28], d["complete"][:28], .001, d["times"][0], d["times"][28])
    for key in full:
        np.testing.assert_allclose(prefix[key], full[key][:, :28], equal_nan=True)


def test_failed_first_touch_consumed():
    d = box_fixture()
    d["prices"][27, 3] = 101.
    d["prices"][28] = [101.2, 102., 100.9, 101.8]
    s = study.signals(d["times"], d["prices"], d["complete"], .001, d["times"][0], d["times"][-1]+900)
    assert not s["sides"][0, 27:29].any()


def test_payoff_uses_net_returns_and_zero_cells_are_undefined():
    rows = [dict(net_r=r, incomplete_bars=0, reason="test") for r in [1.8, -.9, -.9]]
    result = study.metrics(rows)
    assert result["realized_payoff_rr"] == 2. and result["pf"] == 1.
    assert study.metrics([])["realized_payoff_rr"] is None
