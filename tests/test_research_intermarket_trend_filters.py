from datetime import datetime, timedelta
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from research_intermarket_trend_filters import (
    TrendSnapshot,
    _currency_confirms,
    _gold_confirms,
    _return_at,
)
def _prepared(closes):
    size = len(closes)
    return SimpleNamespace(
        times=[datetime(2024, 1, 1) + timedelta(minutes=15 * i) for i in range(size)],
        close=np.asarray(closes, dtype=float),
    )


def test_return_at_uses_only_timestamp_or_older_bar():
    data = _prepared([100, 110, 121, 200])
    assert np.isclose(_return_at(data, data.times[2], 2), np.log(1.21))


def test_currency_filter_compares_base_and_quote_strength():
    snapshot = TrendSnapshot({"EUR": 0.02, "USD": -0.01}, 0.03)
    assert _currency_confirms("EURUSD", 1, snapshot)
    assert not _currency_confirms("EURUSD", -1, snapshot)


def test_gold_filter_respects_pair_orientation_and_skips_non_usd_crosses():
    snapshot = TrendSnapshot({}, 0.03)
    assert _gold_confirms("EURUSD", 1, snapshot)
    assert _gold_confirms("USDJPY", -1, snapshot)
    assert _gold_confirms("XAUUSD", 1, snapshot)
    assert _gold_confirms("EURJPY", -1, snapshot)
