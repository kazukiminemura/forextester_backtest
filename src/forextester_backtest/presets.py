"""Pair-family presets selected by the quote/base currencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyPreset:
    name: str
    max_range_atr: float
    first_target_r: float
    first_target_fraction: float
    direction: str


PINE_PRESET = StrategyPreset("pine", 1.5, 1.0, 0.5, "both")
JPY_CROSS_PRESET = StrategyPreset("jpy-cross", 1.0, 0.5, 1.0, "long")
USD_CROSS_PRESET = StrategyPreset("usd-cross", 0.75, 0.5, 1.0, "long")

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
    if base == "USD" or quote == "USD":
        return "usd-cross"
    return "pine"


def resolve_preset(symbol: str, requested: str) -> StrategyPreset:
    name = automatic_preset_name(symbol) if requested == "auto" else requested
    if name == "usdjpy-70":
        name = "jpy-cross"
    presets = {
        "pine": PINE_PRESET,
        "jpy-cross": JPY_CROSS_PRESET,
        "usd-cross": USD_CROSS_PRESET,
    }
    try:
        return presets[name]
    except KeyError as exc:
        raise ValueError(f"未知のプリセットです: {requested}") from exc
