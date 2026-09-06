from datetime import datetime, timedelta
import math
from pathlib import Path

import pytest

from forextester_backtest.models import Bar
from forextester_backtest.sniper import RMA, SniperReplay, Technicals, expression, pine_defaults


SOURCE = (Path(__file__).resolve().parents[1] / "scripts/tradingview/sniper_vip_pro_reconstruction.pine").read_text(encoding="utf-8")
BASE = datetime(2020, 1, 1)


class FixedTechnicals:
    """Controlled TA outputs test the real Pine engine and complete price tracker."""
    def __init__(self, directions):
        self.directions = directions
        self.index = -1

    def update(self, bar):
        self.index += 1

    def atr(self, length):
        return 1.0

    def ema(self, close, length):
        return 99.0 if self.directions[self.index] == 1 else 101.0

    def rsi(self, close, length):
        return 60.0 if self.directions[self.index] == 1 else 40.0

    def dmi(self, *args):
        return (30, 10, 30) if self.directions[self.index] == 1 else (10, 30, 30)

    def supertrend(self, *args):
        return 99.0, -self.directions[self.index]


def replay(bars, directions, source=SOURCE, **kwargs):
    runner = SniperReplay(source, 0.01, **kwargs)
    runner.ta = FixedTechnicals(directions)
    runner.env["ta"] = runner.ta
    for i, (high, low) in enumerate(bars):
        runner.update(Bar(BASE + timedelta(minutes=i*15), 100, high, low, 100, 1))
    return runner


def test_real_pine_entry_targets_and_independent_outcomes():
    runner = replay([(110, 90), (101, 100), (100, 98)], [1, 1, 1])
    rows = [s.rows[0] for s in runner.samples]
    assert [r["target"] for r in rows] == [101, 102, 103]
    assert [r["outcome"] for r in rows] == ["win", "loss", "loss"]
    assert all(r["stop"] == 98.5 for r in rows)
    assert runner.env["side"] == 0
    assert runner.env["sampledSignals"] == 1


def test_short_real_tracker_and_same_bar_priority():
    runner = replay([(101, 99), (104, 96)], [-1, -1])
    for sample in runner.samples:
        assert sample.rows[0]["outcome"] == "loss"
        assert sample.rows[0]["ambiguous"]


def test_real_pine_rolling_targets_do_not_duplicate_samples():
    source = SOURCE.replace('input.bool(false, "TP到達後', 'input.bool(true, "TP到達後')
    runner = replay([(101, 99), (101, 100), (103, 100)], [1, 1, 1], source)
    assert runner.env["target3"] > 103
    assert runner.env["side"] == 1
    assert all(len(s.rows) == 1 and s.rows[0]["outcome"] == "win" for s in runner.samples)


def test_period_end_leaves_open_samples_pending():
    end = int(((BASE + timedelta(minutes=15)) - datetime(1970, 1, 1)).total_seconds()*1000)
    runner = replay([(101, 99), (104, 99)], [1, 1], end_ms=end)
    assert all(s.rows[0]["outcome"] is None for s in runner.samples)


def test_signal_close_edge_is_not_reissued_each_bar():
    runner = replay([(101, 99), (104, 99), (101, 99), (101, 99)], [1]*4)
    assert runner.env["sampledSignals"] == 1


def test_new_opposite_edge_on_exit_bar_is_not_accepted():
    runner = replay([(101, 99), (104, 99), (101, 99)], [1, -1, -1])
    assert runner.env["sampledSignals"] == 1


@pytest.mark.parametrize("code,expected", [
    ("true ? 1 : false ? 2 : 3", 1),
    ("false ? 1 : (true ? 2 : 3)", 2),
    ('max(1, true ? 2 : 3)', 2),
    ('"a?b:c"', "a?b:c"),
])
def test_source_bridge_nested_ternaries(code, expected):
    assert eval(expression(code), {"max": max}) == expected


def test_wilder_seed_ignores_na_and_uses_sma_then_recursive_average():
    rma = RMA(3)
    values = [rma.update(x) for x in [math.nan, 1, 2, 3, 6]]
    assert all(math.isnan(x) for x in values[:3])
    assert values[3:] == pytest.approx([2, 10/3])


def test_ta_warmup_and_uninterrupted_uptrend():
    ta = Technicals(pine_defaults(SOURCE))
    for i in range(60):
        p = 100 + i
        ta.update(Bar(BASE + timedelta(minutes=15*i), p, p+1, p-1, p+.5, 1))
        if i == 12:
            assert math.isnan(ta.a)
        if i == 13:
            assert ta.a == pytest.approx(2)
    assert ta.r == pytest.approx(100)
    assert ta.adx == pytest.approx(100)
    assert ta.direction == -1
    assert ta.e < 159.5


def test_modifying_source_threshold_changes_execution_without_python_rule_edit():
    source = SOURCE.replace('input.float(52, "買いRSI下限', 'input.float(70, "買いRSI下限')
    runner = replay([(101, 99), (104, 99)], [1, 1], source)
    assert runner.env["sampledSignals"] == 0


def test_period_summary_excludes_future_resolutions_and_pending_from_denominator():
    from scripts.research_sniper_vip import summarize
    rows = [
        dict(entry_time=10, exit_time=20, outcome="win", ambiguous=False),
        dict(entry_time=11, exit_time=21, outcome="loss", ambiguous=True),
        dict(entry_time=12, exit_time=100, outcome="win", ambiguous=False),
        dict(entry_time=13, exit_time=None, outcome=None, ambiguous=False),
        dict(entry_time=1, exit_time=15, outcome="win", ambiguous=False),
    ]
    result = summarize(rows, 10, 30)
    assert result == dict(signals=4, wins=1, losses=1, pending=2, win_rate_pct=50, ambiguous_stop_first=1)
    assert summarize(rows, 40, 50)["win_rate_pct"] is None


def test_period_start_does_not_turn_a_carried_trade_into_a_new_sample():
    start = int(((BASE + timedelta(minutes=30)) - datetime(1970, 1, 1)).total_seconds()*1000)
    runner = replay([(101, 99), (104, 99)], [1, 1], start_ms=start)
    assert runner.env["sampledSignals"] == 0
    assert runner.env["side"] == 0


def test_streaming_atr_and_dmi_match_existing_batch_implementation_after_warmup():
    from forextester_backtest.tamukai import _atr, _dmi
    bars = []
    ta = Technicals(pine_defaults(SOURCE))
    for i in range(1000):
        p = 100 + math.sin(i / 8) * 3 + math.sin(i / 37)
        bar = Bar(BASE + timedelta(minutes=15*i), p, p+.7, p-.6, p+.2, 1)
        bars.append(bar)
        ta.update(bar)
    plus, minus, adx = _dmi(bars)
    assert ta.a == pytest.approx(_atr(bars)[-1], abs=1e-10)
    assert ta.p == pytest.approx(plus[-1], abs=1e-10)
    assert ta.m == pytest.approx(minus[-1], abs=1e-10)
    assert ta.adx == pytest.approx(adx[-1], abs=1e-10)
