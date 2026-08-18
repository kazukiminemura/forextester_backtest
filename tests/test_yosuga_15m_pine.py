from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "yosuga_15m_4h_trade_journal.pine"
).read_text(encoding="utf-8")


def test_yosuga_fifteen_minute_journal_logic_and_requested_fields() -> None:
    assert SOURCE.startswith("//@version=6\n")
    assert 'indicator("よすが式 4H順張り・15分足エントリー RR1 + 取引評価 v1"' in SOURCE
    assert "dynamic_requests=true" in SOURCE
    assert "strategy(" not in SOURCE
    assert "timeframe.multiplier == 15" in SOURCE
    assert 'input.timeframe("240", "上位足"' in SOURCE
    assert "htfTrend == 1 and ltfUp" in SOURCE
    assert "htfTrend == -1 and ltfDown" in SOURCE
    assert "trendlineBuy or pullbackBuy" in SOURCE
    assert "activeTarget := activeEntry + initialRisk * positionDirection" in SOURCE
    assert 'previousResult != "負け"' in SOURCE
    assert "dailyTrades < i_maxTradesPerDay" in SOURCE
    for label in (
        "曜日",
        "時間帯",
        "保有分",
        "買い・売り",
        "15分足方向",
        "5分足方向",
        "トレード評価",
        "獲得pips",
        "結果",
        "初動・追随",
        "当日取引",
        "1回前の結果",
        "取引種別",
        "エントリー理由",
    ):
        assert f'"{label}"' in SOURCE


def test_yosuga_tables_are_high_contrast_and_scanner_is_complete() -> None:
    assert SOURCE.count("input.symbol(") == 12
    assert SOURCE.count("= f_scanPair(i_scanSymbol") == 12
    assert "table.new(position.middle_left, 2, 15" in SOURCE
    assert "table.new(position.middle_right, 2, 7" in SOURCE
    assert "table.new(position.bottom_right, 4, 13" in SOURCE
    assert "bgcolor=cJournalPanel" in SOURCE
    assert "text_color=cJournalMuted" in SOURCE
    assert "text_color=textColor" in SOURCE
    assert 'lastEvaluation == "A" ? color.lime' in SOURCE
    assert 'lastResult == "勝ち" ? color.lime' in SOURCE
    assert "winRate >= 50 ? color.lime" in SOURCE
    assert "alertcondition(scannerNewChance" in SOURCE


def test_yosuga_pine_avoids_known_static_failures() -> None:
    assert "string text)" not in SOURCE
    assert SOURCE.count("(") == SOURCE.count(")")
    assert SOURCE.count("[") == SOURCE.count("]")
