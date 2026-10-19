"""Structural checks only; these do not compile or execute Pine."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source():
    return (ROOT / 'scripts/tradingview/bb3_context_strategy.pine').read_text(encoding='utf-8')


def test_strategy_execution_and_exit_guards():
    s = source()
    for token in ['//@version=6', 'strategy(', 'pyramiding=0',
                  'calc_on_every_tick=false', 'calc_on_order_fills=false',
                  'process_orders_on_close=false', 'strategy.position_size == 0',
                  'strategy.closedtrades == nz(strategy.closedtrades[1])',
                  'bar_index > armedBar', 'limit=basis, loss=stopTicks',
                  'math.round(slPips * pipSize / syminfo.mintick)']:
        assert token in s
    assert s.count('strategy.entry(') == 2
    assert s.count('strategy.exit(') == 4
    assert 'alertcondition(' not in s
    assert 'request.security(' not in s


def test_context_filters_preserved():
    s = source()
    for token in ['ta.highest(high[1], lookback)', 'ta.lowest(low[1], lookback)',
                  'recentImpulse(breakUp, priorHigh, true)',
                  'recentImpulse(breakDown, priorLow, false)',
                  'recentImpulse(roundUp, nextRound, true)',
                  'recentImpulse(roundDown, priorRound, false)',
                  'newsBlocked or manualPause or explained',
                  'timeframe.in_seconds() == 300']:
        assert token in s
    assert s.count('input.time(') == 3


def test_pf_zero_guards_and_open_loss_disclosure():
    s = source()
    for token in ['math.abs(strategy.grossloss)',
                  'grossLoss > 0 ? strategy.grossprofit / grossLoss : na',
                  'strategy.closedtrades == 0', '算出不能（損失なし）',
                  'strategy.openprofit', '含み損益（PF対象外）',
                  'commission_value=0.0', '手数料既定0', 'ニュース自動取得なし']:
        assert token in s


def test_multi_pair_units_and_chart_guard():
    s = source()
    assert 'syminfo.basecurrency == "USD"' not in s
    assert 'USDJPY・5分足へ変更' not in s
    for token in ['bool unitOK = not autoPip or syminfo.type == "forex"',
                  '(syminfo.currency == "JPY" ? 0.01 : 0.0001) : manualPip',
                  'roundPips * pipSize / syminfo.mintick',
                  'unitOK and (not restrictChart or timeframe.in_seconds() == 300)',
                  'pip幅 / 節目幅（価格）', 'syminfo.ticker']:
        assert token in s
    assert s.count('float pipSize =') == 1
    assert s.index('float pipSize =') < s.index('float roundStep =')
