from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "strict_rr_ml_15m_strategy_2026.pine"
).read_text(encoding="utf-8")


def test_strict_rr_ml_pine_requires_confirmed_four_hour_alignment() -> None:
    assert SOURCE.startswith("//@version=6\n")
    assert 'indicator("11通貨ML + 7銘柄構造分析 2026 [SCENARIO NOWCAST]"' in SOURCE
    assert "strategy(" not in SOURCE
    assert "strategy." not in SOURCE
    assert 'syminfo.tickerid, "240", f_htfContext()' in SOURCE
    assert "lookahead=barmerge.lookahead_on" in SOURCE
    assert "[lastHigh[1], previousHigh[1], lastLow[1], previousLow[1]," in SOURCE
    assert "channelHigh1[1], channelHigh2[1], channelLow1[1], channelLow2[1]," in SOURCE
    assert "channelHighTime1[1], channelHighTime2[1]" in SOURCE
    assert "ready and hourlyBar" in SOURCE
    assert "longProbability >= 0.485 and htfTrend == 1" in SOURCE
    assert "shortProbability >= 0.485 and htfTrend == -1" in SOURCE


def test_strict_rr_ml_pine_shows_entry_rr_and_readable_win_rate() -> None:
    assert '"過去のEntry・TP・SLラインを表示"' not in SOURCE
    assert 'input.int(50, "過去トレード保持数", minval=1, maxval=50' in SOURCE
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
    assert '"ENTRY BUY\\n"' in SOURCE
    assert '"ENTRY SELL\\n"' in SOURCE
    assert '"TP 利確\\n"' in SOURCE
    assert '"SL 損切り\\n"' in SOURCE
    assert "box profitZone = box.new" in SOURCE
    assert "box riskZone = box.new" in SOURCE
    assert "bgcolor=color.new(color.lime, 88)" in SOURCE
    assert "bgcolor=color.new(color.red, 88)" in SOURCE
    assert "int historyObjectLimit = i_historyTradeCount * 3" in SOURCE
    assert "while array.size(tradeLines) > historyObjectLimit" in SOURCE
    assert "while array.size(tradeLabels) > historyObjectLimit" in SOURCE
    assert SOURCE.count("line.delete") == 4
    assert SOURCE.count("label.delete") == 3
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
    assert "float visibleTarget = not na(pendingTargetPrice) ? pendingTargetPrice" in SOURCE
    assert "var line pendingTargetLine = na" in SOURCE
    assert "var label pendingTargetLabel = na" in SOURCE
    assert "pendingTargetLine := line.new(bar_index, pendingTargetPrice" in SOURCE
    assert "xloc=xloc.bar_index, color=color.lime, width=2" in SOURCE
    assert 'pendingTargetPrice, "TP 利確\\n"' in SOURCE
    assert "table.new(position.middle_right" not in SOURCE
    assert "table.cell(stats" not in SOURCE
    assert '"勝率"' in SOURCE
    assert '"現在-- / 検証55.6%"' in SOURCE
    assert '" B" + str.tostring(lastLongProbability * 100.0' in SOURCE
    assert '" / S" + str.tostring(lastShortProbability * 100.0' in SOURCE
    assert "float winRate = closedTrades > 0 ? wins * 100.0 / closedTrades : na" in SOURCE
    assert "if hitStop" in SOURCE
    assert "bar_index == pendingSignalBar + 1" in SOURCE


def test_entry_guide_makes_wait_signal_and_live_trade_unambiguous() -> None:
    assert 'text="BUY予告\\n次足ENTRY"' in SOURCE
    assert 'text="SELL予告\\n次足ENTRY"' in SOURCE
    assert '"エントリーなし・待機"' in SOURCE
    assert '"次の15分足始値で買い"' in SOURCE
    assert '"次の15分足始値で売り"' in SOURCE
    assert '"買い保有中"' in SOURCE
    assert '"売り保有中"' in SOURCE
    assert "var table entryGuide = table.new(position.top_right, 2, 5" in SOURCE
    assert '"4H / ML"' in SOURCE
    assert '"ENTRY 黄"' in SOURCE
    assert '"TP緑 / SL赤"' in SOURCE
    assert "text_size=size.small" in SOURCE
    assert 'guidePending ? "次の15分足始値" : "--"' in SOURCE
    assert '"11通貨ML: BUY予告・次の15分足始値でENTRY"' in SOURCE
    assert '"11通貨ML: SELL予告・次の15分足始値でENTRY"' in SOURCE
    assert "固定11通貨 コンパクトML" not in SOURCE


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
    assert len(SOURCE) < 70_000


def test_chart_analysis_layer_uses_confirmed_structure_and_scenarios() -> None:
    assert 'input.bool(true, "構造分析を表示"' in SOURCE
    assert 'input.int(5, "スイング確定本数"' in SOURCE
    assert "ta.pivothigh(high, i_analysisPivotBars, i_analysisPivotBars)" in SOURCE
    assert "ta.pivotlow(low, i_analysisPivotBars, i_analysisPivotBars)" in SOURCE
    assert "float channelPivotHigh = ta.pivothigh(high, i_analysisPivotBars" in SOURCE
    assert "float channelPivotLow = ta.pivotlow(low, i_analysisPivotBars" in SOURCE
    assert "time[i_analysisPivotBars]" in SOURCE
    assert '"確定スイング高値"' in SOURCE
    assert '"確定スイング安値"' in SOURCE
    assert "line resistance1 = line.new" in SOURCE
    assert "line support1 = line.new" in SOURCE
    assert "line upperChannel = line.new" in SOURCE
    assert "line lowerChannel = line.new" in SOURCE
    assert '"4H 上限チャネル"' in SOURCE
    assert '"4H 下限チャネル"' in SOURCE
    assert "line bullishScenario1 = line.new" in SOURCE
    assert "line bullishScenario2 = line.new" in SOURCE
    assert "line bullishScenario3 = line.new" in SOURCE
    assert "line bearishScenario1 = line.new" in SOURCE
    assert "line bearishScenario2 = line.new" in SOURCE
    assert "line bearishScenario3 = line.new" in SOURCE
    assert 'bullishExtension, "上昇シナリオ"' in SOURCE
    assert 'bearishExtension, "下降シナリオ"' in SOURCE
    assert "analysisDirection == -1 ? 55 : 0" in SOURCE
    assert "analysisDirection == 1 ? 55 : 0" in SOURCE


def test_untrained_symbols_are_analysis_only_without_ml_entries() -> None:
    for symbol in (
        "XAUUSD", "EURJPY", "NZDJPY", "CADJPY", "EURAUD", "AUDNZD", "EURGBP"
    ):
        assert f'pair == "{symbol}"' in SOURCE
        assert f'"{symbol}" =>' not in SOURCE
    assert '"CHFJPY" => 0.017999999999999999' in SOURCE
    assert "bool chartSupported = supportedPair or analysisOnlyPair" in SOURCE
    assert 'analysisOnlyPair ? "構造分析のみ・MLエントリーなし"' in SOURCE
    assert "yearAllowed and supportedPair and not na(activeSpread)" in SOURCE


def test_entry_analysis_snapshot_retains_levels_and_channels() -> None:
    assert "var array<line> entryAnalysisLines = array.new_line()" in SOURCE
    assert "var array<int> entryAnalysisCounts = array.new_int()" in SOURCE
    assert "line entryR1 = line.new" in SOURCE
    assert "line entryR2 = line.new" in SOURCE
    assert "line entryS1 = line.new" in SOURCE
    assert "line entryS2 = line.new" in SOURCE
    assert "line entryUpperChannel = line.new" in SOURCE
    assert "line entryLowerChannel = line.new" in SOURCE
    assert "array.push(entryAnalysisCounts, entryAnalysisCount)" in SOURCE
    assert "while array.size(entryAnalysisCounts) > i_historyTradeCount" in SOURCE
    assert "int oldestAnalysisCount = array.shift(entryAnalysisCounts)" in SOURCE


def test_upper_and_lower_channels_are_parallel_not_converging() -> None:
    assert "float htfChannelSlope" in SOURCE
    assert "htfChannelDirection == 1 and not na(htfLowerPivotSlope)" in SOURCE
    assert "htfChannelDirection == -1 and not na(htfUpperPivotSlope)" in SOURCE
    assert "upperChannelEnd = htfAnalysisHigh1 + htfChannelSlope" in SOURCE
    assert "lowerChannelEnd = htfAnalysisLow1 + htfChannelSlope" in SOURCE
    assert "entryUpperEnd = htfAnalysisHigh1 + htfChannelSlope" in SOURCE
    assert "entryLowerEnd = htfAnalysisLow1 + htfChannelSlope" in SOURCE
    assert "xloc=xloc.bar_time, color=color.rgb(6, 182, 212)" in SOURCE
    assert "xloc=xloc.bar_time, color=color.new(color.rgb(6, 182, 212)" in SOURCE
    assert "int htfChannelStartTime" in SOURCE
    assert "int analysisChannelStartBar" not in SOURCE
    assert "float upperSlope =" not in SOURCE
    assert "float lowerSlope =" not in SOURCE
    assert "entryUpperSlope" not in SOURCE
    assert "entryLowerSlope" not in SOURCE


def test_multi_pair_scanner_shows_only_complete_mobile_candidates() -> None:
    assert "dynamic_requests=true" in SOURCE
    assert SOURCE.count("input.symbol(") == 18
    assert SOURCE.count("request.security(i_scanSymbol") == 36
    assert SOURCE.count("request.security(") == 37
    assert "table.new(position.bottom_right, 5, 7" in SOURCE
    for symbol in (
        "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY",
        "GBPJPY", "NZDJPY", "CADJPY", "NZDUSD", "AUDJPY", "USDCHF",
        "CHFJPY", "EURAUD", "EURCHF", "GBPCHF", "AUDNZD", "EURGBP",
    ):
        assert f'input.symbol("OANDA:{symbol}"' in SOURCE
    assert "bool showReady = row <= 6 and (buyReady or sellReady)" in SOURCE
    assert 'buyReady ? "BUY" : "SELL"' in SOURCE
    assert '"買い監視"' not in SOURCE
    assert '"売り監視"' not in SOURCE
    assert '"構造待ち"' not in SOURCE
    assert "hourlyAge >= 0 and hourlyAge <= 1" in SOURCE
    assert SOURCE.count("f_scanCompactRow(scanner, compactRow,") == 18
    assert '"現在候補なし"' in SOURCE
    assert "table.clear(scanner, 0, 0, 4, 6)" in SOURCE
    assert '"Entry"' in SOURCE
    assert 'table.cell(scanner, 3, 0, "TP"' in SOURCE
    assert "float targetPrice = not na(riskPrice)" in SOURCE
    assert 'str.tostring(targetPrice, "#.#####")' in SOURCE
    assert 'na(entryPrice) ? "次足始値"' in SOURCE
    assert 'table.cell(scanner, 4, 0, "SL"' in SOURCE
    assert "signalClose - signalAtr * 2.0" in SOURCE
    assert "signalClose + signalAtr * 2.0 + requestedSpread" in SOURCE
