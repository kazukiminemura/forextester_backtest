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


def test_uses_confirmed_higher_timeframe_direction() -> None:
    assert "ta.sma(close, htfMaLength)[1]" in SOURCE
    assert "ta.sma(close, htfMaLength)[2]" in SOURCE
    assert SOURCE.count("lookahead=barmerge.lookahead_off") == 2
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


def test_uses_structure_stop_full_one_r_target_and_next_bar_breakeven() -> None:
    assert "stopPrice := proposedStop" in SOURCE
    assert "targetPrice := entryPrice + tradeDirection * riskDistance" in SOURCE
    assert "breakevenActive ? entryPrice : stopPrice" in SOURCE
    assert "bar_index > entryBar" in SOURCE
    assert "建値SLは次の足から有効" in SOURCE
    assert "else if targetHit" in SOURCE


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


def test_local_dow_direction_persists_until_the_opposite_break() -> None:
    data = Prepared(
        times=[],
        high=np.zeros(7),
        low=np.zeros(7),
        close=np.zeros(7),
        cross_events=[(1, 1), (3, 1), (5, -1)],
    )
    assert _local_dow_trend(data).tolist() == [0, 1, 1, 1, 1, -1, -1]
