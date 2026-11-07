"""Structural contracts only; TradingView compile/display needs separate evidence."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PINE = (ROOT / 'scripts/tradingview/patrick_vp_jst_reverse_cost10_indicator.pine').read_text(encoding='utf-8')
ORIGINAL = (ROOT / 'scripts/tradingview/patrick_vp_jst_weekly_indicator.pine').read_text(encoding='utf-8')


def block(text, signature):
    start = text.index(signature)
    remaining = text[start:]
    match = re.search(r'\n(?=method |f_\w+\(|var Engine )', remaining[1:])
    return remaining[:match.start() + 1].rstrip() if match else remaining.rstrip()


def test_frozen_features_and_history_visibility_are_unchanged():
    for signature in ['f_week(int', 'f_jstWeek(int', 'f_touch(int', 'f_weekend(int',
                      'f_deadline(int', 'f_profile(int', 'method detect(',
                      'method finishH4(', 'method renderTradeLevels(']:
        assert block(PINE, signature) == block(ORIGINAL, signature)


def test_filter_is_fixed_and_candidate_and_fill_each_check_it():
    assert 'const float MIN_RISK_COST = 10.0' in PINE
    assert 'float filterCost = spread + 2 * slip + 3 * carry' in PINE
    select = block(PINE, 'method selectAtOpen(')
    process = block(PINE, 'method process(')
    assert 'math.abs(executionQuote - s.target) / filterCost >= MIN_RISK_COST' in select
    predicate = next(line for line in select.splitlines() if 'if geometry and' in line)
    assert 'executionGeometry and costFits' in predicate
    assert 'math.abs(quote - best) <= NEAR_ATR * s.a' in predicate
    assert select.index(predicate) < select.index('break')
    assert 'math.abs(actual - e.pendingS.target) / filterCost >= MIN_RISK_COST' in process
    assert 'if originalGeometry and executionGeometry and costFits' in process
    assert 'e.cancelPending("08:15 方向/費用10%条件不成立")' in process


def test_signal_and_execution_sides_are_separate_and_levels_are_swapped():
    enter = block(PINE, 'method enterPosition(')
    assert 'e.side := -s.side' in enter
    assert 'e.stop := s.target' in enter
    assert 'e.target := e.pendingStop' in enter
    assert 'math.abs(quote - e.stop) + spread + 2 * slip + 3 * carry' in enter
    process = block(PINE, 'method process(')
    assert 'float planned = o + (e.pendingS.side == 1 ? spread : 0)' in process
    assert 'float actual = o + (executionSide == 1 ? spread : 0)' in process
    assert 'f_touch(s.side, s.target, h, l)' in process
    assert 'f_touch(e.pendingS.side, e.pendingS.target, h, l)' in process
    assert 's.side == -1 ? p.vah : p.val' in block(PINE, 'method selectAtOpen(')


def test_current_extremes_cannot_enter_open_decision_and_sl_is_first():
    process = block(PINE, 'method process(')
    assert process.index('e.selectAtOpen(t, o)') < process.index('// INTRAMINUTE PATH:')
    assert process.index('// INTRAMINUTE PATH:') < process.index('// Only now may')
    assert process.index('// Only now may') < process.index('s.touched := true')
    assert process.index('s.touched := true') < process.index('e.hh := math.max(e.hh, h)')
    assert process.index('if stopHit') < process.index('else if targetHit')
    assert process.index('if t >= e.deadline') < process.index('"SL gap"')


def test_planned_and_executed_prices_use_actual_reverse_role():
    planned = block(PINE, 'method drawPending(')
    assert 'float executionTarget = e.pendingStop' in planned
    assert 'float executionStop = e.pendingS.target' in planned
    assert 'int executionSide = -e.pendingS.side' in planned
    assert 'f_price(executionTarget)' in planned and 'f_price(executionStop)' in planned
    enter = block(PINE, 'method enterPosition(')
    assert '"Entry " + (e.side == 1 ? "BUY " : "SELL ") + f_price(quote)' in enter
    assert '"TP " + f_price(e.target)' in enter and '"SL " + f_price(e.stop)' in enter
    assert 'e.pendingQuote := executionQuote' in block(PINE, 'method selectAtOpen(')


def test_dynamic_stats_and_usable_defaults_disclose_unvalidated_period():
    close = block(PINE, 'method closePosition(')
    assert 'if pnl > 0' in close and 'e.wins += 1' in close
    assert 'e.profitR += r' in close and 'e.lossR -= r' in close
    assert 'engine.profitR / engine.lossR' in PINE
    assert 'engine.profit / engine.loss' in PINE
    assert 'engine.wins / float(engine.closed) * 100' in PINE
    assert 'timestamp("01 Jan 2099 00:00 +0000")' in PINE
    assert 'bool showPanel = input.bool(true,' in PINE
    assert '研究未採用' in PINE and '後半収益未検証' in PINE
    assert '6180' not in PINE and '0.946' not in PINE and '61.12' not in PINE
    assert 'strategy.entry' not in PINE and 'alert(' not in PINE
