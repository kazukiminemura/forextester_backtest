"""Structural Pine checks and independent OHLC decision model; not a Pine compiler."""
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/tradingview/bb3_reversal_confirmation_indicator.pine'


def decision(side, op, hi, lo, threshold, invalidation, prior_center, pip=.01, close=None):
    if (lo < invalidation if side == 1 else hi > invalidation):
        return 'cancel', None
    if not (hi > threshold if side == 1 else lo < threshold):
        return 'wait', None
    entry = max(op, threshold + .001) if side == 1 else min(op, threshold - .001)
    room = side * (prior_center-entry)/pip
    return ('signal' if room + 1e-9 >= 3 else 'distance'), entry


@pytest.mark.parametrize('side', [1, -1])
@pytest.mark.parametrize('close,expected', [
    (99.99, 'signal'), (100, 'signal'),
    (100.001, 'signal'), (100.07, 'signal'),
    (100.071, 'signal'), (100.10, 'signal'), (100.11, 'signal'),
])
def test_original_candidate_does_not_require_close_break_or_close_room(side, close, expected):
    op, hi, lo, center, invalidation = 99.99, 100.12, 99.98, 100.10, 99
    if side == -1:
        op, hi, lo, center, invalidation, close = (
            200-op, 200-lo, 200-hi, 200-center, 200-invalidation, 200-close)
    assert decision(side, op, hi, lo, 100, invalidation, center, close=close)[0] == expected


def test_gap_reference_gate_and_cancel_still_take_priority():
    assert decision(1, 100.09, 100.12, 99.98, 100, 99, 100.1, close=100.01)[0] == 'distance'
    assert decision(1, 99.99, 100.12, 98.9, 100, 99, 100.1, close=100.01)[0] == 'cancel'


@pytest.mark.parametrize('side', [1,-1])
def test_breakout_invalidation_gap_and_distance_reference(side):
    def check(op, hi, lo, target):
        if side == 1:
            return decision(1, op, hi, lo, 100, 99, target)
        return decision(-1, 200-op, 200-lo, 200-hi, 100, 101, 200-target)
    assert check(99.5,100,99,100.1)[0] == 'wait'  # equality not breakout
    assert check(99.5,100.01,98.9,100.1)[0] == 'cancel'  # both touched
    assert check(99.5,100.01,99,100.1)[0] == 'signal'
    state,entry=check(100.08,100.1,99.9,100.1)
    assert state == 'distance'  # gap consumes reward room
    assert entry == pytest.approx(100.08 if side==1 else 99.92)


def test_standalone_indicator_has_no_execution_or_pf_engine():
    s=PATH.read_text(encoding='utf-8')
    assert s.startswith('//@version=6\n')
    assert 'indicator(' in s and 'overlay=true' in s
    assert 'barstate.isconfirmed' in s
    assert 'strategy.entry(' not in s and 'strategy.exit(' not in s
    assert 'grossProfit' not in s
    assert 'request.security(' not in s.split('// Multi-symbol reversal scanner')[0]
    assert 'label.new(' in s and 'plot.style_linebr' in s
    assert 'alertcondition(' in s


def test_confirmed_separate_stages_and_fixed_invalidation_contract():
    s=PATH.read_text(encoding='utf-8').split('// Multi-symbol reversal scanner')[0]
    for token in ['low < cancelLevel : high > cancelLevel',
                  'bar_index > confirmedBar', 'bar_index > preparedBar',
                  'close > open : close < open', 'close > lower and close < upper',
                  'high > threshold : low < threshold', 'candidateCenter := basis[1]',
                  'candidateCheck(side, threshold, candidateCenter, pipSize)',
                  'reason != "" or candidateSide != 0',
                  'side == 0 and reason == "" and candidateSide == 0',
                  'cancelLevel := side == 1 ? low : high']:
        assert token in s
    assert s.index('if reason == ""\n            if not na(confirmedBar)') < s.index('else if na(confirmedBar)')
    assert s.count('cancelLevel :=') == 2  # initial extreme and clear only; never ratchet
    assert s.count('alertcondition(barstate.isconfirmed') == 2


@pytest.mark.parametrize('stamp,now,expected', [(1000,1000,False), (1000,601000,False),
    (1000,601001,True), (1001,1000,True)])
def test_scanner_staleness_boundary_reference(stamp,now,expected):
    assert (now-stamp>300*2000 or stamp>now) is expected


def test_scanner_priority_reference():
    def rank(state):
        return {3:0,2:1,1:2}.get(abs(state),3 if state==4 else 4 if state==0 else 5)
    states=[0,2,-3,1,3,-2,7,4]
    assert sorted(range(len(states)),key=lambda i:rank(states[i]))==[2,4,1,5,3,7,0,6]


def test_reversal_scanner_confirmed_symbol_local_state_and_ui():
    s=PATH.read_text(encoding='utf-8')
    core,scanner=s.split('// Multi-symbol reversal scanner',1)
    snapshot=scanner.split('scannerSnapshot() =>',1)[1].split('scannerName(',1)[0]
    assert scanner.count('input.symbol(')==11
    assert scanner.count('request.security(')==1
    assert 'lookahead=barmerge.lookahead_on, ignore_invalid_symbol=true' in scanner
    assert '[state[1], triggerText[1], invalidationText[1], distance[1], time_close[1], skip[1]]' in snapshot
    assert 'barstate.isconfirmed' not in snapshot
    assert 'table.new(position.bottom_right, 2, 7' in core
    assert 'table.new(position.bottom_left' not in core  # no competing scanner panel
    for token in ['low < invalidation : high > invalidation',
                  'bar_index > confirmed', 'bar_index > prepared',
                  'close > open : close < open', 'close > bottom and close < top',
                  'high > trigger : low < trigger', 'center[1] - reference',
                  'candidateCheck(setupSide, trigger, center[1], unit)',
                  'skip != "" or signal != 0',
                  'setupSide == 0 and skip == "" and signal == 0',
                  'invalidation := setupSide == 1 ? low : high',
                  'str.tostring(shownTrigger, format.mintick)']:
        assert token in snapshot
    for token in ['scannerPosition = input.string("左下"',
                  'position.bottom_left, 6, 13)', 'table.clear(scanner, 0, 0, 5, 12)',
                  'symbol == "" ? syminfo.tickerid : symbol',
                  'array.indexof(scannerSymbols, symbol) < i',
                  'timenow - stamp > timeframe.in_seconds() * 2000 or stamp > timenow',
                  '"買い・高値突破待ち"', '"売り・安値突破待ち"',
                  '"買い・陽線回帰待ち"', '"売り・陰線回帰待ち"',
                  '"OANDA:USDCAD"', '"確認足終了 JST"',
                  '"BUY候補（直前足）"', '"SELL候補（直前足）"']:
        assert token in scanner
    assert scanner.count('= scannerImpulse(')==4
    assert 'alert(' not in scanner and 'grossProfit' not in scanner


def test_chart_and_scanner_share_candidate_gate():
    s = PATH.read_text(encoding='utf-8')
    assert s.count('candidateCheck(') == 3  # one definition, two consumers
    helper = s.split('candidateCheck(int direction', 1)[1].split('var int side', 1)[0]
    assert 'close - trigger' not in helper and 'center - close' not in helper
    assert 'direction * (center - reference) / unit' in helper
    assert 'na(room) or room + 1e-9 < minCenterPips' in helper
    assert 'barstate.' not in helper


def test_entry_notifications_use_confirmed_candidate_only():
    s = PATH.read_text(encoding='utf-8')
    core, scanner = s.split('// Multi-symbol reversal scanner', 1)
    assert 'if barstate.isconfirmed and candidateSide != 0\n    alert(' in core
    assert core.count('alert.freq_once_per_bar_close') == 1
    assert '"BUYエントリー条件成立"' in core and '"SELLエントリー条件成立"' in core
    message = next(line for line in core.splitlines() if line.startswith('    alert('))
    for token in ['syminfo.tickerid', 'timeframe.period', 'candidateSide == 1 ? " BUY" : " SELL"',
                  'str.tostring(close, format.mintick)', 'str.format_time(time_close,',
                  '約定通知ではありません。']:
        assert token in message
    assert 'candidatePrice' not in message  # do not advertise retrospective price as entry fill
    assert 'alert(' not in scanner


def test_scanner_reuses_storage_but_keeps_full_history_requests():
    s = PATH.read_text(encoding='utf-8').split('var table scanner', 1)[1]
    arrays = [line for line in s.splitlines() if 'array<' in line and ' = array.' in line]
    assert len(arrays) == 11
    assert all(line.strip().startswith('var array<') for line in arrays)
    init = s.split('if barstate.isfirst\n', 1)[1].split('if showScanner\n', 1)[0]
    assert 'array.push(scannerIndices, i)' in init
    requests = s.split('    for i in scannerIndices\n', 1)[1].split('if barstate.islast\n    if not showScanner', 1)[0]
    assert requests.index('request.security(') < requests.index('        if barstate.islast\n')
    assert 'calc_bars_count' not in requests
    assert 'if barstate.islast\n        array.clear(scannerOrder)' in s
    assert 'if not showScanner\n        table.clear(' in s


@pytest.mark.parametrize('symbols', [
    ['A', 'B', 'C'], ['A', 'A', 'B'], ['', 'A', '', 'B'], ['A', '', 'A', ''],
])
def test_precomputed_scanner_indices_preserve_symbol_order(symbols):
    def prior_each_bar(raw):
        raw = list(raw)
        result = []
        for i, symbol in enumerate(raw):
            raw[i] = symbol or 'A'
            if raw.index(raw[i]) == i:
                result.append((i, raw[i]))
        return result
    normalized = [symbol or 'A' for symbol in symbols]
    indices = [i for i, symbol in enumerate(normalized) if normalized.index(symbol) == i]
    assert [(i, normalized[i]) for i in indices] == prior_each_bar(symbols)
