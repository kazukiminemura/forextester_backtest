from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_textbook_retest_shapes import _shape_masks  # noqa: E402


def test_shape_masks_detect_strict_bullish_pin_and_engulfing() -> None:
    data = SimpleNamespace(
        open=np.asarray([10.4, 10.0, 10.2, 9.9]),
        high=np.asarray([10.5, 10.25, 10.25, 10.35]),
        low=np.asarray([10.1, 9.2, 9.95, 9.85]),
        close=np.asarray([10.2, 10.2, 10.0, 10.3]),
        atr=np.ones(4),
    )

    masks = _shape_masks(data)

    assert masks["pin_bar"][0].tolist() == [False, True, False, False]
    assert masks["engulfing"][0].tolist() == [False, False, False, True]
    assert masks["pin_or_engulfing"][0].tolist() == [False, True, False, True]


def test_shape_masks_detect_strict_bearish_pin() -> None:
    data = SimpleNamespace(
        open=np.asarray([9.8, 10.2]),
        high=np.asarray([9.9, 11.0]),
        low=np.asarray([9.6, 9.95]),
        close=np.asarray([9.7, 10.0]),
        atr=np.ones(2),
    )

    masks = _shape_masks(data)

    assert masks["pin_bar"][1].tolist() == [False, True]
