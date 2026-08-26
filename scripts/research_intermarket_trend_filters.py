"""Test currency-basket and gold/USD trend filters on classical patterns."""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from research_4h_wall_breakout import PERIODS, SYMBOLS, Trade, _period_rows, _stats
from research_classic_chart_patterns import Candidate as ClassicCandidate
from research_classic_chart_patterns import PatternSignal, _pivots
from research_classic_chart_patterns import _signals as classic_signals
from research_classic_chart_patterns import _simulate
from research_flag_patterns import Candidate as FlagCandidate
from research_flag_patterns import _signals as flag_signals
from research_geometric_chart_patterns import Candidate as GeometricCandidate
from research_geometric_chart_patterns import _signals as geometric_signals
from research_strict_rr_portfolio import Prepared, _prepare
from research_triple_chart_patterns import _signals as triple_signals


HORIZONS = (80, 320, 960)
FILTERS = ("baseline", "currency", "gold_usd", "currency_and_gold")


@dataclass(frozen=True, slots=True)
class TrendSnapshot:
    currency: dict[str, float]
    gold: float | None


def _selected(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["selected"]["candidate"]


def _all_signals(data: Prepared, candidates: dict[str, object]) -> list[PatternSignal]:
    pivot_sizes = {
        candidates["classic"].pivot_bars,
        candidates["geometric"].pivot_bars,
        candidates["triple"].pivot_bars,
    }
    pivots = {size: _pivots(data, size) for size in pivot_sizes}
    rows = list(classic_signals(data, candidates["classic"], pivots[candidates["classic"].pivot_bars]))
    rows.extend(geometric_signals(data, candidates["geometric"], pivots[candidates["geometric"].pivot_bars]))
    rows.extend(flag_signals(data, candidates["flag"]))
    rows.extend(triple_signals(data, candidates["triple"], True, pivots[candidates["triple"].pivot_bars]))
    rows.extend(triple_signals(data, candidates["triple"], False, pivots[candidates["triple"].pivot_bars]))
    rows.sort(key=lambda row: row.index)
    # One opportunity per symbol/bar. The family order above is fixed before
    # looking at results so overlapping descriptions cannot multiply trades.
    deduplicated: list[PatternSignal] = []
    used: set[int] = set()
    for row in rows:
        if row.index not in used:
            deduplicated.append(row)
            used.add(row.index)
    return deduplicated


def _return_at(data: Prepared, timestamp: datetime, horizon: int) -> float | None:
    index = bisect_right(data.times, timestamp) - 1
    if index < horizon or data.close[index] <= 0 or data.close[index - horizon] <= 0:
        return None
    return float(np.log(data.close[index] / data.close[index - horizon]))


def _snapshot(prepared: dict[str, Prepared], timestamp: datetime, horizon: int) -> TrendSnapshot:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for symbol, data in prepared.items():
        if symbol == "XAUUSD":
            continue
        change = _return_at(data, timestamp, horizon)
        if change is None:
            continue
        base, quote = symbol[:3], symbol[3:]
        totals[base] = totals.get(base, 0.0) + change
        totals[quote] = totals.get(quote, 0.0) - change
        counts[base] = counts.get(base, 0) + 1
        counts[quote] = counts.get(quote, 0) + 1
    strength = {currency: total / counts[currency] for currency, total in totals.items()}
    return TrendSnapshot(strength, _return_at(prepared["XAUUSD"], timestamp, horizon))


def _currency_confirms(symbol: str, direction: int, snapshot: TrendSnapshot) -> bool:
    if symbol == "XAUUSD":
        return True
    base, quote = symbol[:3], symbol[3:]
    if base not in snapshot.currency or quote not in snapshot.currency:
        return False
    return direction * (snapshot.currency[base] - snapshot.currency[quote]) > 0


def _gold_confirms(symbol: str, direction: int, snapshot: TrendSnapshot) -> bool:
    if snapshot.gold is None or snapshot.gold == 0:
        return False
    if symbol == "XAUUSD":
        expected_pair_direction = snapshot.gold
    elif symbol.startswith("USD"):
        expected_pair_direction = -snapshot.gold
    elif symbol.endswith("USD"):
        expected_pair_direction = snapshot.gold
    else:
        return True
    return direction * expected_pair_direction > 0


def _filter_signals(
    symbol: str,
    data: Prepared,
    signals: list[PatternSignal],
    prepared: dict[str, Prepared],
    horizon: int,
    filter_name: str,
) -> list[PatternSignal]:
    if filter_name == "baseline":
        return signals
    kept = []
    cache: dict[datetime, TrendSnapshot] = {}
    for signal in signals:
        timestamp = data.times[signal.index]
        snapshot = cache.setdefault(timestamp, _snapshot(prepared, timestamp, horizon))
        currency_ok = _currency_confirms(symbol, signal.direction, snapshot)
        gold_ok = _gold_confirms(symbol, signal.direction, snapshot)
        if (
            (filter_name == "currency" and currency_ok)
            or (filter_name == "gold_usd" and gold_ok)
            or (filter_name == "currency_and_gold" and currency_ok and gold_ok)
        ):
            kept.append(signal)
    return kept


def _periods(rows: list[Trade]) -> dict:
    return {
        name: _stats(_period_rows(rows, start, end), months)
        for name, (start, end, months) in PERIODS.items()
    }


def _selection_score(periods: dict) -> tuple[float, float, int]:
    train = periods["train_2010_2018"]
    validation = periods["validation_2019_2022"]
    return (
        min(float(train["expectancy_r"]), float(validation["expectancy_r"])),
        min(float(train["profit_factor"] or 0), float(validation["profit_factor"] or 0)),
        int(train["trades"]) + int(validation["trades"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--output", type=Path, default=Path("scripts/intermarket_trend_filter_results.json"))
    args = parser.parse_args()
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
    for symbol in SYMBOLS:
        print(f"Loading {symbol}...", file=sys.stderr, flush=True)
        prepared[symbol] = _prepare(repository, symbol, end, "15m")
        signals[symbol] = _all_signals(prepared[symbol], candidates)

    rows = []
    for filter_name in FILTERS:
        horizons = (HORIZONS[0],) if filter_name == "baseline" else HORIZONS
        for horizon in horizons:
            trades: list[Trade] = []
            by_symbol: dict[str, dict] = {}
            for symbol in SYMBOLS:
                selected_signals = _filter_signals(
                    symbol, prepared[symbol], signals[symbol], prepared, horizon, filter_name
                )
                symbol_trades = _simulate(symbol, prepared[symbol], selected_signals)
                trades.extend(symbol_trades)
                by_symbol[symbol] = _periods(symbol_trades)
            periods = _periods(trades)
            rows.append({
                "filter": filter_name,
                "horizon_15m_bars": horizon,
                "periods": periods,
                "by_symbol": by_symbol,
                "selection_score": _selection_score(periods),
            })
            print(filter_name, horizon, periods, file=sys.stderr, flush=True)

    selected = {}
    for filter_name in FILTERS:
        options = [row for row in rows if row["filter"] == filter_name]
        selected[filter_name] = max(options, key=lambda row: tuple(row["selection_score"]))
    payload = {
        "definition": {
            "signal_pool": "selected classical tops/bottoms/H&S, triangles/rectangle/wedges, flags, triple tops/bottoms",
            "currency_trend": "equal-weight mean log return of each currency across available FX pairs, oriented base positive and quote negative",
            "gold_trend": "XAUUSD log return; confirms XAUUSD direction and the historical inverse USD relationship only for USD pairs",
            "timing": "filter uses signal-bar close or older observations; entry is next bar open",
            "exit": "strict RR 1:1 full exit; same-bar ambiguity is loss",
            "non_usd_crosses": "gold gate passes through because no universal directional mapping was assumed",
        },
        "symbols": list(SYMBOLS),
        "selection": "horizon selected independently per filter using 2010-2018 and 2019-2022 only",
        "pattern_candidates": raw,
        "selected": selected,
        "all_results": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
