"""Composition checks, not Pine compilation."""
import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("ytt_builder", ROOT / "scripts/build_ytt_combined_pine.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_combined_keeps_price_drawings_and_is_reproducible():
    source = (ROOT / "scripts/tradingview/yosuga_ytt_combined.pine").read_text(encoding="utf-8")
    assert source == builder.build()
    assert len(re.findall(r"^indicator\(", source, re.M)) == 1
    assert "overlay=false" in source
    for constructor in ("array.push(levels, line.new", "channelBase := line.new", "channelParallel := line.new"):
        assert constructor in source
    for panel in ("panel", "candidatePanel"):
        declaration = next(line for line in source.splitlines() if line.startswith(f"var table {panel} ="))
        assert "force_overlay=true" not in declaration
    assert 'table.new(position.top_left, 4, 13,' in source
    assert 'table.new(position.top_right, 2, 14,' in source
    assert 'var table BB_winStats = candidatePanel' in source
    assert 'table.clear(BB_winStats, 0, 7, 1, 13)' in source
    assert 'table.cell(candidatePanel, 0, 1, "突破候補"' not in source
    assert 'table.new(position.top_right, 2, 14, bgcolor=color.new(color.black, 100), border_width=0)' in source
    assert 'table.cell(BB_winStats, 0, 7, "仮想RR1・研究用"' in source
    assert 'var table scan_panel = combinedScanner == "YTT" and not combinedSimple ? table.new(position.top_center' in source
    assert source.count("int leftBars =") == source.count("int rightBars =") == 1
    assert "Snapshot.new(status[1], priceText[1], d1[1], d2[1], time_close[1])" in source
    assert 'input.symbol("OANDA:EURUSD"' in source
    assert "confirm=true" not in source


def test_bb_price_visuals_and_reversal_rule_survive_composition():
    source = builder.build()
    bb = source.split("// BB reversal: independent research-only", 1)[1]
    for line in bb.splitlines():
        if re.search(r"\b(?:plot|plotshape|label\.new)\(", line):
            assert "force_overlay=true" in line, line
    for rule in (
        "low < BB_cancelLevel : high > BB_cancelLevel",
        "bar_index > BB_confirmedBar", "bar_index > BB_preparedBar",
        "high > BB_threshold : low < BB_threshold",
        "BB_candidateCenter := BB_basis[1]",
        "BB_statsStop := 2 * BB_statsEntry - BB_statsTarget",
        "stopTouched ? BB_statsStop : targetTouched ? BB_statsTarget : na",
    ):
        assert rule in bb
    assert 'BB_restrictChart = input.bool(false, "5分足に限定"' in bb
    assert "array.from(symbol1, symbol2, symbol3, symbol4, symbol5, symbol6, symbol7, symbol8)" in bb
    assert 'bool BB_showScanner = combinedScanner == "BB3σ反転"' in bb
    assert "[state[1], triggerText[1], invalidationText[1], distance[1], time_close[1], skip[1]]" in bb
    assert "alertcondition(bbAlertsEnabled and barstate.isconfirmed" in bb
    assert not re.search(r"\bstrategy\.(entry|order|exit)\s*\(", source)


def test_namespacing_does_not_rewrite_user_strings_or_comments():
    assert builder.rename_identifiers('side = "side" // side\nside := side', {"side"}, "BB_") == 'BB_side = "side" // side\nBB_side := BB_side'


def test_simple_display_filters_confirmed_fresh_events_and_waiting_only():
    source = builder.build()
    assert 'combinedSimple = input.bool(true,' in source
    assert 'if barstate.islast and not combinedSimple' in source
    assert 'for priority = 0 to 1' in source
    assert 'int s = fresh ? item.status : 0' in source
    assert 'bool event = s == 3 or s == 4' in source
    assert 'bool waiting = s == 1 or s == 2' in source
    assert 'if fresh and (priority == 0 ? event : waiting)' in source
    assert 'alertsEnabled and barstate.isrealtime and realtimeInitialized and newClose and eventNow and not stale' in source
