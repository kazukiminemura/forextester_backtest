"""Tune the transparent Pine vote entry logic without pair selection."""

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
from research_strict_rr_portfolio import (
    PERIODS,
    SYMBOLS,
    RTrade,
    _ema,
    _prepare,
    _rsi,
    _stats,
)


@dataclass(frozen=True, slots=True)
class VoteCandidate:
    required_votes: int
    min_atr_ratio: float
    max_atr_ratio: float
    min_momentum_atr: float
    min_trend_atr: float
    stop_atr: float


@dataclass(slots=True)
class VoteFeatures:
    long_votes: np.ndarray
    short_votes: np.ndarray
    atr_ratio: np.ndarray
    momentum_atr: np.ndarray
    trend_atr: np.ndarray
    hourly: np.ndarray


def _features(data) -> VoteFeatures:
    close = data.close
    atr = data.atr
    ema20 = _ema(close, 20)
    ema80 = _ema(close, 80)
    ema200 = _ema(close, 200)
    atr56 = np.full(close.size, np.nan)
    # Prepared already has the exact Wilder ATR helper cached only for 14.
    from research_strict_rr_portfolio import _atr

    atr56[:] = _atr(data.high, data.low, close, 56)
    rsi14 = _rsi(close, 14)
    middle = (data.high + data.low) / 2.0
    long_votes = np.zeros(close.size, dtype=np.int8)
    short_votes = np.zeros(close.size, dtype=np.int8)
    for bars in (1, 4, 16, 64):
        previous = np.roll(close, bars)
        long_votes += close > previous
        short_votes += close < previous
    long_votes += close > ema20
    short_votes += close < ema20
    long_votes += ema80 > ema200
    short_votes += ema80 < ema200
    long_votes += rsi14 > 50.0
    short_votes += rsi14 < 50.0
    long_votes += close > data.open
    short_votes += close < data.open
    long_votes += close > middle
    short_votes += close < middle
    long_votes[:208] = 0
    short_votes[:208] = 0
    return VoteFeatures(
        long_votes=long_votes,
        short_votes=short_votes,
        atr_ratio=atr / atr56,
        momentum_atr=np.abs(close - np.roll(close, 16)) / atr,
        trend_atr=np.abs(ema80 - ema200) / atr,
        hourly=np.asarray([time.minute == 0 for time in data.times]),
    )


def _directions(features: VoteFeatures, candidate: VoteCandidate) -> np.ndarray:
    ready = (
        features.hourly
        & (features.atr_ratio >= candidate.min_atr_ratio)
        & (features.atr_ratio <= candidate.max_atr_ratio)
        & (features.momentum_atr >= candidate.min_momentum_atr)
        & (features.trend_atr >= candidate.min_trend_atr)
    )
    long_signal = (
        ready
        & (features.long_votes >= candidate.required_votes)
        & (features.long_votes > features.short_votes)
    )
    short_signal = (
        ready
        & (features.short_votes >= candidate.required_votes)
        & (features.short_votes > features.long_votes)
    )
    directions = np.zeros(features.long_votes.size, dtype=np.int8)
    directions[long_signal] = 1
    directions[short_signal] = -1
    return directions


def _simulate(symbol: str, data, features: VoteFeatures, candidate: VoteCandidate):
    directions = _directions(features, candidate)
    signal_indices = np.flatnonzero(directions)
    trades = []
    cursor = 0
    while cursor < signal_indices.size:
        signal_index = int(signal_indices[cursor])
        entry_index = signal_index + 1
        if entry_index >= data.close.size:
            break
        direction = int(directions[signal_index])
        entry = float(data.open[entry_index])
        if direction == 1:
            stop = float(data.close[signal_index] - data.atr[signal_index] * candidate.stop_atr)
            risk = entry - stop
            target = entry + risk
        else:
            stop = float(data.close[signal_index] + data.atr[signal_index] * candidate.stop_atr)
            risk = stop - entry
            target = entry - risk
        if risk <= 0.0:
            cursor += 1
            continue
        exit_index = entry_index
        while exit_index < data.close.size:
            if direction == 1:
                hit_stop = data.low[exit_index] <= stop
                hit_target = data.high[exit_index] >= target
            else:
                hit_stop = data.high[exit_index] >= stop
                hit_target = data.low[exit_index] <= target
            if hit_stop or hit_target:
                trades.append(
                    RTrade(symbol, data.times[entry_index], -1.0 if hit_stop else 1.0)
                )
                break
            exit_index += 1
        cursor = int(np.searchsorted(signal_indices, exit_index + 1))
    return trades


def _target_gate(stats) -> bool:
    return (
        float(stats["win_rate"]) >= 65.0
        and float(stats["trades_per_month"]) >= 3.0
        and float(stats["profit_factor"] or 0.0) >= 1.15
        and float(stats["expectancy_r"]) > 0.0
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output", type=Path, default=Path("scripts/pine_vote_entry_results.json")
    )
    args = parser.parse_args()
    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    prepared = {}
    features = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        features[symbol] = _features(prepared[symbol])

    candidates = [
        VoteCandidate(votes, low, high, momentum, trend, stop)
        for votes, (low, high), momentum, trend, stop in product(
            (7, 8, 9),
            ((0.70, 1.50), (0.90, 1.30)),
            (0.50, 1.00, 1.50),
            (0.0, 0.50),
            (1.50, 2.00, 2.50),
        )
    ]
    results = []
    for index, candidate in enumerate(candidates, 1):
        trades = [
            trade
            for symbol in SYMBOLS
            for trade in _simulate(symbol, prepared[symbol], features[symbol], candidate)
        ]
        periods = {
            name: _stats(trades, start, finish, months)
            for name, (start, finish, months) in PERIODS.items()
        }
        prequalified = _target_gate(periods["train_2010_2018"]) and _target_gate(
            periods["validation_2019_2022"]
        )
        passes_all = prequalified and all(_target_gate(stats) for stats in periods.values())
        results.append(
            {
                "config": asdict(candidate),
                "prequalified": prequalified,
                "passes_all": passes_all,
                "periods": periods,
            }
        )
        print(
            f"{index}/{len(candidates)} votes={candidate.required_votes} "
            f"pre={prequalified} all={passes_all}",
            file=sys.stderr,
            flush=True,
        )
    results.sort(
        key=lambda row: (
            row["prequalified"],
            min(
                float(row["periods"][period]["win_rate"])
                for period in ("train_2010_2018", "validation_2019_2022")
            ),
            min(
                float(row["periods"][period]["trades_per_month"])
                for period in ("train_2010_2018", "validation_2019_2022")
            ),
        ),
        reverse=True,
    )
    args.output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"RESULTS={len(results)} PRE={sum(row['prequalified'] for row in results)} "
        f"PASS={sum(row['passes_all'] for row in results)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
