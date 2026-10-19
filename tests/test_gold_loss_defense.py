from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

from forextester_backtest.models import Bar
from forextester_backtest.gold_loss_defense import defensive_exit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research_sniper_daytrade import outcome


def quotes(side=1):
    origin = datetime(2020, 1, 1, 8)
    values = [(100, 100.2, 99.4, 99.5), (99.8, 100, 98, 98.5), (99, 100, 98, 99)]
    return [Bar(origin + timedelta(hours=i), 100 + side*(op-100),
                hi if side == 1 else 200-lo, lo if side == 1 else 200-hi,
                100 + side*(cl-100), 1) for i, (op, hi, lo, cl) in enumerate(values)]


@pytest.mark.parametrize("side", [-1, 1])
def test_failure_exits_next_open_before_that_bars_stop(side):
    bars = quotes(side)
    base = outcome(bars, 0, side, 1, 0, 60, 3, None)
    assert base[2] == "stop"
    result = defensive_exit(bars, 0, side, 1, 0, 100, base, "failed_1")
    assert result[0] == 1
    assert result[1] == pytest.approx(-.2/1.5)
    assert result[2] == "defense"


def test_trigger_bar_stop_cannot_be_avoided():
    bars = quotes()
    bars[0] = Bar(bars[0].time, 100, 100.2, 98, 99.5, 1)
    base = outcome(bars, 0, 1, 1, 0, 60, 3, None)
    assert defensive_exit(bars, 0, 1, 1, 0, 100, base, "failed_1") == base


def test_gap_through_stop_pays_gap_price_and_slippage():
    bars = quotes()
    bars[1] = Bar(bars[1].time, 97, 98, 96, 97, 1)
    base = outcome(bars, 0, 1, 1, .1, 60, 3, None)
    result = defensive_exit(bars, 0, 1, 1, .1, 100, base, "failed_1")
    assert result[2] == "stop"
    assert result[1] == pytest.approx((96.99-100.11)/1.5)


def test_stall_does_not_use_future_close_and_deadline_takes_priority():
    bars = quotes()
    base = outcome(bars, 0, 1, 1, 0, 60, 3, None)
    assert defensive_exit(bars, 0, 1, 1, 0, 100, base, "stalled_3") == base
    bars[1] = Bar(bars[0].time.replace(hour=20), 99.8, 104, 95, 99, 1)
    base = outcome(bars[:2], 0, 1, 1, 0, 60, 3, None)
    assert defensive_exit(bars[:2], 0, 1, 1, 0, 100, base, "failed_1") == base
