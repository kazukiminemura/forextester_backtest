"""Export the selected compact 2026 entry model as a Pine indicator."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_compact_pine_ml import CompactModelConfig, _model
from research_ml_strict_rr import _opportunities, _training_rows
from research_strict_rr_portfolio import SYMBOLS, _prepare

SPREADS = {
    "AUDUSD": 0.00012,
    "EURUSD": 0.00011,
    "GBPUSD": 0.00014,
    "NZDUSD": 0.00014,
    "USDCHF": 0.00015,
    "USDJPY": 0.012,
    "AUDJPY": 0.014,
    "CHFJPY": 0.018,
    "EURCHF": 0.00017,
    "GBPCHF": 0.00016,
    "GBPJPY": 0.018,
}
CONFIG = CompactModelConfig(20, 15, 0.10, 300)
DEFAULT_THRESHOLD = 0.487


def _number(value: float) -> str:
    return "0.0" if value == 0.0 else format(float(value), ".17g")


def _tree_expression(nodes: np.ndarray, index: int = 0) -> str:
    node = nodes[index]
    if bool(node["is_leaf"]):
        return _number(node["value"])
    feature = int(node["feature_idx"])
    threshold = _number(node["num_threshold"])
    left = _tree_expression(nodes, int(node["left"]))
    right = _tree_expression(nodes, int(node["right"]))
    return f"(array.get(x, {feature}) <= {threshold} ? {left} : {right})"


def _exported_probability(model, values: np.ndarray) -> np.ndarray:
    raw = np.full(values.shape[0], float(model._baseline_prediction[0, 0]))
    for predictors in model._predictors:
        nodes = predictors[0].nodes
        for row, features in enumerate(values):
            node_index = 0
            while not bool(nodes[node_index]["is_leaf"]):
                node = nodes[node_index]
                value = features[int(node["feature_idx"])]
                go_left = (
                    bool(node["missing_go_to_left"])
                    if np.isnan(value)
                    else value <= float(node["num_threshold"])
                )
                node_index = int(node["left"] if go_left else node["right"])
            raw[row] += float(nodes[node_index]["value"])
    return 1.0 / (1.0 + np.exp(-raw))


def _pine(model, threshold: float, require_htf_alignment: bool) -> str:
    functions = "\n".join(
        f"f_tree_{index}(array<float> x) => {_tree_expression(predictors[0].nodes)}"
        for index, predictors in enumerate(model._predictors)
    )
    additions = "\n".join(
        f"    raw += f_tree_{index}(x)" for index in range(len(model._predictors))
    )
    spread_cases = "\n".join(
        f'        "{symbol}" => {_number(spread)}' for symbol, spread in SPREADS.items()
    )
    supported = " or ".join(f'pair == "{symbol}"' for symbol in SYMBOLS)
    htf_buy_filter = " and htfTrend == 1" if require_htf_alignment else ""
    htf_sell_filter = " and htfTrend == -1" if require_htf_alignment else ""
    mode_title = "4H順張り コンパクトML" if require_htf_alignment else "コンパクトML"
    return f'''//@version=6
// 2026年用の固定11通貨・共有コンパクトMLエントリー。
// 2025年末までに決済済みのデータだけで学習。注文は出さず、シグナルを表示する。
indicator("固定11通貨 {mode_title}エントリー 2026 [ANALYSIS PLAN]", overlay=true,
     max_labels_count=500, max_lines_count=500, max_boxes_count=500, dynamic_requests=true)

string gModel = "エントリー"
string i_timezone = input.string("Etc/UTC", "Forex Testerデータの時間帯", group=gModel)
float i_spreadOverride = input.float(0.0, "スプレッド価格差（0=既定値）", minval=0.0, group=gModel)
int i_entryLineBars = input.int(48, "トレード計画の表示幅", minval=6, maxval=192, group=gModel)
int i_historyTradeCount = input.int(150, "過去トレード保持数", minval=1, maxval=160, group=gModel)
bool i_only2026 = input.bool(true, "2026年だけに限定（検証条件）", group=gModel)

string gAnalysis = "チャート分析"
bool i_showAnalysis = input.bool(true, "構造分析を表示", group=gAnalysis)
int i_analysisPivotBars = input.int(5, "スイング確定本数", minval=2, maxval=20, group=gAnalysis)
int i_analysisScenarioBars = input.int(48, "シナリオ予測幅", minval=12, maxval=192, group=gAnalysis)

string gScanner = "通貨ペア・チャンス一覧"
bool i_showScanner = input.bool(true, "11通貨を一覧表示", group=gScanner)
string i_scanSymbol1 = input.symbol("OANDA:AUDUSD", "1", group=gScanner)
string i_scanSymbol2 = input.symbol("OANDA:EURUSD", "2", group=gScanner)
string i_scanSymbol3 = input.symbol("OANDA:GBPUSD", "3", group=gScanner)
string i_scanSymbol4 = input.symbol("OANDA:NZDUSD", "4", group=gScanner)
string i_scanSymbol5 = input.symbol("OANDA:USDCHF", "5", group=gScanner)
string i_scanSymbol6 = input.symbol("OANDA:USDJPY", "6", group=gScanner)
string i_scanSymbol7 = input.symbol("OANDA:AUDJPY", "7", group=gScanner)
string i_scanSymbol8 = input.symbol("OANDA:CHFJPY", "8", group=gScanner)
string i_scanSymbol9 = input.symbol("OANDA:EURCHF", "9", group=gScanner)
string i_scanSymbol10 = input.symbol("OANDA:GBPCHF", "10", group=gScanner)
string i_scanSymbol11 = input.symbol("OANDA:GBPJPY", "11", group=gScanner)

f_pairSpread(string pair) =>
    switch pair
{spread_cases}
        => na

f_htfContext() =>
    float pivotHigh = ta.pivothigh(high, 2, 2)
    float pivotLow = ta.pivotlow(low, 2, 2)
    float lastHigh = ta.valuewhen(not na(pivotHigh), pivotHigh, 0)
    float previousHigh = ta.valuewhen(not na(pivotHigh), pivotHigh, 1)
    float lastLow = ta.valuewhen(not na(pivotLow), pivotLow, 0)
    float previousLow = ta.valuewhen(not na(pivotLow), pivotLow, 1)
    [lastHigh[1], previousHigh[1], lastLow[1], previousLow[1]]

string pair = syminfo.basecurrency + syminfo.currency
bool supportedPair = {supported}
float defaultSpread = f_pairSpread(pair)
float activeSpread = i_spreadOverride > 0.0 ? i_spreadOverride : defaultSpread
bool correctTimeframe = timeframe.in_seconds() == 15 * 60
bool yearAllowed = not i_only2026 or year(time, i_timezone) == 2026

// Pythonと同じSMAシードのEMA。
var float ema20 = na
var float ema80 = na
var float ema200 = na
ema20 := bar_index == 19 ? ta.sma(close, 20) : bar_index > 19 ? ema20[1] + 2.0 / 21.0 * (close - ema20[1]) : na
ema80 := bar_index == 79 ? ta.sma(close, 80) : bar_index > 79 ? ema80[1] + 2.0 / 81.0 * (close - ema80[1]) : na
ema200 := bar_index == 199 ? ta.sma(close, 200) : bar_index > 199 ? ema200[1] + 2.0 / 201.0 * (close - ema200[1]) : na

{functions}

f_predict(array<float> x) =>
    float raw = {_number(float(model._baseline_prediction[0, 0]))}
{additions}
    1.0 / (1.0 + math.exp(-raw))

f_weekdayIndex() =>
    switch dayofweek(time, i_timezone)
        dayofweek.monday => 0.0
        dayofweek.tuesday => 1.0
        dayofweek.wednesday => 2.0
        dayofweek.thursday => 3.0
        dayofweek.friday => 4.0
        dayofweek.saturday => 5.0
        => 6.0

f_features(float direction) =>
    float atr14 = ta.atr(14)
    float atr56 = ta.atr(56)
    float hourAngle = hour(time, i_timezone) * (2.0 * math.pi / 24.0)
    float weekdayAngle = f_weekdayIndex() * (2.0 * math.pi / 5.0)
    array.from(
         direction * (close - close[1]) / atr14,
         direction * (close - close[4]) / atr14,
         direction * (close - close[16]) / atr14,
         direction * (close - close[64]) / atr14,
         direction * (close - ema20) / atr14,
         direction * (ema80 - ema200) / atr14,
         direction * (ta.rsi(close, 14) - 50.0) / 50.0,
         direction * (close - open) / atr14,
         direction * (close - (high + low) / 2.0) / atr14,
         (high - low) / atr14,
         atr14 / atr56,
         activeSpread / atr14,
         math.sin(hourAngle), math.cos(hourAngle),
         math.sin(weekdayAngle), math.cos(weekdayAngle))

f_scanFeatures(float direction, float spreadValue) =>
    float atr14 = ta.atr(14)
    float atr56 = ta.atr(56)
    float hourAngle = hour(time, i_timezone) * (2.0 * math.pi / 24.0)
    float weekdayAngle = f_weekdayIndex() * (2.0 * math.pi / 5.0)
    array.from(
         direction * (close - close[1]) / atr14,
         direction * (close - close[4]) / atr14,
         direction * (close - close[16]) / atr14,
         direction * (close - close[64]) / atr14,
         direction * (close - ta.ema(close, 20)) / atr14,
         direction * (ta.ema(close, 80) - ta.ema(close, 200)) / atr14,
         direction * (ta.rsi(close, 14) - 50.0) / 50.0,
         direction * (close - open) / atr14,
         direction * (close - (high + low) / 2.0) / atr14,
         (high - low) / atr14,
         atr14 / atr56,
         spreadValue / atr14,
         math.sin(hourAngle), math.cos(hourAngle),
         math.sin(weekdayAngle), math.cos(weekdayAngle))

f_scanProbabilities() =>
    string requestedPair = syminfo.basecurrency + syminfo.currency
    float requestedSpread = f_pairSpread(requestedPair)
    bool calculationReady = bar_index >= 208 and not na(requestedSpread)
    bool hourlyNow = minute(time, i_timezone) == 0
    float longNow = calculationReady and hourlyNow ? f_predict(f_scanFeatures(1.0, requestedSpread)) : na
    float shortNow = calculationReady and hourlyNow ? f_predict(f_scanFeatures(-1.0, requestedSpread)) : na
    float lastHourlyLong = ta.valuewhen(hourlyNow, longNow, 0)
    float lastHourlyShort = ta.valuewhen(hourlyNow, shortNow, 0)
    float lastHourlyClose = ta.valuewhen(hourlyNow, close, 0)
    float lastHourlyAtr = ta.valuewhen(hourlyNow, ta.atr(14), 0)
    int hourlyAge = ta.barssince(hourlyNow)
    float entryOpen = hourlyAge == 1 ? open : na
    [lastHourlyLong, lastHourlyShort, hourlyAge, entryOpen, requestedSpread,
     lastHourlyClose, lastHourlyAtr]

f_scanHtfTrend() =>
    float pivotHigh = ta.pivothigh(high, 2, 2)
    float pivotLow = ta.pivotlow(low, 2, 2)
    float lastHigh = ta.valuewhen(not na(pivotHigh), pivotHigh, 0)
    float previousHigh = ta.valuewhen(not na(pivotHigh), pivotHigh, 1)
    float lastLow = ta.valuewhen(not na(pivotLow), pivotLow, 0)
    float previousLow = ta.valuewhen(not na(pivotLow), pivotLow, 1)
    int trend = lastHigh > previousHigh and lastLow > previousLow ? 1 :
         lastHigh < previousHigh and lastLow < previousLow ? -1 : 0
    trend[1]

f_scanName(string symbol) =>
    string value = str.replace_all(symbol, "OANDA:", "")
    value := str.replace_all(value, "FX:", "")
    value := str.replace_all(value, "FOREXCOM:", "")
    value

f_scanRow(table target, int row, string symbol, int trend,
     float longValue, float shortValue, int hourlyAge,
     float entryOpen, float requestedSpread, float signalClose, float signalAtr) =>
    bool fresh = hourlyAge >= 0 and hourlyAge <= 1
    bool buyReady = fresh and trend == 1 and longValue >= {threshold} and longValue >= shortValue
    bool sellReady = fresh and trend == -1 and shortValue >= {threshold} and shortValue >= longValue
    string statusText = buyReady ? "BUY" : sellReady ? "SELL" :
         trend == 1 ? "買い監視" : trend == -1 ? "売り監視" : "方向待ち"
    color statusColor = buyReady ? color.rgb(34, 197, 94) :
         sellReady ? color.rgb(239, 68, 68) :
         trend == 1 ? color.rgb(21, 128, 61) :
         trend == -1 ? color.rgb(185, 28, 28) : color.rgb(75, 85, 99)
    float activeProbability = trend == 1 ? longValue : trend == -1 ? shortValue : math.max(longValue, shortValue)
    float entryPrice = buyReady and not na(entryOpen) ? entryOpen + requestedSpread :
         sellReady and not na(entryOpen) ? entryOpen : na
    float stopPrice = buyReady ? signalClose - signalAtr * 2.0 :
         sellReady ? signalClose + signalAtr * 2.0 + requestedSpread : na
    string entryText = buyReady or sellReady ?
         na(entryPrice) ? "次足始値" : str.tostring(entryPrice, "#.#####") : "--"
    string stopText = buyReady or sellReady ?
         na(stopPrice) ? "計算待ち" : str.tostring(stopPrice, "#.#####") : "--"
    table.cell(target, 0, row, f_scanName(symbol), text_color=color.white,
         bgcolor=color.rgb(31, 41, 55))
    table.cell(target, 1, row, trend == 1 ? "↑" : trend == -1 ? "↓" : "–",
         text_color=color.white, bgcolor=statusColor)
    table.cell(target, 2, row, statusText, text_color=color.white, bgcolor=statusColor)
    table.cell(target, 3, row, na(activeProbability) ? "--" :
         str.tostring(activeProbability * 100.0, "#.0") + "%",
         text_color=color.white, bgcolor=color.rgb(17, 24, 39))
    table.cell(target, 4, row, entryText, text_color=color.white,
         bgcolor=buyReady or sellReady ? statusColor : color.rgb(17, 24, 39))
    table.cell(target, 5, row, stopText, text_color=color.white,
         bgcolor=buyReady or sellReady ? color.rgb(153, 27, 27) : color.rgb(17, 24, 39))

bool hourlyBar = minute(time, i_timezone) == 0
[htfLastHigh, htfPreviousHigh, htfLastLow, htfPreviousLow] = request.security(
     syminfo.tickerid, "240", f_htfContext(),
     gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
bool hasHtfTrend = not na(htfLastHigh) and not na(htfPreviousHigh) and
     not na(htfLastLow) and not na(htfPreviousLow)
int htfTrend = hasHtfTrend and htfLastHigh > htfPreviousHigh and
     htfLastLow > htfPreviousLow ? 1 :
     hasHtfTrend and htfLastHigh < htfPreviousHigh and
     htfLastLow < htfPreviousLow ? -1 : 0

// 確定ピボットだけを使う非リペイントの分析表示。
float analysisPivotHigh = ta.pivothigh(high, i_analysisPivotBars, i_analysisPivotBars)
float analysisPivotLow = ta.pivotlow(low, i_analysisPivotBars, i_analysisPivotBars)
float analysisHigh1 = ta.valuewhen(not na(analysisPivotHigh), analysisPivotHigh, 0)
float analysisHigh2 = ta.valuewhen(not na(analysisPivotHigh), analysisPivotHigh, 1)
float analysisLow1 = ta.valuewhen(not na(analysisPivotLow), analysisPivotLow, 0)
float analysisLow2 = ta.valuewhen(not na(analysisPivotLow), analysisPivotLow, 1)
int analysisHighBar1 = int(ta.valuewhen(not na(analysisPivotHigh), bar_index - i_analysisPivotBars, 0))
int analysisHighBar2 = int(ta.valuewhen(not na(analysisPivotHigh), bar_index - i_analysisPivotBars, 1))
int analysisLowBar1 = int(ta.valuewhen(not na(analysisPivotLow), bar_index - i_analysisPivotBars, 0))
int analysisLowBar2 = int(ta.valuewhen(not na(analysisPivotLow), bar_index - i_analysisPivotBars, 1))
bool analysisUpStructure = analysisHigh1 > analysisHigh2 and analysisLow1 > analysisLow2
bool analysisDownStructure = analysisHigh1 < analysisHigh2 and analysisLow1 < analysisLow2
int analysisDirection = analysisUpStructure ? 1 : analysisDownStructure ? -1 : htfTrend
bool ready = bar_index >= 208 and barstate.isconfirmed and correctTimeframe and
     yearAllowed and supportedPair and not na(activeSpread)
float longProbability = ready and hourlyBar ? f_predict(f_features(1.0)) : na
float shortProbability = ready and hourlyBar ? f_predict(f_features(-1.0)) : na

var float lastLongProbability = na
var float lastShortProbability = na
var int evaluatedBars = 0
if not na(longProbability) and not na(shortProbability)
    lastLongProbability := longProbability
    lastShortProbability := shortProbability
    evaluatedBars += 1

var int pendingSignalBar = na
var int pendingDirection = 0
var float pendingClose = na
var float pendingAtr = na
var bool trackingTrade = false
var int tradeDirection = 0
var float trackedEntry = na
var float trackedStop = na
var float trackedTarget = na
var float historicalEntry = na
var float historicalStop = na
var float historicalTarget = na
var int historicalLineEndBar = na
var int wins = 0
var int losses = 0
var int entryCount = 0
var array<line> tradeLines = array.new_line()
var array<label> tradeLabels = array.new_label()
var array<box> tradeZones = array.new_box()

bool buyEntry = ready and hourlyBar and not trackingTrade and na(pendingSignalBar) and
     longProbability >= {threshold}{htf_buy_filter} and longProbability >= shortProbability
bool sellEntry = ready and hourlyBar and not trackingTrade and na(pendingSignalBar) and
     shortProbability >= {threshold}{htf_sell_filter} and shortProbability >= longProbability

if buyEntry or sellEntry
    entryCount += 1
    pendingSignalBar := bar_index
    pendingDirection := buyEntry ? 1 : -1
    pendingClose := close
    pendingAtr := ta.atr(14)

if not na(pendingSignalBar) and bar_index == pendingSignalBar + 1
    float entryPrice = pendingDirection == 1 ? open + activeSpread : open
    trackedEntry := entryPrice
    tradeDirection := pendingDirection
    if tradeDirection == 1
        trackedStop := pendingClose - pendingAtr * 2.0
    else
        trackedStop := pendingClose + pendingAtr * 2.0 + activeSpread
    float risk = math.abs(entryPrice - trackedStop)
    trackedTarget := tradeDirection == 1 ? entryPrice + risk : entryPrice - risk
    trackingTrade := risk > 0.0
    if trackingTrade
        historicalEntry := trackedEntry
        historicalStop := trackedStop
        historicalTarget := trackedTarget
        historicalLineEndBar := bar_index + i_entryLineBars
    if trackingTrade
        int planEndBar = bar_index + i_entryLineBars
        float profitTop = math.max(entryPrice, trackedTarget)
        float profitBottom = math.min(entryPrice, trackedTarget)
        float riskTop = math.max(entryPrice, trackedStop)
        float riskBottom = math.min(entryPrice, trackedStop)
        box profitZone = box.new(bar_index, profitTop, planEndBar, profitBottom,
             xloc=xloc.bar_index, border_color=color.new(color.lime, 35),
             bgcolor=color.new(color.lime, 88))
        box riskZone = box.new(bar_index, riskTop, planEndBar, riskBottom,
             xloc=xloc.bar_index, border_color=color.new(color.red, 35),
             bgcolor=color.new(color.red, 88))
        line entryLine = line.new(bar_index, entryPrice, bar_index + i_entryLineBars,
             entryPrice, xloc=xloc.bar_index, color=color.yellow, width=2,
             style=line.style_solid)
        line targetLine = line.new(bar_index, trackedTarget, bar_index + i_entryLineBars,
             trackedTarget, xloc=xloc.bar_index, color=color.lime, width=2,
             style=line.style_dashed)
        line stopLine = line.new(bar_index, trackedStop, bar_index + i_entryLineBars,
             trackedStop, xloc=xloc.bar_index, color=color.red, width=2,
             style=line.style_dotted)
        label entryLabel = label.new(bar_index + i_entryLineBars, entryPrice,
             "ENTRY\\n" + str.tostring(entryPrice, format.mintick),
             xloc=xloc.bar_index, style=label.style_label_left,
             color=color.yellow, textcolor=color.black, size=size.tiny)
        label targetLabel = label.new(bar_index + i_entryLineBars, trackedTarget,
             "TP 利確\\n" + str.tostring(trackedTarget, format.mintick),
             xloc=xloc.bar_index,
             style=tradeDirection == 1 ? label.style_label_down : label.style_label_up,
             color=color.rgb(22, 163, 74), textcolor=color.white, size=size.tiny)
        label stopLabel = label.new(bar_index + i_entryLineBars, trackedStop,
             "SL 損切り\\n" + str.tostring(trackedStop, format.mintick),
             xloc=xloc.bar_index,
             style=tradeDirection == 1 ? label.style_label_up : label.style_label_down,
             color=color.rgb(220, 38, 38), textcolor=color.white, size=size.tiny)
        array.push(tradeLines, entryLine)
        array.push(tradeLines, targetLine)
        array.push(tradeLines, stopLine)
        array.push(tradeLabels, entryLabel)
        array.push(tradeLabels, targetLabel)
        array.push(tradeLabels, stopLabel)
        array.push(tradeZones, profitZone)
        array.push(tradeZones, riskZone)
        // 決済後も残し、指定件数を超えた場合だけ最古のトレードから削除する。
        int historyObjectLimit = i_historyTradeCount * 3
        while array.size(tradeLines) > historyObjectLimit
            line.delete(array.shift(tradeLines))
        while array.size(tradeLabels) > historyObjectLimit
            label.delete(array.shift(tradeLabels))
        int historyZoneLimit = i_historyTradeCount * 2
        while array.size(tradeZones) > historyZoneLimit
            box.delete(array.shift(tradeZones))
    pendingSignalBar := na
    pendingDirection := 0
    pendingClose := na
    pendingAtr := na

bool winThisBar = false
bool lossThisBar = false
if trackingTrade
    bool hitStop = tradeDirection == 1 ? low <= trackedStop : high + activeSpread >= trackedStop
    bool hitTarget = tradeDirection == 1 ? high >= trackedTarget : low + activeSpread <= trackedTarget
    if hitStop or hitTarget
        if hitStop
            losses += 1
            lossThisBar := true
        else
            wins += 1
            winThisBar := true
        trackingTrade := false
        tradeDirection := 0
        trackedEntry := na
        trackedStop := na
        trackedTarget := na

int closedTrades = wins + losses
float winRate = closedTrades > 0 ? wins * 100.0 / closedTrades : na
bool showHistoricalWindow = not na(historicalLineEndBar) and
     bar_index <= historicalLineEndBar
float pendingEntryPrice = not na(pendingSignalBar) ?
     pendingDirection == 1 ? pendingClose + activeSpread : pendingClose : na
float pendingStopPrice = not na(pendingSignalBar) ?
     pendingDirection == 1 ? pendingClose - pendingAtr * 2.0 :
     pendingClose + pendingAtr * 2.0 + activeSpread : na
float visibleEntry = not na(pendingEntryPrice) ? pendingEntryPrice :
     trackingTrade ? trackedEntry : showHistoricalWindow ? historicalEntry : na
float visibleStop = not na(pendingStopPrice) ? pendingStopPrice :
     trackingTrade ? trackedStop : showHistoricalWindow ? historicalStop : na
float visibleTarget = trackingTrade ? trackedTarget :
     showHistoricalWindow ? historicalTarget : na
// 透明plotで価格を自動縮尺へ含め、見た目は名称付きlineだけにする。
plot(visibleEntry, "Entry scale", color=color.new(color.yellow, 100), linewidth=1,
     style=plot.style_linebr)
plot(visibleStop, "SL scale", color=color.new(color.red, 100), linewidth=1,
     style=plot.style_linebr)
plot(visibleTarget, "TP scale", color=color.new(color.lime, 100), linewidth=1,
     style=plot.style_linebr)
plotshape(buyEntry, "ML BUY", shape.labelup, location.belowbar, color=#00C853,
     text="BUY", textcolor=color.white, size=size.tiny)
plotshape(sellEntry, "ML SELL", shape.labeldown, location.abovebar, color=#D50000,
     text="SELL", textcolor=color.white, size=size.tiny)
plotshape(winThisBar, "WIN", shape.circle, location.abovebar, color=#00C853,
     text="W", textcolor=color.white, size=size.tiny)
plotshape(lossThisBar, "LOSS", shape.circle, location.belowbar, color=#D50000,
     text="L", textcolor=color.white, size=size.tiny)
plotshape(i_showAnalysis and not na(analysisPivotHigh), "確定スイング高値",
     shape.triangledown, location.abovebar, offset=-i_analysisPivotBars,
     color=color.rgb(239, 68, 68), text="H", textcolor=color.white, size=size.tiny)
plotshape(i_showAnalysis and not na(analysisPivotLow), "確定スイング安値",
     shape.triangleup, location.belowbar, offset=-i_analysisPivotBars,
     color=color.rgb(37, 99, 235), text="L", textcolor=color.white, size=size.tiny)

var array<line> analysisLines = array.new_line()
var array<label> analysisLabels = array.new_label()
if barstate.islast
    while array.size(analysisLines) > 0
        line.delete(array.pop(analysisLines))
    while array.size(analysisLabels) > 0
        label.delete(array.pop(analysisLabels))
    if i_showAnalysis
        int analysisEndBar = bar_index + i_analysisScenarioBars
        if not na(analysisHigh1) and not na(analysisHighBar1)
            line resistance1 = line.new(analysisHighBar1, analysisHigh1, analysisEndBar, analysisHigh1,
                 xloc=xloc.bar_index, color=color.rgb(245, 158, 11), width=2)
            label resistance1Label = label.new(analysisEndBar, analysisHigh1,
                 "R1 " + str.tostring(analysisHigh1, format.mintick), xloc=xloc.bar_index,
                 style=label.style_label_left, color=color.rgb(180, 83, 9),
                 textcolor=color.white, size=size.tiny)
            array.push(analysisLines, resistance1)
            array.push(analysisLabels, resistance1Label)
        if not na(analysisHigh2) and not na(analysisHighBar2)
            line resistance2 = line.new(analysisHighBar2, analysisHigh2, analysisEndBar, analysisHigh2,
                 xloc=xloc.bar_index, color=color.new(color.rgb(245, 158, 11), 45),
                 width=1, style=line.style_dashed)
            array.push(analysisLines, resistance2)
        if not na(analysisLow1) and not na(analysisLowBar1)
            line support1 = line.new(analysisLowBar1, analysisLow1, analysisEndBar, analysisLow1,
                 xloc=xloc.bar_index, color=color.rgb(37, 99, 235), width=2)
            label support1Label = label.new(analysisEndBar, analysisLow1,
                 "S1 " + str.tostring(analysisLow1, format.mintick), xloc=xloc.bar_index,
                 style=label.style_label_left, color=color.rgb(29, 78, 216),
                 textcolor=color.white, size=size.tiny)
            array.push(analysisLines, support1)
            array.push(analysisLabels, support1Label)
        if not na(analysisLow2) and not na(analysisLowBar2)
            line support2 = line.new(analysisLowBar2, analysisLow2, analysisEndBar, analysisLow2,
                 xloc=xloc.bar_index, color=color.new(color.rgb(37, 99, 235), 45),
                 width=1, style=line.style_dashed)
            array.push(analysisLines, support2)

        if not na(analysisHigh1) and not na(analysisHigh2) and analysisHighBar1 > analysisHighBar2
            float upperSlope = (analysisHigh1 - analysisHigh2) / (analysisHighBar1 - analysisHighBar2)
            float upperProjected = analysisHigh1 + upperSlope * (analysisEndBar - analysisHighBar1)
            line upperChannel = line.new(analysisHighBar2, analysisHigh2, analysisEndBar, upperProjected,
                 xloc=xloc.bar_index, color=color.rgb(29, 78, 216), width=2)
            array.push(analysisLines, upperChannel)
        if not na(analysisLow1) and not na(analysisLow2) and analysisLowBar1 > analysisLowBar2
            float lowerSlope = (analysisLow1 - analysisLow2) / (analysisLowBar1 - analysisLowBar2)
            float lowerProjected = analysisLow1 + lowerSlope * (analysisEndBar - analysisLowBar1)
            line lowerChannel = line.new(analysisLowBar2, analysisLow2, analysisEndBar, lowerProjected,
                 xloc=xloc.bar_index, color=color.rgb(29, 78, 216), width=2)
            array.push(analysisLines, lowerChannel)

        float analysisAtr = ta.atr(14)
        if analysisDirection != 0 and not na(analysisAtr)
            int scenarioBar1 = bar_index + int(math.round(i_analysisScenarioBars / 3.0))
            int scenarioBar2 = bar_index + int(math.round(i_analysisScenarioBars * 2.0 / 3.0))
            float scenarioTurn = analysisDirection == 1 ?
                 (na(analysisLow1) ? close - analysisAtr : math.max(analysisLow1, close - analysisAtr)) :
                 (na(analysisHigh1) ? close + analysisAtr : math.min(analysisHigh1, close + analysisAtr))
            float scenarioTarget = analysisDirection == 1 ?
                 (na(analysisHigh1) or analysisHigh1 <= close ? close + analysisAtr * 1.5 : analysisHigh1) :
                 (na(analysisLow1) or analysisLow1 >= close ? close - analysisAtr * 1.5 : analysisLow1)
            float scenarioExtension = analysisDirection == 1 ?
                 scenarioTarget + analysisAtr : scenarioTarget - analysisAtr
            color scenarioColor = analysisDirection == 1 ? color.rgb(22, 163, 74) : color.rgb(220, 38, 38)
            line scenario1 = line.new(bar_index, close, scenarioBar1, scenarioTurn,
                 xloc=xloc.bar_index, color=scenarioColor, width=2, style=line.style_dotted)
            line scenario2 = line.new(scenarioBar1, scenarioTurn, scenarioBar2, scenarioTarget,
                 xloc=xloc.bar_index, color=scenarioColor, width=2, style=line.style_dotted)
            line scenario3 = line.new(scenarioBar2, scenarioTarget, analysisEndBar, scenarioExtension,
                 xloc=xloc.bar_index, color=scenarioColor, width=2, style=line.style_dotted)
            label scenarioLabel = label.new(analysisEndBar, scenarioExtension,
                 analysisDirection == 1 ? "上昇シナリオ" : "下降シナリオ",
                 xloc=xloc.bar_index, style=analysisDirection == 1 ? label.style_label_up : label.style_label_down,
                 color=scenarioColor, textcolor=color.white, size=size.tiny)
            array.push(analysisLines, scenario1)
            array.push(analysisLines, scenario2)
            array.push(analysisLines, scenario3)
            array.push(analysisLabels, scenarioLabel)
bgcolor(not correctTimeframe or not supportedPair or not yearAllowed ? color.new(color.orange, 88) : na)
alertcondition(buyEntry, "コンパクトML BUY", "固定11通貨 コンパクトML: BUY")
alertcondition(sellEntry, "コンパクトML SELL", "固定11通貨 コンパクトML: SELL")

string runtimeStatus = "稼働中"
if not correctTimeframe
    runtimeStatus := "15分足に変更"
else if not supportedPair
    runtimeStatus := "対象外: " + pair
else if not yearAllowed
    runtimeStatus := "2026年外"
else if bar_index < 208
    runtimeStatus := "計算準備中"
else if trackingTrade
    runtimeStatus := "保有判定中"
else if htfTrend == 0
    runtimeStatus := "4H方向待ち"

var table stats = table.new(position.middle_right, 2, 13, border_width=1)
table.cell(stats, 0, 0, "Compact ML", bgcolor=color.new(color.blue, 35), text_color=color.white)
table.cell(stats, 1, 0, runtimeStatus, bgcolor=color.new(color.blue, 35), text_color=color.white)
table.cell(stats, 0, 1, "通貨 / 足")
table.cell(stats, 1, 1, pair + " / " + timeframe.period)
table.cell(stats, 0, 2, "検出数")
table.cell(stats, 1, 2, str.tostring(entryCount))
table.cell(stats, 0, 3, "当チャート勝率")
table.cell(stats, 1, 3, na(winRate) ? "--" : str.tostring(winRate, "#.00") + "%")
table.cell(stats, 0, 4, "勝ち / 負け")
table.cell(stats, 1, 4, str.tostring(wins) + " / " + str.tostring(losses))
table.cell(stats, 0, 5, "判定済み正時")
table.cell(stats, 1, 5, str.tostring(evaluatedBars))
table.cell(stats, 0, 6, "直近の買い確率")
table.cell(stats, 1, 6, na(lastLongProbability) ? "--" : str.tostring(lastLongProbability, "#.000"))
table.cell(stats, 0, 7, "直近の売り確率")
table.cell(stats, 1, 7, na(lastShortProbability) ? "--" : str.tostring(lastShortProbability, "#.000"))
table.cell(stats, 0, 8, "閾値")
table.cell(stats, 1, 8, "{threshold}")
table.cell(stats, 0, 9, "表示期間")
table.cell(stats, 1, 9, i_only2026 ? "2026年のみ" : "全期間（参考）")
table.cell(stats, 0, 10, "判定")
table.cell(stats, 1, 10, "正時判定→次足 / RR1:1")
table.cell(stats, 0, 11, "確定4H方向")
table.cell(stats, 1, 11, htfTrend == 1 ? "上昇・買いのみ" : htfTrend == -1 ? "下降・売りのみ" : "方向待ち")
table.cell(stats, 0, 12, "11通貨検証参考")
table.cell(stats, 1, 12, "2026: 72.8% / 312件")

[scanLong1, scanShort1, scanAge1, scanOpen1, scanSpread1, scanClose1, scanAtr1] = request.security(i_scanSymbol1, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong2, scanShort2, scanAge2, scanOpen2, scanSpread2, scanClose2, scanAtr2] = request.security(i_scanSymbol2, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong3, scanShort3, scanAge3, scanOpen3, scanSpread3, scanClose3, scanAtr3] = request.security(i_scanSymbol3, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong4, scanShort4, scanAge4, scanOpen4, scanSpread4, scanClose4, scanAtr4] = request.security(i_scanSymbol4, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong5, scanShort5, scanAge5, scanOpen5, scanSpread5, scanClose5, scanAtr5] = request.security(i_scanSymbol5, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong6, scanShort6, scanAge6, scanOpen6, scanSpread6, scanClose6, scanAtr6] = request.security(i_scanSymbol6, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong7, scanShort7, scanAge7, scanOpen7, scanSpread7, scanClose7, scanAtr7] = request.security(i_scanSymbol7, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong8, scanShort8, scanAge8, scanOpen8, scanSpread8, scanClose8, scanAtr8] = request.security(i_scanSymbol8, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong9, scanShort9, scanAge9, scanOpen9, scanSpread9, scanClose9, scanAtr9] = request.security(i_scanSymbol9, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong10, scanShort10, scanAge10, scanOpen10, scanSpread10, scanClose10, scanAtr10] = request.security(i_scanSymbol10, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
[scanLong11, scanShort11, scanAge11, scanOpen11, scanSpread11, scanClose11, scanAtr11] = request.security(i_scanSymbol11, "15", f_scanProbabilities(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_off)
int scanTrend1 = request.security(i_scanSymbol1, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend2 = request.security(i_scanSymbol2, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend3 = request.security(i_scanSymbol3, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend4 = request.security(i_scanSymbol4, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend5 = request.security(i_scanSymbol5, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend6 = request.security(i_scanSymbol6, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend7 = request.security(i_scanSymbol7, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend8 = request.security(i_scanSymbol8, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend9 = request.security(i_scanSymbol9, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend10 = request.security(i_scanSymbol10, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)
int scanTrend11 = request.security(i_scanSymbol11, "240", f_scanHtfTrend(), gaps=barmerge.gaps_off, lookahead=barmerge.lookahead_on)

var table scanner = table.new(position.bottom_right, 6, 13, border_width=1)
if barstate.islast and i_showScanner
    table.cell(scanner, 0, 0, "通貨", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 1, 0, "4H", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 2, 0, "チャンス", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 3, 0, "ML値", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 4, 0, "Entry", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 5, 0, "SL", text_color=color.white, bgcolor=color.rgb(153, 27, 27))
    f_scanRow(scanner, 1, i_scanSymbol1, scanTrend1, scanLong1, scanShort1, scanAge1, scanOpen1, scanSpread1, scanClose1, scanAtr1)
    f_scanRow(scanner, 2, i_scanSymbol2, scanTrend2, scanLong2, scanShort2, scanAge2, scanOpen2, scanSpread2, scanClose2, scanAtr2)
    f_scanRow(scanner, 3, i_scanSymbol3, scanTrend3, scanLong3, scanShort3, scanAge3, scanOpen3, scanSpread3, scanClose3, scanAtr3)
    f_scanRow(scanner, 4, i_scanSymbol4, scanTrend4, scanLong4, scanShort4, scanAge4, scanOpen4, scanSpread4, scanClose4, scanAtr4)
    f_scanRow(scanner, 5, i_scanSymbol5, scanTrend5, scanLong5, scanShort5, scanAge5, scanOpen5, scanSpread5, scanClose5, scanAtr5)
    f_scanRow(scanner, 6, i_scanSymbol6, scanTrend6, scanLong6, scanShort6, scanAge6, scanOpen6, scanSpread6, scanClose6, scanAtr6)
    f_scanRow(scanner, 7, i_scanSymbol7, scanTrend7, scanLong7, scanShort7, scanAge7, scanOpen7, scanSpread7, scanClose7, scanAtr7)
    f_scanRow(scanner, 8, i_scanSymbol8, scanTrend8, scanLong8, scanShort8, scanAge8, scanOpen8, scanSpread8, scanClose8, scanAtr8)
    f_scanRow(scanner, 9, i_scanSymbol9, scanTrend9, scanLong9, scanShort9, scanAge9, scanOpen9, scanSpread9, scanClose9, scanAtr9)
    f_scanRow(scanner, 10, i_scanSymbol10, scanTrend10, scanLong10, scanShort10, scanAge10, scanOpen10, scanSpread10, scanClose10, scanAtr10)
    f_scanRow(scanner, 11, i_scanSymbol11, scanTrend11, scanLong11, scanShort11, scanAge11, scanOpen11, scanSpread11, scanClose11, scanAtr11)
    table.cell(scanner, 0, 12, "基準", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 1, 12, "", bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 2, 12, "48.5%以上", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 3, 12, "勝率ではない", text_color=color.rgb(254, 240, 138), bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 4, 12, "成立時表示", text_color=color.white, bgcolor=color.rgb(30, 64, 175))
    table.cell(scanner, 5, 12, "ATR×2", text_color=color.white, bgcolor=color.rgb(153, 27, 27))
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--pine-output",
        type=Path,
        default=Path("scripts/tradingview/shared_feature_entry_logic.pine"),
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("scripts/tradingview/compact_ml_model_2026.json"),
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--require-htf-alignment", action="store_true")
    args = parser.parse_args()
    repository = HistoryRepository(args.history_dir)
    end = datetime(2025, 12, 31, 23, 59, 59)
    prepared = {}
    opportunities = {}
    for symbol in SYMBOLS:
        print(f"Loading and labeling {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        opportunities[symbol] = _opportunities(prepared[symbol], 4, 2.0)
    x_train, y_train = _training_rows(prepared, opportunities, 2026)
    model = _model(CONFIG)
    model.fit(x_train, y_train)
    sample = x_train[:: max(1, x_train.shape[0] // 10_000)][:10_000]
    expected = model.predict_proba(sample)[:, 1]
    actual = _exported_probability(model, sample)
    max_error = float(np.max(np.abs(expected - actual)))
    if max_error > 1e-12:
        raise RuntimeError(f"tree export mismatch: {max_error}")
    payload = {
        "year": 2026,
        "config": asdict(CONFIG),
        "threshold": args.threshold,
        "require_htf_alignment": args.require_htf_alignment,
        "baseline": float(model._baseline_prediction[0, 0]),
        "trees": [
            [
                {
                    "value": float(node["value"]),
                    "feature": int(node["feature_idx"]),
                    "threshold": float(node["num_threshold"]),
                    "left": int(node["left"]),
                    "right": int(node["right"]),
                    "leaf": bool(node["is_leaf"]),
                }
                for node in predictors[0].nodes
            ]
            for predictors in model._predictors
        ],
        "parity_max_abs_error": max_error,
    }
    args.model_output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    pine = _pine(model, args.threshold, args.require_htf_alignment)
    args.pine_output.write_text(pine, encoding="utf-8")
    print(
        f"EXPORTED trees={CONFIG.trees} chars={len(pine)} parity_error={max_error:.3g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
