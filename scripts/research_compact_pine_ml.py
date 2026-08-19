"""Search compact shared tree models that can be emitted as Pine if/else logic."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from forextester_backtest import HistoryRepository
from research_ml_strict_rr import (
    _opportunities,
    _signal_map,
    _training_rows,
)
from research_strict_rr_portfolio import (
    PERIODS,
    SYMBOLS,
    Candidate,
    _passes,
    _prepare,
    _simulate,
    _stats,
)


@dataclass(frozen=True, slots=True)
class CompactModelConfig:
    trees: int
    leaves: int
    learning_rate: float
    min_samples_leaf: int
    l2: float = 2.0


MODEL_CONFIGS = (
    CompactModelConfig(10, 7, 0.10, 300),
    CompactModelConfig(20, 7, 0.10, 300),
    CompactModelConfig(30, 7, 0.10, 300),
    CompactModelConfig(20, 15, 0.10, 300),
    CompactModelConfig(40, 7, 0.05, 300),
    CompactModelConfig(40, 15, 0.05, 300),
)


def _model(config: CompactModelConfig) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=config.learning_rate,
        max_iter=config.trees,
        max_leaf_nodes=config.leaves,
        min_samples_leaf=config.min_samples_leaf,
        l2_regularization=config.l2,
        early_stopping=False,
        random_state=20260803,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument(
        "--output", type=Path, default=Path("scripts/compact_pine_ml_results.json")
    )
    parser.add_argument("--fine", action="store_true")
    parser.add_argument("--require-htf-alignment", action="store_true")
    args = parser.parse_args()
    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 17, 23, 59, 59)
    prepared = {}
    opportunities = {}
    for symbol in SYMBOLS:
        print(f"Loading and labeling {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        opportunities[symbol] = _opportunities(prepared[symbol], 4, 2.0)

    model_configs = (
        (CompactModelConfig(20, 15, 0.10, 300),) if args.fine else MODEL_CONFIGS
    )
    probability_sets = []
    for _ in model_configs:
        probability_sets.append(
            {
                symbol: (
                    np.full(rows.indices.size, np.nan),
                    np.full(rows.indices.size, np.nan),
                )
                for symbol, rows in opportunities.items()
            }
        )

    for prediction_year in range(2019, 2027):
        x_train, y_train = _training_rows(prepared, opportunities, prediction_year)
        print(
            f"Training before {prediction_year}: rows={y_train.size}",
            file=sys.stderr,
            flush=True,
        )
        for model_index, config in enumerate(model_configs):
            model = _model(config)
            model.fit(x_train, y_train)
            probability_map = probability_sets[model_index]
            for symbol, rows in opportunities.items():
                years = prepared[symbol].years[rows.indices]
                if prediction_year == 2019:
                    in_sample = years <= 2018
                    probability_map[symbol][0][in_sample] = model.predict_proba(
                        rows.x_long[in_sample]
                    )[:, 1]
                    probability_map[symbol][1][in_sample] = model.predict_proba(
                        rows.x_short[in_sample]
                    )[:, 1]
                predict = years == prediction_year
                probability_map[symbol][0][predict] = model.predict_proba(
                    rows.x_long[predict]
                )[:, 1]
                probability_map[symbol][1][predict] = model.predict_proba(
                    rows.x_short[predict]
                )[:, 1]

    simulation_candidate = Candidate(
        "compact_shared_ml", timeframe="15m", stop_atr=2.0
    )
    results = []
    if args.require_htf_alignment:
        thresholds = tuple(round(0.46 + index * 0.005, 3) for index in range(21))
    elif args.fine:
        thresholds = (0.485, 0.486, 0.487, 0.488, 0.489, 0.490)
    else:
        thresholds = (0.44, 0.45, 0.46, 0.47, 0.48, 0.49, 0.50)
    for model_index, config in enumerate(model_configs):
        for threshold in thresholds:
            signals = _signal_map(
                prepared,
                opportunities,
                probability_sets[model_index],
                threshold,
                0.0,
                0,
                24,
                args.require_htf_alignment,
            )
            trades = [
                trade
                for symbol in SYMBOLS
                for trade in _simulate(
                    symbol, prepared[symbol], simulation_candidate, signals[symbol]
                )
            ]
            periods = {
                name: _stats(trades, start, finish, months)
                for name, (start, finish, months) in PERIODS.items()
            }
            annual_periods = {
                str(year): _stats(trades, year, year, 12)
                for year in range(2010, 2027)
            }
            prequalified = _passes(periods["train_2010_2018"]) and _passes(
                periods["validation_2019_2022"]
            )
            passes_all = prequalified and all(
                _passes(stats) for stats in periods.values()
            )
            results.append(
                {
                    "model": asdict(config),
                    "threshold": threshold,
                    "require_htf_alignment": args.require_htf_alignment,
                    "prequalified": prequalified,
                    "passes_all": passes_all,
                    "periods": periods,
                    "annual_periods": annual_periods,
                }
            )
    selectable = [row for row in results if row["prequalified"]]
    if selectable:
        selected = max(
            selectable,
            key=lambda row: float(
                row["periods"]["validation_2019_2022"]["profit_factor"] or 0.0
            ),
        )
        selected["selected_by_validation_only"] = True
    results.sort(
        key=lambda row: (
            row["prequalified"],
            min(
                float(row["periods"][period]["profit_factor"] or 0.0)
                for period in ("train_2010_2018", "validation_2019_2022")
            ),
            min(
                float(row["periods"][period]["trades_per_month"])
                for period in ("train_2010_2018", "validation_2019_2022")
            ),
        ),
        reverse=True,
    )
    args.output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"RESULTS={len(results)} PRE={sum(row['prequalified'] for row in results)} "
        f"PASS={sum(row['passes_all'] for row in results)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
