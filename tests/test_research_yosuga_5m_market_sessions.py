from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_strict_rr_portfolio import RTrade  # noqa: E402
from research_yosuga_5m_market_sessions import (  # noqa: E402
    _active_markets,
    _exclusive_market,
    _market_group_stats,
    _select_markets,
)


def _trade(entry_time: datetime, result: float) -> RTrade:
    return RTrade("TEST", entry_time, result, direction=1, daily_trade_number=1)


def test_market_hours_apply_historical_dst() -> None:
    winter = datetime(2024, 1, 15, 8, 0)
    summer = datetime(2024, 7, 15, 7, 0)
    assert "london" in _active_markets(winter)
    assert "london" in _active_markets(summer)


def test_exclusive_overlap_prefers_new_york_then_london() -> None:
    london_new_york_overlap = datetime(2024, 7, 15, 13, 0)
    tokyo_london_overlap = datetime(2024, 7, 15, 7, 0)
    assert _exclusive_market(london_new_york_overlap) == "new_york"
    assert _exclusive_market(tokyo_london_overlap) == "london"


def test_overlapping_stats_can_count_one_trade_in_two_markets() -> None:
    row = _trade(datetime(2024, 7, 15, 13, 0), 1.0)
    stats = _market_group_stats([row], exclusive=False)
    assert stats["london"]["trades"] == 1
    assert stats["new_york"]["trades"] == 1


def test_market_selection_requires_train_and_validation_to_pass() -> None:
    passing = {"trades": 100, "win_rate": 52.0, "profit_rate_pct": 4.0}
    validation_pass = {"trades": 40, "win_rate": 50.0, "profit_rate_pct": 0.0}
    failing = {"trades": 100, "win_rate": 49.0, "profit_rate_pct": -2.0}
    groups = {
        "train_2010_2018": {
            "tokyo": passing,
            "london": passing,
            "new_york": failing,
        },
        "validation_2019_2022": {
            "tokyo": validation_pass,
            "london": failing,
            "new_york": validation_pass,
        },
    }
    assert _select_markets(groups) == ["tokyo"]
