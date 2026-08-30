"""Validate strict RR1 exits and optional breakeven moves for Yosuga Dow entries."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_yosuga_dow_filters import (
    MIN_TRAIN_TRADES,
    MIN_VALIDATION_TRADES,
    Prepared,
    _eligible,
    _passes_unseen_periods,
    _prepare,
    _selection_score,
)
from research_yosuga_dow_htf_filter import (
    ConfirmedHtf,
    HtfCandidate,
    _completed_four_hour_dow_trend,
    _completed_four_hour_features,
    _htf_allowed,
)


ATR_LENGTH = 14
STOP_ATR_MULTIPLE = 2.0
TARGET_R = 1.0


@dataclass(frozen=True, slots=True)
class RiskCandidate:
    htf: HtfCandidate
    breakeven_trigger_r: float | None

    @property
    def name(self) -> str:
        suffix = (
            "no_breakeven"
            if self.breakeven_trigger_r is None
            else f"breakeven_{self.breakeven_trigger_r:g}r"
        )
        return f"{self.htf.name}_{suffix}"


@dataclass(frozen=True, slots=True)
class RiskTrade:
    entry_time: datetime
    exit_time: datetime
    direction: int
    outcome: str
    return_pct: float


def _atr(data: Prepared, length: int = ATR_LENGTH) -> np.ndarray:
    true_range = np.empty(data.close.size, dtype=float)
    true_range[0] = data.high[0] - data.low[0]
    true_range[1:] = np.maximum.reduce(
        (
            data.high[1:] - data.low[1:],
            np.abs(data.high[1:] - data.close[:-1]),
            np.abs(data.low[1:] - data.close[:-1]),
        )
    )
    result = np.full(data.close.size, np.nan)
    if data.close.size < length:
        return result
    result[length - 1] = float(true_range[:length].mean())
    for index in range(length, data.close.size):
        result[index] = (
            result[index - 1] * (length - 1) + true_range[index]
        ) / length
    return result


def _trend_context(
    data: Prepared, candidate: HtfCandidate
) -> tuple[ConfirmedHtf | None, np.ndarray | None]:
    if candidate.average_kind == "dow":
        return None, _completed_four_hour_dow_trend(data, candidate.length)
    return (
        _completed_four_hour_features(
            data, candidate.average_kind, candidate.length
        ),
        None,
    )


def _entry_allowed(
    direction: int,
    index: int,
    candidate: HtfCandidate,
    features: ConfirmedHtf | None,
    dow_trend: np.ndarray | None,
) -> bool:
    if dow_trend is not None:
        return direction == int(dow_trend[index])
    assert features is not None
    return _htf_allowed(direction, index, features, candidate.mode)


def _simulate(
    data: Prepared,
    cost_pct: float,
    candidate: RiskCandidate,
) -> list[RiskTrade]:
    atr = _atr(data)
    features, dow_trend = _trend_context(data, candidate.htf)
    events_by_index: dict[int, list[int]] = {}
    for index, direction in data.cross_events:
        events_by_index.setdefault(index, []).append(direction)

    ltf_trend = 0
    position = 0
    entry_index = -1
    entry_price = np.nan
    risk_distance = np.nan
    stop_price = np.nan
    target_price = np.nan
    trigger_price = np.nan
    breakeven_active = False
    trades: list[RiskTrade] = []

    for index in range(data.close.size):
        if position != 0 and index > entry_index:
            effective_stop = entry_price if breakeven_active else stop_price
            if position == 1:
                stop_hit = data.low[index] <= effective_stop
                target_hit = data.high[index] >= target_price
                trigger_hit = data.high[index] >= trigger_price
            else:
                stop_hit = data.high[index] >= effective_stop
                target_hit = data.low[index] <= target_price
                trigger_hit = data.low[index] <= trigger_price

            exit_price = np.nan
            outcome = ""
            if stop_hit:
                exit_price = effective_stop
                outcome = "breakeven" if breakeven_active else "stop"
            elif target_hit:
                exit_price = target_price
                outcome = "target"
            elif candidate.breakeven_trigger_r is not None and trigger_hit:
                # Activate only after this bar closes to avoid assuming an
                # advantageous intrabar order between trigger and stop.
                breakeven_active = True

            if outcome:
                raw_return = position * (exit_price - entry_price) / entry_price
                trades.append(
                    RiskTrade(
                        data.times[entry_index],
                        data.times[index],
                        position,
                        outcome,
                        float(raw_return * 100.0 - cost_pct),
                    )
                )
                position = 0
                entry_index = -1
                entry_price = np.nan
                risk_distance = np.nan
                stop_price = np.nan
                target_price = np.nan
                trigger_price = np.nan
                breakeven_active = False

        for direction in events_by_index.get(index, []):
            if direction == ltf_trend:
                continue
            ltf_trend = direction
            if position != 0 or np.isnan(atr[index]):
                continue
            if not _entry_allowed(
                direction, index, candidate.htf, features, dow_trend
            ):
                continue
            position = direction
            entry_index = index
            entry_price = data.close[index]
            risk_distance = atr[index] * STOP_ATR_MULTIPLE
            stop_price = entry_price - direction * risk_distance
            target_price = entry_price + direction * risk_distance * TARGET_R
            trigger_r = (
                candidate.breakeven_trigger_r
                if candidate.breakeven_trigger_r is not None
                else TARGET_R
            )
            trigger_price = entry_price + direction * risk_distance * trigger_r
            breakeven_active = False
    return trades


def _stats(trades: list[RiskTrade]) -> dict[str, float | int | None]:
    returns = np.asarray([trade.return_pct for trade in trades], dtype=float)
    if returns.size == 0:
        return {
            "trades": 0,
            "targets": 0,
            "stops": 0,
            "breakevens": 0,
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
        "targets": sum(trade.outcome == "target" for trade in trades),
        "stops": sum(trade.outcome == "stop" for trade in trades),
        "breakevens": sum(trade.outcome == "breakeven" for trade in trades),
        "win_rate": float(wins.size / returns.size * 100.0),
        "total_return_pct": float(returns.sum()),
        "expectancy_pct": float(returns.mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else None,
    }


def _period_stats(
    trades: list[RiskTrade],
) -> dict[str, dict[str, float | int | None]]:
    periods = {
        "train_2004_2018": (2004, 2018),
        "validation_2019_2022": (2019, 2022),
        "holdout_2023_2024": (2023, 2024),
        "true_oos_2025_2026": (2025, 2026),
    }
    return {
        name: _stats(
            [trade for trade in trades if start <= trade.entry_time.year <= end]
        )
        for name, (start, end) in periods.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_dow_rr_breakeven_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    print(f"Loading {args.symbol} 15m...", file=sys.stderr, flush=True)
    data = _prepare(repository, args.symbol, datetime(2026, 7, 17, 23, 59, 59))
    htf_candidates = (
        HtfCandidate("sma", 10, "price"),
        HtfCandidate("sma", 20, "slope"),
        HtfCandidate("dow", 2, "trend"),
    )
    candidates = [
        RiskCandidate(htf, trigger)
        for htf in htf_candidates
        for trigger in (None, 0.5, 0.75)
    ]
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        periods = _period_stats(_simulate(data, args.cost_pct, candidate))
        rows.append(
            {
                "candidate": {
                    "htf": asdict(candidate.htf),
                    "breakeven_trigger_r": candidate.breakeven_trigger_r,
                },
                "name": candidate.name,
                "periods": periods,
                "eligible": _eligible(periods),
            }
        )
    eligible = [row for row in rows if bool(row["eligible"])]
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
            "entry_timeframe": "15m",
            "trend_timeframe": "previous completed 4h bar",
            "initial_stop": "ATR(14) x 2",
            "target": "full exit at 1R",
            "breakeven_activation": "after trigger bar closes; effective next bar",
            "same_bar_rule": "stop before target; no favorable intrabar ordering",
            "round_trip_cost_pct": args.cost_pct,
        },
        "selection_rule": {
            "minimum_train_trades": MIN_TRAIN_TRADES,
            "minimum_validation_trades": MIN_VALIDATION_TRADES,
            "selection_periods": ["train_2004_2018", "validation_2019_2022"],
            "unseen_periods": ["holdout_2023_2024", "true_oos_2025_2026"],
        },
        "candidates": rows,
        "selected_by_train_validation": selected,
        "adopted": adopted,
        "adoption_reason": (
            "selected RR1/breakeven candidate stayed positive in both unseen periods"
            if adopted
            else "no selected RR1/breakeven candidate stayed positive in both unseen periods"
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload["adopted"], ensure_ascii=False, indent=2))
    return 0 if adopted else 2


if __name__ == "__main__":
    raise SystemExit(main())
