"""Source contracts + Python reference examples, NOT a Pine compiler/runtime."""
from pathlib import Path
from itertools import product

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'scripts/tradingview/bb3_context_pf_indicator.pine').read_text(encoding='utf-8')


def reference_fill(side, opening, high, low, target, stop):
    gap_stop = stop is not None and (opening <= stop if side == 1 else opening >= stop)
    gap_target = opening >= target if side == 1 else opening <= target
    hit_stop = stop is not None and (low <= stop if side == 1 else high >= stop)
    hit_target = high >= target if side == 1 else low <= target
    price = opening if gap_stop or gap_target else stop if hit_stop else target if hit_target else None
    return price, gap_stop or (not gap_target and hit_stop)


@pytest.mark.parametrize('side,opening,high,low,target,stop,expected', [
    (1, 100, 103, 99, 102, 98, (102, False)),
    (-1, 100, 101, 97, 98, 102, (98, False)),
    (1, 100, 103, 97, 102, 98, (98, True)),
    (-1, 100, 103, 97, 98, 102, (102, True)),
    (1, 97, 104, 96, 102, 98, (97, True)),
    (-1, 103, 104, 96, 98, 102, (103, True)),
    (1, 103, 104, 97, 102, 98, (103, False)),
    (-1, 97, 103, 96, 98, 102, (97, False)),
    (1, 100, 101, 90, 102, None, (None, False)),
    (-1, 100, 110, 99, 98, None, (None, False)),
    (1, 100, 102, 99, 102, None, (102, False)),
    (-1, 100, 101, 98, 98, None, (98, False)),
])
def test_reference_fill_cases(side, opening, high, low, target, stop, expected):
    assert reference_fill(side, opening, high, low, target, stop) == expected


def test_pine_fill_contract_matches_reference():
    for line in [
        'bool gapStop = not na(stop) and (side == 1 ? barOpen <= stop : barOpen >= stop)',
        'bool gapTarget = side == 1 ? barOpen >= target : barOpen <= target',
        'bool hitStop = not na(stop) and (side == 1 ? barLow <= stop : barHigh >= stop)',
        'bool hitTarget = side == 1 ? barHigh >= target : barLow <= target',
        'float price = gapStop or gapTarget ? barOpen : hitStop ? stop : hitTarget ? target : na',
        'bool stopped = gapStop or (not gapTarget and hitStop)',
    ]:
        assert line in SOURCE


def test_indicator_only_and_delayed_state_machine():
    assert SOURCE.startswith('//@version=6\nindicator(')
    assert 'strategy(' not in SOURCE and 'strategy.' not in SOURCE
    assert 'varip ' not in SOURCE
    for token in ['if barstate.isconfirmed\n    if tradeSide == 0',
                  'bar_index > pendingBar', 'entryPrice := open',
                  'targetPrice := pendingTarget', 'bar_index > armedBar',
                  'tradeSide == 0 and pendingSide == 0 and not exited',
                  'if barstate.isconfirmed and signalSide != 0']:
        assert token in SOURCE
    assert SOURCE.index('[fillPrice, stopped] = exitFill(') < SOURCE.index('targetPrice := basis')
    assert SOURCE.index('targetPrice := basis') < SOURCE.index('pendingTarget := basis')
    assert SOURCE.count('alertcondition(') == 3
    assert '\\\\n' not in SOURCE


def test_filters_and_multi_pair_support_preserved():
    for token in ['ta.highest(high[1], lookback)', 'ta.lowest(low[1], lookback)',
                  'recentImpulse(breakUp, priorHigh, true)',
                  'recentImpulse(breakDown, priorLow, false)',
                  'recentImpulse(roundUp, nextRound, true)',
                  'recentImpulse(roundDown, priorRound, false)',
                  '(syminfo.currency == "JPY" ? 0.01 : 0.0001) : manualPip',
                  'reason != "" or signalSide != 0',
                  'both or manualPause or explained']:
        assert token in SOURCE
    assert SOURCE.count('input.time(') == 0
    assert 'syminfo.basecurrency == "USD"' not in SOURCE


def test_economic_event_code_removed():
    for token in ['newsBlocked', 'inEvent', 'event1', 'event2', 'event3',
                  'beforeMinutes', 'afterMinutes', 'timestamp(', 'bgcolor(',
                  '指標', 'ニュース', 'group=gn']:
        assert token not in SOURCE
    assert 'bool manualPause = input.bool(false,' in SOURCE


def test_costs_and_pf_reference():
    for token in ['spreadPips + 2 * slipPips + feePips',
                  'side * (exit - entry) / unit - cost',
                  'grossProfit += math.max(resultPips, 0)',
                  'grossLoss += math.max(-resultPips, 0)',
                  'winCount += resultPips > 0 ? 1 : 0',
                  'grossLoss > 0 ? grossProfit / grossLoss : na',
                  'closedCount == 0', '算出不能（損失なし）',
                  '含み損益 pips（PF対象外）']:
        assert token in SOURCE
    cost = 1.2 + 2 * 0.1
    returns = [side * (exit_price - entry) / unit - cost for side, entry, exit_price, unit in [
        (1, 150, 150.10, 0.01), (-1, 1.10, 1.101, 0.0001),
        (1, 150, 150, 0.01),
    ]]
    assert returns == pytest.approx([8.6, -11.4, -1.4])
    profit = sum(max(x, 0) for x in returns)
    loss = sum(max(-x, 0) for x in returns)
    assert profit / loss == pytest.approx(8.6 / 12.8)


def preparation_reference(armed, *, compact, ready, gap, pause, buy_explained,
                          sell_explained, expired, center, opposite, later,
                          require_return, returned, touch_buy, touch_sell):
    """Old/new control flow mirrors, not execution of the Pine source."""
    prep = signal = 0
    reason = ''
    if not ready or gap:
        armed = 0
    handled = False
    if ready and armed:
        explained = buy_explained if armed == 1 else sell_explained
        if compact:
            reason = ('pause' if pause else 'break' if explained else 'expired' if expired
                      else 'center' if center else 'opposite' if opposite else '')
            if not reason and later and (not require_return or returned):
                signal = armed
            if reason or signal:
                armed = 0
        else:
            if pause or explained or expired or center or opposite:
                reason = ('pause' if pause else 'break' if explained else 'expired' if expired
                          else 'center' if center else 'opposite')
                armed = 0
                handled = True
            elif later:
                if not require_return or returned:
                    signal = armed
                    armed = 0
                    handled = True
    can_prepare = not reason and not signal if compact else not handled
    if ready and armed == 0 and can_prepare and (touch_buy or touch_sell):
        both = touch_buy and touch_sell
        explained = buy_explained if touch_buy else sell_explained
        if both or pause or explained:
            reason = 'both' if both else 'pause' if pause else 'break'
        else:
            armed = prep = 1 if touch_buy else -1
    return armed, prep, signal, reason


def test_preparation_old_new_exhaustive_reference_equivalence():
    names = ('ready', 'gap', 'pause', 'buy_explained', 'sell_explained', 'expired',
             'center', 'opposite', 'later', 'require_return', 'returned', 'touch_buy', 'touch_sell')
    for armed in (-1, 0, 1):
        for flags in product((False, True), repeat=len(names)):
            args = dict(zip(names, flags))
            assert preparation_reference(armed, compact=False, **args) == preparation_reference(armed, compact=True, **args)


def test_compact_structure_and_safety_guards():
    assert len(SOURCE.splitlines()) <= 235
    assert SOURCE.count('bool gap =') == 1
    assert SOURCE.count('table.cell(') == 2
    assert SOURCE.count('tableRow(notice,') == 9
    for redundant in ['bool entered', 'bool skipped', 'bool handled', 'bool candidateBuy', 'bool prepBuy']:
        assert redundant not in SOURCE
    assert 'reason == "" and bar_index > armedBar and (not requireReturn or (close > lower and close < upper))' in SOURCE
    # Keep these calls unconditional: each has independent persistent state.
    for call in ['recentHighBreak', 'recentLowBreak', 'recentRoundUp', 'recentRoundDown']:
        assert '\nbool ' + call + ' = recentImpulse(' in SOURCE


def test_profit_and_entry_flag_simplification_equivalence():
    for value in (-100.0, -0.1, 0.0, 0.1, 100.0):
        old = (value if value > 0 else 0, -value if value < 0 else 0, int(value > 0))
        assert old == (max(value, 0), max(-value, 0), int(value > 0))
    # After an entry, either it remains open or it has exited on the same bar.
    for entered, exited, side in [(False, False, 0), (False, False, 1),
                                 (False, True, 0), (True, False, 1),
                                 (True, False, -1), (True, True, 0)]:
        assert (side == 0 and not exited and not entered) == (side == 0 and not exited)


@pytest.mark.parametrize('opening,high,low,close,tick,expected', [
    (100, 110, 99, 101, 0.01, (False, True)),
    (100, 101, 90, 99, 0.01, (True, False)),
    (100, 104, 99, 103, 0.01, (False, False)),
    (100, 102, 99, 100, 0.01, (False, True)),
    (100, 100, 100, 100, 0.01, (False, False)),
    (100, 100.01, 100, 100, 0.01, (False, False)),
    (100, 104, 100, 102, 0.01, (False, False)),
    (100, 103, 99, 101, 0.01, (False, True)),
])
def test_long_wick_reference(opening, high, low, close, tick, expected):
    def blocked(wick):
        return high > low and wick >= max(abs(close - opening), tick) * 2 and wick >= (high - low) * 0.5
    assert (blocked(min(opening, close) - low), blocked(high - max(opening, close))) == expected


def test_wick_guard_covers_preparation_and_retouch():
    for token in ['excludeWick = input.bool(true',
                  'math.max(math.abs(close - open), syminfo.mintick) * wickBodyRatio',
                  'wick >= (high - low) * wickRangePct / 100',
                  'buyWick = touchBuy and longWick(math.min(open, close) - low)',
                  'sellWick = touchSell and longWick(high - math.max(open, close))',
                  'wickBlocked = armed == 1 ? buyWick : sellWick',
                  'wickBlocked = touchBuy ? buyWick : sellWick',
                  'if both or manualPause or explained or wickBlocked',
                  'wickBlocked ? "長いヒゲ"']:
        assert token in SOURCE
