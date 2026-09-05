from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_yosuga_dow_filters import Prepared  # noqa: E402
from research_yosuga_dow_pullback_entry import _local_dow_trend  # noqa: E402


SOURCE_PATH = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "yosuga_dow_expectancy_indicator.pine"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def test_uses_an_identifiable_simple_indicator_title() -> None:
    assert 'indicator("Yosuga × Tamukai Simple Entry MTF v3"' in SOURCE
    assert 'shorttitle="Yosuga_Simple_MTF_v3"' in SOURCE


def test_uses_confirmed_higher_timeframe_direction() -> None:
    assert "ta.sma(close, htfMaLength)[1]" in SOURCE
    assert "ta.sma(close, htfMaLength)[2]" in SOURCE
    assert SOURCE.count("lookahead=barmerge.lookahead_off") >= 10
    assert "requireDowAlignment" in SOURCE
    assert "dowTrend == 1" in SOURCE
    assert "dowTrend == -1" in SOURCE


def test_waits_for_first_ma_contact_rejection_and_reacceleration() -> None:
    assert "low[1] > entryMa[1]" in SOURCE
    assert "high[1] < entryMa[1]" in SOURCE
    assert "longCloseLocation >= closeLocationThreshold" in SOURCE
    assert "shortCloseLocation >= closeLocationThreshold" in SOURCE
    assert "close > high[1]" in SOURCE
    assert "close < low[1]" in SOURCE
    assert "setupAge >= 1" in SOURCE


def test_has_no_acceleration_or_deceleration_judgment() -> None:
    for removed in (
        "accelerationMode",
        "phaseThresholdAtr",
        "fDirectionalPhase",
        "fLocalPhaseAllowed",
        "fHtfPhaseAllowed",
        "加速",
        "減速",
    ):
        assert removed not in SOURCE
    assert "priceBreakConfirmed" in SOURCE
    assert "if maSlopeOk and priceBreakConfirmed and correctMaSide" in SOURCE


def test_uses_structure_stop_full_one_r_target_and_next_bar_breakeven() -> None:
    assert "stopPrice := proposedStop" in SOURCE
    assert "targetPrice := entryPrice + tradeDirection * riskDistance" in SOURCE
    assert "breakevenActive ? entryPrice : stopPrice" in SOURCE
    assert "bar_index > entryBar" in SOURCE
    assert "建値SLは次の足から有効" in SOURCE
    assert "else if targetHit" in SOURCE
    assert "not breakevenActive and triggerHit" in SOURCE
    assert '"建値\\n" + str.tostring(entryPrice, format.mintick)' in SOURCE


def test_displays_entry_exit_prices_and_performance() -> None:
    for text in (
        "Entry:",
        "TP:",
        "SL:",
        "建値撤退",
        "損切",
        "利確 1R",
        "勝率",
        "期待値 / 取引",
        "累計損益 (単純合計)",
    ):
        assert text in SOURCE
    assert "position.bottom_right" in SOURCE


def test_counts_breakeven_exits_as_wins_in_win_rate_only() -> None:
    assert "int winsIncludingBreakeven = wins + breakevens" in SOURCE
    assert "winsIncludingBreakeven * 100.0 / closedTrades" in SOURCE
    assert '"勝率 (建値含む)"' in SOURCE
    assert "float averageWinPct = wins > 0 ? grossProfitPct / wins : na" in SOURCE
    assert "float profitFactor = grossLossPct > 0 ? grossProfitPct / grossLossPct : na" in SOURCE


def test_supports_requested_chart_timeframes() -> None:
    for condition in (
        "timeframe.multiplier == 5",
        "timeframe.multiplier == 15",
        "timeframe.multiplier == 60",
        "timeframe.multiplier == 240",
        "timeframe.isdaily and timeframe.multiplier == 1",
    ):
        assert condition in SOURCE
    assert "isFiveMinuteChart or isFifteenMinuteChart or isOneHourChart or isFourHourChart or isOneDayChart" in SOURCE
    assert "対応足: 5分 / 15分 / 1時間 / 4時間 / 日足" in SOURCE


def test_automatically_selects_a_strictly_higher_timeframe() -> None:
    assert "dynamic_requests=true" in SOURCE
    assert 'isFiveMinuteChart ? "60"' in SOURCE
    assert 'isFifteenMinuteChart ? "240"' in SOURCE
    assert 'isOneHourChart ? "240"' in SOURCE
    assert 'isFourHourChart ? "D"' in SOURCE
    assert 'isOneDayChart ? "W"' in SOURCE
    assert "timeframe.in_seconds(effectiveHtfTimeframe) > timeframe.in_seconds(timeframe.period)" in SOURCE
    assert SOURCE.count("effectiveHtfTimeframe, ta.sma(close, htfMaLength)") == 2


def test_table_displays_chart_and_higher_timeframes() -> None:
    assert '"チャート / 上位足"' in SOURCE
    assert 'chartTimeframeName + " / " + htfTimeframeName' in SOURCE
    assert "table.new(position.bottom_right, 2, 13" in SOURCE


def test_displays_entry_opportunity_for_every_supported_timeframe() -> None:
    assert "table.new(position.top_right, 3, 6" in SOURCE
    for timeframe in ('"5"', '"15"', '"60"', '"240"', '"D"'):
        assert f"request.security(syminfo.tickerid, {timeframe}" in SOURCE
    for label in ("BUY候補", "SELL候補", "反発待ち", "反落待ち", "押し目待ち", "戻り待ち"):
        assert label in SOURCE
    assert "fScannerDowTrend()[1]" in SOURCE
    assert "fScannerPullbackState()[1]" in SOURCE
    assert '"上位足 / ダウ"' in SOURCE
    assert '"エントリーチャンス"' in SOURCE


def test_chart_is_reduced_to_trade_prices_and_outcomes() -> None:
    assert "plot(" not in SOURCE
    assert "plotshape(" not in SOURCE
    assert "showDowSignals" not in SOURCE
    assert "showMa" not in SOURCE
    assert "showPreviousDayLevels" not in SOURCE
    assert '"\\nEntry: " + str.tostring(entryPrice, format.mintick)' in SOURCE
    assert '"\\nTP: " + str.tostring(targetPrice, format.mintick)' in SOURCE
    assert '"\\nSL: " + str.tostring(stopPrice, format.mintick)' in SOURCE
    assert 'exitName := "利確 1R"' in SOURCE
    assert 'exitName := breakevenActive ? "建値撤退" : "損切"' in SOURCE
    assert 'alertcondition(longEntrySignal, "押し目BUY"' in SOURCE
    assert 'alertcondition(shortEntrySignal, "戻りSELL"' in SOURCE


def test_displays_the_active_entry_on_its_chart_timeframe_row() -> None:
    assert '"BUY エントリー中"' in SOURCE
    assert '"SELL エントリー中"' in SOURCE
    for chart_timeframe_flag in (
        "isFiveMinuteChart",
        "isFifteenMinuteChart",
        "isOneHourChart",
        "isFourHourChart",
        "isOneDayChart",
    ):
        assert f"fScannerDisplayTextColor({chart_timeframe_flag}, tradeDirection)" in SOURCE
    assert "isChartTimeframe and activeTradeDirection != 0" in SOURCE
    assert "activeTradeDirection == 1 ? color.blue : color.orange" in SOURCE


def test_local_dow_direction_persists_until_the_opposite_break() -> None:
    data = Prepared(
        times=[],
        high=np.zeros(7),
        low=np.zeros(7),
        close=np.zeros(7),
        cross_events=[(1, 1), (3, 1), (5, -1)],
    )
    assert _local_dow_trend(data).tolist() == [0, 1, 1, 1, 1, -1, -1]
