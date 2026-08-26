from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_pattern_market_environments import _causal_ema, _eligible  # noqa: E402


def _period(trades: int, expectancy: float) -> dict:
    return {"trades": trades, "expectancy_r": expectancy}


def test_environment_requires_positive_train_and_validation_with_sample_floor():
    periods = {
        "train_2010_2018": _period(500, 0.01),
        "validation_2019_2022": _period(200, 0.02),
        "holdout_2023_2024": _period(100, -0.01),
        "true_oos_2025_2026": _period(100, 0.03),
    }
    assert _eligible(periods, False)
    assert not _eligible(periods, True)


def test_environment_rejects_small_or_negative_development_sample():
    periods = {
        "train_2010_2018": _period(499, 0.10),
        "validation_2019_2022": _period(200, 0.10),
        "holdout_2023_2024": _period(100, 0.10),
        "true_oos_2025_2026": _period(100, 0.10),
    }
    assert not _eligible(periods, False)


def test_causal_ema_starts_after_atr_warmup_nan_values():
    values = np.asarray([np.nan, np.nan, 2.0, 4.0])
    result = _causal_ema(values, 3)
    assert np.isnan(result[1])
    assert result[2] == 2.0
    assert result[3] == 3.0
