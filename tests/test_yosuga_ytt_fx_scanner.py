"""Source safety checks only; TradingView must compile and render the final Pine."""
from pathlib import Path
import re

SOURCE = (Path(__file__).parents[1] / "scripts/tradingview/yosuga_ytt_fx_scanner.pine").read_text(encoding="utf-8")


def test_remote_values_and_time_are_confirmed_and_currency_specific():
    assert "[d[1], h[1], l[1]]" in SOURCE
    assert "Snapshot.new(status[1], priceText[1], d1[1], d2[1], time_close[1])" in SOURCE
    assert 'request.security("", contextTf1' in SOURCE
    assert 'request.security("", contextTf2' in SOURCE
    assert "str.tostring(displayedPrice, format.mintick)" in SOURCE
    assert "chartSeconds <= entrySeconds" in SOURCE
    assert "type Snapshot" in SOURCE
    assert SOURCE.count('input.symbol("OANDA:') == 8
    assert "overlay=false" in SOURCE


def test_old_threshold_is_consumed_before_new_pivot_rearms():
    assert "float priorHigh = h[1]" in SOURCE
    assert "float priorLow = l[1]" in SOURCE
    assert "not highBroken" in SOURCE and "not lowBroken" in SOURCE
    assert "close > priorHigh and close[1] <= priorHigh" in SOURCE
    assert "close < priorLow and close[1] >= priorLow" in SOURCE
    assert SOURCE.index("bool buyEvent") < SOURCE.index("highBroken := highBroken or") < SOURCE.index("highBroken := close > h")
    assert "buyEvent ? priorHigh : sellEvent ? priorLow : candidate" in SOURCE
    assert not re.search(r"\bstrategy\.(entry|order|exit)\s*\(", SOURCE)


def test_alerts_do_not_replay_stale_or_initial_events():
    assert "varip array<int> lastSeen" in SOURCE
    assert "stamp > previousStamp" in SOURCE
    assert "alertsEnabled and barstate.isrealtime and realtimeInitialized and newClose and eventNow and not stale" in SOURCE
    assert "ageMinutes > entrySeconds / 60 * 2" in SOURCE
    assert 'stale ? "更新待ち"' in SOURCE
    assert 'input.bool(false, "新しい候補成立を通知対象にする"' in SOURCE
