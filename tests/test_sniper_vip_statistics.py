"""Exercise the actual Pine accounting method bodies via a restricted translation.

This validates their arithmetic/state transitions, not Pine compilation or rendering.
Only the small assignment/if/ternary subset used by these two methods is translated.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from forextester_backtest.sniper import method_from_source


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "scripts/tradingview/sniper_vip_pro_reconstruction.pine"
).read_text(encoding="utf-8")


def load_accounting_method(name, arguments):
    return method_from_source(SOURCE, name, arguments)


start_sample = load_accounting_method("startSample", "this, direction, signalBar, target, stopPrice")
observe = load_accounting_method("observe", "this, barNumber, barHigh, barLow")


def sample(side=1, target=110, stop=95):
    result = SimpleNamespace(wins=0, losses=0, pendingSide=0)
    start_sample(result, side, 10, target, stop)
    return result


@pytest.mark.parametrize(
    "side,target,stop,high,low,wins,losses",
    [
        (1, 110, 95, 110, 99, 1, 0),
        (-1, 90, 105, 101, 90, 1, 0),
        (1, 110, 95, 105, 95, 0, 1),
        (-1, 90, 105, 105, 95, 0, 1),
        (1, 110, 95, 111, 94, 0, 1),
        (-1, 90, 105, 106, 89, 0, 1),
        (1, 110, 95, 109, 96, 0, 0),
        (-1, 90, 105, 104, 91, 0, 0),
    ],
)
def test_long_short_exact_touches_stop_priority_and_pending(side, target, stop, high, low, wins, losses):
    result = sample(side, target, stop)
    observe(result, 11, high, low)
    assert (result.wins, result.losses) == (wins, losses)
    assert result.pendingSide == (0 if wins + losses else side)


def test_entry_bar_is_never_scored():
    result = sample()
    observe(result, 10, 120, 80)
    assert (result.wins, result.losses, result.pendingSide) == (0, 0, 1)


def test_resolved_sample_is_not_counted_again_and_counts_survive_next_entry():
    result = sample()
    observe(result, 11, 111, 100)
    observe(result, 12, 120, 80)
    assert (result.wins, result.losses) == (1, 0)
    start_sample(result, -1, 13, 90, 105)
    observe(result, 14, 106, 100)
    assert (result.wins, result.losses, result.pendingSide) == (1, 1, 0)


def test_tp1_success_does_not_make_tp2_or_tp3_a_win():
    results = [sample(target=target) for target in (105, 110, 115)]
    for result in results:
        observe(result, 11, 106, 99)
        observe(result, 12, 104, 94)
    assert [(r.wins, r.losses) for r in results] == [(1, 0), (0, 1), (0, 1)]


def test_initial_target_is_preserved_across_price_tracker_rolls():
    # The tracker might replace TP3 with 125 after TP1=105 is hit.
    result = sample(target=115)
    observe(result, 11, 106, 99)
    observe(result, 12, 116, 100)
    assert result.initialTarget == 115
    assert (result.wins, result.losses) == (1, 0)
    rolling = SOURCE.split("if rollTargets and", 1)[1].split("else if touch3", 1)[0]
    assert "startSample" not in rolling


def test_statistics_are_wired_only_to_confirmed_in_range_accepted_signals():
    observers = SOURCE.split("// Observe BEFORE", 1)[1].split("// Signal calculation", 1)[0]
    assert "if barstate.isconfirmed" in observers
    assert "if time_close >= statsStart and time_close <= statsEnd" in observers
    for number in (1, 2, 3):
        assert f"tp{number}Stats.observe(bar_index, high, low)" in observers
        assert SOURCE.count(f"tp{number}Stats.startSample(") == 1
    entry = SOURCE.split("if side == 0 and not closedThisBar", 1)[1].split("barcolor(", 1)[0]
    assert "if time_close >= statsStart and time_close <= statsEnd" in entry
    assert "sampledSignals += 1" in entry
    assert "tp3Stats.startSample(side, bar_index, target3, stop)" in entry
    assert "int settled = wins + losses" in SOURCE
    assert 'settled > 0 ? str.tostring(100.0 * wins / settled, "#.0") + "%" : "—"' in SOURCE
