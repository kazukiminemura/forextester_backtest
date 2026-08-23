"""Audit the wall/Yosuga setup by Tokyo, London, and New York session."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import PERIODS, SYMBOLS, _confirmed_four_hour_walls
from research_strict_rr_portfolio import Prepared, RTrade, _prepare, _signals, _simulate
from research_yosuga_5m_time_filters import _bin_stats, _candidate, _period_rows


TOKYO = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")
MARKETS = ("tokyo", "london", "new_york")
MARKET_NAMES_JA = {
    "tokyo": "東京市場",
    "london": "ロンドン市場",
    "new_york": "NY市場",
    "off_session": "主要市場外",
}
MIN_TRAIN_TRADES = 100
MIN_VALIDATION_TRADES = 40


def _local_hour(entry_time_utc: datetime, zone: ZoneInfo) -> float:
    aware_utc = entry_time_utc.replace(tzinfo=timezone.utc)
    local = aware_utc.astimezone(zone)
    return local.hour + local.minute / 60.0


def _active_markets(entry_time_utc: datetime) -> tuple[str, ...]:
    """Return markets open at entry, using local hours and historical DST."""
    active: list[str] = []
    if 9.0 <= _local_hour(entry_time_utc, TOKYO) < 17.0:
        active.append("tokyo")
    if 8.0 <= _local_hour(entry_time_utc, LONDON) < 17.0:
        active.append("london")
    if 8.0 <= _local_hour(entry_time_utc, NEW_YORK) < 17.0:
        active.append("new_york")
    return tuple(active)


def _exclusive_market(entry_time_utc: datetime) -> str:
    """Assign overlaps to the latest-opening active market."""
    active = _active_markets(entry_time_utc)
    for market in ("new_york", "london", "tokyo"):
        if market in active:
            return market
    return "off_session"


def _market_group_stats(
    rows: list[RTrade], *, exclusive: bool
) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[str, list[RTrade]] = {
        market: [] for market in (*MARKETS, "off_session")
    }
    for trade in rows:
        if exclusive:
            grouped[_exclusive_market(trade.entry_time)].append(trade)
            continue
        active = _active_markets(trade.entry_time)
        if active:
            for market in active:
                grouped[market].append(trade)
        else:
            grouped["off_session"].append(trade)
    return {market: _bin_stats(grouped[market]) for market in grouped}


def _period_market_stats(
    rows: list[RTrade], *, exclusive: bool
) -> dict[str, dict[str, dict[str, float | int | None]]]:
    return {
        name: _market_group_stats(_period_rows(rows, start, end), exclusive=exclusive)
        for name, (start, end, _months) in PERIODS.items()
    }


def _eligible_market(
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


def _select_markets(
    period_groups: dict[str, dict[str, dict[str, float | int | None]]]
) -> list[str]:
    train = period_groups["train_2010_2018"]
    validation = period_groups["validation_2019_2022"]
    return [
        market
        for market in MARKETS
        if _eligible_market(train[market], validation[market])
    ]


def _filtered_directions(
    data: Prepared, directions: np.ndarray, allowed_markets: set[str]
) -> np.ndarray:
    filtered = directions.copy()
    for signal_raw in np.flatnonzero(filtered):
        signal_index = int(signal_raw)
        entry_index = signal_index + 1
        if entry_index >= len(data.times):
            filtered[signal_index] = 0
            continue
        if _exclusive_market(data.times[entry_index]) not in allowed_markets:
            filtered[signal_index] = 0
    return filtered


def _period_stats(rows: list[RTrade]) -> dict[str, dict[str, float | int | None]]:
    return {
        name: _bin_stats(_period_rows(rows, start, end))
        for name, (start, end, _months) in PERIODS.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--timeframe", choices=("5m", "15m"), default="5m")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts/yosuga_5m_market_session_results.json"),
    )
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    candidate = replace(
        _candidate(),
        timeframe=args.timeframe,
        session_start=0,
        session_end=24,
    )
    baseline_rows: list[RTrade] = []
    prepared_cache: dict[str, tuple[Prepared, np.ndarray]] = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        data = _prepare(repository, symbol, end, args.timeframe)
        data.htf_trend = _confirmed_four_hour_walls(data, 5).trend
        directions = _signals(data, candidate)
        prepared_cache[symbol] = (data, directions)
        baseline_rows.extend(_simulate(symbol, data, candidate, directions))

    exclusive_groups = _period_market_stats(baseline_rows, exclusive=True)
    overlapping_groups = _period_market_stats(baseline_rows, exclusive=False)
    selected_markets = _select_markets(exclusive_groups)

    filtered_rows: list[RTrade] = []
    if selected_markets:
        for symbol, (data, directions) in prepared_cache.items():
            filtered = _filtered_directions(data, directions, set(selected_markets))
            filtered_rows.extend(_simulate(symbol, data, candidate, filtered))

    payload = {
        "strategy": {
            "name": (
                f"4H wall + {args.timeframe} structure + {args.timeframe} "
                "Yosuga PA, strict RR1"
            ),
            "symbols": list(SYMBOLS),
            "signal_generation": "24 hours for fair market-session comparison",
            "source_time_assumption": "naive Forex Tester timestamps are UTC",
            "candidate": asdict(candidate),
        },
        "market_definition": {
            "tokyo": "09:00-17:00 Asia/Tokyo",
            "london": "08:00-17:00 Europe/London (historical DST applied)",
            "new_york": "08:00-17:00 America/New_York (historical DST applied)",
            "exclusive_overlap_priority": ["new_york", "london", "tokyo"],
            "exclusive_use": "selection and filtered backtest",
            "overlapping_use": "reference only; one trade may appear in multiple markets",
        },
        "selection_rule": {
            "periods_used": ["train_2010_2018", "validation_2019_2022"],
            "minimum_trades": {
                "train": MIN_TRAIN_TRADES,
                "validation": MIN_VALIDATION_TRADES,
            },
            "condition": (
                "exclusive market win rate >= 50% and profit rate >= 0% in both "
                "train and validation"
            ),
            "holdout_not_used_for_selection": True,
        },
        "baseline": {
            "periods": _period_stats(baseline_rows),
            "exclusive_by_market": exclusive_groups,
            "overlapping_actual_market_hours": overlapping_groups,
        },
        "selected_filter": {
            "markets": selected_markets,
            "market_names_ja": [MARKET_NAMES_JA[key] for key in selected_markets],
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
