from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "market_wall_4h_channel_15m.pine"
).read_text(encoding="utf-8")


def test_wall_indicator_uses_fifteen_minute_validated_trade_filter() -> None:
    assert SOURCE.startswith("//@version=6\n")
    assert 'indicator("4H 相場の壁・チャネル + よすが式15分足 RR1"' in SOURCE
    assert "strategy(" not in SOURCE
    assert 'plotshape(newBuy, "BUY entry"' in SOURCE
    assert 'plotshape(newSell, "SELL entry"' in SOURCE
    assert 'sideText + " ENTRY  " + str.tostring(activeEntry' in SOURCE
    assert '"TP 利確  "' in SOURCE
    assert '"SL 損切り  "' in SOURCE
    assert "table.new" not in SOURCE
    assert 'input.bool(false, "ヒゲ反転を許可（検証勝率36.73%）"' in SOURCE
    assert 'input.bool(false, "包み足を許可（検証勝率39.12%）"' in SOURCE
    assert 'input.bool(false, "ヒゲ＋包み足を許可（検証勝率27.59%）"' in SOURCE
    assert "bullShapeAllowed" in SOURCE
    assert "bearShapeAllowed" in SOURCE
    assert '"エントリー停止：勝率50%以上の形なし' in SOURCE


def test_confirmed_four_hour_swings_are_projected_to_fifteen_minutes() -> None:
    assert "ta.pivothigh(high, i_pivotBars, i_pivotBars)" in SOURCE
    assert "ta.pivotlow(low, i_pivotBars, i_pivotBars)" in SOURCE
    assert "high1[1]" in SOURCE
    assert "low1[1]" in SOURCE
    assert 'syminfo.tickerid, "240", f_confirmed4hSwings()' in SOURCE
    assert "lookahead=barmerge.lookahead_on" in SOURCE
    assert "timeframe.in_seconds() == 15 * 60" in SOURCE
    assert '"15分足で使用してください"' in SOURCE
    assert "i_projectionBars * 15 * 60 * 1000" in SOURCE


def test_latest_and_previous_high_low_walls_are_clear() -> None:
    assert '"4H H1  "' in SOURCE
    assert '"4H H2"' in SOURCE
    assert '"4H L1  "' in SOURCE
    assert '"4H L2"' in SOURCE
    assert "line highWall1 = line.new" in SOURCE
    assert "line highWall2 = line.new" in SOURCE
    assert "line lowWall1 = line.new" in SOURCE
    assert "line lowWall2 = line.new" in SOURCE
    assert SOURCE.count("style=line.style_dashed") == 2


def test_upper_and_lower_channels_share_one_four_hour_slope() -> None:
    assert "float channelSlope" in SOURCE
    assert "structureDirection == 1 and not na(lowerPivotSlope)" in SOURCE
    assert "structureDirection == -1 and not na(upperPivotSlope)" in SOURCE
    assert "upperEnd = swingHigh1 + channelSlope" in SOURCE
    assert "lowerEnd = swingLow1 + channelSlope" in SOURCE
    assert "line upperChannel = line.new" in SOURCE
    assert "line lowerChannel = line.new" in SOURCE
    assert '"4H 上限チャネル"' in SOURCE
    assert '"4H 下限チャネル"' in SOURCE
    assert "xloc=xloc.bar_time" in SOURCE


def test_fifteen_minute_signal_uses_confirmed_multi_timeframe_context() -> None:
    assert 'syminfo.tickerid, "15", f_confirmed15mSwings()' in SOURCE
    assert SOURCE.count("lookahead=barmerge.lookahead_on") == 3
    assert "high1[1]" in SOURCE
    assert "low1[1]" in SOURCE
    assert "upStructure and" in SOURCE
    assert "setupHigherLow and atSupport" in SOURCE
    assert "downStructure and" in SOURCE
    assert "setupLowerHigh and atResistance" in SOURCE
    assert "bullPaScore >= i_minPaScore" in SOURCE
    assert "bearPaScore >= i_minPaScore" in SOURCE
    assert "f_confirmed4hCloses()" in SOURCE
    assert "bool htfDecelerating" in SOURCE
    assert "htfSpeedAllowed" in SOURCE


def test_trade_lines_are_strict_rr1_and_historical_lines_are_retained() -> None:
    assert "activeTarget := activeEntry + risk * positionDirection" in SOURCE
    assert "array.push(tradeLines, activeEntryLine)" in SOURCE
    assert "array.push(tradeLines, activeStopLine)" in SOURCE
    assert "array.push(tradeLines, activeTargetLine)" in SOURCE
    assert "while array.size(tradeLines) > i_keepTrades * 3" in SOURCE
    assert "line.delete(array.shift(tradeLines))" in SOURCE
    assert "line.delete(array.pop(tradeLines))" not in SOURCE
    assert 'input.int(60, "残す過去トレード数"' in SOURCE
