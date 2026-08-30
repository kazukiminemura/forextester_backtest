"""Validate confirmed 4H trend filters for the 15m Yosuga Dow indicator."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_yosuga_dow_filters import (
    MIN_TRAIN_TRADES,
    MIN_VALIDATION_TRADES,
    Prepared,
    Trade,
    _eligible,
    _ema,
    _confirmed_pivots,
    _passes_unseen_periods,
    _period_stats,
    _prepare,
    _selection_score,
    _simulate,
    _sma,
)


HTF_LENGTHS = (10, 20, 50)
MODES = ("price", "slope", "price_and_slope")


@dataclass(frozen=True, slots=True)
class HtfCandidate:
    average_kind: str
    length: int
    mode: str

    @property
    def name(self) -> str:
        if self.average_kind == "dow":
            return f"confirmed_4h_dow_pivot{self.length}"
        return f"confirmed_4h_{self.average_kind}{self.length}_{self.mode}"


@dataclass(frozen=True, slots=True)
class ConfirmedHtf:
    close: np.ndarray
    average: np.ndarray
    previous_average: np.ndarray


def _completed_four_hour_features(
    data: Prepared, average_kind: str, length: int
) -> ConfirmedHtf:
    """Map only the previous completed 4H bar to every 15m bar."""
    epoch = datetime(1899, 12, 30)
    buckets = np.asarray(
        [int((time - epoch).total_seconds()) // 14_400 for time in data.times],
        dtype=np.int64,
    )
    _unique_buckets, group_for_bar = np.unique(buckets, return_inverse=True)
    group_count = int(group_for_bar[-1]) + 1 if group_for_bar.size else 0
    group_close = np.full(group_count, np.nan)
    for bar_index, group_raw in enumerate(group_for_bar):
        group_close[int(group_raw)] = data.close[bar_index]
    group_average = (
        _ema(group_close, length)
        if average_kind == "ema"
        else _sma(group_close, length)
    )
    completed_close = np.full(data.close.size, np.nan)
    completed_average = np.full(data.close.size, np.nan)
    previous_average = np.full(data.close.size, np.nan)
    for bar_index, group_raw in enumerate(group_for_bar):
        completed_group = int(group_raw) - 1
        if completed_group < 0:
            continue
        completed_close[bar_index] = group_close[completed_group]
        completed_average[bar_index] = group_average[completed_group]
        if completed_group > 0:
            previous_average[bar_index] = group_average[completed_group - 1]
    return ConfirmedHtf(completed_close, completed_average, previous_average)


def _four_hour_groups(
    data: Prepared,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    epoch = datetime(1899, 12, 30)
    buckets = np.asarray(
        [int((time - epoch).total_seconds()) // 14_400 for time in data.times],
        dtype=np.int64,
    )
    _unique_buckets, group_for_bar = np.unique(buckets, return_inverse=True)
    group_count = int(group_for_bar[-1]) + 1 if group_for_bar.size else 0
    group_high = np.full(group_count, -np.inf)
    group_low = np.full(group_count, np.inf)
    group_close = np.full(group_count, np.nan)
    for bar_index, group_raw in enumerate(group_for_bar):
        group = int(group_raw)
        group_high[group] = max(group_high[group], data.high[bar_index])
        group_low[group] = min(group_low[group], data.low[bar_index])
        group_close[group] = data.close[bar_index]
    return buckets, group_for_bar, group_high, group_low, group_close


def _completed_four_hour_dow_trend(
    data: Prepared, pivot_bars: int
) -> np.ndarray:
    """Map the previous completed 4H Dow-break direction to each 15m bar."""
    _buckets, group_for_bar, high, low, close = _four_hour_groups(data)
    pivot_high = _confirmed_pivots(high, pivot_bars, pivot_bars, high=True)
    pivot_low = _confirmed_pivots(low, pivot_bars, pivot_bars, high=False)
    group_trend = np.zeros(close.size, dtype=np.int8)
    last_high = np.nan
    last_low = np.nan
    trend = 0
    for group in range(close.size):
        previous_high = last_high
        previous_low = last_low
        if not np.isnan(pivot_high[group]):
            last_high = float(pivot_high[group])
        if not np.isnan(pivot_low[group]):
            last_low = float(pivot_low[group])
        if group > 0:
            crossed_high = (
                not np.isnan(last_high)
                and not np.isnan(previous_high)
                and close[group] > last_high
                and close[group - 1] <= previous_high
            )
            crossed_low = (
                not np.isnan(last_low)
                and not np.isnan(previous_low)
                and close[group] < last_low
                and close[group - 1] >= previous_low
            )
            if crossed_high and trend <= 0:
                trend = 1
            if crossed_low and trend >= 0:
                trend = -1
        group_trend[group] = trend
    completed_trend = np.zeros(data.close.size, dtype=np.int8)
    for bar_index, group_raw in enumerate(group_for_bar):
        completed_group = int(group_raw) - 1
        if completed_group >= 0:
            completed_trend[bar_index] = group_trend[completed_group]
    return completed_trend


def _htf_allowed(
    direction: int,
    index: int,
    features: ConfirmedHtf,
    mode: str,
) -> bool:
    average = features.average[index]
    previous = features.previous_average[index]
    close = features.close[index]
    if np.isnan(average) or np.isnan(previous) or np.isnan(close):
        return False
    price_ok = direction * (close - average) > 0
    slope_ok = direction * (average - previous) > 0
    if mode == "price":
        return bool(price_ok)
    if mode == "slope":
        return bool(slope_ok)
    return bool(price_ok and slope_ok)


def _simulate_htf_entry_only(
    data: Prepared,
    cost_pct: float,
    candidate: HtfCandidate,
) -> list[Trade]:
    features = None
    dow_trend = None
    if candidate.average_kind == "dow":
        dow_trend = _completed_four_hour_dow_trend(data, candidate.length)
    else:
        features = _completed_four_hour_features(
            data, candidate.average_kind, candidate.length
        )
    position = 0
    ltf_trend = 0
    entry_index = -1
    entry_price = np.nan
    trades: list[Trade] = []
    for index, direction in data.cross_events:
        if direction == ltf_trend:
            continue
        ltf_trend = direction
        if position == -direction and entry_index >= 0:
            raw_return = direction * (entry_price - data.close[index]) / entry_price
            trades.append(
                Trade(
                    data.times[entry_index],
                    data.times[index],
                    position,
                    float(raw_return * 100.0 - cost_pct),
                )
            )
            position = 0
            entry_index = -1
            entry_price = np.nan
        trend_allowed = (
            direction == int(dow_trend[index])
            if dow_trend is not None
            else _htf_allowed(direction, index, features, candidate.mode)
        )
        if position == 0 and trend_allowed:
            position = direction
            entry_index = index
            entry_price = data.close[index]
    return trades


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_dow_htf_filter_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    print(f"Loading {args.symbol} 15m...", file=sys.stderr, flush=True)
    data = _prepare(repository, args.symbol, end)
    baseline = _period_stats(_simulate(data, args.cost_pct))
    rows: list[dict[str, object]] = []
    for average_kind in ("ema", "sma"):
        for length in HTF_LENGTHS:
            for mode in MODES:
                candidate = HtfCandidate(average_kind, length, mode)
                periods = _period_stats(
                    _simulate_htf_entry_only(data, args.cost_pct, candidate)
                )
                rows.append(
                    {
                        "candidate": asdict(candidate),
                        "name": candidate.name,
                        "periods": periods,
                        "eligible": _eligible(periods),
                    }
                )
    for pivot_bars in (2, 3, 5, 8, 10):
        candidate = HtfCandidate("dow", pivot_bars, "trend")
        periods = _period_stats(
            _simulate_htf_entry_only(data, args.cost_pct, candidate)
        )
        rows.append(
            {
                "candidate": asdict(candidate),
                "name": candidate.name,
                "periods": periods,
                "eligible": _eligible(periods),
            }
        )
    eligible = [row for row in rows if bool(row["eligible"])]
    selected = (
        max(eligible, key=lambda row: _selection_score(row["periods"]))
        if eligible
        else None
    )
    adopted = (
        selected
        if selected and _passes_unseen_periods(selected["periods"])
        else None
    )
    payload = {
        "strategy": {
            "symbol": args.symbol,
            "entry_timeframe": "15m",
            "trend_timeframe": "4h",
            "trend_source": "previous completed 4H bar only",
            "filter_scope": "entries only; every opposite 15m Dow signal still exits",
            "round_trip_cost_pct": args.cost_pct,
        },
        "selection_rule": {
            "minimum_train_trades": MIN_TRAIN_TRADES,
            "minimum_validation_trades": MIN_VALIDATION_TRADES,
            "selection_periods": ["train_2004_2018", "validation_2019_2022"],
            "unseen_periods": ["holdout_2023_2024", "true_oos_2025_2026"],
        },
        "baseline": baseline,
        "candidates": rows,
        "selected_by_train_validation": selected,
        "adopted": adopted,
        "adoption_reason": (
            "selected 4H filter stayed positive in both unseen periods"
            if adopted
            else "no train/validation-selected 4H filter stayed positive in both unseen periods"
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload["adopted"], ensure_ascii=False, indent=2))
    return 0 if adopted else 2


if __name__ == "__main__":
    raise SystemExit(main())
