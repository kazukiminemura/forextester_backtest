"""Audit 5-minute wall/Yosuga trades by JST hour, weekday, and daily order."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import (
    PERIODS,
    SYMBOLS,
    _confirmed_four_hour_walls,
)
from research_strict_rr_portfolio import (
    Candidate,
    Prepared,
    RTrade,
    _prepare,
    _signals,
    _simulate,
)


WEEKDAYS_JA = ("月", "火", "水", "木", "金", "土", "日")
MIN_TRAIN = {"hour": 50, "weekday": 100, "daily_order": 30}
MIN_VALIDATION = {"hour": 20, "weekday": 40, "daily_order": 15}


def _candidate() -> Candidate:
    """Return the shared Yosuga PA parameters used by the timeframe audits."""
    return Candidate(
        "yosuga_pa",
        timeframe="5m",
        session_start=6,
        session_end=16,
        trend_fast=150,
        trend_slow=150,
        require_trend=False,
        entry_ema=150,
        atr_length=42,
        pullback_lookback=10_000_000,
        pa_min_score=1,
        zone_atr=0.50,
        swing_buffer_atr=0.20,
        max_risk_atr=2.50,
        trigger_break=True,
        cooldown_bars=0,
    )


def _jst_data(data: Prepared) -> Prepared:
    return replace(
        data,
        times=[time + timedelta(hours=9) for time in data.times],
    )


def _bin_stats(rows: list[RTrade]) -> dict[str, float | int | None]:
    wins = sum(trade.result_r > 0 for trade in rows)
    losses = sum(trade.result_r < 0 for trade in rows)
    trades = len(rows)
    net_r = sum(trade.result_r for trade in rows)
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / trades * 100.0 if trades else 0.0,
        "profit_factor": wins / losses if losses else None,
        "net_r": net_r,
        "profit_rate_pct": net_r / trades * 100.0 if trades else 0.0,
    }


def _period_rows(rows: list[RTrade], start: int, end: int) -> list[RTrade]:
    return [trade for trade in rows if start <= trade.entry_time.year <= end]


def _group_stats(
    rows: list[RTrade], key_name: str
) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[int, list[RTrade]] = {}
    for trade in rows:
        if key_name == "hour":
            key = trade.entry_time.hour
        elif key_name == "weekday":
            key = trade.entry_time.weekday()
        else:
            key = trade.daily_trade_number
        grouped.setdefault(key, []).append(trade)
    return {str(key): _bin_stats(grouped[key]) for key in sorted(grouped)}


def _eligible(
    train: dict[str, float | int | None],
    validation: dict[str, float | int | None],
    key_name: str,
) -> bool:
    return (
        int(train["trades"]) >= MIN_TRAIN[key_name]
        and int(validation["trades"]) >= MIN_VALIDATION[key_name]
        and float(train["win_rate"]) >= 50.0
        and float(validation["win_rate"]) >= 50.0
        and float(train["profit_rate_pct"]) >= 0.0
        and float(validation["profit_rate_pct"]) >= 0.0
    )


def _select_keys(
    period_groups: dict[str, dict[str, dict[str, float | int | None]]],
    key_name: str,
) -> list[int]:
    train = period_groups["train_2010_2018"]
    validation = period_groups["validation_2019_2022"]
    return [
        int(key)
        for key in sorted(set(train) & set(validation), key=int)
        if _eligible(train[key], validation[key], key_name)
    ]


def _select_daily_cap(
    period_groups: dict[str, dict[str, dict[str, float | int | None]]]
) -> int:
    eligible = set(_select_keys(period_groups, "daily_order"))
    cap = 0
    while cap + 1 in eligible:
        cap += 1
    return cap


def _period_stats(rows: list[RTrade]) -> dict[str, dict[str, float | int | None]]:
    return {
        name: _bin_stats(_period_rows(rows, start, end))
        for name, (start, end, _months) in PERIODS.items()
    }


def _period_group_stats(
    rows: list[RTrade], key_name: str
) -> dict[str, dict[str, dict[str, float | int | None]]]:
    return {
        name: _group_stats(_period_rows(rows, start, end), key_name)
        for name, (start, end, _months) in PERIODS.items()
    }


def _filtered_directions(
    data: Prepared,
    directions: np.ndarray,
    allowed_hours: set[int],
    allowed_weekdays: set[int],
) -> np.ndarray:
    filtered = directions.copy()
    for signal_raw in np.flatnonzero(filtered):
        signal_index = int(signal_raw)
        entry_index = signal_index + 1
        if entry_index >= len(data.times):
            filtered[signal_index] = 0
            continue
        entry_time = data.times[entry_index]
        if (
            entry_time.hour not in allowed_hours
            or entry_time.weekday() not in allowed_weekdays
        ):
            filtered[signal_index] = 0
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_5m_time_filter_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    candidate = _candidate()
    baseline_rows: list[RTrade] = []
    prepared_cache: dict[str, tuple[Prepared, np.ndarray]] = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        data = _prepare(repository, symbol, end, "5m")
        # The integrated Pine uses five confirmed 4H bars on each side.
        data.htf_trend = _confirmed_four_hour_walls(data, 5).trend
        directions = _signals(data, candidate)
        data_jst = _jst_data(data)
        prepared_cache[symbol] = (data_jst, directions)
        baseline_rows.extend(_simulate(symbol, data_jst, candidate, directions))

    hour_groups = _period_group_stats(baseline_rows, "hour")
    weekday_groups = _period_group_stats(baseline_rows, "weekday")
    daily_order_groups = _period_group_stats(baseline_rows, "daily_order")
    allowed_hours = _select_keys(hour_groups, "hour")
    allowed_weekdays = _select_keys(weekday_groups, "weekday")
    max_daily_trades = _select_daily_cap(daily_order_groups)

    filtered_rows: list[RTrade] = []
    if allowed_hours and allowed_weekdays and max_daily_trades > 0:
        filtered_candidate = replace(candidate, max_trades_per_day=max_daily_trades)
        for symbol, (data_jst, directions) in prepared_cache.items():
            filtered = _filtered_directions(
                data_jst,
                directions,
                set(allowed_hours),
                set(allowed_weekdays),
            )
            filtered_rows.extend(
                _simulate(symbol, data_jst, filtered_candidate, filtered)
            )

    payload = {
        "strategy": {
            "name": "4H wall + 15m structure + 5m Yosuga PA, strict RR1",
            "symbols": list(SYMBOLS),
            "entry_session_raw_data_time": "06:00-16:00",
            "analysis_timezone": "Asia/Tokyo (UTC+9 fixed conversion)",
            "candidate": asdict(candidate),
        },
        "selection_rule": {
            "periods_used": ["train_2010_2018", "validation_2019_2022"],
            "minimum_trades": {
                "train": MIN_TRAIN,
                "validation": MIN_VALIDATION,
            },
            "condition": (
                "win rate >= 50% and profit rate >= 0% in both train and "
                "validation; daily cap is the largest contiguous prefix from trade 1"
            ),
            "holdout_not_used_for_selection": True,
        },
        "baseline": {
            "periods": _period_stats(baseline_rows),
            "by_hour_jst": hour_groups,
            "by_weekday_jst": weekday_groups,
            "by_daily_trade_order_jst": daily_order_groups,
        },
        "selected_filter": {
            "hours_jst": allowed_hours,
            "weekdays": allowed_weekdays,
            "weekday_names": [WEEKDAYS_JA[index] for index in allowed_weekdays],
            "max_daily_trades": max_daily_trades,
        },
        "filtered": {
            "periods": _period_stats(filtered_rows),
            "trades": len(filtered_rows),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload["selected_filter"], ensure_ascii=False))
    print(json.dumps(payload["filtered"]["periods"], ensure_ascii=False))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
