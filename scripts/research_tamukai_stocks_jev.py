"""Three fixed stock hypotheses; training first, hash-bound Jev selection second."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_tamukai_stocks_daily as base

ROOT = base.ROOT
EXPERIMENT = "tamukai_stocks_jev_20260926"
PROTOCOL = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT / "results"
DATA = ROOT / "data/stocks/yahoo/jp_largecap10_20260926"
CANDIDATES = ("no_dow", "prior_day_breakout", "sma63_trend")


def candidate_signals(bars: list[base.Bar], candidate: str) -> list[float | None]:
    if candidate == "baseline":
        return base.signals(bars)
    if candidate not in CANDIDATES:
        raise ValueError("Unknown candidate")
    close = [bar.close for bar in bars]
    ma21, ma63 = base._sma(close, 21), base._sma(close, 63)
    dow = base.pivot_trend(bars)
    result = [None] * len(bars)
    for i in range(23, len(bars)):
        trend = (candidate == "no_dow" or candidate == "prior_day_breakout" and dow[i]
                 or candidate == "sma63_trend" and ma63[i] is not None and ma21[i] > ma63[i])
        prior = bars[i-3:i]
        threshold = bars[i-1].high if candidate == "prior_day_breakout" else max(b.high for b in prior)
        if (trend and close[i] > ma21[i] > ma21[i-2]
                and any(bars[k].low <= ma21[k] for k in range(i-3, i)) and close[i] > threshold):
            result[i] = min(b.low for b in prior)
    return result


def qualifies(row: dict, min_trades: int = 50) -> bool:
    pf = row["net_pf"]
    return (row["trades"] >= min_trades and row["net_profit"] > 0
            and row["max_drawdown_pct"] <= 20
            and (pf == "infinity" or isinstance(pf, (float, int)) and pf >= 1.1))


def selected_candidate(selection: dict, training: dict, training_hash: str) -> str:
    if (selection.get("experiment_id") != EXPERIMENT or selection.get("selector") != "jev"
            or selection.get("training_sha256") != training_hash):
        raise ValueError("Selection provenance mismatch")
    chosen = selection.get("selected_candidate")
    if chosen == "none":
        return chosen
    if (chosen not in CANDIDATES or chosen not in training["eligible_candidates"]
            or not qualifies(training["results"][chosen]["main"]["metrics"])):
        raise ValueError("Jev cannot select an ineligible candidate")
    return chosen


def compact(row: dict) -> dict:
    keys = ("trades", "net_profit", "return_pct", "net_pf", "win_rate_pct", "max_drawdown_pct", "exposure_pct")
    return {key: row[key] for key in keys}


def group_result(sleeves: dict, path: Path) -> dict:
    total = base.aggregate(sleeves, path, 2017, False)
    curves = [curve for _, curve in sleeves.values()]
    all_trades = [t for trades, _ in sleeves.values() for t in trades]
    combined = [dict(date=rows[0]["date"], equity=sum(r["equity"] for r in rows),
                     exposed=sum(r["exposed"] for r in rows) / len(rows)) for rows in zip(*curves)]
    previous, yearly = 100000 * len(sleeves), {}
    for year in sorted({r["date"][:4] for r in combined}):
        rows = [r for r in combined if r["date"].startswith(year)]
        trades = [t for t in all_trades if t.exit_date.startswith(year)]
        result = compact(base.metrics(trades, rows, previous))
        result["net_realized_profit"] = sum(t.net_pnl for t in trades)
        yearly[year] = result
        previous = rows[-1]["equity"]
    return dict(metrics=compact(total), yearly=yearly)


def evaluate(datasets: dict, candidate: str, start: str, end: str, cost: float, folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    sleeves, by_symbol = {}, {}
    for symbol, bars in datasets.items():
        stops = [None] * len(bars) if candidate == "buyhold" else candidate_signals(bars, candidate)
        trades, curve = base.simulate(bars, stops, start, end, cost, buyhold=candidate == "buyhold")
        sleeves[symbol] = trades, curve
        by_symbol[symbol] = compact(base.metrics(trades, curve, 100000))
        base.write_csv(folder / f"{symbol}_trades.csv", [asdict(t) for t in trades], list(base.Trade.__dataclass_fields__))
        base.write_csv(folder / f"{symbol}_equity.csv", curve, ["date", "equity", "cash", "exposed"])
    result = group_result(sleeves, folder / "portfolio_equity.csv")
    result["by_symbol"] = by_symbol
    result["quality_diagnostics"] = {}
    for name, excluded in (("exclude_sony", {"6758.T"}),
                           ("exclude_three_known_issues", {"6758.T", "8306.T", "8035.T"})):
        subset = {s: value for s, value in sleeves.items() if s not in excluded}
        result["quality_diagnostics"][name] = group_result(subset, folder / f"{name}_equity.csv")
    return result


def evidence() -> dict:
    symbols = json.loads(PROTOCOL.read_text(encoding="utf-8"))["symbols"]
    paths = {"protocol": PROTOCOL, "source": Path(__file__), "baseline_source": Path(base.__file__),
             "baseline_protocol": base.PROTOCOL, "shared_indicators": ROOT / "src/forextester_backtest/tamukai.py",
             "test": ROOT / "tests/test_tamukai_stocks_jev.py", "data_manifest": DATA / "manifest.json"}
    paths.update({symbol: DATA / f"{symbol}.csv" for symbol in symbols})
    return {key: base.sha256(path) for key, path in paths.items()}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def run(phase: str, output: Path, selection_path: Path | None = None) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    hashes = evidence()
    selection, chosen = {}, "none"
    if phase == "evaluation":
        if selection_path is None:
            raise ValueError("Evaluation requires hash-bound selection.json")
        training_path = output / "training.json"
        training = json.loads(training_path.read_text(encoding="utf-8"))
        if training["evidence"] != hashes:
            raise ValueError("Code/spec/data changed after training")
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        chosen = selected_candidate(selection, training, base.sha256(training_path))
        if chosen == "none":
            write_json(output / "evaluation.json", dict(experiment_id=EXPERIMENT, phase=phase,
                       status="NO_SELECTION_NO_POST_TRAINING_CALCULATION", selection=selection))
            print("NO_SELECTION_NO_POST_TRAINING_CALCULATION")
            return
    output.mkdir(parents=True, exist_ok=True)
    start_record = dict(experiment_id=EXPERIMENT, phase=phase, evidence=hashes,
                        started_at=datetime.now(timezone.utc).isoformat())
    if selection_path is not None:
        start_record["selection_sha256"] = base.sha256(selection_path)
    write_json(output / f"{phase}_start_manifest.json", start_record)
    datasets = {symbol: base.read_bars(DATA / f"{symbol}.csv") for symbol in protocol["symbols"]}
    calendar = [bar.time for bar in next(iter(datasets.values()))]
    if any([bar.time for bar in bars] != calendar for bars in datasets.values()):
        raise ValueError("Mismatching symbol calendar")
    if phase == "training":
        datasets = {s: [b for b in bars if b.time.year <= 2019] for s, bars in datasets.items()}
        start, end = protocol["periods"]["training"]
        results = {}
        for candidate in ("baseline", *CANDIDATES, "buyhold"):
            results[candidate] = {name: evaluate(datasets, candidate, start, end, cost,
                                  output / "training" / name / candidate)
                                  for name, cost in (("main", .001), ("stress", .002))}
        eligible = [c for c in CANDIDATES if qualifies(results[c]["main"]["metrics"])]
        result = dict(**start_record, period=[start, end], results=results, eligible_candidates=eligible,
                      status="AWAITING_INDEPENDENT_VALIDATION_AND_JEV" if eligible else "NO_ELIGIBLE_CANDIDATE",
                      notes="DATA_LIMITED; previously exposed data; yearly net_profit MTM, yearly PF realized exit-year")
    else:
        periods = {}
        for period in ("validation", "final_confirmation", "continuous"):
            start, end = protocol["periods"][period]
            truncated = {s: [b for b in bars if b.time.date().isoformat() <= end] for s, bars in datasets.items()}
            periods[period] = {candidate: {name: evaluate(truncated, candidate, start, end, cost,
                                           output / "evaluation" / period / name / candidate)
                                          for name, cost in (("main", .001), ("stress", .002))}
                               for candidate in (chosen, "baseline", "buyhold")}
        final = periods["final_confirmation"][chosen]
        gates = {period: qualifies(periods[period][chosen]["main"]["metrics"], 100)
                 for period in ("validation", "final_confirmation")}
        gates["final_positive_symbols"] = sum(r["net_profit"] > 0 for r in final["main"]["by_symbol"].values()) >= 6
        gates["final_stress_positive"] = final["stress"]["metrics"]["net_profit"] > 0
        result = dict(**start_record, selection=selection, selected_candidate=chosen, periods=periods,
                      gates=gates, observational_gate_pass=all(gates.values()), status="PENDING_INDEPENDENT_VALIDATION")
    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(output / f"{phase}.json", result)
    print(f"RESULT_JSON={output / (phase + '.json')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("training", "evaluation"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--selection", type=Path)
    args = parser.parse_args()
    run(args.phase, args.output, args.selection)
