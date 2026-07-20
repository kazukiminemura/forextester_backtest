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
            and self.train.expectancy > 0
            and self.validation.expectancy > 0
            and (self.train.profit_factor or 0.0) > 1.0
            and (self.validation.profit_factor or 0.0) > 1.0
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


def _base_config() -> TamukaiConfig:
    # Forex defaults cap risk at 80 pips (= $0.80 for 3-decimal XAUUSD), which
    # suppresses every historical trade. Zero intentionally disables that
    # absolute cap; the existing 2.5 ATR cap remains active.
    return TamukaiConfig(
        entry_buffer_pips=20.0,
        stop_buffer_pips=20.0,
        max_risk_pips=0.0,
    )


def _candidates() -> list[TamukaiConfig]:
    base = _base_config()
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


def _rr1_signal_candidates() -> list[TamukaiConfig]:
    """Search signal filters while enforcing a true full-position 1R exit."""
    base = replace(
        _base_config(),
        first_target_r=1.0,
        first_target_fraction=1.0,
        move_stop_to_break_even=False,
    )
    return [
        replace(
            base,
            direction=direction,
            max_range_atr=max_range,
            min_slope_atr=min_slope,
            min_pullback_atr=min_pullback,
        )
        for direction, max_range, min_slope, min_pullback in product(
            ("both", "long", "short"),
            (0.75, 1.0, 1.25, 1.5),
            (0.0, 0.03, 0.06, 0.10),
            (0.25, 0.50, 0.75, 1.0),
        )
    ]


def _rr1_risk_candidates(seed: TamukaiConfig) -> list[TamukaiConfig]:
    """Tune execution/risk filters without relaxing the strict 1R exit."""
    candidates: list[TamukaiConfig] = []
    for buffer_pips, min_room, max_risk_atr, expiry in product(
        (10.0, 20.0, 40.0),
        (1.0, 1.5, 2.0),
        (1.5, 2.0, 2.5),
        (4, 8, 12),
    ):
        candidates.append(
            replace(
                seed,
                entry_buffer_pips=buffer_pips,
                stop_buffer_pips=buffer_pips,
                min_room_r=min_room,
                max_risk_atr=max_risk_atr,
                order_expiry_bars=expiry,
                first_target_r=1.0,
                first_target_fraction=1.0,
                move_stop_to_break_even=False,
            )
        )
    return candidates


def _rr1_context_candidates(seed: TamukaiConfig) -> list[TamukaiConfig]:
    """Tune range construction and broad time windows at a strict 1R exit."""
    hour_sets = (
        None,
        tuple(range(0, 10)),
        tuple(range(7, 16)),
        tuple(range(13, 24)),
        (3, 5, 8, 13, 14),
        (5, 7, 8, 9, 13, 14),
    )
    return [
        replace(
            seed,
            entry_hours=hours,
            range_bars=range_bars,
            zone_tolerance_atr=zone_tolerance,
            first_target_r=1.0,
            first_target_fraction=1.0,
            move_stop_to_break_even=False,
        )
        for hours, range_bars, zone_tolerance in product(
            hour_sets,
            (2, 3, 4),
            (0.15, 0.25, 0.40),
        )
    ]


def _load_seed(path: Path, index: int = 0) -> TamukaiConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        if not payload:
            raise ValueError(f"seed結果が空です: {path}")
        try:
            payload = payload[index]
        except IndexError as exc:
            raise ValueError(
                f"seed-indexが結果件数を超えています: {index} / {len(payload)}"
            ) from exc
    if "config" in payload:
        payload = payload["config"]
    if payload.get("entry_hours") is not None:
        payload["entry_hours"] = tuple(payload["entry_hours"])
    return TamukaiConfig(**payload)


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
    parser.add_argument(
        "--stage",
        choices=("legacy", "rr1-signal", "rr1-risk", "rr1-context"),
        default="legacy",
    )
    parser.add_argument("--seed-json", type=Path)
    parser.add_argument(
        "--seed-index",
        type=int,
        action="append",
        help="rr1-riskで使う結果配列の添字（複数指定可）",
    )
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
    if args.stage == "legacy":
        candidates = _candidates()
    elif args.stage == "rr1-signal":
        candidates = _rr1_signal_candidates()
    elif args.stage == "rr1-risk":
        if args.seed_json is None:
            parser.error("--stage rr1-risk requires --seed-json")
        seed_indices = args.seed_index or [0]
        candidates = [
            candidate
            for seed_index in seed_indices
            for candidate in _rr1_risk_candidates(
                _load_seed(args.seed_json, seed_index)
            )
        ]
    else:
        if args.seed_json is None:
            parser.error("--stage rr1-context requires --seed-json")
        seed_indices = args.seed_index or [0]
        candidates = [
            candidate
            for seed_index in seed_indices
            for candidate in _rr1_context_candidates(
                _load_seed(args.seed_json, seed_index)
            )
        ]
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
