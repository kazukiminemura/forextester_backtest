"""Evaluate entry-quality and post-loss filters for Yosuga consistency."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from forextester_backtest import HistoryRepository
from research_yosuga_dow_filters import (
    MIN_TRAIN_TRADES,
    MIN_VALIDATION_TRADES,
    PERIODS,
    _eligible,
    _passes_unseen_periods,
    _prepare,
    _selection_score,
)
from research_yosuga_dow_htf_filter import ConfirmedHtf, HtfCandidate
from research_yosuga_dow_pullback_entry import (
    PullbackCandidate,
    PullbackState,
    _atr,
    _local_dow_trend,
    _pullback_state,
    _simulate,
)
from research_yosuga_dow_rr_breakeven import RiskTrade, _period_stats, _trend_context


@dataclass(frozen=True, slots=True)
class ConsistencyCandidate:
    name: str
    filter_kind: str = "none"
    threshold: float = 0.0
    loss_cooldown_bars: int = 0
    stop_after_loss_for_day: bool = False


def _streak(values: list[bool]) -> int:
    longest = 0
    current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _consistency_stats(
    trades: list[RiskTrade],
) -> dict[str, dict[str, float | int | None]]:
    base = _period_stats(trades)
    for period_name, (start, end) in PERIODS.items():
        selected = [
            trade for trade in trades if start <= trade.entry_time.year <= end
        ]
        returns = np.asarray([trade.return_pct for trade in selected], dtype=float)
        curve = np.cumsum(returns)
        peaks = np.maximum.accumulate(np.insert(curve, 0, 0.0))[1:]
        drawdown = curve - peaks
        monthly: dict[str, float] = {}
        for trade in selected:
            key = trade.entry_time.strftime("%Y-%m")
            monthly[key] = monthly.get(key, 0.0) + trade.return_pct
        stats = base[period_name]
        stats["win_rate_including_breakeven"] = (
            (int(stats["targets"]) + int(stats["breakevens"]))
            * 100.0
            / int(stats["trades"])
            if int(stats["trades"])
            else None
        )
        stats["max_negative_streak"] = _streak(
            [trade.return_pct <= 0 for trade in selected]
        )
        stats["max_stop_streak"] = _streak(
            [trade.outcome == "stop" for trade in selected]
        )
        stats["max_drawdown_pct"] = (
            float(drawdown.min()) if drawdown.size else 0.0
        )
        stats["positive_month_rate"] = (
            sum(value > 0 for value in monthly.values())
            * 100.0
            / len(monthly)
            if monthly
            else None
        )
    return base


def _entry_filter(
    candidate: ConsistencyCandidate,
    atr: np.ndarray,
    pullback: PullbackState,
    confirmed_htf: ConfirmedHtf,
) -> Callable[[int, int, float, float], bool] | None:
    if candidate.filter_kind == "none":
        return None

    def allowed(index: int, direction: int, entry: float, stop: float) -> bool:
        del direction
        current_atr = atr[index]
        if candidate.filter_kind == "max_risk_atr":
            return abs(entry - stop) / current_atr <= candidate.threshold
        if candidate.filter_kind == "max_ma_distance_atr":
            return (
                abs(entry - pullback.average[index]) / current_atr
                <= candidate.threshold
            )
        if candidate.filter_kind == "min_htf_slope_atr":
            return (
                abs(
                    confirmed_htf.average[index]
                    - confirmed_htf.previous_average[index]
                )
                / current_atr
                >= candidate.threshold
            )
        if candidate.filter_kind == "max_ltf_slope_atr":
            return (
                abs(pullback.average[index] - pullback.average[index - 1])
                / current_atr
                <= candidate.threshold
            )
        raise ValueError(f"unknown filter kind: {candidate.filter_kind}")

    return allowed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_consistency_filter_results.json"),
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
    confirmed_htf = trend_context[0]
    assert confirmed_htf is not None

    candidates = [ConsistencyCandidate("baseline")]
    candidates += [
        ConsistencyCandidate(f"loss_cooldown_{bars}", loss_cooldown_bars=bars)
        for bars in (4, 8, 16, 32)
    ]
    candidates.append(
        ConsistencyCandidate(
            "stop_after_loss_for_day", stop_after_loss_for_day=True
        )
    )
    candidates += [
        ConsistencyCandidate(f"max_risk_{value:g}atr", "max_risk_atr", value)
        for value in (1.25, 1.5, 2.0, 2.5)
    ]
    candidates += [
        ConsistencyCandidate(
            f"max_ma_distance_{value:g}atr", "max_ma_distance_atr", value
        )
        for value in (0.75, 1.0, 1.5, 2.0)
    ]
    candidates += [
        ConsistencyCandidate(
            f"min_htf_slope_{value:g}atr", "min_htf_slope_atr", value
        )
        for value in (0.2, 0.4, 0.7)
    ]
    candidates += [
        ConsistencyCandidate(
            f"max_ltf_slope_{value:g}atr", "max_ltf_slope_atr", value
        )
        for value in (0.08, 0.12, 0.16)
    ]

    rows: list[dict[str, object]] = []
    for candidate in candidates:
        trades = _simulate(
            data,
            args.cost_pct,
            signal,
            atr=atr,
            pullback=pullback,
            trend_context=trend_context,
            local_dow=local_dow,
            entry_filter=_entry_filter(candidate, atr, pullback, confirmed_htf),
            loss_cooldown_bars=candidate.loss_cooldown_bars,
            stop_after_loss_for_day=candidate.stop_after_loss_for_day,
        )
        periods = _consistency_stats(trades)
        rows.append(
            {
                "candidate": asdict(candidate),
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
            "history_end": data.times[-1].isoformat(),
            "signal": asdict(signal),
            "exit": "strict RR1 with 0.5R next-bar breakeven",
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
            "selected consistency filter stayed positive in both unseen periods"
            if adopted
            else "no consistency filter passed all period gates"
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"selected": selected, "adopted": adopted}, indent=2))
    return 0 if adopted else 2


if __name__ == "__main__":
    raise SystemExit(main())
