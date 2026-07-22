"""Pair-family presets selected by the quote/base currencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyPreset:
    name: str
    min_slope_atr: float
    max_range_atr: float
    min_room_r: float
    first_target_r: float
    first_target_fraction: float
    direction: str
    validation: str


PINE_PRESET = StrategyPreset("pine", 0.03, 1.5, 1.5, 1.0, 0.5, "both", "baseline")
JPY_CROSS_PRESET = StrategyPreset(
    "jpy-cross", 0.03, 1.0, 1.5, 1.0, 1.0, "long", "strict RR1"
)
JPY_FREQUENCY_RESEARCH_PRESET = StrategyPreset(
    "jpy-frequency", 0.03, 1.0, 1.0, 1.0, 1.0, "long", "frequency research"
)
EURUSD_RESEARCH_PRESET = StrategyPreset(
    "eurusd-research",
    0.03,
    0.75,
    1.5,
    0.5,
    1.0,
    "long",
    "recent OOS failed",
)

_FX_CURRENCIES = frozenset({"AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NZD", "USD"})


def automatic_preset_name(symbol: str) -> str:
    """Return the family preset, giving JPY precedence for USDJPY."""
    normalized = symbol.upper()
    if len(normalized) != 6:
        return "pine"
    base, quote = normalized[:3], normalized[3:]
    if base not in _FX_CURRENCIES or quote not in _FX_CURRENCIES:
        return "pine"
    if quote == "JPY":
        return "jpy-cross"
    if normalized == "EURUSD":
        return "eurusd-research"
    return "pine"


def resolve_preset(symbol: str, requested: str) -> StrategyPreset:
    name = automatic_preset_name(symbol) if requested == "auto" else requested
    if name == "usdjpy-70":
        name = "jpy-cross"
    if name == "usd-cross":
        name = "eurusd-research"
    presets = {
        "pine": PINE_PRESET,
        "jpy-cross": JPY_CROSS_PRESET,
        "jpy-frequency": JPY_FREQUENCY_RESEARCH_PRESET,
        "eurusd-research": EURUSD_RESEARCH_PRESET,
    }
    try:
        return presets[name]
    except KeyError as exc:
        raise ValueError(f"未知のプリセットです: {requested}") from exc
