"""Local source-contract checks, not a Pine compiler or broker-emulator test."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PINE = ROOT / "scripts/tradingview/research/tamukai_stocks_no_dow_rr1_strategy.pine"


def source():
    return PINE.read_text(encoding="utf-8")


def test_daily_long_only_fixed_research_contract():
    text = source()
    assert text.startswith("//@version=6")
    for token in ("strategy(", "pyramiding = 0", "initial_capital = 100000",
                  "currency.JPY", "commission_value = 0.1", "ta.sma(close, 21)",
                  "timeframe.isdaily", "timeframe.multiplier", "runtime.error("):
        assert token in text
    for token in ("strategy.short", "request.security(", "lookahead_on", "ta.pivothigh(",
                  "ta.pivotlow(", "ta.atr(", "trail_points", "alert("):
        assert token not in text


def test_market_entry_is_not_filled_at_signal_close():
    text = source()
    for token in ("process_orders_on_close = false", "calc_on_order_fills = true",
                  "calc_on_every_tick = false", "barstate.isconfirmed", "varip"):
        assert token in text
    entries = re.findall(r"strategy\.entry\((.*?)\)", text, re.S)
    assert len(entries) == 1
    assert "strategy.long" in entries[0]
    assert "limit =" not in entries[0] and "stop =" not in entries[0]


def test_signal_excludes_current_bar_from_pullback_high_and_stop():
    text = source()
    for token in ("ta.highest(high[1], 3)", "ta.lowest(low[1], 3)",
                  "low[1] <= sma21[1] or low[2] <= sma21[2] or low[3] <= sma21[3]",
                  "bar_index >= 23 and close > sma21 and sma21 > sma21[2] and touched and close > priorHigh",
                  "stopPrice := priorLow"):
        assert token in text


def test_fill_callback_cannot_submit_fresh_signal_order():
    text = source()
    assert "barstate.isconfirmed and not fillExecution and lastDecisionBar != bar_index" in text
    assert "strategy.position_size != seenPosition or strategy.closedtrades != seenClosed" in text
    assert text.index("if closedDecision") < text.index('strategy.entry("Long"')
    assert "targetPrice := entryPrice + (entryPrice - stopPrice)" in text
    assert text.count("stopPrice :=") == 1  # Freeze stop; never trail after filling.


def test_risk_uses_actual_fill_and_full_bracket_exit():
    text = source()
    assert "strategy.position_avg_price" in text
    brackets = re.findall(r"strategy\.exit\((.*?)\)", text, re.S)
    assert len(brackets) == 1
    assert "stop =" in brackets[0] and "limit =" in brackets[0]
    assert "qty_percent = 100" in brackets[0]
    assert "immediately = true" in text  # Invalid gap fill must not remain open.


def test_prices_are_visible_and_external_order_alerts_disabled():
    text = source()
    assert "line.new(" in text and "label.new(" in text
    for token in ("Entry", "TP", "SL", "format.mintick", "max_lines_count = 500", "label.delete("):
        assert token in text
    orders = re.findall(r"strategy\.(?:entry|exit|close)\((.*?)\)", text, re.S)
    assert orders
    assert all("disable_alert = true" in order for order in orders)
