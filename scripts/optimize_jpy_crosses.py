"""Shared strict-RR1 parameter search across liquid JPY crosses."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Iterable

from forextester_backtest import HistoryRepository, TamukaiBacktester, TamukaiConfig
from forextester_backtest.models import Trade

PRIMARY_SYMBOLS = ("USDJPY", "GBPJPY", "AUDJPY", "CHFJPY")


@dataclass(frozen=True, slots=True)
class PeriodStats:
    trades: int
    wins: int
    win_rate: float
    net_profit: float
    profit_factor: float | None
    expectancy: float
    expectancy_r: float


@dataclass(frozen=True, slots=True)
class PairEvaluation:
    train: PeriodStats
    validation: PeriodStats
    holdout: PeriodStats
    true_oos: PeriodStats


@dataclass(frozen=True, slots=True)
class Evaluation:
    config: TamukaiConfig
    pairs: dict[str, PairEvaluation]
    train: PeriodStats
    validation: PeriodStats
    holdout: PeriodStats
    true_oos: PeriodStats

    def _positive_pairs(self, period: str) -> int:
        return sum(
            getattr(pair, period).net_profit > 0
            and (getattr(pair, period).profit_factor or 0.0) > 1.0
            for pair in self.pairs.values()
        )

    @property
    def eligible(self) -> bool:
        return (
            self.train.trades >= 150
            and self.validation.trades >= 30
            and self.train.expectancy_r > 0
            and self.validation.expectancy_r > 0
            and self.train.net_profit > 0
            and self.validation.net_profit > 0
            and (self.train.profit_factor or 0.0) > 1.0
            and (self.validation.profit_factor or 0.0) > 1.0
            and self._positive_pairs("train") >= 3
            and self._positive_pairs("validation") >= 2
        )

    @property
    def selection_key(self) -> tuple[float, ...]:
        """Never use the 2023-2026 holdout periods for candidate ranking."""
        return (
            float(self.eligible),
            float(
                self._positive_pairs("train")
                + self._positive_pairs("validation")
            ),
            min(self.train.expectancy_r, self.validation.expectancy_r),
            min(
                self.train.profit_factor or 0.0,
                self.validation.profit_factor or 0.0,
            ),
            float(self.validation.trades),
        )


def _stats(trades: Iterable[Trade]) -> PeriodStats:
    rows = list(trades)
    gains = sum(trade.net_pnl for trade in rows if trade.net_pnl > 0)
    losses = sum(trade.net_pnl for trade in rows if trade.net_pnl < 0)
    net = gains + losses
    r_values: list[float] = []
    for trade in rows:
        if trade.initial_stop is None:
            continue
        risk = abs(trade.entry_price - trade.initial_stop) * trade.units
        if risk > 0:
            r_values.append(trade.net_pnl / risk)
    wins = sum(trade.net_pnl > 0 for trade in rows)
    return PeriodStats(
        trades=len(rows),
        wins=wins,
        win_rate=wins / len(rows) * 100 if rows else 0.0,
        net_profit=net,
        profit_factor=gains / abs(losses) if losses else None,
        expectancy=net / len(rows) if rows else 0.0,
        expectancy_r=sum(r_values) / len(r_values) if r_values else 0.0,
    )


def _period(trades: Iterable[Trade], start_year: int, end_year: int) -> PeriodStats:
    return _stats(
        trade for trade in trades if start_year <= trade.entry_time.year <= end_year
    )


def _periods(trades: Iterable[Trade]) -> PairEvaluation:
    rows = list(trades)
    return PairEvaluation(
        train=_period(rows, 2004, 2018),
        validation=_period(rows, 2019, 2022),
        holdout=_period(rows, 2023, 2024),
        true_oos=_period(rows, 2025, 2026),
    )


def _base() -> TamukaiConfig:
    return TamukaiConfig(
        first_target_r=1.0,
        first_target_fraction=1.0,
        move_stop_to_break_even=False,
    )


def _signal_candidates() -> list[TamukaiConfig]:
    base = _base()
    return [
        replace(
            base,
            direction=direction,
            max_range_atr=max_range,
            min_slope_atr=min_slope,
            range_bars=range_bars,
        )
        for direction, max_range, min_slope, range_bars in product(
            ("both", "long", "short"),
            (0.75, 1.0, 1.25, 1.5),
            (0.0, 0.03, 0.06, 0.10),
            (3, 4),
        )
    ]


def _risk_candidates(seed: TamukaiConfig) -> list[TamukaiConfig]:
    return [
        replace(
            seed,
            min_pullback_atr=min_pullback,
            zone_tolerance_atr=zone_tolerance,
            min_room_r=min_room,
            max_risk_atr=max_risk,
            first_target_r=1.0,
            first_target_fraction=1.0,
            move_stop_to_break_even=False,
        )
        for min_pullback, zone_tolerance, min_room, max_risk in product(
            (0.25, 0.50, 0.75),
            (0.15, 0.25, 0.40),
            (1.0, 1.5, 2.0),
            (1.5, 2.0, 2.5),
        )
    ]


def _load_seed(path: Path, index: int) -> TamukaiConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload = payload[index]
    if "config" in payload:
        payload = payload["config"]
    if payload.get("entry_hours") is not None:
        payload["entry_hours"] = tuple(payload["entry_hours"])
    return TamukaiConfig(**payload)


def _evaluation_dict(item: Evaluation) -> dict[str, object]:
    return {
        "eligible": item.eligible,
        "positive_pairs": {
            period: item._positive_pairs(period)
            for period in ("train", "validation", "holdout", "true_oos")
        },
        "config": asdict(item.config),
        "group": {
            "train_2004_2018": asdict(item.train),
            "validation_2019_2022": asdict(item.validation),
            "holdout_2023_2024": asdict(item.holdout),
            "true_oos_2025_2026": asdict(item.true_oos),
        },
        "pairs": {
            symbol: {
                "train_2004_2018": asdict(pair.train),
                "validation_2019_2022": asdict(pair.validation),
                "holdout_2023_2024": asdict(pair.holdout),
                "true_oos_2025_2026": asdict(pair.true_oos),
            }
            for symbol, pair in item.pairs.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--stage", choices=("signal", "risk"), default="signal")
    parser.add_argument("--seed-json", type=Path)
    parser.add_argument("--seed-index", type=int, default=0)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    bars_by_symbol = {}
    metadata_by_symbol = {}
    for symbol in PRIMARY_SYMBOLS:
        print(f"Loading {symbol} 1H bars...", file=sys.stderr, flush=True)
        metadata_by_symbol[symbol] = repository.metadata(symbol)
        bars_by_symbol[symbol] = list(repository.bars(symbol, None, end, "1h"))
        print(
            f"Loaded {len(bars_by_symbol[symbol])} bars",
            file=sys.stderr,
            flush=True,
        )

    if args.stage == "signal":
        candidates = _signal_candidates()
    else:
        if args.seed_json is None:
            parser.error("--stage risk requires --seed-json")
        candidates = _risk_candidates(_load_seed(args.seed_json, args.seed_index))

    evaluations: list[Evaluation] = []
    for index, config in enumerate(candidates, 1):
        pair_rows: dict[str, list[Trade]] = {}
        pair_evaluations: dict[str, PairEvaluation] = {}
        for symbol in PRIMARY_SYMBOLS:
            result = TamukaiBacktester(
                metadata_by_symbol[symbol], config, lots=0.1
            ).run(
                bars_by_symbol[symbol],
                start=datetime(2004, 1, 1),
                end=end,
            )
            pair_rows[symbol] = list(result.trades)
            pair_evaluations[symbol] = _periods(result.trades)

        all_rows = [trade for rows in pair_rows.values() for trade in rows]
        item = Evaluation(
            config=config,
            pairs=pair_evaluations,
            train=_period(all_rows, 2004, 2018),
            validation=_period(all_rows, 2019, 2022),
            holdout=_period(all_rows, 2023, 2024),
            true_oos=_period(all_rows, 2025, 2026),
        )
        evaluations.append(item)
        if index % 6 == 0 or index == len(candidates):
            best = max(evaluations, key=lambda value: value.selection_key)
            print(
                f"{index}/{len(candidates)} best "
                f"train={best.train.expectancy_r:.3f}R/"
                f"PF{(best.train.profit_factor or 0.0):.2f} "
                f"validation={best.validation.expectancy_r:.3f}R/"
                f"PF{(best.validation.profit_factor or 0.0):.2f}",
                file=sys.stderr,
                flush=True,
            )

    evaluations.sort(key=lambda value: value.selection_key, reverse=True)
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
