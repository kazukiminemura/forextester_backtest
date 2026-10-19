from pathlib import Path


def test_indicator_guards_and_disclosures():
    root=Path(__file__).resolve().parents[1]
    s=(root/'scripts/tradingview/bb3_context_setup.pine').read_text(encoding='utf-8')
    assert s.startswith('//@version=6')
    assert 'indicator(' in s and 'strategy.entry(' not in s
    for item in ['barstate.isconfirmed','bar_index > armedBar','ta.highest(high[1], lookback)',
                 'ta.lowest(low[1], lookback)','timeframe.in_seconds() == 300',
                 'ニュース自動取得なし','BUY候補','SELL候補','requireReturn']:
        assert item in s
    assert s.count('input.time(')==3
    assert 'request.security(' not in s


def test_recent_breakout_context_not_only_touch_bar():
    root=Path(__file__).resolve().parents[1]
    s=(root/'scripts/tradingview/bb3_context_setup.pine').read_text(encoding='utf-8')
    for item in ['int impulseBars = input.int(3,', 'var int started = na',
                 'if gap or reclaimed or expired', 'bar_index - started <= impulseBars',
                 'recentImpulse(breakUp, priorHigh, true)',
                 'recentImpulse(breakDown, priorLow, false)',
                 'recentImpulse(roundUp, nextRound, true)',
                 'recentImpulse(roundDown, priorRound, false)',
                 'buyExplained = (excludeBreak and recentLowBreak)',
                 'sellExplained = (excludeBreak and recentHighBreak)']:
        assert item in s
