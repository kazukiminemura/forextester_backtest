from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_yosuga_15m_entry_context import (  # noqa: E402
    _decelerating_groups,
    _form_label,
    _select_forms,
    _strategy_still_bad,
)


def test_form_label_separates_actual_pa_reasons() -> None:
    assert _form_label(True, False) == "wick_rejection"
    assert _form_label(False, True) == "engulfing"
    assert _form_label(True, True) == "wick_and_engulfing"
    assert _form_label(False, False) == "none"


def test_deceleration_uses_only_completed_directional_progress() -> None:
    closes = np.asarray([100.0, 104.0, 107.0, 109.0, 108.0])
    trends = np.asarray([1, 1, 1, 1, 1], dtype=np.int8)
    result = _decelerating_groups(closes, trends)
    assert result.tolist() == [False, False, False, True, True]


def test_form_selection_requires_train_and_validation_pass() -> None:
    passing_train = {"trades": 100, "win_rate": 52.0, "profit_rate_pct": 4.0}
    passing_validation = {"trades": 40, "win_rate": 50.0, "profit_rate_pct": 0.0}
    failing = {"trades": 100, "win_rate": 49.0, "profit_rate_pct": -2.0}
    groups = {
        "train_2010_2018": {
            "wick_rejection": passing_train,
            "engulfing": passing_train,
        },
        "validation_2019_2022": {
            "wick_rejection": passing_validation,
            "engulfing": failing,
        },
    }
    assert _select_forms(groups) == ["wick_rejection"]


def test_strategy_bad_requires_both_selection_periods_to_fail() -> None:
    periods = {
        "train_2010_2018": {"win_rate": 49.0, "profit_rate_pct": -2.0},
        "validation_2019_2022": {"win_rate": 45.0, "profit_rate_pct": -10.0},
    }
    assert _strategy_still_bad(periods)
