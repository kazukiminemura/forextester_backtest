"""Backtest classical bull and bear flags under strict RR1."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import PERIODS, SYMBOLS, Trade, _period_rows, _stats
from research_classic_chart_patterns import PatternSignal, _simulate
from research_strict_rr_portfolio import Prepared, _prepare


@dataclass(frozen=True, slots=True)
class Candidate:
    pole_bars: int
    flag_bars: int
    min_pole_atr: float
    max_retracement: float
    parallel_tolerance_atr: float = 0.30
    stop_buffer_atr: float = 0.10


def _previous_extreme(values: np.ndarray, window: int, maximum: bool) -> np.ndarray:
    result = np.full(values.size, np.nan)
    queue: deque[int] = deque()
    for index, value in enumerate(values):
        while queue and queue[0] < index - window:
            queue.popleft()
        if index >= window and queue:
            result[index] = values[queue[0]]
        while queue and ((values[queue[-1]] <= value) if maximum else (values[queue[-1]] >= value)):
            queue.pop()
        queue.append(index)
    return result


def _previous_regression(values: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    size = values.size
    slope = np.full(size, np.nan)
    projected = np.full(size, np.nan)
    cumulative_y = np.concatenate(([0.0], np.cumsum(values)))
    cumulative_xy = np.concatenate(([0.0], np.cumsum(np.arange(size) * values)))
    indices = np.arange(window, size)
    starts = indices - window
    sum_y = cumulative_y[indices] - cumulative_y[starts]
    sum_xy = cumulative_xy[indices] - cumulative_xy[starts]
    mean_x = (starts + indices - 1) / 2.0
    denominator = window * (window * window - 1) / 12.0
    local_slope = (sum_xy - mean_x * sum_y) / denominator
    slope[indices] = local_slope
    projected[indices] = sum_y / window + local_slope * (indices - mean_x)
    return slope, projected


def _signals(data: Prepared, candidate: Candidate) -> list[PatternSignal]:
    upper_slope, upper_at_break = _previous_regression(data.high, candidate.flag_bars)
    lower_slope, lower_at_break = _previous_regression(data.low, candidate.flag_bars)
    flag_high = _previous_extreme(data.high, candidate.flag_bars, True)
    flag_low = _previous_extreme(data.low, candidate.flag_bars, False)
    earliest = candidate.pole_bars + candidate.flag_bars
    indices = np.arange(earliest, data.close.size)
    flag_starts = indices - candidate.flag_bars
    pole_starts = flag_starts - candidate.pole_bars
    atr = data.atr[indices - 1]
    pole_move = data.close[flag_starts] - data.close[pole_starts]
    parallel = np.abs(upper_slope[indices] - lower_slope[indices]) * candidate.flag_bars <= atr * candidate.parallel_tolerance_atr
    valid = np.isfinite(atr) & (atr > 0) & parallel
    upper_previous = upper_at_break[indices] - upper_slope[indices]
    lower_previous = lower_at_break[indices] - lower_slope[indices]
    bullish_retracement = np.divide(
        data.close[flag_starts] - flag_low[indices],
        pole_move,
        out=np.full(indices.size, np.nan),
        where=pole_move > 0,
    )
    bearish_retracement = np.divide(
        flag_high[indices] - data.close[flag_starts],
        -pole_move,
        out=np.full(indices.size, np.nan),
        where=pole_move < 0,
    )
    bullish = (
        valid
        & (pole_move >= atr * candidate.min_pole_atr)
        & (upper_slope[indices] * candidate.flag_bars <= atr * 0.25)
        & (lower_slope[indices] * candidate.flag_bars <= atr * 0.25)
        & (bullish_retracement >= 0)
        & (bullish_retracement <= candidate.max_retracement)
        & (data.close[indices] > upper_at_break[indices])
        & (data.close[indices - 1] <= upper_previous)
    )
    bearish = (
        valid
        & (pole_move <= -atr * candidate.min_pole_atr)
        & (upper_slope[indices] * candidate.flag_bars >= -atr * 0.25)
        & (lower_slope[indices] * candidate.flag_bars >= -atr * 0.25)
        & (bearish_retracement >= 0)
        & (bearish_retracement <= candidate.max_retracement)
        & (data.close[indices] < lower_at_break[indices])
        & (data.close[indices - 1] >= lower_previous)
    )
    rows = [
        PatternSignal(int(index), 1, "bull_flag", float(flag_low[index] - candidate.stop_buffer_atr * data.atr[index - 1]))
        for index in indices[bullish]
    ] + [
        PatternSignal(int(index), -1, "bear_flag", float(flag_high[index] + candidate.stop_buffer_atr * data.atr[index - 1]))
        for index in indices[bearish]
    ]
    rows.sort(key=lambda row: row.index)
    deduplicated = []
    last = -candidate.flag_bars
    for row in rows:
        if row.index - last >= candidate.flag_bars:
            deduplicated.append(row)
            last = row.index
    return deduplicated


def _grid() -> list[Candidate]:
    return [Candidate(*values) for values in product((8, 16), (8, 16), (2.0, 3.0), (0.50, 0.67))]


def _periods(rows: list[Trade]) -> dict:
    return {name: _stats(_period_rows(rows, start, end), months) for name, (start, end, months) in PERIODS.items()}


def _score(periods: dict) -> tuple:
    train, validation = periods["train_2010_2018"], periods["validation_2019_2022"]
    return (min(float(train["expectancy_r"]), float(validation["expectancy_r"])), min(float(train["profit_factor"] or 0), float(validation["profit_factor"] or 0)), int(train["trades"]) + int(validation["trades"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--output", type=Path, default=Path("scripts/flag_pattern_results.json"))
    args = parser.parse_args()
    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    prepared = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
    summaries = []
    for candidate in _grid():
        rows = []
        by_pattern = {"bull_flag": [], "bear_flag": []}
        for symbol, data in prepared.items():
            signals = _signals(data, candidate)
            symbol_rows = _simulate(symbol, data, signals)
            rows.extend(symbol_rows)
            pattern_by_time = {data.times[signal.index + 1]: signal.pattern for signal in signals if signal.index + 1 < data.close.size}
            for trade in symbol_rows:
                by_pattern[pattern_by_time[trade.entry_time]].append(trade)
        periods = _periods(rows)
        summaries.append({"candidate": asdict(candidate), "periods": periods, "by_pattern": {key: _periods(value) for key, value in by_pattern.items()}, "score": _score(periods)})
    selected = max(summaries, key=lambda item: tuple(item["score"]))
    payload = {"definition": {"patterns": ["bull_flag", "bear_flag"], "timeframe": "15m", "structure": "sharp flagpole followed by short parallel countertrend or flat channel", "entry": "close beyond channel in flagpole direction; enter next open", "exit": "strict RR 1:1 full exit"}, "symbols": list(SYMBOLS), "selection": "2010-2018 and 2019-2022 only", "selected": selected, "all_candidates": summaries}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
