"""Replay the frozen J Law VCP rules across the current Nikkei 225 constituents."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from research_jlaw_vcp import (
    COSTS, ROOT, VARIANTS, Trade, gates, metrics, read_bars, replay, self_check, signals,
)


EXPERIMENT = "jlaw_vcp_nikkei225_20261115"
PROTOCOL = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
DATA = ROOT / "data/stocks/yahoo/nikkei225_current_20261115"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(data_dir: Path, protocol: dict) -> tuple[dict, dict, dict]:
    manifest_path = data_dir / "manifest.json"
    if sha256(manifest_path) != protocol["data_manifest"]["sha256"]:
        raise ValueError("Snapshot manifest differs from the frozen input")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records, omissions = manifest["symbols"], manifest["omissions"]
    official = set(protocol["symbols"])
    if len(official) != 225 or records.keys() & omissions.keys() or records.keys() | omissions.keys() != official:
        raise ValueError("Manifest must account for each frozen constituent exactly once")

    histories, coverage, excluded = {}, {}, dict(omissions)
    for symbol, record in sorted(records.items()):
        if not symbol.endswith(".T") or not symbol[:-2].isalnum():
            raise ValueError(f"Invalid Japanese stock symbol: {symbol}")
        for suffix, key in (("json", "raw_sha256"), ("csv", "csv_sha256")):
            if sha256(data_dir / f"{symbol}.{suffix}") != record[key]:
                raise ValueError(f"Snapshot checksum mismatch: {symbol}.{suffix}")
        bars = read_bars(data_dir / f"{symbol}.csv")
        first_day = bars[0].time.date().isoformat()
        last_day = bars[-1].time.date().isoformat()
        eligible_day = bars[251].time.date().isoformat() if len(bars) >= 252 else None
        gaps = record["missing_dates_inside_coverage"]
        trailing = record["trailing_reference_days"]
        if not isinstance(gaps, list) or not isinstance(trailing, int) or trailing < 0:
            raise ValueError(f"Missing-date list malformed: {symbol}")
        coverage[symbol] = {
            "rows": len(bars), "first": first_day, "last": last_day,
            "first_indicator_eligible_date": eligible_day, "missing_dates_inside_coverage": gaps,
            "trailing_reference_days": trailing,
        }
        full_start, full_end = protocol["periods"]["continuous"]
        if gaps:
            excluded[symbol] = {"reason": "interior_calendar_gaps", "dates": gaps}
        elif trailing:
            excluded[symbol] = {"reason": "terminal_calendar_gaps", "sessions": trailing}
        elif eligible_day is None or eligible_day > full_end or last_day < full_start:
            excluded[symbol] = {"reason": "insufficient_eligible_coverage"}
        else:
            histories[symbol] = bars
    if not histories:
        raise ValueError("No analysis-eligible constituents in the frozen input")
    return histories, coverage, excluded


def robustness(total: dict, by_symbol: dict) -> dict:
    profitable = sorted(
        ((symbol, data["net_r"]) for symbol, data in by_symbol.items() if data["net_r"] > 0),
        key=lambda item: item[1], reverse=True,
    )
    active = {symbol: data for symbol, data in by_symbol.items() if data["trades"]}
    leave_one_out = {}
    for symbol, removed in active.items():
        wins = total["gross_win_r"] - removed["gross_win_r"]
        losses = total["gross_loss_r"] - removed["gross_loss_r"]
        leave_one_out[symbol] = {
            "net_r": total["net_r"] - removed["net_r"],
            "profit_factor": wins / losses if losses > 1e-12 else None,
        }
    net_values = [item["net_r"] for item in leave_one_out.values()]
    pfs = [item["profit_factor"] for item in leave_one_out.values() if item["profit_factor"] is not None]
    return {
        "evaluated_symbols": len(by_symbol), "active_symbols": len(active),
        "profitable_symbols": len(profitable),
        "top_profitable_symbol": profitable[0][0] if profitable else None,
        "top_share_of_profitable_symbol_net_pct": (
            100 * profitable[0][1] / sum(net_r for _, net_r in profitable) if profitable else None
        ),
        "leave_one_active_symbol_out": leave_one_out,
        "leave_one_out_net_r_range": [min(net_values), max(net_values)] if net_values else None,
        "leave_one_out_pf_range": [min(pfs), max(pfs)] if pfs else None,
    }


def breadth_gates(results: dict, variant: str) -> dict[str, bool]:
    conditions = gates(results, variant)
    del conditions["at_least_five_profitable_symbols"]
    broad = results["continuous"][variant]["usual"]["robustness"]
    conditions["at_least_half_of_evaluated_symbols_profitable"] = (
        2 * broad["profitable_symbols"] >= broad["evaluated_symbols"]
    )
    return conditions


def run(data_dir: Path, output: Path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol["status"] != "FROZEN_DESCRIPTIVE":
        raise ValueError("Freeze and verify the input manifest before evaluating the strategy")
    base_protocol = ROOT / protocol["base_protocol"]
    if protocol["periods"] != json.loads(base_protocol.read_text(encoding="utf-8"))["periods"]:
        raise ValueError("The Nikkei replay must use the original period boundaries")
    histories, coverage, excluded = snapshot(data_dir, protocol)
    candidates = {symbol: signals(bars) for symbol, bars in histories.items()}
    results, ledger, eligible_by_period = {}, [], {}
    for period, (start, end) in protocol["periods"].items():
        results[period] = {}
        available = {
            symbol: bars for symbol, bars in histories.items()
            if coverage[symbol]["first_indicator_eligible_date"] <= end and coverage[symbol]["last"] >= start
        }
        eligible_by_period[period] = sorted(available)
        for variant in VARIANTS:
            by_symbol = {symbol: replay(symbol, bars, candidates[symbol], variant, start, end)
                         for symbol, bars in available.items()}
            trades = [trade for items in by_symbol.values() for trade in items]
            cost_results = {}
            for name, cost in COSTS.items():
                aggregate = metrics(trades, cost)
                by_symbol_metrics = {symbol: metrics(items, cost) for symbol, items in by_symbol.items()}
                cost_results[name] = {**aggregate, "symbols": by_symbol_metrics,
                                      "robustness": robustness(aggregate, by_symbol_metrics)}
            results[period][variant] = cost_results
            ledger.extend({"period": period, "variant": variant, **asdict(trade),
                           **{f"net_r_{name}": trade.net_r(cost) for name, cost in COSTS.items()}}
                          for trade in trades)

    summary = {
        "experiment_id": EXPERIMENT, "protocol_sha256": sha256(PROTOCOL),
        "base_protocol_sha256": sha256(base_protocol),
        "runner_sha256": sha256(Path(__file__)), "base_runner_sha256": sha256(Path(__file__).with_name("research_jlaw_vcp.py")),
        "data_directory": str(data_dir.resolve()), "data_manifest_sha256": sha256(data_dir / "manifest.json"),
        "constituents": protocol["symbols"], "coverage": coverage, "excluded_symbols": excluded,
        "eligible_symbols_by_period": eligible_by_period, "cost_per_side": COSTS, "results": results,
        "gates": {variant: breadth_gates(results, variant) for variant in VARIANTS if variant != "control"},
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=ROOT / "agent_runs" / EXPERIMENT)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        assert robustness(metrics([], 0.001), {})["leave_one_out_net_r_range"] is None
        profitable = Trade("A", "2020-01-01", "2020-01-02", "2020-01-03", 99, 100, 95, 115, 115, "target")
        unprofitable = Trade("B", "2020-01-01", "2020-01-02", "2020-01-03", 99, 100, 95, 115, 95, "stop")
        broad = robustness(metrics([profitable, unprofitable], 0), {
            "A": metrics([profitable], 0), "B": metrics([unprofitable], 0), "C": metrics([], 0),
        })
        assert broad["leave_one_out_net_r_range"] == [-1, 3] and broad["active_symbols"] == 2
        assert broad["evaluated_symbols"] == 3 and broad["profitable_symbols"] == 1
        print("VCP self-check passed")
        return
    run(args.data_dir, args.output)
    print(args.output / "summary.json")


if __name__ == "__main__":
    main()
