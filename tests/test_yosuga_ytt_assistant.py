"""Pine source safeguards; these checks do not compile or execute Pine."""

from pathlib import Path
import re


SOURCE = (Path(__file__).parents[1] / "scripts/tradingview/yosuga_ytt_assistant.pine").read_text(encoding="utf-8")


def test_confirmed_context_and_disabled_lower_timeframes():
    assert "[d[1], h[1], l[1], s[1]]" in SOURCE
    assert "lookahead=barmerge.lookahead_on" in SOURCE
    assert "if timeframe.in_seconds(tf) > timeframe.in_seconds()" in SOURCE
    assert "else if timeframe.in_seconds(tf) == timeframe.in_seconds()" in SOURCE
    assert "if barstate.isconfirmed\n    confirmedDirection := currentDirection" in SOURCE
    assert 'string s = "下位足は対象外"' in SOURCE


def test_levels_begin_at_detection_and_are_bounded_together():
    assert "line.new(bar_index, price, bar_index + 1, price, xloc=xloc.bar_index" in SOURCE
    assert "line.set_x2(level, bar_index + 1)" in SOURCE
    assert "int i = array.size(levels) - 1" in SOURCE
    assert "if array.size(levels) > keepLevels" in SOURCE
    for name in ("levels", "levelLabels", "levelSides", "levelActive"):
        assert f"array.remove({name}, i)" in SOURCE
        assert f"array.shift({name})" in SOURCE
    assert SOURCE.index("touchedLevel :=") < SOURCE.index("f_addLevel(pivotHigh")


def test_channel_direction_compares_prices_not_tiny_per_ms_slope():
    assert "rising and p2 > p1 and width > 0" in SOURCE
    assert "not rising and p2 < p1 and width < 0" in SOURCE
    assert not re.search(r"slope\s*[<>]\s*0", SOURCE)
    assert "oppositeTime >= t1 and oppositeTime <= t2" in SOURCE


def test_manual_scenario_guards_and_theoretical_quantity():
    assert 'input.bool(false, "手動シナリオを表示"' in SOURCE
    assert "math.round_to_mintick(entryInput)" in SOURCE
    assert "math.round_to_mintick(stopInput)" in SOURCE
    assert "math.round(math.abs(entry - stop) / syminfo.mintick) * syminfo.mintick" in SOURCE
    assert "distance >= syminfo.mintick" in SOURCE
    assert "stop < entry and target > entry : stop > entry and target < entry" in SOURCE
    assert "math.floor(riskBudget / lossPerQty / quantityStep) * quantityStep" in SOURCE
    assert "capital > 0 and valuePerPrice > 0" in SOURCE
    assert "quantity < quantityStep" in SOURCE
    assert 'array.from("Entry", "TP", "SL")' in SOURCE
    assert "売買注文なし" in SOURCE and "費用なし理論値" in SOURCE
    assert not re.search(r"\bstrategy\.(entry|order|exit)\s*\(", SOURCE)


def test_notifications_require_confirmed_information():
    assert 'alertcondition(barstate.isconfirmed and touchedLevel, "確定足の水平線接触"' in SOURCE
    assert "bool directionChanged = barstate.isconfirmed" in SOURCE
    assert "売買シグナルではありません" in SOURCE


def test_all_price_drawings_use_main_chart_scale():
    # Every price constructor must remain attached to the main chart's scale.
    constructors = list(re.finditer(r"(?:line|label)\.new\(", SOURCE))
    assert constructors
    for constructor in constructors:
        depth = 1
        in_string = False
        escaped = False
        end = constructor.end()
        for end in range(end, len(SOURCE)):
            char = SOURCE[end]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
        assert "force_overlay=true" in SOURCE[constructor.end():end]


def test_candidate_events_use_prior_confirmed_pivots_and_strict_close_cross():
    snapshot = SOURCE.index("float candidatePriorHigh = confirmedHigh")
    assert snapshot < SOURCE.index("confirmedHigh := currentHigh")
    assert SOURCE.index("float candidatePriorLow = confirmedLow") < SOURCE.index("confirmedLow := currentLow")
    assert "barstate.isconfirmed and candidateBuyAligned and not candidateHighBroken" in SOURCE
    assert "close > candidatePriorHigh and close[1] <= candidatePriorHigh" in SOURCE
    assert "barstate.isconfirmed and candidateSellAligned and not candidateLowBroken" in SOURCE
    assert "close < candidatePriorLow and close[1] >= candidatePriorLow" in SOURCE


def test_candidates_require_two_distinct_strictly_higher_agreeing_timeframes():
    assert 'input.timeframe("1D", "合意する上位足1"' in SOURCE
    assert 'input.timeframe("1W", "合意する上位足2"' in SOURCE
    assert "timeframe.in_seconds(effectiveCandidateTf1) > timeframe.in_seconds()" in SOURCE
    assert "timeframe.in_seconds(effectiveCandidateTf2) > timeframe.in_seconds()" in SOURCE
    assert "timeframe.in_seconds(effectiveCandidateTf1) != timeframe.in_seconds(effectiveCandidateTf2)" in SOURCE
    assert "candidateDirection1 == 1 and candidateDirection2 == 1" in SOURCE
    assert "candidateDirection1 == -1 and candidateDirection2 == -1" in SOURCE
    assert '"見送り"' in SOURCE and '"時間足設定を確認"' in SOURCE


def test_consumed_pivots_do_not_rearm_on_retracement_or_direction_alignment():
    assert "candidateHighBroken := candidateHighBroken or (not na(candidatePriorHigh) and close > candidatePriorHigh)" in SOURCE
    assert "candidateLowBroken := candidateLowBroken or (not na(candidatePriorLow) and close < candidatePriorLow)" in SOURCE
    assert "if not na(pivotHigh)\n        candidateHighBroken := close > confirmedHigh" in SOURCE
    assert "if not na(pivotLow)\n        candidateLowBroken := close < confirmedLow" in SOURCE
    assert "not candidateAlreadyBroken" in SOURCE
    assert "if array.size(candidateEvents) > 20" in SOURCE
    assert "int candidateNow = bar_index + 1" in SOURCE
    assert "candidateNow + 1, candidatePrice, xloc=xloc.bar_index" in SOURCE


def test_daily_channel_uses_distinct_pivots_and_preserves_current_price():
    # Session close and close+1ms can share a daily chart column. Connect pivots.
    assert "float nowBase = p2 + slope * (time_close - t2)" in SOURCE
    assert "line.new(t1, p1, t2, p2," in SOURCE
    assert "line.new(t1, p1 + width, t2, p2 + width," in SOURCE
    assert "xloc=xloc.bar_time, extend=extend.right, color=color.orange" in SOURCE
    assert "チャネル作成時に初めて判明した参考線" in SOURCE
    assert 'input.bool(false, "終値で突破した水平線を削除"' in SOURCE
    assert SOURCE.index("line.delete(channelBase)") > SOURCE.index("if (rising and p2 > p1")
    assert '前回チャネル（参考）' in SOURCE
    assert 'line.set_style(channelBase, line.style_dotted)' in SOURCE


def test_weekly_context_and_table_rows_stay_within_capacity():
    assert '[dW, hW, lW, sW] = f_context("1W")' in SOURCE
    assert 'f_row(2, "W", dW, hW, lW, sW)' in SOURCE
    capacity = int(re.search(r"table.new\(position.bottom_left, 4, (\d+)", SOURCE).group(1))
    used_rows = [int(r) for r in re.findall(r"table.cell\(panel, \d+, (\d+)", SOURCE)]
    used_rows += [int(r) for r in re.findall(r"f_row\((\d+),", SOURCE)]
    assert set(used_rows) == set(range(capacity))


def test_daily_automatic_context_routes_requests_guard_and_display_together():
    assert 'input.bool(true, "日足では週足＋月足を自動使用"' in SOURCE
    assert 'effectiveCandidateTf1 = timeframe.isdaily and dailyAutoContext ? "1W" : candidateTf1' in SOURCE
    assert 'effectiveCandidateTf2 = timeframe.isdaily and dailyAutoContext ? "1M" : candidateTf2' in SOURCE
    assert 'f_context(effectiveCandidateTf1)' in SOURCE
    assert 'f_context(effectiveCandidateTf2)' in SOURCE
    assert 'f_tfName(effectiveCandidateTf1) + " / " + f_tfName(effectiveCandidateTf2)' in SOURCE
    assert '[dM, hM, lM, sM] = f_context("1M")' in SOURCE
    assert 'f_row(1, "月足", dM, hM, lM, sM)' in SOURCE
    assert 'not candidateDataReady ? "データ不足"' in SOURCE
    readiness = re.search(r"bool candidateDataReady = (.*)", SOURCE).group(1)
    for field in ("candidateDirection1", "candidateDirection2", "candidateHigh1", "candidateLow1", "candidateHigh2", "candidateLow2"):
        assert f"not na({field})" in readiness
    reason = re.search(r"string candidateReason = (.*)", SOURCE).group(1)
    assert "not candidateDataReady ?" in reason
