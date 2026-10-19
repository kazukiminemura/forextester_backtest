"""Frozen daily stock pullback experiment. No optimization or external API calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forextester_backtest.models import Bar
from forextester_backtest.tamukai import _sma

EXPERIMENT = "tamukai_stocks_daily_20260926"
PROTOCOL = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"


def read_bars(path: Path) -> list[Bar]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        bars = [Bar(datetime.strptime(row["date"], "%Y-%m-%d"),
                    *(float(row[key]) for key in ("open", "high", "low", "close", "volume")))
                for row in csv.DictReader(stream)]
    if not bars:
        raise ValueError(f"Empty data: {path}")
    for index, bar in enumerate(bars):
        prices = (bar.open, bar.high, bar.low, bar.close)
        if (not all(math.isfinite(x) and x > 0 for x in prices)
                or not math.isfinite(bar.volume) or bar.volume < 0
                or not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high
                or (index and bar.time <= bars[index - 1].time)):
            raise ValueError(f"Invalid OHLC/date: {path} row {index + 2}")
    return bars


def pivot_trend(bars: list[Bar]) -> list[bool]:
    """Strict pivots become available only on the second subsequent close."""
    highs, lows, trends = [], [], []
    for i in range(len(bars)):
        if i >= 4:
            center = bars[i - 2]
            neighbors = bars[i - 4:i - 2] + bars[i - 1:i + 1]
            if all(center.high > item.high for item in neighbors):
                highs.append(center.high)
            if all(center.low < item.low for item in neighbors):
                lows.append(center.low)
        trends.append(len(highs) >= 2 and len(lows) >= 2
                      and highs[-1] > highs[-2] and lows[-1] > lows[-2])
    return trends


def signals(bars: list[Bar]) -> list[float | None]:
    """Return frozen stop at signal-day close, or None; execution is separate."""
    averages = _sma([bar.close for bar in bars], 21)
    trends = pivot_trend(bars)
    result = [None] * len(bars)
    for i in range(23, len(bars)):
        prior = bars[i - 3:i]
        if (trends[i] and bars[i].close > averages[i] > averages[i - 2]
                and any(bars[k].low <= averages[k] for k in range(i - 3, i))
                and bars[i].close > max(bar.high for bar in prior)):
            result[i] = min(bar.low for bar in prior)
    return result


def exit_fill(bar: Bar, stop: float, target: float) -> tuple[float, str] | None:
    if bar.open <= stop:
        return bar.open, "gap_stop"
    if bar.open >= target:
        return bar.open, "gap_target"
    if bar.low <= stop:
        return stop, "stop"
    if bar.high >= target:
        return target, "target"
    return None


@dataclass
class Trade:
    signal_date: str
    entry_date: str
    exit_date: str
    entry: float
    exit: float
    stop: float
    target: float
    units: float
    entry_cost: float
    exit_cost: float
    net_pnl: float
    return_pct: float
    reason: str


def simulate(bars: list[Bar], stops: list[float | None], start: str, end: str,
             cost: float, initial: float = 100000, buyhold: bool = False) -> tuple[list[Trade], list[dict]]:
    if len(stops) != len(bars) or not 0 <= cost < 1 or initial <= 0:
        raise ValueError("Invalid signal length/cost/capital")
    indices = [i for i, bar in enumerate(bars) if start <= bar.time.date().isoformat() <= end]
    if not indices:
        raise ValueError("No data in period")
    cash, position, pending = initial, None, None
    trades, equity = [], []
    for i in indices:
        bar = bars[i]
        date = bar.time.date().isoformat()
        if buyhold and i == indices[0]:
            pending = (date, 0.0)
        if position is None and pending is not None:
            signal_date, stop = pending
            if bar.open > stop:
                units = cash / (bar.open * (1 + cost))
                position = dict(signal_date=signal_date, entry_date=date, entry=bar.open,
                                stop=stop, target=bar.open + (bar.open - stop), units=units,
                                entry_cost=units * bar.open * cost, initial_cash=cash)
                cash = 0.0
        pending = None
        exposed = position is not None
        if position is not None:
            fill = None if buyhold else exit_fill(bar, position["stop"], position["target"])
            if fill is None and i == indices[-1]:
                fill = bar.close, "period_end"
            if fill is not None:
                price, reason = fill
                exit_cost = position["units"] * price * cost
                cash = position["units"] * price - exit_cost
                net_pnl = cash - position["initial_cash"]
                trades.append(Trade(**{key: position[key] for key in
                                       ("signal_date", "entry_date", "entry", "stop", "target", "units", "entry_cost")},
                                    exit_date=date, exit=price, exit_cost=exit_cost, net_pnl=net_pnl,
                                    return_pct=100 * net_pnl / position["initial_cash"], reason=reason))
                position = None
        value = cash + (position["units"] * bar.close if position is not None else 0)
        equity.append(dict(date=date, equity=value, cash=cash, exposed=int(exposed)))
        if not buyhold and position is None and stops[i] is not None and i != indices[-1]:
            pending = date, stops[i]
    return trades, equity


def metrics(trades: list[Trade], equity: list[dict], initial: float) -> dict:
    profits = sum(max(trade.net_pnl, 0) for trade in trades)
    losses = -sum(min(trade.net_pnl, 0) for trade in trades)
    peak, drawdown = initial, 0.0
    for row in equity:
        peak = max(peak, row["equity"])
        drawdown = max(drawdown, 100 * (peak - row["equity"]) / peak)
    profit = equity[-1]["equity"] - initial
    return dict(initial_capital=initial, final_equity=equity[-1]["equity"], net_profit=profit,
                return_pct=100 * profit / initial, trades=len(trades),
                win_rate_pct=100 * sum(t.net_pnl > 0 for t in trades) / len(trades) if trades else 0,
                net_pf=profits / losses if losses else ("infinity" if profits else "undefined"),
                average_net_profit=profit / len(trades) if trades else 0,
                max_drawdown_pct=drawdown,
                exposure_pct=100 * sum(row["exposed"] for row in equity) / len(equity))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(sleeves: dict, folder: Path, start_year: int, yearly: bool) -> dict:
    """Reuse executed sleeves for portfolio and quality-only subset diagnostics."""
    initial = 100000 * len(sleeves)
    trades = [trade for symbol_trades, _ in sleeves.values() for trade in symbol_trades]
    curve = [dict(date=rows[0]["date"], equity=sum(r["equity"] for r in rows),
                  cash=sum(r["cash"] for r in rows),
                  exposed=sum(r["exposed"] for r in rows) / len(rows))
             for rows in zip(*(curve for _, curve in sleeves.values()))]
    write_csv(folder, curve, ["date", "equity", "cash", "exposed"])
    result = metrics(trades, curve, initial)
    result["symbols"] = list(sleeves)
    if yearly:
        years, previous = {}, initial
        for year in range(start_year, 2026):
            rows = [r for r in curve if r["date"].startswith(str(year))]
            year_trades = [t for t in trades if t.exit_date.startswith(str(year))]
            row = metrics(year_trades, rows, previous)
            row["net_realized_profit"] = sum(t.net_pnl for t in year_trades)
            row["average_net_profit"] = row["net_realized_profit"] / len(year_trades) if year_trades else 0
            row["note"] = "MTM net_profit; PF/win rate use exit-year realized trades"
            years[str(year)] = row
            previous = rows[-1]["equity"]
        result["yearly"] = years
    return result


def run(data_dir: Path, output: Path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    symbols = protocol["symbols"]
    datasets = {symbol: read_bars(data_dir / f"{symbol}.csv") for symbol in symbols}
    reference_dates = [b.time for b in datasets[symbols[0]]]
    if any([b.time for b in bars] != reference_dates for bars in datasets.values()):
        raise ValueError("Symbols must share the same complete observed session calendar")
    if (reference_dates[0].date().isoformat() != "2016-07-12"
            or reference_dates[-1].date().isoformat() != "2025-12-30"):
        raise ValueError("Required warmup/evaluation coverage unavailable")
    output.mkdir(parents=True, exist_ok=True)
    summary = dict(experiment_id=EXPERIMENT, started_at=datetime.now(timezone.utc).isoformat(),
                   protocol_sha256=sha256(PROTOCOL), source_sha256=sha256(Path(__file__)),
                   tests_sha256=sha256(ROOT / "tests/test_tamukai_stocks_daily.py"),
                   reused_source_sha256=sha256(ROOT / "src/forextester_backtest/tamukai.py"),
                   data_sha256={symbol: sha256(data_dir / f"{symbol}.csv") for symbol in symbols},
                   periods={}, gate_status="PENDING_INDEPENDENT_VALIDATION")
    manifest_path = data_dir / "manifest.json"
    summary["data_manifest_sha256"] = sha256(manifest_path)
    (output / "run_start_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    computed_signals = {symbol: signals(bars) for symbol, bars in datasets.items()}
    for cost_name, cost in (("main", 0.001), ("stress", 0.002)):
        summary["periods"][cost_name] = {}
        for period, (start, end) in protocol["periods"].items():
            methods = {}
            for method in ("strategy", "buyhold"):
                by_symbol, sleeves = {}, {}
                folder = output / cost_name / period / method
                folder.mkdir(parents=True, exist_ok=True)
                for symbol, bars in datasets.items():
                    trades, curve = simulate(bars, computed_signals[symbol], start, end, cost,
                                             buyhold=method == "buyhold")
                    by_symbol[symbol] = metrics(trades, curve, 100000)
                    sleeves[symbol] = trades, curve
                    write_csv(folder / f"{symbol}_trades.csv", [asdict(t) for t in trades], list(Trade.__dataclass_fields__))
                    write_csv(folder / f"{symbol}_equity.csv", curve, ["date", "equity", "cash", "exposed"])
                result = aggregate(sleeves, folder / "portfolio_equity.csv", int(start[:4]), period == "continuous")
                result["by_symbol"] = by_symbol
                result["quality_diagnostics"] = {}
                for name, exclusions in (("exclude_sony", {"6758.T"}),
                                          ("exclude_three_known_issues", {"6758.T", "8306.T", "8035.T"})):
                    subset = {symbol: value for symbol, value in sleeves.items() if symbol not in exclusions}
                    result["quality_diagnostics"][name] = aggregate(
                        subset, folder / f"{name}_equity.csv", int(start[:4]), period == "continuous")
                methods[method] = result
            summary["periods"][cost_name][period] = methods
    gates = {}
    for period in ("validation", "final_confirmation"):
        row = summary["periods"]["main"][period]["strategy"]
        pf = row["net_pf"]
        gates[period] = dict(min_trades=row["trades"] >= 100,
                             min_pf=pf == "infinity" or isinstance(pf, (int, float)) and pf >= 1.1,
                             positive_profit=row["net_profit"] > 0,
                             max_drawdown=row["max_drawdown_pct"] <= 20)
    final = summary["periods"]["main"]["final_confirmation"]["strategy"]
    gates["final_cross_symbol"] = sum(r["net_profit"] > 0 for r in final["by_symbol"].values()) >= 6
    gates["final_stress_positive"] = summary["periods"]["stress"]["final_confirmation"]["strategy"]["net_profit"] > 0
    summary["gates"] = gates
    summary["observational_gate_pass"] = (all(gates["validation"].values())
                                           and all(gates["final_confirmation"].values())
                                           and gates["final_cross_symbol"] and gates["final_stress_positive"])
    summary["completed_at"] = datetime.now(timezone.utc).isoformat()
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"RESULT_JSON={output / 'summary.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "agent_runs" / EXPERIMENT / "data")
    parser.add_argument("--output", type=Path, default=ROOT / "agent_runs" / EXPERIMENT / "results")
    args = parser.parse_args()
    run(args.data_dir, args.output)
