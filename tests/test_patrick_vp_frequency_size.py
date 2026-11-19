"""All entries remain openable, including those with unavailable reversal data."""

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backtest_patrick_vp_frequency_size as study


def test_size_preserves_entries_with_opposite_or_missing_pattern():
    times = np.arange(500, dtype=np.int64) * 60
    prices = np.full((len(times), 4), 100.0)
    prices[[74, 149, 224], 3] = [99.0, 101.0, 101.0]
    ledger = np.zeros((3, 17))
    ledger[:, 0] = times[[0, 225, 225]]
    ledger[:, 2] = [1, 1, -1]
    ledger[:, 7] = [1, 2, -1]

    trades = study.sized_entries("EURUSD", "normal", ledger, times, prices)

    assert [r["six_observed"] for r in trades] == [False, True, True]
    assert [r["size"] for r in trades] == [.5, 1, .5]
    assert [r["scaled_r"] for r in trades] == [.5, 2, -.5]


def test_size_changes_common_budget_pf_and_preserves_own_risk_pf():
    stats = study.trade_stats([{"original_r": 1.0, "size": 1.0},
                               {"original_r": -1.0, "size": .5}])

    assert stats["trades"] == 2
    assert stats["scaled_pf"] == pytest.approx(2.0)
    assert stats["control_pf"] == stats["own_risk_pf"] == pytest.approx(1.0)
