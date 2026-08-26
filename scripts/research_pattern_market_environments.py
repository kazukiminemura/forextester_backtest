"""Find pre-defined market environments where classical patterns may work."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import PERIODS, SYMBOLS, Trade, _period_rows, _stats
from research_classic_chart_patterns import PatternSignal, _simulate
from research_intermarket_trend_filters import (
    _all_signals,
    _selected,
    _snapshot,
)
from research_classic_chart_patterns import Candidate as ClassicCandidate
from research_flag_patterns import Candidate as FlagCandidate
from research_geometric_chart_patterns import Candidate as GeometricCandidate
from research_strict_rr_portfolio import Prepared, _prepare
from research_yosuga_5m_market_sessions import _exclusive_market


REVERSAL_PATTERNS = {
    "double_top", "double_bottom", "head_shoulders", "inverse_head_shoulders",
    "rising_wedge", "falling_wedge", "triple_top", "triple_bottom",
}
CONTINUATION_PATTERNS = {
    "ascending_triangle", "descending_triangle", "symmetrical_triangle",
    "rectangle", "bull_flag", "bear_flag",
}
ENVIRONMENTS = (
    "baseline",
    "tokyo", "london", "new_york",
    "htf_align", "htf_counter",
    "own_trend_align", "own_trend_counter",
    "vol_high", "vol_low", "vol_expanding",
    "currency_strength_expanding", "gold_usd_inverse_regime",
    "continuation_theory", "reversal_theory",
)
MIN_TRAIN_TRADES = 500
MIN_VALIDATION_TRADES = 200


@dataclass(slots=True)
class EnvironmentArrays:
    own_move: np.ndarray
    atr_average: np.ndarray


def _environment_arrays(data: Prepared, scale: int) -> EnvironmentArrays:
    horizon = 320 * scale
    own_move = np.full(data.close.size, np.nan)
    own_move[horizon:] = np.log(data.close[horizon:] / data.close[:-horizon])
    return EnvironmentArrays(own_move, _causal_ema(data.atr, horizon))


def _causal_ema(values: np.ndarray, length: int) -> np.ndarray:
    """EMA starting at the first finite value without backfilling warm-up bars."""
    result = np.full(values.size, np.nan)
    finite = np.flatnonzero(np.isfinite(values))
    if not finite.size:
        return result
    first = int(finite[0])
    result[first] = values[first]
    alpha = 2.0 / (length + 1.0)
    for index in range(first + 1, values.size):
        value = values[index]
        result[index] = (
            alpha * value + (1.0 - alpha) * result[index - 1]
            if np.isfinite(value)
            else result[index - 1]
        )
    return result


def _currency_expanding(
    symbol: str,
    direction: int,
    timestamp: datetime,
    previous_timestamp: datetime,
    prepared: dict[str, Prepared],
    cache: dict[tuple[datetime, int], object],
    horizon: int,
) -> bool:
    if symbol == "XAUUSD":
        return False
    current = cache.setdefault((timestamp, horizon), _snapshot(prepared, timestamp, horizon))
    previous = cache.setdefault((previous_timestamp, horizon), _snapshot(prepared, previous_timestamp, horizon))
    base, quote = symbol[:3], symbol[3:]
    needed = (base, quote)
    if any(currency not in current.currency or currency not in previous.currency for currency in needed):
        return False
    now_gap = direction * (current.currency[base] - current.currency[quote])
    previous_gap = direction * (previous.currency[base] - previous.currency[quote])
    return now_gap > 0 and now_gap > previous_gap


def _gold_inverse_regime(
    symbol: str,
    direction: int,
    timestamp: datetime,
    prepared: dict[str, Prepared],
    cache: dict[tuple[datetime, int], object],
    horizon: int,
) -> bool:
    if symbol != "XAUUSD" and "USD" not in (symbol[:3], symbol[3:]):
        return False
    snapshot = cache.setdefault((timestamp, horizon), _snapshot(prepared, timestamp, horizon))
    usd = snapshot.currency.get("USD")
    gold = snapshot.gold
    if usd is None or gold is None or usd * gold >= 0:
        return False
    if symbol == "XAUUSD" or symbol.endswith("USD"):
        expected = gold
    else:
        expected = -gold
    return direction * expected > 0


def _keep(
    environment: str,
    symbol: str,
    signal: PatternSignal,
    data: Prepared,
    arrays: EnvironmentArrays,
    prepared: dict[str, Prepared],
    snapshot_cache: dict[tuple[datetime, int], object],
    scale: int,
) -> bool:
    if environment == "baseline":
        return True
    index = signal.index
    timestamp = data.times[index]
    session = _exclusive_market(timestamp)
    htf = int(data.htf_trend[index])
    own = float(arrays.own_move[index])
    atr_average = float(arrays.atr_average[index])
    vol_high = np.isfinite(atr_average) and data.atr[index] >= 1.20 * atr_average
    vol_low = np.isfinite(atr_average) and data.atr[index] <= 0.80 * atr_average
    vol_expanding = (
        index >= 16 * scale
        and np.isfinite(atr_average)
        and data.atr[index] > atr_average
        and data.atr[index] > data.atr[index - 16 * scale]
    )
    htf_align = htf == signal.direction
    htf_counter = htf == -signal.direction
    own_align = np.isfinite(own) and signal.direction * own > 0
    if environment in ("tokyo", "london", "new_york"):
        return session == environment
    if environment == "htf_align":
        return htf_align
    if environment == "htf_counter":
        return htf_counter
    if environment == "own_trend_align":
        return own_align
    if environment == "own_trend_counter":
        return np.isfinite(own) and signal.direction * own < 0
    if environment == "vol_high":
        return vol_high
    if environment == "vol_low":
        return vol_low
    if environment == "vol_expanding":
        return vol_expanding
    if environment == "currency_strength_expanding":
        horizon = 80 * scale
        if index < horizon:
            return False
        return _currency_expanding(
            symbol, signal.direction, timestamp, data.times[index - horizon],
            prepared, snapshot_cache, horizon,
        )
    if environment == "gold_usd_inverse_regime":
        return _gold_inverse_regime(
            symbol, signal.direction, timestamp, prepared, snapshot_cache, 320 * scale
        )
    liquid_session = session in ("london", "new_york")
    if environment == "continuation_theory":
        return signal.pattern in CONTINUATION_PATTERNS and htf_align and vol_expanding and liquid_session
    if environment == "reversal_theory":
        return signal.pattern in REVERSAL_PATTERNS and htf_counter and vol_expanding and liquid_session
    raise ValueError(f"unknown environment: {environment}")


def _periods(rows: list[Trade]) -> dict:
    return {
        name: _stats(_period_rows(rows, start, end), months)
        for name, (start, end, months) in PERIODS.items()
    }


def _eligible(periods: dict, include_oos: bool) -> bool:
    train = periods["train_2010_2018"]
    validation = periods["validation_2019_2022"]
    development_pass = (
        train["trades"] >= MIN_TRAIN_TRADES
        and validation["trades"] >= MIN_VALIDATION_TRADES
        and train["expectancy_r"] > 0
        and validation["expectancy_r"] > 0
    )
    if not include_oos:
        return development_pass
    return development_pass and all(
        periods[name]["expectancy_r"] > 0
        for name in ("holdout_2023_2024", "true_oos_2025_2026")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--timeframe", choices=("5m", "15m"), default="5m")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        args.output = Path(f"scripts/pattern_market_environment_{args.timeframe}_results.json")
    scale = 3 if args.timeframe == "5m" else 1
    base = Path(__file__).resolve().parent
    raw = {
        "classic": _selected(base / "classic_chart_pattern_results.json"),
        "geometric": _selected(base / "geometric_chart_pattern_results.json"),
        "flag": _selected(base / "flag_pattern_results.json"),
        "triple": _selected(base / "triple_chart_pattern_results.json"),
    }
    candidates: dict[str, object] = {
        "classic": ClassicCandidate(**raw["classic"]),
        "geometric": GeometricCandidate(**raw["geometric"]),
        "flag": FlagCandidate(**raw["flag"]),
        "triple": ClassicCandidate(**raw["triple"]),
    }
    repository = HistoryRepository(args.history_dir)
    end = datetime(2026, 7, 31, 23, 59, 59)
    prepared: dict[str, Prepared] = {}
    signals: dict[str, list[PatternSignal]] = {}
    arrays: dict[str, EnvironmentArrays] = {}
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        data = _prepare(repository, symbol, end, args.timeframe)
        prepared[symbol] = data
        signals[symbol] = _all_signals(data, candidates)
        arrays[symbol] = _environment_arrays(data, scale)

    results = []
    for environment in ENVIRONMENTS:
        rows: list[Trade] = []
        by_symbol = {}
        snapshot_cache: dict[tuple[datetime, int], object] = {}
        for symbol in SYMBOLS:
            selected = [
                signal for signal in signals[symbol]
                if _keep(
                    environment, symbol, signal, prepared[symbol], arrays[symbol],
                    prepared, snapshot_cache, scale,
                )
            ]
            trades = _simulate(symbol, prepared[symbol], selected)
            rows.extend(trades)
            by_symbol[symbol] = _periods(trades)
        periods = _periods(rows)
        item = {
            "environment": environment,
            "periods": periods,
            "by_symbol": by_symbol,
            "development_pass": _eligible(periods, False),
            "all_periods_pass": _eligible(periods, True),
        }
        results.append(item)
        print(environment, periods, file=sys.stderr, flush=True)

    payload = {
        "definition": {
            "timeframe": args.timeframe,
            "signal_pool": "same fixed selected classical pattern pool as intermarket filter research",
            "environments": list(ENVIRONMENTS),
            "volatility": f"ATR14 versus its causal EMA{320 * scale}; expanding also exceeds ATR {16 * scale} bars earlier",
            "own_trend": f"{320 * scale}-bar log return (same elapsed time as 320 15m bars)",
            "currency_strength_expanding": f"directional {80 * scale}-bar basket-strength gap is positive and larger than {80 * scale} bars earlier",
            "gold_usd_inverse_regime": f"gold and basket USD {320 * scale}-bar trends are currently opposite, then gold confirms the USD pair direction",
            "sessions": "historical DST-aware local market hours; overlaps assigned NY, then London, then Tokyo",
            "exit": "strict RR 1:1 full exit; same-bar ambiguity is loss",
        },
        "selection_rule": {
            "predefined_candidates": len(ENVIRONMENTS),
            "development": "expectancy > 0 in both 2010-2018 and 2019-2022",
            "minimum_trades": {"train": MIN_TRAIN_TRADES, "validation": MIN_VALIDATION_TRADES},
            "adoption": "development rule plus expectancy > 0 in 2023-2024 and 2025-2026",
        },
        "symbols": list(SYMBOLS),
        "pattern_candidates": raw,
        "results": results,
        "development_passes": [row["environment"] for row in results if row["development_pass"]],
        "all_periods_passes": [row["environment"] for row in results if row["all_periods_pass"]],
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"development_passes": payload["development_passes"], "all_periods_passes": payload["all_periods_passes"]}, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
