"""Research simple non-repainting filters for the Yosuga Dow reversal indicator."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository


PERIODS = {
    "train_2004_2018": (2004, 2018),
    "validation_2019_2022": (2019, 2022),
    "holdout_2023_2024": (2023, 2024),
    "true_oos_2025_2026": (2025, 2026),
}
LENGTHS = (10, 20, 50, 100, 200, 400, 800, 1200, 1600, 2000, 2400, 3200)
MODES = ("price", "slope", "price_and_slope")
SESSIONS = (
    (0, 8),
    (6, 15),
    (7, 16),
    (8, 17),
    (12, 21),
    (13, 22),
    (6, 21),
)
MIN_TRAIN_TRADES = 100
MIN_VALIDATION_TRADES = 30


@dataclass(frozen=True, slots=True)
class Candidate:
    length: int
    mode: str
    average_kind: str = "sma"
    session_start: int = 0
    session_end: int = 24

    @property
    def name(self) -> str:
        ma_name = (
            f"{self.average_kind}{self.length}_{self.mode}"
            if self.length
            else "no_ma"
        )
        session_name = f"h{self.session_start:02d}_{self.session_end:02d}"
        return f"{ma_name}_{session_name}"


@dataclass(frozen=True, slots=True)
class Trade:
    entry_time: datetime
    exit_time: datetime
    direction: int
    return_pct: float


@dataclass(frozen=True, slots=True)
class Prepared:
    times: list[datetime]
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    cross_events: list[tuple[int, int]]


def _confirmed_pivots(
    values: np.ndarray, left: int, right: int, high: bool
) -> np.ndarray:
    """Return pivot values on their confirmation bars, matching Pine timing."""
    result = np.full(values.size, np.nan)
    width = left + right + 1
    if values.size < width:
        return result
    windows = np.lib.stride_tricks.sliding_window_view(values, width)
    centers = windows[:, left]
    extrema = np.max(windows, axis=1) if high else np.min(windows, axis=1)
    matches = centers == extrema
    center_indexes = np.flatnonzero(matches) + left
    confirmation_indexes = center_indexes + right
    result[confirmation_indexes] = values[center_indexes]
    return result


def _cross_events(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    left: int,
    right: int,
) -> list[tuple[int, int]]:
    pivot_high = _confirmed_pivots(high, left, right, high=True)
    pivot_low = _confirmed_pivots(low, left, right, high=False)
    last_high = np.nan
    last_low = np.nan
    previous_high = np.nan
    previous_low = np.nan
    events: list[tuple[int, int]] = []
    for index in range(close.size):
        previous_high = last_high if index > 0 else np.nan
        previous_low = last_low if index > 0 else np.nan
        if not np.isnan(pivot_high[index]):
            last_high = float(pivot_high[index])
        if not np.isnan(pivot_low[index]):
            last_low = float(pivot_low[index])
        if index == 0:
            continue
        crossed_high = (
            not np.isnan(last_high)
            and not np.isnan(previous_high)
            and close[index] > last_high
            and close[index - 1] <= previous_high
        )
        crossed_low = (
            not np.isnan(last_low)
            and not np.isnan(previous_low)
            and close[index] < last_low
            and close[index - 1] >= previous_low
        )
        if crossed_high:
            events.append((index, 1))
        if crossed_low:
            events.append((index, -1))
    return events


def _prepare(
    repository: HistoryRepository,
    symbol: str,
    end: datetime,
    left: int = 5,
    right: int = 5,
) -> Prepared:
    bars = list(repository.bars(symbol, end=end, timeframe="15m"))
    times = [bar.time for bar in bars]
    high = np.asarray([bar.high for bar in bars], dtype=float)
    low = np.asarray([bar.low for bar in bars], dtype=float)
    close = np.asarray([bar.close for bar in bars], dtype=float)
    return Prepared(
        times, high, low, close, _cross_events(high, low, close, left, right)
    )


def _sma(values: np.ndarray, length: int) -> np.ndarray:
    result = np.full(values.size, np.nan)
    if values.size < length:
        return result
    sums = np.cumsum(np.insert(values, 0, 0.0))
    result[length - 1 :] = (sums[length:] - sums[:-length]) / length
    return result


def _ema(values: np.ndarray, length: int) -> np.ndarray:
    result = np.full(values.size, np.nan)
    if values.size < length:
        return result
    alpha = 2.0 / (length + 1.0)
    result[length - 1] = float(values[:length].mean())
    for index in range(length, values.size):
        result[index] = alpha * values[index] + (1.0 - alpha) * result[index - 1]
    return result


def _allowed(
    direction: int,
    index: int,
    times: list[datetime],
    close: np.ndarray,
    average: np.ndarray | None,
    mode: str | None,
) -> bool:
    if average is None or mode is None:
        return True
    if index == 0 or np.isnan(average[index]) or np.isnan(average[index - 1]):
        return False
    price_ok = direction * (close[index] - average[index]) > 0
    slope_ok = direction * (average[index] - average[index - 1]) > 0
    if mode == "price":
        return bool(price_ok)
    if mode == "slope":
        return bool(slope_ok)
    return bool(price_ok and slope_ok)


def _simulate(
    data: Prepared,
    cost_pct: float,
    candidate: Candidate | None = None,
) -> list[Trade]:
    average = None
    if candidate and candidate.length > 0:
        average = (
            _ema(data.close, candidate.length)
            if candidate.average_kind == "ema"
            else _sma(data.close, candidate.length)
        )
    mode = candidate.mode if candidate else None
    position = 0
    entry_index = -1
    entry_price = np.nan
    trades: list[Trade] = []
    for index, direction in data.cross_events:
        if candidate and not (
            candidate.session_start
            <= data.times[index].hour
            < candidate.session_end
        ):
            continue
        if position == direction or not _allowed(
            direction, index, data.times, data.close, average, mode
        ):
            continue
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
        if position == 0:
            position = direction
            entry_index = index
            entry_price = data.close[index]
    return trades


def _stats(trades: list[Trade]) -> dict[str, float | int | None]:
    returns = np.asarray([trade.return_pct for trade in trades], dtype=float)
    if returns.size == 0:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": None,
            "total_return_pct": 0.0,
            "expectancy_pct": None,
            "profit_factor": None,
        }
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = float(-losses.sum())
    return {
        "trades": int(returns.size),
        "wins": int(wins.size),
        "win_rate": float(wins.size / returns.size * 100.0),
        "total_return_pct": float(returns.sum()),
        "expectancy_pct": float(returns.mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else None,
    }


def _period_stats(trades: list[Trade]) -> dict[str, dict[str, float | int | None]]:
    return {
        name: _stats(
            [trade for trade in trades if start <= trade.entry_time.year <= end]
        )
        for name, (start, end) in PERIODS.items()
    }


def _eligible(periods: dict[str, dict[str, float | int | None]]) -> bool:
    train = periods["train_2004_2018"]
    validation = periods["validation_2019_2022"]
    return (
        int(train["trades"]) >= MIN_TRAIN_TRADES
        and int(validation["trades"]) >= MIN_VALIDATION_TRADES
        and float(train["total_return_pct"]) > 0.0
        and float(validation["total_return_pct"]) > 0.0
        and float(train["expectancy_pct"]) > 0.0
        and float(validation["expectancy_pct"]) > 0.0
    )


def _selection_score(periods: dict[str, dict[str, float | int | None]]) -> float:
    return min(
        float(periods["train_2004_2018"]["expectancy_pct"]),
        float(periods["validation_2019_2022"]["expectancy_pct"]),
    )


def _passes_unseen_periods(
    periods: dict[str, dict[str, float | int | None]],
) -> bool:
    return all(
        float(periods[name]["total_return_pct"]) > 0.0
        and float(periods[name]["expectancy_pct"]) > 0.0
        for name in ("holdout_2023_2024", "true_oos_2025_2026")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_dow_filter_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    print(f"Loading {args.symbol} 15m...", file=sys.stderr, flush=True)
    data = _prepare(repository, args.symbol, end)
    baseline_periods = _period_stats(_simulate(data, args.cost_pct))

    results: list[dict[str, object]] = []
    candidates = [
        Candidate(length, mode) for length in LENGTHS for mode in MODES
    ]
    candidates.extend(
        Candidate(length, mode, average_kind="ema")
        for length in LENGTHS
        for mode in MODES
    )
    candidates.extend(
        Candidate(0, "session", session_start=start, session_end=end)
        for start, end in SESSIONS
    )
    candidates.extend(
        Candidate(1600, "slope", session_start=start, session_end=end)
        for start, end in SESSIONS
    )
    for candidate in candidates:
        periods = _period_stats(_simulate(data, args.cost_pct, candidate))
        results.append(
            {
                "candidate": asdict(candidate),
                "name": candidate.name,
                "periods": periods,
                "eligible": _eligible(periods),
            }
        )

    eligible = [row for row in results if bool(row["eligible"])]
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
            "timeframe": "15m",
            "pivot_left": 5,
            "pivot_right": 5,
            "exit": "opposite raw Dow signal close",
            "round_trip_cost_pct": args.cost_pct,
        },
        "periods": PERIODS,
        "selection_rule": {
            "used_for_selection": ["train_2004_2018", "validation_2019_2022"],
            "not_used_for_selection": ["holdout_2023_2024", "true_oos_2025_2026"],
            "minimum_train_trades": MIN_TRAIN_TRADES,
            "minimum_validation_trades": MIN_VALIDATION_TRADES,
            "require_positive_total_and_expectancy_in_train_and_validation": True,
        },
        "baseline": baseline_periods,
        "candidates": results,
        "selected_by_train_validation": selected,
        "adopted": adopted,
        "adoption_reason": (
            "selected candidate stayed positive in both unseen periods"
            if adopted
            else "no train/validation-selected candidate stayed positive in both unseen periods"
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload["adopted"], ensure_ascii=False, indent=2))
    return 0 if adopted else 2


if __name__ == "__main__":
    raise SystemExit(main())
