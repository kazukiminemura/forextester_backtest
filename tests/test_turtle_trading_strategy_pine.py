from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "tradingview"
    / "turtle_trading_strategy.pine"
).read_text(encoding="utf-8")


def test_is_independent_daily_strategy() -> None:
    assert SOURCE.startswith("//@version=6\n")
    assert 'strategy("タートル・トレーディング 日足 v3"' in SOURCE
    assert "pyramiding=4" in SOURCE
    assert "timeframe.isdaily and timeframe.multiplier == 1" in SOURCE
    assert "indicator(" not in SOURCE


def test_classic_entry_and_exit_channels_are_available() -> None:
    assert '"System 1 (20/10)"' in SOURCE
    assert '"System 2 (55/20)"' in SOURCE
    assert "int entryLength = useSystem1 ? 20 : 55" in SOURCE
    assert "int exitLength = useSystem1 ? 10 : 20" in SOURCE
    assert "ta.highest(high, entryLength)[1]" in SOURCE
    assert "ta.lowest(low, entryLength)[1]" in SOURCE
    assert "ta.highest(high, 55)[1]" in SOURCE
    assert "ta.lowest(low, 55)[1]" in SOURCE


def test_n_stops_and_pyramiding_follow_turtle_parameters() -> None:
    assert "ta.rma(trueRange, i_nLength)" in SOURCE
    assert 'input.float(0.5, "増し玉間隔（N）"' in SOURCE
    assert 'input.float(2.0, "損切り幅（N）"' in SOURCE
    assert 'input.int(4, "最大ユニット数"' in SOURCE
    assert "latestUnitPrice - i_stopN * tradeN" in SOURCE
    assert "latestUnitPrice + i_stopN * tradeN" in SOURCE
    assert "latestUnitPrice + i_addN * tradeN" in SOURCE
    assert "latestUnitPrice - i_addN * tradeN" in SOURCE
    for entry_id in ("L2", "L3", "L4", "S2", "S3", "S4"):
        assert f'strategy.entry("{entry_id}"' in SOURCE


def test_position_sizing_and_risk_controls_are_explicit() -> None:
    assert 'options=["口座リスク率", "固定数量"]' in SOURCE
    assert "strategy.equity * i_riskPercent / 100.0" in SOURCE
    assert "n * syminfo.pointvalue" in SOURCE
    assert "math.floor(quantity / i_qtyStep) * i_qtyStep" in SOURCE
    assert "margin_long=100, margin_short=100" in SOURCE
    assert "time >= i_startTime and time <= i_endTime" in SOURCE
    assert "strategy.cancel_all()" in SOURCE
    assert "bar_index > lastExitBar" in SOURCE


def test_visual_state_and_alerts_are_included() -> None:
    assert 'plot(activeEntryUpper, "買いブレイク"' in SOURCE
    assert 'plot(activeEntryLower, "売りブレイク"' in SOURCE
    assert 'plot(isLong ? longExitStop : isShort ? shortExitStop : na, "有効ストップ"' in SOURCE
    assert 'table.new(position.top_right, 2, 8' in SOURCE
    assert 'table.new(position.bottom_right, 2, 7' in SOURCE
    assert "barstate.islastconfirmedhistory or barstate.isrealtime" in SOURCE
    assert "if updateDashboard" in SOURCE
    assert 'alertcondition(longBreakoutNow, "Turtle LONG breakout"' in SOURCE
    assert 'alertcondition(shortBreakoutNow, "Turtle SHORT breakout"' in SOURCE


def test_win_rate_and_expectancy_use_closed_campaigns() -> None:
    assert "f_campaignStats() =>" in SOURCE
    assert "strategy.closedtrades.first_index" in SOURCE
    assert "for tradeIndex = firstTrade to lastTrade" in SOURCE
    assert "tradeExitBar == groupedExitBar" in SOURCE
    assert "groupedProfit += tradeProfit" in SOURCE
    assert "strategy.closedtrades.commission(tradeIndex)" not in SOURCE
    assert "winningCampaigns * 100.0 / campaignCount" in SOURCE
    assert "campaignProfitSum / campaignCount" in SOURCE
    assert 'table.cell(statsTable, 0, 1, "勝率"' in SOURCE
    assert 'table.cell(statsTable, 0, 2, "期待値 / 取引"' in SOURCE
    assert 'table.cell(statsTable, 0, 6, "PF"' in SOURCE
    assert 'na(winRatePercent) ? "未決済"' in SOURCE
