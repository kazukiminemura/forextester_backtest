"""Causal day/hour boundaries and unchanged RR1 accounting, on synthetic prices."""
import copy
import json

import numpy as np
import pytest

from scripts import research_yosuga_daily_time as y


def sample(n=600, start="2020-01-01"):
    times = int(np.datetime64(start, "s").astype(int))+np.arange(n, dtype=np.int64)*300
    op = 100+np.arange(n)*.01
    prices = np.column_stack((op, op+.03, op-.03, op+.02))
    complete = np.ones(n, dtype=bool)
    return times, prices, complete


def signal(times, prices, i=310, side=1, risk=1.):
    return dict(index=i, side=side, stop=float(prices[i, 3]-side*risk),
                line_target=float(prices[i, 3]+side*5), signal_time=int(times[i]+300),
                setup_index=max(0, i-15), setup_level=100., retest_index=i-10,
                turn_index=i-8, pullback_origin=i-4, pullback_confirm=i-2,
                line_origin=i-20, line_confirm=i-18)


def run_sim(t, p, c, arm="combined", candidates=None, cost=.1, ctx=None):
    candidates = [signal(t, p)] if candidates is None else candidates
    return y.simulate(t, p, candidates, np.zeros(len(t)), 1., .01, arm, cost,
                      int(t[0]), int(t[-1]+300), c, y.context(t, p, c) if ctx is None else ctx)


def test_daily_uses_previous_calendar_day_and_no_weekend_fallback():
    t, p, c = sample()
    ctx = y.context(t, p, c)
    s = signal(t, p)
    reason, evidence = y.signal_gate(t, p, s, ctx, 1., .1, "daily")
    assert reason == "allowed"
    assert evidence["daily_previous_day"] == t[0]//86400
    # Keep a high-quality Friday, then Monday; Sunday is absent.
    t[288:] += 2*86400
    ctx = y.context(t, p, c)
    assert y.signal_gate(t, p, s, ctx, 1., .1, "daily")[0] == "daily_missing_previous_day"


def test_daily_quality_checks_observed_complete_and_internal_gap():
    t, p, c = sample()
    day = int(t[0]//86400)
    c[:29] = False
    assert not y.context(t, p, c)["days"][day]["quality_ok"]
    c[28] = True
    assert y.context(t, p, c)["days"][day]["quality_ok"]
    # Seven removed consecutive slots cause a 40-minute gap; counts still pass.
    keep = np.ones(len(t), dtype=bool)
    keep[100:107] = False
    ctx = y.context(t[keep], p[keep], np.ones(keep.sum(), dtype=bool))
    assert ctx["days"][day]["observed_bars"] == 281
    assert not ctx["days"][day]["quality_ok"]
    # 18 missing isolated slots leave exactly 270 observed bars and pass.
    keep[:] = True
    keep[np.arange(10, 190, 10)] = False
    assert y.context(t[keep], p[keep], c[keep])["days"][day]["quality_ok"] is False  # complete count now <260
    assert y.context(t[keep], p[keep], np.ones(keep.sum(), dtype=bool))["days"][day]["quality_ok"]


def test_daily_first_and_last_slot_quality_boundaries():
    t, p, c = sample()
    day = int(t[0]//86400)
    keep = np.ones(len(t), dtype=bool)
    keep[:6] = False
    keep[282:288] = False
    assert y.context(t[keep], p[keep], c[keep])["days"][day]["quality_ok"]
    keep[6] = False
    assert not y.context(t[keep], p[keep], c[keep])["days"][day]["quality_ok"]
    keep[6] = True
    keep[281] = False
    assert not y.context(t[keep], p[keep], c[keep])["days"][day]["quality_ok"]


def test_hourly_exact_12_completed_consecutive_bars():
    t, p, c = sample()
    ctx = y.context(t, p, c)
    assert not ctx["hour_quality"][10] and ctx["hour_quality"][11]
    c[305] = False
    assert not y.context(t, p, c)["hour_quality"][310]
    c[305] = True
    t[305:] += 300
    assert not y.context(t, p, c)["hour_quality"][310]
    assert y.context(t, p, c)["hour_quality"][316]


def test_flat_or_wrong_direction_disables_gates():
    t, p, c = sample()
    s = signal(t, p, side=-1)
    ctx = y.context(t, p, c)
    assert y.signal_gate(t, p, s, ctx, 1., .1, "daily")[0] == "daily_direction"
    assert y.signal_gate(t, p, s, ctx, 1., .1, "hourly")[0] == "hourly_direction"
    p[:] = 100.
    ctx = y.context(t, p, c)
    assert y.signal_gate(t, p, signal(t, p), ctx, 1., .1, "daily")[0] == "daily_efficiency"
    assert y.signal_gate(t, p, signal(t, p), ctx, 1., .1, "hourly")[0] == "hourly_efficiency"


def test_midnight_signal_bar_rejected_daily_but_not_hourly():
    t, p, c = sample()
    s = signal(t, p, i=575)
    ctx = y.context(t, p, c)
    assert y.signal_gate(t, p, s, ctx, 1., .1, "daily")[0] == "daily_entry_date_change"
    assert y.signal_gate(t, p, s, ctx, 1., .1, "combined")[0] == "daily_entry_date_change"
    assert y.signal_gate(t, p, s, ctx, 1., .1, "hourly")[0] == "allowed"


def test_signal_cost_limit_and_entry_cost_are_separate_causal_checks():
    t, p, c = sample()
    s = signal(t, p)
    ctx = y.context(t, p, c)
    assert y.signal_gate(t, p, s, ctx, 1., .2, "hourly")[0] == "allowed"
    assert y.signal_gate(t, p, s, ctx, 1., .201, "hourly")[0] == "signal_cost_risk"
    # Signal-close risk is 1, but the next open is only .4 above the stop.
    p[311] = [s["stop"]+.4, s["stop"]+.5, s["stop"]+.3, s["stop"]+.45]
    sim = run_sim(t, p, c, arm="hourly", candidates=[s], cost=.1)
    assert sim["ledger"][0]["signal_gate"] == "allowed"
    assert sim["ledger"][0]["signal_cost_risk"] == pytest.approx(.1)
    assert sim["ledger"][0]["status"] == "entry_cost_risk"
    assert sim["trades"] == []


def test_future_mutation_does_not_change_prior_close_decision():
    t, p, c = sample()
    s = signal(t, p)
    before = y.signal_gate(t, p, s, y.context(t, p, c), 1., .1, "combined")
    p[311:] *= 2
    c[311:] = False
    after = y.signal_gate(t, p, s, y.context(t, p, c), 1., .1, "combined")
    prefix = y.signal_gate(t[:311], p[:311], s, y.context(t[:311], p[:311], c[:311]), 1., .1, "combined")
    assert before == after == prefix


def test_all_allowed_filtered_accounting_matches_baseline_and_stays_open():
    t, p, c = sample()
    signals = [signal(t, p), signal(t, p, i=320)]
    baseline = run_sim(t, p, c, arm="baseline", candidates=signals)
    ctx = y.context(t, p, c)
    ctx["hour_quality"][311:] = False  # switch gate off while holding
    filtered = run_sim(t, p, c, candidates=signals, ctx=ctx)
    assert len(filtered["trades"]) == len(baseline["trades"]) == 1
    for key, value in baseline["trades"][0].items():
        assert filtered["trades"][0][key] == value
    np.testing.assert_array_equal(filtered["mtm"], baseline["mtm"])
    assert filtered["ledger"][1]["status"] == "occupied"
    assert filtered["ledger"][1]["signal_gate"] == "hourly_quality"
    assert filtered["summary"]["observed_days"] == 3
    assert filtered["summary"]["trading_days"] == 1


@pytest.mark.parametrize("bar,reason", [([103.31, 105., 101., 103.3], "stop"),
                                      ([101., 102., 100., 101.5], "gap_stop"),
                                      ([105., 106., 104., 105.5], "gap_target")])
def test_filtered_fill_order_matches_baseline(bar, reason):
    t, p, c = sample()
    p[312] = bar
    baseline = run_sim(t, p, c, arm="baseline")
    filtered = run_sim(t, p, c)
    assert filtered["trades"][0]["exit_reason"] == reason
    for key, value in baseline["trades"][0].items():
        assert filtered["trades"][0][key] == value
    np.testing.assert_array_equal(filtered["mtm"], baseline["mtm"])


def test_period_end_and_entry_gap_preserve_baseline_behavior():
    t, p, c = sample(315)
    baseline = run_sim(t, p, c, arm="baseline")
    filtered = run_sim(t, p, c)
    assert filtered["trades"][0]["exit_reason"] == "period_end"
    np.testing.assert_array_equal(filtered["mtm"], baseline["mtm"])
    t[311:] += 300
    assert run_sim(t, p, c)["ledger"][0]["status"] == "entry_gap"


def test_short_price_mirror_has_identical_gates_and_accounting():
    t, p, c = sample()
    long = run_sim(t, p, c)
    mirrored = 250-p[:, [0, 2, 1, 3]]
    short_signal = signal(t, mirrored, side=-1)
    short = run_sim(t, mirrored, c, candidates=[short_signal])
    assert short["ledger"][0]["signal_gate"] == "allowed"
    assert short["ledger"][0]["status"] == "entered"
    for key in ("entry_index", "exit_index", "exit_reason", "gross_r", "net_r", "risk_pips", "cost_pips"):
        expected = long["trades"][0][key]
        if isinstance(expected, float):
            assert short["trades"][0][key] == pytest.approx(expected)
        else:
            assert short["trades"][0][key] == expected
    np.testing.assert_allclose(short["mtm"], long["mtm"], rtol=0, atol=1e-12)


def test_entry_bar_incomplete_does_not_retroactively_cancel_signal():
    t, p, c = sample()
    c[311] = False
    sim = run_sim(t, p, c)
    assert sim["ledger"][0]["status"] == "entered"
    assert sim["trades"][0]["incomplete_m5_held"] == 1
    assert sim["summary"]["trades_exposed_to_incomplete_m5"] == 1


def test_training_selection_ignores_later_results_and_has_no_baseline_fallback():
    rows = []
    good = dict(trades=100, profit_factor_r=1.2, mean_net_r=.1, ci95_mean_r=[.01, .2],
                positive_pairs=4, leave_one_pair_min_net_r=.1, net_r=10.)
    for arm in y.ARMS[1:]:
        for cost in (1., 1.5):
            rows.append(dict(good, period="2020_2022", arm=arm, cost_multiplier=cost))
    assert y.select_training(rows)["selected"] == "daily"
    rows.append(dict(good, period="2025", arm="combined", cost_multiplier=1., mean_net_r=999.))
    assert y.select_training(rows)["selected"] == "daily"
    for row in rows:
        if row["period"] == "2020_2022":
            row["trades"] = 99
    assert y.select_training(rows)["selected"] is None


def test_protocol_rejects_gate_or_baseline_drift():
    protocol = json.loads((y.ROOT/"docs/quant_organization/experiments"/y.ID/"protocol.json").read_text(encoding="utf-8"))
    y.validate_protocol(protocol)
    for key, replacement in (("daily_rule", dict(y.DAILY_RULE, min_efficiency=.4)),
                             ("hourly_rule", dict(y.HOURLY_RULE, bars=10)),
                             ("selection_rule", dict(y.SELECTION_RULE, period="2025"))):
        altered = copy.deepcopy(protocol)
        altered[key] = replacement
        with pytest.raises(ValueError):
            y.validate_protocol(altered)
