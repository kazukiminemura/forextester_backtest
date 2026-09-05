from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_compact_pine_ml import _max_loss_streak  # noqa: E402
from research_strict_rr_portfolio import RTrade  # noqa: E402


def _trade(day: int, result: float, symbol: str = "EURUSD") -> RTrade:
    return RTrade(symbol, datetime(2026, 1, day), result)


def test_max_loss_streak_sorts_portfolio_trades_and_limits_period() -> None:
    trades = [
        _trade(4, 1.0),
        _trade(2, -1.0),
        _trade(1, -1.0),
        _trade(3, -1.0),
        RTrade("EURUSD", datetime(2025, 12, 31), -1.0),
    ]
    assert _max_loss_streak(trades, 2026, 2026) == 3
