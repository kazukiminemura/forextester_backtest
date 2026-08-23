"""Compare non-Tamukai entry logics on a fixed one-hour timeframe."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Iterable

from forextester_backtest import (
    AlternativeBacktester,
    AlternativeConfig,
    HistoryRepository,
)
from forextester_backtest.models import Trade

ENTRY_TIMEFRAME = "1h"
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
    config: AlternativeConfig
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
            self.train.trades >= 200
            and self.validation.trades >= 40
            and self.train.expectancy_r > 0
            and self.validation.expectancy_r > 0
            and (self.train.profit_factor or 0.0) > 1.0
            and (self.validation.profit_factor or 0.0) > 1.0
            and self._positive_pairs("train") >= 3
            and self._positive_pairs("validation") >= 2
        )

    @property
    def passes_holdouts(self) -> bool:
        """Audit only; never use this property for candidate ranking."""
        return (
            self.holdout.trades >= 40
            and self.true_oos.trades >= 20
            and self.holdout.expectancy_r > 0
            and self.true_oos.expectancy_r > 0
            and (self.holdout.profit_factor or 0.0) > 1.0
            and (self.true_oos.profit_factor or 0.0) > 1.0
            and self._positive_pairs("holdout") >= 2
            and self._positive_pairs("true_oos") >= 2
        )

    @property
    def selection_key(self) -> tuple[float, ...]:
        """Rank on 2004-2022 only; holdout data must not affect selection."""
        return (
            float(self.eligible),
            float(self._positive_pairs("train") + self._positive_pairs("validation")),
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
    r_values = []
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


def _periods(trades: Iterable[Trade], train_start_year: int) -> PairEvaluation:
    rows = list(trades)
    return PairEvaluation(
        train=_period(rows, train_start_year, 2018),
        validation=_period(rows, 2019, 2022),
        holdout=_period(rows, 2023, 2024),
        true_oos=_period(rows, 2025, 2026),
    )


def _candidates() -> list[AlternativeConfig]:
    candidates = [
        AlternativeConfig(
            logic="donchian",
            direction=direction,
            channel_length=channel,
            slow_ema=trend,
            stop_atr=stop,
        )
        for direction, channel, trend, stop in product(
            ("both", "long"), (12, 24, 48), (100, 200), (1.0, 1.5)
        )
    ]
    candidates.extend(
        AlternativeConfig(
            logic="ema-pullback",
            direction=direction,
            fast_ema=fast,
            slow_ema=slow,
            stop_atr=stop,
        )
        for direction, fast, slow, stop in product(
            ("both", "long"), (10, 20), (50, 100), (1.0, 1.5)
        )
    )
    candidates.extend(
        AlternativeConfig(
            logic="bollinger-reversion",
            direction=direction,
            band_length=length,
            band_deviation=deviation,
            stop_atr=stop,
        )
        for direction, length, deviation, stop in product(
            ("both", "long"), (20, 40), (1.5, 2.0), (1.0, 1.5)
        )
    )
    return candidates


def _evaluation_dict(
    item: Evaluation, train_start_year: int
) -> dict[str, object]:
    return {
        "entry_timeframe": ENTRY_TIMEFRAME,
        "exit_rule": "strict 1R full exit",
        "eligible_train_validation": item.eligible,
        "passes_holdouts": item.passes_holdouts,
        "positive_pairs": {
            period: item._positive_pairs(period)
            for period in ("train", "validation", "holdout", "true_oos")
        },
        "config": asdict(item.config),
        "group": {
            f"train_{train_start_year}_2018": asdict(item.train),
            "validation_2019_2022": asdict(item.validation),
            "holdout_2023_2024": asdict(item.holdout),
            "true_oos_2025_2026": asdict(item.true_oos),
        },
        "pairs": {
            symbol: {
                f"train_{train_start_year}_2018": asdict(pair.train),
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
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=list(PRIMARY_SYMBOLS),
        help="検証する通貨ペア。既定はJPYクロス4通貨",
    )
    parser.add_argument("--train-start-year", type=int, default=2004)
    parser.add_argument(
        "--logic",
        choices=("donchian", "ema-pullback", "bollinger-reversion"),
    )
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    symbols = tuple(symbol.upper() for symbol in args.symbols)
    if len(symbols) != len(set(symbols)):
        parser.error("--symbols に重複した通貨ペアがあります")
    if args.train_start_year > 2018:
        parser.error("--train-start-year は2018以下にしてください")

    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    bars_by_symbol = {}
    metadata_by_symbol = {}
    for symbol in symbols:
        print(f"Loading {symbol} {ENTRY_TIMEFRAME} bars...", file=sys.stderr)
        metadata_by_symbol[symbol] = repository.metadata(symbol)
        bars_by_symbol[symbol] = list(
            repository.bars(symbol, None, end, ENTRY_TIMEFRAME)
        )

    evaluations: list[Evaluation] = []
    candidates = [
        config
        for config in _candidates()
        if args.logic is None or config.logic == args.logic
    ]
    for index, config in enumerate(candidates, 1):
        pair_rows: dict[str, list[Trade]] = {}
        pair_evaluations: dict[str, PairEvaluation] = {}
        for symbol in symbols:
            result = AlternativeBacktester(
                metadata_by_symbol[symbol], config, lots=0.1
            ).run(
                bars_by_symbol[symbol],
                start=datetime(2004, 1, 1),
                end=end,
            )
            pair_rows[symbol] = list(result.trades)
            pair_evaluations[symbol] = _periods(
                result.trades, args.train_start_year
            )
        all_rows = [trade for rows in pair_rows.values() for trade in rows]
        evaluations.append(
            Evaluation(
                config=config,
                pairs=pair_evaluations,
                train=_period(all_rows, args.train_start_year, 2018),
                validation=_period(all_rows, 2019, 2022),
                holdout=_period(all_rows, 2023, 2024),
                true_oos=_period(all_rows, 2025, 2026),
            )
        )
        if index % 4 == 0 or index == len(candidates):
            best = max(evaluations, key=lambda item: item.selection_key)
            print(
                f"{index}/{len(candidates)} {config.logic} | best "
                f"train={best.train.expectancy_r:.3f}R "
                f"validation={best.validation.expectancy_r:.3f}R",
                file=sys.stderr,
                flush=True,
            )

    evaluations.sort(key=lambda item: item.selection_key, reverse=True)
    payload = json.dumps(
        [
            _evaluation_dict(item, args.train_start_year)
            for item in evaluations[: args.top]
        ],
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
