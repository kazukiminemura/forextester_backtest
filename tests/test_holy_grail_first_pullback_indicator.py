"""Pine structure and extracted fill-function parity; NOT TradingView compilation.

The deliberately small translator executes the actual two pure Pine function
bodies (typed assignments, if/else, boolean expressions, tuple return) in Python.
It does not interpret the full indicator or claim Pine runtime equivalence.
"""
from pathlib import Path
import random
import re

import pytest

from scripts.research_holy_grail_first_pullback import entry_fill, exit_fill


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "scripts/tradingview/holy_grail_first_pullback_rr1_indicator.pine").read_text(encoding="utf-8")


def extract_function(name):
    header, body = re.search(rf"^{name}\((.*?)\) =>\n((?:    .*\n)+)", SOURCE, re.M).groups()
    args = ", ".join(arg.split()[-1] for arg in header.split(","))
    lines = [f"def extracted({args}):"]
    for original in body.splitlines():
        indent = original[:len(original) - len(original.lstrip())]
        line = original.strip()
        line = re.sub(r"^(int|float|bool) ", "", line)
        line = line.replace(":=", "=")
        line = re.sub(r"\btrue\b", "True", line)
        line = re.sub(r"\bfalse\b", "False", line)
        line = re.sub(r"\bna\b", "None", line)
        if line.startswith("else if "):
            line = "elif " + line[8:] + ":"
        elif line.startswith("if "):
            line += ":"
        elif line == "else":
            line += ":"
        elif line.startswith("["):
            line = "return " + line
        lines.append(indent + line)
    scope = {}
    exec("\n".join(lines), scope)
    return scope["extracted"]


ENTRY = extract_function("f_entry")
EXIT = extract_function("f_exit")


def test_indicator_identity_state_and_notifications():
    assert SOURCE.startswith("//@version=6\n")
    assert "indicator(" in SOURCE and "overlay = true" in SOURCE
    heartbeat = 'plot(close, "Compiler output heartbeat", display = display.none)'
    assert heartbeat in SOURCE
    assert SOURCE.index(heartbeat) < SOURCE.index("f_entry(")
    assert "strategy." not in SOURCE
    assert "request.security" not in SOURCE and "lookahead_on" not in SOURCE
    assert "varip " not in SOURCE
    assert SOURCE.count("alertcondition(") == 4
    for token in ("if barstate.isconfirmed", "REJECTED_TRAINING_ONLY", "TV_UNVERIFIED",
                  "Strategy Tester非対応", "Entry候補 ", "Entry約定 ", "TP 1R ", "SL "):
        assert token in SOURCE


def test_causal_processing_and_signal_contract():
    for token in ("bar_index > pendingBar", "bar_index - pendingBar >= 3",
                  "lastExitBar != bar_index", "bar_index >= 249", "touch and not spent",
                  "adx14[1] <= 30 and adx14 > 30", "adx14 < 25 or dominance != direction",
                  "riskPrice := tradeDirection * (entryPrice - stopPrice)",
                  "targetPrice := entryPrice + tradeDirection * riskPrice"):
        assert token in SOURCE
    assert SOURCE.index("spent := true") < SOURCE.index("if away and direction")
    assert SOURCE.index("if pending and not inWindow") < SOURCE.index("if pending and bar_index > pendingBar")
    assert SOURCE.index("else if entryAction == 1") < SOURCE.index("bar_index - pendingBar >= 3")
    assert SOURCE.index("    if active\n") < SOURCE.index("    if not inWindow\n")
    assert SOURCE.index("    if not inWindow\n") < SOURCE.index("if touch and not spent")


@pytest.mark.parametrize("direction", [1, -1])
def test_actual_pine_entry_body_matches_frozen_python(direction):
    rng = random.Random(104)
    order = {"direction": direction, "trigger": 100., "stop": 100. - direction * 2.}
    prices = [96., 98., 100., 102., 104.] + [rng.uniform(94, 106) for _ in range(200)]
    for op in prices:
        for width in [0., 1., 3., 6.]:
            bar = [op, op + width, op - width, op]
            expected_action, expected_price, expected_at_open = entry_fill(order, bar)
            actual = ENTRY(direction, order["trigger"], order["stop"], *bar[:3])
            assert actual == [{"cancel": -1, "wait": 0, "fill": 1}[expected_action], expected_price, expected_at_open]


@pytest.mark.parametrize("direction", [1, -1])
@pytest.mark.parametrize("fresh", [False, True])
def test_actual_pine_exit_body_matches_frozen_python(direction, fresh):
    rng = random.Random(205)
    position = {"direction": direction, "stop": 100. - direction * 2., "target": 100. + direction * 2.}
    for op in [96., 98., 100., 102., 104.] + [rng.uniform(94, 106) for _ in range(200)]:
        for width in [0., 1., 3., 6.]:
            bar = [op, op + width, op - width, op]
            expected = exit_fill(position, bar, fresh)
            actual = EXIT(direction, position["stop"], position["target"], *bar[:3], fresh)
            if expected is None:
                assert actual == [0, None, False]
            else:
                price, reason, at_open = expected
                code = {"stop_gap": -2, "target_gap_capped": 2, "stop": -1, "both_stop_first": -1, "target": 1}[reason]
                assert actual == [code, price, at_open]


@pytest.mark.parametrize("direction", [1, -1])
def test_gap_entry_reanchors_rr1_then_same_bar_stop_wins(direction):
    trigger, stop = 100., 100. - direction * 2.
    op = trigger + direction
    action, entry, _ = ENTRY(direction, trigger, stop, op, 106., 94.)
    assert action == 1 and entry == op
    risk = direction * (entry - stop)
    target = entry + direction * risk
    assert risk == 3.
    assert target == 100. + direction * 4.
    assert EXIT(direction, stop, target, op, 106., 94., True) == [-1, stop, False]


def test_whole_order_history_and_explicit_cost_scope():
    assert "array.push(historyCounts, 3)" in SOURCE
    assert "array.set(historyCounts, array.size(historyCounts) - 1, 4)" in SOURCE
    assert "while array.size(historyCounts) > keepLevels" in SOURCE
    assert "for objectIndex = 1 to oldestCount" in SOURCE
    assert "exposureTime = exitAtOpen ? time : time_close" in SOURCE
    assert "roundtripPips + carryPips * chargedDays" in SOURCE
    assert "保有中は集計外" in SOURCE


def test_mapping_and_samples_exist():
    mapping = ROOT / "docs/quant_organization/experiments/holy_grail_first_pullback_20260913/indicator_mapping.md"
    text = mapping.read_text(encoding="utf-8")
    for token in ("TV_UNVERIFIED", "期間境界", "比較サンプル", "OHLC", "Strategy Tester"):
        assert token in text
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if not target.startswith("https://"):
            assert (mapping.parent / target).resolve().exists(), target
