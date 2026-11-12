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


def test_frozen_signal_features_are_unchanged():
    for signature in ['f_week(int', 'f_jstWeek(int', 'f_touch(int', 'f_weekend(int',
                      'f_deadline(int', 'f_profile(int', 'method detect(',
                      'method finishH4(']:
        assert block(PINE, signature) == block(ORIGINAL, signature)


def test_chart_keeps_current_prices_and_can_restore_historical_labels():
    render = block(PINE, 'method renderTradeLevels(')
    assert 'bool current = today or active' in render
    assert 'bool labelEnabled = enabled and (current or showHistoricalLabels or chartIsGoldUsd)' in render
    assert 'prefix + role + f_price(label.get_y(tag))' in render
    assert 'current and kind == 0 ? label.style_label_right : label.style_label_left' in render
    assert 'line.set_color(level, enabled ?' in render


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
    assert '価格/費用10%条件不成立' in process


def test_preentry_filters_guard_all_fill_paths():
    standalone = (ROOT / 'scripts/tradingview/patrick_vp_jst_reverse_cost10_scanner.pine').read_text(encoding='utf-8')
    for source, select_name, process_name, enter_name in [
        (PINE, 'selectAtOpen', 'process', 'enterPosition'),
        (PINE, 'scanSelectAtOpen', 'scanProcess', 'scanEnterPosition'),
        (standalone, 'selectAtOpen', 'process', 'enterPosition'),
    ]:
        select = block(source, f'method {select_name}(')
        process = block(source, f'method {process_name}(')
        assert 'e.pendingBidOpen := bidOpen' in select
        assert 'e.pendingBars := 0' in select and 'e.pendingAdverse := 0.0' in select
        assert 'insideva' in next(line for line in select.splitlines() if 'if geometry and' in line).lower()
        assert 'directionalMove = executionSide * (o - e.pendingBidOpen)' in process
        assert 'directionalMove >= filterCost' in process
        assert 'e.pendingAdverse <= directionalMove / 2' in process
        fill_guard = next(line for line in process.splitlines() if 'if originalGeometry' in line)
        assert 'insideva' in fill_guard.lower()
        fill_path = process[process.index(fill_guard):process.index(f'e.{enter_name}(t, actual)')]
        assert 'and aligned' in fill_path or 'else if not moveFits' in fill_path
        assert 'and pullbackFits' in fill_path or 'else if not pullbackFits' in fill_path
        assert 'completeWindow = e.pendingBars == 15' in process or 'if e.pendingBars != 15' in fill_path
        assert process.index(f'e.{enter_name}(t, actual)') < process.index('e.pendingBars += 1')
        assert 't == e.pendingT + e.pendingBars * MINUTE' in process


def test_signal_and_execution_sides_are_separate_and_levels_are_swapped():
    enter = block(PINE, 'method enterPosition(')
    assert 'e.side := -s.side' in enter
    assert 'e.stop := s.target' in enter
    assert 'e.target := e.pendingStop' in enter
    assert 'math.abs(quote - e.stop) + spread + 2 * slip + 3 * carry' in enter
    process = block(PINE, 'method process(')
    assert 'float planned = o + (e.pendingS.side == 1 ? spread : 0)' in process
    assert 'float actual = o + (executionSide == 1 ? spread : 0)' in process
    assert 'f_touch(s.side, s.target, h, l)' in block(PINE, 'f_markTouched(')
    assert 'f_touch(e.pendingS.side, e.pendingS.target, h, l)' in process
    assert 's.side == -1 ? p.vah : p.val' in block(PINE, 'method selectAtOpen(')


def test_current_extremes_cannot_enter_open_decision_and_sl_is_first():
    process = block(PINE, 'method process(')
    assert process.index('e.selectAtOpen(t, o)') < process.index('// INTRAMINUTE PATH:')
    assert process.index('// INTRAMINUTE PATH:') < process.index('// Only now may')
    mark = process.index('f_markTouched(')
    assert process.index('// Only now may') < mark
    assert mark < process.index('e.hh := math.max(e.hh, h)')
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
    assert 'bool showPanel = input.bool(false,' in PINE
    assert 'showPanel ? table.new(position.bottom_left' in PINE
    assert '研究未採用' in PINE and '2026 厳しめでPF低下' in PINE
    assert '6180' not in PINE and '0.946' not in PINE and '61.12' not in PINE
    assert 'strategy.entry' not in PINE and 'alert(' not in PINE


def test_integrated_scanner_loads_all_symbols_before_realtime_and_hides_closed_prices():
    scanner = PINE[PINE.index('// 9-symbol K10 scanner'):]
    assert len(re.findall(r'^string symbol\d+ = input\.symbol', PINE, re.M)) == 9
    assert 'for [index, scanSymbol] in scannerSymbols\n        [day,' in scanner
    assert 'request.security(scanSymbol, "1", f_scan(),' in scanner
    assert 'if barstate.islast\n            int rowDecisionAt' in scanner
    assert 'f_row(scannerPanel, index + 2' in scanner
    row = scanner[scanner.index('f_row(table'):]
    prices = next(line for line in row.splitlines() if 'bool showPrices =' in line)
    assert all(state in prices for state in ('SCAN_CANDIDATE', 'SCAN_FILLED', 'SCAN_HOLDING'))
    assert 'SCAN_TP' not in prices and 'SCAN_SL' not in prices
    assert 'エントリーチャンスなし（TP到達）' in row and 'エントリーチャンスなし（SL到達）' in row
