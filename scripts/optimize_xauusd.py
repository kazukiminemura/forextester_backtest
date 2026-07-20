"""Out-of-sample-aware parameter search for the XAUUSD Tamukai strategy."""

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
class Evaluation:
    config: TamukaiConfig
    train: PeriodStats
    validation: PeriodStats
    holdout: PeriodStats

    @property
    def eligible(self) -> bool:
        return (
            self.train.trades >= 60
            and self.validation.trades >= 15
            and self.train.expectancy_r > 0
            and self.validation.expectancy_r > 0
        )

    @property
    def selection_key(self) -> tuple[float, ...]:
        """Rank without looking at the 2025-2026 holdout result."""
        return (
            float(self.eligible),
            min(self.train.expectancy_r, self.validation.expectancy_r),
            min(self.train.profit_factor or 0.0, self.validation.profit_factor or 0.0),
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


def _candidates() -> list[TamukaiConfig]:
    # Forex defaults cap risk at 80 pips (= $0.80 for 3-decimal XAUUSD), which
    # suppresses every historical trade. Zero intentionally disables that
    # absolute cap; the existing 2.5 ATR cap remains active.
    base = TamukaiConfig(
        entry_buffer_pips=20.0,
        stop_buffer_pips=20.0,
        max_risk_pips=0.0,
    )
    candidates: list[TamukaiConfig] = []
    exit_profiles = ((1.0, False), (0.5, False), (0.5, True))
    for direction, max_range, target_r, exit_profile in product(
        ("both", "long", "short"),
        (0.75, 1.0, 1.25, 1.5),
        (0.5, 0.75, 1.0),
        exit_profiles,
    ):
        fraction, break_even = exit_profile
        candidates.append(
            replace(
                base,
                direction=direction,
                max_range_atr=max_range,
                first_target_r=target_r,
                first_target_fraction=fraction,
                move_stop_to_break_even=break_even,
            )
        )
    return candidates


def _evaluation_dict(item: Evaluation) -> dict[str, object]:
    return {
        "eligible": item.eligible,
        "config": asdict(item.config),
        "train_2013_2021": asdict(item.train),
        "validation_2022_2024": asdict(item.validation),
        "holdout_2025_2026": asdict(item.holdout),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    repository = HistoryRepository(args.history_dir)
    metadata = repository.metadata("XAUUSD")
    end = datetime(2026, 7, 17, 23, 59, 59)
    print("Loading XAUUSD 1H bars...", file=sys.stderr, flush=True)
    bars = list(repository.bars("XAUUSD", None, end, "1h"))
    print(f"Loaded {len(bars)} bars", file=sys.stderr, flush=True)

    evaluations: list[Evaluation] = []
    candidates = _candidates()
    for index, config in enumerate(candidates, 1):
        result = TamukaiBacktester(metadata, config, lots=0.1).run(
            bars,
            start=datetime(2013, 5, 1),
            end=end,
        )
        item = Evaluation(
            config=config,
            train=_period(result.trades, 2013, 2021),
            validation=_period(result.trades, 2022, 2024),
            holdout=_period(result.trades, 2025, 2026),
        )
        evaluations.append(item)
        if index % 12 == 0 or index == len(candidates):
            best = max(evaluations, key=lambda value: value.selection_key)
            print(
                f"{index}/{len(candidates)} best "
                f"train={best.train.expectancy_r:.3f}R/{best.train.trades} "
                f"validation={best.validation.expectancy_r:.3f}R/"
                f"{best.validation.trades}",
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
