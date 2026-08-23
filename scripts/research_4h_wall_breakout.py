"""Research 15-minute entries on confirmed 4H wall breaks under strict RR 1:1."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_strict_rr_portfolio import Prepared, _is_pivot, _prepare


SYMBOLS = (
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "EURJPY",
    "GBPJPY",
    "NZDJPY",
    "NZDUSD",
    "AUDJPY",
    "USDCHF",
    "EURCHF",
    "GBPCHF",
    "EURGBP",
)
PERIODS = {
    "train_2010_2018": (2010, 2018, 108),
    "validation_2019_2022": (2019, 2022, 48),
    "holdout_2023_2024": (2023, 2024, 24),
    "true_oos_2025_2026": (2025, 2026, 19),
}


@dataclass(frozen=True, slots=True)
class Candidate:
    pivot_bars: int
    break_buffer_atr: float
    stop_atr: float


@dataclass(frozen=True, slots=True)
class Trade:
    symbol: str
    entry_time: datetime
    result_r: float
    direction: int
    ambiguous_bar: bool
    hold_bars: int


@dataclass(slots=True)
class FourHourWalls:
    trend: np.ndarray
    high: np.ndarray
    low: np.ndarray


def _four_hour_groups(data: Prepared) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    starts: list[datetime] = []
    highs: list[float] = []
    lows: list[float] = []
    group_for_bar = np.empty(len(data.times), dtype=np.int32)
    for index, time in enumerate(data.times):
        start = time.replace(
            hour=(time.hour // 4) * 4, minute=0, second=0, microsecond=0
        )
        if not starts or start != starts[-1]:
            starts.append(start)
            highs.append(float(data.high[index]))
            lows.append(float(data.low[index]))
        else:
            highs[-1] = max(highs[-1], float(data.high[index]))
            lows[-1] = min(lows[-1], float(data.low[index]))
        group_for_bar[index] = len(starts) - 1
    return np.asarray(highs), np.asarray(lows), group_for_bar


def _confirmed_four_hour_walls(data: Prepared, pivot_bars: int) -> FourHourWalls:
    """Map only previously confirmed 4H pivots onto each 15-minute bar."""
    htf_high, htf_low, group_for_bar = _four_hour_groups(data)
    group_trend = np.zeros(htf_high.size, dtype=np.int8)
    group_wall_high = np.full(htf_high.size, np.nan)
    group_wall_low = np.full(htf_low.size, np.nan)
    confirmed_highs: list[tuple[int, float]] = []
    confirmed_lows: list[tuple[int, float]] = []
    trend = 0
    for group_index in range(htf_high.size):
        # The current 4H group is still open. Only its predecessor and older
        # groups may confirm a pivot, matching request.security(...)[1].
        confirmed_index = group_index - 1
        if confirmed_index >= 0:
            high_pivot = _is_pivot(
                htf_high, confirmed_index, pivot_bars, pivot_bars, True
            )
            low_pivot = _is_pivot(
                htf_low, confirmed_index, pivot_bars, pivot_bars, False
            )
            if high_pivot is not None:
                confirmed_highs.append(high_pivot)
            if low_pivot is not None:
                confirmed_lows.append(low_pivot)
            if len(confirmed_highs) >= 2 and len(confirmed_lows) >= 2:
                if (
                    confirmed_highs[-1][1] > confirmed_highs[-2][1]
                    and confirmed_lows[-1][1] > confirmed_lows[-2][1]
                ):
                    trend = 1
                elif (
                    confirmed_highs[-1][1] < confirmed_highs[-2][1]
                    and confirmed_lows[-1][1] < confirmed_lows[-2][1]
                ):
                    trend = -1
                else:
                    trend = 0
        group_trend[group_index] = trend
        if confirmed_highs:
            group_wall_high[group_index] = confirmed_highs[-1][1]
        if confirmed_lows:
            group_wall_low[group_index] = confirmed_lows[-1][1]
    return FourHourWalls(
        trend=group_trend[group_for_bar],
        high=group_wall_high[group_for_bar],
        low=group_wall_low[group_for_bar],
    )


def _break_signals(
    data: Prepared, walls: FourHourWalls, break_buffer_atr: float
) -> tuple[np.ndarray, np.ndarray]:
    previous_close = np.roll(data.close, 1)
    previous_atr = np.roll(data.atr, 1)
    previous_high_wall = np.roll(walls.high, 1)
    previous_low_wall = np.roll(walls.low, 1)
    previous_close[0] = np.nan
    previous_atr[0] = np.nan
    same_high_wall = walls.high == previous_high_wall
    same_low_wall = walls.low == previous_low_wall
    long_level = walls.high + data.atr * break_buffer_atr
    previous_long_level = previous_high_wall + previous_atr * break_buffer_atr
    short_level = walls.low - data.atr * break_buffer_atr
    previous_short_level = previous_low_wall - previous_atr * break_buffer_atr
    long_signal = (
        (walls.trend == 1)
        & same_high_wall
        & np.isfinite(long_level)
        & (previous_close <= previous_long_level)
        & (data.close > long_level)
    )
    short_signal = (
        (walls.trend == -1)
        & same_low_wall
        & np.isfinite(short_level)
        & (previous_close >= previous_short_level)
        & (data.close < short_level)
    )
    indices = np.flatnonzero(long_signal | short_signal)
    directions = np.where(long_signal[indices], 1, -1).astype(np.int8)
    return indices, directions


def _simulate(
    symbol: str,
    data: Prepared,
    walls: FourHourWalls,
    candidate: Candidate,
) -> list[Trade]:
    indices, directions = _break_signals(data, walls, candidate.break_buffer_atr)
    trades: list[Trade] = []
    used_walls: set[tuple[int, float]] = set()
    next_available_index = 0
    for signal_index_raw, direction_raw in zip(indices, directions, strict=True):
        signal_index = int(signal_index_raw)
        direction = int(direction_raw)
        entry_index = signal_index + 1
        if entry_index < next_available_index or entry_index >= data.close.size:
            continue
        if not np.isfinite(data.atr[signal_index]):
            continue
        wall = walls.high[signal_index] if direction == 1 else walls.low[signal_index]
        wall_key = (direction, float(wall))
        if wall_key in used_walls:
            continue
        if direction == 1:
            entry = float(data.open[entry_index] + data.spread)
            stop = float(data.close[signal_index] - data.atr[signal_index] * candidate.stop_atr)
            risk = entry - stop
            target = entry + risk
            stop_hits = data.low[entry_index:] <= stop
            target_hits = data.high[entry_index:] >= target
        else:
            entry = float(data.open[entry_index])
            stop = float(
                data.close[signal_index]
                + data.atr[signal_index] * candidate.stop_atr
                + data.spread
            )
            risk = stop - entry
            target = entry - risk
            stop_hits = data.high[entry_index:] + data.spread >= stop
            target_hits = data.low[entry_index:] + data.spread <= target
        if risk <= 0:
            continue
        resolved = np.flatnonzero(stop_hits | target_hits)
        if resolved.size == 0:
            continue
        exit_index = entry_index + int(resolved[0])
        hit_stop = bool(stop_hits[resolved[0]])
        hit_target = bool(target_hits[resolved[0]])
        trades.append(
            Trade(
                symbol=symbol,
                entry_time=data.times[entry_index],
                result_r=-1.0 if hit_stop else 1.0,
                direction=direction,
                ambiguous_bar=hit_stop and hit_target,
                hold_bars=exit_index - entry_index + 1,
            )
        )
        used_walls.add(wall_key)
        next_available_index = exit_index + 1
    return trades


def _stats(rows: list[Trade], months: int) -> dict[str, float | int | None]:
    wins = sum(trade.result_r > 0 for trade in rows)
    losses = len(rows) - wins
    ambiguous = sum(trade.ambiguous_bar for trade in rows)
    return {
        "trades": len(rows),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(rows) * 100.0 if rows else 0.0,
        "profit_factor": wins / losses if losses else None,
        "expectancy_r": (wins - losses) / len(rows) if rows else 0.0,
        "trades_per_month": len(rows) / months,
        "ambiguous_bars": ambiguous,
        "average_hold_bars": (
            sum(trade.hold_bars for trade in rows) / len(rows) if rows else 0.0
        ),
    }


def _period_rows(rows: list[Trade], start: int, end: int) -> list[Trade]:
    return [trade for trade in rows if start <= trade.entry_time.year <= end]


def _passes(stats: dict[str, float | int | None]) -> bool:
    return (
        float(stats["profit_factor"] or 0.0) >= 1.15
        and float(stats["expectancy_r"]) > 0.0
        and float(stats["trades_per_month"]) >= 3.0
    )


def _candidate_score(periods: dict[str, dict[str, float | int | None]]) -> tuple:
    train = periods["train_2010_2018"]
    validation = periods["validation_2019_2022"]
    train_pf = float(train["profit_factor"] or 0.0)
    validation_pf = float(validation["profit_factor"] or 0.0)
    return (
        _passes(train) and _passes(validation),
        min(train_pf, validation_pf),
        min(float(train["expectancy_r"]), float(validation["expectancy_r"])),
        int(train["trades"]) + int(validation["trades"]),
    )


def _candidate_grid() -> list[Candidate]:
    return [
        Candidate(pivot_bars, break_buffer_atr, stop_atr)
        for pivot_bars, break_buffer_atr, stop_atr in product(
            (2, 3, 5), (0.0, 0.05, 0.10), (1.0, 1.5, 2.0)
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output", type=Path, default=Path("scripts/4h_wall_breakout_results.json")
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    prepared: dict[str, Prepared] = {}
    wall_cache: dict[tuple[str, int], FourHourWalls] = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        for pivot_bars in (2, 3, 5):
            wall_cache[(symbol, pivot_bars)] = _confirmed_four_hour_walls(
                prepared[symbol], pivot_bars
            )

    candidate_summaries = []
    for candidate in _candidate_grid():
        rows: list[Trade] = []
        per_symbol_periods = {}
        for symbol in SYMBOLS:
            symbol_rows = _simulate(
                symbol,
                prepared[symbol],
                wall_cache[(symbol, candidate.pivot_bars)],
                candidate,
            )
            rows.extend(symbol_rows)
            per_symbol_periods[symbol] = {
                name: _stats(
                    _period_rows(symbol_rows, start, end_year), months
                )
                for name, (start, end_year, months) in PERIODS.items()
            }
        periods = {
            name: _stats(_period_rows(rows, start, end_year), months)
            for name, (start, end_year, months) in PERIODS.items()
        }
        candidate_summaries.append(
            {
                "candidate": asdict(candidate),
                "periods": periods,
                "per_symbol": per_symbol_periods,
                "train_pass": _passes(periods["train_2010_2018"]),
                "validation_pass": _passes(periods["validation_2019_2022"]),
                "holdout_pass": _passes(periods["holdout_2023_2024"]),
                "true_oos_pass": _passes(periods["true_oos_2025_2026"]),
            }
        )

    selected_summary = max(
        candidate_summaries,
        key=lambda item: _candidate_score(item["periods"]),
    )
    per_symbol = selected_summary["per_symbol"]

    payload = {
        "strategy": {
            "signal_timeframe": "15m",
            "trend_timeframe": "4h",
            "entry": "confirmed close break in 4H trend direction, next 15m open",
            "exit": "full exit at strict RR 1:1; same-bar ambiguity is loss",
            "one_entry_per_wall": True,
            "symbols": list(SYMBOLS),
            "missing_watchlist_history": ["CADJPY", "EURAUD", "AUDNZD"],
        },
        "selection_rule": (
            "rank on train and validation only; holdout and true OOS are not used "
            "to select the candidate"
        ),
        "selected": selected_summary,
        "selected_per_symbol": per_symbol,
        "all_candidates": candidate_summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(selected_summary, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
