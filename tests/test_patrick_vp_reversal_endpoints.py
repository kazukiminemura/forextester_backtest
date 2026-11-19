"""Check that the relaxed Patrick reversal uses six exact observations."""

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backtest_patrick_vp_reversal_endpoints as study


def price_window(side=1):
    fill = study.base.stamp("2024-01-07T23:15")  # Monday 08:15 JST.
    times = fill + np.arange(-225, 2) * 60
    prices = np.full((len(times), 4), 100.)
    prices[[74, 149, 224], 3] = 100. + side * np.array([-2., 3., 1.])
    return times, prices


@pytest.mark.parametrize("side", [1, -1])
def test_full_window_matches_original_and_ignores_nonendpoint_prices(side):
    times, prices = price_window(side)
    assert study.original.reversal_side(times, prices, 225) == side
    assert study.endpoint_decision(times, prices, 225) == (True, side)
    prices[[2, 100, 201, 225, 226], :] = 10_000.
    assert study.endpoint_decision(times, prices, 225) == (True, side)
    keep = np.arange(len(times)) != 100
    assert study.endpoint_decision(times[keep], prices[keep], 224) == (True, side)
    assert study.original.reversal_side(times[keep], prices[keep], 224) == 0


@pytest.mark.parametrize("offset", [-225, -151, -150, -76, -75, -1])
def test_each_endpoint_timestamp_is_required(offset):
    times, prices = price_window()
    times[offset + 225] += 1   # The displaced observation must not be substituted.
    assert study.endpoint_decision(times, prices, 225) == (False, 0)


def test_zero_move_passes_availability_control_but_fails_reversal():
    times, prices = price_window()
    prices[149, 3] = prices[75, 0]
    begin = study.base.stamp("2024-01-07")
    available, reversal = study.fill_masks(times, prices, begin, begin + study.va.DAY)

    np.testing.assert_array_equal(np.flatnonzero(available), [225])
    assert available[225] == 2
    assert np.count_nonzero(reversal) == 0
