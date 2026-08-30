from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_yosuga_dow_filters import (  # noqa: E402
    Prepared,
    _confirmed_pivots,
    _passes_unseen_periods,
)
from research_yosuga_dow_htf_filter import (  # noqa: E402
    _completed_four_hour_features,
)
from research_yosuga_dow_rr_breakeven import (  # noqa: E402
    RiskTrade,
    _stats as risk_stats,
)


def test_confirmed_pivot_is_emitted_on_confirmation_bar() -> None:
    values = np.asarray([1.0, 2.0, 5.0, 2.0, 1.0])
    pivots = _confirmed_pivots(values, left=2, right=2, high=True)
    assert np.isnan(pivots[:4]).all()
    assert pivots[4] == 5.0


def test_adoption_requires_both_unseen_periods_to_be_positive() -> None:
    periods = {
        "holdout_2023_2024": {
            "total_return_pct": 1.0,
            "expectancy_pct": 0.01,
        },
        "true_oos_2025_2026": {
            "total_return_pct": -0.1,
            "expectancy_pct": -0.001,
        },
    }
    assert not _passes_unseen_periods(periods)


def test_four_hour_filter_uses_only_previous_completed_group() -> None:
    times = [
        datetime(2026, 1, 1, 0, 0),
        datetime(2026, 1, 1, 3, 45),
        datetime(2026, 1, 1, 4, 0),
        datetime(2026, 1, 1, 7, 45),
        datetime(2026, 1, 1, 8, 0),
    ]
    values = np.asarray([1.0, 2.0, 3.0, 4.0, 5.0])
    data = Prepared(times, values, values, values, [])
    features = _completed_four_hour_features(data, "sma", 1)
    assert np.isnan(features.close[0])
    assert features.close[2] == 2.0
    assert features.close[4] == 4.0
    assert features.average[4] == 4.0
    assert features.previous_average[4] == 2.0


def test_risk_stats_counts_breakeven_as_cost_adjusted_loss() -> None:
    start = datetime(2026, 1, 1)
    trades = [
        RiskTrade(start, start, 1, "target", 1.0),
        RiskTrade(start, start, 1, "stop", -1.0),
        RiskTrade(start, start, 1, "breakeven", -0.01),
    ]
    stats = risk_stats(trades)
    assert stats["targets"] == 1
    assert stats["stops"] == 1
    assert stats["breakevens"] == 1
    assert stats["total_return_pct"] == pytest.approx(-0.01)
