from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "strict_rr_ml_15m_strategy_2026.pine"
).read_text(encoding="utf-8")


def test_strict_rr_ml_pine_requires_confirmed_four_hour_alignment() -> None:
    assert SOURCE.startswith("//@version=6\n")
    assert 'indicator("固定11通貨 4H順張り コンパクトMLエントリー 2026 [ANALYSIS PLAN]"' in SOURCE
    assert "strategy(" not in SOURCE
    assert "strategy." not in SOURCE
    assert 'request.security(\n     syminfo.tickerid, "240", f_htfContext()' in SOURCE
    assert "lookahead=barmerge.lookahead_on" in SOURCE
    assert "[lastHigh[1], previousHigh[1], lastLow[1], previousLow[1]]" in SOURCE
    assert "ready and hourlyBar" in SOURCE
    assert "longProbability >= 0.485 and htfTrend == 1" in SOURCE
    assert "shortProbability >= 0.485 and htfTrend == -1" in SOURCE


def test_strict_rr_ml_pine_shows_entry_rr_and_readable_win_rate() -> None:
    assert '"過去のEntry・TP・SLラインを表示"' not in SOURCE
    assert 'input.int(150, "過去トレード保持数", minval=1, maxval=160' in SOURCE
    assert "max_lines_count=500" in SOURCE
    assert "max_boxes_count=500" in SOURCE
    assert 'input.int(48, "トレード計画の表示幅", minval=6, maxval=192' in SOURCE
    assert "line targetLine = line.new" in SOURCE
    assert "line stopLine = line.new" in SOURCE
    assert "color=color.yellow" in SOURCE
    assert "color=color.lime" in SOURCE
    assert "color=color.red" in SOURCE
    assert "style=line.style_solid" in SOURCE
    assert "style=line.style_dashed" in SOURCE
    assert "style=line.style_dotted" in SOURCE
    assert '"ENTRY\\n"' in SOURCE
    assert '"TP 利確\\n"' in SOURCE
    assert '"SL 損切り\\n"' in SOURCE
    assert "box profitZone = box.new" in SOURCE
    assert "box riskZone = box.new" in SOURCE
    assert "bgcolor=color.new(color.lime, 88)" in SOURCE
    assert "bgcolor=color.new(color.red, 88)" in SOURCE
    assert "int historyObjectLimit = i_historyTradeCount * 3" in SOURCE
    assert "while array.size(tradeLines) > historyObjectLimit" in SOURCE
    assert "while array.size(tradeLabels) > historyObjectLimit" in SOURCE
    assert SOURCE.count("line.delete") == 2
    assert SOURCE.count("label.delete") == 2
    assert SOURCE.count("box.delete") == 1
    assert "historicalStop := trackedStop" in SOURCE
    assert "historicalTarget := trackedTarget" in SOURCE
    assert "if i_showEntryLine" not in SOURCE
    assert "bar_index <= historicalLineEndBar" in SOURCE
    assert 'plot(visibleEntry, "Entry scale", color=color.new(color.yellow, 100)' in SOURCE
    assert "pendingDirection == 1 ? pendingClose + activeSpread : pendingClose" in SOURCE
    assert 'plot(visibleStop, "SL scale", color=color.new(color.red, 100)' in SOURCE
    assert "pendingClose - pendingAtr * 2.0" in SOURCE
    assert 'plot(visibleTarget, "TP scale", color=color.new(color.lime, 100)' in SOURCE
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
    assert len(SOURCE) < 60_000


def test_chart_analysis_layer_uses_confirmed_structure_and_scenarios() -> None:
    assert 'input.bool(true, "構造分析を表示"' in SOURCE
    assert 'input.int(5, "スイング確定本数"' in SOURCE
    assert "ta.pivothigh(high, i_analysisPivotBars, i_analysisPivotBars)" in SOURCE
    assert "ta.pivotlow(low, i_analysisPivotBars, i_analysisPivotBars)" in SOURCE
    assert '"確定スイング高値"' in SOURCE
    assert '"確定スイング安値"' in SOURCE
    assert "line resistance1 = line.new" in SOURCE
    assert "line support1 = line.new" in SOURCE
    assert "line upperChannel = line.new" in SOURCE
    assert "line lowerChannel = line.new" in SOURCE
    assert "line scenario1 = line.new" in SOURCE
    assert "line scenario2 = line.new" in SOURCE
    assert "line scenario3 = line.new" in SOURCE
    assert 'analysisDirection == 1 ? "上昇シナリオ" : "下降シナリオ"' in SOURCE


def test_multi_pair_scanner_shows_complete_and_monitoring_states() -> None:
    assert "dynamic_requests=true" in SOURCE
    assert SOURCE.count("input.symbol(") == 11
    assert SOURCE.count("request.security(i_scanSymbol") == 22
    assert "table.new(position.bottom_right, 6, 13" in SOURCE
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
    assert 'table.cell(scanner, 5, 0, "SL"' in SOURCE
    assert "signalClose - signalAtr * 2.0" in SOURCE
    assert "signalClose + signalAtr * 2.0 + requestedSpread" in SOURCE
