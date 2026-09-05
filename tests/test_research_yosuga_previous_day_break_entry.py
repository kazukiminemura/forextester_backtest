from datetime import datetime
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_yosuga_dow_filters import Prepared  # noqa: E402
from research_yosuga_previous_day_break_entry import _previous_day_state  # noqa: E402


def test_previous_day_update_distinguishes_current_and_prior_bar() -> None:
    data = Prepared(
        times=[
            datetime(2025, 1, 1, 0),
            datetime(2025, 1, 1, 12),
            datetime(2025, 1, 2, 0),
            datetime(2025, 1, 2, 1),
            datetime(2025, 1, 2, 2),
        ],
        high=np.asarray([10.0, 12.0, 11.0, 13.0, 12.5]),
        low=np.asarray([8.0, 9.0, 8.5, 8.0, 7.0]),
        close=np.asarray([9.0, 11.0, 10.0, 12.0, 8.0]),
        cross_events=[],
    )
    state = _previous_day_state(data, np.zeros(5))
    assert state.high[2] == 12.0
    assert not state.high_updated_before_bar[3]
    assert state.high_updated[3]
    assert state.high_updated_before_bar[4]
    assert not state.low_updated_before_bar[4]
    assert state.low_updated[4]
