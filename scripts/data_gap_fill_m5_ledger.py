#!/usr/bin/env python
"""Read-only data ledger for experiment gap_fill_m5_20261019.

Builds, for 11 FX symbols:
  * file fingerprints (size / mtime / SHA256 of Bars.dat and info.dat)
  * M1 population, metadata (spread, commission, pip, lot, quote currency)
  * deterministic M5 aggregation from stored M1 (same rule as
    forextester_backtest.data._aggregate_bars) with per-bucket M1 counts
  * time-discontinuity (gap) population: previous-M5-bar time difference >= 120 min
  * M1 quality audit over the whole file and over the 2009-10-01..end window
  * verification that aggregation equals HistoryRepository.bars(..., "5m")

Never writes to the Forex Tester history directory. Reads only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import struct
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from forextester_backtest.data import OLE_EPOCH, HistoryRepository

HISTORY_ROOT = Path(r"C:\ForexTester6\data\History")
WORKSPACE = Path(__file__).resolve().parents[1]
RUN_DIR = WORKSPACE / "agent_runs" / "gap_fill_m5_20261019"

DEFAULT_SYMBOLS = [
    "AUDUSD",
    "EURUSD",
    "GBPUSD",
    "NZDUSD",
    "USDCHF",
    "USDJPY",
    "AUDJPY",
    "CHFJPY",
    "EURCHF",
    "GBPCHF",
    "GBPJPY",
]

RECORD_SIZE = 48  # <6d
CHUNK_RECORDS = 1 << 20
M5_SECONDS = 300
GAP_MIN_MINUTES = 120
WIDTH_LEVELS = (10.0, 25.0)

TRAIN_START = datetime(2009, 10, 1)
PROTOCOL_FINAL_END = datetime(2026, 7, 17, 23, 59, 59)

PERIODS: list[tuple[str, datetime, datetime]] = [
    ("training", datetime(2009, 10, 1), datetime(2016, 12, 31, 23, 59, 59)),
    ("validation", datetime(2017, 1, 1), datetime(2021, 12, 31, 23, 59, 59)),
    ("final_confirmation", datetime(2022, 1, 1), datetime(2100, 1, 1)),
]

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Values copied from docs/quant_organization/data_inventory.md (2026-09-08 survey)
# for the endpoint diff. Not re-derived here.
PREVIOUS_LEDGER = {
    "AUDUSD": ("2009-10-01 00:00", "2026-07-19 23:59", 6_236_644, 1.2),
    "EURUSD": ("2003-05-06 00:00", "2026-07-17 20:59", 8_517_565, 1.1),
    "GBPUSD": ("2003-05-06 00:00", "2026-07-17 20:59", 8_631_252, 1.4),
    "NZDUSD": ("2003-08-05 00:00", "2026-07-17 20:59", 8_525_392, 1.4),
    "USDCHF": ("2001-01-02 23:01", "2026-07-17 20:59", 9_176_194, 1.5),
    "USDJPY": ("2003-05-06 00:00", "2026-07-17 20:59", 8_486_336, 1.2),
    "AUDJPY": ("2003-12-02 00:00", "2026-07-17 20:59", 8_429_303, 1.4),
    "CHFJPY": ("2001-01-02 23:01", "2026-07-19 23:59", 9_136_956, 1.8),
    "EURCHF": ("2003-08-05 00:00", "2026-07-17 20:59", 8_471_194, 1.7),
    "GBPCHF": ("2003-08-15 08:55", "2026-07-17 20:59", 8_539_678, 1.6),
    "GBPJPY": ("2001-01-02 23:01", "2026-07-17 20:59", 9_222_676, 1.8),
}


def to_us(value: datetime) -> int:
    return (value - OLE_EPOCH) // timedelta(microseconds=1)


def from_us(us: int) -> datetime:
    return OLE_EPOCH + timedelta(microseconds=int(us))


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.strftime("%Y-%m-%d %H:%M:%S")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def file_fingerprint(path: Path, do_hash: bool) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "sha256": sha256_file(path) if do_hash else None,
    }


def group_aggregate(
    us: np.ndarray,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    bucket: np.ndarray,
) -> dict[str, np.ndarray]:
    """Aggregate minute rows into buckets exactly like data._aggregate_bars."""
    new = np.empty(bucket.size, dtype=bool)
    new[0] = True
    if bucket.size > 1:
        new[1:] = bucket[1:] != bucket[:-1]
    starts = np.flatnonzero(new)
    ends = np.empty_like(starts)
    ends[:-1] = starts[1:]
    ends[-1] = bucket.size
    last = ends - 1
    return {
        "bucket": bucket[starts],
        "us": us[starts],
        "open": open_[starts],
        "high": np.maximum.reduceat(high, starts),
        "low": np.minimum.reduceat(low, starts),
        "close": close[last],
        "volume": np.add.reduceat(volume, starts),
        "n_m1": np.diff(np.append(starts, bucket.size)),
    }


def append_groups(store: dict[str, list[np.ndarray]], groups: dict[str, np.ndarray]) -> None:
    for key, value in groups.items():
        store[key].append(value)


def join_groups(store: dict[str, list[np.ndarray]]) -> dict[str, np.ndarray]:
    return {key: (np.concatenate(value) if value else np.empty(0)) for key, value in store.items()}


def symbol_metadata(repo: HistoryRepository, symbol: str) -> dict[str, Any]:
    meta = repo.metadata(symbol)
    decimals = meta.decimals
    pip = 10 ** (-(decimals - 1))
    values = meta.values
    return {
        "symbol": symbol,
        "directory": str(repo.root / symbol),
        "raw": dict(values),
        "decimals": decimals,
        "spread_points": meta.spread_points,
        "spread_price": meta.spread_price,
        "spread_pips": meta.spread_points / 10.0,
        "pip_size": pip,
        "lot_size": meta.lot_size,
        "commission_per_lot_from_metadata": meta.commission_per_lot,
        "apply_commission": values.get("ApplyCommission"),
        "comm_per_lot_raw": values.get("CommPerLot"),
        "base_currency": values.get("BaseCurrency"),
        "lot_currency": values.get("LotCurrency"),
        "margin_currency": values.get("MarginCurrency"),
        "quote_currency_pnl": meta.pnl_currency,
        "swap_long": values.get("SwapLong"),
        "swap_short": values.get("SwapShort"),
        "broker": values.get("Broker"),
        "group": values.get("group"),
        "min_dist_to_price": values.get("MinDistToPrice"),
        "type": values.get("type"),
    }


def scan_symbol(
    repo: HistoryRepository, symbol: str, do_hash: bool, limit_records: int | None = None
) -> dict[str, Any]:
    started = time.time()
    directory = repo.root / symbol
    bars_path = directory / "Bars.dat"
    info_path = directory / "info.dat"
    ticks_path = directory / "ticks.dat"

    summary = repo.summary(symbol)
    effective_count = (
        summary.bar_count if limit_records is None else min(summary.bar_count, limit_records)
    )
    truncated = effective_count < summary.bar_count
    if truncated:
        do_hash = False
    size = bars_path.stat().st_size
    slots = (size - 4) // RECORD_SIZE if size >= 4 else 0
    remainder = (size - 4) % RECORD_SIZE if size >= 4 else -1
    with bars_path.open("rb") as stream:
        header = struct.unpack("<I", stream.read(4))[0]

    bytes_beyond_counted = size - 4 - summary.bar_count * RECORD_SIZE
    first_trailing_ole: float | None = None
    trailing_all_zero: bool | None = None
    if bytes_beyond_counted >= 8:
        extra = bytes_beyond_counted // RECORD_SIZE
        with bars_path.open("rb") as stream:
            stream.seek(4 + summary.bar_count * RECORD_SIZE)
            trailing = np.frombuffer(stream.read(extra * RECORD_SIZE), dtype="<f8").reshape(-1, 6)
        first_trailing_ole = float(trailing[0, 0])
        trailing_all_zero = bool((trailing[:, 0] == 0.0).all() and (trailing[:, 1:] == 0.0).all())

    m5_store: dict[str, list[np.ndarray]] = {
        key: [] for key in ("bucket", "us", "open", "high", "low", "close", "volume", "n_m1")
    }
    audit = {
        "records_scanned": 0,
        "records_scanned_in_scope": 0,
        "non_finite": 0,
        "non_finite_in_scope": 0,
        "non_positive_time": 0,
        "non_positive_time_in_scope": 0,
        "non_positive_price": 0,
        "non_positive_price_in_scope": 0,
        "non_positive_high_or_low": 0,
        "non_positive_high_or_low_in_scope": 0,
        "negative_volume": 0,
        "zero_volume": 0,
        "zero_volume_in_scope": 0,
        "ohlc_high_lt_max_oc": 0,
        "ohlc_high_lt_max_oc_in_scope": 0,
        "ohlc_low_gt_min_oc": 0,
        "ohlc_low_gt_min_oc_in_scope": 0,
        "ohlc_high_lt_low": 0,
        "ohlc_high_lt_low_in_scope": 0,
        "non_increasing_time": 0,
        "non_increasing_time_in_scope": 0,
        "duplicate_time": 0,
        "duplicate_time_in_scope": 0,
        "m1_steps_gt_1min": 0,
        "m1_steps_ge_5min": 0,
        "negative_volume_examples": [],
        "zero_volume_examples": [],
        "examples": [],
    }
    train_start_us = to_us(TRAIN_START)

    digest = hashlib.sha256()
    carry: dict[str, np.ndarray] | None = None
    parsed = 0
    previous_last_us: int | None = None
    chunk_bytes = CHUNK_RECORDS * RECORD_SIZE

    with bars_path.open("rb", buffering=1024 * 1024) as stream:
        first = stream.read(4)
        if do_hash:
            digest.update(first)
        stream.seek(4)
        while True:
            raw = stream.read(chunk_bytes)
            if not raw:
                break
            if do_hash:
                digest.update(raw)
            usable = min(len(raw), max(0, (effective_count - parsed) * RECORD_SIZE))
            if usable <= 0:
                continue
            usable -= usable % RECORD_SIZE
            rows = np.frombuffer(raw[:usable], dtype="<f8").reshape(-1, 6)
            parsed += rows.shape[0]

            ole = rows[:, 0]
            open_ = rows[:, 1].copy()
            close = rows[:, 2].copy()
            high = rows[:, 3].copy()
            low = rows[:, 4].copy()
            volume = rows[:, 5].copy()

            finite = np.isfinite(rows).all(axis=1)
            us = np.rint(ole * 86_400.0 * 1_000_000.0).astype(np.int64)
            in_scope = us >= train_start_us

            audit["records_scanned"] += int(rows.shape[0])
            audit["records_scanned_in_scope"] += int(in_scope.sum())

            bad_finite = ~finite
            audit["non_finite"] += int(bad_finite.sum())
            audit["non_finite_in_scope"] += int((bad_finite & in_scope).sum())

            bad_time = ole <= 0
            audit["non_positive_time"] += int(bad_time.sum())
            audit["non_positive_time_in_scope"] += int((bad_time & in_scope).sum())

            bad_price = (open_ <= 0) | (close <= 0)
            audit["non_positive_price"] += int(bad_price.sum())
            audit["non_positive_price_in_scope"] += int((bad_price & in_scope).sum())

            bad_hl = (high <= 0) | (low <= 0)
            audit["non_positive_high_or_low"] += int(bad_hl.sum())
            audit["non_positive_high_or_low_in_scope"] += int((bad_hl & in_scope).sum())

            audit["negative_volume"] += int((volume < 0).sum())
            zero_vol = volume == 0
            audit["zero_volume"] += int(zero_vol.sum())
            audit["zero_volume_in_scope"] += int((zero_vol & in_scope).sum())

            bad_high = high < np.maximum(open_, close)
            audit["ohlc_high_lt_max_oc"] += int(bad_high.sum())
            audit["ohlc_high_lt_max_oc_in_scope"] += int((bad_high & in_scope).sum())

            bad_low = low > np.minimum(open_, close)
            audit["ohlc_low_gt_min_oc"] += int(bad_low.sum())
            audit["ohlc_low_gt_min_oc_in_scope"] += int((bad_low & in_scope).sum())

            bad_range = high < low
            audit["ohlc_high_lt_low"] += int(bad_range.sum())
            audit["ohlc_high_lt_low_in_scope"] += int((bad_range & in_scope).sum())

            if rows.shape[0] > 1:
                d = np.diff(us)
                non_inc = d <= 0
                audit["non_increasing_time"] += int(non_inc.sum())
                audit["non_increasing_time_in_scope"] += int((non_inc & in_scope[1:]).sum())
                dup = d == 0
                audit["duplicate_time"] += int(dup.sum())
                audit["duplicate_time_in_scope"] += int((dup & in_scope[1:]).sum())
                audit["m1_steps_gt_1min"] += int((d > 60_000_000).sum())
                audit["m1_steps_ge_5min"] += int((d >= 300_000_000).sum())

            if previous_last_us is not None and rows.shape[0]:
                boundary = us[0] - previous_last_us
                if boundary <= 0:
                    audit["non_increasing_time"] += 1
                    if in_scope[0]:
                        audit["non_increasing_time_in_scope"] += 1
                if boundary == 0:
                    audit["duplicate_time"] += 1
                    if in_scope[0]:
                        audit["duplicate_time_in_scope"] += 1
                if boundary > 60_000_000:
                    audit["m1_steps_gt_1min"] += 1
                if boundary >= 300_000_000:
                    audit["m1_steps_ge_5min"] += 1
            if rows.shape[0]:
                previous_last_us = int(us[-1])

            if len(audit["negative_volume_examples"]) < 5:
                for index in np.flatnonzero(volume < 0)[: 5 - len(audit["negative_volume_examples"])]:
                    audit["negative_volume_examples"].append(
                        {
                            "time": iso(from_us(us[index])),
                            "volume": float(volume[index]),
                            "open": float(open_[index]),
                            "high": float(high[index]),
                            "low": float(low[index]),
                            "close": float(close[index]),
                        }
                    )
            if len(audit["zero_volume_examples"]) < 5:
                for index in np.flatnonzero(volume == 0)[: 5 - len(audit["zero_volume_examples"])]:
                    audit["zero_volume_examples"].append(
                        {
                            "time": iso(from_us(us[index])),
                            "volume": float(volume[index]),
                            "close": float(close[index]),
                        }
                    )
            if len(audit["examples"]) < 8:
                flagged = np.flatnonzero(
                    (~finite)
                    | (open_ <= 0)
                    | (close <= 0)
                    | bad_high
                    | bad_low
                    | bad_range
                    | zero_vol
                    | (volume < 0)
                )
                for index in flagged[: 8 - len(audit["examples"])]:
                    audit["examples"].append(
                        {
                            "time": iso(from_us(us[index])),
                            "open": float(open_[index]),
                            "close": float(close[index]),
                            "high": float(high[index]),
                            "low": float(low[index]),
                            "volume": float(volume[index]),
                            "reason": (
                                "non_finite"
                                if not finite[index]
                                else "zero_volume"
                                if volume[index] == 0
                                else "ohlc_or_price"
                            ),
                        }
                    )

            chunk = {
                "us": us,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
            if carry is not None:
                merged = {key: np.concatenate([carry[key], chunk[key]]) for key in chunk}
            else:
                merged = chunk
            bucket = (merged["us"] // 1_000_000) // M5_SECONDS
            split = int(np.flatnonzero(bucket == bucket[-1])[0]) if bucket.size else 0
            is_final = parsed >= effective_count
            if is_final:
                head = merged
                carry = None
            else:
                head = {key: merged[key][:split] for key in merged}
                carry = {key: merged[key][split:] for key in merged}
            if head["us"].size:
                head_bucket = (head["us"] // 1_000_000) // M5_SECONDS
                groups = group_aggregate(
                    head["us"],
                    head["open"],
                    head["high"],
                    head["low"],
                    head["close"],
                    head["volume"],
                    head_bucket,
                )
                append_groups(m5_store, groups)

    if carry is not None and carry["us"].size:
        carry_bucket = (carry["us"] // 1_000_000) // M5_SECONDS
        append_groups(
            m5_store,
            group_aggregate(
                carry["us"],
                carry["open"],
                carry["high"],
                carry["low"],
                carry["close"],
                carry["volume"],
                carry_bucket,
            ),
        )

    if do_hash:
        bars_sha256 = digest.hexdigest()
    else:
        bars_sha256 = None

    m5 = join_groups(m5_store)
    m5_time_us = m5["bucket"] * M5_SECONDS * 1_000_000
    m5_dt_minutes = np.diff(m5_time_us) / 60_000_000.0

    gap_positions = np.flatnonzero(m5_dt_minutes >= GAP_MIN_MINUTES)
    gap_rows: list[dict[str, Any]] = []
    meta = symbol_metadata(repo, symbol)
    pip = meta["pip_size"]
    for position in gap_positions:
        index = int(position) + 1
        gap_time = from_us(int(m5_time_us[index]))
        width_pips = abs(float(m5["open"][index]) - float(m5["close"][index - 1])) / pip
        period = next(
            (name for name, start, end in PERIODS if start <= gap_time <= end),
            "before_training",
        )
        gap_rows.append(
            {
                "symbol": symbol,
                "gap_bar_time": gap_time,
                "prev_bar_time": from_us(int(m5_time_us[index - 1])),
                "gap_minutes": float(m5_dt_minutes[position]),
                "width_pips": width_pips,
                "direction": "up" if m5["open"][index] > m5["close"][index - 1] else "down",
                "open": float(m5["open"][index]),
                "prev_close": float(m5["close"][index - 1]),
                "n_m1_gap_bar": int(m5["n_m1"][index]),
                "period": period,
                "in_protocol_final_window": gap_time <= PROTOCOL_FINAL_END,
            }
        )

    dt_counter: dict[str, int] = {}
    for row in gap_rows:
        key = f"{row['gap_minutes']:.0f}"
        dt_counter[key] = dt_counter.get(key, 0) + 1
    gap_minutes_top = sorted(dt_counter.items(), key=lambda item: (-item[1], item[0]))[:6]

    medium_positions = np.flatnonzero((m5_dt_minutes >= 30) & (m5_dt_minutes < GAP_MIN_MINUTES))
    medium_steps: list[dict[str, Any]] = []
    for position in medium_positions:
        index = int(position) + 1
        medium_steps.append(
            {
                "symbol": symbol,
                "bar_time": from_us(int(m5_time_us[index])),
                "prev_bar_time": from_us(int(m5_time_us[index - 1])),
                "minutes": float(m5_dt_minutes[position]),
                "n_m1": int(m5["n_m1"][index]),
            }
        )

    dt_hist: dict[str, int] = {
        "=5": int((m5_dt_minutes == 5).sum()),
        "6-9": int(((m5_dt_minutes > 5) & (m5_dt_minutes < 10)).sum()),
        "10-14": int(((m5_dt_minutes >= 10) & (m5_dt_minutes < 15)).sum()),
        "15-29": int(((m5_dt_minutes >= 15) & (m5_dt_minutes < 30)).sum()),
        "30-59": int(((m5_dt_minutes >= 30) & (m5_dt_minutes < 60)).sum()),
        "60-119": int(((m5_dt_minutes >= 60) & (m5_dt_minutes < 120)).sum()),
        ">=120": int((m5_dt_minutes >= 120).sum()),
    }

    n_m1_counts = m5["n_m1"]
    partial = {str(k): int((n_m1_counts == k).sum()) for k in range(1, 6)}
    partial["gt5"] = int((n_m1_counts > 5).sum())

    elapsed = time.time() - started
    return {
        "symbol": symbol,
        "metadata": meta,
        "summary": {
            "bar_count_from_repository": summary.bar_count,
            "bar_count_header": int(header),
            "slots_in_file": int(slots),
            "record_bytes_not_divisible": int(remainder),
            "bytes_beyond_counted_records": int(bytes_beyond_counted),
            "extra_record_slots": int(slots - summary.bar_count),
            "first_trailing_ole": first_trailing_ole,
            "trailing_slots_all_zero": trailing_all_zero,
            "records_parsed": parsed,
            "truncated_smoke_test": bool(truncated),
            "bar_start": iso(summary.bar_start),
            "bar_end": iso(summary.bar_end),
            "tick_count": summary.tick_count,
            "tick_start": iso(summary.tick_start),
            "tick_end": iso(summary.tick_end),
        },
        "files": {
            "Bars.dat": {
                "bytes": size,
                "mtime": datetime.fromtimestamp(bars_path.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "sha256": bars_sha256,
            },
            "info.dat": file_fingerprint(info_path, do_hash),
            "ticks.dat": {
                "bytes": ticks_path.stat().st_size,
                "mtime": datetime.fromtimestamp(ticks_path.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "sha256": None,
                "sha256_note": "not computed: file is 7.7-17.1 GB per symbol; read for size/mtime only",
            },
        },
        "m5": {
            "buckets": int(m5["bucket"].size),
            "first_bucket": iso(from_us(int(m5_time_us[0]))) if m5["bucket"].size else None,
            "last_bucket": iso(from_us(int(m5_time_us[-1]))) if m5["bucket"].size else None,
            "partial_bucket_counts_by_n_m1": partial,
            "dt_minutes_histogram": dt_hist,
            "gap_minutes_top": gap_minutes_top,
            "steps_30_119_count": int(medium_positions.size),
        },
        "audit": audit,
        "gap_events": gap_rows,
        "medium_steps": medium_steps,
        "elapsed_seconds": round(elapsed, 1),
    }


def aggregate_window(bars: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for bar in bars:
        bucket = ((bar.time - OLE_EPOCH) // timedelta(microseconds=1)) // 1_000_000 // M5_SECONDS
        if current is None or bucket != current["bucket"]:
            if current is not None:
                out.append(current)
            current = {
                "bucket": bucket,
                "time": OLE_EPOCH + timedelta(seconds=int(bucket) * M5_SECONDS),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "n_m1": 1,
            }
        else:
            current["high"] = max(current["high"], bar.high)
            current["low"] = min(current["low"], bar.low)
            current["close"] = bar.close
            current["volume"] += bar.volume
            current["n_m1"] += 1
    if current is not None:
        out.append(current)
    return out


def verify_aggregation(repo: HistoryRepository, symbol: str, start: datetime, end: datetime) -> dict[str, Any]:
    mine = aggregate_window(list(repo.bars(symbol, start=start, end=end, timeframe="1m")))
    theirs = list(repo.bars(symbol, start=start, end=end, timeframe="5m"))
    result: dict[str, Any] = {
        "symbol": symbol,
        "window": [iso(start), iso(end)],
        "mine_bars": len(mine),
        "repository_bars": len(theirs),
        "time_mismatch": 0,
        "price_mismatch": 0,
        "volume_mismatch": 0,
        "partial_buckets_mine": sum(1 for item in mine if item["n_m1"] < 5),
        "partial_buckets_matched": 0,
        "first_mismatch": None,
    }
    for left, right in zip(mine, theirs):
        if left["time"] != right.time:
            result["time_mismatch"] += 1
            if result["first_mismatch"] is None:
                result["first_mismatch"] = {
                    "kind": "time",
                    "mine": iso(left["time"]),
                    "repo": iso(right.time),
                }
        if (
            left["open"],
            left["high"],
            left["low"],
            left["close"],
        ) != (right.open, right.high, right.low, right.close):
            result["price_mismatch"] += 1
            if result["first_mismatch"] is None:
                result["first_mismatch"] = {
                    "kind": "price",
                    "time": iso(left["time"]),
                    "mine": [left["open"], left["high"], left["low"], left["close"]],
                    "repo": [right.open, right.high, right.low, right.close],
                }
        if abs(left["volume"] - right.volume) > 1e-9:
            result["volume_mismatch"] += 1
        if left["n_m1"] < 5 and left["time"] == right.time:
            result["partial_buckets_matched"] += 1
    if len(mine) != len(theirs):
        result["length_mismatch"] = abs(len(mine) - len(theirs))
    return result


def end_inclusive_probe(repo: HistoryRepository, symbol: str, probe: datetime) -> dict[str, Any]:
    single = list(repo.bars(symbol, start=probe, end=probe, timeframe="1m"))
    return {
        "symbol": symbol,
        "probe_time": iso(probe),
        "bars_returned": len(single),
        "time_returned": iso(single[0].time) if single else None,
    }


def percentile(values: list[float], qs: list[float]) -> dict[str, float | None]:
    if not values:
        return {f"p{q}": None for q in qs}
    array = np.asarray(values, dtype=float)
    return {f"p{q}": float(np.percentile(array, q)) for q in qs}


def period_slice(gaps: list[dict[str, Any]], name: str, end: datetime | None = None) -> list[dict[str, Any]]:
    if name == "before_training":
        return [g for g in gaps if g["period"] == "before_training"]
    if name == "all":
        return list(gaps)
    selected = [g for g in gaps if g["period"] == name]
    if end is not None:
        selected = [g for g in selected if g["gap_bar_time"] <= end]
    return selected


def md_table(header: list[Any], rows: list[list[Any]]) -> str:
    out = [
        "| " + " | ".join(str(item) for item in header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if item is None else str(item) for item in row) + " |")
    return "\n".join(out)


def quantile_map(values: list[float], qs: list[float]) -> dict[float, float | None]:
    if not values:
        return {q: None for q in qs}
    array = np.asarray(values, dtype=float)
    return {q: float(np.percentile(array, q)) for q in qs}


def write_tables(report: dict[str, Any], run_dir: Path) -> Path:
    symbols = [
        s
        for s in report["requested_symbols"]
        if s in report["symbols"] and "error" not in report["symbols"][s]
    ]
    blocks: list[str] = []
    blocks.append(f"generated_at: {report['generated_at']}")

    blocks.append("## metadata")
    rows = []
    for symbol in symbols:
        meta = report["symbols"][symbol]["metadata"]
        rows.append(
            [
                symbol,
                meta["decimals"],
                meta["pip_size"],
                meta["spread_points"],
                f"{meta['spread_price']:.10g}",
                meta["spread_pips"],
                meta["lot_size"],
                meta["commission_per_lot_from_metadata"],
                meta["apply_commission"],
                meta["comm_per_lot_raw"],
                meta["base_currency"],
                meta["lot_currency"],
                meta["margin_currency"],
                meta["quote_currency_pnl"],
                meta["swap_long"],
                meta["swap_short"],
                meta["broker"],
                meta["group"],
                meta["min_dist_to_price"],
            ]
        )
    blocks.append(
        md_table(
            [
                "symbol",
                "decimals",
                "pip_size",
                "spread_points",
                "spread_price",
                "spread_pips",
                "lot",
                "commission_per_lot",
                "ApplyCommission",
                "CommPerLot",
                "BaseCcy",
                "LotCcy",
                "MarginCcy",
                "quote(PnL)",
                "SwapLong",
                "SwapShort",
                "Broker",
                "group",
                "MinDistToPrice",
            ],
            rows,
        )
    )

    blocks.append("## endpoints and diff vs data_inventory.md (2026-09-08)")
    rows = []
    for symbol in symbols:
        summary = report["symbols"][symbol]["summary"]
        old = PREVIOUS_LEDGER.get(symbol, ("", "", "", ""))
        rows.append(
            [
                symbol,
                summary["bar_start"],
                summary["bar_end"],
                f"{summary['bar_count_from_repository']:,}",
                old[0],
                old[1],
                f"{old[2]:,}" if old[2] != "" else "",
                f"{summary['bar_count_from_repository'] - old[2]:+,}" if old[2] != "" else "",
                summary["bar_count_header"],
                summary["slots_in_file"],
                summary["extra_record_slots"],
                summary["first_trailing_ole"],
                summary["tick_count"],
                summary["tick_start"],
                summary["tick_end"],
            ]
        )
    blocks.append(
        md_table(
            [
                "symbol",
                "M1_start_now",
                "M1_end_now",
                "bars_now",
                "M1_start_20260908",
                "M1_end_20260908",
                "bars_20260908",
                "delta_bars",
                "header_count",
                "slots",
                "extra_slots",
                "first_trailing_ole",
                "tick_count",
                "tick_start",
                "tick_end",
            ],
            rows,
        )
    )

    blocks.append("## file fingerprints")
    rows = []
    for symbol in symbols:
        files = report["symbols"][symbol]["files"]
        for name in ("Bars.dat", "info.dat", "ticks.dat"):
            item = files[name]
            rows.append(
                [
                    symbol,
                    name,
                    f"{item['bytes']:,}",
                    item["mtime"],
                    item["sha256"] or "(not computed)",
                ]
            )
    blocks.append(md_table(["symbol", "file", "bytes", "mtime", "sha256"], rows))

    blocks.append("## M5 buckets and partial buckets (n_m1 per bucket)")
    rows = []
    for symbol in symbols:
        m5 = report["symbols"][symbol]["m5"]
        counts = m5["partial_bucket_counts_by_n_m1"]
        partial = sum(counts[str(k)] for k in range(1, 5))
        rows.append(
            [
                symbol,
                f"{m5['buckets']:,}",
                f"{counts['1']:,}",
                f"{counts['2']:,}",
                f"{counts['3']:,}",
                f"{counts['4']:,}",
                f"{counts['5']:,}",
                f"{counts['gt5']:,}",
                f"{100.0 * partial / m5['buckets']:.2f}%" if m5["buckets"] else "n/a",
                m5["first_bucket"],
                m5["last_bucket"],
            ]
        )
    blocks.append(
        md_table(
            [
                "symbol",
                "M5_buckets",
                "n_m1=1",
                "n_m1=2",
                "n_m1=3",
                "n_m1=4",
                "n_m1=5",
                "n_m1>5",
                "partial_share",
                "first_bucket",
                "last_bucket",
            ],
            rows,
        )
    )

    blocks.append("## M1 / M5 step histogram")
    rows = []
    for symbol in symbols:
        data = report["symbols"][symbol]
        audit = data["audit"]
        hist = data["m5"]["dt_minutes_histogram"]
        rows.append(
            [
                symbol,
                f"{audit['m1_steps_gt_1min']:,}",
                f"{audit['m1_steps_ge_5min']:,}",
                f"{hist['=5']:,}",
                f"{hist['6-9']:,}",
                f"{hist['10-14']:,}",
                f"{hist['15-29']:,}",
                f"{hist['30-59']:,}",
                f"{hist['60-119']:,}",
                f"{hist['>=120']:,}",
            ]
        )
    blocks.append(
        md_table(
            [
                "symbol",
                "M1_steps_gt_1min",
                "M1_steps_ge_5min",
                "M5_dt=5m",
                "M5_dt_6-9m",
                "M5_dt_10-14m",
                "M5_dt_15-29m",
                "M5_dt_30-59m",
                "M5_dt_60-119m",
                "M5_dt_ge120m",
            ],
            rows,
        )
    )

    for scope, suffix in ((False, "full_file"), (True, "in_scope_2009-10-01_onward")):
        blocks.append(f"## M1 quality audit ({suffix})")
        rows = []
        for symbol in symbols:
            audit = report["symbols"][symbol]["audit"]
            key = (lambda name: name + "_in_scope") if scope else (lambda name: name)
            rows.append(
                [
                    symbol,
                    f"{audit['records_scanned_in_scope' if scope else 'records_scanned']:,}",
                    audit[key("non_finite")],
                    audit[key("duplicate_time")],
                    audit[key("non_increasing_time")],
                    audit[key("non_positive_time")],
                    audit[key("non_positive_price")],
                    audit[key("non_positive_high_or_low")],
                    audit[key("ohlc_high_lt_max_oc")],
                    audit[key("ohlc_low_gt_min_oc")],
                    audit[key("ohlc_high_lt_low")],
                    audit[key("zero_volume")],
                    audit["negative_volume"],
                ]
            )
        blocks.append(
            md_table(
                [
                    "symbol",
                    "records",
                    "non_finite",
                    "duplicate_time",
                    "non_increasing_time",
                    "time<=0",
                    "price<=0(O/C)",
                    "price<=0(H/L)",
                    "H<max(O,C)",
                    "L>min(O,C)",
                    "H<L",
                    "volume=0",
                    "volume<0",
                ],
                rows,
            )
        )

    period_names = ["before_training", "training", "validation", "final_confirmation"]
    for period in period_names:
        blocks.append(f"## gap events by symbol ({period})")
        rows = []
        total = [0, 0, 0]
        for symbol in symbols:
            gaps = period_slice(report["symbols"][symbol]["gap_events"], period)
            ge10 = sum(1 for g in gaps if g["width_pips"] >= WIDTH_LEVELS[0])
            ge25 = sum(1 for g in gaps if g["width_pips"] >= WIDTH_LEVELS[1])
            total[0] += len(gaps)
            total[1] += ge10
            total[2] += ge25
            rows.append([symbol, len(gaps), ge10, ge25])
        rows.append(["TOTAL", total[0], total[1], total[2]])
        blocks.append(md_table(["symbol", "n_gap", "n_ge10pip", "n_ge25pip"], rows))

    blocks.append("## gap events after the protocol final end (2026-07-17) by symbol")
    rows = []
    for symbol in symbols:
        gaps = report["symbols"][symbol]["gap_events"]
        after = [g for g in gaps if not g["in_protocol_final_window"]]
        rows.append(
            [
                symbol,
                len(after),
                sum(1 for g in after if g["width_pips"] >= WIDTH_LEVELS[0]),
                sum(1 for g in after if g["width_pips"] >= WIDTH_LEVELS[1]),
                after[0]["gap_bar_time"] if after else "",
                after[-1]["gap_bar_time"] if after else "",
            ]
        )
    blocks.append(
        md_table(
            ["symbol", "n_gap", "n_ge10pip", "n_ge25pip", "first", "last"],
            rows,
        )
    )

    blocks.append("## most frequent gap durations (minutes) per symbol")
    rows = []
    for symbol in symbols:
        top = report["symbols"][symbol]["m5"]["gap_minutes_top"]
        rows.append(
            [
                symbol,
                sum(count for _, count in top),
                *[f"{minutes}m x{count}" for minutes, count in top],
            ]
        )
    blocks.append(
        md_table(
            [
                "symbol",
                "n_top6",
                "top1",
                "top2",
                "top3",
                "top4",
                "top5",
                "top6",
            ],
            rows,
        )
    )

    blocks.append("## negative / zero volume examples")
    rows = []
    for symbol in symbols:
        audit = report["symbols"][symbol]["audit"]
        neg = audit["negative_volume_examples"]
        zero = audit["zero_volume_examples"]
        rows.append(
            [
                symbol,
                len(neg),
                "; ".join(f"{item['time']} vol={item['volume']:.0f}" for item in neg) or "",
                len(zero),
                "; ".join(f"{item['time']} vol={item['volume']:.0f}" for item in zero) or "",
            ]
        )
    blocks.append(
        md_table(
            ["symbol", "n_neg_shown", "negative_volume_examples", "n_zero_shown", "zero_volume_examples"],
            rows,
        )
    )

    blocks.append("## gap width quantiles (pooled, by period)")
    qs = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    rows = []
    for period in period_names + ["all"]:
        pool: list[float] = []
        for symbol in symbols:
            pool.extend(g["width_pips"] for g in period_slice(report["symbols"][symbol]["gap_events"], period))
        qmap = quantile_map(pool, [float(q) for q in qs])
        rows.append(
            [
                period,
                f"{len(pool):,}",
                *[f"{qmap[float(q)]:.2f}" if qmap[float(q)] is not None else "" for q in qs],
                f"{max(pool):.2f}" if pool else "",
                sum(1 for v in pool if v >= 10.0),
                sum(1 for v in pool if v >= 25.0),
            ]
        )
    blocks.append(
        md_table(
            ["period", "n", *[f"p{q}" for q in qs], "max", "n_ge10", "n_ge25"], rows
        )
    )

    blocks.append("## gap width quantiles per symbol (all parsed dates)")
    rows = []
    for symbol in symbols:
        gaps = period_slice(report["symbols"][symbol]["gap_events"], "all")
        pool = [g["width_pips"] for g in gaps]
        qmap = quantile_map(pool, [50.0, 75.0, 90.0, 99.0])
        partial = sum(1 for g in gaps if g["n_m1_gap_bar"] < 5)
        rows.append(
            [
                symbol,
                f"{len(gaps):,}",
                f"{qmap[50.0]:.2f}" if qmap[50.0] is not None else "",
                f"{qmap[75.0]:.2f}" if qmap[75.0] is not None else "",
                f"{qmap[90.0]:.2f}" if qmap[90.0] is not None else "",
                f"{qmap[99.0]:.2f}" if qmap[99.0] is not None else "",
                f"{max(pool):.2f}" if pool else "",
                partial,
                sum(1 for g in gaps if g["direction"] == "up"),
                sum(1 for g in gaps if g["direction"] == "down"),
            ]
        )
    blocks.append(
        md_table(
            [
                "symbol",
                "n_gap",
                "p50",
                "p75",
                "p90",
                "p99",
                "max",
                "gap_bars_with_n_m1_lt_5",
                "n_up",
                "n_down",
            ],
            rows,
        )
    )

    blocks.append("## gap width median/p90 by symbol x protocol period")
    rows = []
    for symbol in symbols:
        row: list[Any] = [symbol]
        for period in ["training", "validation", "final_confirmation"]:
            gaps = period_slice(report["symbols"][symbol]["gap_events"], period)
            pool = [g["width_pips"] for g in gaps]
            qmap = quantile_map(pool, [50.0, 90.0])
            row.extend(
                [
                    len(pool),
                    f"{qmap[50.0]:.2f}" if qmap[50.0] is not None else "",
                    f"{qmap[90.0]:.2f}" if qmap[90.0] is not None else "",
                ]
            )
        rows.append(row)
    blocks.append(
        md_table(
            [
                "symbol",
                "train_n",
                "train_p50",
                "train_p90",
                "valid_n",
                "valid_p50",
                "valid_p90",
                "final_n",
                "final_p50",
                "final_p90",
            ],
            rows,
        )
    )

    def matrix(key_fn, labels, title, source="gap_events"):
        blocks.append(title)
        rows = []
        for label in labels:
            row = [label]
            total = 0
            for symbol in symbols:
                count = sum(1 for g in report["symbols"][symbol][source] if key_fn(g) == label)
                row.append(count)
                total += count
            row.append(total)
            rows.append(row)
        blocks.append(md_table(["bucket", *symbols, "TOTAL"], rows))

    years = sorted({g["gap_bar_time"].year for symbol in symbols for g in report["symbols"][symbol]["gap_events"]})
    matrix(lambda g: g["gap_bar_time"].year, years, "## gap counts by year x symbol")
    matrix(lambda g: WEEKDAYS[g["gap_bar_time"].weekday()], WEEKDAYS, "## gap counts by weekday x symbol")
    matrix(lambda g: g["gap_bar_time"].hour, list(range(24)), "## gap counts by hour (gap bar) x symbol")
    matrix(
        lambda g: WEEKDAYS[g["bar_time"].weekday()],
        WEEKDAYS,
        "## M5 steps of 30-119 min by weekday x symbol",
        source="medium_steps",
    )
    matrix(
        lambda g: g["bar_time"].hour,
        list(range(24)),
        "## M5 steps of 30-119 min by hour x symbol",
        source="medium_steps",
    )

    blocks.append("## aggregation verification (2024-01-01..2024-03-31)")
    rows = []
    for item in report["verification"]["aggregation"]:
        rows.append(
            [
                item["symbol"],
                item["window"][0],
                item["window"][1],
                item["mine_bars"],
                item["repository_bars"],
                item["time_mismatch"],
                item["price_mismatch"],
                item["volume_mismatch"],
                item["partial_buckets_mine"],
                item["partial_buckets_matched"],
                item.get("length_mismatch", 0),
                json.dumps(item["first_mismatch"], ensure_ascii=False),
            ]
        )
    blocks.append(
        md_table(
            [
                "symbol",
                "window_start",
                "window_end",
                "mine",
                "repository",
                "time_mismatch",
                "price_mismatch",
                "volume_mismatch",
                "partial_buckets",
                "partial_matched",
                "length_mismatch",
                "first_mismatch",
            ],
            rows,
        )
    )
    blocks.append("## end-inclusive probe")
    blocks.append(
        md_table(
            ["symbol", "probe_time", "bars_returned", "time_returned"],
            [
                [i["symbol"], i["probe_time"], i["bars_returned"], i["time_returned"]]
                for i in report["verification"]["end_inclusive"]
            ],
        )
    )

    path = run_dir / "data_ledger_tables.md"
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--no-hash", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="smoke test only: parse at most N M1 records per symbol",
    )
    parser.add_argument("--run-dir", default=str(RUN_DIR))
    parser.add_argument("--verify-symbols", nargs="*", default=["USDJPY", "EURUSD", "GBPJPY"])
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    repo = HistoryRepository()

    availability = repo.symbols()
    report: dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "script": "scripts/data_gap_fill_m5_ledger.py",
        "history_root": str(repo.root),
        "history_root_exists": repo.root.is_dir(),
        "available_symbols": availability,
        "requested_symbols": args.symbols,
        "missing_symbols": [s for s in args.symbols if s not in availability],
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "constants": {
            "record_size": RECORD_SIZE,
            "m5_seconds": M5_SECONDS,
            "gap_min_minutes": GAP_MIN_MINUTES,
            "width_levels_pips": list(WIDTH_LEVELS),
            "periods": [[name, iso(start), iso(end)] for name, start, end in PERIODS],
            "protocol_final_end": iso(PROTOCOL_FINAL_END),
        },
        "symbols": {},
        "verification": {"aggregation": [], "end_inclusive": []},
    }

    for symbol in args.symbols:
        if symbol not in availability:
            print(f"[skip] {symbol}: not in repository", flush=True)
            continue
        print(f"[scan] {symbol} ...", flush=True)
        try:
            data = scan_symbol(repo, symbol, do_hash=not args.no_hash, limit_records=args.limit)
        except Exception as exc:  # noqa: BLE001
            report["symbols"][symbol] = {"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"}
            print(f"[fail] {symbol}: {type(exc).__name__}: {exc}", flush=True)
            continue
        report["symbols"][symbol] = data
        csv_path = run_dir / f"gap_events_{symbol}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "symbol",
                    "gap_bar_time",
                    "prev_bar_time",
                    "gap_minutes",
                    "width_pips",
                    "direction",
                    "open",
                    "prev_close",
                    "n_m1_gap_bar",
                    "period",
                    "in_protocol_final_window",
                ]
            )
            for row in data["gap_events"]:
                writer.writerow(
                    [
                        row["symbol"],
                        row["gap_bar_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        row["prev_bar_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        f"{row['gap_minutes']:.1f}",
                        f"{row['width_pips']:.4f}",
                        row["direction"],
                        f"{row['open']:.6f}",
                        f"{row['prev_close']:.6f}",
                        row["n_m1_gap_bar"],
                        row["period"],
                        int(row["in_protocol_final_window"]),
                    ]
                )
        print(
            f"[done] {symbol}: M1={data['summary']['bar_count_from_repository']:,} "
            f"M5={data['m5']['buckets']:,} gaps={len(data['gap_events']):,} "
            f"steps30-119={data['m5']['steps_30_119_count']:,} "
            f"{data['elapsed_seconds']}s",
            flush=True,
        )
        with (run_dir / f"m5_steps_ge30min_{symbol}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(["symbol", "bar_time", "prev_bar_time", "minutes", "n_m1", "class"])
            for row in data["medium_steps"]:
                writer.writerow(
                    [
                        row["symbol"],
                        row["bar_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        row["prev_bar_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        f"{row['minutes']:.1f}",
                        row["n_m1"],
                        "30-119min",
                    ]
                )
            for row in data["gap_events"]:
                writer.writerow(
                    [
                        row["symbol"],
                        row["gap_bar_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        row["prev_bar_time"].strftime("%Y-%m-%d %H:%M:%S"),
                        f"{row['gap_minutes']:.1f}",
                        row["n_m1_gap_bar"],
                        "ge120min",
                    ]
                )

    for symbol in args.verify_symbols:
        if symbol not in report["symbols"] or "error" in report["symbols"][symbol]:
            continue
        print(f"[verify] {symbol} aggregation ...", flush=True)
        report["verification"]["aggregation"].append(
            verify_aggregation(
                repo,
                symbol,
                datetime(2024, 1, 1, 0, 0),
                datetime(2024, 3, 31, 23, 59),
            )
        )
        raw = list(
            repo.bars(
                symbol,
                start=datetime(2024, 3, 5, 12, 0),
                end=datetime(2024, 3, 5, 13, 0),
                timeframe="1m",
            )
        )
        if raw:
            report["verification"]["end_inclusive"].append(end_inclusive_probe(repo, symbol, raw[0].time))

    json_path = run_dir / "data_ledger.json"
    with json_path.open("w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=1, default=str)
    print(f"[wrote] {json_path}", flush=True)
    tables_path = write_tables(report, run_dir)
    print(f"[wrote] {tables_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
