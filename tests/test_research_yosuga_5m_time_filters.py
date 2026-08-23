from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_strict_rr_portfolio import RTrade  # noqa: E402
from research_yosuga_5m_time_filters import (  # noqa: E402
    _bin_stats,
    _select_daily_cap,
    _select_keys,
)


def _trade(hour: int, result: float, order: int = 1) -> RTrade:
    return RTrade(
        "TEST",
        datetime(2020, 1, 6, hour),
        result,
        direction=1,
        daily_trade_number=order,
    )


def test_bin_stats_reports_win_rate_profit_factor_and_profit_rate() -> None:
    stats = _bin_stats([_trade(9, 1.0), _trade(9, 1.0), _trade(9, -1.0)])
    assert stats["trades"] == 3
    assert stats["win_rate"] == pytest.approx(200 / 3)
    assert stats["profit_factor"] == 2.0
    assert stats["net_r"] == 1.0
    assert stats["profit_rate_pct"] == pytest.approx(100 / 3)


def test_selection_requires_fifty_percent_in_train_and_validation() -> None:
    period_groups = {
        "train_2010_2018": {
            "9": {"trades": 50, "win_rate": 52.0, "profit_rate_pct": 4.0},
            "10": {"trades": 50, "win_rate": 60.0, "profit_rate_pct": 20.0},
        },
        "validation_2019_2022": {
            "9": {"trades": 20, "win_rate": 50.0, "profit_rate_pct": 0.0},
            "10": {"trades": 20, "win_rate": 45.0, "profit_rate_pct": -10.0},
        },
    }
    assert _select_keys(period_groups, "hour") == [9]


def test_daily_cap_requires_a_contiguous_prefix_from_first_trade() -> None:
    period_groups = {
        "train_2010_2018": {
            "1": {"trades": 30, "win_rate": 55.0, "profit_rate_pct": 10.0},
            "2": {"trades": 30, "win_rate": 49.0, "profit_rate_pct": -2.0},
            "3": {"trades": 30, "win_rate": 60.0, "profit_rate_pct": 20.0},
        },
        "validation_2019_2022": {
            "1": {"trades": 15, "win_rate": 53.0, "profit_rate_pct": 6.0},
            "2": {"trades": 15, "win_rate": 55.0, "profit_rate_pct": 10.0},
            "3": {"trades": 15, "win_rate": 60.0, "profit_rate_pct": 20.0},
        },
    }
    assert _select_daily_cap(period_groups) == 1
