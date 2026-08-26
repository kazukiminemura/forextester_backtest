"""Backtest classic double top/bottom and head-and-shoulders patterns."""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left, bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import PERIODS, SYMBOLS, Trade, _period_rows, _stats
from research_strict_rr_portfolio import Prepared, _is_pivot, _prepare


PATTERNS = ("double_top", "double_bottom", "head_shoulders", "inverse_head_shoulders")


@dataclass(frozen=True, slots=True)
class Candidate:
    pivot_bars: int
    similarity_atr: float
    min_height_atr: float
    max_pattern_bars: int
    confirmation_bars: int = 64
    stop_buffer_atr: float = 0.10


@dataclass(frozen=True, slots=True)
class Pivot:
    index: int
    confirmed_at: int
    price: float


@dataclass(frozen=True, slots=True)
class PatternSignal:
    index: int
    direction: int
    pattern: str
    stop: float


def _pivots(data: Prepared, bars: int) -> tuple[list[Pivot], list[Pivot]]:
    highs: list[Pivot] = []
    lows: list[Pivot] = []
    for confirmation in range(data.close.size):
        high = _is_pivot(data.high, confirmation, bars, bars, True)
        low = _is_pivot(data.low, confirmation, bars, bars, False)
        if high is not None:
            highs.append(Pivot(high[0], confirmation, float(high[1])))
        if low is not None:
            lows.append(Pivot(low[0], confirmation, float(low[1])))
    return highs, lows


def _between(
    items: list[Pivot], indices: list[int], left: int, right: int
) -> list[Pivot]:
    start = bisect_right(indices, left)
    end = bisect_left(indices, right)
    return items[start:end]


def _confirm_break(
    data: Prepared, start: int, end: int, direction: int, neckline_at
) -> int | None:
    start = max(1, start)
    for index in range(start, min(data.close.size, end + 1)):
        neckline = float(neckline_at(index))
        crossed = (
            data.close[index] < neckline <= data.close[index - 1]
            if direction == -1
            else data.close[index] > neckline >= data.close[index - 1]
        )
        if crossed:
            return index
    return None


def _prior_reversal_trend(
    same_side: list[Pivot], position: int, direction: int
) -> bool:
    if position == 0:
        return False
    return (
        same_side[position].price > same_side[position - 1].price
        if direction == -1
        else same_side[position].price < same_side[position - 1].price
    )


def _double_signals(
    data: Prepared,
    highs: list[Pivot],
    lows: list[Pivot],
    candidate: Candidate,
    top: bool,
) -> list[PatternSignal]:
    sides, middles = (highs, lows) if top else (lows, highs)
    direction = -1 if top else 1
    name = "double_top" if top else "double_bottom"
    signals: list[PatternSignal] = []
    middle_indices = [item.index for item in middles]
    for position in range(1, len(sides)):
        first, second = sides[position - 1], sides[position]
        if second.index - first.index > candidate.max_pattern_bars:
            continue
        middle = _between(middles, middle_indices, first.index, second.index)
        if not middle or not _prior_reversal_trend(sides, position - 1, direction):
            continue
        neckline_pivot = min(middle, key=lambda p: p.price) if top else max(middle, key=lambda p: p.price)
        atr = float(data.atr[second.confirmed_at])
        if not np.isfinite(atr) or atr <= 0:
            continue
        similar = abs(first.price - second.price) <= atr * candidate.similarity_atr
        height = (min(first.price, second.price) - neckline_pivot.price) if top else (neckline_pivot.price - max(first.price, second.price))
        if not similar or height < atr * candidate.min_height_atr:
            continue
        start = max(second.confirmed_at, neckline_pivot.confirmed_at) + 1
        confirmed = _confirm_break(
            data, start, start + candidate.confirmation_bars, direction,
            lambda _index, level=neckline_pivot.price: level,
        )
        if confirmed is None:
            continue
        extreme = max(first.price, second.price) if top else min(first.price, second.price)
        stop = extreme + candidate.stop_buffer_atr * atr if top else extreme - candidate.stop_buffer_atr * atr
        signals.append(PatternSignal(confirmed, direction, name, stop))
    return signals


def _head_shoulders_signals(
    data: Prepared,
    highs: list[Pivot],
    lows: list[Pivot],
    candidate: Candidate,
    inverse: bool,
) -> list[PatternSignal]:
    sides, middles = (lows, highs) if inverse else (highs, lows)
    direction = 1 if inverse else -1
    name = "inverse_head_shoulders" if inverse else "head_shoulders"
    signals: list[PatternSignal] = []
    middle_indices = [item.index for item in middles]
    for position in range(2, len(sides)):
        left, head, right = sides[position - 2 : position + 1]
        if right.index - left.index > candidate.max_pattern_bars:
            continue
        first_necks = _between(middles, middle_indices, left.index, head.index)
        second_necks = _between(middles, middle_indices, head.index, right.index)
        if not first_necks or not second_necks or not _prior_reversal_trend(sides, position - 2, direction):
            continue
        neck1 = min(first_necks, key=lambda p: p.price) if not inverse else max(first_necks, key=lambda p: p.price)
        neck2 = min(second_necks, key=lambda p: p.price) if not inverse else max(second_necks, key=lambda p: p.price)
        atr = float(data.atr[right.confirmed_at])
        if not np.isfinite(atr) or atr <= 0:
            continue
        shoulders_match = abs(left.price - right.price) <= atr * candidate.similarity_atr
        head_prominence = (min(head.price - left.price, head.price - right.price) if not inverse else min(left.price - head.price, right.price - head.price))
        height = (head.price - min(neck1.price, neck2.price)) if not inverse else (max(neck1.price, neck2.price) - head.price)
        if not shoulders_match or head_prominence < atr * 0.25 or height < atr * candidate.min_height_atr:
            continue
        slope = (neck2.price - neck1.price) / (neck2.index - neck1.index)
        neckline = lambda index, p=neck1.price, i=neck1.index, s=slope: p + s * (index - i)
        start = max(right.confirmed_at, neck2.confirmed_at) + 1
        confirmed = _confirm_break(data, start, start + candidate.confirmation_bars, direction, neckline)
        if confirmed is None:
            continue
        stop = right.price - candidate.stop_buffer_atr * atr if inverse else right.price + candidate.stop_buffer_atr * atr
        signals.append(PatternSignal(confirmed, direction, name, stop))
    return signals


def _signals(
    data: Prepared,
    candidate: Candidate,
    pivots: tuple[list[Pivot], list[Pivot]] | None = None,
) -> list[PatternSignal]:
    highs, lows = pivots or _pivots(data, candidate.pivot_bars)
    rows = (
        _double_signals(data, highs, lows, candidate, True)
        + _double_signals(data, highs, lows, candidate, False)
        + _head_shoulders_signals(data, highs, lows, candidate, False)
        + _head_shoulders_signals(data, highs, lows, candidate, True)
    )
    priority = {"head_shoulders": 0, "inverse_head_shoulders": 0, "double_top": 1, "double_bottom": 1}
    rows.sort(key=lambda row: (row.index, priority[row.pattern]))
    deduplicated: list[PatternSignal] = []
    used_indices: set[int] = set()
    for row in rows:
        if row.index not in used_indices:
            deduplicated.append(row)
            used_indices.add(row.index)
    return deduplicated


def _simulate(symbol: str, data: Prepared, signals: list[PatternSignal]) -> list[Trade]:
    trades: list[Trade] = []
    next_available = 0
    for signal in signals:
        entry_index = signal.index + 1
        if entry_index < next_available or entry_index >= data.close.size:
            continue
        entry = float(data.open[entry_index] + data.spread) if signal.direction == 1 else float(data.open[entry_index])
        risk = entry - signal.stop if signal.direction == 1 else signal.stop - entry
        atr = float(data.atr[signal.index])
        if risk <= 0 or risk > 4.0 * atr:
            continue
        target = entry + signal.direction * risk
        if signal.direction == 1:
            stop_hits = data.low[entry_index:] <= signal.stop
            target_hits = data.high[entry_index:] >= target
        else:
            stop_hits = data.high[entry_index:] + data.spread >= signal.stop
            target_hits = data.low[entry_index:] + data.spread <= target
        resolved = np.flatnonzero(stop_hits | target_hits)
        if not resolved.size:
            continue
        offset = int(resolved[0])
        hit_stop = bool(stop_hits[offset])
        trades.append(Trade(symbol, data.times[entry_index], -1.0 if hit_stop else 1.0, signal.direction, hit_stop and bool(target_hits[offset]), offset + 1))
        next_available = entry_index + offset + 1
    return trades


def _grid() -> list[Candidate]:
    return [Candidate(*values) for values in product((3, 5), (0.25, 0.50), (0.75, 1.25), (96, 192))]


def _periods(rows: list[Trade]) -> dict:
    return {name: _stats(_period_rows(rows, start, end), months) for name, (start, end, months) in PERIODS.items()}


def _score(periods: dict) -> tuple:
    train, validation = periods["train_2010_2018"], periods["validation_2019_2022"]
    return (min(float(train["expectancy_r"]), float(validation["expectancy_r"])), min(float(train["profit_factor"] or 0), float(validation["profit_factor"] or 0)), int(train["trades"]) + int(validation["trades"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--output", type=Path, default=Path("scripts/classic_chart_pattern_results.json"))
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
    candidates = []
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
        candidates.append({"candidate": asdict(candidate), "periods": periods, "by_pattern": {key: _periods(value) for key, value in by_pattern.items()}, "score": _score(periods)})
    selected = max(candidates, key=lambda item: tuple(item["score"]))
    payload = {"definition": {"timeframe": "15m", "patterns": list(PATTERNS), "confirmation": "close beyond neckline; entry next bar open", "exit": "strict RR 1:1 full exit; same-bar ambiguity is loss", "prior_trend_required": True}, "symbols": list(SYMBOLS), "selection": "candidate selected using 2010-2018 and 2019-2022 only", "selected": selected, "all_candidates": candidates}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
