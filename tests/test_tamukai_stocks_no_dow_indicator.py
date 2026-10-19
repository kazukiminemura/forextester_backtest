"""Pine source-contract checks only; not a TradingView compiler."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/tradingview/research/tamukai_stocks_no_dow_rr1_indicator.pine"


def source():
    return PATH.read_text(encoding="utf-8")


def test_indicator_has_no_order_ledger_or_stop_array():
    text = source()
    assert text.startswith("//@version=6")
    assert "indicator(" in text
    for token in ("strategy(", "strategy.", "array.", "varip", "request.security", "alert("):
        assert token not in text
    assert "timeframe.isdaily" in text and "chart.is_standard" in text


def test_signal_contract_is_unchanged():
    text = source()
    for token in ("ta.sma(close, 21)", "ta.highest(high[1], 3)", "ta.lowest(low[1], 3)",
                  "close > sma21", "sma21 > sma21[2]", "bar_index >= 23",
                  "low[1] <= sma21[1]", "low[2] <= sma21[2]", "low[3] <= sma21[3]",
                  "close > priorHigh", "barstate.isconfirmed"):
        assert token in text


def test_named_price_history_is_retained():
    text = source()
    for token in ("line.new(", "label.new(", "line.set_x2(", "format.mintick",
                  "Entry", "TP", "SL", "max_lines_count = 500"):
        assert token in text
    assert "line.delete(" not in text


def test_next_open_entry_then_gap_then_sl_then_tp_then_next_signal():
    text = source()
    branches = ("if barstate.isconfirmed", "if pending and not holding", "if open > pendingStop",
                "entryPrice := open", "stopPrice := pendingStop",
                "targetPrice := entryPrice + (entryPrice - stopPrice)", "pending := false",
                "if holding", "if open <= stopPrice", "else if open >= targetPrice",
                "else if low <= stopPrice", "else if high >= targetPrice",
                "holding := false", "if not holding and time >= startTime",
                "pendingStop := priorLow")
    offsets = [text.index(branch) for branch in branches]
    assert offsets == sorted(offsets)
    assert text.count("entryPrice :=") == 1
    assert text.count("stopPrice :=") == 1
    assert text.count("targetPrice :=") == 1


def test_close_only_and_no_profit_claim_are_documented():
    guide = (ROOT / "docs/tamukai_stocks_no_dow_pine.md").read_text(encoding="utf-8")
    assert "日足確定後" in guide
    assert "金額損益や手数料も集計しない" in guide
    assert "indicator版のTradingView実コンパイル・実表示は未確認" in guide
