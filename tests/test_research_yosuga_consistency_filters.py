from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_yosuga_consistency_filters import _streak  # noqa: E402


def test_streak_returns_longest_consecutive_true_run() -> None:
    assert _streak([False, True, True, False, True, True, True]) == 3
    assert _streak([]) == 0
