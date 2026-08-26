from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_classic_chart_patterns import Pivot  # noqa: E402
from research_flag_patterns import (  # noqa: E402
    _previous_extreme,
    _previous_regression,
)
from research_geometric_chart_patterns import _line  # noqa: E402


def test_boundary_line_uses_three_confirmed_pivots() -> None:
    slope, intercept = _line(
        [Pivot(1, 2, 3.0), Pivot(2, 3, 5.0), Pivot(3, 4, 7.0)]
    )
    assert slope == 2.0
    assert intercept == 1.0


def test_flag_helpers_use_only_bars_before_breakout() -> None:
    values = np.asarray([1.0, 2.0, 3.0, 4.0, 100.0])
    maximum = _previous_extreme(values, 3, True)
    slope, projected = _previous_regression(values, 3)

    assert maximum[3] == 3.0
    assert maximum[4] == 4.0
    assert slope[3] == 1.0
    assert projected[3] == 4.0
