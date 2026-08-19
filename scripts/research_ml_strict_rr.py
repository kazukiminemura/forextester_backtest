"""Research a shared ML signal model under strict RR 1:1 portfolio gates."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from forextester_backtest import HistoryRepository
from research_strict_rr_portfolio import (
    PERIODS,
    SYMBOLS,
    Candidate,
    Prepared,
    _atr,
    _ema,
    _passes,
    _prepare,
    _rsi,
    _simulate,
    _stats,
)


@dataclass(slots=True)
class Opportunities:
    indices: np.ndarray
    x_long: np.ndarray
    x_short: np.ndarray
    y_long: np.ndarray
    y_short: np.ndarray
    resolved_long: np.ndarray
    resolved_short: np.ndarray


def _shift(values: np.ndarray, bars: int) -> np.ndarray:
    shifted = np.full(values.size, np.nan)
    shifted[bars:] = values[:-bars]
    return shifted


def _strict_labels(
    data: Prepared, indices: np.ndarray, direction: int, stop_atr: float
) -> tuple[np.ndarray, np.ndarray]:
    labels = np.full(indices.size, np.nan)
    resolved = np.full(indices.size, -1, dtype=np.int64)
    for row, signal_index in enumerate(indices):
        entry_index = int(signal_index) + 1
        if entry_index >= data.close.size or not np.isfinite(data.atr[signal_index]):
            continue
        if direction == 1:
            entry = float(data.open[entry_index] + data.spread)
            stop = float(data.close[signal_index] - data.atr[signal_index] * stop_atr)
            risk = entry - stop
            target = entry + risk
        else:
            entry = float(data.open[entry_index])
            stop = float(
                data.close[signal_index] + data.atr[signal_index] * stop_atr + data.spread
            )
            risk = stop - entry
            target = entry - risk
        if risk <= 0:
            continue
        for exit_index in range(entry_index, data.close.size):
            if direction == 1:
                hit_stop = data.low[exit_index] <= stop
                hit_target = data.high[exit_index] >= target
            else:
                hit_stop = data.high[exit_index] + data.spread >= stop
                hit_target = data.low[exit_index] + data.spread <= target
            if hit_stop or hit_target:
                labels[row] = 0.0 if hit_stop else 1.0
                resolved[row] = exit_index
                break
    return labels, resolved


def _directional_features(
    data: Prepared, indices: np.ndarray, direction: int
) -> np.ndarray:
    close = data.close
    atr = data.atr
    scale = np.maximum(atr, 1e-12)
    if 20 not in data.ema_cache:
        data.ema_cache[20] = _ema(close, 20)
    if 80 not in data.ema_cache:
        data.ema_cache[80] = _ema(close, 80)
    if 200 not in data.ema_cache:
        data.ema_cache[200] = _ema(close, 200)
    if 56 not in data.atr_cache:
        data.atr_cache[56] = _atr(data.high, data.low, close, 56)
    if 14 not in data.rsi_cache:
        data.rsi_cache[14] = _rsi(close, 14)

    directional = [
        direction * (close - _shift(close, length)) / scale
        for length in (1, 4, 16, 64)
    ]
    directional.extend(
        (
            direction * (close - data.ema_cache[20]) / scale,
            direction * (data.ema_cache[80] - data.ema_cache[200]) / scale,
            direction * (data.rsi_cache[14] - 50.0) / 50.0,
            direction * (close - data.open) / scale,
            direction * (close - (data.high + data.low) / 2.0) / scale,
        )
    )
    hour_angle = np.asarray(data.hours, dtype=float) * (2.0 * np.pi / 24.0)
    weekdays = np.asarray([time.weekday() for time in data.times], dtype=float)
    weekday_angle = weekdays * (2.0 * np.pi / 5.0)
    nondirectional = (
        (data.high - data.low) / scale,
        atr / np.maximum(data.atr_cache[56], 1e-12),
        np.full(close.size, data.spread) / scale,
        np.sin(hour_angle),
        np.cos(hour_angle),
        np.sin(weekday_angle),
        np.cos(weekday_angle),
    )
    return np.column_stack([feature[indices] for feature in (*directional, *nondirectional)])


def _opportunities(data: Prepared, stride: int, stop_atr: float) -> Opportunities:
    if stride != 4:
        raise ValueError("the operational 15-minute strategy requires stride=4")
    indices = np.asarray(
        [
            index
            for index, time in enumerate(data.times[208:-1], start=208)
            if time.minute == 0
        ],
        dtype=np.int64,
    )
    x_long = _directional_features(data, indices, 1)
    x_short = _directional_features(data, indices, -1)
    finite = np.isfinite(x_long).all(axis=1) & np.isfinite(x_short).all(axis=1)
    indices = indices[finite]
    x_long = x_long[finite]
    x_short = x_short[finite]
    y_long, resolved_long = _strict_labels(data, indices, 1, stop_atr)
    y_short, resolved_short = _strict_labels(data, indices, -1, stop_atr)
    return Opportunities(
        indices=indices,
        x_long=x_long,
        x_short=x_short,
        y_long=y_long,
        y_short=y_short,
        resolved_long=resolved_long,
        resolved_short=resolved_short,
    )


def _training_rows(
    prepared: dict[str, Prepared],
    opportunities: dict[str, Opportunities],
    prediction_year: int,
) -> tuple[np.ndarray, np.ndarray]:
    x_rows = []
    y_rows = []
    for symbol in SYMBOLS:
        data = prepared[symbol]
        rows = opportunities[symbol]
        resolved_long = rows.resolved_long >= 0
        resolved_short = rows.resolved_short >= 0
        long_before_cutoff = resolved_long.copy()
        short_before_cutoff = resolved_short.copy()
        long_before_cutoff[resolved_long] &= (
            data.years[rows.resolved_long[resolved_long]] < prediction_year
        )
        short_before_cutoff[resolved_short] &= (
            data.years[rows.resolved_short[resolved_short]] < prediction_year
        )
        x_rows.extend(
            (rows.x_long[long_before_cutoff], rows.x_short[short_before_cutoff])
        )
        y_rows.extend(
            (rows.y_long[long_before_cutoff], rows.y_short[short_before_cutoff])
        )
    return np.vstack(x_rows), np.concatenate(y_rows).astype(np.int8)


def _new_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=120,
        max_leaf_nodes=15,
        min_samples_leaf=200,
        l2_regularization=2.0,
        early_stopping=False,
        random_state=20260802,
    )


def _signal_map(
    prepared: dict[str, Prepared],
    opportunities: dict[str, Opportunities],
    probabilities: dict[str, tuple[np.ndarray, np.ndarray]],
    threshold: float,
    margin: float,
    session_start: int,
    session_end: int,
    require_htf_alignment: bool = False,
) -> dict[str, np.ndarray]:
    output = {}
    for symbol in SYMBOLS:
        data = prepared[symbol]
        rows = opportunities[symbol]
        long_probability, short_probability = probabilities[symbol]
        hours = data.hours[rows.indices]
        session = (hours >= session_start) & (hours < session_end)
        htf_trend = data.htf_trend[rows.indices]
        long_htf_ok = (htf_trend == 1) if require_htf_alignment else True
        short_htf_ok = (htf_trend == -1) if require_htf_alignment else True
        long_signal = (
            session
            & long_htf_ok
            & (long_probability >= threshold)
            & (long_probability >= short_probability + margin)
        )
        short_signal = (
            session
            & short_htf_ok
            & (short_probability >= threshold)
            & (short_probability >= long_probability + margin)
        )
        directions = np.zeros(data.close.size, dtype=np.int8)
        directions[rows.indices[long_signal]] = 1
        directions[rows.indices[short_signal]] = -1
        output[symbol] = directions
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output", type=Path, default=Path("scripts/strict_rr_ml_results.json")
    )
    parser.add_argument("--stop-atr", type=float, default=2.0)
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument(
        "--require-htf-alignment",
        action="store_true",
        help="Only trade in the direction of the confirmed 4-hour Dow trend.",
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    prepared = {}
    opportunities = {}
    for symbol in SYMBOLS:
        print(f"Loading and labeling {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        opportunities[symbol] = _opportunities(
            prepared[symbol], args.stride, args.stop_atr
        )

    probabilities = {
        symbol: (
            np.full(rows.indices.size, np.nan),
            np.full(rows.indices.size, np.nan),
        )
        for symbol, rows in opportunities.items()
    }
    for prediction_year in range(2019, 2027):
        x_train, y_train = _training_rows(
            prepared, opportunities, prediction_year
        )
        print(
            f"Training before {prediction_year}: rows={y_train.size} "
            f"wins={int(y_train.sum())} features={x_train.shape[1]}",
            file=sys.stderr,
            flush=True,
        )
        model = _new_model()
        model.fit(x_train, y_train)
        for symbol, rows in opportunities.items():
            years = prepared[symbol].years[rows.indices]
            if prediction_year == 2019:
                train_rows = years <= 2018
                probabilities[symbol][0][train_rows] = model.predict_proba(
                    rows.x_long[train_rows]
                )[:, 1]
                probabilities[symbol][1][train_rows] = model.predict_proba(
                    rows.x_short[train_rows]
                )[:, 1]
            predict_rows = years == prediction_year
            probabilities[symbol][0][predict_rows] = model.predict_proba(
                rows.x_long[predict_rows]
            )[:, 1]
            probabilities[symbol][1][predict_rows] = model.predict_proba(
                rows.x_short[predict_rows]
            )[:, 1]

    candidate = Candidate(
        "shared_ml", timeframe="15m", stop_atr=args.stop_atr, cooldown_bars=0
    )
    results = []
    for threshold in (0.50, 0.51, 0.52, 0.53, 0.54, 0.55):
        for margin in (0.0,):
            for session_start, session_end in ((0, 24), (6, 20)):
                signals = _signal_map(
                    prepared,
                    opportunities,
                    probabilities,
                    threshold,
                    margin,
                    session_start,
                    session_end,
                    args.require_htf_alignment,
                )
                trades_by_symbol = {
                    symbol: _simulate(
                        symbol, prepared[symbol], candidate, signals[symbol]
                    )
                    for symbol in SYMBOLS
                }
                trades = [
                    trade
                    for symbol in SYMBOLS
                    for trade in trades_by_symbol[symbol]
                ]
                periods = {
                    name: _stats(trades, start, finish, months)
                    for name, (start, finish, months) in PERIODS.items()
                }
                annual_validation = {
                    str(year): _stats(trades, year, year, 12)
                    for year in range(2019, 2023)
                }
                annual_periods = {
                    str(year): _stats(trades, year, year, 12)
                    for year in range(2010, 2027)
                }
                symbol_periods = {
                    symbol: {
                        name: _stats(symbol_trades, start, finish, months)
                        for name, (start, finish, months) in PERIODS.items()
                    }
                    for symbol, symbol_trades in trades_by_symbol.items()
                }
                prequalified = _passes(periods["train_2010_2018"]) and _passes(
                    periods["validation_2019_2022"]
                )
                passes_all = prequalified and all(
                    _passes(stats) for stats in periods.values()
                )
                results.append(
                    {
                        "config": {
                            **asdict(candidate),
                            "threshold": threshold,
                            "probability_margin": margin,
                            "session_start": session_start,
                            "session_end": session_end,
                            "stride": args.stride,
                            "require_htf_alignment": args.require_htf_alignment,
                        },
                        "prequalified": prequalified,
                        "passes_all": passes_all,
                        "periods": periods,
                        "annual_validation": annual_validation,
                        "annual_periods": annual_periods,
                        "symbol_periods": symbol_periods,
                    }
                )
    selectable = [
        row
        for row in results
        if row["prequalified"]
        and row["config"]["session_start"] == 0
        and row["config"]["session_end"] == 24
    ]
    selected = max(
        selectable,
        key=lambda row: float(
            row["periods"]["validation_2019_2022"]["profit_factor"] or 0.0
        ),
    )
    selected["selected_by_validation_only"] = True
    results.sort(
        key=lambda row: (
            row["prequalified"],
            min(
                float(row["periods"][name]["profit_factor"] or 0.0)
                for name in ("train_2010_2018", "validation_2019_2022")
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
