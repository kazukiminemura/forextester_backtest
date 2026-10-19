"""Filters must use signal-time fields and replay position admission."""
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from research_sniper_losses import apply_filter, admitted, detailed  # noqa: E402


def rows():
    return np.asarray([
        [1, 10, 2018, -1, 25, 60, 2, 8, 0, 0, .1, 0],
        [6, 7, 2018, 2, 25, 65, 3, 9, 0, 1, .05, 0],
        [12, 13, 2018, -1, 25, 59, 1, 10, 0, 0, .11, 0],
    ], dtype=float)


def test_filter_boundaries_and_outcome_independence():
    original = rows()
    actual = apply_filter(original, (.1, 2, 60))
    np.testing.assert_array_equal(actual[:, 0], [1, 6])
    changed = original.copy()
    changed[:, [1, 2, 3, 8, 9, 11]] = -999
    np.testing.assert_array_equal(apply_filter(changed, (.1, 2, 60))[:, 0], actual[:, 0])


def test_filter_reopens_admission_for_previously_blocked_trade():
    original = rows()
    baseline = admitted({'X': original}, (100, 0, 52))['X']
    filtered = admitted({'X': original}, (.05, 0, 52))['X']
    np.testing.assert_array_equal(baseline[:, 0], [1, 12])
    np.testing.assert_array_equal(filtered[:, 0], [6])


def test_loss_metrics_distinguish_frequency_and_magnitude():
    actual = detailed(rows())
    assert actual['n'] == 3 and actual['losses'] == 2
    assert actual['gross_loss_r'] == actual['gross_gain_r'] == 2
    assert actual['pf'] == 1 and actual['mean_r'] == 0
    empty = detailed(np.empty((0, 12)))
    assert empty['n'] == 0 and empty['loss_rate'] is None
