"""Compare Yosuga pullback entries with directional acceleration filters."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_yosuga_dow_filters import _prepare
from research_yosuga_dow_htf_filter import HtfCandidate, _four_hour_groups
from research_yosuga_dow_pullback_entry import (
    PullbackCandidate,
    _atr,
    _local_dow_trend,
    _pullback_state,
    _simulate,
)
from research_yosuga_dow_rr_breakeven import _period_stats, _trend_context


@dataclass(frozen=True, slots=True)
class AccelerationCandidate:
    name: str
    threshold_atr: float
    require_local_acceleration: bool
    htf_mode: str


@dataclass(frozen=True, slots=True)
class PhaseInputs:
    close0: np.ndarray
    close1: np.ndarray
    close2: np.ndarray
    atr: np.ndarray


def _wilder_atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 14
) -> np.ndarray:
    true_range = np.full(close.size, np.nan)
    if close.size:
        true_range[0] = high[0] - low[0]
    for index in range(1, close.size):
        true_range[index] = max(
            high[index] - low[index],
            abs(high[index] - close[index - 1]),
            abs(low[index] - close[index - 1]),
        )
    result = np.full(close.size, np.nan)
    if close.size >= length:
        result[length - 1] = np.mean(true_range[:length])
        for index in range(length, close.size):
            result[index] = (
                result[index - 1] * (length - 1) + true_range[index]
            ) / length
    return result


def _completed_four_hour_phase_inputs(data) -> PhaseInputs:
    _buckets, group_for_bar, high, low, close = _four_hour_groups(data)
    group_atr = _wilder_atr(high, low, close)
    values = [np.full(data.close.size, np.nan) for _ in range(4)]
    for bar_index, group_raw in enumerate(group_for_bar):
        completed = int(group_raw) - 1
        if completed >= 2:
            values[0][bar_index] = close[completed]
            values[1][bar_index] = close[completed - 1]
            values[2][bar_index] = close[completed - 2]
            values[3][bar_index] = group_atr[completed]
    return PhaseInputs(*values)


def _phase(
    direction: int,
    close0: float,
    close1: float,
    close2: float,
    atr: float,
    threshold_atr: float,
) -> int:
    if direction == 0 or atr <= 0 or any(
        np.isnan(value) for value in (close0, close1, close2, atr)
    ):
        return 0
    latest = direction * (close0 - close1) / atr
    previous = direction * (close1 - close2) / atr
    change = latest - previous
    if latest <= 0:
        return -2
    if change > threshold_atr:
        return 2
    if change < -threshold_atr:
        return -1
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_acceleration_entry_results.json"),
    )
    args = parser.parse_args()

    data = _prepare(
        HistoryRepository(args.history_dir),
        args.symbol,
        datetime(2026, 7, 17, 23, 59, 59),
    )
    htf = HtfCandidate("sma", 20, "slope")
    signal = PullbackCandidate(htf, 4, True, 0.5, True)
    atr = _atr(data)
    pullback = _pullback_state(data)
    local_dow = _local_dow_trend(data)
    trend_context = _trend_context(data, htf)
    htf_phase = _completed_four_hour_phase_inputs(data)

    candidates = [AccelerationCandidate("baseline", 0.0, False, "none")]
    for threshold in (0.0, 0.03, 0.05, 0.1):
        candidates.extend(
            (
                AccelerationCandidate(
                    f"local_accel_{threshold:g}_htf_non_decel",
                    threshold,
                    True,
                    "non_decelerating",
                ),
                AccelerationCandidate(
                    f"local_and_htf_accel_{threshold:g}",
                    threshold,
                    True,
                    "accelerating",
                ),
            )
        )

    rows = []
    for candidate in candidates:
        def allowed(index: int, direction: int, entry: float, stop: float) -> bool:
            del entry, stop
            local_phase = _phase(
                direction,
                data.close[index],
                data.close[index - 1],
                data.close[index - 2],
                atr[index],
                candidate.threshold_atr,
            )
            higher_phase = _phase(
                direction,
                htf_phase.close0[index],
                htf_phase.close1[index],
                htf_phase.close2[index],
                htf_phase.atr[index],
                candidate.threshold_atr,
            )
            local_ok = (
                not candidate.require_local_acceleration or local_phase == 2
            )
            htf_ok = (
                candidate.htf_mode == "none"
                or candidate.htf_mode == "non_decelerating"
                and higher_phase in (1, 2)
                or candidate.htf_mode == "accelerating"
                and higher_phase == 2
            )
            return local_ok and htf_ok

        trades = _simulate(
            data,
            args.cost_pct,
            signal,
            atr=atr,
            pullback=pullback,
            trend_context=trend_context,
            local_dow=local_dow,
            entry_filter=None if candidate.name == "baseline" else allowed,
        )
        rows.append(
            {
                "candidate": asdict(candidate),
                "periods": _period_stats(trades),
            }
        )

    payload = {
        "symbol": args.symbol,
        "entry_timeframe": "15m",
        "higher_timeframe": "previous completed 4h",
        "phase_definition": (
            "directional close progress and its one-bar change, normalized by ATR14; "
            "2=accelerating, 1=cruising, -1=decelerating, -2=pullback"
        ),
        "round_trip_cost_pct": args.cost_pct,
        "candidates": rows,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
