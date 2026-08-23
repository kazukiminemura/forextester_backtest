"""Research 15-minute retest entries after confirmed 4H wall breaks."""

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
from research_4h_wall_breakout import (
    PERIODS,
    SYMBOLS,
    FourHourWalls,
    Trade,
    _break_signals,
    _candidate_score,
    _confirmed_four_hour_walls,
    _passes,
    _period_rows,
    _stats,
)
from research_strict_rr_portfolio import Prepared, _prepare


@dataclass(frozen=True, slots=True)
class Candidate:
    pivot_bars: int
    break_buffer_atr: float
    retest_window_bars: int
    retest_tolerance_atr: float
    stop_mode: str
    friday_cutoff_hour: int = 24


@dataclass(frozen=True, slots=True)
class RetestSignal:
    index: int
    direction: int
    wall: float


def _candidate_grid(friday_cutoff_hours: tuple[int, ...] = (24,)) -> list[Candidate]:
    return [
        Candidate(
            pivot_bars, break_buffer, window, tolerance, stop_mode, friday_cutoff
        )
        for pivot_bars, break_buffer, window, tolerance, stop_mode, friday_cutoff in product(
            (3, 5),
            (0.0, 0.10),
            (8, 16, 32),
            (0.10, 0.20),
            ("retest", "atr"),
            friday_cutoff_hours,
        )
    ]


def _retest_signals(
    data: Prepared, walls: FourHourWalls, candidate: Candidate
) -> list[RetestSignal]:
    """Return the first confirmed retest after each unique broken wall."""
    break_indices, directions = _break_signals(
        data, walls, candidate.break_buffer_atr
    )
    signals: list[RetestSignal] = []
    armed_walls: set[tuple[int, float]] = set()
    for break_raw, direction_raw in zip(break_indices, directions, strict=True):
        break_index = int(break_raw)
        direction = int(direction_raw)
        wall = float(
            walls.high[break_index] if direction == 1 else walls.low[break_index]
        )
        wall_key = (direction, wall)
        if wall_key in armed_walls:
            continue
        armed_walls.add(wall_key)
        start = break_index + 1
        end = min(data.close.size, start + candidate.retest_window_bars)
        if start >= end:
            continue
        tolerance = data.atr[start:end] * candidate.retest_tolerance_atr
        if direction == 1:
            confirmed = (
                (data.low[start:end] <= wall + tolerance)
                & (data.close[start:end] > wall)
                & (data.close[start:end] > data.open[start:end])
            )
        else:
            confirmed = (
                (data.high[start:end] >= wall - tolerance)
                & (data.close[start:end] < wall)
                & (data.close[start:end] < data.open[start:end])
            )
        matches = np.flatnonzero(confirmed)
        if matches.size:
            signals.append(
                RetestSignal(start + int(matches[0]), direction, wall)
            )
    signals.sort(key=lambda signal: signal.index)
    return signals


def _simulate(
    symbol: str,
    data: Prepared,
    walls: FourHourWalls,
    candidate: Candidate,
    signals: list[RetestSignal] | None = None,
) -> list[Trade]:
    trades: list[Trade] = []
    next_available_index = 0
    if signals is None:
        signals = _retest_signals(data, walls, candidate)
    for signal in signals:
        entry_index = signal.index + 1
        if entry_index < next_available_index or entry_index >= data.close.size:
            continue
        entry_time = data.times[entry_index]
        if entry_time.weekday() == 4 and entry_time.hour >= candidate.friday_cutoff_hour:
            continue
        atr = float(data.atr[signal.index])
        if not np.isfinite(atr) or atr <= 0:
            continue
        if signal.direction == 1:
            entry = float(data.open[entry_index] + data.spread)
            if candidate.stop_mode == "retest":
                stop = float(
                    min(signal.wall, data.low[signal.index]) - 0.10 * atr
                )
            else:
                stop = float(data.close[signal.index] - 2.0 * atr)
            risk = entry - stop
            target = entry + risk
            stop_hits = data.low[entry_index:] <= stop
            target_hits = data.high[entry_index:] >= target
        else:
            entry = float(data.open[entry_index])
            if candidate.stop_mode == "retest":
                stop = float(
                    max(signal.wall, data.high[signal.index])
                    + 0.10 * atr
                    + data.spread
                )
            else:
                stop = float(
                    data.close[signal.index] + 2.0 * atr + data.spread
                )
            risk = stop - entry
            target = entry - risk
            stop_hits = data.high[entry_index:] + data.spread >= stop
            target_hits = data.low[entry_index:] + data.spread <= target
        # Exclude invalid gaps and excessively wide structural stops.
        if risk <= 0 or risk > 2.5 * atr:
            continue
        resolved = np.flatnonzero(stop_hits | target_hits)
        if resolved.size == 0:
            continue
        offset = int(resolved[0])
        exit_index = entry_index + offset
        hit_stop = bool(stop_hits[offset])
        hit_target = bool(target_hits[offset])
        trades.append(
            Trade(
                symbol=symbol,
                entry_time=entry_time,
                result_r=-1.0 if hit_stop else 1.0,
                direction=signal.direction,
                ambiguous_bar=hit_stop and hit_target,
                hold_bars=exit_index - entry_index + 1,
            )
        )
        next_available_index = exit_index + 1
    return trades


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output", type=Path, default=Path("scripts/4h_wall_retest_results.json")
    )
    parser.add_argument(
        "--friday-cutoffs",
        nargs="+",
        type=int,
        default=[24],
        help="Friday entry cutoff hours in raw Forex Tester data time; 24 disables",
    )
    args = parser.parse_args()
    if any(hour < 0 or hour > 24 for hour in args.friday_cutoffs):
        parser.error("--friday-cutoffs must be between 0 and 24")

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    prepared: dict[str, Prepared] = {}
    wall_cache: dict[tuple[str, int], FourHourWalls] = {}
    signal_cache: dict[
        tuple[str, int, float, int, float], list[RetestSignal]
    ] = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        for pivot_bars in (3, 5):
            wall_cache[(symbol, pivot_bars)] = _confirmed_four_hour_walls(
                prepared[symbol], pivot_bars
            )

    candidate_summaries = []
    for candidate in _candidate_grid(tuple(dict.fromkeys(args.friday_cutoffs))):
        rows: list[Trade] = []
        per_symbol = {}
        for symbol in SYMBOLS:
            signal_key = (
                symbol,
                candidate.pivot_bars,
                candidate.break_buffer_atr,
                candidate.retest_window_bars,
                candidate.retest_tolerance_atr,
            )
            if signal_key not in signal_cache:
                signal_cache[signal_key] = _retest_signals(
                    prepared[symbol],
                    wall_cache[(symbol, candidate.pivot_bars)],
                    candidate,
                )
            symbol_rows = _simulate(
                symbol,
                prepared[symbol],
                wall_cache[(symbol, candidate.pivot_bars)],
                candidate,
                signal_cache[signal_key],
            )
            rows.extend(symbol_rows)
            per_symbol[symbol] = {
                name: _stats(_period_rows(symbol_rows, start, end_year), months)
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
                "per_symbol": per_symbol,
                "train_pass": _passes(periods["train_2010_2018"]),
                "validation_pass": _passes(periods["validation_2019_2022"]),
                "holdout_pass": _passes(periods["holdout_2023_2024"]),
                "true_oos_pass": _passes(periods["true_oos_2025_2026"]),
            }
        )

    selected = max(
        candidate_summaries, key=lambda item: _candidate_score(item["periods"])
    )
    payload = {
        "strategy": {
            "signal_timeframe": "15m",
            "trend_timeframe": "4h",
            "entry": (
                "after a trend-direction 4H wall break, first wall retest that "
                "closes back on the breakout side with matching candle direction; "
                "enter next 15m open"
            ),
            "exit": "full exit at strict RR 1:1; same-bar ambiguity is loss",
            "one_attempt_per_wall": True,
            "atr_stop_multiple": 2.0,
            "retest_stop_buffer_atr": 0.10,
            "maximum_risk_atr": 2.5,
            "friday_cutoff_hours_tested": list(
                dict.fromkeys(args.friday_cutoffs)
            ),
            "symbols": list(SYMBOLS),
            "missing_watchlist_history": ["CADJPY", "EURAUD", "AUDNZD"],
        },
        "selection_rule": (
            "rank on train and validation only; holdout and true OOS are not used "
            "to select the candidate"
        ),
        "selected": selected,
        "selected_per_symbol": selected["per_symbol"],
        "all_candidates": candidate_summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
