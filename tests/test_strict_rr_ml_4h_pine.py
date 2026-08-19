from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "strict_rr_ml_15m_strategy_2026.pine"
).read_text(encoding="utf-8")


def test_strict_rr_ml_pine_requires_confirmed_four_hour_alignment() -> None:
    assert SOURCE.startswith("//@version=6\n")
    assert 'indicator("固定11通貨 4H順張り コンパクトMLエントリー 2026"' in SOURCE
    assert "strategy(" not in SOURCE
    assert "strategy." not in SOURCE
    assert 'request.security(\n     syminfo.tickerid, "240", f_htfContext()' in SOURCE
    assert "lookahead=barmerge.lookahead_on" in SOURCE
    assert "[lastHigh[1], previousHigh[1], lastLow[1], previousLow[1]]" in SOURCE
    assert "ready and hourlyBar" in SOURCE
    assert "longProbability >= 0.485 and htfTrend == 1" in SOURCE
    assert "shortProbability >= 0.485 and htfTrend == -1" in SOURCE


def test_strict_rr_ml_pine_shows_entry_rr_and_readable_win_rate() -> None:
    assert 'plot(visibleEntry, "Entry"' in SOURCE
    assert "pendingDirection == 1 ? pendingClose + activeSpread : pendingClose" in SOURCE
    assert 'plot(trackingTrade ? trackedStop : na, "SL"' in SOURCE
    assert 'plot(trackingTrade ? trackedTarget : na, "TP 1R"' in SOURCE
    assert '"当チャート勝率"' in SOURCE
    assert '"正時判定→次足 / RR1:1"' in SOURCE
    assert "table.new(position.middle_right, 2, 13" in SOURCE
    assert '"当チャート勝率"' in SOURCE
    assert '"2026: 72.8% / 312件"' in SOURCE
    assert "float winRate = closedTrades > 0 ? wins * 100.0 / closedTrades : na" in SOURCE
    assert "if hitStop" in SOURCE
    assert "bar_index == pendingSignalBar + 1" in SOURCE


def test_strict_rr_ml_pine_avoids_known_static_failures() -> None:
    assert "string text)" not in SOURCE
    assert "float f_pairSpread(" not in SOURCE
    assert "switch pair" in SOURCE
    assert 'pair == "AUDUSD" ?' not in SOURCE
    assert SOURCE.count("(") == SOURCE.count(")")
    assert SOURCE.count("[") == SOURCE.count("]")


def test_compact_model_stays_below_the_previous_tree_budget() -> None:
    tree_lines = [line for line in SOURCE.splitlines() if line.startswith("f_tree_")]
    assert len(tree_lines) == 20
    assert all("=> (" in line for line in tree_lines)
    assert len(SOURCE) < 50_000


def test_multi_pair_scanner_shows_complete_and_monitoring_states() -> None:
    assert "dynamic_requests=true" in SOURCE
    assert SOURCE.count("input.symbol(") == 11
    assert SOURCE.count("request.security(i_scanSymbol") == 22
    assert "table.new(position.bottom_right, 5, 13" in SOURCE
    assert 'buyReady ? "BUY" : sellReady ? "SELL"' in SOURCE
    assert 'trend == 1 ? "買い監視"' in SOURCE
    assert 'trend == -1 ? "売り監視"' in SOURCE
    assert '"方向待ち"' in SOURCE
    assert "hourlyAge >= 0 and hourlyAge <= 1" in SOURCE
    assert SOURCE.count("f_scanRow(scanner,") == 11
    assert '"ML値"' in SOURCE
    assert '"勝率ではない"' in SOURCE
    assert '"Entry"' in SOURCE
    assert 'na(entryPrice) ? "次足始値"' in SOURCE
