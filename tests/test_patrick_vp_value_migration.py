"""Check the completed-UTC-week boundary of the Patrick VP direction filter."""

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backtest_patrick_vp_value_migration as study


def test_mask_uses_weeks_completed_at_decision_time():
    first_week = study.base.stamp("2024-01-01")
    monday = first_week + 3 * study.va.WEEK
    times = np.array([first_week, monday - 45 * 60, monday + 14 * 60, monday + 15 * 60])
    profiles = np.array([[12., 8.], [15., 5.], [13., 11.], [20., 2.], [1_000., 900.]])

    mask = study.migration_side_mask(times, profiles, first_week)

    # Monday 08:15 JST is Sunday 23:15 UTC. The UTC week is still incomplete.
    np.testing.assert_array_equal(mask, [0, 0, 0, 1])


def test_mask_allows_negative_migration_even_if_a_current_week_is_higher():
    first_week = study.base.stamp("2024-01-01")
    times = np.array([first_week + 3 * study.va.WEEK + study.FILL_DELAY])
    profiles = np.array([[12., 8.], [15., 9.], [13., 9.], [100., 90.]])

    np.testing.assert_array_equal(study.migration_side_mask(times, profiles, first_week), [-1])


@pytest.mark.parametrize("invalid", [(np.nan, 5.), (np.inf, 5.), (5., 5.), (4., 5.)])
@pytest.mark.parametrize("week", [0, 1])
def test_mask_requires_both_previous_weeks_to_have_valid_va(invalid, week):
    first_week = study.base.stamp("2024-01-01")
    times = np.array([first_week + 2 * study.va.WEEK + study.FILL_DELAY])
    profiles = np.array([[12., 8.], [14., 9.], [15., 10.]])
    profiles[week] = invalid

    np.testing.assert_array_equal(study.migration_side_mask(times, profiles, first_week), [0])
