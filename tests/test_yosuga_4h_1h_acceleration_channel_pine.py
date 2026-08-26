from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "yosuga_4h_1h_acceleration_channel.pine"
).read_text(encoding="utf-8")


def test_indicator_is_visual_only_and_uses_confirmed_4h_1h_context() -> None:
    assert SOURCE.startswith("//@version=6\n")
    assert 'indicator("よすが式 4H・1H 加速減速 + 平行チャネル v1"' in SOURCE
    assert "strategy(" not in SOURCE
    assert 'syminfo.tickerid, "240", f_confirmedContext(i_4hPivot)' in SOURCE
    assert 'syminfo.tickerid, "60", f_confirmedContext(i_1hPivot)' in SOURCE
    assert SOURCE.count("lookahead=barmerge.lookahead_on") == 2
    assert "close[1], close[2], close[3], atrValue[1]" in SOURCE
    assert "high1[1], high2[1], low1[1], low2[1]" in SOURCE


def test_acceleration_and_deceleration_are_atr_normalized() -> None:
    assert "direction * (close1 - close2) / atrValue" in SOURCE
    assert "direction * (close2 - close3) / atrValue" in SOURCE
    assert "change > i_phaseThresholdAtr ? 2" in SOURCE
    assert "change < -i_phaseThresholdAtr ? -1 : 1" in SOURCE
    assert 'phase == 2 ? "加速"' in SOURCE
    assert 'phase == -1 ? "減速"' in SOURCE
    assert 'phase == -2 ? "押し・戻り"' in SOURCE


def test_four_hour_and_one_hour_channels_are_parallel_and_distinct() -> None:
    assert "f_channelSlope" in SOURCE
    assert "direction == 1 and not na(lowSlope) ? lowSlope" in SOURCE
    assert "direction == -1 and not na(highSlope) ? highSlope" in SOURCE
    assert "h4UpperEnd = h4High1 + h4ChannelSlope" in SOURCE
    assert "h4LowerEnd = h4Low1 + h4ChannelSlope" in SOURCE
    assert "h1UpperEnd = h1High1 + h1ChannelSlope" in SOURCE
    assert "h1LowerEnd = h1Low1 + h1ChannelSlope" in SOURCE
    assert '"4Hチャネル"' in SOURCE
    assert '"1Hチャネル"' in SOURCE
    assert "xloc=xloc.bar_time" in SOURCE


def test_state_table_background_labels_and_alerts_are_present() -> None:
    assert "table.new(position.top_right, 5, 4" in SOURCE
    assert '"同方向・両方加速"' in SOURCE
    assert '"方向不一致"' in SOURCE
    assert '"減速あり"' in SOURCE
    assert "bgcolor(i_showBackground ? contextBackground : na" in SOURCE
    assert 'alertcondition(new4hAcceleration, "よすが式 4H加速"' in SOURCE
    assert 'alertcondition(new1hDeceleration, "よすが式 1H減速"' in SOURCE
    assert 'alertcondition(newBothAcceleration, "よすが式 4H・1H同方向加速"' in SOURCE


def test_chart_guard_and_object_retention_are_bounded() -> None:
    assert "timeframe.in_seconds() <= 60 * 60" in SOURCE
    assert '"1時間足以下で使用してください' in SOURCE
    assert "while array.size(stateLabels) > i_keepStateLabels" in SOURCE
    assert "max_lines_count=50" in SOURCE
    assert "max_labels_count=300" in SOURCE
