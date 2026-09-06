from datetime import datetime, timedelta
from pathlib import Path

import pytest

from forextester_backtest.data import _aggregate_bars
from forextester_backtest.models import Bar
from forextester_backtest.sniper import SniperReplay


@pytest.mark.parametrize("minutes", [5, 15, 30, 60, 240, 1440])
def test_shared_five_minute_aggregation_matches_direct_minute_source(minutes):
    start = datetime(2024, 12, 30)
    source = []
    for i in range(3 * 1440 + 17):
        if i % 17 == 0 or 720 <= i < 900:
            continue  # Missing minutes and a long gap are not filled.
        price = 100 + i % 101
        source.append(Bar(start + timedelta(minutes=i), price, price+2, price-1, price+1, 1))
    base = list(_aggregate_bars(source, timedelta(minutes=5)))
    expected = list(_aggregate_bars(source, timedelta(minutes=minutes)))
    actual = list(_aggregate_bars(base, timedelta(minutes=minutes)))
    assert actual == expected


@pytest.mark.parametrize("minutes", [5, 15, 30, 60, 240, 1440])
def test_replay_uses_selected_duration_for_signal_close_timestamp(minutes):
    source = (Path(__file__).resolve().parents[1] / "scripts/tradingview/sniper_vip_pro_reconstruction.pine").read_text(encoding="utf-8")
    replay = SniperReplay(source, 0.001, minutes=minutes)
    start = datetime(2024, 12, 31)
    replay.update(Bar(start, 100, 101, 99, 100, 1))
    expected = int(((start + timedelta(minutes=minutes)) - datetime(1970, 1, 1)).total_seconds()*1000)
    assert replay.env["time_close"] == expected
