"""Measure strict-RR1 expectancy of textbook wall-break retest shapes."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import (
    PERIODS,
    SYMBOLS,
    FourHourWalls,
    _break_signals,
    _confirmed_four_hour_walls,
    _passes,
    _period_rows,
    _stats,
)
from research_4h_wall_retest import Candidate, RetestSignal, _simulate
from research_strict_rr_portfolio import Prepared, _prepare


SHAPES = ("pin_bar", "engulfing", "pin_or_engulfing", "pin_and_engulfing")
SHAPE_NAMES_JA = {
    "pin_bar": "ピンバー（長い反転ヒゲ）",
    "engulfing": "包み足",
    "pin_or_engulfing": "ピンバーまたは包み足",
    "pin_and_engulfing": "ピンバーかつ包み足",
}
FIXED_CANDIDATE = Candidate(
    pivot_bars=5,
    break_buffer_atr=0.10,
    retest_window_bars=32,
    retest_tolerance_atr=0.20,
    stop_mode="retest",
)


def _shape_masks(data: Prepared) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Return strict bullish/bearish textbook candle masks without lookahead."""
    previous_open = np.roll(data.open, 1)
    previous_close = np.roll(data.close, 1)
    body = np.maximum(np.abs(data.close - data.open), data.atr * 0.02)
    upper_wick = data.high - np.maximum(data.open, data.close)
    lower_wick = np.minimum(data.open, data.close) - data.low

    bullish_pin = (
        (data.close > data.open)
        & (lower_wick >= body * 2.0)
        & (lower_wick >= data.atr * 0.25)
        & (upper_wick <= body)
    )
    bearish_pin = (
        (data.close < data.open)
        & (upper_wick >= body * 2.0)
        & (upper_wick >= data.atr * 0.25)
        & (lower_wick <= body)
    )
    bullish_engulfing = (
        (data.close > data.open)
        & (previous_close < previous_open)
        & (data.open <= previous_close)
        & (data.close >= previous_open)
    )
    bearish_engulfing = (
        (data.close < data.open)
        & (previous_close > previous_open)
        & (data.open >= previous_close)
        & (data.close <= previous_open)
    )
    for mask in (
        bullish_pin,
        bearish_pin,
        bullish_engulfing,
        bearish_engulfing,
    ):
        mask[0] = False
    return {
        "pin_bar": (bullish_pin, bearish_pin),
        "engulfing": (bullish_engulfing, bearish_engulfing),
        "pin_or_engulfing": (
            bullish_pin | bullish_engulfing,
            bearish_pin | bearish_engulfing,
        ),
        "pin_and_engulfing": (
            bullish_pin & bullish_engulfing,
            bearish_pin & bearish_engulfing,
        ),
    }


def _textbook_retest_signals(
    data: Prepared,
    walls: FourHourWalls,
    candidate: Candidate,
    shape: str,
) -> list[RetestSignal]:
    """Find the first shape-confirmed support/resistance flip for each wall."""
    if shape not in SHAPES:
        raise ValueError(f"unknown shape: {shape}")
    bullish_shape, bearish_shape = _shape_masks(data)[shape]
    break_indices, directions = _break_signals(
        data, walls, candidate.break_buffer_atr
    )
    signals: list[RetestSignal] = []
    used_walls: set[tuple[int, float]] = set()
    for break_raw, direction_raw in zip(break_indices, directions, strict=True):
        break_index = int(break_raw)
        direction = int(direction_raw)
        wall = float(walls.high[break_index] if direction == 1 else walls.low[break_index])
        wall_key = (direction, wall)
        if wall_key in used_walls:
            continue
        used_walls.add(wall_key)
        start = break_index + 1
        end = min(data.close.size, start + candidate.retest_window_bars)
        if start >= end:
            continue
        tolerance = data.atr[start:end] * candidate.retest_tolerance_atr
        if direction == 1:
            confirmed = (
                (data.low[start:end] <= wall + tolerance)
                & (data.close[start:end] > wall)
                & bullish_shape[start:end]
            )
        else:
            confirmed = (
                (data.high[start:end] >= wall - tolerance)
                & (data.close[start:end] < wall)
                & bearish_shape[start:end]
            )
        matches = np.flatnonzero(confirmed)
        if matches.size:
            signals.append(RetestSignal(start + int(matches[0]), direction, wall))
    signals.sort(key=lambda signal: signal.index)
    return signals


def _period_stats(rows: list) -> dict[str, dict[str, float | int | None]]:
    return {
        name: _stats(_period_rows(rows, start, end), months)
        for name, (start, end, months) in PERIODS.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/textbook_retest_shape_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    all_rows = {shape: [] for shape in SHAPES}
    per_symbol: dict[str, dict[str, dict]] = {shape: {} for shape in SHAPES}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        data = _prepare(repository, symbol, end, "15m")
        walls = _confirmed_four_hour_walls(data, FIXED_CANDIDATE.pivot_bars)
        for shape in SHAPES:
            signals = _textbook_retest_signals(
                data, walls, FIXED_CANDIDATE, shape
            )
            rows = _simulate(
                symbol, data, walls, FIXED_CANDIDATE, signals=signals
            )
            all_rows[shape].extend(rows)
            per_symbol[shape][symbol] = _period_stats(rows)

    results = {}
    for shape in SHAPES:
        periods = _period_stats(all_rows[shape])
        results[shape] = {
            "name_ja": SHAPE_NAMES_JA[shape],
            "periods": periods,
            "per_symbol": per_symbol[shape],
            "passes": {name: _passes(stats) for name, stats in periods.items()},
            "robust_positive": all(
                int(stats["trades"]) > 0 and float(stats["expectancy_r"]) > 0
                for stats in periods.values()
            ),
        }
    payload = {
        "definition": {
            "context": "confirmed 4H trend and wall break, then first matching 15m retest",
            "entry": "next 15m open after the shape closes on the breakout side",
            "pin_bar": "directional body; rejection wick >= 2x body and 0.25 ATR; opposite wick <= body",
            "engulfing": "directional real body fully engulfs the previous opposite real body",
            "exit": "full exit at strict RR 1:1; same-bar TP/SL ambiguity counted as loss",
            "one_attempt_per_wall": True,
            "maximum_risk_atr": 2.5,
        },
        "fixed_candidate": asdict(FIXED_CANDIDATE),
        "symbols": list(SYMBOLS),
        "periods": PERIODS,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        shape: {period: values["expectancy_r"] for period, values in result["periods"].items()}
        for shape, result in results.items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
