"""Independent validator for experiment ``gap_fill_m5_20261019`` (Stage A only).

Written by the independent-verification role (quant_validator).  This file is a
**separate implementation** from ``scripts/research_gap_fill_m5.py``: that module
is deliberately never imported.  The only shared component is
``forextester_backtest.data.HistoryRepository`` for read-only raw bars (plus the
raw-record epoch constant ``OLE_EPOCH``).

What is recomputed, straight from the frozen protocol
(``docs/quant_organization/experiments/gap_fill_m5_20261019/protocol.json``):

1.  M1 -> M5 aggregation on absolute 300-second OLE buckets.  Partial buckets
    (fewer than five M1 bars) are kept as one bar; bucket-start time; open is the
    first M1 open.  Implemented with a vectorised bucket/reduceat algorithm, i.e.
    not the sequential accumulation the research script uses.
2.  Gap detection: first M5 bar whose bucket-start differs from the previous
    bucket by >= 120 minutes.  Width = |open - previous close| / pip, with
    pip = 0.0001 for decimals=5 and 0.01 for decimals=3.
3.  Fade direction (open > previous close -> sell, open < previous close -> buy).
4.  Full-fill target = previous bar close; stop = open -/+ gap width.  Walk up to
    48 M5 bars on high/low; a bar that reaches both barriers counts as a stop and
    sets ambiguous=true; an opening already beyond a barrier gives
    target_gap / stop_gap.  Continuation arm mirrors direction on the same event.
5.  Thresholds X = 10.0 and 25.0 pips with a 1e-9 pip tolerance so "exactly X"
    is adopted (frozen convention).
6.  Periods training / validation / final_confirmation exactly as declared.
7.  Per-symbol, per-period and pooled counts, fill-first ratios, stop-first
    ratios, ambiguous counts/ratios, 25/50/75/100 % partial-fill reach ratios and
    the same for the continuation arm.
8.  Frozen acceptance gates re-evaluated mechanically.  The numeric criteria are
    *parsed out of the frozen protocol strings*; if parsing fails the gate is
    reported as not evaluated instead of being guessed.
9.  Field-by-field comparison against the research output
    (``agent_runs/gap_fill_m5_20261019/stage_a/stage_a_summary.json`` and
    ``run_manifest.json``) with absolute and relative differences.
10. Data gate: SHA256 of the eleven ``Bars.dat`` files vs ``data_inventory.md``
    and vs the research ``run_manifest.json``.

Stage B is never executed here: the frozen Stage A population/fill-first gates
are re-evaluated first and the protocol does not allow Stage B before they pass.

Read-only with respect to ``C:\\ForexTester6``.  No orders, no network, no git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np

from forextester_backtest.data import OLE_EPOCH, HistoryRepository

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "gap_fill_m5_20261019"
EXPERIMENT_DIR = ROOT / "docs" / "quant_organization" / "experiments" / EXPERIMENT_ID
PROTOCOL_PATH = EXPERIMENT_DIR / "protocol.json"
DATA_INVENTORY_PATH = EXPERIMENT_DIR / "data_inventory.md"
RESEARCH_STAGE_A_DIR = ROOT / "agent_runs" / EXPERIMENT_ID / "stage_a"
RESEARCH_SUMMARY_PATH = RESEARCH_STAGE_A_DIR / "stage_a_summary.json"
RESEARCH_MANIFEST_PATH = RESEARCH_STAGE_A_DIR / "run_manifest.json"
# The researcher re-ran the same frozen specification into a second directory after
# fixing the non-gate control-block matching (see docs/gap_fill_m5_20261019.md §10.3).
# Both are compared so the gate-relevant equality claim is verified, not assumed.
RESEARCH_ALT_DIRS = (ROOT / "agent_runs" / EXPERIMENT_ID / "stage_a_v2",)
RESEARCH_LEDGER_PATH = ROOT / "agent_runs" / EXPERIMENT_ID / "data_ledger.json"
DEFAULT_OUTPUT_DIR = ROOT / "agent_runs" / EXPERIMENT_ID / "validation"
DEFAULT_HISTORY_DIR = r"C:\ForexTester6\data\History"

PERIOD_ORDER = ("training", "validation", "final_confirmation")
THRESHOLDS = (10.0, 25.0)
M5_SECONDS = 300
GAP_MIN_SECONDS = 120 * 60
MAX_HOLDING_BARS = 48
THRESHOLD_TOLERANCE_PIPS = 1e-9
PARTIAL_LEVELS = (0.25, 0.50, 0.75, 1.0)
QUANTILE_POINTS = (0.10, 0.25, 0.50, 0.75, 0.90)
M1_CHUNK = 200_000
FLOAT_EQ_REL = 1e-12
MISMATCH_REL = 1e-9

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
SHA_RE = re.compile(r"\b([0-9a-f]{64})\b")


class ValidationError(RuntimeError):
    """Raised when the frozen inputs are missing or inconsistent."""


# ---------------------------------------------------------------------------
# Protocol / ledger input
# ---------------------------------------------------------------------------

def guard_frozen(protocol: dict[str, Any]) -> None:
    """Refuse to produce a verdict unless the specification is frozen.

    The validator's contract is that a frozen hypothesis, code identifier, data
    ledger and pre-declared criteria are the input; when any of that is missing
    the result must be "not verified" rather than a verdict.
    """
    if protocol.get("status") != "SPEC_FROZEN" or not protocol.get("frozen_at"):
        raise ValidationError(
            "protocol.json is not frozen "
            f"(status={protocol.get('status')!r}, frozen_at={protocol.get('frozen_at')!r}); "
            "an independent verdict must not be produced"
        )


def code_identity(research_manifest: dict[str, Any]) -> dict[str, Any]:
    """Hash the frozen code identifiers and compare with the research manifest.

    This proves the research artifact compared against is the one that produced
    the stored evidence, and that the frozen inputs have not moved since.
    """
    declared = research_manifest.get("code_sha256") or {}
    rows: list[dict[str, Any]] = []
    for relative, expected in declared.items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else None
        rows.append(
            {
                "file": relative,
                "manifest_sha256": expected,
                "validator_sha256": actual,
                "status": "match" if actual == expected else "mismatch",
            }
        )
    return {
        "rows": rows,
        "all_match": bool(rows) and all(row["status"] == "match" for row in rows),
    }


def load_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise ValidationError(f"protocol.json not found: {PROTOCOL_PATH}")
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def parse_periods(protocol: dict[str, Any]) -> list[tuple[str, datetime, datetime]]:
    """Inclusive datetime windows for the declared periods (own parser)."""
    raw = protocol.get("periods")
    if not isinstance(raw, dict):
        raise ValidationError("protocol.periods is missing")
    windows: list[tuple[str, datetime, datetime]] = []
    for name in PERIOD_ORDER:
        text = raw.get(name)
        if not isinstance(text, str):
            raise ValidationError(f"protocol.periods[{name!r}] is missing")
        dates = DATE_RE.findall(text)
        if len(dates) != 2:
            raise ValidationError(f"protocol.periods[{name!r}] = {text!r} has no date range")
        start = datetime.fromisoformat(dates[0])
        end = datetime.fromisoformat(dates[1]) + timedelta(hours=23, minutes=59, seconds=59)
        windows.append((name, start, end))
    return windows


def pip_size(decimals: int) -> float:
    """One pip from stored decimals: 5 -> 0.0001, 3 -> 0.01 (protocol)."""
    if decimals == 5:
        return 0.0001
    if decimals == 3:
        return 0.01
    raise ValidationError(f"unsupported decimals={decimals}; protocol declares 3 or 5")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_inventory_hashes(path: Path) -> tuple[dict[str, str], list[str]]:
    """Bars.dat SHA256 per symbol from the data-inventory markdown table."""
    if not path.is_file():
        raise ValidationError(f"data inventory not found: {path}")
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        symbol = cells[0]
        match = SHA_RE.search(cells[-1])
        if re.fullmatch(r"[A-Z]{6}", symbol) and match:
            found[symbol] = match.group(1)
    return found, sorted(found)


# ---------------------------------------------------------------------------
# Raw M1 read and independent M5 aggregation
# ---------------------------------------------------------------------------

def _whole_seconds(moment: datetime) -> int:
    """Whole OLE seconds, refusing sub-second stamps (as the frozen rule does)."""
    delta = moment - OLE_EPOCH
    if delta.microseconds:
        raise ValidationError(f"non whole-second M1 timestamp: {moment.isoformat()}")
    return delta.days * 86_400 + delta.seconds


def _chunks(iterator: Iterator[Any], size: int) -> Iterator[list[Any]]:
    while True:
        batch = [bar for _, bar in zip(range(size), iterator)]
        if not batch:
            return
        yield batch


def read_m1_arrays(
    repository: HistoryRepository,
    symbol: str,
    start: datetime,
    end: datetime,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Read stored M1 and return (epoch_seconds, open, high, low, close)."""
    epoch_parts: list[np.ndarray] = []
    open_parts: list[np.ndarray] = []
    high_parts: list[np.ndarray] = []
    low_parts: list[np.ndarray] = []
    close_parts: list[np.ndarray] = []
    for batch in _chunks(repository.bars(symbol, start, end, "1m"), M1_CHUNK):
        count = len(batch)
        epoch_parts.append(
            np.fromiter((_whole_seconds(bar.time) for bar in batch), dtype=np.int64, count=count)
        )
        open_parts.append(np.fromiter((bar.open for bar in batch), dtype=np.float64, count=count))
        high_parts.append(np.fromiter((bar.high for bar in batch), dtype=np.float64, count=count))
        low_parts.append(np.fromiter((bar.low for bar in batch), dtype=np.float64, count=count))
        close_parts.append(np.fromiter((bar.close for bar in batch), dtype=np.float64, count=count))
    if not epoch_parts:
        empty = np.empty(0, dtype=np.float64)
        return np.empty(0, dtype=np.int64), empty, empty, empty, empty
    epoch = np.concatenate(epoch_parts)
    return (
        epoch,
        np.concatenate(open_parts),
        np.concatenate(high_parts),
        np.concatenate(low_parts),
        np.concatenate(close_parts),
    )


def aggregate_m5(
    epoch: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised absolute-bucket M5 aggregation.

    Bucket = floor(OLE second / 300).  Bucket-start time, first M1 open,
    max high, min low, last M1 close, constituent M1 count.  Partial buckets are
    kept: a bucket with one M1 bar stays a bar with count 1.
    """
    if epoch.size == 0:
        empty_i = np.empty(0, dtype=np.int64)
        empty_f = np.empty(0, dtype=np.float64)
        return empty_i, empty_f, empty_f, empty_f, empty_f, np.empty(0, dtype=np.int64)
    bucket = epoch // M5_SECONDS
    if np.any(np.diff(bucket) < 0):
        raise ValidationError("M1 timestamps are not non-decreasing")
    is_start = np.empty(bucket.size, dtype=bool)
    is_start[0] = True
    np.not_equal(bucket[1:], bucket[:-1], out=is_start[1:])
    starts = np.flatnonzero(is_start)
    counts = np.diff(np.append(starts, bucket.size))
    bucket_epoch = bucket[starts] * M5_SECONDS
    if np.any(np.diff(bucket_epoch) <= 0):
        raise ValidationError("aggregated M5 timestamps are not strictly increasing")
    last_index = np.append(starts[1:], bucket.size) - 1
    m5 = (
        bucket_epoch.astype(np.int64),
        open_[starts].copy(),
        np.maximum.reduceat(high, starts).copy(),
        np.minimum.reduceat(low, starts).copy(),
        close[last_index].copy(),
        counts.astype(np.int64),
    )
    if np.any(m5[1] <= 0) or np.any(m5[2] < m5[3]):
        raise ValidationError("aggregated M5 prices are invalid")
    if np.any(m5[2] < np.maximum(m5[1], m5[4])) or np.any(m5[3] > np.minimum(m5[1], m5[4])):
        raise ValidationError("aggregated M5 OHLC is inconsistent")
    if np.any(m5[5] < 1):
        raise ValidationError("aggregated M5 bucket has no M1 bars")
    return m5


def series_fingerprint(
    epoch: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    counts: np.ndarray,
) -> str:
    """Canonical column fingerprint.

    This is a comparison device only: the research manifest stores the same
    canonical serialisation of *its* M5 columns, so an identical digest proves the
    two aggregations agree bar-by-bar and not merely at rounded precision.  No
    research code is imported; the digest is computed from this script's own
    arrays.
    """
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(epoch, dtype="<i8").tobytes())
    for column in (open_, high, low, close):
        digest.update(np.ascontiguousarray(column, dtype="<f8").tobytes())
    digest.update(np.ascontiguousarray(counts, dtype="<i4").tobytes())
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Gap detection and barrier race
# ---------------------------------------------------------------------------

def find_gaps(
    m5_epoch: np.ndarray,
    m5_open: np.ndarray,
    m5_close: np.ndarray,
    pip: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Gap bars after a >= 120 minute discontinuity.

    Returns (index, gap_pips, gap_minutes, fade_direction).
    """
    if m5_epoch.size < 2:
        empty_i = np.empty(0, dtype=np.int64)
        empty_f = np.empty(0, dtype=np.float64)
        return empty_i, empty_f, empty_f, empty_i
    delta = np.diff(m5_epoch)
    index = np.flatnonzero(delta >= GAP_MIN_SECONDS) + 1
    previous_close = m5_close[index - 1]
    gap_price = np.abs(m5_open[index] - previous_close)
    gap_pips = gap_price / pip
    # Fade: sell the gap up (open > previous close -> -1), buy the gap down.
    direction = np.where(m5_open[index] > previous_close, -1, 1).astype(np.int64)
    gap_minutes = delta[index - 1].astype(np.float64) / 60.0
    return index.astype(np.int64), gap_pips, gap_minutes, direction


def classify_race(
    m5_open: np.ndarray,
    m5_high: np.ndarray,
    m5_low: np.ndarray,
    index: int,
    direction: int,
    gap_price: float,
    last_index: int,
) -> tuple[str, int, bool, bool]:
    """First barrier reached from ``index`` within 48 M5 bars.

    Reason order per bar follows the frozen rule: an opening beyond a barrier is
    settled first (stop before target), then same-bar touches with the stop
    taking priority, then the period boundary.

    Returns (reason, bar_offset, ambiguous, window_truncated).
    """
    if direction not in (-1, 1):
        raise ValidationError("direction must be -1 or 1")
    stop_level = m5_open[index] - direction * gap_price
    target_level = m5_open[index] + direction * gap_price
    last = min(index + MAX_HOLDING_BARS - 1, last_index)
    if last < index:
        raise ValidationError(f"empty holding window at index {index}")
    truncated = (index + MAX_HOLDING_BARS - 1) > last_index
    window = slice(index, last + 1)
    openings = m5_open[window]
    if direction == 1:
        gap_stop_hits = np.flatnonzero(openings <= stop_level)
        gap_target_hits = np.flatnonzero(openings >= target_level)
        hit_stop = m5_low[window] <= stop_level
        hit_target = m5_high[window] >= target_level
    else:
        gap_stop_hits = np.flatnonzero(openings >= stop_level)
        gap_target_hits = np.flatnonzero(openings <= target_level)
        hit_stop = m5_high[window] >= stop_level
        hit_target = m5_low[window] <= target_level
    gap_bar: int | None = None
    gap_reason: str | None = None
    first_stop_gap = int(gap_stop_hits[0]) if gap_stop_hits.size else None
    first_target_gap = int(gap_target_hits[0]) if gap_target_hits.size else None
    if first_stop_gap is not None and (first_target_gap is None or first_stop_gap <= first_target_gap):
        gap_bar, gap_reason = first_stop_gap, "stop_gap"
    elif first_target_gap is not None:
        gap_bar, gap_reason = first_target_gap, "target_gap"
    touches = hit_stop | hit_target
    touch_bars = np.flatnonzero(touches)
    first_touch = int(touch_bars[0]) if touch_bars.size else None
    if gap_bar is not None and (first_touch is None or gap_bar <= first_touch):
        return gap_reason, gap_bar, False, truncated
    if first_touch is None:
        return "none", -1, False, truncated
    if hit_stop[first_touch] and hit_target[first_touch]:
        return "stop", first_touch, True, truncated
    if hit_stop[first_touch]:
        return "stop", first_touch, False, truncated
    return "target", first_touch, False, truncated


def directional_excursion(
    m5_open: np.ndarray,
    m5_high: np.ndarray,
    m5_low: np.ndarray,
    index: int,
    direction: int,
    gap_price: float,
    last_index: int,
) -> tuple[float, float, tuple[bool, ...], bool]:
    """Maximum favourable excursion in ``direction``, stop ignored.

    Returns (mfe_price, mfe/gap, reached-at-25/50/75/100 %, truncated).
    """
    last = min(index + MAX_HOLDING_BARS - 1, last_index)
    if last < index:
        raise ValidationError(f"empty excursion window at index {index}")
    window = slice(index, last + 1)
    entry = m5_open[index]
    window_high = float(np.max(m5_high[window]))
    window_low = float(np.min(m5_low[window]))
    if direction == 1:
        mfe = window_high - entry
        reached = tuple(bool(window_high >= entry + gap_price * level) for level in PARTIAL_LEVELS)
    else:
        mfe = entry - window_low
        reached = tuple(bool(window_low <= entry - gap_price * level) for level in PARTIAL_LEVELS)
    fraction = mfe / gap_price if gap_price > 0 else 0.0
    return float(mfe), float(fraction), reached, (index + MAX_HOLDING_BARS - 1) > last_index


# ---------------------------------------------------------------------------
# Per-symbol analysis
# ---------------------------------------------------------------------------

def analyse_symbol(
    repository: HistoryRepository,
    symbol: str,
    windows: Sequence[tuple[str, datetime, datetime]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recompute every Stage A metric for one symbol."""
    started = time.perf_counter()
    metadata = repository.metadata(symbol)
    pip = pip_size(metadata.decimals)
    load_start = windows[0][1]
    load_end = windows[-1][2]
    m1_epoch, m1_open, m1_high, m1_low, m1_close = read_m1_arrays(
        repository, symbol, load_start, load_end
    )
    m1_first_epoch = int(m1_epoch[0]) if m1_epoch.size else None
    m1_last_epoch = int(m1_epoch[-1]) if m1_epoch.size else None
    m5_epoch, m5_open, m5_high, m5_low, m5_close, m5_count = aggregate_m5(
        m1_epoch, m1_open, m1_high, m1_low, m1_close
    )
    del m1_epoch, m1_open, m1_high, m1_low, m1_close

    index, gap_pips, gap_minutes, direction = find_gaps(m5_epoch, m5_open, m5_close, pip)

    period_bounds: dict[str, tuple[int, int, int, int]] = {}
    for name, start, end in windows:
        start_epoch = int((start - OLE_EPOCH).total_seconds())
        end_epoch = int((end - OLE_EPOCH).total_seconds())
        first = int(np.searchsorted(m5_epoch, start_epoch, side="left"))
        last = int(np.searchsorted(m5_epoch, end_epoch, side="right")) - 1
        period_bounds[name] = (start_epoch, end_epoch, first, last)

    records: list[dict[str, Any]] = []
    for position in range(index.size):
        bar = int(index[position])
        epoch = int(m5_epoch[bar])
        window_name: str | None = None
        for name, start, end in windows:
            start_epoch = int((start - OLE_EPOCH).total_seconds())
            end_epoch = int((end - OLE_EPOCH).total_seconds())
            if start_epoch <= epoch <= end_epoch:
                window_name = name
                break
        if window_name is None:
            continue
        period_last = period_bounds[window_name][3]
        gap_price = float(gap_pips[position] * pip)
        fade_direction = int(direction[position])
        fade_reason, fade_offset, fade_ambiguous, fade_truncated = classify_race(
            m5_open, m5_high, m5_low, bar, fade_direction, gap_price, period_last
        )
        cont_reason, cont_offset, cont_ambiguous, cont_truncated = classify_race(
            m5_open, m5_high, m5_low, bar, -fade_direction, gap_price, period_last
        )
        mfe, fraction, reached, excursion_truncated = directional_excursion(
            m5_open, m5_high, m5_low, bar, fade_direction, gap_price, period_last
        )
        cont_mfe, cont_fraction, cont_reached, cont_excursion_truncated = directional_excursion(
            m5_open, m5_high, m5_low, bar, -fade_direction, gap_price, period_last
        )
        records.append(
            {
                "symbol": symbol,
                "period": window_name,
                "index": bar,
                "time": (OLE_EPOCH + timedelta(seconds=epoch)).isoformat(sep=" "),
                "gap_pips": float(gap_pips[position]),
                "gap_minutes": float(gap_minutes[position]),
                "entry_m1_count": int(m5_count[bar]),
                "previous_m1_count": int(m5_count[bar - 1]),
                "fade_reason": fade_reason,
                "fade_offset": fade_offset,
                "fade_ambiguous": fade_ambiguous,
                "fade_truncated": fade_truncated,
                "cont_reason": cont_reason,
                "cont_offset": cont_offset,
                "cont_ambiguous": cont_ambiguous,
                "cont_truncated": cont_truncated,
                "mfe_pips": mfe / pip,
                "gap_fraction": fraction,
                "reached": reached,
                "excursion_truncated": excursion_truncated,
                "cont_mfe_pips": cont_mfe / pip,
                "cont_gap_fraction": cont_fraction,
                "cont_reached": cont_reached,
                "cont_excursion_truncated": cont_excursion_truncated,
            }
        )

    fingerprint = {
        "decimals": int(metadata.decimals),
        "pip_price": float(pip),
        "spread_price": float(metadata.spread_price),
        "spread_pips": float(metadata.spread_price) / pip,
        "m1_bars": int(m5_count.sum()),
        "m5_bars": int(m5_epoch.size),
        "m5_partial_buckets": int(np.sum(m5_count < 5)),
        "m1_first_time": (
            (OLE_EPOCH + timedelta(seconds=m1_first_epoch)).isoformat(sep=" ")
            if m1_first_epoch is not None
            else None
        ),
        "m1_last_time": (
            (OLE_EPOCH + timedelta(seconds=m1_last_epoch)).isoformat(sep=" ")
            if m1_last_epoch is not None
            else None
        ),
        "m5_first_time": (
            (OLE_EPOCH + timedelta(seconds=int(m5_epoch[0]))).isoformat(sep=" ")
            if m5_epoch.size
            else None
        ),
        "m5_last_time": (
            (OLE_EPOCH + timedelta(seconds=int(m5_epoch[-1]))).isoformat(sep=" ")
            if m5_epoch.size
            else None
        ),
        "m5_series_sha256": series_fingerprint(
            m5_epoch, m5_open, m5_high, m5_low, m5_close, m5_count
        ),
        "gap_events": int(index.size),
        "gap_events_partial_entry_bar": int(np.sum(m5_count[index] < 5)),
        "gap_events_within_24h": int(np.sum(gap_minutes <= 1440.0)),
        "period_bar_counts": {
            name: max(period_bounds[name][3] - period_bounds[name][2] + 1, 0)
            for name in PERIOD_ORDER
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    return records, fingerprint


# ---------------------------------------------------------------------------
# Summaries and frozen gates
# ---------------------------------------------------------------------------

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


def meets_threshold(gap_pips: float, threshold: float) -> bool:
    return gap_pips >= threshold - THRESHOLD_TOLERANCE_PIPS


def race_block(records: Sequence[dict[str, Any]], prefix: str) -> dict[str, Any]:
    reasons = [record[f"{prefix}_reason"] for record in records]
    total = len(records)
    target_first = sum(reason in ("target", "target_gap") for reason in reasons)
    stop_first = sum(reason in ("stop", "stop_gap") for reason in reasons)
    ambiguous = sum(
        bool(record[f"{prefix}_ambiguous"]) and reason in ("stop", "stop_gap")
        for record, reason in zip(records, reasons)
    )
    offsets = [
        int(record[f"{prefix}_offset"])
        for record, reason in zip(records, reasons)
        if reason in ("target", "target_gap") and int(record[f"{prefix}_offset"]) >= 0
    ]
    return {
        "events": total,
        "target_first": target_first,
        "target_first_ratio": ratio(target_first, total),
        "stop_first": stop_first,
        "stop_first_ratio": ratio(stop_first, total),
        "none": sum(reason == "none" for reason in reasons),
        "none_ratio": ratio(sum(reason == "none" for reason in reasons), total),
        "target_gap": sum(reason == "target_gap" for reason in reasons),
        "stop_gap": sum(reason == "stop_gap" for reason in reasons),
        "ambiguous": ambiguous,
        "ambiguous_ratio": ratio(ambiguous, total),
        "window_truncated": sum(bool(record[f"{prefix}_truncated"]) for record in records),
        "median_target_first_offset_bars": (
            float(np.median(np.asarray(offsets, dtype=np.float64))) if offsets else None
        ),
    }


def summarise_group(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    summary: dict[str, Any] = {
        "events": total,
        "entry_bar_partial_m1": sum(record["entry_m1_count"] < 5 for record in records),
        "previous_bar_partial_m1": sum(record["previous_m1_count"] < 5 for record in records),
        "gap_pips": quantiles([record["gap_pips"] for record in records]),
        "gap_minutes": quantiles([record["gap_minutes"] for record in records]),
        "gap_minutes_over_24h": sum(record["gap_minutes"] > 1440 for record in records),
    }
    summary["fade"] = race_block(records, "fade")
    reached_target = sum(record["reached"][-1] for record in records)
    fade = summary["fade"]
    fade["fill_reached_within_48"] = reached_target
    fade["fill_reached_ratio"] = ratio(reached_target, total)
    fade["partial_fill_reach_ratio"] = {
        f"{level:g}": ratio(sum(record["reached"][i] for record in records), total)
        for i, level in enumerate(PARTIAL_LEVELS)
    }
    fade["mfe_pips"] = quantiles([record["mfe_pips"] for record in records])
    fade["mfe_gap_fraction"] = quantiles([record["gap_fraction"] for record in records])
    fade["excursion_truncated"] = sum(record["excursion_truncated"] for record in records)
    summary["continuation"] = race_block(records, "cont")
    # Validator-added mirror statistics for the continuation arm (same distance
    # structure, opposite direction).  Descriptive only; no acceptance gate uses
    # them and the research output does not contain them.
    continuation = summary["continuation"]
    cont_reached_target = sum(record["cont_reached"][-1] for record in records)
    continuation["fill_reached_within_48"] = cont_reached_target
    continuation["fill_reached_ratio"] = ratio(cont_reached_target, total)
    continuation["partial_fill_reach_ratio"] = {
        f"{level:g}": ratio(sum(record["cont_reached"][i] for record in records), total)
        for i, level in enumerate(PARTIAL_LEVELS)
    }
    continuation["mfe_pips"] = quantiles([record["cont_mfe_pips"] for record in records])
    continuation["mfe_gap_fraction"] = quantiles([record["cont_gap_fraction"] for record in records])
    continuation["excursion_truncated"] = sum(
        record["cont_excursion_truncated"] for record in records
    )
    return summary


def threshold_key(threshold: float) -> str:
    return f"X{threshold:g}"


def build_summary(
    records: Sequence[dict[str, Any]],
    symbols: Sequence[str],
) -> dict[str, Any]:
    def for_threshold(threshold: float, subset: Sequence[dict[str, Any]]) -> dict[str, Any]:
        return summarise_group(
            [record for record in subset if meets_threshold(record["gap_pips"], threshold)]
        )

    summary: dict[str, Any] = {
        "pooled_all_periods": {threshold_key(x): for_threshold(x, records) for x in THRESHOLDS},
        "pooled_by_period": {
            name: {
                threshold_key(x): for_threshold(
                    x, [record for record in records if record["period"] == name]
                )
                for x in THRESHOLDS
            }
            for name in PERIOD_ORDER
        },
        "by_symbol": {
            symbol: {
                "all_periods": {
                    threshold_key(x): for_threshold(
                        x, [record for record in records if record["symbol"] == symbol]
                    )
                    for x in THRESHOLDS
                },
                "by_period": {
                    name: {
                        threshold_key(x): for_threshold(
                            x,
                            [
                                record
                                for record in records
                                if record["symbol"] == symbol and record["period"] == name
                            ],
                        )
                        for x in THRESHOLDS
                    }
                    for name in PERIOD_ORDER
                },
            }
            for symbol in symbols
        },
    }
    partial_entry = [record for record in records if record["entry_m1_count"] < 5]
    complete_entry = [record for record in records if record["entry_m1_count"] >= 5]
    summary["robustness_entry_bar_completeness"] = {
        "note": (
            "Validator recomputation. Robustness only; entry-bar M1 completeness splits "
            "the same population and is not used by any acceptance gate."
        ),
        "partial_entry_bar": {threshold_key(x): for_threshold(x, partial_entry) for x in THRESHOLDS},
        "complete_entry_bar": {
            threshold_key(x): for_threshold(x, complete_entry) for x in THRESHOLDS
        },
        "partial_entry_bar_events": len(partial_entry),
        "complete_entry_bar_events": len(complete_entry),
        # Validator addition (not present in the research output): the same split
        # inside each declared period, because the partial-bucket share changes
        # strongly between periods and would otherwise confound the pooled compare.
        "by_period": {
            name: {
                "partial_entry_bar": {
                    threshold_key(x): for_threshold(
                        x, [record for record in partial_entry if record["period"] == name]
                    )
                    for x in THRESHOLDS
                },
                "complete_entry_bar": {
                    threshold_key(x): for_threshold(
                        x, [record for record in complete_entry if record["period"] == name]
                    )
                    for x in THRESHOLDS
                },
                "partial_entry_bar_events": sum(
                    record["period"] == name for record in partial_entry
                ),
                "complete_entry_bar_events": sum(
                    record["period"] == name for record in complete_entry
                ),
            }
            for name in PERIOD_ORDER
        },
    }
    return summary


def fill_first_sensitivity(summary: dict[str, Any]) -> dict[str, Any]:
    """Denominator sensitivity of the fill-first ratio (descriptive, not a gate).

    The frozen sentence defines the numerator ("reached the previous close before
    the full-width stop") but not the denominator.  The applied criterion used by
    this validator - and by the research implementation - is the ratio over the
    whole population, including events that reach neither barrier inside 48 bars.
    Both alternatives are reported so the ambiguity cannot be resolved after the
    fact by picking whichever number passes.
    """
    rows: list[dict[str, Any]] = []
    scopes: list[tuple[str, dict[str, Any]]] = [("pooled_all_periods", summary["pooled_all_periods"])]
    scopes += [(name, summary["pooled_by_period"][name]) for name in PERIOD_ORDER]
    for scope, block in scopes:
        for threshold in THRESHOLDS:
            fade = block[threshold_key(threshold)]["fade"]
            total = fade["events"]
            target = fade["target_first"]
            stop = fade["stop_first"]
            none = fade["none"]
            rows.append(
                {
                    "scope": scope,
                    "threshold": threshold_key(threshold),
                    "events": total,
                    "applied_all_events": ratio(target, total),
                    "decided_only": ratio(target, target + stop),
                    "none_counted_as_fill": ratio(target + none, total),
                    "none_counted_as_stop_is_same_as_applied": True,
                }
            )
    return {
        "applied_criterion": "applied_all_events (population ratio, all events in the denominator)",
        "note": (
            "The frozen gate sentence fixes the numerator but not the denominator. "
            "Only 'applied_all_events' is used for the gate verdict; the other two "
            "readings are reported as a specification defect and must not be selected "
            "after seeing the result."
        ),
        "rows": rows,
    }


def parse_gate_criteria(protocol: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Extract the frozen numeric criteria from the protocol strings.

    Nothing is relaxed or reinterpreted: each number used below is read out of the
    frozen sentence with a targeted pattern.  A pattern that stops matching marks
    the gate as not evaluated rather than silently inventing a value.
    """
    gates = protocol.get("acceptance_gates")
    if not isinstance(gates, dict):
        return {}, ["protocol.acceptance_gates is missing"]
    problems: list[str] = []
    text_population = str(gates.get("stage_a_population", ""))
    text_fill = str(gates.get("stage_a_fill_first", ""))
    text_consistency = str(gates.get("stage_a_symbol_consistency", ""))

    def grab(pattern: str, text: str, name: str, cast: Any) -> Any:
        match = re.search(pattern, text)
        if match is None:
            problems.append(f"could not parse {name} from {text!r}")
            return None
        return cast(match.group(1))

    criteria = {
        "population_min_total": grab(r"合計(\d+)件以上", text_population, "population total", int),
        "population_min_per_period": grab(
            r"それぞれ(\d+)件以上", text_population, "population per period", int
        ),
        "population_min_per_symbol": grab(
            r"(\d+)件以上の通貨が", text_population, "population per symbol", int
        ),
        "population_min_symbols": grab(
            r"件以上の通貨が(\d+)つ以上", text_population, "population symbol count", int
        ),
        "fill_first_min_pooled": grab(
            r"pooledで([\d.]+)以上", text_fill, "fill-first pooled", float
        ),
        "fill_first_min_training_and_validation": grab(
            r"trainingとvalidationの両方で([\d.]+)以上", text_fill, "fill-first per period", float
        ),
        "consistency_min_ratio": grab(
            r"全埋め先行率([\d.]+)以上", text_consistency, "consistency ratio", float
        ),
        "consistency_min_symbols": grab(
            r"うち(\d+)通貨以上", text_consistency, "consistency symbol count", int
        ),
        "consistency_universe": grab(
            r"(\d+)通貨のうち", text_consistency, "consistency universe", int
        ),
        "same_bar_rule": (
            "same M5 bar reaching both barriers counts as a stop first and is "
            "reported as ambiguous"
        ),
        "raw_strings": {
            "stage_a_population": text_population,
            "stage_a_fill_first": text_fill,
            "stage_a_symbol_consistency": text_consistency,
            "stage_a_vs_baseline": str(gates.get("stage_a_vs_baseline", "")),
            "stage_a_data": str(gates.get("stage_a_data", "")),
        },
    }
    return criteria, problems


def evaluate_gates(
    summary: dict[str, Any],
    criteria: dict[str, Any],
    symbols: Sequence[str],
    data_gate: dict[str, Any],
) -> dict[str, Any]:
    primary = threshold_key(THRESHOLDS[0])
    pooled = summary["pooled_all_periods"][primary]
    per_period = {name: summary["pooled_by_period"][name][primary] for name in PERIOD_ORDER}
    per_symbol_events = {
        symbol: summary["by_symbol"][symbol]["all_periods"][primary]["events"] for symbol in symbols
    }
    per_symbol_ratio = {
        symbol: summary["by_symbol"][symbol]["all_periods"][primary]["fade"]["target_first_ratio"]
        for symbol in symbols
    }
    population = {
        "pooled_events": pooled["events"],
        "per_period_events": {name: per_period[name]["events"] for name in PERIOD_ORDER},
        "symbols_with_min_events": sorted(
            symbol
            for symbol, count in per_symbol_events.items()
            if count >= (criteria.get("population_min_per_symbol") or 0)
        ),
        "passed": bool(
            pooled["events"] >= (criteria.get("population_min_total") or 1 << 30)
            and all(
                per_period[name]["events"] >= (criteria.get("population_min_per_period") or 1 << 30)
                for name in PERIOD_ORDER
            )
            and sum(
                count >= (criteria.get("population_min_per_symbol") or 1 << 30)
                for count in per_symbol_events.values()
            )
            >= (criteria.get("population_min_symbols") or 1 << 30)
        ),
    }
    fill_first = {
        "pooled_all_periods_ratio": pooled["fade"]["target_first_ratio"],
        "training_ratio": per_period["training"]["fade"]["target_first_ratio"],
        "validation_ratio": per_period["validation"]["fade"]["target_first_ratio"],
        "passed": bool(
            (pooled["fade"]["target_first_ratio"] or 0.0)
            >= (criteria.get("fill_first_min_pooled") or 1 << 30)
            and all(
                (per_period[name]["fade"]["target_first_ratio"] or 0.0)
                >= (criteria.get("fill_first_min_training_and_validation") or 1 << 30)
                for name in ("training", "validation")
            )
        ),
    }
    consistency = {
        "symbols_at_or_above_threshold": sorted(
            symbol
            for symbol, value in per_symbol_ratio.items()
            if value is not None and value >= (criteria.get("consistency_min_ratio") or 2.0)
        ),
        "criterion": (
            f">= {criteria.get('consistency_min_symbols')} of "
            f"{criteria.get('consistency_universe')} symbols with all-period "
            f"fill-first ratio >= {criteria.get('consistency_min_ratio')}"
        ),
        "passed": bool(
            sum(
                value is not None and value >= (criteria.get("consistency_min_ratio") or 2.0)
                for value in per_symbol_ratio.values()
            )
            >= (criteria.get("consistency_min_symbols") or 1 << 30)
        ),
    }
    per_symbol_period_ratio = {
        symbol: {
            name: summary["by_symbol"][symbol]["by_period"][name][primary]["fade"][
                "target_first_ratio"
            ]
            for name in PERIOD_ORDER
        }
        for symbol in symbols
    }
    consistency["alternative_readings"] = {
        "note": (
            "The frozen sentence does not name a period for the per-symbol ratio. "
            "All plausible readings are reported; none reaches the required count."
        ),
        "training_only_symbols_at_or_above": sorted(
            symbol
            for symbol, values in per_symbol_period_ratio.items()
            if (values["training"] or 0.0) >= (criteria.get("consistency_min_ratio") or 2.0)
        ),
        "validation_only_symbols_at_or_above": sorted(
            symbol
            for symbol, values in per_symbol_period_ratio.items()
            if (values["validation"] or 0.0) >= (criteria.get("consistency_min_ratio") or 2.0)
        ),
        "final_only_symbols_at_or_above": sorted(
            symbol
            for symbol, values in per_symbol_period_ratio.items()
            if (values["final_confirmation"] or 0.0) >= (criteria.get("consistency_min_ratio") or 2.0)
        ),
        "all_three_periods_symbols_at_or_above": sorted(
            symbol
            for symbol, values in per_symbol_period_ratio.items()
            if all(
                (values[name] or 0.0) >= (criteria.get("consistency_min_ratio") or 2.0)
                for name in PERIOD_ORDER
            )
        ),
        "per_symbol_per_period_ratio": per_symbol_period_ratio,
    }
    baseline = {
        name: {
            "fade_target_first_ratio": per_period[name]["fade"]["target_first_ratio"],
            "continuation_target_first_ratio": per_period[name]["continuation"]["target_first_ratio"],
        }
        for name in ("training", "validation")
    }
    baseline["passed"] = bool(
        all(
            (baseline[name]["fade_target_first_ratio"] or 0.0)
            > (baseline[name]["continuation_target_first_ratio"] or 0.0)
            for name in ("training", "validation")
        )
    )
    return {
        "evaluated_by": "scripts/validate_gap_fill_m5.py (independent re-implementation)",
        "threshold": primary,
        "criteria_source": "protocol.json acceptance_gates strings (parsed, not relaxed)",
        "stage_a_population": population,
        "stage_a_fill_first": fill_first,
        "stage_a_symbol_consistency": consistency,
        "stage_a_vs_baseline": baseline,
        "stage_a_data": data_gate,
        "stage_a_overall_passed": bool(
            population["passed"]
            and fill_first["passed"]
            and consistency["passed"]
            and baseline["passed"]
            and data_gate.get("passed") is True
        ),
        "stage_b": {
            "status": "not_run",
            "reason": (
                "Frozen workflow: Stage A gates are evaluated first. This validator "
                "does not execute Stage B at all; post-cost PF, expectancy and drawdown "
                "are therefore unverified."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Comparison against the research output
# ---------------------------------------------------------------------------

def flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            flat.update(flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for position, value in enumerate(node):
            flat.update(flatten(value, f"{prefix}[{position}]"))
    else:
        flat[prefix] = node
    return flat


def compare_trees(mine: dict[str, Any], research: dict[str, Any], subset_run: bool) -> dict[str, Any]:
    my_flat = flatten(mine)
    their_flat = flatten(research)
    exact: list[str] = []
    near: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    not_recomputed: list[str] = []
    informational: list[str] = []
    subset_skipped: list[str] = []
    for path, their_value in their_flat.items():
        if path.rsplit(".", 1)[-1] == "note":
            informational.append(path)
            continue
        if path not in my_flat:
            not_recomputed.append(path)
            continue
        if subset_run and not path.startswith("by_symbol."):
            subset_skipped.append(path)
            continue
        my_value = my_flat[path]
        if isinstance(my_value, (int, float)) and isinstance(their_value, (int, float)):
            if my_value == their_value:
                exact.append(path)
                continue
            abs_diff = abs(float(my_value) - float(their_value))
            scale = abs(float(their_value))
            rel_diff = abs_diff / scale if scale else (0.0 if abs_diff == 0 else float("inf"))
            entry = {
                "path": path,
                "validator": float(my_value),
                "research": float(their_value),
                "abs_diff": abs_diff,
                "rel_diff": rel_diff,
            }
            if rel_diff <= FLOAT_EQ_REL or abs_diff <= FLOAT_EQ_REL:
                near.append(entry)
            else:
                entry["significant"] = rel_diff > MISMATCH_REL
                mismatches.append(entry)
        else:
            if my_value == their_value:
                exact.append(path)
            else:
                mismatches.append(
                    {"path": path, "validator": my_value, "research": their_value, "kind": "value"}
                )
    extra_in_validator = sorted(set(my_flat) - set(their_flat))
    return {
        "exact_matches": len(exact),
        "exact_match_paths": exact,
        "float_level_differences": near,
        "mismatches": mismatches,
        "significant_mismatches": [entry for entry in mismatches if entry.get("significant")],
        "paths_not_recomputed_by_validator": not_recomputed,
        "informational_note_paths_excluded": informational,
        "paths_skipped_subset_run": subset_skipped,
        "paths_only_in_validator": extra_in_validator,
    }


def compare_manifest(
    fingerprints: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    lookups = {
        "decimals": "decimals",
        "pip_price": "pip_price",
        "spread_price": "spread_price",
        "m1_bars": "m1_bars",
        "m5_bars": "m5_bars",
        "m5_partial_buckets": "m5_partial_buckets",
        "gap_events": "gap_events",
        "gap_events_partial_entry_bar": "gap_events_partial_entry_bar",
        "gap_events_within_24h": "gap_events_within_24h",
        "m5_series_sha256": "m5_series_sha256",
    }
    for symbol, theirs in (manifest.get("input_sha256") or {}).items():
        mine = fingerprints.get(symbol)
        if mine is None:
            rows.append({"symbol": symbol, "field": "*", "status": "not_recomputed"})
            continue
        for key, their_key in lookups.items():
            if key not in theirs:
                continue
            a, b = mine.get(key), theirs.get(their_key)
            status = "match" if a == b else "mismatch"
            rows.append({"symbol": symbol, "field": key, "validator": a, "research": b, "status": status})
        their_periods = theirs.get("period_bar_counts") or {}
        my_periods = mine.get("period_bar_counts") or {}
        for name, value in their_periods.items():
            a = my_periods.get(name)
            rows.append(
                {
                    "symbol": symbol,
                    "field": f"period_bar_counts.{name}",
                    "validator": a,
                    "research": value,
                    "status": "match" if a == value else "mismatch",
                }
            )
    mismatched = [row for row in rows if row["status"] == "mismatch"]
    return {
        "rows": rows,
        "match_count": sum(row["status"] == "match" for row in rows),
        "mismatch_count": len(mismatched),
        "mismatches": mismatched,
    }


def parse_inventory_symbol_period_table(path: Path) -> dict[str, list[dict[str, int]]]:
    """Per-symbol x per-period population table from the data ledger markdown.

    Row form: ``AUDUSD 386/201/75・267/56/12・257/88/23`` = (events, >=10.0 pips,
    >=25.0 pips) for training / validation / final_confirmation.  The ledger uses
    the raw float comparison (no 1e-9 tolerance), so this cross-checks the
    population independently of the research implementation.
    """
    if not path.is_file():
        return {}
    pattern = re.compile(
        r"([A-Z]{6})\s+(\d+)/(\d+)/(\d+)・(\d+)/(\d+)/(\d+)・(\d+)/(\d+)/(\d+)"
    )
    table: dict[str, list[dict[str, int]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        for match in pattern.finditer(line):
            symbol = match.group(1)
            numbers = [int(value) for value in match.groups()[1:]]
            table[symbol] = [
                {
                    "events": numbers[0],
                    "ge_10p0pips_raw": numbers[1],
                    "ge_25p0pips_raw": numbers[2],
                },
                {
                    "events": numbers[3],
                    "ge_10p0pips_raw": numbers[4],
                    "ge_25p0pips_raw": numbers[5],
                },
                {
                    "events": numbers[6],
                    "ge_10p0pips_raw": numbers[7],
                    "ge_25p0pips_raw": numbers[8],
                },
            ]
    return table


def ledger_crosscheck(
    records: Sequence[dict[str, Any]],
    symbols: Sequence[str],
    table: dict[str, list[dict[str, int]]],
) -> dict[str, Any]:
    """Third-source population check against the data ledger table."""
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        for position, name in enumerate(PERIOD_ORDER):
            subset = [
                record
                for record in records
                if record["symbol"] == symbol and record["period"] == name
            ]
            mine = {
                "events": len(subset),
                "ge_10p0pips_raw": sum(record["gap_pips"] >= 10.0 for record in subset),
                "ge_25p0pips_raw": sum(record["gap_pips"] >= 25.0 for record in subset),
            }
            theirs = (table.get(symbol) or [{}] * 3)[position]
            for field, my_value in mine.items():
                their_value = theirs.get(field)
                rows.append(
                    {
                        "symbol": symbol,
                        "period": name,
                        "field": field,
                        "validator": my_value,
                        "ledger": their_value,
                        "status": (
                            "match"
                            if their_value is not None and my_value == their_value
                            else ("not_available" if their_value is None else "mismatch")
                        ),
                    }
                )
    mismatches = [row for row in rows if row["status"] == "mismatch"]
    return {
        "source": str(DATA_INVENTORY_PATH.relative_to(ROOT)),
        "note": (
            "The ledger's per-symbol/per-period table uses the raw >= comparison "
            "(no 1e-9 tolerance), so this is an independent population check of gap "
            "detection, pip conversion and period membership."
        ),
        "rows": rows,
        "match_count": sum(row["status"] == "match" for row in rows),
        "not_available_count": sum(row["status"] == "not_available" for row in rows),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def research_target_consistency(targets: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Tree difference between stored research Stage A directories.

    The researcher's report claims the gate-relevant numbers are identical between
    the two runs and that only the non-gate control block changed.  That claim is
    checked here mechanically instead of being taken on trust.
    """
    if len(targets) < 2:
        return {
            "note": "only one research target present; nothing to cross-check",
            "pairs": [],
            "differing_paths": 0,
            "non_control_differing_paths": 0,
        }
    pairs: list[dict[str, Any]] = []
    for left, right in zip(targets, targets[1:]):
        left_flat = flatten(left["summary"])
        right_flat = flatten(right["summary"])
        differing = sorted(
            path
            for path in set(left_flat) | set(right_flat)
            if left_flat.get(path) != right_flat.get(path)
        )
        non_control = [path for path in differing if ".control." not in path]
        pairs.append(
            {
                "left": left["name"],
                "right": right["name"],
                "differing_paths": len(differing),
                "non_control_differing_paths": non_control,
                "non_control_differing_count": len(non_control),
                "differing_paths_under_control": sum(".control." in path for path in differing),
                "input_fingerprints_equal": (
                    left["manifest"].get("input_sha256") == right["manifest"].get("input_sha256")
                ),
                "gate_evaluation_equal": (
                    left["manifest"].get("gate_evaluation_stage_a")
                    == right["manifest"].get("gate_evaluation_stage_a")
                ),
            }
        )
    total = sum(pair["differing_paths"] for pair in pairs)
    non_control_total = sum(pair["non_control_differing_count"] for pair in pairs)
    return {
        "note": (
            "gate-relevant equality between the stored research runs is verified; "
            "differences are reported per path"
        ),
        "pairs": pairs,
        "differing_paths": total,
        "non_control_differing_paths": non_control_total,
    }


# ---------------------------------------------------------------------------
# Data gate
# ---------------------------------------------------------------------------

def data_gate(
    history_dir: Path,
    symbols: Sequence[str],
    inventory_hashes: dict[str, str],
    manifest: dict[str, Any],
    skip_hash: bool,
) -> dict[str, Any]:
    manifest_hashes = {
        symbol: entry.get("bars_dat_sha256")
        for symbol, entry in (manifest.get("input_sha256") or {}).items()
    }
    manifest_info = {
        symbol: entry.get("info_dat_sha256")
        for symbol, entry in (manifest.get("input_sha256") or {}).items()
    }
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        bars_path = history_dir / symbol / "Bars.dat"
        info_path = history_dir / symbol / "info.dat"
        if not bars_path.is_file():
            raise ValidationError(f"Bars.dat not found: {bars_path}")
        row: dict[str, Any] = {
            "symbol": symbol,
            "bars_dat_bytes": bars_path.stat().st_size,
            "inventory_sha256": inventory_hashes.get(symbol),
            "research_manifest_sha256": manifest_hashes.get(symbol),
            "validator_sha256": None if skip_hash else sha256_file(bars_path),
            "info_dat_validator_sha256": None if skip_hash else sha256_file(info_path),
            "info_dat_research_sha256": manifest_info.get(symbol),
        }
        checks = {
            "inventory_vs_validator": row["validator_sha256"] == row["inventory_sha256"],
            "manifest_vs_validator": row["validator_sha256"] == row["research_manifest_sha256"],
            "inventory_vs_manifest": row["inventory_sha256"] == row["research_manifest_sha256"],
            "info_dat_manifest_vs_validator": (
                row["info_dat_validator_sha256"] == row["info_dat_research_sha256"]
            ),
        }
        row["checks"] = checks
        row["passed"] = all(checks.values()) if not skip_hash else None
        rows.append(row)
    symbols_checked = [row for row in rows if row["validator_sha256"] is not None]
    return {
        "criterion": "input SHA256 matches data_inventory.md and no unresolved data problem",
        "source": "docs/quant_organization/experiments/gap_fill_m5_20261019/data_inventory.md",
        "rows": rows,
        "bars_dat_checked": len(symbols_checked),
        "bars_dat_all_match": bool(symbols_checked)
        and all(row["passed"] for row in symbols_checked),
        "inventory_symbols": sorted(inventory_hashes),
        "passed": bool(symbols_checked) and all(row["passed"] for row in symbols_checked),
        "quality_review": {
            "note": (
                "This validator re-reads every M1 record and the aggregation asserts finite "
                "prices, positive prices, consistent OHLC and strictly increasing bucket times. "
                "Duplicate/ordering problems would raise.  Volume is not used by this strategy, "
                "so the inventory's 41 negative and 20 zero volume records are out of scope."
            ),
            "assertions_enforced_in_this_run": [
                "M1 timestamps are whole seconds",
                "M1 bucket order is non-decreasing",
                "M5 bucket times are strictly increasing",
                "M5 OHLC consistent, prices positive (raises otherwise)",
            ],
        },
    }


# ---------------------------------------------------------------------------
# M5 aggregation equivalence cross-check
# ---------------------------------------------------------------------------

def aggregation_equivalence(
    repository: HistoryRepository,
    symbols: Sequence[str],
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    """Own aggregation vs ``HistoryRepository.bars(..., "5m")`` on a window.

    The window starts at midnight so that the library aggregation cannot differ
    merely because it begins inside a bucket.
    """
    results: list[dict[str, Any]] = []
    for symbol in symbols:
        epoch, open_, high, low, close = read_m1_arrays(repository, symbol, window_start, window_end)
        mine = aggregate_m5(epoch, open_, high, low, close)
        reference = list(repository.bars(symbol, window_start, window_end, "5m"))
        reference_epoch = np.fromiter(
            (_whole_seconds(bar.time) for bar in reference), dtype=np.int64, count=len(reference)
        )
        reference_open = np.fromiter(
            (bar.open for bar in reference), dtype=np.float64, count=len(reference)
        )
        reference_high = np.fromiter(
            (bar.high for bar in reference), dtype=np.float64, count=len(reference)
        )
        reference_low = np.fromiter(
            (bar.low for bar in reference), dtype=np.float64, count=len(reference)
        )
        reference_close = np.fromiter(
            (bar.close for bar in reference), dtype=np.float64, count=len(reference)
        )
        results.append(
            {
                "symbol": symbol,
                "m1_bars": int(epoch.size),
                "validator_m5_bars": int(mine[0].size),
                "reference_m5_bars": int(reference_epoch.size),
                "bars_equal": bool(mine[0].size == reference_epoch.size),
                "times_equal": bool(
                    mine[0].size == reference_epoch.size
                    and np.array_equal(mine[0], reference_epoch)
                ),
                "prices_equal": bool(
                    mine[0].size == reference_epoch.size
                    and np.array_equal(mine[1], reference_open)
                    and np.array_equal(mine[2], reference_high)
                    and np.array_equal(mine[3], reference_low)
                    and np.array_equal(mine[4], reference_close)
                ),
            }
        )
    return {
        "window": [window_start.isoformat(sep=" "), window_end.isoformat(sep=" ")],
        "note": (
            "Equivalence check of this validator's own bucket algorithm against the "
            "library aggregation on one calendar window.  It uses no research code."
        ),
        "results": results,
        "all_equal": all(
            row["bars_equal"] and row["times_equal"] and row["prices_equal"] for row in results
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independent Stage A validator for gap_fill_m5_20261019")
    parser.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument(
        "--research-dirs",
        nargs="+",
        default=None,
        help=(
            "stored research Stage A output directories to compare against; "
            "defaults to agent_runs/<id>/stage_a plus any stage_a_v2"
        ),
    )
    parser.add_argument("--skip-hash", action="store_true", help="skip Bars.dat SHA256 (smoke only)")
    parser.add_argument(
        "--equivalence-window",
        nargs=2,
        default=["2025-01-01", "2025-01-31"],
        metavar=("START", "END"),
    )
    return parser.parse_args(argv)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False, default=str),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.perf_counter()
    protocol = load_protocol()
    guard_frozen(protocol)
    windows = parse_periods(protocol)
    declared_symbols = list(protocol.get("symbols") or [])
    if not declared_symbols:
        raise ValidationError("protocol.symbols is empty")
    symbols = list(args.symbols) if args.symbols else declared_symbols
    unknown = [symbol for symbol in symbols if symbol not in declared_symbols]
    if unknown:
        raise ValidationError(f"symbols outside the frozen list: {unknown}")
    subset_run = set(symbols) != set(declared_symbols)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []

    def log(message: str) -> None:
        line = f"[validate_gap_fill_m5] {message}"
        print(line, flush=True)
        log_lines.append(line)

    log(f"experiment={EXPERIMENT_ID} symbols={len(symbols)} subset_run={subset_run}")
    log(f"protocol status={protocol.get('status')} frozen_at={protocol.get('frozen_at')}")
    for name, start, end in windows:
        log(f"period {name}: {start.isoformat(sep=' ')} .. {end.isoformat(sep=' ')}")

    repository = HistoryRepository(args.history_dir)
    records: list[dict[str, Any]] = []
    fingerprints: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        symbol_records, fingerprint = analyse_symbol(repository, symbol, windows)
        records.extend(symbol_records)
        fingerprints[symbol] = fingerprint
        log(
            f"{symbol}: m5={fingerprint['m5_bars']} partial={fingerprint['m5_partial_buckets']} "
            f"gaps={fingerprint['gap_events']} metrics={len(symbol_records)} "
            f"in {fingerprint['elapsed_seconds']}s"
        )

    summary = build_summary(records, symbols)
    criteria, criteria_problems = parse_gate_criteria(protocol)
    inventory_hashes, inventory_symbols = parse_inventory_hashes(DATA_INVENTORY_PATH)

    # Every stored research Stage A directory is compared, not just the one named
    # in the assignment: the researcher re-ran the frozen specification into
    # stage_a_v2 after fixing the non-gate control block, and the equality of the
    # gate-relevant numbers between the two runs must be verified, not assumed.
    target_dirs = [Path(value) for value in (args.research_dirs or [])]
    if not target_dirs:
        target_dirs = [RESEARCH_STAGE_A_DIR, *RESEARCH_ALT_DIRS]
    targets: list[dict[str, Any]] = []
    for directory in target_dirs:
        summary_path = directory / "stage_a_summary.json"
        manifest_path = directory / "run_manifest.json"
        if not summary_path.is_file():
            log(f"research target skipped (no stage_a_summary.json): {directory}")
            continue
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        )
        identity = code_identity(manifest) if manifest else {"rows": [], "all_match": None}
        targets.append(
            {
                "name": directory.name,
                "path": str(directory),
                "summary": json.loads(summary_path.read_text(encoding="utf-8")),
                "manifest": manifest,
                "summary_sha256": sha256_file(summary_path),
                "manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
                "code_identity": identity,
            }
        )
    if not targets:
        raise ValidationError(
            "no stored research Stage A output found; nothing to compare against (not verified)"
        )

    for target in targets:
        comparison = compare_trees(summary, target["summary"], subset_run)
        target["summary_comparison"] = comparison
        log(
            f"compare[{target['name']}]: exact={comparison['exact_matches']} "
            f"float_level={len(comparison['float_level_differences'])} "
            f"mismatch={len(comparison['mismatches'])} "
            f"significant={len(comparison['significant_mismatches'])}"
        )
        for row in comparison["significant_mismatches"]:
            log(f"SIGNIFICANT MISMATCH {target['name']} {row['path']}: {row}")
        for row in target["code_identity"]["rows"]:
            log(
                f"code identity[{target['name']}] {row['file']}: {row['status']}"
            )

    primary = targets[0]
    research_manifest = primary["manifest"]
    manifest_comparison = compare_manifest(fingerprints, research_manifest)
    for row in manifest_comparison["mismatches"]:
        log(f"MANIFEST MISMATCH {row['symbol']} {row['field']}: {row['validator']} != {row['research']}")

    gate_data = data_gate(
        Path(args.history_dir), symbols, inventory_hashes, research_manifest, args.skip_hash
    )
    log(
        f"data gate: {gate_data['bars_dat_checked']} Bars.dat hashed, "
        f"all_match={gate_data['bars_dat_all_match']}"
    )
    if criteria_problems:
        for problem in criteria_problems:
            log(f"CRITERIA PROBLEM: {problem}")

    gates = evaluate_gates(summary, criteria, symbols, gate_data)
    gates["criteria_parse_problems"] = criteria_problems
    gates["criteria"] = {key: value for key, value in criteria.items() if key != "raw_strings"}
    gates["criteria_raw_strings"] = criteria.get("raw_strings")
    gates["fill_first_denominator_sensitivity"] = fill_first_sensitivity(summary)

    comparison: dict[str, Any] = {
        "subset_run": subset_run,
        "primary_research_dir": primary["name"],
        "summary_comparison": primary["summary_comparison"],
        "manifest_comparison": manifest_comparison,
        "code_identity": primary["code_identity"],
        "all_research_targets": {
            target["name"]: {
                "summary_sha256": target["summary_sha256"],
                "manifest_sha256": target["manifest_sha256"],
                "exact_matches": target["summary_comparison"]["exact_matches"],
                "float_level_differences": len(target["summary_comparison"]["float_level_differences"]),
                "mismatches": len(target["summary_comparison"]["mismatches"]),
                "significant_mismatches": len(target["summary_comparison"]["significant_mismatches"]),
                "code_identity_all_match": target["code_identity"]["all_match"],
                "research_gate_evaluation": target["manifest"].get("gate_evaluation_stage_a"),
            }
            for target in targets
        },
    }
    target_consistency = research_target_consistency(targets)
    log(
        f"research target consistency: {target_consistency['note']} "
        f"(differing paths: {target_consistency['differing_paths']}, "
        f"non-control: {target_consistency['non_control_differing_paths']})"
    )

    ledger_table = parse_inventory_symbol_period_table(DATA_INVENTORY_PATH)
    ledger_check = ledger_crosscheck(records, symbols, ledger_table)
    log(
        f"ledger cross-check: {ledger_check['match_count']} match / "
        f"{ledger_check['mismatch_count']} mismatch / "
        f"{ledger_check['not_available_count']} not available"
    )
    for row in ledger_check["mismatches"]:
        log(
            f"LEDGER MISMATCH {row['symbol']} {row['period']} {row['field']}: "
            f"{row['validator']} != {row['ledger']}"
        )

    equivalence = aggregation_equivalence(
        repository,
        symbols[: min(2, len(symbols))],
        datetime.fromisoformat(args.equivalence_window[0]),
        datetime.fromisoformat(args.equivalence_window[1]) + timedelta(hours=23, minutes=59, seconds=59),
    )
    log(f"aggregation equivalence: all_equal={equivalence['all_equal']}")

    elapsed = time.perf_counter() - started
    log(f"total elapsed {elapsed:.1f}s")
    validator_manifest = {
        "experiment_id": EXPERIMENT_ID,
        "role": "independent verification (quant_validator)",
        "script": "scripts/validate_gap_fill_m5.py",
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "generated_at_local": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": round(elapsed, 3),
        "protocol_path": str(PROTOCOL_PATH.relative_to(ROOT)),
        "protocol_status": protocol.get("status"),
        "protocol_frozen_at": protocol.get("frozen_at"),
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "research_targets": [
            {
                "name": target["name"],
                "path": str(Path(target["path"]).relative_to(ROOT)),
                "summary_sha256": target["summary_sha256"],
                "manifest_sha256": target["manifest_sha256"],
                "declared_code_sha256": target["manifest"].get("code_sha256"),
                "code_identity": target["code_identity"],
                "elapsed_seconds": target["manifest"].get("elapsed_seconds"),
                "research_gate_evaluation": target["manifest"].get("gate_evaluation_stage_a"),
            }
            for target in targets
        ],
        "imports_research_module": False,
        "stage_b_executed": False,
        "frozen_precondition_checked": True,
        "code_identity": primary["code_identity"],
        "symbols": symbols,
        "thresholds_pips": list(THRESHOLDS),
        "threshold_tolerance_pips": THRESHOLD_TOLERANCE_PIPS,
        "gap_min_minutes": GAP_MIN_SECONDS // 60,
        "max_holding_bars": MAX_HOLDING_BARS,
        "input_fingerprints": fingerprints,
        "total_stage_a_records": len(records),
        "log": log_lines,
    }

    write_json(output_dir / "validator_stage_a_summary.json", summary)
    write_json(output_dir / "validator_manifest.json", validator_manifest)
    write_json(output_dir / "gate_evaluation.json", gates)
    write_json(output_dir / "comparison.json", comparison)
    write_json(output_dir / "code_identity.json", primary["code_identity"])
    write_json(output_dir / "research_target_consistency.json", target_consistency)
    for target in targets:
        write_json(
            output_dir / f"comparison_{target['name']}.json",
            {
                "research_dir": target["name"],
                "summary_sha256": target["summary_sha256"],
                "subset_run": subset_run,
                "summary_comparison": target["summary_comparison"],
                "code_identity": target["code_identity"],
            },
        )
    write_json(output_dir / "ledger_crosscheck.json", ledger_check)
    write_json(output_dir / "aggregation_equivalence.json", equivalence)
    write_json(
        output_dir / "records_index.json",
        {
            "note": (
                "Per-event detail is kept only in memory; this index records the counts that "
                "the aggregates above were built from so the run can be spot-checked."
            ),
            "per_symbol_period_counts": {
                symbol: {
                    name: sum(
                        1
                        for record in records
                        if record["symbol"] == symbol and record["period"] == name
                    )
                    for name in PERIOD_ORDER
                }
                for symbol in symbols
            },
        },
    )
    log(f"wrote {output_dir}")

    print(json.dumps(
        {
            "stage_a_gates": {
                key: gates[key].get("passed")
                for key in (
                    "stage_a_population",
                    "stage_a_fill_first",
                    "stage_a_symbol_consistency",
                    "stage_a_vs_baseline",
                    "stage_a_data",
                )
            },
            "stage_a_overall_passed": gates["stage_a_overall_passed"],
            "comparison": {
                key: comparison["summary_comparison"].get(key)
                for key in ("exact_matches", "float_level_differences", "mismatches")
            },
            "research_targets": {
                name: {
                    "exact_matches": block["exact_matches"],
                    "mismatches": block["mismatches"],
                    "significant_mismatches": block["significant_mismatches"],
                    "code_identity_all_match": block["code_identity_all_match"],
                }
                for name, block in comparison["all_research_targets"].items()
            },
            "research_target_consistency": {
                "differing_paths": target_consistency["differing_paths"],
                "non_control_differing_paths": target_consistency["non_control_differing_paths"],
            },
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    ), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
