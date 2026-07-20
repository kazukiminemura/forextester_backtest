"""Forex Tester 6 history reader and backtesting toolkit."""

from .data import HistoryRepository
from .engine import BacktestEngine, BacktestResult
from .strategies import SmaCrossoverStrategy, Strategy

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "HistoryRepository",
    "SmaCrossoverStrategy",
    "Strategy",
]
