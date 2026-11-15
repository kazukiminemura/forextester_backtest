"""Replay the frozen J Law VCP proxy using a verified Japanese stock snapshot."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from research_tamukai_stocks_daily import ROOT, Bar, _sma, exit_fill, read_bars
from stock_data_cache import verify


EXPERIMENT = "jlaw_vcp_jp_20261115"
PROTOCOL = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
COSTS = {"usual": 0.0010, "stress": 0.0025}
VARIANTS = ("control", "vcp_strict", "vcp_relaxed")
BLOCKS = ("training", "validation", "final_confirmation")


@dataclass(frozen=True)
class Signal:
    pivot: float
    stop: float
    depths: tuple[float, float, float]
    mean_volumes: tuple[float, float, float]

    def qualifies(self, variant: str) -> bool:
        if variant == "control":
            return True
        first, middle, last = self.depths
        old_volume, middle_volume, recent_volume = self.mean_volumes
        minimum_depth = 0.20 if variant == "vcp_strict" else 0.10
        return (minimum_depth <= first <= 0.35 and first > middle > last
                and last <= 0.10 and old_volume > middle_volume > recent_volume)


@dataclass(frozen=True)
class Trade:
    symbol: str
    signal_date: str
    entry_date: str
    exit_date: str
    pivot: float
    entry: float
    stop: float
    target: float
    exit: float
    reason: str

    def net_r(self, cost: float) -> float:
        return (self.exit - self.entry - cost * (self.exit + self.entry)) / (self.entry - self.stop)


def pullback_depth(bars: list[Bar]) -> float:
    peak = bars[0].high
    depth = 0.0
    for bar in bars[1:]:
        depth = max(depth, (peak - bar.low) / peak)
        peak = max(peak, bar.high)
    return depth


def valid_stop(price: float, stop: float) -> bool:
    return 0 < (price - stop) / price <= 0.08


def signals(bars: list[Bar]) -> list[Signal | None]:
    closes = [bar.close for bar in bars]
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    vol50 = _sma([bar.volume for bar in bars], 50)
    result: list[Signal | None] = [None] * len(bars)
    for i in range(251, len(bars)):
        bar = bars[i]
        if not (bar.close > sma50[i] > sma200[i] and sma50[i] > sma50[i - 20]
                and sma200[i] > sma200[i - 20]
                and vol50[i - 1] > 0 and bar.volume >= 1.5 * vol50[i - 1]
                and bar.close >= 0.85 * max(item.high for item in bars[i - 251:i + 1])):
            continue
        recent = bars[i - 10:i]
        pivot = max(item.high for item in recent)
        stop = min(item.low for item in recent)
        if bar.close <= pivot or not valid_stop(bar.close, stop):
            continue
        windows = (bars[i - 40:i - 20], bars[i - 20:i - 10], recent)
        result[i] = Signal(pivot, stop, tuple(pullback_depth(w) for w in windows),
                           tuple(sum(item.volume for item in w) / len(w) for w in windows))
    return result


def replay(symbol: str, bars: list[Bar], candidates: list[Signal | None],
           variant: str, start: str, end: str) -> list[Trade]:
    days = [bar.time.date().isoformat() for bar in bars]
    indices = [i for i, day in enumerate(days) if start <= day <= end]
    if not indices:
        raise ValueError(f"No bars for {symbol}: {start} through {end}")
    trades = []
    pending = None
    position = None
    for i in indices:
        bar = bars[i]
        if pending is not None and bar.open > pending.pivot and valid_stop(bar.open, pending.stop):
            target = bar.open + 3 * (bar.open - pending.stop)
            position = (pending, days[i - 1], days[i], bar.open, target)
        pending = None
        if position is not None:
            signal, signal_date, entry_date, entry, target = position
            fill = exit_fill(bar, signal.stop, target)
            if fill is None and i == indices[-1]:
                fill = bar.close, "period_end"
            if fill is not None:
                price, reason = fill
                trades.append(Trade(symbol, signal_date, entry_date, days[i], signal.pivot,
                                    entry, signal.stop, target, price, reason))
                position = None
        candidate = candidates[i]
        if position is None and i != indices[-1] and candidate is not None and candidate.qualifies(variant):
            pending = candidate
    return trades


def metrics(trades: list[Trade], cost: float) -> dict:
    realized_by_date: dict[str, float] = {}
    values = []
    for trade in trades:
        value = trade.net_r(cost)
        values.append(value)
        realized_by_date[trade.exit_date] = realized_by_date.get(trade.exit_date, 0.0) + value
    gross_win = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)
    cumulative = peak = drawdown = 0.0
    for day in sorted(realized_by_date):
        cumulative += realized_by_date[day]
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    count = len(values)
    return {
        "trades": count,
        "win_rate_pct": 100 * sum(value > 0 for value in values) / count if count else None,
        "net_r": sum(values),
        "average_r": sum(values) / count if count else None,
        "profit_factor": gross_win / gross_loss if gross_loss else None,
        "gross_win_r": gross_win,
        "gross_loss_r": gross_loss,
        "realized_drawdown_r": drawdown,
    }


def gates(results: dict, variant: str) -> dict[str, bool]:
    continuous = results["continuous"][variant]["usual"]
    block_candidates = [results[block][variant]["usual"] for block in BLOCKS]
    block_controls = [results[block]["control"]["usual"] for block in BLOCKS]
    return {
        "minimum_sample": continuous["trades"] >= 100 and all(m["trades"] >= 20 for m in block_candidates),
        "positive_in_each_block_at_both_costs": all(
            results[block][variant][cost]["net_r"] > 0 for block in BLOCKS for cost in COSTS
        ),
        "improves_control_in_each_block": all(
            candidate["average_r"] is not None and control["average_r"] is not None
            and candidate["average_r"] > control["average_r"]
            for candidate, control in zip(block_candidates, block_controls)
        ),
        "at_least_five_profitable_symbols": sum(m["net_r"] > 0 for m in continuous["symbols"].values()) >= 5,
        "realized_drawdown_at_most_25r": continuous["realized_drawdown_r"] <= 25,
    }


def run(data_dir: Path, output: Path) -> dict:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    manifest_hash = hashlib.sha256((data_dir / "manifest.json").read_bytes()).hexdigest()
    if manifest_hash != protocol["data_manifest"]["sha256"]:
        raise ValueError("Snapshot manifest differs from the frozen input")
    verified_files = verify(data_dir)
    csv_files = {path.stem: path for path in verified_files if path.suffix == ".csv"}
    if set(csv_files) != set(protocol["symbols"]):
        raise ValueError("Snapshot does not contain the ten frozen symbols")
    histories = {symbol: read_bars(csv_files[symbol]) for symbol in protocol["symbols"]}
    cal = [tuple(bar.time for bar in bars) for bars in histories.values()]
    if any(item != cal[0] for item in cal[1:]) or len(cal[0]) < 252:
        raise ValueError("Snapshot calendars must agree and contain at least 252 dates")
    candidates = {symbol: signals(bars) for symbol, bars in histories.items()}
    results = {}
    ledger = []
    for period, (start, end) in protocol["periods"].items():
        results[period] = {}
        for variant in VARIANTS:
            by_symbol = {symbol: replay(symbol, bars, candidates[symbol], variant, start, end)
                         for symbol, bars in histories.items()}
            trades = [trade for items in by_symbol.values() for trade in items]
            results[period][variant] = {
                name: {**metrics(trades, cost),
                       "symbols": {symbol: metrics(items, cost) for symbol, items in by_symbol.items()}}
                for name, cost in COSTS.items()
            }
            ledger.extend({"period": period, "variant": variant, **asdict(trade),
                           **{f"net_r_{name}": trade.net_r(cost) for name, cost in COSTS.items()}}
                          for trade in trades)
    summary = {
        "experiment_id": EXPERIMENT,
        "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "data_directory": str(data_dir.resolve()),
        "input_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in verified_files},
        "calendar_first": cal[0][0].date().isoformat(),
        "calendar_last": cal[0][-1].date().isoformat(),
        "first_indicator_eligible_date": cal[0][251].date().isoformat(),
        "calendar_rows": len(cal[0]),
        "cost_per_side": COSTS,
        "results": results,
        "gates": {variant: gates(results, variant) for variant in VARIANTS if variant != "control"},
    }
    output.mkdir(parents=True, exist_ok=True)
    with (output / "trades.csv").open("x", newline="", encoding="utf-8") as stream:
        fields = ["period", "variant", *Trade.__dataclass_fields__, *(f"net_r_{name}" for name in COSTS)]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ledger)
    with (output / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return summary


def self_check() -> None:
    from datetime import datetime

    bars = [Bar(datetime(2020, 1, day), *values) for day, values in enumerate([
        (95, 100, 90, 95, 5), (92, 130, 90, 100, 5), (105, 120, 85, 105, 5),
    ], start=1)]
    assert abs(pullback_depth(bars[:2]) - 0.10) < 1e-12
    strict = Signal(90, 88, (0.25, 0.13, 0.05), (30, 20, 10))
    relaxed = Signal(90, 88, (0.15, 0.13, 0.05), (30, 20, 10))
    assert strict.qualifies("vcp_strict") and relaxed.qualifies("vcp_relaxed")
    assert not relaxed.qualifies("vcp_strict")
    assert valid_stop(100, 92) and not valid_stop(100, 91.99)
    trades = replay("test", bars, [strict, None, None], "vcp_strict", "2020-01-01", "2020-01-03")
    assert len(trades) == 1 and trades[0].entry == 92 and trades[0].target == 104
    assert trades[0].reason == "target" and trades[0].net_r(0) == 3
    both_touched = Bar(datetime(2020, 1, 2), 92, 130, 85, 100, 5)
    trades = replay("test", [bars[0], both_touched], [strict, None], "control", "2020-01-01", "2020-01-02")
    assert trades[0].reason == "stop" and trades[0].net_r(0) == -1
    canceled = replay("test", bars, [Signal(92, 88, strict.depths, strict.mean_volumes), None, None],
                      "control", "2020-01-01", "2020-01-03")
    assert canceled == []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/stocks/yahoo/jp_largecap10_20261115")
    parser.add_argument("--output", type=Path, default=ROOT / "agent_runs" / EXPERIMENT)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("VCP self-check passed")
        return
    run(args.data_dir, args.output)
    print(args.output / "summary.json")


if __name__ == "__main__":
    main()
