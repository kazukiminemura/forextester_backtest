"""Backtest classical triple tops and bottoms under strict RR1."""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left, bisect_right
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import PERIODS, SYMBOLS, Trade, _period_rows, _stats
from research_classic_chart_patterns import Candidate, PatternSignal, Pivot, _grid, _pivots, _prior_reversal_trend, _simulate
from research_strict_rr_portfolio import Prepared, _prepare


def _between(items: list[Pivot], indices: list[int], left: int, right: int) -> list[Pivot]:
    return items[bisect_right(indices, left) : bisect_left(indices, right)]


def _signals(
    data: Prepared,
    candidate: Candidate,
    top: bool,
    pivots: tuple[list[Pivot], list[Pivot]] | None = None,
) -> list[PatternSignal]:
    highs, lows = pivots or _pivots(data, candidate.pivot_bars)
    sides, middles = (highs, lows) if top else (lows, highs)
    middle_indices = [item.index for item in middles]
    direction = -1 if top else 1
    name = "triple_top" if top else "triple_bottom"
    rows = []
    for position in range(2, len(sides)):
        first, second, third = sides[position - 2 : position + 1]
        if third.index - first.index > candidate.max_pattern_bars or not _prior_reversal_trend(sides, position - 2, direction):
            continue
        neck1 = _between(middles, middle_indices, first.index, second.index)
        neck2 = _between(middles, middle_indices, second.index, third.index)
        if not neck1 or not neck2:
            continue
        valley1 = min(neck1, key=lambda p: p.price) if top else max(neck1, key=lambda p: p.price)
        valley2 = min(neck2, key=lambda p: p.price) if top else max(neck2, key=lambda p: p.price)
        atr = float(data.atr[third.confirmed_at])
        prices = (first.price, second.price, third.price)
        if not np.isfinite(atr) or atr <= 0 or max(prices) - min(prices) > atr * candidate.similarity_atr:
            continue
        neckline_level = min(valley1.price, valley2.price) if top else max(valley1.price, valley2.price)
        height = min(prices) - neckline_level if top else neckline_level - max(prices)
        if height < atr * candidate.min_height_atr:
            continue
        slope = (valley2.price - valley1.price) / (valley2.index - valley1.index)
        start = max(third.confirmed_at, valley2.confirmed_at) + 1
        for index in range(start, min(data.close.size, start + candidate.confirmation_bars)):
            neckline = valley1.price + slope * (index - valley1.index)
            previous = valley1.price + slope * (index - 1 - valley1.index)
            crossed = data.close[index] < neckline <= data.close[index - 1] if top else data.close[index] > neckline >= data.close[index - 1]
            if crossed:
                extreme = max(prices) if top else min(prices)
                stop = extreme + candidate.stop_buffer_atr * atr if top else extreme - candidate.stop_buffer_atr * atr
                rows.append(PatternSignal(index, direction, name, stop))
                break
    rows.sort(key=lambda row: row.index)
    return rows


def _periods(rows: list[Trade]) -> dict:
    return {name: _stats(_period_rows(rows, start, end), months) for name, (start, end, months) in PERIODS.items()}


def _score(periods: dict) -> tuple:
    train, validation = periods["train_2010_2018"], periods["validation_2019_2022"]
    return (min(float(train["expectancy_r"]), float(validation["expectancy_r"])), min(float(train["profit_factor"] or 0), float(validation["profit_factor"] or 0)), int(train["trades"]) + int(validation["trades"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--output", type=Path, default=Path("scripts/triple_chart_pattern_results.json"))
    args = parser.parse_args()
    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    prepared, pivot_cache = {}, {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        for bars in (3, 5):
            pivot_cache[(symbol, bars)] = _pivots(prepared[symbol], bars)
    summaries = []
    for candidate in _grid():
        rows, by_pattern = [], {"triple_top": [], "triple_bottom": []}
        for symbol, data in prepared.items():
            signals = _signals(data, candidate, True, pivot_cache[(symbol, candidate.pivot_bars)]) + _signals(data, candidate, False, pivot_cache[(symbol, candidate.pivot_bars)])
            signals.sort(key=lambda row: row.index)
            symbol_rows = _simulate(symbol, data, signals)
            rows.extend(symbol_rows)
            mapping = {data.times[signal.index + 1]: signal.pattern for signal in signals if signal.index + 1 < data.close.size}
            for trade in symbol_rows:
                by_pattern[mapping[trade.entry_time]].append(trade)
        periods = _periods(rows)
        summaries.append({"candidate": asdict(candidate), "periods": periods, "by_pattern": {key: _periods(value) for key, value in by_pattern.items()}, "score": _score(periods)})
    selected = max(summaries, key=lambda item: tuple(item["score"]))
    payload = {"definition": {"patterns": ["triple_top", "triple_bottom"], "entry": "close beyond neckline after three similar confirmed peaks/troughs; enter next open", "exit": "strict RR 1:1 full exit"}, "symbols": list(SYMBOLS), "selection": "2010-2018 and 2019-2022 only", "selected": selected, "all_candidates": summaries}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
