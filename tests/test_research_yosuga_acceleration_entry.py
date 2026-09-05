from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_yosuga_acceleration_entry import _phase, _wilder_atr  # noqa: E402


def test_phase_distinguishes_acceleration_deceleration_and_pullback() -> None:
    assert _phase(1, 103.0, 101.0, 100.0, 10.0, 0.05) == 2
    assert _phase(1, 101.5, 101.0, 100.0, 10.0, 0.04) == -1
    assert _phase(1, 100.5, 101.0, 100.0, 10.0, 0.05) == -2
    assert _phase(-1, 97.0, 99.0, 100.0, 10.0, 0.05) == 2


def test_wilder_atr_starts_after_requested_period() -> None:
    high = np.asarray([2.0, 3.0, 4.0])
    low = np.asarray([1.0, 2.0, 3.0])
    close = np.asarray([1.5, 2.5, 3.5])
    result = _wilder_atr(high, low, close, length=2)
    assert np.isnan(result[0])
    assert result[1] == 1.25
    assert result[2] == 1.375
