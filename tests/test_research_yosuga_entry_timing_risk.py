from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_yosuga_dow_pullback_entry import _simulate  # noqa: E402
from research_yosuga_entry_timing_risk import (  # noqa: E402
    ENTRY_DELAYS,
    STOP_BUFFERS_ATR,
    TARGET_R,
    _with_protected_rate,
)


def test_sensitivity_grid_keeps_equal_distance_rr1() -> None:
    assert ENTRY_DELAYS == (-1, 0, 1, 2)
    assert STOP_BUFFERS_ATR == (0.1, 0.15, 0.2, 0.3)
    assert TARGET_R == 1.0


def test_protected_rate_includes_targets_and_breakevens() -> None:
    periods = {
        "sample": {
            "trades": 10,
            "targets": 4,
            "stops": 3,
            "breakevens": 3,
        }
    }
    result = _with_protected_rate(periods)
    assert result["sample"]["win_rate_including_breakeven"] == 70.0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"entry_delay_bars": -2}, "entry_delay_bars"),
        ({"stop_buffer_atr": -0.1}, "stop_buffer_atr"),
        ({"target_r": 0.0}, "target_r"),
        ({"loss_cooldown_bars": -1}, "loss_cooldown_bars"),
    ],
)
def test_simulation_rejects_invalid_execution_parameters(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        _simulate(None, 0.01, None, **kwargs)
