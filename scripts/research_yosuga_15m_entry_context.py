"""Audit 15m Yosuga entry shapes, 4H deceleration, and post-loss controls."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import (
    PERIODS,
    SYMBOLS,
    _confirmed_four_hour_walls,
    _four_hour_groups,
)
from research_strict_rr_portfolio import Prepared, RTrade, _prepare, _signals, _simulate
from research_yosuga_5m_time_filters import _bin_stats, _candidate, _period_rows


MIN_TRAIN_TRADES = 100
MIN_VALIDATION_TRADES = 40
TWO_HOUR_BARS_15M = 8
FORMS = ("wick_rejection", "engulfing", "wick_and_engulfing")
FORM_NAMES_JA = {
    "wick_rejection": "ヒゲ反転",
    "engulfing": "包み足",
    "wick_and_engulfing": "ヒゲ反転＋包み足",
}


@dataclass(frozen=True, slots=True)
class TradeContext:
    trade: RTrade
    form: str
    htf_decelerating: bool


def _form_label(wick: bool, engulfing: bool) -> str:
    if wick and engulfing:
        return "wick_and_engulfing"
    if wick:
        return "wick_rejection"
    if engulfing:
        return "engulfing"
    return "none"


def _pa_forms(data: Prepared, directions: np.ndarray) -> np.ndarray:
    previous_open = np.roll(data.open, 1)
    previous_close = np.roll(data.close, 1)
    body = np.maximum(np.abs(data.close - data.open), data.atr * 0.05)
    upper_wick = data.high - np.maximum(data.open, data.close)
    lower_wick = np.minimum(data.open, data.close) - data.low
    bullish_wick = (lower_wick >= body * 1.5) & (lower_wick >= data.atr * 0.25)
    bearish_wick = (upper_wick >= body * 1.5) & (upper_wick >= data.atr * 0.25)
    bullish_engulfing = (
        (data.close > data.open)
        & (previous_close < previous_open)
        & (data.close >= previous_open)
        & (data.open <= previous_close)
    )
    bearish_engulfing = (
        (data.close < data.open)
        & (previous_close > previous_open)
        & (data.close <= previous_open)
        & (data.open >= previous_close)
    )
    labels = np.full(data.close.size, "none", dtype=object)
    for index_raw in np.flatnonzero(directions):
        index = int(index_raw)
        if directions[index] == 1:
            labels[index] = _form_label(
                bool(bullish_wick[index]), bool(bullish_engulfing[index])
            )
        else:
            labels[index] = _form_label(
                bool(bearish_wick[index]), bool(bearish_engulfing[index])
            )
    return labels


def _decelerating_groups(closes: np.ndarray, trends: np.ndarray) -> np.ndarray:
    """Use only the two latest completed 4H close-to-close advances."""
    result = np.zeros(closes.size, dtype=bool)
    for group in range(3, closes.size):
        trend = int(trends[group])
        if trend == 0 or int(trends[group - 1]) != trend:
            continue
        latest_progress = trend * (closes[group - 1] - closes[group - 2])
        previous_progress = trend * (closes[group - 2] - closes[group - 3])
        result[group] = latest_progress < previous_progress
    return result


def _htf_deceleration(data: Prepared) -> np.ndarray:
    _highs, _lows, group_for_bar = _four_hour_groups(data)
    group_count = int(group_for_bar[-1]) + 1 if group_for_bar.size else 0
    group_closes = np.empty(group_count)
    group_trends = np.zeros(group_count, dtype=np.int8)
    for bar_index, group_raw in enumerate(group_for_bar):
        group = int(group_raw)
        group_closes[group] = data.close[bar_index]
        group_trends[group] = data.htf_trend[bar_index]
    return _decelerating_groups(group_closes, group_trends)[group_for_bar]


def _annotate(
    data: Prepared,
    directions: np.ndarray,
    trades: list[RTrade],
) -> list[TradeContext]:
    forms = _pa_forms(data, directions)
    decelerating = _htf_deceleration(data)
    index_by_time = {time: index for index, time in enumerate(data.times)}
    contexts: list[TradeContext] = []
    for trade in trades:
        entry_index = index_by_time[trade.entry_time]
        signal_index = entry_index - 1
        contexts.append(
            TradeContext(
                trade=trade,
                form=str(forms[signal_index]),
                htf_decelerating=bool(decelerating[signal_index]),
            )
        )
    return contexts


def _period_stats(rows: list[RTrade]) -> dict[str, dict[str, float | int | None]]:
    return {
        name: _bin_stats(_period_rows(rows, start, end))
        for name, (start, end, _months) in PERIODS.items()
    }


def _context_group_stats(
    rows: list[TradeContext], key_name: str
) -> dict[str, dict[str, dict[str, float | int | None]]]:
    output: dict[str, dict[str, dict[str, float | int | None]]] = {}
    for period_name, (start, end, _months) in PERIODS.items():
        period_rows = [
            row for row in rows if start <= row.trade.entry_time.year <= end
        ]
        grouped: dict[str, list[RTrade]] = {}
        for row in period_rows:
            if key_name == "form":
                key = row.form
            elif key_name == "htf_decelerating":
                key = str(row.htf_decelerating).lower()
            else:
                key = str(row.trade.previous_result_r == -1.0).lower()
            grouped.setdefault(key, []).append(row.trade)
        output[period_name] = {
            key: _bin_stats(grouped.get(key, []))
            for key in sorted(grouped)
        }
    return output


def _eligible(
    train: dict[str, float | int | None],
    validation: dict[str, float | int | None],
) -> bool:
    return (
        int(train["trades"]) >= MIN_TRAIN_TRADES
        and int(validation["trades"]) >= MIN_VALIDATION_TRADES
        and float(train["win_rate"]) >= 50.0
        and float(validation["win_rate"]) >= 50.0
        and float(train["profit_rate_pct"]) >= 0.0
        and float(validation["profit_rate_pct"]) >= 0.0
    )


def _select_forms(
    groups: dict[str, dict[str, dict[str, float | int | None]]]
) -> list[str]:
    train = groups["train_2010_2018"]
    validation = groups["validation_2019_2022"]
    return [
        form
        for form in FORMS
        if form in train
        and form in validation
        and _eligible(train[form], validation[form])
    ]


def _bad_subgroup(
    groups: dict[str, dict[str, dict[str, float | int | None]]], key: str
) -> bool:
    train = groups["train_2010_2018"].get(key, _bin_stats([]))
    validation = groups["validation_2019_2022"].get(key, _bin_stats([]))
    return (
        int(train["trades"]) >= MIN_TRAIN_TRADES
        and int(validation["trades"]) >= MIN_VALIDATION_TRADES
        and float(train["win_rate"]) < 50.0
        and float(validation["win_rate"]) < 50.0
        and float(train["profit_rate_pct"]) < 0.0
        and float(validation["profit_rate_pct"]) < 0.0
    )


def _strategy_still_bad(periods: dict[str, dict[str, float | int | None]]) -> bool:
    return all(
        float(periods[period]["win_rate"]) < 50.0
        and float(periods[period]["profit_rate_pct"]) < 0.0
        for period in ("train_2010_2018", "validation_2019_2022")
    )


def _filter_directions(
    directions: np.ndarray,
    forms: np.ndarray,
    allowed_forms: set[str] | None = None,
    decelerating: np.ndarray | None = None,
) -> np.ndarray:
    filtered = directions.copy()
    if allowed_forms is not None:
        filtered[~np.isin(forms, list(allowed_forms))] = 0
    if decelerating is not None:
        filtered[decelerating] = 0
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_15m_entry_context_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    candidate = replace(
        _candidate(), timeframe="15m", session_start=0, session_end=24
    )
    cache: dict[str, tuple[Prepared, np.ndarray, np.ndarray, np.ndarray]] = {}
    baseline_rows: list[RTrade] = []
    baseline_contexts: list[TradeContext] = []
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        data = _prepare(repository, symbol, end, "15m")
        data.htf_trend = _confirmed_four_hour_walls(data, 5).trend
        directions = _signals(data, candidate)
        forms = _pa_forms(data, directions)
        decelerating = _htf_deceleration(data)
        trades = _simulate(symbol, data, candidate, directions)
        cache[symbol] = (data, directions, forms, decelerating)
        baseline_rows.extend(trades)
        baseline_contexts.extend(_annotate(data, directions, trades))

    form_groups = _context_group_stats(baseline_contexts, "form")
    deceleration_groups = _context_group_stats(
        baseline_contexts, "htf_decelerating"
    )
    previous_loss_groups = _context_group_stats(baseline_contexts, "previous_loss")
    selected_forms = _select_forms(form_groups)
    exclude_deceleration = _bad_subgroup(deceleration_groups, "true")
    previous_loss_is_bad = _bad_subgroup(previous_loss_groups, "true")

    form_filtered_rows: list[RTrade] = []
    no_deceleration_rows: list[RTrade] = []
    for symbol, (data, directions, forms, decelerating) in cache.items():
        if selected_forms:
            form_filtered = _filter_directions(
                directions, forms, allowed_forms=set(selected_forms)
            )
            form_filtered_rows.extend(
                _simulate(symbol, data, candidate, form_filtered)
            )
        if exclude_deceleration:
            no_deceleration = _filter_directions(
                directions, forms, decelerating=decelerating
            )
            no_deceleration_rows.extend(
                _simulate(symbol, data, candidate, no_deceleration)
            )

    cooldown_rows: list[RTrade] = []
    cooldown_periods = _period_stats([])
    if previous_loss_is_bad:
        cooldown_candidate = replace(
            candidate, loss_cooldown_bars=TWO_HOUR_BARS_15M
        )
        for symbol, (data, directions, _forms, _decelerating) in cache.items():
            cooldown_rows.extend(
                _simulate(symbol, data, cooldown_candidate, directions)
            )
        cooldown_periods = _period_stats(cooldown_rows)

    stop_day_rows: list[RTrade] = []
    stop_day_applied = previous_loss_is_bad and _strategy_still_bad(cooldown_periods)
    if stop_day_applied:
        stop_day_candidate = replace(candidate, stop_after_loss_for_day=True)
        for symbol, (data, directions, _forms, _decelerating) in cache.items():
            stop_day_rows.extend(
                _simulate(symbol, data, stop_day_candidate, directions)
            )

    payload = {
        "strategy": {
            "name": "4H confirmed walls + 15m Yosuga PA, strict RR1",
            "symbols": list(SYMBOLS),
            "candidate": asdict(candidate),
        },
        "definitions": {
            "forms": FORM_NAMES_JA,
            "htf_decelerating": (
                "trend-direction close progress of the latest completed 4H bar "
                "is smaller than the preceding completed 4H bar; current 4H bar excluded"
            ),
            "previous_loss": "previous completed trade on the same symbol was -1R",
            "two_hour_cooldown": "8 x 15-minute bars after the loss exit",
        },
        "selection_rule": {
            "periods_used": ["train_2010_2018", "validation_2019_2022"],
            "minimum_trades": {
                "train": MIN_TRAIN_TRADES,
                "validation": MIN_VALIDATION_TRADES,
            },
            "positive_condition": (
                "win rate >= 50% and profit rate >= 0% in both train and validation"
            ),
            "negative_condition": (
                "win rate < 50% and profit rate < 0% in both train and validation"
            ),
            "holdout_not_used_for_selection": True,
        },
        "baseline": {
            "periods": _period_stats(baseline_rows),
            "by_entry_form": form_groups,
            "by_htf_decelerating": deceleration_groups,
            "by_previous_trade_loss": previous_loss_groups,
        },
        "decisions": {
            "selected_forms": selected_forms,
            "selected_form_names_ja": [FORM_NAMES_JA[key] for key in selected_forms],
            "exclude_htf_decelerating": exclude_deceleration,
            "previous_loss_is_bad": previous_loss_is_bad,
            "apply_two_hour_cooldown": previous_loss_is_bad,
            "cooldown_still_bad": (
                _strategy_still_bad(cooldown_periods) if previous_loss_is_bad else False
            ),
            "apply_stop_after_loss_for_day": stop_day_applied,
        },
        "variants": {
            "selected_forms_only": {
                "periods": _period_stats(form_filtered_rows),
                "trades": len(form_filtered_rows),
            },
            "exclude_htf_decelerating": {
                "periods": _period_stats(no_deceleration_rows),
                "trades": len(no_deceleration_rows),
            },
            "two_hour_cooldown_after_loss": {
                "periods": cooldown_periods,
                "trades": len(cooldown_rows),
            },
            "stop_after_loss_for_day": {
                "periods": _period_stats(stop_day_rows),
                "trades": len(stop_day_rows),
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload["decisions"], ensure_ascii=False))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
