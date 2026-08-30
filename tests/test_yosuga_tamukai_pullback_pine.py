from pathlib import Path


SOURCE_PATH = (
    Path(__file__).parents[1]
    / "scripts"
    / "tradingview"
    / "yosuga_tamukai_pullback_research.pine"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def test_uses_confirmed_four_hour_direction_without_lookahead() -> None:
    assert "ta.sma(close, htfMaLength)[1]" in SOURCE
    assert "ta.sma(close, htfMaLength)[2]" in SOURCE
    assert SOURCE.count("lookahead=barmerge.lookahead_off") == 2


def test_requires_ma20_contact_rejection_and_reacceleration() -> None:
    assert "low[1] > entryMa[1]" in SOURCE
    assert "high[1] < entryMa[1]" in SOURCE
    assert "longCloseLocation >= closeLocationThreshold" in SOURCE
    assert "shortCloseLocation >= closeLocationThreshold" in SOURCE
    assert "close > high[1]" in SOURCE
    assert "close < low[1]" in SOURCE


def test_keeps_strict_rr1_structure_stop_and_breakeven() -> None:
    assert "stopPrice := proposedStop" in SOURCE
    assert "targetPrice := entryPrice + tradeDirection * riskDistance" in SOURCE
    assert "breakevenTriggerR" in SOURCE
    assert "breakevenActive ? entryPrice : stopPrice" in SOURCE
    assert "次足から建値を有効" in SOURCE


def test_displays_explicit_entry_tp_sl_and_exit_labels() -> None:
    for text in ("Entry:", "TP:", "SL:", "建値撤退", "損切", "利確 1R"):
        assert text in SOURCE
    assert "position.bottom_right" in SOURCE
