"""Validate 15m MA20 pullback quality with confirmed 4H direction."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

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
    _sma,
)
from research_yosuga_dow_htf_filter import HtfCandidate
from research_yosuga_dow_htf_filter import ConfirmedHtf
from research_yosuga_dow_rr_breakeven import (
    ATR_LENGTH,
    STOP_ATR_MULTIPLE,
    TARGET_R,
    RiskTrade,
    _atr,
    _entry_allowed,
    _period_stats,
    _trend_context,
)


PULLBACK_MA_LENGTH = 20


@dataclass(frozen=True, slots=True)
class PullbackCandidate:
    htf: HtfCandidate
    pullback_lookback_bars: int
    require_ma_slope: bool
    breakeven_trigger_r: float | None
    require_local_dow: bool = False

    @property
    def name(self) -> str:
        slope = "slope" if self.require_ma_slope else "no_slope"
        breakeven = (
            "no_be"
            if self.breakeven_trigger_r is None
            else f"be_{self.breakeven_trigger_r:g}r"
        )
        local_dow = "local_dow" if self.require_local_dow else "no_local_dow"
        return (
            f"{self.htf.name}_ma20_reaccel_{self.pullback_lookback_bars}bars_"
            f"{slope}_{breakeven}_{local_dow}"
        )


@dataclass(frozen=True, slots=True)
class PullbackState:
    average: np.ndarray
    long_touch_age: np.ndarray
    short_touch_age: np.ndarray


def _local_dow_trend(data: Prepared) -> np.ndarray:
    """Return the persistent 15m Dow direction used by the Pine indicator."""
    event_direction = np.zeros(data.close.size, dtype=np.int8)
    for index, direction in data.cross_events:
        event_direction[index] = direction
    result = np.zeros(data.close.size, dtype=np.int8)
    current = 0
    for index, direction in enumerate(event_direction):
        if direction:
            current = int(direction)
        result[index] = current
    return result


def _pullback_state(data: Prepared) -> PullbackState:
    average = _sma(data.close, PULLBACK_MA_LENGTH)
    long_touch_age = np.full(data.close.size, -1, dtype=np.int32)
    short_touch_age = np.full(data.close.size, -1, dtype=np.int32)
    last_long_touch = -1
    last_short_touch = -1
    for index in range(data.close.size):
        if not np.isnan(average[index]):
            if data.low[index] <= average[index]:
                last_long_touch = index
            if data.high[index] >= average[index]:
                last_short_touch = index
        if last_long_touch >= 0:
            long_touch_age[index] = index - last_long_touch
        if last_short_touch >= 0:
            short_touch_age[index] = index - last_short_touch
    return PullbackState(average, long_touch_age, short_touch_age)


def _pullback_allowed(
    data: Prepared,
    state: PullbackState,
    index: int,
    direction: int,
    candidate: PullbackCandidate,
) -> bool:
    if index == 0 or np.isnan(state.average[index]):
        return False
    touch_age = (
        int(state.long_touch_age[index])
        if direction == 1
        else int(state.short_touch_age[index])
    )
    touched_recently = 1 <= touch_age <= candidate.pullback_lookback_bars
    reclaimed_side = direction * (data.close[index] - state.average[index]) > 0
    slope_ok = (
        not candidate.require_ma_slope
        or direction * (state.average[index] - state.average[index - 1]) > 0
    )
    return bool(touched_recently and reclaimed_side and slope_ok)


def _simulate(
    data: Prepared,
    cost_pct: float,
    candidate: PullbackCandidate,
    atr: np.ndarray | None = None,
    pullback: PullbackState | None = None,
    trend_context: tuple[ConfirmedHtf | None, np.ndarray | None] | None = None,
    local_dow: np.ndarray | None = None,
    entry_delay_bars: int = 0,
    stop_buffer_atr: float = 0.1,
    target_r: float = TARGET_R,
    entry_filter: Callable[[int, int, float, float], bool] | None = None,
    loss_cooldown_bars: int = 0,
    stop_after_loss_for_day: bool = False,
) -> list[RiskTrade]:
    if entry_delay_bars < -1:
        raise ValueError("entry_delay_bars must be -1 or greater")
    if stop_buffer_atr < 0:
        raise ValueError("stop_buffer_atr must be non-negative")
    if target_r <= 0:
        raise ValueError("target_r must be positive")
    if loss_cooldown_bars < 0:
        raise ValueError("loss_cooldown_bars must be non-negative")
    atr = _atr(data) if atr is None else atr
    pullback = _pullback_state(data) if pullback is None else pullback
    features, dow_trend = (
        _trend_context(data, candidate.htf)
        if trend_context is None
        else trend_context
    )
    local_dow = _local_dow_trend(data) if local_dow is None else local_dow
    position = 0
    entry_index = -1
    entry_price = np.nan
    stop_price = np.nan
    target_price = np.nan
    trigger_price = np.nan
    breakeven_active = False
    armed_direction = 0
    armed_index = -1
    armed_extreme = np.nan
    pending_direction = 0
    pending_entry_index = -1
    pending_extreme = np.nan
    last_loss_exit_index = -1_000_000_000
    last_loss_exit_date = None
    trades: list[RiskTrade] = []

    def entry_policy_allows(
        index: int, direction: int, entry: float, stop: float
    ) -> bool:
        if (
            loss_cooldown_bars > 0
            and index - last_loss_exit_index <= loss_cooldown_bars
        ):
            return False
        if (
            stop_after_loss_for_day
            and last_loss_exit_date == data.times[index].date()
        ):
            return False
        return entry_filter is None or entry_filter(index, direction, entry, stop)

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
                if trades[-1].return_pct <= 0:
                    last_loss_exit_index = index
                    last_loss_exit_date = data.times[index].date()
                position = 0
                entry_index = -1
                entry_price = np.nan
                stop_price = np.nan
                target_price = np.nan
                trigger_price = np.nan
                breakeven_active = False
                armed_direction = 0
                armed_index = -1
                armed_extreme = np.nan

        if position != 0 or index == 0 or np.isnan(atr[index]):
            continue

        if pending_direction != 0:
            pending_extreme = (
                min(pending_extreme, data.low[index])
                if pending_direction == 1
                else max(pending_extreme, data.high[index])
            )
            if index < pending_entry_index:
                continue
            direction_still_valid = _entry_allowed(
                pending_direction,
                index,
                candidate.htf,
                features,
                dow_trend,
            ) and (
                not candidate.require_local_dow
                or pending_direction == int(local_dow[index])
            )
            correct_side = (
                pending_direction
                * (data.close[index] - pullback.average[index])
                > 0
            )
            if direction_still_valid and correct_side:
                position = pending_direction
                entry_index = index
                entry_price = data.close[index]
                stop_price = (
                    pending_extreme - position * atr[index] * stop_buffer_atr
                )
                risk_distance = position * (entry_price - stop_price)
                entry_accepted = risk_distance > 0 and entry_policy_allows(
                    index, position, entry_price, stop_price
                )
                if entry_accepted:
                    target_price = (
                        entry_price + position * risk_distance * target_r
                    )
                    trigger_r = (
                        candidate.breakeven_trigger_r
                        if candidate.breakeven_trigger_r is not None
                        else target_r
                    )
                    trigger_price = (
                        entry_price + position * risk_distance * trigger_r
                    )
                    breakeven_active = False
                else:
                    position = 0
                    entry_index = -1
                    entry_price = np.nan
            pending_direction = 0
            pending_entry_index = -1
            pending_extreme = np.nan
            continue

        if armed_direction != 0:
            age = index - armed_index
            direction_still_valid = _entry_allowed(
                armed_direction,
                index,
                candidate.htf,
                features,
                dow_trend,
            ) and (
                not candidate.require_local_dow
                or armed_direction == int(local_dow[index])
            )
            if age > candidate.pullback_lookback_bars or not direction_still_valid:
                armed_direction = 0
                armed_index = -1
                armed_extreme = np.nan
            elif age >= 1:
                armed_extreme = (
                    min(armed_extreme, data.low[index])
                    if armed_direction == 1
                    else max(armed_extreme, data.high[index])
                )
                average = pullback.average[index]
                slope_ok = (
                    not candidate.require_ma_slope
                    or armed_direction
                    * (average - pullback.average[index - 1])
                    > 0
                )
                reaccelerated = (
                    data.close[index] > data.high[index - 1]
                    if armed_direction == 1
                    else data.close[index] < data.low[index - 1]
                )
                correct_side = armed_direction * (data.close[index] - average) > 0
                if slope_ok and reaccelerated and correct_side:
                    if entry_delay_bars > 0:
                        pending_direction = armed_direction
                        pending_entry_index = index + entry_delay_bars
                        pending_extreme = armed_extreme
                    else:
                        position = armed_direction
                        entry_index = index
                        entry_price = data.close[index]
                        stop_price = (
                            armed_extreme
                            - position * atr[index] * stop_buffer_atr
                        )
                        risk_distance = position * (entry_price - stop_price)
                        entry_accepted = risk_distance > 0 and entry_policy_allows(
                            index, position, entry_price, stop_price
                        )
                        if not entry_accepted:
                            position = 0
                            entry_index = -1
                            entry_price = np.nan
                            armed_direction = 0
                            armed_index = -1
                            armed_extreme = np.nan
                            continue
                        target_price = (
                            entry_price + position * risk_distance * target_r
                        )
                        trigger_r = (
                            candidate.breakeven_trigger_r
                            if candidate.breakeven_trigger_r is not None
                            else target_r
                        )
                        trigger_price = (
                            entry_price + position * risk_distance * trigger_r
                        )
                        breakeven_active = False
                    armed_direction = 0
                    armed_index = -1
                    armed_extreme = np.nan
                    continue

        if armed_direction == 0 and not np.isnan(pullback.average[index - 1]):
            bar_range = data.high[index] - data.low[index]
            long_close_location = (
                (data.close[index] - data.low[index]) / bar_range
                if bar_range > 0
                else 0.5
            )
            short_close_location = 1.0 - long_close_location
            long_touch = (
                _entry_allowed(1, index, candidate.htf, features, dow_trend)
                and (not candidate.require_local_dow or local_dow[index] == 1)
                and data.low[index - 1] > pullback.average[index - 1]
                and data.low[index] <= pullback.average[index]
                and data.close[index] >= pullback.average[index]
                and long_close_location >= 0.65
            )
            short_touch = (
                _entry_allowed(-1, index, candidate.htf, features, dow_trend)
                and (not candidate.require_local_dow or local_dow[index] == -1)
                and data.high[index - 1] < pullback.average[index - 1]
                and data.high[index] >= pullback.average[index]
                and data.close[index] <= pullback.average[index]
                and short_close_location >= 0.65
            )
            touch_direction = 1 if long_touch else -1 if short_touch else 0
            if touch_direction != 0:
                touch_extreme = (
                    data.low[index] if touch_direction == 1 else data.high[index]
                )
                if entry_delay_bars == -1:
                    position = touch_direction
                    entry_index = index
                    entry_price = data.close[index]
                    stop_price = (
                        touch_extreme
                        - position * atr[index] * stop_buffer_atr
                    )
                    risk_distance = position * (entry_price - stop_price)
                    entry_accepted = risk_distance > 0 and entry_policy_allows(
                        index, position, entry_price, stop_price
                    )
                    if entry_accepted:
                        target_price = (
                            entry_price + position * risk_distance * target_r
                        )
                        trigger_r = (
                            candidate.breakeven_trigger_r
                            if candidate.breakeven_trigger_r is not None
                            else target_r
                        )
                        trigger_price = (
                            entry_price + position * risk_distance * trigger_r
                        )
                        breakeven_active = False
                    else:
                        position = 0
                        entry_index = -1
                        entry_price = np.nan
                else:
                    armed_direction = touch_direction
                    armed_index = index
                    armed_extreme = touch_extreme
    return trades


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--cost-pct", type=float, default=0.01)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_dow_pullback_entry_results.json"),
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
        PullbackCandidate(htf, lookback, slope, trigger, local_dow)
        for htf in htf_candidates
        for lookback in (4, 8, 16)
        for slope in (False, True)
        for trigger in (None, 0.5)
        for local_dow in (False, True)
    ]
    atr = _atr(data)
    pullback = _pullback_state(data)
    local_dow = _local_dow_trend(data)
    trend_contexts = {
        htf.name: _trend_context(data, htf) for htf in htf_candidates
    }
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        periods = _period_stats(
            _simulate(
                data,
                args.cost_pct,
                candidate,
                atr=atr,
                pullback=pullback,
                trend_context=trend_contexts[candidate.htf.name],
                local_dow=local_dow,
            )
        )
        rows.append(
            {
                "candidate": {
                    "htf": asdict(candidate.htf),
                    "pullback_lookback_bars": candidate.pullback_lookback_bars,
                    "require_ma_slope": candidate.require_ma_slope,
                    "breakeven_trigger_r": candidate.breakeven_trigger_r,
                    "require_local_dow": candidate.require_local_dow,
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
            "entry": (
                "arm on the first MA20 contact from the 4H-trend side when the "
                "contact bar closes back on the trend side and in the trend-side "
                "35% of its range; enter only after a later close breaks the "
                "previous 15m high/low, optionally with MA20 slope and persistent "
                "15m Dow-direction alignment"
            ),
            "initial_stop": (
                f"pullback extreme plus {ATR_LENGTH}-period ATR x 0.1 buffer"
            ),
            "target": f"full exit at {TARGET_R:g}R",
            "breakeven": "optional 0.5R trigger, effective from next bar",
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
            "selected pullback candidate stayed positive in both unseen periods"
            if adopted
            else "no selected pullback candidate stayed positive in both unseen periods"
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload["adopted"], ensure_ascii=False, indent=2))
    return 0 if adopted else 2


if __name__ == "__main__":
    raise SystemExit(main())
