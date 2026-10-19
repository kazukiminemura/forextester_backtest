"""Local structure + independent streaming-anchor parity; NOT a Pine compiler."""
from pathlib import Path
import re

import numpy as np

from scripts.research_holy_grail_first_pullback import generate_setups


PINE = Path(__file__).resolve().parents[1] / "scripts/tradingview/holy_grail_first_pullback_rr1_research.pine"
SOURCE = PINE.read_text(encoding="utf-8")


def test_research_identity_and_close_only_entry_decisions():
    assert SOURCE.startswith("//@version=6")
    for text in ("REJECTED_TRAINING_ONLY", "TV_UNVERIFIED", "calc_on_order_fills = true",
                 "process_orders_on_close = false", "calc_on_every_tick = false",
                 "barstate.isconfirmed and not fillExecution and lastDecisionBar != bar_index"):
        assert text in SOURCE
    assert "request.security(" not in SOURCE
    assert "lookahead_on" not in SOURCE
    assert "alert(" not in SOURCE
    assert SOURCE.count("disable_alert = true") == 2


def test_date_window_is_global_and_has_a_real_local_block():
    decision = SOURCE.index("if closedDecision")
    window = SOURCE.index("bool inWindow = time >= startTime and time < endTime")
    branch = SOURCE.index("    if not inWindow")
    assert window < decision < branch
    assert "    if not inWindow\n        direction := 0\n        if pending\n" in SOURCE


def test_signal_contract_and_first_touch_consumption():
    for text in ("adx14[1] <= 30 and adx14 > 30", "adx14 < 25 or dominance != direction",
                 "bar_index >= 249", "bar_index > armBar", "low <= ema20 and ema20 <= high",
                 "low[1] > ema20[1] : high[1] < ema20[1]", "touch and not spent",
                 "high >= anchorExtreme", "low <= anchorExtreme"):
        assert text in SOURCE
    assert SOURCE.index("spent := true") < SOURCE.index("if away and direction * (close - ema20) > 0")
    assert SOURCE.index("spent := true") < SOURCE.index("if strategy.position_size == 0 and not pending")


def test_stop_entry_expiry_and_actual_fill_rr1():
    for text in ("bar_index - pendingBar >= 3", "lastExitBar != bar_index",
                 "high + syminfo.mintick : low - syminfo.mintick",
                 "stopPrice := pullbackExtreme - direction * syminfo.mintick",
                 "entryPrice := strategy.position_avg_price",
                 "riskPrice := tradeDirection * (entryPrice - stopPrice)",
                 "targetPrice := entryPrice + tradeDirection * riskPrice",
                 "qty_percent = 100", 'stop = triggerPrice'):
        assert text in SOURCE
    assert "trail_" not in SOURCE
    assert "strategy.close(" not in SOURCE


def test_labels_and_gross_net_cost_separation():
    for text in ('"Entry "', '"SL "', '"TP 1R "', '"TP仮1R "',
                 "format.mintick", "keepLevels * 3", "commission_value = 0",
                 "roundtripPips + carryPips * chargedDays", "Strategy Tester = コストなし"):
        assert text in SOURCE


def test_fill_callback_updates_drawings_outside_signal_decision_block():
    draw_start = SOURCE.index("\nif not na(entryLine) and")
    draw_end = SOURCE.index('\nplot(ema20', draw_start)
    draw_block = SOURCE[draw_start:draw_end]
    assert SOURCE.index("if closedDecision") < draw_start
    assert "closedDecision" not in draw_block
    assert "fillExecution" not in draw_block
    assert "float displayEntry = orderWasFilled ? entryPrice : triggerPrice" in draw_block
    for setter in ("line.set_y1(entryLine, displayEntry)", "line.set_y1(targetLine, targetPrice)",
                   "label.set_xy(entryLabel, endBar, displayEntry)", "label.set_xy(targetLabel, endBar, targetPrice)"):
        assert setter in draw_block
    assert "spent :=" not in draw_block and "direction :=" not in draw_block
    assert "strategy.entry(" not in draw_block


def test_mapping_links_only_existing_local_evidence():
    root = PINE.parents[2]
    mapping_path = root / "docs/quant_organization/experiments/holy_grail_first_pullback_20260913/pine_mapping.md"
    mapping = mapping_path.read_text(encoding="utf-8")
    assert "主担当作成" not in mapping
    assert "比較サンプルを参照" not in mapping
    for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", mapping):
        if not link.startswith("https://"):
            assert (mapping_path.parent / link).exists(), link
    references = re.findall(r"`(agent_runs/[^`]+\.json)`", mapping)
    assert references
    for reference in references:
        assert (root / reference).is_file(), reference


def streaming_setups(bars, features, point):
    """Independently model Pine's O(1) running pullback range, both directions."""
    direction, spent, anchor, pullback = 0, False, None, None
    found = {}
    for i in range(1, len(bars)):
        _, hi, lo, close = bars[i]
        adx, ema = features["adx"][i], features["ema"][i]
        dominance = int(np.sign(features["plus"][i] - features["minus"][i]))
        if direction and (adx < 25 or dominance != direction):
            direction = 0
        if not direction:
            if features["adx"][i-1] <= 30 < adx and dominance * (close-ema) > 0:
                direction, spent = dominance, False
                anchor, pullback = hi if direction == 1 else lo, None
            continue
        extreme = lo if direction == 1 else hi
        pullback = extreme if pullback is None else (min(pullback, extreme) if direction == 1 else max(pullback, extreme))
        away = bars[i-1, 2] > features["ema"][i-1] if direction == 1 else bars[i-1, 1] < features["ema"][i-1]
        if lo <= ema <= hi and not spent:
            spent = True
            if away and direction*(close-ema) > 0:
                found[i] = (direction, hi+point if direction == 1 else lo-point, pullback-direction*point)
        if (direction == 1 and hi >= anchor) or (direction == -1 and lo <= anchor):
            anchor, pullback = hi if direction == 1 else lo, None
    return found


def test_streaming_anchor_matches_python_sliced_range_for_both_directions():
    rng = np.random.default_rng(41028)
    for _ in range(20):
        n = 600
        close = rng.integers(90, 111, n).astype(float)
        bars = np.column_stack((close, close+rng.integers(0, 9, n), close-rng.integers(0, 9, n), close))
        f = {"ema": np.full(n, 100.0), "adx": rng.choice([24., 29., 31., 35.], n),
             "plus": rng.choice([10., 40.], n), "minus": np.full(n, 25.0)}
        expected, _, _ = generate_setups(bars, f, 0, n, True, 0.01, warmup=1)
        assert streaming_setups(bars, f, .01) == {
            i: (s["direction"], s["trigger"], s["stop"]) for i, s in expected.items()
        }


def test_invalid_first_touch_stays_consumed_in_streaming_port():
    bars = np.array([[11,12,11,11.5], [12,13,11,12], [11,12,9,9.5],
                     [11,12,11,11.5], [11,12,9,11]], dtype=float)
    f = {"ema": np.full(5, 10.), "adx": np.array([29.,31,32,32,32]),
         "plus": np.full(5, 40.), "minus": np.full(5, 10.)}
    assert not streaming_setups(bars, f, .1)
