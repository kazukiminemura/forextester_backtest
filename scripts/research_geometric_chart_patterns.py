"""Backtest classical triangles, rectangles, and wedges under strict RR1."""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import PERIODS, SYMBOLS, Trade, _period_rows, _stats
from research_classic_chart_patterns import PatternSignal, Pivot, _pivots, _simulate
from research_strict_rr_portfolio import Prepared, _prepare


PATTERNS = (
    "ascending_triangle",
    "descending_triangle",
    "symmetrical_triangle",
    "rectangle",
    "rising_wedge",
    "falling_wedge",
)


@dataclass(frozen=True, slots=True)
class Candidate:
    pivot_bars: int
    flat_tolerance_atr: float
    min_boundary_move_atr: float
    max_pattern_bars: int
    confirmation_bars: int = 48
    stop_buffer_atr: float = 0.10


def _line(items: list[Pivot]) -> tuple[float, float]:
    mean_x = sum(item.index for item in items) / len(items)
    mean_y = sum(item.price for item in items) / len(items)
    denominator = sum((item.index - mean_x) ** 2 for item in items)
    if denominator == 0:
        return 0.0, mean_y
    slope = sum(
        (item.index - mean_x) * (item.price - mean_y) for item in items
    ) / denominator
    return slope, mean_y - slope * mean_x


def _value(line: tuple[float, float], index: int) -> float:
    return line[0] * index + line[1]


def _formation_signal(
    data: Prepared,
    highs: list[Pivot],
    lows: list[Pivot],
    candidate: Candidate,
    end_position: int,
    low_indices: list[int],
) -> PatternSignal | None:
    recent_highs = highs[max(0, end_position - 2) : end_position + 1]
    end_index = recent_highs[-1].index
    low_end = bisect_right(low_indices, end_index)
    if len(recent_highs) < 3 or low_end < 3:
        return None
    recent_lows = lows[low_end - 3 : low_end]
    if recent_lows[-1].index <= recent_highs[0].index or recent_highs[-1].index <= recent_lows[0].index:
        return None
    start_index = min(recent_highs[0].index, recent_lows[0].index)
    formation_end = max(recent_highs[-1].confirmed_at, recent_lows[-1].confirmed_at)
    span = end_index - start_index
    if span <= 0 or span > candidate.max_pattern_bars:
        return None
    atr = float(data.atr[formation_end])
    if not np.isfinite(atr) or atr <= 0:
        return None
    upper = _line(recent_highs)
    lower = _line(recent_lows)
    upper_move = upper[0] * span / atr
    lower_move = lower[0] * span / atr
    flat = candidate.flat_tolerance_atr
    directional = candidate.min_boundary_move_atr
    width_start = _value(upper, start_index) - _value(lower, start_index)
    width_end = _value(upper, formation_end) - _value(lower, formation_end)
    if width_start < atr * 0.75 or width_end <= 0:
        return None
    converging = width_end < width_start * 0.80
    pattern = ""
    direction = 0
    if abs(upper_move) <= flat and lower_move >= directional and converging:
        pattern, direction = "ascending_triangle", 1
    elif abs(lower_move) <= flat and upper_move <= -directional and converging:
        pattern, direction = "descending_triangle", -1
    elif upper_move <= -directional and lower_move >= directional and converging:
        pattern = "symmetrical_triangle"
    elif abs(upper_move) <= flat and abs(lower_move) <= flat:
        pattern = "rectangle"
    elif upper_move > 0 and lower_move > upper_move + directional and converging:
        pattern, direction = "rising_wedge", -1
    elif lower_move < 0 and upper_move < lower_move - directional and converging:
        pattern, direction = "falling_wedge", 1
    else:
        return None
    if pattern in ("symmetrical_triangle", "rectangle"):
        prior_start = max(0, start_index - span)
        prior_move = float(data.close[start_index] - data.close[prior_start])
        if abs(prior_move) < atr * candidate.min_boundary_move_atr:
            return None
        direction = 1 if prior_move > 0 else -1
    start = formation_end + 1
    for index in range(start, min(data.close.size, start + candidate.confirmation_bars)):
        boundary = _value(upper if direction == 1 else lower, index)
        previous_boundary = _value(upper if direction == 1 else lower, index - 1)
        crossed = (
            data.close[index] > boundary >= data.close[index - 1]
            if direction == 1
            else data.close[index] < boundary <= data.close[index - 1]
        )
        if crossed:
            far_boundary = _value(lower if direction == 1 else upper, index)
            stop = far_boundary - candidate.stop_buffer_atr * atr if direction == 1 else far_boundary + candidate.stop_buffer_atr * atr
            return PatternSignal(index, direction, pattern, stop)
    return None


def _signals(
    data: Prepared,
    candidate: Candidate,
    pivots: tuple[list[Pivot], list[Pivot]] | None = None,
) -> list[PatternSignal]:
    highs, lows = pivots or _pivots(data, candidate.pivot_bars)
    rows = []
    low_indices = [pivot.index for pivot in lows]
    for position in range(2, len(highs)):
        signal = _formation_signal(
            data, highs, lows, candidate, position, low_indices
        )
        if signal is not None:
            rows.append(signal)
    rows.sort(key=lambda row: row.index)
    deduplicated = []
    last_index = -candidate.confirmation_bars
    for row in rows:
        if row.index - last_index >= candidate.pivot_bars:
            deduplicated.append(row)
            last_index = row.index
    return deduplicated


def _grid() -> list[Candidate]:
    return [Candidate(*values) for values in product((3, 5), (0.15, 0.30), (0.35, 0.70), (96, 192))]


def _periods(rows: list[Trade]) -> dict:
    return {name: _stats(_period_rows(rows, start, end), months) for name, (start, end, months) in PERIODS.items()}


def _score(periods: dict) -> tuple:
    train, validation = periods["train_2010_2018"], periods["validation_2019_2022"]
    return (min(float(train["expectancy_r"]), float(validation["expectancy_r"])), min(float(train["profit_factor"] or 0), float(validation["profit_factor"] or 0)), int(train["trades"]) + int(validation["trades"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--output", type=Path, default=Path("scripts/geometric_chart_pattern_results.json"))
    args = parser.parse_args()
    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    prepared = {}
    pivot_cache = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        for pivot_bars in (3, 5):
            pivot_cache[(symbol, pivot_bars)] = _pivots(prepared[symbol], pivot_bars)
    summaries = []
    for candidate in _grid():
        rows = []
        by_pattern = {pattern: [] for pattern in PATTERNS}
        for symbol, data in prepared.items():
            signals = _signals(data, candidate, pivot_cache[(symbol, candidate.pivot_bars)])
            symbol_rows = _simulate(symbol, data, signals)
            rows.extend(symbol_rows)
            pattern_by_time = {data.times[signal.index + 1]: signal.pattern for signal in signals if signal.index + 1 < data.close.size}
            for trade in symbol_rows:
                by_pattern[pattern_by_time[trade.entry_time]].append(trade)
        periods = _periods(rows)
        summaries.append({"candidate": asdict(candidate), "periods": periods, "by_pattern": {key: _periods(value) for key, value in by_pattern.items()}, "score": _score(periods)})
    selected = max(summaries, key=lambda item: tuple(item["score"]))
    payload = {"definition": {"patterns": list(PATTERNS), "timeframe": "15m", "entry": "close beyond confirmed pattern boundary; enter next open", "exit": "strict RR 1:1 full exit", "pivots_per_boundary": 3}, "symbols": list(SYMBOLS), "selection": "2010-2018 and 2019-2022 only", "selected": selected, "all_candidates": summaries}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
