"""Execute actual local Pine trade methods, not the TradingView runtime."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from forextester_backtest.models import Bar
from forextester_backtest.sniper import is_na, method_from_source, translate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/tradingview/gold_breakout55_pf_refined.pine").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "scripts"))
from research_sniper_daytrade import outcome  # noqa: E402


def method(name, args):
    result = method_from_source(SOURCE, name, args)
    result.__globals__.update(NAN=float("nan"), na=is_na, math=SimpleNamespace(min=min, max=max))
    return result


enter = method("enter", "this, direction, barNumber, barTime, dueTime, barOpen, signalAtr, costSpread")
observe = method("observe", "this, barTime, barOpen, barHigh, barLow, confirmed, costSpread")


def new_trade():
    block = re.search(r"^type GoldTrade\n((?:    [^\n]*\n)+)", SOURCE, re.M)[1]
    env = {"NAN": float("nan")}
    exec(compile(translate(block).replace("    ", ""), "<pine-defaults>", "exec"), {}, env)
    env.pop("NAN")
    return SimpleNamespace(**env)


def eligible(trade, bar_number, entry_hour, regular=True):
    expr = re.search(r"^bool canEnter = (.+)$", SOURCE, re.M)[1]
    return eval(expr, {"__builtins__": {}}, dict(trade=trade, bar_index=bar_number,
                                               entryHour=entry_hour, regularNextBar=regular))


@pytest.mark.parametrize("direction", [-1, 1])
def test_entry_prices_are_available_before_close_and_do_not_drift(direction):
    saved = new_trade()
    snapshots = []
    for confirmed, high, low in [(False, 100, 100), (False, 101, 99.5), (True, 101, 99.5)]:
        # Each realtime update restarts from the previous close, as Pine rollback does.
        trade = deepcopy(saved)
        enter(trade, direction, 205, 8, 20, 100, 2, .376)
        observe(trade, 8, 100, high, low, confirmed, .376)
        snapshots.append((trade.entry, trade.target, trade.stop, trade.count, trade.side))
    assert snapshots[0] == snapshots[1] == snapshots[2]
    assert trade.target - trade.entry == pytest.approx(direction * 6)
    assert trade.stop - trade.entry == pytest.approx(-direction * 3)
    assert trade.count == 0


def test_unconfirmed_touch_waits_for_stop_first_accounting():
    trade = new_trade()
    enter(trade, 1, 205, 8, 20, 100, 1, 0)
    observe(trade, 8, 100, 104, 100, False, 0)
    assert trade.side == 1 and trade.count == 0
    observe(trade, 8, 100, 104, 98, True, 0)
    assert trade.exitReason == "SL" and trade.lossesR == 1
    observe(trade, 9, 100, 104, 98, True, 0)
    assert trade.count == 1 and trade.exitReason == ""


def test_deadline_uses_open_even_before_bar_is_confirmed():
    saved = new_trade()
    enter(saved, 1, 205, 8, 20, 100, 1, .376)
    for confirmed in (False, True):
        trade = deepcopy(saved)
        observe(trade, 20, 101, 110, 90, confirmed, .376)
        assert trade.exitReason == "20時決済"
        assert trade.exitPrice == pytest.approx(101 - .0376)
        assert trade.count == 1 and trade.side == 0


def test_session_gap_cooldown_and_position_admission():
    trade = new_trade()
    assert eligible(trade, 205, 6)
    assert eligible(trade, 205, 15)
    assert not eligible(trade, 205, 5)
    assert not eligible(trade, 205, 16)
    assert not eligible(trade, 205, 8, regular=False)
    trade.lastEntry = 205
    assert not eligible(trade, 209, 8)
    assert eligible(trade, 210, 8)
    trade.side = -1
    assert not eligible(trade, 210, 8)
    # Check the actual caller: prior confirmed setup + ATR, new open, then exit.
    caller = SOURCE.split("var GoldTrade trade =", 1)[1].split('plot(fast,', 1)[0]
    assert "bool adoptedBuy = canEnter and buySetup[1]" in caller
    assert "bool adoptedSell = canEnter and sellSetup[1]" in caller
    assert ", open, a[1], spread)" in caller
    assert caller.index("trade.enter(") < caller.index("trade.observe(")
    assert "if barstate.isconfirmed" not in caller


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("spread", [0, .376, .752])
def test_actual_pine_exit_matches_frozen_research_across_paths(direction, spread):
    rng = np.random.default_rng(24)
    base = datetime(2020, 1, 1, 8)
    for _ in range(60):
        atr = float(rng.uniform(.5, 3))
        opens = 100 + np.cumsum(rng.normal(0, .7, 15))
        bars = [Bar(base + timedelta(hours=i), op, op + rng.uniform(0, 3),
                    op - rng.uniform(0, 3), op, 1) for i, op in enumerate(opens)]
        expected = outcome(bars, 0, direction, atr, spread, 60, 3, None)
        trade = new_trade()
        enter(trade, direction, 205, 8, 20, bars[0].open, atr, spread)
        for i, bar in enumerate(bars):
            observe(trade, 8+i, bar.open, bar.high, bar.low, True, spread)
            if trade.count:
                reason = {"TP": "target", "SL": "stop", "20時決済": "time"}[trade.exitReason]
                assert (i, reason) == (expected[0], expected[2])
                assert trade.gainsR - trade.lossesR == pytest.approx(expected[1])
                assert trade.wins == int(expected[1] > 0)
                break
        assert trade.count == 1


def test_missing_deadline_bar_records_late_exit_and_keeps_loss_costs():
    trade = new_trade()
    enter(trade, -1, 205, 8, 20, 100, 1, .376)
    observe(trade, 32, 100, 100, 100, False, .376)
    assert trade.late == 1 and trade.count == 1
    assert trade.wins == 0 and trade.lossesR > 0
