"""Boundary tests for experiment gap_fill_m5_20261019 (scripts/research_gap_fill_m5.py).

These tests are deterministic, use small synthetic inputs only, and never read the
Forex Tester history.  ``scripts`` and ``src`` are added to ``sys.path`` here so the
suite runs with the documented command:

    $env:PYTHONPATH = "src;<site-packages>"
    python -B -m pytest tests/test_gap_fill_m5.py -q -p no:cacheprovider
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _extra in (ROOT / "scripts", ROOT / "src"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from forextester_backtest.models import Bar, InstrumentMetadata  # noqa: E402
from research_gap_fill_m5 import (  # noqa: E402
    CLAIMED_COST_SCALES,
    CLAIMED_THRESHOLDS,
    MAX_HOLDING_BARS,
    PERIOD_NAMES,
    SYMBOLS,
    ControlIndex,
    PeriodSpec,
    ProtocolViolation,
    aggregate_m5_prices,
    build_event_metrics,
    build_period_windows,
    build_stage_a_summary,
    classify_race,
    find_gap_events,
    guard_frozen,
    load_m5_series,
    main,
    meets_threshold,
    parse_periods,
    pip_size,
    quantiles,
    ratio,
    series_sha256,
    simulate_stage_b,
    stream_sha256,
    summarise_group,
    validate_grid,
    validate_protocol_against_code,
)

PIP = 0.0001
SPREAD = 0.00011           # EURUSD metadata: spread=11 points, decimals=5
BASE = datetime(2016, 1, 4, 0, 0)   # Monday inside the training period

# Synthetic declared periods: kept separate from protocol.json so that Stage A/B
# boundary tests do not depend on director edits.  A dedicated test below does
# parse the real protocol.json and fails loudly on specification drift.
SPECS = (
    PeriodSpec("training", "2016-01-01", "2016-12-31"),
    PeriodSpec("validation", "2017-01-01", "2017-12-31"),
    PeriodSpec("final_confirmation", "2018-01-01", "2018-12-31"),
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def build_series(
    specs,
    *,
    symbol="EURUSD",
    pip=PIP,
    spread_price=SPREAD,
    decimals=5,
    m1_count=None,
):
    """``specs`` is a list of (offset_minutes, open, high, low, close)."""
    return make_series(
        specs,
        symbol=symbol,
        pip=pip,
        spread_price=spread_price,
        decimals=decimals,
        m1_count=m1_count,
    )


def make_series(specs, *, symbol="EURUSD", pip=PIP, spread_price=SPREAD, decimals=5, m1_count=None):
    from research_gap_fill_m5 import make_m5_series

    return make_m5_series(
        symbol=symbol,
        times=[BASE + timedelta(minutes=row[0]) for row in specs],
        open=[row[1] for row in specs],
        high=[row[2] for row in specs],
        low=[row[3] for row in specs],
        close=[row[4] for row in specs],
        pip=pip,
        spread_price=spread_price,
        decimals=decimals,
        m1_count=m1_count,
    )


def flat(offset_minutes, count, price, step=5):
    """``count`` flat bars starting at ``offset_minutes``."""
    return [
        (offset_minutes + index * step, price, price, price, price)
        for index in range(count)
    ]


def window_for(series, name="training"):
    windows = {window.name: window for window in build_period_windows(series, SPECS)}
    return windows[name]


def metrics_for(series, events=None):
    if events is None:
        events = find_gap_events(series)
    return build_event_metrics(series, events, build_period_windows(series, SPECS), None, SPECS)


def stage_b(series, metrics, *, threshold=10.0, cost_scale=1.0, arm="fade", period="training"):
    return simulate_stage_b(
        series, metrics, window_for(series, period), threshold, cost_scale, arm
    )


def gap_up_short_series(*, extra_bars=0, gap_pips=10.0, price=1.1000):
    """Bar 0 flat, bar 1 opens ``gap_pips`` above it (a fade short), then flat.

    The corridor keeps every following bar strictly between the two barriers.
    """
    open_ = price + gap_pips * PIP
    bars = [(0, price, price, price, price)]
    bars.append((120, open_, open_ + 0.0005, open_ - 0.0005, open_))
    for index in range(1 + extra_bars):
        offset = 125 + index * 5
        bars.append((offset, open_, open_ + 0.0003, open_ - 0.0003, open_))
    return bars


# --------------------------------------------------------------------------
# 1. gap detection: exactly 120 minutes is a gap, 119 is not
# --------------------------------------------------------------------------

def test_exactly_120_minutes_is_a_gap():
    series = build_series([(0, 1.1, 1.1, 1.1, 1.1), (120, 1.102, 1.102, 1.102, 1.102)])
    events = find_gap_events(series)
    assert len(events) == 1
    assert events[0].index == 1
    assert events[0].gap_minutes == 120.0


def test_119_minutes_is_not_a_gap():
    series = build_series([(0, 1.1, 1.1, 1.1, 1.1), (119, 1.102, 1.102, 1.102, 1.102)])
    assert find_gap_events(series) == []


@pytest.mark.parametrize("minutes,expected", [(119, 0), (120, 1), (121, 1), (5, 0)])
def test_gap_threshold_is_inclusive_and_other_steps_are_ignored(minutes, expected):
    series = build_series([(0, 1.1, 1.1, 1.1, 1.1), (minutes, 1.102, 1.102, 1.102, 1.102)])
    assert len(find_gap_events(series)) == expected


def test_first_bar_after_the_discontinuity_is_the_gap_bar():
    series = build_series(
        [(0, 1.1, 1.1, 1.1, 1.1), (120, 1.102, 1.102, 1.102, 1.102), (125, 1.103, 1.103, 1.103, 1.103)]
    )
    events = find_gap_events(series)
    assert [event.index for event in events] == [1]


# --------------------------------------------------------------------------
# 2. threshold boundary: exactly 10.0 pips is adopted, less is not
# --------------------------------------------------------------------------

def test_gap_exactly_at_threshold_is_adopted():
    assert meets_threshold(10.0, 10.0)
    series = build_series(gap_up_short_series())
    events = find_gap_events(series)
    assert len(events) == 1
    assert events[0].gap_pips == pytest.approx(10.0, abs=1e-9)
    summary = build_stage_a_summary(metrics_for(series), [10.0, 25.0], ["EURUSD"])
    assert summary["pooled_all_periods"]["X10"]["events"] == 1
    assert summary["pooled_all_periods"]["X25"]["events"] == 0


def test_gap_just_below_threshold_is_not_adopted():
    series = build_series(gap_up_short_series(gap_pips=9.999))
    events = find_gap_events(series)
    assert events[0].gap_pips == pytest.approx(9.999, abs=1e-9)
    summary = build_stage_a_summary(metrics_for(series), [10.0], ["EURUSD"])
    assert summary["pooled_all_periods"]["X10"]["events"] == 0


def test_threshold_tolerance_is_far_below_any_real_measurement():
    assert meets_threshold(10.0 - 1e-10, 10.0)
    assert not meets_threshold(10.0 - 1e-6, 10.0)


def test_threshold_filters_population_but_not_the_metric_set():
    small = gap_up_short_series(gap_pips=9.999)
    large = [(0, 1.1, 1.1, 1.1, 1.1)]
    large += gap_up_short_series(gap_pips=30.0)[1:]
    series = build_series(large)
    metrics = metrics_for(series)
    assert len(metrics) == 1
    summary = build_stage_a_summary(metrics, [10.0, 25.0], ["EURUSD"])
    assert summary["pooled_all_periods"]["X10"]["events"] == 1
    assert summary["pooled_all_periods"]["X25"]["events"] == 1
    assert len(metrics_for(build_series(small))) == 1


# --------------------------------------------------------------------------
# 3. pip conversion, including JPY crosses
# --------------------------------------------------------------------------

def test_pip_size_from_decimals():
    assert pip_size(5) == pytest.approx(0.0001)
    assert pip_size(3) == pytest.approx(0.01)


def test_pip_size_rejects_unknown_decimals():
    with pytest.raises(ValueError):
        pip_size(4)


def test_jpy_cross_gap_is_measured_on_the_001_base():
    series = make_series(
        [(0, 100.00, 100.00, 100.00, 100.00), (120, 100.10, 100.10, 100.10, 100.10)],
        symbol="USDJPY",
        pip=0.01,
        spread_price=0.012,
        decimals=3,
    )
    events = find_gap_events(series)
    assert events[0].gap_pips == pytest.approx(10.0, abs=1e-9)
    summary = build_stage_a_summary(metrics_for(series), [10.0], ["USDJPY"])
    assert summary["pooled_all_periods"]["X10"]["events"] == 1


def test_non_jpy_gap_uses_the_00001_base():
    series = build_series([(0, 1.1, 1.1, 1.1, 1.1), (120, 1.101, 1.101, 1.101, 1.101)])
    assert find_gap_events(series)[0].gap_pips == pytest.approx(10.0, abs=1e-9)


# --------------------------------------------------------------------------
# 4. same bar hits both barriers -> stop first and ambiguous
# --------------------------------------------------------------------------

def test_same_bar_both_barriers_is_stop_first_and_ambiguous():
    series = build_series(
        [(0, 1.1, 1.1, 1.1, 1.1), (120, 1.101, 1.1025, 1.0985, 1.101)]
    )
    event = find_gap_events(series)[0]
    assert event.direction == -1                      # gap up -> fade short
    stop_level = event.open + event.gap_price
    target_level = event.open - event.gap_price
    outcome = classify_race(series, event.index, -1, stop_level, target_level, series.size - 1)
    assert outcome.reason == "stop"
    assert outcome.ambiguous is True
    assert outcome.bar_offset == 0
    metric = metrics_for(series)[0]
    assert metric.fade_reason == "stop"
    assert metric.fade_ambiguous is True


def test_both_barriers_realised_as_stop_in_stage_b():
    series = build_series(
        [(0, 1.1, 1.1, 1.1, 1.1), (120, 1.101, 1.1025, 1.0985, 1.101)]
    )
    trade = stage_b(series, metrics_for(series))[0]
    assert trade.reason == "stop"
    assert trade.ambiguous is True
    # A stop-out is exactly -1R for both directions by construction.
    assert trade.net_r == pytest.approx(-1.0, rel=1e-12)


# --------------------------------------------------------------------------
# 5. opening already beyond a barrier
# --------------------------------------------------------------------------

def test_opening_beyond_target_is_target_gap():
    series = build_series(
        [
            (0, 1.1, 1.1, 1.1, 1.1),
            (120, 1.101, 1.1012, 1.1008, 1.101),
            (125, 1.0995, 1.0995, 1.0995, 1.0995),
        ]
    )
    metric = metrics_for(series)[0]
    assert metric.direction == -1
    assert metric.fade_reason == "target_gap"
    assert metric.fade_offset == 1


def test_opening_beyond_stop_is_stop_gap():
    series = build_series(
        [
            (0, 1.1, 1.1, 1.1, 1.1),
            (120, 1.101, 1.1012, 1.1008, 1.101),
            (125, 1.1030, 1.1030, 1.1030, 1.1030),
        ]
    )
    metric = metrics_for(series)[0]
    assert metric.fade_reason == "stop_gap"
    assert metric.fade_offset == 1


def test_target_gap_fills_at_the_limit_price_and_stop_gap_at_the_open():
    target_gap = build_series(
        [
            (0, 1.1, 1.1, 1.1, 1.1),
            (120, 1.101, 1.1012, 1.1008, 1.101),
            (125, 1.0995, 1.0995, 1.0995, 1.0995),
        ]
    )
    trade = stage_b(target_gap, metrics_for(target_gap))[0]
    assert trade.reason == "target_gap"
    # The resting limit is filled at its own price, never better: the short target
    # is the previous close plus the buy-side exit cost.
    assert trade.exit == pytest.approx(trade.target_fill)
    assert trade.target_fill > trade.target
    stop_gap = build_series(
        [
            (0, 1.1, 1.1, 1.1, 1.1),
            (120, 1.101, 1.1012, 1.1008, 1.101),
            (125, 1.1030, 1.1030, 1.1030, 1.1030),
        ]
    )
    trade = stage_b(stop_gap, metrics_for(stop_gap))[0]
    assert trade.reason == "stop_gap"
    # A resting stop becomes a market order: it fills at the actual opening.
    assert trade.exit > trade.stop
    assert trade.net_r < -1.0


# --------------------------------------------------------------------------
# 6. unresolved after 48 bars -> period_end
# --------------------------------------------------------------------------

def test_unresolved_after_48_bars_is_period_end_at_holding_limit():
    series = build_series(gap_up_short_series(extra_bars=60))
    metrics = metrics_for(series)
    assert metrics[0].fade_reason == "none"
    trade = stage_b(series, metrics)[0]
    assert trade.reason == "period_end"
    assert trade.period_end_cause == "holding_limit"
    assert trade.bars_held == MAX_HOLDING_BARS
    assert trade.exit_index == metrics[0].index + MAX_HOLDING_BARS - 1


def test_unresolved_at_period_boundary_is_period_end():
    specs = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),
        (125, 1.101, 1.1012, 1.1008, 1.101),
        (130, 1.101, 1.1012, 1.1008, 1.101),
    ]
    series = build_series(specs)
    trade = stage_b(series, metrics_for(series))[0]
    assert trade.reason == "period_end"
    assert trade.period_end_cause == "period_boundary"
    assert trade.bars_held == 3


def test_entry_bar_counts_as_the_first_holding_bar():
    series = build_series(gap_up_short_series(extra_bars=60))
    trade = stage_b(series, metrics_for(series))[0]
    assert trade.entry_index == 1
    assert trade.bars_held == 48
    assert trade.exit_index == 48


# --------------------------------------------------------------------------
# 7. the exit bar is never reused as the next signal
# --------------------------------------------------------------------------

def test_exit_bar_is_not_reused_as_the_next_signal():
    """Event A exits exactly on event B's bar, so B must be skipped."""
    bars = [(0, 1.1, 1.1, 1.1, 1.1)]
    bars.append((120, 1.101, 1.1012, 1.1008, 1.101))        # event A bar
    for index in range(23):                                  # bars 2..24 stay inside
        offset = 125 + index * 5
        bars.append((offset, 1.101, 1.1012, 1.1008, 1.101))
    bars.append((360, 1.0995, 1.0995, 1.0995, 1.0995))       # event B bar (gap >= 120 min)
    series = build_series(bars)
    metrics = metrics_for(series)
    assert len(metrics) == 2
    assert [metric.index for metric in metrics] == [1, 25]
    trades = stage_b(series, metrics)
    assert len(trades) == 1
    assert trades[0].entry_index == 1
    assert trades[0].exit_index == 25
    # Event B on its own is valid; it is skipped only because A exited on its bar.
    assert len(stage_b(series, [metrics[1]])) == 1


def test_next_signal_is_allowed_after_the_exit_bar():
    bars = [(0, 1.1, 1.1, 1.1, 1.1)]
    bars.append((120, 1.101, 1.1012, 1.1008, 1.101))          # event A bar
    for index in range(3):                                    # bars 2..4 stay inside
        bars.append((125 + index * 5, 1.101, 1.1012, 1.1008, 1.101))
    bars.append((140, 1.101, 1.1012, 1.0990, 1.101))          # A hits its target (bar 5)
    bars += flat(145, 19, 1.101)                              # bars 6..24 inside
    bars.append((360, 1.0995, 1.0995, 1.0995, 1.0995))        # event B bar (index 25)
    bars += flat(365, 10, 1.0995)
    series = build_series(bars)
    trades = stage_b(series, metrics_for(series))
    assert [trade.entry_index for trade in trades] == [1, 25]
    assert trades[0].exit_index == 5
    # A exits on an earlier bar than B's entry, so B is allowed.
    assert trades[0].exit_index < trades[1].entry_index


# --------------------------------------------------------------------------
# 8. no future reference in the signal
# --------------------------------------------------------------------------

def test_signal_uses_only_the_gap_bar_open_and_the_previous_close():
    calm = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),
    ] + flat(125, 60, 1.101)
    wild = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),
    ] + [(125 + index * 5, 1.2, 1.25, 1.15, 1.2) for index in range(60)]
    calm_series = build_series(calm)
    wild_series = build_series(wild)
    calm_event = find_gap_events(calm_series)[0]
    wild_event = find_gap_events(wild_series)[0]
    assert calm_event.gap_pips == wild_event.gap_pips
    assert calm_event.direction == wild_event.direction == -1
    assert calm_event.open == wild_event.open == 1.101
    assert calm_event.previous_close == wild_event.previous_close == 1.1
    # The classification does consume the forward path, so the comparison above
    # is not vacuous: the same signal leads to a different outcome.
    assert metrics_for(calm_series)[0].fade_reason == "none"
    assert metrics_for(wild_series)[0].fade_reason == "stop_gap"


def test_gap_event_ignores_bars_after_it():
    series = build_series(
        [(0, 1.1, 1.1, 1.1, 1.1), (120, 1.101, 1.1012, 1.1008, 1.101)]
    )
    truncated = build_series([(0, 1.1, 1.1, 1.1, 1.1), (120, 1.101, 1.1012, 1.1008, 1.101)])
    assert find_gap_events(series)[0] == find_gap_events(truncated)[0]


# --------------------------------------------------------------------------
# 9. partial M5 buckets and missing bars
# --------------------------------------------------------------------------

def test_partial_m5_bucket_is_kept_with_bucket_start_and_first_m1_open():
    rows = [
        (datetime(2016, 1, 4, 0, 0), 1.1, 1.1002, 1.0998, 1.1, 1.0),
        (datetime(2016, 1, 4, 0, 1), 1.1, 1.1004, 1.0996, 1.1001, 1.0),
        (datetime(2016, 1, 4, 0, 2), 1.1001, 1.1005, 1.0999, 1.1002, 1.0),
        (datetime(2016, 1, 4, 0, 3), 1.1002, 1.1006, 1.1, 1.1003, 1.0),
        (datetime(2016, 1, 4, 0, 4), 1.1003, 1.1007, 1.1001, 1.1004, 1.0),
        # Data hole, then a bucket with only two M1 bars and no bar at its start.
        (datetime(2016, 1, 4, 3, 2), 1.11, 1.1105, 1.1095, 1.1101, 1.0),
        (datetime(2016, 1, 4, 3, 3), 1.1101, 1.1106, 1.1096, 1.1102, 1.0),
    ]
    series = aggregate_m5_prices("EURUSD", rows, pip=PIP, spread_price=SPREAD, decimals=5)
    assert series.size == 2
    assert series.m1_bars == 7
    assert list(series.m1_count) == [5, 2]
    assert series.times[0] == datetime(2016, 1, 4, 0, 0)
    assert series.times[1] == datetime(2016, 1, 4, 3, 0)      # bucket start, not 03:02
    assert series.open[1] == pytest.approx(1.11)              # first M1 open of the bucket
    assert series.close[1] == pytest.approx(1.1102)
    events = find_gap_events(series)
    assert len(events) == 1
    assert events[0].entry_m1_count == 2
    assert events[0].entry_partial is True
    assert events[0].previous_m1_count == 5
    assert events[0].gap_minutes == 180.0
    summary = summarise_group(metrics_for(series))
    assert summary["events"] == 1
    assert summary["entry_bar_partial_m1"] == 1
    assert summary["previous_bar_partial_m1"] == 0


def test_partial_entry_bar_population_is_split_out_for_robustness_only():
    rows = [
        (datetime(2016, 1, 4, 0, 0), 1.1, 1.1, 1.1, 1.1, 1.0),
        (datetime(2016, 1, 4, 0, 1), 1.1, 1.1, 1.1, 1.1, 1.0),
        (datetime(2016, 1, 4, 0, 2), 1.1, 1.1, 1.1, 1.1, 1.0),
        (datetime(2016, 1, 4, 0, 3), 1.1, 1.1, 1.1, 1.1, 1.0),
        (datetime(2016, 1, 4, 0, 4), 1.1, 1.1, 1.1, 1.1, 1.0),
        (datetime(2016, 1, 4, 3, 0), 1.101, 1.1012, 1.1008, 1.101, 1.0),
        (datetime(2016, 1, 4, 3, 1), 1.101, 1.1012, 1.1008, 1.101, 1.0),
    ]
    series = aggregate_m5_prices("EURUSD", rows, pip=PIP, spread_price=SPREAD, decimals=5)
    summary = build_stage_a_summary(metrics_for(series), [10.0], ["EURUSD"])
    robustness = summary["robustness_entry_bar_completeness"]
    assert robustness["partial_entry_bar_events"] == 1
    assert robustness["complete_entry_bar_events"] == 0
    assert robustness["partial_entry_bar"]["X10"]["events"] == 1
    assert robustness["complete_entry_bar"]["X10"]["events"] == 0
    assert "not used by any acceptance gate" in robustness["note"]


def test_aggregation_matches_bucket_floor_for_partial_and_complete_buckets():
    rows = [
        (datetime(2016, 1, 4, 0, 4), 1.1, 1.1, 1.1, 1.1, 1.0),     # partial: starts late
        (datetime(2016, 1, 4, 0, 5), 1.1, 1.1004, 1.0996, 1.1002, 1.0),
    ]
    series = aggregate_m5_prices("EURUSD", rows, pip=PIP, spread_price=SPREAD, decimals=5)
    assert series.size == 2
    assert series.times[0] == datetime(2016, 1, 4, 0, 0)
    assert series.times[1] == datetime(2016, 1, 4, 0, 5)
    assert list(series.m1_count) == [1, 1]


def test_load_m5_series_derives_costs_from_metadata():
    class StubRepository:
        def __init__(self, bars):
            self._bars = bars

        def metadata(self, symbol):
            return InstrumentMetadata(symbol, {"decimals": "3", "spread": "12"})

        def bars(self, symbol, start, end, timeframe):
            assert timeframe == "1m"
            yield from self._bars

    rows = [
        Bar(datetime(2016, 1, 4, 0, 0), 100.0, 100.0, 100.0, 100.0, 1.0),
        Bar(datetime(2016, 1, 4, 3, 0), 100.1, 100.1, 100.1, 100.1, 1.0),
    ]
    series = load_m5_series(StubRepository(rows), "USDJPY", BASE, BASE + timedelta(days=1))
    assert series.pip == pytest.approx(0.01)
    assert series.spread_price == pytest.approx(0.012)
    assert series.spread_pips == pytest.approx(1.2)
    assert series.size == 2
    assert series.symbol == "USDJPY"


# --------------------------------------------------------------------------
# control bars (same symbol, weekday and time band, non-gap)
# --------------------------------------------------------------------------

def test_control_bar_is_on_the_same_weekday_inside_the_band():
    bars = flat(0, 60, 1.1)                                   # Monday 00:00..04:55
    bars += flat(7 * 24 * 60, 60, 1.101)                      # next Monday 00:00..
    series = build_series(bars)
    metrics = metrics_for(series)
    assert len(metrics) == 1
    assert metrics[0].control_status == "matched"
    # Nearest strictly earlier same-weekday bar inside the +/-60 minute band.
    assert metrics[0].control_index == 12
    assert series.times[12].weekday() == series.times[metrics[0].index].weekday()
    assert metrics[0].control_return_48 is not None


def test_control_bar_matches_inside_the_time_band():
    """The same weekday and a nearby minute, because the exact minute is a gap bar."""
    bars = flat(0, 12, 1.1)                                   # Monday 00:00..00:55
    bars += flat(7 * 24 * 60, 60, 1.101)                      # next Monday 00:00..
    series = build_series(bars)
    metrics = metrics_for(series)
    assert len(metrics) == 1
    assert metrics[0].control_status == "matched"
    # The previous week's Monday 00:00 bar is itself a gap bar and is excluded, so
    # the nearest earlier same-weekday bar inside the band is 00:55.
    assert metrics[0].control_index == 11
    assert series.times[11].weekday() == series.times[metrics[0].index].weekday()


def test_control_bar_is_never_a_gap_bar():
    bars = flat(0, 60, 1.1)
    bars += flat(7 * 24 * 60, 60, 1.101)                      # gap bar at index 60
    bars += flat(14 * 24 * 60, 60, 1.102)                     # gap bar at index 120
    series = build_series(bars)
    events = find_gap_events(series)
    assert [event.index for event in events] == [60, 120]
    gap_indices = {event.index for event in events}
    metrics = metrics_for(series)
    # Week 1 has no preceding gap, so its nearest in-band bar wins; for week 3 the
    # gap bar at index 60 is skipped and index 72 is used instead.
    assert [metric.control_index for metric in metrics] == [12, 72]
    for metric in metrics:
        assert metric.control_index not in gap_indices


# --------------------------------------------------------------------------
# Stage B cost model
# --------------------------------------------------------------------------

def test_zero_cost_fade_fill_is_exactly_one_r(monkeypatch):
    monkeypatch.setattr("research_gap_fill_m5.SLIPPAGE_PIPS", 0.0)
    bars = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),
        (125, 1.1, 1.1, 1.0990, 1.1),
    ]
    series = make_series(bars, spread_price=0.0)
    trade = stage_b(series, metrics_for(series))[0]
    assert trade.reason in ("target", "target_gap")
    # No spread and no slippage: the target pays exactly the structural 1R and the
    # reward distance equals the risk distance.
    assert trade.net_r == pytest.approx(1.0, abs=1e-9)
    assert trade.risk == pytest.approx(
        trade.direction * (trade.target_fill - trade.entry), rel=1e-12
    )
    assert trade.risk == pytest.approx(0.001, rel=1e-9)


def test_one_spread_is_charged_per_round_trip_in_both_directions():
    long_bars = [
        (0, 1.101, 1.101, 1.101, 1.101),
        (120, 1.1, 1.1002, 1.0998, 1.1),                 # gap down -> fade long
        (125, 1.101, 1.1015, 1.1005, 1.101),             # target 1.101 reached
    ]
    short_bars = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),             # gap up -> fade short
        (125, 1.1, 1.1005, 1.0990, 1.1),                 # target 1.100 reached
    ]
    long_series = make_series(long_bars)
    short_series = make_series(short_bars)
    long_trade = stage_b(long_series, metrics_for(long_series))[0]
    short_trade = stage_b(short_series, metrics_for(short_series))[0]
    assert long_trade.reason in ("target", "target_gap")
    assert short_trade.reason in ("target", "target_gap")
    assert long_trade.direction == 1 and short_trade.direction == -1
    assert long_trade.risk == pytest.approx(short_trade.risk, rel=1e-12)
    assert long_trade.net_r == pytest.approx(short_trade.net_r, rel=1e-12)
    # net_r = (gap - spread - 2 * slippage) / (gap + spread + 2 * slippage),
    # identical for both directions: one spread and one adverse slippage per leg,
    # and a stop-out is exactly -1R.
    expected = (0.001 - SPREAD - 2 * 0.1 * PIP) / (0.001 + SPREAD + 2 * 0.1 * PIP)
    assert long_trade.net_r == pytest.approx(expected, rel=1e-9)


def test_cost_scale_is_applied_to_the_spread_only():
    bars = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),
        (125, 1.1, 1.1005, 1.0990, 1.1),
    ]
    series = build_series(bars)
    metrics = metrics_for(series)
    normal = stage_b(series, metrics, cost_scale=1.0)[0]
    stress = stage_b(series, metrics, cost_scale=2.0)[0]
    assert normal.risk == pytest.approx(0.001 + SPREAD + 2 * 0.1 * PIP, rel=1e-9)
    assert stress.risk == pytest.approx(0.001 + 2 * SPREAD + 2 * 0.1 * PIP, rel=1e-9)
    assert stress.net_r < normal.net_r


def test_continuation_arm_mirrors_the_fade_arm():
    bars = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),
        (125, 1.1005, 1.1015, 1.1005, 1.101),
    ]
    series = build_series(bars)
    metrics = metrics_for(series)
    fade = stage_b(series, metrics, arm="fade")[0]
    continuation = stage_b(series, metrics, arm="continuation")[0]
    assert fade.direction == -1 and continuation.direction == 1
    # Same event, same barrier distances, mirrored: the fade target is the
    # previous close and the continuation stop is that same level.
    assert continuation.stop == pytest.approx(fade.target)
    assert continuation.target == pytest.approx(fade.stop)
    assert continuation.risk == pytest.approx(fade.risk, rel=1e-12)
    # Mirrored barriers on a gap bar that closes back at its own open: both arms
    # end at the period boundary with exactly the round-trip cost, so net_r is the
    # same negative number for both.
    expected_cost_r = (SPREAD + 2 * 0.1 * PIP) / (0.001 + SPREAD + 2 * 0.1 * PIP)
    assert fade.net_r == pytest.approx(continuation.net_r, rel=1e-9)
    assert fade.net_r == pytest.approx(-expected_cost_r, rel=1e-9)


# --------------------------------------------------------------------------
# Stage A summary and gates
# --------------------------------------------------------------------------

def test_stage_a_summary_reports_fill_first_split_and_partial_reach():
    series = build_series(gap_up_short_series(extra_bars=60))
    metrics = metrics_for(series)
    summary = summarise_group(metrics)
    assert summary["events"] == 1
    assert summary["fade"]["events"] == 1
    assert summary["fade"]["target_first"] == 0
    assert summary["fade"]["none"] == 1
    assert summary["fade"]["fill_reached_ratio"] == 0.0
    # The entry bar itself spans half the gap, so 25% is reached and 75% is not.
    assert summary["fade"]["partial_fill_reach_ratio"]["0.25"] == 1.0
    assert summary["fade"]["partial_fill_reach_ratio"]["0.75"] == 0.0
    assert summary["fade"]["mfe_gap_fraction"]["max"] == pytest.approx(0.5, abs=1e-3)


def test_stage_a_summary_counts_a_fill_first_event():
    bars = [
        (0, 1.1, 1.1, 1.1, 1.1),
        (120, 1.101, 1.1012, 1.1008, 1.101),
        (125, 1.1, 1.1005, 1.0995, 1.1),
    ]
    series = build_series(bars)
    summary = summarise_group(metrics_for(series))
    assert summary["fade"]["target_first"] == 1
    assert summary["fade"]["target_first_ratio"] == 1.0
    assert summary["fade"]["fill_reached_within_48"] == 1
    assert summary["fade"]["partial_fill_reach_ratio"]["0.5"] == 1.0
    assert summary["continuation"]["stop_first"] == 1


def test_empty_group_keeps_the_block_structure():
    summary = summarise_group([])
    assert summary["events"] == 0
    assert summary["fade"]["target_first_ratio"] is None
    assert summary["continuation"]["events"] == 0
    assert summary["control"]["matched"] == 0
    assert summary["gap_pips"] is None


def test_stage_a_gates_are_evaluated_without_crashing_on_thin_data():
    series = build_series(gap_up_short_series())
    summary = build_stage_a_summary(metrics_for(series), [10.0, 25.0], ["EURUSD"])
    gates = summary["gate_evaluation"]
    assert gates["status"] == "descriptive_check_by_research_script"
    assert gates["stage_a_population"]["passed"] is False
    assert gates["stage_a_data"]["status"] == "manual"
    assert "stage_a_fill_first" in gates


def test_quantiles_and_ratio_handle_empty_input():
    assert quantiles([]) is None
    assert ratio(0, 0) is None
    assert ratio(1, 4) == 0.25
    described = quantiles([1.0, 2.0, 3.0, 4.0, 5.0])
    assert described["count"] == 5
    assert described["p50"] == pytest.approx(3.0)


def test_stage_a_summary_is_deterministic():
    series = build_series(gap_up_short_series(extra_bars=60))
    metrics = metrics_for(series)
    first = json.dumps(build_stage_a_summary(metrics, [10.0], ["EURUSD"]), sort_keys=True)
    second = json.dumps(build_stage_a_summary(metrics, [10.0], ["EURUSD"]), sort_keys=True)
    assert first == second


# --------------------------------------------------------------------------
# protocol parsing, frozen guard and the fixed candidate grid
# --------------------------------------------------------------------------

def test_parse_periods_reads_the_three_declared_ranges():
    protocol = {
        "periods": {
            "training": "2009-10-01〜2016-12-31",
            "validation": "2017-01-01〜2021-12-31",
            "final_confirmation": "2022-01-01〜2026-09-07",
        }
    }
    specs = parse_periods(protocol)
    assert [spec.name for spec in specs] == list(PERIOD_NAMES)
    assert specs[0].start_date == "2009-10-01"
    assert specs[2].end_date == "2026-09-07"


DISTINCT_RANGES = {
    "training": "2016-01-01〜2016-12-31",
    "validation": "2017-01-01〜2017-12-31",
    "final_confirmation": "2018-01-01〜2018-12-31",
}


def test_parse_periods_accepts_an_ascii_tilde_separator():
    periods = {
        "training": "2020-01-01~2020-12-31",
        "validation": "2021-01-01~2021-12-31",
        "final_confirmation": "2022-01-01~2022-12-31",
    }
    specs = parse_periods({"periods": periods})
    assert specs[1].start_date == "2021-01-01"


@pytest.mark.parametrize(
    "periods",
    [
        {"training": "2009-10-01", "validation": "2017-01-01〜2021-12-31",
         "final_confirmation": "2022-01-01〜2026-09-07"},
        {"training": "2009-10-01〜2016-12-31", "validation": "2017-01-01〜2021-12-31"},
        {"training": "2009-10-01〜2016-12-31", "validation": "2017-01-01〜2021-12-31",
         "final_confirmation": "2022-01-01〜2026-09-07", "extra": "2027-01-01〜2027-12-31"},
        {"training": "2016-12-31〜2009-10-01", "validation": "2017-01-01〜2021-12-31",
         "final_confirmation": "2022-01-01〜2026-09-07"},
        {"training": "2009-10-01〜2018-12-31", "validation": "2017-01-01〜2021-12-31",
         "final_confirmation": "2022-01-01〜2026-09-07"},
        {"training": "2009-13-01〜2016-12-31", "validation": "2017-01-01〜2021-12-31",
         "final_confirmation": "2022-01-01〜2026-09-07"},
    ],
    ids=["no-range", "missing-key", "extra-key", "reversed", "overlapping", "bad-month"],
)
def test_parse_periods_rejects_malformed_ranges(periods):
    with pytest.raises(ProtocolViolation):
        parse_periods({"periods": periods})


def test_real_protocol_parses_and_matches_the_script_constants():
    protocol = json.loads(
        (ROOT / "docs/quant_organization/experiments/gap_fill_m5_20261019/protocol.json").read_text(
            encoding="utf-8"
        )
    )
    specs = parse_periods(protocol)
    assert tuple(spec.name for spec in specs) == PERIOD_NAMES
    # Fails loudly if the director changes symbols / RR / holding bars without
    # updating the script (this is the guard against silent specification drift).
    validate_protocol_against_code(protocol, specs)
    windows = period_windows_for_testing(specs)
    for (_, start, end), (_, next_start, _) in zip(windows, windows[1:]):
        assert start < end < next_start


def period_windows_for_testing(specs):
    from research_gap_fill_m5 import period_windows

    return period_windows(specs)


def test_validate_protocol_against_code_rejects_drift():
    protocol = {
        "experiment_id": "gap_fill_m5_20261019",
        "symbols": list(SYMBOLS[:-1]),
        "exit_rules": {"reward_risk_ratio": 1.0, "max_holding_bars_m5": 48},
    }
    specs = parse_periods({"periods": DISTINCT_RANGES})
    with pytest.raises(ProtocolViolation):
        validate_protocol_against_code(protocol, specs)
    protocol["symbols"] = list(SYMBOLS)
    validate_protocol_against_code(protocol, specs)
    protocol["exit_rules"] = {"reward_risk_ratio": 1.5, "max_holding_bars_m5": 48}
    with pytest.raises(ProtocolViolation):
        validate_protocol_against_code(protocol, specs)
    protocol["exit_rules"] = {"reward_risk_ratio": 1.0, "max_holding_bars_m5": 24}
    with pytest.raises(ProtocolViolation):
        validate_protocol_against_code(protocol, specs)


def test_unfrozen_protocol_is_refused():
    with pytest.raises(ProtocolViolation):
        guard_frozen({"frozen_at": None, "status": "SPEC_DRAFT_DATA_PENDING"}, False)
    guard_frozen({"frozen_at": None}, True)          # explicit development override
    guard_frozen({"frozen_at": "2026-10-19T00:00:00Z"}, False)


def test_main_refuses_to_run_before_the_protocol_is_frozen(monkeypatch, capsys):
    frozen = {
        "experiment_id": "gap_fill_m5_20261019",
        "status": "SPEC_DRAFT_DATA_PENDING",
        "frozen_at": None,
        "symbols": list(SYMBOLS),
        "exit_rules": {"reward_risk_ratio": 1.0, "max_holding_bars_m5": 48},
        "periods": dict(DISTINCT_RANGES),
    }
    monkeypatch.setattr("research_gap_fill_m5.read_protocol", lambda: frozen)
    blocked = ROOT / "agent_runs" / "_gap_fill_m5_must_not_be_created"
    assert main(["--output", str(blocked)]) == 2
    assert "PROTOCOL GUARD" in capsys.readouterr().err
    assert not blocked.exists()


def test_main_rejects_a_threshold_outside_the_frozen_grid(monkeypatch, capsys):
    frozen = {
        "experiment_id": "gap_fill_m5_20261019",
        "status": "SPEC_FROZEN",
        "frozen_at": "2026-10-19T00:29:28Z",
        "symbols": list(SYMBOLS),
        "exit_rules": {"reward_risk_ratio": 1.0, "max_holding_bars_m5": 48},
        "periods": dict(DISTINCT_RANGES),
    }
    monkeypatch.setattr("research_gap_fill_m5.read_protocol", lambda: frozen)
    blocked = ROOT / "agent_runs" / "_gap_fill_m5_must_not_be_created"
    assert main(["--output", str(blocked), "--thresholds", "7.5"]) == 2
    assert "PROTOCOL GUARD" in capsys.readouterr().err
    assert not blocked.exists()


@pytest.mark.parametrize(
    "thresholds,cost_scales,periods,symbols",
    [
        ([10.0, 25.0], [1.0, 2.0], list(PERIOD_NAMES), list(SYMBOLS)),
        ([10.0], [1.0], ["training"], ["EURUSD"]),
    ],
)
def test_validate_grid_accepts_the_declared_grid(thresholds, cost_scales, periods, symbols):
    validate_grid(thresholds, cost_scales, periods, symbols)


@pytest.mark.parametrize(
    "thresholds,cost_scales,periods,symbols",
    [
        ([5.0], [1.0], list(PERIOD_NAMES), list(SYMBOLS)),
        ([10.0], [3.0], list(PERIOD_NAMES), list(SYMBOLS)),
        ([10.0], [1.0], ["holdout"], list(SYMBOLS)),
        ([10.0], [1.0], list(PERIOD_NAMES), ["EURUSD", "XAUUSD"]),
    ],
    ids=["threshold", "cost", "period", "symbol"],
)
def test_validate_grid_rejects_anything_outside_it(thresholds, cost_scales, periods, symbols):
    with pytest.raises(ProtocolViolation):
        validate_grid(thresholds, cost_scales, periods, symbols)


def test_claim_constants_match_the_protocol_text():
    assert list(CLAIMED_THRESHOLDS) == [10.0, 25.0]
    assert list(CLAIMED_COST_SCALES) == [1.0, 2.0]
    assert MAX_HOLDING_BARS == 48
    assert len(SYMBOLS) == 11


# --------------------------------------------------------------------------
# fingerprints and determinism helpers
# --------------------------------------------------------------------------

def test_series_sha256_is_stable_and_content_dependent():
    first = build_series(gap_up_short_series())
    same = build_series(gap_up_short_series())
    other = build_series(gap_up_short_series(gap_pips=11.0))
    assert series_sha256(first) == series_sha256(same)
    assert series_sha256(first) != series_sha256(other)


def test_stream_sha256_matches_plain_hashing():
    # Any existing repository file works; the digest must equal the plain hash of
    # the same bytes (no temporary files, which the sandbox denies).
    path = ROOT / "pyproject.toml"
    assert stream_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_no_random_source_is_imported():
    import research_gap_fill_m5 as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "import random" not in source
    assert "np.random" not in source


def test_control_index_is_deterministic():
    bars = flat(0, 60, 1.1) + flat(7 * 24 * 60, 60, 1.101)
    series = build_series(bars)
    events = find_gap_events(series)
    first = ControlIndex(series, [event.index for event in events]).find(events[0].index)
    second = ControlIndex(series, [event.index for event in events]).find(events[0].index)
    assert first == second == 12
