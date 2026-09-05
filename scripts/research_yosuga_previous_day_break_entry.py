"""Test Yosuga entries only after the prior-day high or low is updated."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_yosuga_dow_filters import Prepared, _cross_events
from research_yosuga_dow_htf_filter import HtfCandidate
from research_yosuga_dow_pullback_entry import (
    PullbackCandidate,
    _atr,
    _local_dow_trend,
    _pullback_state,
    _simulate,
)
from research_yosuga_dow_rr_breakeven import _period_stats, _trend_context


@dataclass(frozen=True, slots=True)
class DailyBreakCandidate:
    name: str
    mode: str
    buffer_atr: float = 0.0


@dataclass(frozen=True, slots=True)
class PreviousDayState:
    high: np.ndarray
    low: np.ndarray
    high_updated: np.ndarray
    low_updated: np.ndarray
    high_updated_before_bar: np.ndarray
    low_updated_before_bar: np.ndarray


def _prepare_timeframe(
    repository: HistoryRepository, symbol: str, timeframe: str, end: datetime
) -> Prepared:
    bars = list(repository.bars(symbol, end=end, timeframe=timeframe))
    high = np.asarray([bar.high for bar in bars], dtype=float)
    low = np.asarray([bar.low for bar in bars], dtype=float)
    close = np.asarray([bar.close for bar in bars], dtype=float)
    return Prepared(
        [bar.time for bar in bars],
        high,
        low,
        close,
        _cross_events(high, low, close, 5, 5),
    )


def _previous_day_state(data: Prepared, buffer: np.ndarray) -> PreviousDayState:
    size = data.close.size
    previous_high = np.full(size, np.nan)
    previous_low = np.full(size, np.nan)
    high_updated = np.zeros(size, dtype=bool)
    low_updated = np.zeros(size, dtype=bool)
    high_updated_before_bar = np.zeros(size, dtype=bool)
    low_updated_before_bar = np.zeros(size, dtype=bool)
    current_day = None
    day_high = -np.inf
    day_low = np.inf
    prior_high = np.nan
    prior_low = np.nan

    for index, time in enumerate(data.times):
        if time.date() != current_day:
            if current_day is not None:
                prior_high = day_high
                prior_low = day_low
            current_day = time.date()
            day_high = -np.inf
            day_low = np.inf
        previous_high[index] = prior_high
        previous_low[index] = prior_low
        high_updated_before_bar[index] = (
            np.isfinite(prior_high) and day_high > prior_high + buffer[index]
        )
        low_updated_before_bar[index] = (
            np.isfinite(prior_low) and day_low < prior_low - buffer[index]
        )
        day_high = max(day_high, float(data.high[index]))
        day_low = min(day_low, float(data.low[index]))
        high_updated[index] = (
            np.isfinite(prior_high) and day_high > prior_high + buffer[index]
        )
        low_updated[index] = (
            np.isfinite(prior_low) and day_low < prior_low - buffer[index]
        )

    return PreviousDayState(
        previous_high,
        previous_low,
        high_updated,
        low_updated,
        high_updated_before_bar,
        low_updated_before_bar,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPCHF"])
    parser.add_argument("--timeframes", nargs="+", default=["15m", "1h"])
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_previous_day_break_entry_results.json"),
    )
    args = parser.parse_args()

    htf = HtfCandidate("sma", 20, "slope")
    signal = PullbackCandidate(htf, 4, True, 0.5, True)
    candidates = (
        DailyBreakCandidate("baseline", "none"),
        DailyBreakCandidate("same_bar_wick_update", "wick"),
        DailyBreakCandidate("prior_bar_wick_update", "prior_wick"),
        DailyBreakCandidate("entry_close_beyond_level", "close"),
        DailyBreakCandidate("same_bar_wick_update_0.05atr", "wick", 0.05),
        DailyBreakCandidate("prior_bar_wick_update_0.05atr", "prior_wick", 0.05),
    )

    result_sets = []
    for symbol in args.symbols:
        for timeframe in args.timeframes:
            data = _prepare_timeframe(
                HistoryRepository(args.history_dir),
                symbol,
                timeframe,
                datetime(2026, 7, 17, 23, 59, 59),
            )
            atr = _atr(data)
            pullback = _pullback_state(data)
            local_dow = _local_dow_trend(data)
            trend_context = _trend_context(data, htf)
            rows = []
            for candidate in candidates:
                state = _previous_day_state(data, atr * candidate.buffer_atr)

                def allowed(
                    index: int, direction: int, entry: float, stop: float
                ) -> bool:
                    del stop
                    if candidate.mode == "wick":
                        return bool(
                            state.high_updated[index]
                            if direction == 1
                            else state.low_updated[index]
                        )
                    if candidate.mode == "prior_wick":
                        return bool(
                            state.high_updated_before_bar[index]
                            if direction == 1
                            else state.low_updated_before_bar[index]
                        )
                    if candidate.mode == "close":
                        level = (
                            state.high[index]
                            if direction == 1
                            else state.low[index]
                        )
                        return bool(
                            np.isfinite(level)
                            and direction * (entry - level) > 0
                        )
                    return True

                trades = _simulate(
                    data,
                    args.cost_pct,
                    signal,
                    atr=atr,
                    pullback=pullback,
                    trend_context=trend_context,
                    local_dow=local_dow,
                    entry_filter=None if candidate.mode == "none" else allowed,
                )
                rows.append(
                    {"candidate": asdict(candidate), "periods": _period_stats(trades)}
                )
            result_sets.append(
                {"symbol": symbol, "timeframe": timeframe, "candidates": rows}
            )

    payload = {
        "definition": (
            "long only after the current day exceeds the previous completed "
            "day high; short only after it falls below the previous day low"
        ),
        "round_trip_cost_pct": args.cost_pct,
        "results": result_sets,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
