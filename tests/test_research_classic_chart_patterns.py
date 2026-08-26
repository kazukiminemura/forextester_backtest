from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_classic_chart_patterns import (  # noqa: E402
    Candidate,
    Pivot,
    _double_signals,
)
from research_triple_chart_patterns import _signals as _triple_signals  # noqa: E402


def test_double_top_requires_close_below_intervening_neckline() -> None:
    data = SimpleNamespace(
        close=np.asarray([8.0, 8.5, 9.0, 10.0, 9.5, 8.5, 9.2, 10.1, 9.0, 8.4, 8.2]),
        atr=np.ones(11),
    )
    highs = [Pivot(1, 2, 9.0), Pivot(3, 4, 10.0), Pivot(7, 8, 10.1)]
    lows = [Pivot(5, 6, 8.5)]
    candidate = Candidate(3, 0.5, 0.75, 96)

    signals = _double_signals(data, highs, lows, candidate, top=True)

    assert [(row.index, row.direction, row.pattern, row.stop) for row in signals] == [
        (9, -1, "double_top", 10.2)
    ]


def test_double_top_is_not_complete_without_neckline_break() -> None:
    data = SimpleNamespace(close=np.asarray([9.0] * 12), atr=np.ones(12))
    highs = [Pivot(1, 2, 9.0), Pivot(3, 4, 10.0), Pivot(7, 8, 10.1)]
    lows = [Pivot(5, 6, 8.5)]

    assert _double_signals(data, highs, lows, Candidate(3, 0.5, 0.75, 96), True) == []


def test_triple_top_requires_three_similar_peaks_and_neckline_break() -> None:
    close = np.asarray([8.0, 9.0, 10.0, 9.5, 8.5, 9.2, 10.1, 9.3, 8.6, 9.4, 9.9, 9.0, 8.4, 8.2])
    data = SimpleNamespace(close=close, atr=np.ones(close.size))
    highs = [Pivot(0, 1, 9.0), Pivot(2, 3, 10.0), Pivot(6, 7, 10.1), Pivot(10, 11, 9.9)]
    lows = [Pivot(4, 5, 8.5), Pivot(8, 9, 8.6)]

    signals = _triple_signals(data, Candidate(3, 0.5, 0.75, 96), True, (highs, lows))

    assert len(signals) == 1
    assert signals[0].pattern == "triple_top"
    assert signals[0].direction == -1
