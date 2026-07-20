"""Forex Tester 6 history reader and backtesting toolkit."""

from .data import HistoryRepository
from .engine import BacktestEngine, BacktestResult
from .presets import StrategyPreset, automatic_preset_name, resolve_preset
from .strategies import SmaCrossoverStrategy, Strategy
from .tamukai import TamukaiBacktester, TamukaiConfig

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "HistoryRepository",
    "SmaCrossoverStrategy",
    "Strategy",
    "StrategyPreset",
    "TamukaiBacktester",
    "TamukaiConfig",
    "automatic_preset_name",
    "resolve_preset",
]
