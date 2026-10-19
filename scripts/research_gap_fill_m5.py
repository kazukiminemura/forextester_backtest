"""Stage A / Stage B research runner for experiment ``gap_fill_m5_20261019``.

Frozen specification (do not edit here):
    docs/quant_organization/experiments/gap_fill_m5_20261019/protocol.json
Hypothesis document:
    docs/quant_organization/experiments/gap_fill_m5_20261019/hypothesis.md

Design notes.  Every convention the frozen protocol depends on is stated here
because the validator must be able to reimplement it without reading my mind.

Data access
    Read-only through ``forextester_backtest.data.HistoryRepository``.  Stored
    ``Bars.dat`` / ``info.dat`` files are only streamed for SHA256; nothing under
    the History directory is ever opened for writing.

M5 aggregation
    Stored M1 is aggregated into OLE-second buckets of 300 s.  Bucketing mirrors
    ``data._aggregate_bars`` (integer-truncated OLE seconds).  The one added
    guarantee is that a non-whole-second M1 stamp raises instead of being
    silently truncated.

    Partial buckets (fewer than five constituent M1 bars) are kept as one bar,
    with the bucket-start time and the first M1 open, exactly like
    ``_aggregate_bars``.  They are never interpolated away and never repaired.
    The number of gap bars built from fewer than five M1 bars is reported, and
    that subset is aggregated separately as robustness evidence.  Robustness
    numbers are not used by any acceptance gate.

Determinism
    No randomness, no search.  Thresholds, cost scales, periods and symbols are
    validated against the frozen grid and rejected otherwise.

Stage separation
    Stage A (population + fill-first aggregation, no P&L) is the default.
    Stage B (RR1 execution simulation) requires the explicit ``--stage-b`` flag.
    Both refuse to run while ``protocol.json`` has ``frozen_at = null`` unless
    ``--allow-unfrozen`` is passed, so a pre-freeze run cannot happen by accident.

Persisted detail
    Only aggregates, quantiles and a capped diagnostic sample are written.  Full
    per-event and per-trade detail is deliberately not persisted (see
    ``run_manifest.json:detail_policy``).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from forextester_backtest.data import OLE_EPOCH, HistoryRepository

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "gap_fill_m5_20261019"
EXPERIMENT_DIR = ROOT / "docs" / "quant_organization" / "experiments" / EXPERIMENT_ID
PROTOCOL_PATH = EXPERIMENT_DIR / "protocol.json"
DEFAULT_OUTPUT = ROOT / "agent_runs" / EXPERIMENT_ID
DEFAULT_HISTORY_DIR = r"C:\ForexTester6\data\History"

SYMBOLS = (
    "AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "USDCHF", "USDJPY",
    "AUDJPY", "CHFJPY", "EURCHF", "GBPCHF", "GBPJPY",
)
# The three declared period names, in declared order.  The dates themselves are
# read from protocol.json at run time (see parse_periods) so that a director edit
# can never silently fall out of sync with a hard-coded range in this script.
PERIOD_NAMES = ("training", "validation", "final_confirmation")
PERIOD_PATTERN = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*[〜~]\s*(\d{4}-\d{2}-\d{2})\s*$")
CLAIMED_THRESHOLDS = (10.0, 25.0)
CLAIMED_COST_SCALES = (1.0, 2.0)

M5_SECONDS = 300
SECONDS_PER_DAY = 86_400
GAP_MINUTES = 120
MAX_HOLDING_BARS = 48
SLIPPAGE_PIPS = 0.1
# A gap exactly equal to the threshold must be adopted.  Float64 price
# differences can land a few 1e-16 above or below the nominal pip value, so the
# comparison carries an explicit tolerance far below any real measurement.
THRESHOLD_TOLERANCE_PIPS = 1e-9
PARTIAL_FILL_LEVELS = (0.25, 0.50, 0.75)
CONTROL_MAX_LAG_SECONDS = 8 * 86_400
# Same weekday and a +/- band around the same time of day.  An exact-minute match
# is structurally impossible here: the weekly gap bar sits at the session-open
# minute, so the bar at that same weekday and minute one week earlier is itself a
# gap bar and is excluded by construction (measured on the USDJPY smoke: 86 of 88
# events unmatched with an exact-minute match).  The band is where the protocol's
# "同一時刻帯" control can actually be sampled.
CONTROL_BAND_MINUTES = 60
DETAIL_SAMPLE_LIMIT = 20
TRADE_SAMPLE_LIMIT = 50
QUANTILE_POINTS = (0.10, 0.25, 0.50, 0.75, 0.90)


class ProtocolViolation(RuntimeError):
    """Raised when a run would leave the frozen candidate grid."""


# --------------------------------------------------------------------------
# Frozen grid helpers
# --------------------------------------------------------------------------

def threshold_key(threshold: float) -> str:
    """Stable JSON key for a threshold, e.g. 10.0 -> 'X10'."""
    return f"X{threshold:g}"


def cost_scale_key(cost_scale: float) -> str:
    """Stable JSON key for a spread multiplier, e.g. 1.0 -> 'cost_scale_1'."""
    return f"cost_scale_{cost_scale:g}"


def meets_threshold(gap_pips: float, threshold: float) -> bool:
    """Threshold test with an explicit tolerance so 'exactly X' is adopted."""
    return gap_pips >= threshold - THRESHOLD_TOLERANCE_PIPS


def period_windows(specs: Sequence["PeriodSpec"]) -> tuple[tuple[str, datetime, datetime], ...]:
    """Inclusive datetime windows for the three declared periods.

    Period strings carry dates only, so each window runs to the last second of
    its end date.
    """
    windows = []
    for spec in specs:
        start = datetime.fromisoformat(spec.start_date)
        end = datetime.fromisoformat(spec.end_date) + timedelta(hours=23, minutes=59, seconds=59)
        windows.append((spec.name, start, end))
    return tuple(windows)


@dataclass(frozen=True, slots=True)
class PeriodSpec:
    """One ``periods`` entry parsed from protocol.json."""

    name: str
    start_date: str
    end_date: str


def parse_periods(protocol: dict[str, Any]) -> tuple[PeriodSpec, ...]:
    """Read the three declared periods from protocol.json.

    Raises ProtocolViolation when the key set is not exactly the declared three,
    when a range is not ``YYYY-MM-DD〜YYYY-MM-DD``, or when the ranges do not
    increase in the declared order.
    """
    raw = protocol.get("periods")
    if not isinstance(raw, dict):
        raise ProtocolViolation("protocol.periods is missing or not an object")
    missing = [name for name in PERIOD_NAMES if name not in raw]
    if missing:
        raise ProtocolViolation(f"protocol.periods is missing {missing}")
    extra = sorted(key for key in raw if key not in PERIOD_NAMES)
    if extra:
        raise ProtocolViolation(
            f"protocol.periods has undeclared entries {extra}; expected exactly {list(PERIOD_NAMES)}"
        )
    specs: list[PeriodSpec] = []
    for name in PERIOD_NAMES:
        text = raw[name]
        match = PERIOD_PATTERN.match(text if isinstance(text, str) else "")
        if match is None:
            raise ProtocolViolation(
                f"protocol.periods[{name!r}] = {text!r} is not 'YYYY-MM-DD〜YYYY-MM-DD'"
            )
        start_date, end_date = match.groups()
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError as exc:
            raise ProtocolViolation(f"protocol.periods[{name!r}] has an invalid date: {exc}") from exc
        if end <= start:
            raise ProtocolViolation(
                f"protocol.periods[{name!r}] ends before it starts: {start_date}..{end_date}"
            )
        specs.append(PeriodSpec(name, start_date, end_date))
    for earlier, later in zip(specs, specs[1:]):
        if datetime.fromisoformat(earlier.end_date) >= datetime.fromisoformat(later.start_date):
            raise ProtocolViolation(
                f"protocol periods overlap or are out of order: "
                f"{earlier.name}({earlier.end_date}) >= {later.name}({later.start_date})"
            )
    return tuple(specs)


def validate_protocol_against_code(protocol: dict[str, Any], specs: Sequence[PeriodSpec]) -> None:
    """Fail loudly when the frozen specification and this script disagree.

    Only the constants that define the frozen grid are checked; a deliberate
    specification change must be paired with an update here so the mismatch can
    never be silent.
    """
    if protocol.get("experiment_id") != EXPERIMENT_ID:
        raise ProtocolViolation(
            f"protocol experiment_id {protocol.get('experiment_id')!r} != {EXPERIMENT_ID!r}"
        )
    symbols = protocol.get("symbols")
    if list(symbols or []) != list(SYMBOLS):
        raise ProtocolViolation(
            f"protocol.symbols {symbols!r} does not match the frozen symbol list "
            f"{list(SYMBOLS)!r}"
        )
    exit_rules = protocol.get("exit_rules") or {}
    if exit_rules.get("reward_risk_ratio") != 1.0:
        raise ProtocolViolation(
            f"protocol.exit_rules.reward_risk_ratio {exit_rules.get('reward_risk_ratio')!r} "
            "!= 1.0 (RR1 full exit)"
        )
    if exit_rules.get("max_holding_bars_m5") != MAX_HOLDING_BARS:
        raise ProtocolViolation(
            f"protocol.exit_rules.max_holding_bars_m5 "
            f"{exit_rules.get('max_holding_bars_m5')!r} != {MAX_HOLDING_BARS}"
        )
    if tuple(spec.name for spec in specs) != PERIOD_NAMES:
        raise ProtocolViolation(
            f"parsed period names {[spec.name for spec in specs]!r} != {list(PERIOD_NAMES)!r}"
        )


def pip_size(decimals: int) -> float:
    """One pip in price terms, derived from the stored metadata.

    Forex Tester stores the smallest quoted increment as ``decimals`` digits.
    In this History directory non-JPY pairs carry 5 decimals (EURUSD spread=11
    points -> 0.00011 = 1.1 pip) and JPY crosses carry 3 decimals (USDJPY
    spread=12 points -> 0.012 = 1.2 pip).  One pip is ten of those increments,
    so 5 digits -> 0.0001 and 3 digits -> 0.01.  Deriving the pip from metadata
    keeps JPY crosses on the 0.01 base without a hard-coded currency list.
    """
    if decimals not in (3, 5):
        raise ValueError(f"unsupported decimals={decimals}; expected 3 (JPY) or 5")
    return 10.0 ** (1 - decimals)


def validate_grid(
    thresholds: Sequence[float],
    cost_scales: Sequence[float],
    periods: Sequence[str],
    symbols: Sequence[str],
) -> None:
    """Reject any run that leaves the pre-declared candidate grid."""
    for value in thresholds:
        if value not in CLAIMED_THRESHOLDS:
            raise ProtocolViolation(
                f"threshold {value} is not in the frozen grid {CLAIMED_THRESHOLDS}; "
                "a new threshold needs a new experiment ID"
            )
    for value in cost_scales:
        if value not in CLAIMED_COST_SCALES:
            raise ProtocolViolation(
                f"cost scale {value} is not in the frozen grid {CLAIMED_COST_SCALES}"
            )
    for name in periods:
        if name not in PERIOD_NAMES:
            raise ProtocolViolation(f"unknown period {name!r}; expected {PERIOD_NAMES}")
    for name in symbols:
        if name not in SYMBOLS:
            raise ProtocolViolation(f"symbol {name!r} is not in the frozen symbol list")


# --------------------------------------------------------------------------
# Data access and M5 aggregation
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class M5Series:
    """Columnar M5 view of one symbol.  No Bar objects are retained."""

    symbol: str
    epoch: np.ndarray        # int64, OLE whole seconds at the bucket start
    open: np.ndarray         # float64, first M1 open of the bucket
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray        # last M1 close of the bucket
    m1_count: np.ndarray     # int32, constituent M1 bars (5 == complete bucket)
    pip: float
    spread_price: float
    decimals: int
    m1_bars: int
    first_m1_time: datetime | None
    last_m1_time: datetime | None

    @property
    def size(self) -> int:
        return int(self.epoch.size)

    @property
    def spread_pips(self) -> float:
        return self.spread_price / self.pip

    @property
    def times(self) -> list[datetime]:
        return [OLE_EPOCH + timedelta(seconds=int(value)) for value in self.epoch]


def _epoch_seconds(times: Sequence[datetime]) -> np.ndarray:
    values = []
    for moment in times:
        seconds = (moment - OLE_EPOCH).total_seconds()
        whole = math.floor(seconds + 1e-6)
        if abs(seconds - whole) > 1e-6:
            raise ValueError(f"timestamp is not a whole second: {moment.isoformat()}")
        values.append(whole)
    return np.asarray(values, dtype=np.int64)


def make_m5_series(
    *,
    symbol: str,
    times: Sequence[datetime],
    open: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    pip: float,
    spread_price: float,
    decimals: int,
    m1_count: Sequence[int] | None = None,
    m1_bars: int = 0,
    first_m1_time: datetime | None = None,
    last_m1_time: datetime | None = None,
) -> M5Series:
    """Build an M5Series with deterministic validation.

    ``m1_count`` defaults to 5 (complete buckets) and is the field that carries
    the partial-bucket information.
    """
    epoch = _epoch_seconds(times)
    o = np.asarray(open, dtype=np.float64)
    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    size = int(epoch.size)
    if not (o.size == h.size == l.size == c.size == size):
        raise ValueError("M5 arrays must have equal lengths")
    if m1_count is None:
        counts = np.full(size, 5, dtype=np.int32)
    else:
        counts = np.asarray(m1_count, dtype=np.int32)
        if counts.size != size:
            raise ValueError("m1_count must match the bar count")
    if size:
        if not np.isfinite(np.concatenate([o, h, l, c])).all():
            raise ValueError("M5 prices must be finite")
        if np.any(o <= 0) or np.any(h < l):
            raise ValueError("invalid M5 prices")
        if np.any(h < np.maximum(o, c) - 1e-12) or np.any(l > np.minimum(o, c) + 1e-12):
            raise ValueError("inconsistent M5 OHLC")
        if np.any(np.diff(epoch) <= 0):
            raise ValueError("M5 times must be strictly increasing")
        if np.any(counts < 1):
            raise ValueError("m1_count must be >= 1")
    if m1_bars == 0:
        m1_bars = int(counts.sum())
    return M5Series(
        symbol=symbol,
        epoch=epoch,
        open=o,
        high=h,
        low=l,
        close=c,
        m1_count=counts,
        pip=float(pip),
        spread_price=float(spread_price),
        decimals=int(decimals),
        m1_bars=int(m1_bars),
        first_m1_time=first_m1_time,
        last_m1_time=last_m1_time,
    )


def aggregate_m5_prices(
    symbol: str,
    rows: Iterable[tuple[datetime, float, float, float, float, float]],
    *,
    pip: float,
    spread_price: float,
    decimals: int,
) -> M5Series:
    """Aggregate stored M1 rows into M5 buckets, deterministically and streamed.

    ``rows`` is an iterable of ``(time, open, high, low, close, volume)``.  Bars
    are accumulated bucket by bucket, so no per-M1 Python object survives the
    call.
    """
    epochs: list[int] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    counts: list[int] = []
    current: int | None = None
    m1_bars = 0
    first_m1: datetime | None = None
    last_m1: datetime | None = None
    for time, open_, high, low, close, _volume in rows:
        seconds = (time - OLE_EPOCH).total_seconds()
        whole = math.floor(seconds + 1e-6)
        if abs(seconds - whole) > 1e-6:
            raise ValueError(f"{symbol}: M1 timestamp is not a whole second: {time.isoformat()}")
        bucket = whole // M5_SECONDS
        if current != bucket:
            epochs.append(bucket * M5_SECONDS)
            opens.append(float(open_))
            highs.append(float(high))
            lows.append(float(low))
            closes.append(float(close))
            counts.append(1)
            current = bucket
        else:
            if float(high) > highs[-1]:
                highs[-1] = float(high)
            if float(low) < lows[-1]:
                lows[-1] = float(low)
            closes[-1] = float(close)
            counts[-1] += 1
        m1_bars += 1
        if first_m1 is None:
            first_m1 = time
        last_m1 = time
    return make_m5_series(
        symbol=symbol,
        times=[OLE_EPOCH + timedelta(seconds=value) for value in epochs],
        open=opens,
        high=highs,
        low=lows,
        close=closes,
        pip=pip,
        spread_price=spread_price,
        decimals=decimals,
        m1_count=counts,
        m1_bars=m1_bars,
        first_m1_time=first_m1,
        last_m1_time=last_m1,
    )


def load_m5_series(
    repository: HistoryRepository,
    symbol: str,
    start: datetime,
    end: datetime,
) -> M5Series:
    """Read stored M1 for one symbol and aggregate it to M5."""
    metadata = repository.metadata(symbol)
    pip = pip_size(metadata.decimals)
    rows = (
        (bar.time, bar.open, bar.high, bar.low, bar.close, bar.volume)
        for bar in repository.bars(symbol, start, end, "1m")
    )
    return aggregate_m5_prices(
        symbol,
        rows,
        pip=pip,
        spread_price=metadata.spread_price,
        decimals=metadata.decimals,
    )


def stream_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def series_sha256(series: M5Series) -> str:
    """Digest of the aggregated M5 columns actually consumed by the analysis."""
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(series.epoch, dtype="<i8").tobytes())
    for column in (series.open, series.high, series.low, series.close):
        digest.update(np.ascontiguousarray(column, dtype="<f8").tobytes())
    digest.update(np.ascontiguousarray(series.m1_count, dtype="<i4").tobytes())
    return digest.hexdigest()


# --------------------------------------------------------------------------
# Period windows
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PeriodWindow:
    name: str
    start: datetime
    end: datetime
    start_epoch: int
    end_epoch: int
    first_index: int
    last_index: int

    @property
    def empty(self) -> bool:
        return self.last_index < self.first_index


def build_period_windows(series: M5Series, specs: Sequence[PeriodSpec]) -> tuple[PeriodWindow, ...]:
    windows = []
    for name, start, end in period_windows(specs):
        start_epoch = int((start - OLE_EPOCH).total_seconds())
        end_epoch = int((end - OLE_EPOCH).total_seconds())
        first = int(np.searchsorted(series.epoch, start_epoch, side="left"))
        last = int(np.searchsorted(series.epoch, end_epoch, side="right")) - 1
        windows.append(PeriodWindow(name, start, end, start_epoch, end_epoch, first, last))
    return tuple(windows)


def window_of_epoch(windows: Sequence[PeriodWindow], epoch: int) -> PeriodWindow | None:
    for window in windows:
        if window.start_epoch <= epoch <= window.end_epoch:
            return window
    return None


# --------------------------------------------------------------------------
# Gap detection
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GapEvent:
    symbol: str
    index: int
    time: datetime
    previous_time: datetime
    previous_close: float
    open: float
    gap_price: float
    gap_pips: float
    direction: int              # fade direction; +1 buys the gap down, -1 sells the gap up
    gap_minutes: float
    previous_m1_count: int
    entry_m1_count: int

    @property
    def entry_partial(self) -> bool:
        return self.entry_m1_count < 5


def find_gap_events(series: M5Series, min_gap_minutes: int = GAP_MINUTES) -> list[GapEvent]:
    """First M5 bar after a time discontinuity of at least ``min_gap_minutes``.

    Only the previous bar's close and this bar's open enter the decision, so the
    signal is available at the gap bar's open and never uses future bars.
    """
    if series.size < 2:
        return []
    delta = np.diff(series.epoch)
    indices = np.flatnonzero(delta >= min_gap_minutes * 60) + 1
    events: list[GapEvent] = []
    for raw in indices:
        i = int(raw)
        previous_close = float(series.close[i - 1])
        open_ = float(series.open[i])
        gap_price = abs(open_ - previous_close)
        direction = -1 if open_ > previous_close else 1
        events.append(
            GapEvent(
                symbol=series.symbol,
                index=i,
                time=OLE_EPOCH + timedelta(seconds=int(series.epoch[i])),
                previous_time=OLE_EPOCH + timedelta(seconds=int(series.epoch[i - 1])),
                previous_close=previous_close,
                open=open_,
                gap_price=gap_price,
                gap_pips=gap_price / series.pip,
                direction=direction,
                gap_minutes=float(series.epoch[i] - series.epoch[i - 1]) / 60.0,
                previous_m1_count=int(series.m1_count[i - 1]),
                entry_m1_count=int(series.m1_count[i]),
            )
        )
    return events


# --------------------------------------------------------------------------
# Barrier race and excursion (Stage A building blocks)
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RaceOutcome:
    """First barrier reached inside the holding window."""

    reason: str          # target | stop | target_gap | stop_gap | none
    bar_offset: int      # 0 == entry bar, -1 when no barrier was reached
    ambiguous: bool      # the same M5 bar contained both barriers; stop wins
    truncated: bool      # the window ended at the period boundary before 48 bars

    @property
    def target_first(self) -> bool:
        return self.reason in ("target", "target_gap")

    @property
    def stop_first(self) -> bool:
        return self.reason in ("stop", "stop_gap")


@dataclass(frozen=True, slots=True)
class Excursion:
    """Favourable excursion ignoring the stop, used for fill-reach statistics."""

    mfe: float
    gap_fraction: float
    reached: tuple[bool, ...]   # 25%, 50%, 75%, 100% of the gap
    truncated: bool

    @property
    def target_reached(self) -> bool:
        return self.reached[-1]


def classify_race(
    series: M5Series,
    index: int,
    direction: int,
    stop_level: float,
    target_level: float,
    last_index: int,
    max_bars: int = MAX_HOLDING_BARS,
) -> RaceOutcome:
    """Walk forward from ``index`` and return the first barrier reached.

    Order follows ``scripts/quant_rr_execution.py``: an opening beyond a barrier
    is settled first (stop before target), then same-bar touches with the stop
    taking priority, then the period boundary.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    last = min(index + max_bars - 1, last_index)
    if last < index:
        raise ValueError("empty holding window")
    truncated = (index + max_bars - 1) > last_index
    for k in range(index, last + 1):
        opening = float(series.open[k])
        if direction * (opening - stop_level) <= 0:
            return RaceOutcome("stop_gap", k - index, False, truncated)
        if direction * (opening - target_level) >= 0:
            return RaceOutcome("target_gap", k - index, False, truncated)
        if direction == 1:
            hit_stop = float(series.low[k]) <= stop_level
            hit_target = float(series.high[k]) >= target_level
        else:
            hit_stop = float(series.high[k]) >= stop_level
            hit_target = float(series.low[k]) <= target_level
        if hit_stop and hit_target:
            return RaceOutcome("stop", k - index, True, truncated)
        if hit_stop:
            return RaceOutcome("stop", k - index, False, truncated)
        if hit_target:
            return RaceOutcome("target", k - index, False, truncated)
    return RaceOutcome("none", -1, False, truncated)


def favourable_excursion(
    series: M5Series,
    index: int,
    direction: int,
    gap_price: float,
    last_index: int,
    max_bars: int = MAX_HOLDING_BARS,
) -> Excursion:
    """Maximum favourable excursion from the entry bar's open, stop ignored."""
    last = min(index + max_bars - 1, last_index)
    if last < index:
        raise ValueError("empty holding window")
    open_ = float(series.open[index])
    window_high = float(np.max(series.high[index:last + 1]))
    window_low = float(np.min(series.low[index:last + 1]))
    mfe = (window_high - open_) if direction == 1 else (open_ - window_low)
    reached = []
    for level in (*PARTIAL_FILL_LEVELS, 1.0):
        bound = open_ + direction * gap_price * level
        if direction == 1:
            reached.append(bool(window_high >= bound))
        else:
            reached.append(bool(window_low <= bound))
    fraction = mfe / gap_price if gap_price > 0 else 0.0
    return Excursion(
        mfe=float(mfe),
        gap_fraction=float(fraction),
        reached=tuple(reached),
        truncated=(index + max_bars - 1) > last_index,
    )


class ControlIndex:
    """Nearest earlier non-gap M5 bar on the same weekday inside a time band.

    The match is same weekday and a +/- ``CONTROL_BAND_MINUTES`` time-of-day band
    around the gap bar's minute, one control per event, bounded to
    ``CONTROL_MAX_LAG_SECONDS``.  Gap bars are removed from the candidate pool so
    the control is always a non-gap bar.  Candidate minutes are clipped to the
    day, never wrapped, and the nearest strictly earlier bar wins; the result is
    deterministic and uses no randomness.
    """

    def __init__(self, series: M5Series, gap_indices: Sequence[int]):
        epoch = series.epoch
        weekday = (epoch // SECONDS_PER_DAY + 5) % 7   # 1899-12-30 is a Saturday
        minute_of_day = (epoch % SECONDS_PER_DAY) // 60
        key = weekday.astype(np.int32) * 1440 + minute_of_day.astype(np.int32)
        keep = np.ones(series.size, dtype=bool)
        if len(gap_indices):
            keep[np.asarray(list(gap_indices), dtype=np.int64)] = False
        position = np.flatnonzero(keep)
        order = np.lexsort((position, key[position]))
        self._key = key[position][order]
        self._index = position[order]
        self._epoch = epoch

    def find(self, index: int) -> int | None:
        epoch = int(self._epoch[index])
        weekday = (epoch // SECONDS_PER_DAY + 5) % 7
        minute = (epoch % SECONDS_PER_DAY) // 60
        # The clipped band stays inside one weekday, so the candidate keys form one
        # contiguous slice: two binary searches instead of one per minute.
        low_key = weekday * 1440 + max(0, minute - CONTROL_BAND_MINUTES)
        high_key = weekday * 1440 + min(1439, minute + CONTROL_BAND_MINUTES)
        low = int(np.searchsorted(self._key, low_key, side="left"))
        high = int(np.searchsorted(self._key, high_key, side="right"))
        if high <= low:
            return None
        candidates = self._index[low:high]
        earlier = candidates[candidates < index]
        if earlier.size == 0:
            return None
        best = int(earlier.max())
        if epoch - int(self._epoch[best]) > CONTROL_MAX_LAG_SECONDS:
            return None
        return best


@dataclass(frozen=True, slots=True)
class EventMetric:
    """Stage A metric set for one gap event.  Independent of the threshold X.

    Because the barriers are built from the gap width itself, the fade race, the
    continuation race, the excursion and the matched control are all threshold
    independent; X only filters which events enter a summary.
    """

    symbol: str
    period: str
    index: int
    time: datetime
    direction: int
    gap_pips: float
    gap_price: float
    gap_minutes: float
    entry_m1_count: int
    previous_m1_count: int
    fade_reason: str
    fade_offset: int
    fade_ambiguous: bool
    fade_truncated: bool
    cont_reason: str
    cont_offset: int
    cont_ambiguous: bool
    cont_truncated: bool
    mfe_pips: float
    gap_fraction: float
    reached: tuple[bool, ...]
    excursion_truncated: bool
    control_status: str            # matched | no_match | truncated
    control_index: int | None
    control_return_48: float | None
    control_fade_reason: str | None


def _control_status(
    series: M5Series,
    control: int | None,
    window: PeriodWindow,
) -> str:
    if control is None:
        return "no_match"
    if min(control + MAX_HOLDING_BARS - 1, window.last_index) < control + MAX_HOLDING_BARS - 1:
        return "truncated"
    return "matched"


def build_event_metrics(
    series: M5Series,
    events: Sequence[GapEvent],
    windows: Sequence[PeriodWindow] | None = None,
    control_index: ControlIndex | None = None,
    specs: Sequence[PeriodSpec] | None = None,
) -> list[EventMetric]:
    """Stage A metrics for every gap event inside a declared period."""
    if not events:
        return []
    if windows is None:
        if specs is None:
            raise ValueError("specs is required when windows are not supplied")
        windows = build_period_windows(series, specs)
    if control_index is None:
        control_index = ControlIndex(series, [event.index for event in events])
    metrics: list[EventMetric] = []
    for event in events:
        epoch = int(series.epoch[event.index])
        window = window_of_epoch(windows, epoch)
        if window is None or window.empty:
            continue
        direction = event.direction
        gap_price = event.gap_price
        stop_level = event.open - direction * gap_price
        target_level = event.open + direction * gap_price
        fade = classify_race(series, event.index, direction, stop_level, target_level, window.last_index)
        cont = classify_race(
            series, event.index, -direction,
            event.open + direction * gap_price, event.open - direction * gap_price,
            window.last_index,
        )
        excursion = favourable_excursion(series, event.index, direction, gap_price, window.last_index)
        control = control_index.find(event.index)
        control_status = _control_status(series, control, window)
        control_return: float | None = None
        control_reason: str | None = None
        if control_status == "matched" and control is not None:
            control_last = control + MAX_HOLDING_BARS - 1
            control_return = (
                direction * (float(series.close[control_last]) - float(series.open[control]))
                / series.pip
            )
            control_open = float(series.open[control])
            control_reason = classify_race(
                series, control, direction,
                control_open - direction * gap_price, control_open + direction * gap_price,
                window.last_index,
            ).reason
        metrics.append(
            EventMetric(
                symbol=series.symbol,
                period=window.name,
                index=event.index,
                time=event.time,
                direction=direction,
                gap_pips=event.gap_pips,
                gap_price=gap_price,
                gap_minutes=event.gap_minutes,
                entry_m1_count=event.entry_m1_count,
                previous_m1_count=event.previous_m1_count,
                fade_reason=fade.reason,
                fade_offset=fade.bar_offset,
                fade_ambiguous=fade.ambiguous,
                fade_truncated=fade.truncated,
                cont_reason=cont.reason,
                cont_offset=cont.bar_offset,
                cont_ambiguous=cont.ambiguous,
                cont_truncated=cont.truncated,
                mfe_pips=excursion.mfe / series.pip,
                gap_fraction=excursion.gap_fraction,
                reached=excursion.reached,
                excursion_truncated=excursion.truncated,
                control_status=control_status,
                control_index=control if control_status == "matched" else None,
                control_return_48=control_return,
                control_fade_reason=control_reason,
            )
        )
    return metrics


# --------------------------------------------------------------------------
# Stage A aggregation
# --------------------------------------------------------------------------

def quantiles(values: Sequence[float]) -> dict[str, float] | None:
    if not len(values):
        return None
    array = np.asarray(values, dtype=np.float64)
    summary: dict[str, float] = {
        "count": int(array.size),
        "mean": float(np.mean(array)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }
    for point in QUANTILE_POINTS:
        summary[f"p{int(point * 100)}"] = float(np.quantile(array, point))
    return summary


def ratio(numerator: int, denominator: int) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _race_block(metrics: Sequence[EventMetric], prefix: str) -> dict[str, Any]:
    reasons = [getattr(metric, f"{prefix}_reason") for metric in metrics]
    target_first = sum(reason in ("target", "target_gap") for reason in reasons)
    stop_first = sum(reason in ("stop", "stop_gap") for reason in reasons)
    ambiguous = sum(
        bool(getattr(metric, f"{prefix}_ambiguous")) and reason in ("stop", "stop_gap")
        for metric, reason in zip(metrics, reasons)
    )
    target_gap = sum(reason == "target_gap" for reason in reasons)
    stop_gap = sum(reason == "stop_gap" for reason in reasons)
    none = sum(reason == "none" for reason in reasons)
    total = len(metrics)
    offsets = [
        int(getattr(metric, f"{prefix}_offset"))
        for metric, reason in zip(metrics, reasons)
        if reason in ("target", "target_gap") and int(getattr(metric, f"{prefix}_offset")) >= 0
    ]
    return {
        "events": total,
        "target_first": target_first,
        "target_first_ratio": ratio(target_first, total),
        "stop_first": stop_first,
        "stop_first_ratio": ratio(stop_first, total),
        "none": none,
        "none_ratio": ratio(none, total),
        "target_gap": target_gap,
        "stop_gap": stop_gap,
        "ambiguous": ambiguous,
        "ambiguous_ratio": ratio(ambiguous, total),
        "window_truncated": sum(bool(getattr(metric, f"{prefix}_truncated")) for metric in metrics),
        "median_target_first_offset_bars": (
            float(np.median(np.asarray(offsets, dtype=np.float64))) if offsets else None
        ),
    }


def summarise_group(metrics: Sequence[EventMetric]) -> dict[str, Any]:
    """Stage A summary for one group of gap events (already threshold filtered).

    The block structure is always present, even for an empty group, so downstream
    gate evaluation never depends on whether a period happened to be empty.
    """
    total = len(metrics)
    summary: dict[str, Any] = {
        "events": total,
        "entry_bar_partial_m1": sum(metric.entry_m1_count < 5 for metric in metrics),
        "previous_bar_partial_m1": sum(metric.previous_m1_count < 5 for metric in metrics),
        "gap_pips": quantiles([metric.gap_pips for metric in metrics]),
        "gap_minutes": quantiles([metric.gap_minutes for metric in metrics]),
        "gap_minutes_over_24h": sum(metric.gap_minutes > 1440 for metric in metrics),
    }
    summary["fade"] = _race_block(metrics, "fade")
    fade = summary["fade"]
    reached_target = sum(metric.reached[-1] for metric in metrics)
    fade["fill_reached_within_48"] = reached_target
    fade["fill_reached_ratio"] = ratio(reached_target, total)
    fade["partial_fill_reach_ratio"] = {
        f"{level:g}": ratio(sum(metric.reached[i] for metric in metrics), total)
        for i, level in enumerate((*PARTIAL_FILL_LEVELS, 1.0))
    }
    fade["mfe_pips"] = quantiles([metric.mfe_pips for metric in metrics])
    fade["mfe_gap_fraction"] = quantiles([metric.gap_fraction for metric in metrics])
    fade["excursion_truncated"] = sum(metric.excursion_truncated for metric in metrics)
    summary["continuation"] = _race_block(metrics, "cont")
    matched = [metric for metric in metrics if metric.control_status == "matched"]
    returns = [metric.control_return_48 for metric in matched if metric.control_return_48 is not None]
    control_reasons = [metric.control_fade_reason for metric in matched]
    summary["control"] = {
        "band_minutes": CONTROL_BAND_MINUTES,
        "max_lag_days": CONTROL_MAX_LAG_SECONDS / SECONDS_PER_DAY,
        "matched": len(matched),
        "unmatched": sum(metric.control_status == "no_match" for metric in metrics),
        "truncated": sum(metric.control_status == "truncated" for metric in metrics),
        "return_48_pips": quantiles(returns),
        "return_48_positive_ratio": ratio(sum(value > 0 for value in returns), len(returns)),
        "target_first": sum(reason in ("target", "target_gap") for reason in control_reasons),
        "target_first_ratio": ratio(
            sum(reason in ("target", "target_gap") for reason in control_reasons),
            len(control_reasons),
        ),
    }
    return summary


def build_stage_a_summary(
    metrics: Sequence[EventMetric],
    thresholds: Sequence[float],
    symbols: Sequence[str],
) -> dict[str, Any]:
    """Pooled / per-period / per-symbol Stage A summaries plus the gate check."""
    def for_threshold(threshold: float, subset: Sequence[EventMetric]) -> dict[str, Any]:
        return summarise_group(
            [m for m in subset if meets_threshold(m.gap_pips, threshold)]
        )

    pooled_all = {
        threshold_key(x): for_threshold(x, metrics) for x in thresholds
    }
    pooled_by_period = {
        name: {threshold_key(x): for_threshold(x, [m for m in metrics if m.period == name]) for x in thresholds}
        for name in PERIOD_NAMES
    }
    by_symbol = {
        symbol: {
            "all_periods": {threshold_key(x): for_threshold(x, [m for m in metrics if m.symbol == symbol]) for x in thresholds},
            "by_period": {
                name: {
                    threshold_key(x): for_threshold(
                        x, [m for m in metrics if m.symbol == symbol and m.period == name]
                    )
                    for x in thresholds
                }
                for name in PERIOD_NAMES
            },
        }
        for symbol in symbols
    }
    partial_entry = [m for m in metrics if m.entry_m1_count < 5]
    complete_entry = [m for m in metrics if m.entry_m1_count >= 5]
    robustness = {
        "note": (
            "Robustness only. Entry-bar M1 completeness splits the same population; "
            "these numbers are not used by any acceptance gate."
        ),
        "partial_entry_bar": {
            threshold_key(x): for_threshold(x, partial_entry) for x in thresholds
        },
        "complete_entry_bar": {
            threshold_key(x): for_threshold(x, complete_entry) for x in thresholds
        },
        "partial_entry_bar_events": len(partial_entry),
        "complete_entry_bar_events": len(complete_entry),
    }
    summary = {
        "pooled_all_periods": pooled_all,
        "pooled_by_period": pooled_by_period,
        "by_symbol": by_symbol,
        "robustness_entry_bar_completeness": robustness,
    }
    summary["gate_evaluation"] = evaluate_stage_a_gates(summary, thresholds, symbols)
    return summary


def evaluate_stage_a_gates(
    summary: dict[str, Any],
    thresholds: Sequence[float],
    symbols: Sequence[str],
) -> dict[str, Any]:
    """Mechanical evaluation of protocol.acceptance_gates (Stage A only).

    This is a descriptive check by the research script.  The independent
    validator must recompute it; no gate result here is an adoption claim.
    """
    primary = threshold_key(CLAIMED_THRESHOLDS[0])
    if primary not in summary["pooled_all_periods"]:
        return {"status": "not_evaluated", "reason": f"{primary} was not requested"}
    pooled_all = summary["pooled_all_periods"][primary]
    per_period = {name: summary["pooled_by_period"][name][primary] for name in PERIOD_NAMES}
    per_symbol_events = {
        symbol: summary["by_symbol"][symbol]["all_periods"][primary]["events"] for symbol in symbols
    }
    per_symbol_ratio = {
        symbol: summary["by_symbol"][symbol]["all_periods"][primary].get("fade", {}).get("target_first_ratio")
        for symbol in symbols
    }
    population = {
        "pooled_events": pooled_all["events"],
        "per_period_events": {name: per_period[name]["events"] for name in PERIOD_NAMES},
        "symbols_with_20_or_more": sorted(
            symbol for symbol, count in per_symbol_events.items() if count >= 20
        ),
        "passed": bool(
            pooled_all["events"] >= 300
            and all(per_period[name]["events"] >= 50 for name in PERIOD_NAMES)
            and sum(count >= 20 for count in per_symbol_events.values()) >= 6
        ),
    }
    fill_first = {
        "pooled_all_periods_ratio": pooled_all["fade"]["target_first_ratio"],
        "training_ratio": per_period["training"]["fade"]["target_first_ratio"],
        "validation_ratio": per_period["validation"]["fade"]["target_first_ratio"],
        "passed": bool(
            (pooled_all["fade"]["target_first_ratio"] or 0.0) >= 0.60
            and (per_period["training"]["fade"]["target_first_ratio"] or 0.0) >= 0.57
            and (per_period["validation"]["fade"]["target_first_ratio"] or 0.0) >= 0.57
        ),
    }
    consistency = {
        "symbols_at_or_above_0.55": sorted(
            symbol for symbol, value in per_symbol_ratio.items() if value is not None and value >= 0.55
        ),
        "passed": bool(
            sum(value is not None and value >= 0.55 for value in per_symbol_ratio.values()) >= 6
        ),
    }
    baseline = {
        name: {
            "fade_target_first_ratio": per_period[name]["fade"]["target_first_ratio"],
            "continuation_target_first_ratio": per_period[name]["continuation"]["target_first_ratio"],
        }
        for name in ("training", "validation")
    }
    baseline["note"] = (
        "The continuation arm mirrors the fade arm on the same events with the same "
        "barrier distances, so fade.target_first + continuation.stop_first = 1 up to "
        "the ambiguous and same-bar cases.  This compares directional asymmetry only."
    )
    baseline["passed"] = bool(
        all(
            (baseline[name]["fade_target_first_ratio"] or 0.0)
            > (baseline[name]["continuation_target_first_ratio"] or 0.0)
            for name in ("training", "validation")
        )
    )
    return {
        "status": "descriptive_check_by_research_script",
        "threshold": primary,
        "stage_a_population": population,
        "stage_a_fill_first": fill_first,
        "stage_a_symbol_consistency": consistency,
        "stage_a_vs_baseline": baseline,
        "stage_a_data": {
            "status": "manual",
            "reason": (
                "Requires the input SHA256 to be compared with "
                "experiments/gap_fill_m5_20261019/data_inventory.md and a data-quality "
                "review; not decidable by this script."
            ),
        },
    }


# --------------------------------------------------------------------------
# Stage B: RR1 execution simulation
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class StageBTrade:
    symbol: str
    period: str
    threshold: float
    cost_scale: float
    arm: str
    direction: int
    entry_index: int
    entry_time: datetime
    entry: float
    stop: float
    target: float
    stop_fill: float
    target_fill: float
    risk: float
    exit_index: int
    exit_time: datetime
    exit: float
    net_r: float
    reason: str
    period_end_cause: str | None
    ambiguous: bool
    bars_held: int
    entry_m1_count: int


def simulate_stage_b(
    series: M5Series,
    metrics: Sequence[EventMetric],
    window: PeriodWindow,
    threshold: float,
    cost_scale: float,
    arm: str = "fade",
) -> list[StageBTrade]:
    """RR1 execution simulation for one symbol / period / threshold / cost scale.

    Cost convention (symmetric, ``protocol.cost_and_fill_model``):
        long  : entry pays the spread, exit is a sale at bid.
        short : entry is a sale at bid, exit pays the spread.
    so exactly one spread is charged per round trip in both directions, and
    adverse slippage of 0.1 pip is applied to entry and to exit.  ``risk`` is the
    realised distance from the entry fill to the stop fill, so a stop-out is
    exactly -1.0R for both directions and the round-trip cost shows up as a
    smaller target payout instead of a direction-dependent R.

    ``arm='fade'`` targets the previous close (full fill).  ``arm='continuation'``
    mirrors direction and distances on the same event, as declared in the
    protocol baseline.

    One position per symbol at a time; the exit bar is never reused as the next
    signal; an unfinished trade at bar 48 or at the period boundary is closed at
    that bar's close with ``reason='period_end'``.
    """
    if arm not in ("fade", "continuation"):
        raise ValueError("arm must be 'fade' or 'continuation'")
    spread = series.spread_price * cost_scale
    slip = series.pip * SLIPPAGE_PIPS
    trades: list[StageBTrade] = []
    next_signal = 0
    for metric in sorted(metrics, key=lambda item: item.index):
        index = metric.index
        if index < next_signal:
            continue
        if not (window.start_epoch <= int(series.epoch[index]) <= window.end_epoch):
            continue
        direction = metric.direction if arm == "fade" else -metric.direction
        gap_price = metric.gap_price
        if gap_price <= 0:
            continue
        open_ = float(series.open[index])
        stop_level = open_ - direction * gap_price
        target_level = open_ + direction * gap_price
        entry = open_ + (spread if direction == 1 else 0.0) + direction * slip
        exit_add = (spread if direction == -1 else 0.0) - direction * slip
        stop_fill = stop_level + exit_add
        target_fill = target_level + exit_add
        risk = direction * (entry - stop_fill)
        if not math.isfinite(risk) or risk <= 0:
            raise ValueError(f"{series.symbol}: non-positive risk at index {index}")
        last = min(index + MAX_HOLDING_BARS - 1, window.last_index)
        reason: str | None = None
        period_end_cause: str | None = None
        exit_price = float(series.close[last]) + exit_add
        exit_index = last
        ambiguous = False
        for k in range(index, last + 1):
            opening = float(series.open[k])
            stop_gap = direction * (opening - stop_level) <= 0
            target_gap = direction * (opening - target_level) >= 0
            if direction == 1:
                hit_stop = float(series.low[k]) <= stop_level
                hit_target = float(series.high[k]) >= target_level
            else:
                hit_stop = float(series.high[k]) >= stop_level
                hit_target = float(series.low[k]) <= target_level
            if stop_gap:
                # A resting stop becomes a market order: fill at the actual open.
                reason, exit_price, exit_index = "stop_gap", opening + exit_add, k
                break
            if target_gap:
                # A resting limit order fills at its own price, not better.
                reason, exit_price, exit_index = "target_gap", target_fill, k
                break
            if hit_stop and hit_target:
                reason, exit_price, exit_index, ambiguous = "stop", stop_fill, k, True
                break
            if hit_stop:
                reason, exit_price, exit_index = "stop", stop_fill, k
                break
            if hit_target:
                reason, exit_price, exit_index = "target", target_fill, k
                break
        if reason is None:
            reason = "period_end"
            exit_price = float(series.close[last]) + exit_add
            exit_index = last
            period_end_cause = (
                "holding_limit" if last == index + MAX_HOLDING_BARS - 1 else "period_boundary"
            )
        net_r = direction * (exit_price - entry) / risk
        trades.append(
            StageBTrade(
                symbol=series.symbol,
                period=window.name,
                threshold=threshold,
                cost_scale=cost_scale,
                arm=arm,
                direction=direction,
                entry_index=index,
                entry_time=OLE_EPOCH + timedelta(seconds=int(series.epoch[index])),
                entry=entry,
                stop=stop_level,
                target=target_level,
                stop_fill=stop_fill,
                target_fill=target_fill,
                risk=risk,
                exit_index=exit_index,
                exit_time=OLE_EPOCH + timedelta(seconds=int(series.epoch[exit_index])),
                exit=exit_price,
                net_r=net_r,
                reason=reason,
                period_end_cause=period_end_cause,
                ambiguous=ambiguous,
                bars_held=exit_index - index + 1,
                entry_m1_count=metric.entry_m1_count,
            )
        )
        next_signal = exit_index + 1
    return trades


def profit_factor(net_values: Sequence[float]) -> float | None:
    gross_profit = sum(value for value in net_values if value > 0)
    gross_loss = -sum(value for value in net_values if value < 0)
    if gross_loss == 0:
        return None
    return gross_profit / gross_loss


def summarise_stage_b(trades: Sequence[StageBTrade], symbols: Sequence[str]) -> dict[str, Any]:
    total = len(trades)
    net_values = [trade.net_r for trade in trades]
    by_symbol: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        subset = [trade for trade in trades if trade.symbol == symbol]
        values = [trade.net_r for trade in subset]
        by_symbol[symbol] = {
            "trades": len(subset),
            "net_r": float(sum(values)) if values else 0.0,
            "mean_net_r": float(np.mean(values)) if values else None,
            "profit_factor": profit_factor(values),
            "wins": sum(value > 0 for value in values),
            "entry_bar_partial_m1": sum(trade.entry_m1_count < 5 for trade in subset),
        }
    positive_total = sum(max(entry["net_r"], 0.0) for entry in by_symbol.values())
    largest = max((max(entry["net_r"], 0.0) for entry in by_symbol.values()), default=0.0)
    reasons: dict[str, int] = {}
    for trade in trades:
        reasons[trade.reason] = reasons.get(trade.reason, 0) + 1
    period_end_causes: dict[str, int] = {}
    for trade in trades:
        if trade.period_end_cause:
            period_end_causes[trade.period_end_cause] = period_end_causes.get(trade.period_end_cause, 0) + 1
    return {
        "trades": total,
        "net_r_total": float(sum(net_values)) if net_values else 0.0,
        "mean_net_r": float(np.mean(net_values)) if net_values else None,
        "profit_factor": profit_factor(net_values),
        "win_rate": ratio(sum(value > 0 for value in net_values), total),
        "reasons": reasons,
        "period_end_causes": period_end_causes,
        "ambiguous": sum(trade.ambiguous for trade in trades),
        "entry_bar_partial_m1": sum(trade.entry_m1_count < 5 for trade in trades),
        "cross_symbol": {
            "symbols_with_trades": sum(entry["trades"] > 0 for entry in by_symbol.values()),
            "symbols_with_20_or_more": sorted(
                symbol for symbol, entry in by_symbol.items() if entry["trades"] >= 20
            ),
            "positive_symbols": sorted(
                symbol for symbol, entry in by_symbol.items() if entry["net_r"] > 0
            ),
            "largest_symbol_share_of_positive_net_r": (
                float(largest / positive_total) if positive_total > 0 else None
            ),
        },
        "by_symbol": by_symbol,
    }


def evaluate_stage_b_gates(
    stage_b: dict[str, Any],
    thresholds: Sequence[float],
) -> dict[str, Any]:
    primary = threshold_key(CLAIMED_THRESHOLDS[0])
    if primary not in stage_b:
        return {"status": "not_evaluated", "reason": f"{primary} was not requested"}
    cell = stage_b[primary]
    normal = cell[cost_scale_key(1.0)]
    stress = cell[cost_scale_key(2.0)]
    counts = {
        name: {
            "trades": normal[name]["fade"]["trades"],
            "symbols_with_20_or_more": normal[name]["fade"]["cross_symbol"]["symbols_with_20_or_more"],
        }
        for name in ("training", "validation")
    }
    counts["passed"] = bool(
        all(
            counts[name]["trades"] >= 150 and len(counts[name]["symbols_with_20_or_more"]) >= 4
            for name in ("training", "validation")
        )
    )
    pf = {
        name: {
            "profit_factor": normal[name]["fade"]["profit_factor"],
            "mean_net_r": normal[name]["fade"]["mean_net_r"],
        }
        for name in ("training", "validation")
    }
    pf["passed"] = bool(
        all(
            (pf[name]["profit_factor"] or 0.0) >= 1.15 and (pf[name]["mean_net_r"] or 0.0) > 0
            for name in ("training", "validation")
        )
    )
    stress_gate = {
        name: {"profit_factor": stress[name]["fade"]["profit_factor"]}
        for name in ("training", "validation")
    }
    stress_gate["passed"] = bool(
        all((stress_gate[name]["profit_factor"] or 0.0) > 1.00 for name in ("training", "validation"))
    )
    concentration = {
        name: {
            "largest_symbol_share_of_positive_net_r": normal[name]["fade"]["cross_symbol"][
                "largest_symbol_share_of_positive_net_r"
            ]
        }
        for name in ("training", "validation")
    }
    concentration["passed"] = bool(
        all(
            (concentration[name]["largest_symbol_share_of_positive_net_r"] or 0.0) <= 0.70
            for name in ("training", "validation")
        )
    )
    baseline = {
        name: {
            "fade_mean_net_r": normal[name]["fade"]["mean_net_r"],
            "continuation_mean_net_r": normal[name]["continuation"]["mean_net_r"],
        }
        for name in ("training", "validation")
    }
    baseline["passed"] = bool(
        all(
            (baseline[name]["fade_mean_net_r"] or 0.0) > (baseline[name]["continuation_mean_net_r"] or 0.0)
            for name in ("training", "validation")
        )
    )
    cross_symbol = {
        "validation_positive_symbols": normal["validation"]["fade"]["cross_symbol"]["positive_symbols"],
    }
    cross_symbol["passed"] = bool(len(cross_symbol["validation_positive_symbols"]) >= 5)
    return {
        "status": "descriptive_check_by_research_script",
        "threshold": primary,
        "arm": "fade",
        "stage_b_counts": counts,
        "stage_b_pf": pf,
        "stage_b_stress": stress_gate,
        "stage_b_concentration": concentration,
        "stage_b_vs_baseline": baseline,
        "stage_b_cross_symbol": cross_symbol,
    }


def build_stage_b_summary(
    trades_by_symbol: dict[str, list[StageBTrade]],
    thresholds: Sequence[float],
    cost_scales: Sequence[float],
    symbols: Sequence[str],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for threshold in thresholds:
        key = threshold_key(threshold)
        summary[key] = {}
        for cost_scale in cost_scales:
            cell: dict[str, Any] = {}
            for name in PERIOD_NAMES:
                for arm in ("fade", "continuation"):
                    subset = [
                        trade
                        for trades in trades_by_symbol.values()
                        for trade in trades
                        if trade.period == name
                        and trade.arm == arm
                        and trade.threshold == threshold
                        and trade.cost_scale == cost_scale
                    ]
                    cell.setdefault(name, {})[arm] = summarise_stage_b(subset, symbols)
            summary[key][cost_scale_key(cost_scale)] = cell
    summary["gate_evaluation"] = evaluate_stage_b_gates(summary, thresholds)
    return summary


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False, default=str),
        encoding="utf-8",
    )


def read_protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def guard_frozen(protocol: dict[str, Any], allow_unfrozen: bool) -> None:
    """Refuse to run before the research director freezes the specification."""
    if protocol.get("frozen_at") in (None, "") and not allow_unfrozen:
        raise ProtocolViolation(
            "protocol.json has frozen_at = null (status "
            f"{protocol.get('status')!r}). Stage A/B must not run before the "
            "research director freezes the specification.  Re-run only after "
            "frozen_at is set."
        )


def sample_metrics(metrics: Sequence[EventMetric], limit: int = DETAIL_SAMPLE_LIMIT) -> list[dict[str, Any]]:
    """Capped, explicitly non-representative diagnostic sample (per symbol)."""
    sample: list[dict[str, Any]] = []
    for metric in metrics:
        if len(sample) >= limit:
            break
        sample.append(
            {
                "symbol": metric.symbol,
                "period": metric.period,
                "time": metric.time.isoformat(sep=" "),
                "direction": metric.direction,
                "gap_pips": round(metric.gap_pips, 4),
                "gap_minutes": round(metric.gap_minutes, 2),
                "entry_m1_count": metric.entry_m1_count,
                "previous_m1_count": metric.previous_m1_count,
                "fade_reason": metric.fade_reason,
                "fade_offset_bars": metric.fade_offset,
                "fade_ambiguous": metric.fade_ambiguous,
                "continuation_reason": metric.cont_reason,
                "mfe_pips": round(metric.mfe_pips, 4),
                "control_status": metric.control_status,
            }
        )
    return sample


def sample_trades(trades: Sequence[StageBTrade], limit: int = TRADE_SAMPLE_LIMIT) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for trade in trades:
        if len(sample) >= limit:
            break
        sample.append(
            {
                "symbol": trade.symbol,
                "period": trade.period,
                "threshold": trade.threshold,
                "cost_scale": trade.cost_scale,
                "arm": trade.arm,
                "direction": trade.direction,
                "entry_time": trade.entry_time.isoformat(sep=" "),
                "entry": trade.entry,
                "stop": trade.stop,
                "target": trade.target,
                "risk": trade.risk,
                "exit_time": trade.exit_time.isoformat(sep=" "),
                "exit": trade.exit,
                "net_r": round(trade.net_r, 6),
                "reason": trade.reason,
                "net_r_reason": trade.period_end_cause or trade.reason,
                "ambiguous": trade.ambiguous,
                "bars_held": trade.bars_held,
            }
        )
    return sample


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage A population/fill-first aggregation for gap_fill_m5_20261019. "
            "Stage B (RR1 execution) requires the explicit --stage-b flag."
        )
    )
    parser.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--symbols", nargs="+", default=list(SYMBOLS), choices=list(SYMBOLS))
    parser.add_argument("--periods", nargs="+", default=list(PERIOD_NAMES), choices=list(PERIOD_NAMES))
    parser.add_argument(
        "--thresholds", nargs="+", type=float, default=list(CLAIMED_THRESHOLDS),
        help=f"gap thresholds in pips; only {CLAIMED_THRESHOLDS} are declared",
    )
    parser.add_argument(
        "--cost-scales", nargs="+", type=float, default=list(CLAIMED_COST_SCALES),
        help=f"spread multipliers; only {CLAIMED_COST_SCALES} are declared",
    )
    parser.add_argument(
        "--stage-b", action="store_true",
        help="additionally run the Stage B RR1 execution simulation (explicit opt-in)",
    )
    parser.add_argument(
        "--allow-unfrozen", action="store_true",
        help="bypass the frozen_at guard (development only; never for evidence runs)",
    )
    parser.add_argument(
        "--load-start", default=None,
        help="first M1 date to load; default is the start of the first declared period",
    )
    parser.add_argument(
        "--load-end", default=None,
        help="last M1 date to load (inclusive); default is the end of the last declared period",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        protocol = read_protocol()
        specs = parse_periods(protocol)
        validate_protocol_against_code(protocol, specs)
        validate_grid(args.thresholds, args.cost_scales, args.periods, args.symbols)
        guard_frozen(protocol, args.allow_unfrozen)
    except ProtocolViolation as exc:
        print(f"[gap_fill_m5] PROTOCOL GUARD: {exc}", file=sys.stderr)
        return 2

    output_dir = Path(args.output)
    if output_dir.exists():
        print(f"[gap_fill_m5] output already exists: {output_dir}", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True)

    declared_windows = period_windows(specs)
    load_start = (
        datetime.fromisoformat(args.load_start)
        if args.load_start
        else declared_windows[0][1]
    )
    load_end = (
        datetime.fromisoformat(args.load_end) + timedelta(hours=23, minutes=59, seconds=59)
        if args.load_end
        else declared_windows[-1][2]
    )

    log_lines: list[str] = []
    started = time.perf_counter()

    def log(message: str) -> None:
        line = f"[gap_fill_m5] {message}"
        print(line, flush=True)
        log_lines.append(line)

    log(f"experiment={EXPERIMENT_ID} stage={'A+B' if args.stage_b else 'A'}")
    log(f"protocol status={protocol.get('status')} frozen_at={protocol.get('frozen_at')}")
    log(
        "thresholds="
        + ",".join(f"{value:g}" for value in args.thresholds)
        + " cost_scales="
        + ",".join(f"{value:g}" for value in args.cost_scales)
        + " periods="
        + ",".join(args.periods)
    )
    log(f"load window {load_start.isoformat(sep=' ')} .. {load_end.isoformat(sep=' ')}")
    for name, start, end in declared_windows:
        log(f"declared period {name}: {start.isoformat(sep=' ')} .. {end.isoformat(sep=' ')}")

    repository = HistoryRepository(args.history_dir)
    metrics_by_symbol: dict[str, list[EventMetric]] = {}
    trades_by_symbol: dict[str, list[StageBTrade]] = {}
    data_fingerprints: dict[str, Any] = {}
    window_filter = set(args.periods)

    for symbol in args.symbols:
        symbol_started = time.perf_counter()
        series = load_m5_series(repository, symbol, load_start, load_end)
        windows = tuple(
            window for window in build_period_windows(series, specs) if window.name in window_filter
        )
        events = find_gap_events(series)
        control_index = ControlIndex(series, [event.index for event in events])
        metrics = build_event_metrics(series, events, windows, control_index)
        metrics_by_symbol[symbol] = metrics
        partial = sum(event.entry_partial for event in events)
        interior = sum(event.gap_minutes <= 1440 for event in events)
        data_fingerprints[symbol] = {
            "bars_dat_sha256": stream_sha256(Path(args.history_dir) / symbol / "Bars.dat"),
            "info_dat_sha256": stream_sha256(Path(args.history_dir) / symbol / "info.dat"),
            "m5_series_sha256": series_sha256(series),
            "decimals": series.decimals,
            "pip_price": series.pip,
            "spread_price": series.spread_price,
            "spread_pips": series.spread_pips,
            "m1_bars": series.m1_bars,
            "m5_bars": series.size,
            "m5_partial_buckets": int(np.sum(series.m1_count < 5)),
            "m1_first_time": series.first_m1_time.isoformat(sep=" ") if series.first_m1_time else None,
            "m1_last_time": series.last_m1_time.isoformat(sep=" ") if series.last_m1_time else None,
            "gap_events": len(events),
            "gap_events_partial_entry_bar": partial,
            "gap_events_within_24h": interior,
            "period_bar_counts": {
                window.name: max(window.last_index - window.first_index + 1, 0) for window in windows
            },
        }
        if args.stage_b:
            window_by_name = {window.name: window for window in windows}
            symbol_trades: list[StageBTrade] = []
            for threshold in args.thresholds:
                selected = [metric for metric in metrics if meets_threshold(metric.gap_pips, threshold)]
                for cost_scale in args.cost_scales:
                    for name in args.periods:
                        window = window_by_name[name]
                        for arm in ("fade", "continuation"):
                            symbol_trades.extend(
                                simulate_stage_b(
                                    series, selected, window, threshold, cost_scale, arm
                                )
                            )
            trades_by_symbol[symbol] = symbol_trades
        symbol_seconds = time.perf_counter() - symbol_started
        log(
            f"{symbol}: m1={series.m1_bars} m5={series.size} "
            f"partial_buckets={int(np.sum(series.m1_count < 5))} gaps={len(events)} "
            f"metrics={len(metrics)} partial_entry_gaps={partial} in {symbol_seconds:.1f}s"
        )
        del series

    stage_a = build_stage_a_summary(
        [metric for metrics in metrics_by_symbol.values() for metric in metrics],
        args.thresholds,
        args.symbols,
    )
    stage_a["note"] = (
        "Partial M5 buckets are kept as bars (never interpolated). "
        "robustness_entry_bar_completeness splits the same population and is not "
        "used by any acceptance gate."
    )
    write_json(output_dir / "stage_a_summary.json", stage_a)
    write_json(
        output_dir / "stage_a_sample.json",
        {
            "non_representative_diagnostic_sample": True,
            "sample_limit_per_symbol": DETAIL_SAMPLE_LIMIT,
            "by_symbol": {
                symbol: sample_metrics(metrics) for symbol, metrics in metrics_by_symbol.items()
            },
        },
    )

    stage_b_payload: dict[str, Any]
    if args.stage_b:
        stage_b_payload = build_stage_b_summary(
            trades_by_symbol, args.thresholds, args.cost_scales, args.symbols
        )
        write_json(output_dir / "stage_b_summary.json", stage_b_payload)
        write_json(
            output_dir / "stage_b_sample.json",
            {
                "non_representative_diagnostic_sample": True,
                "sample_limit_per_symbol": TRADE_SAMPLE_LIMIT,
                "by_symbol": {
                    symbol: sample_trades(trades) for symbol, trades in trades_by_symbol.items()
                },
            },
        )
    else:
        stage_b_payload = {
            "not_run": True,
            "reason": "Stage B requires the explicit --stage-b flag (protocol Stage A gate first).",
        }

    elapsed = time.perf_counter() - started
    log(f"total elapsed {elapsed:.1f}s")
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "A+B" if args.stage_b else "A",
        "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "elapsed_seconds": round(elapsed, 3),
        "protocol_path": str(PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_status": protocol.get("status"),
        "protocol_frozen_at": protocol.get("frozen_at"),
        "declared_periods": {
            spec.name: {"start": spec.start_date, "end": spec.end_date} for spec in specs
        },
        "parameters": {
            "symbols": args.symbols,
            "periods": args.periods,
            "thresholds_pips": args.thresholds,
            "cost_scales": args.cost_scales,
            "stage_b": bool(args.stage_b),
            "gap_minutes": GAP_MINUTES,
            "max_holding_bars": MAX_HOLDING_BARS,
            "slippage_pips": SLIPPAGE_PIPS,
            "reward_risk": 1.0,
            "load_start": load_start.isoformat(sep=" "),
            "load_end": load_end.isoformat(sep=" "),
        },
        "determinism": "no randomness; identical inputs produce identical outputs",
        "detail_policy": (
            "Full per-event and per-trade detail is deliberately not persisted. Only "
            "aggregates, quantiles and a capped diagnostic sample are written; "
            "stage_a_sample.json / stage_b_sample.json are not representative."
        ),
        "code_sha256": {
            "scripts/research_gap_fill_m5.py": stream_sha256(Path(__file__).resolve()),
            "tests/test_gap_fill_m5.py": stream_sha256(ROOT / "tests" / "test_gap_fill_m5.py"),
            "docs/quant_organization/experiments/gap_fill_m5_20261019/protocol.json": stream_sha256(PROTOCOL_PATH),
        },
        "input_sha256": data_fingerprints,
        "counts": {
            "gap_events_by_symbol": {
                symbol: len(metrics) for symbol, metrics in metrics_by_symbol.items()
            },
            "gap_events_total": sum(len(metrics) for metrics in metrics_by_symbol.values()),
            "stage_a_events_total": sum(
                metrics["events"]
                for metrics in (
                    stage_a["pooled_all_periods"][threshold_key(x)] for x in args.thresholds
                )
            ),
            "stage_b_trades_total": (
                sum(len(trades) for trades in trades_by_symbol.values()) if args.stage_b else 0
            ),
        },
        "gate_evaluation_stage_a": stage_a["gate_evaluation"],
        "gate_evaluation_stage_b": stage_b_payload.get("gate_evaluation", {"status": "not_run"}),
        "log": log_lines,
    }
    write_json(output_dir / "run_manifest.json", manifest)
    print(f"[gap_fill_m5] wrote {output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
