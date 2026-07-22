"""Walk-forward parameter exploration for a Tamukai FX pair."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable

from forextester_backtest import HistoryRepository, TamukaiBacktester, TamukaiConfig
from forextester_backtest.models import Trade


@dataclass(frozen=True, slots=True)
class PeriodStats:
    trades: int
    wins: int
    win_rate: float
    net_profit: float
    expectancy: float
    expectancy_r: float


@dataclass(frozen=True, slots=True)
class Evaluation:
    config: TamukaiConfig
    train: PeriodStats
    validation: PeriodStats
    holdout: PeriodStats
    full: PeriodStats

    @property
    def robust(self) -> bool:
        enough = (
            self.train.trades >= 30
            and self.validation.trades >= 8
            and self.holdout.trades >= 5
        )
        return enough and all(
            period.expectancy > 0
            for period in (self.train, self.validation, self.holdout)
        )

    @property
    def selection_key(self) -> tuple[float, ...]:
        positive_periods = sum(
            period.expectancy > 0
            for period in (self.train, self.validation, self.holdout)
        )
        return (
            float(self.robust),
            float(positive_periods),
            min(
                self.train.expectancy_r,
                self.validation.expectancy_r,
                self.holdout.expectancy_r,
            ),
            min(
                self.train.win_rate,
                self.validation.win_rate,
                self.holdout.win_rate,
            ),
            self.full.trades,
        )


def _stats(trades: Iterable[Trade]) -> PeriodStats:
    rows = list(trades)
    wins = sum(trade.net_pnl > 0 for trade in rows)
    net = sum(trade.net_pnl for trade in rows)
    r_values: list[float] = []
    for trade in rows:
        if trade.initial_stop is None:
            continue
        risk = abs(trade.entry_price - trade.initial_stop) * trade.units
        if risk > 0:
            r_values.append(trade.net_pnl / risk)
    return PeriodStats(
        trades=len(rows),
        wins=wins,
        win_rate=wins / len(rows) * 100 if rows else 0.0,
        net_profit=net,
        expectancy=net / len(rows) if rows else 0.0,
        expectancy_r=sum(r_values) / len(r_values) if r_values else 0.0,
    )


def _period(trades: Iterable[Trade], start_year: int, end_year: int) -> PeriodStats:
    return _stats(
        trade for trade in trades if start_year <= trade.entry_time.year <= end_year
    )


def _exit_candidates() -> list[TamukaiConfig]:
    candidates: list[TamukaiConfig] = []
    base = TamukaiConfig()
    for target_r in (0.35, 0.5, 0.65, 0.8, 1.0):
        for fraction, break_even in (
            (1.0, False),
            (0.75, True),
            (0.5, True),
            (0.5, False),
        ):
            for direction in ("both", "long", "short"):
                candidates.append(
                    replace(
                        base,
                        first_target_r=target_r,
                        first_target_fraction=fraction,
                        move_stop_to_break_even=break_even,
                        direction=direction,
                    )
                )
    return candidates


def _filter_candidates(seed: TamukaiConfig) -> list[TamukaiConfig]:
    candidates: list[TamukaiConfig] = []
    hour_sets = (
        None,
        (3, 4, 5, 6, 8, 9, 10, 14, 16, 17, 18),
        (3, 5, 6, 8, 9, 10, 16, 18),
        (0, 1, 2, 3, 4, 5, 6, 8, 9, 10),
        (3, 4, 5, 6, 8, 9, 10, 14, 16, 17, 18, 19),
    )
    for hours in hour_sets:
        for min_slope in (0.03, 0.06, 0.10):
            for min_pullback in (0.5, 0.75, 1.0):
                for max_range in (1.0, 1.25, 1.5):
                    candidates.append(
                        replace(
                            seed,
                            entry_hours=hours,
                            min_slope_atr=min_slope,
                            min_pullback_atr=min_pullback,
                            max_range_atr=max_range,
                        )
                    )
    return candidates


def _robust_candidates() -> list[TamukaiConfig]:
    candidates: list[TamukaiConfig] = []
    base = TamukaiConfig(first_target_fraction=1.0)
    for target_r in (0.45, 0.5, 0.6):
        for min_slope in (0.03, 0.06, 0.10):
            for max_range in (0.75, 1.0, 1.25):
                for direction in ("both", "long", "short"):
                    candidates.append(
                        replace(
                            base,
                            first_target_r=target_r,
                            min_slope_atr=min_slope,
                            max_range_atr=max_range,
                            direction=direction,
                        )
                    )
    return candidates


def _pair_candidates() -> list[TamukaiConfig]:
    """Explore the four pair-specific axes requested for cross presets."""
    candidates: list[TamukaiConfig] = []
    base = TamukaiConfig()
    for direction in ("both", "long", "short"):
        for max_range in (0.75, 1.0, 1.25, 1.5):
            for target_r in (0.35, 0.5, 0.65, 0.8, 1.0):
                for fraction in (0.5, 0.75, 1.0):
                    candidates.append(
                        replace(
                            base,
                            direction=direction,
                            max_range_atr=max_range,
                            first_target_r=target_r,
                            first_target_fraction=fraction,
                        )
                    )
    return candidates


def _frequency_candidates() -> list[TamukaiConfig]:
    """Relax entry filters while preserving the strict 1R full exit."""
    candidates: list[TamukaiConfig] = []
    base = TamukaiConfig(
        direction="long",
        first_target_r=1.0,
        first_target_fraction=1.0,
    )
    for min_slope in (0.0, 0.03):
        for min_pullback in (0.0, 0.25, 0.5):
            for max_range in (1.0, 1.25, 1.5, 2.0):
                for min_room in (0.5, 1.0, 1.5, 2.0):
                    candidates.append(
                        replace(
                            base,
                            min_slope_atr=min_slope,
                            min_pullback_atr=min_pullback,
                            max_range_atr=max_range,
                            min_room_r=min_room,
                        )
                    )
    return candidates


def _evaluation_dict(evaluation: Evaluation) -> dict[str, object]:
    return {
        "robust": evaluation.robust,
        "config": asdict(evaluation.config),
        "train": asdict(evaluation.train),
        "validation": asdict(evaluation.validation),
        "holdout": asdict(evaluation.holdout),
        "full": asdict(evaluation.full),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", nargs="?", default="USDJPY")
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--stage",
        choices=(
            "exit",
            "filter",
            "robust",
            "pair",
            "frequency",
        ),
        default="exit",
    )
    parser.add_argument("--seed-json", type=Path)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    symbol = args.symbol.upper()
    metadata = repository.metadata(symbol)
    print(f"Loading {symbol} 1H bars...", file=sys.stderr, flush=True)
    bars = list(
        repository.bars(
            symbol,
            None,
            datetime(2024, 8, 30, 23, 59, 59),
            "1h",
        )
    )
    print(f"Loaded {len(bars)} bars", file=sys.stderr, flush=True)

    if args.stage == "exit":
        candidates = _exit_candidates()
    elif args.stage == "filter":
        if args.seed_json is None:
            parser.error("--stage filter requires --seed-json")
        seed_values = json.loads(args.seed_json.read_text(encoding="utf-8"))
        if seed_values.get("entry_hours") is not None:
            seed_values["entry_hours"] = tuple(seed_values["entry_hours"])
        candidates = _filter_candidates(TamukaiConfig(**seed_values))
    elif args.stage == "robust":
        candidates = _robust_candidates()
    elif args.stage == "pair":
        candidates = _pair_candidates()
    else:
        candidates = _frequency_candidates()

    evaluations: list[Evaluation] = []
    for index, config in enumerate(candidates, 1):
        result = TamukaiBacktester(metadata, config, lots=0.1).run(
            bars,
            start=datetime(2004, 1, 1),
            end=datetime(2024, 8, 30, 23, 59, 59),
        )
        trades = result.trades
        evaluation = Evaluation(
            config=config,
            train=_period(trades, 2004, 2018),
            validation=_period(trades, 2019, 2022),
            holdout=_period(trades, 2023, 2024),
            full=_stats(trades),
        )
        evaluations.append(evaluation)
        if index % 10 == 0 or index == len(candidates):
            best = max(evaluations, key=lambda item: item.selection_key)
            print(
                f"{index}/{len(candidates)} best train={best.train.win_rate:.1f}%/"
                f"{best.train.trades} val={best.validation.win_rate:.1f}%/"
                f"{best.validation.trades}",
                file=sys.stderr,
                flush=True,
            )

    evaluations.sort(key=lambda item: item.selection_key, reverse=True)
    payload = json.dumps(
        [_evaluation_dict(item) for item in evaluations[: args.top]],
        ensure_ascii=False,
        indent=2,
    )
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
