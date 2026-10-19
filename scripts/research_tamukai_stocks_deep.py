"""Frozen six-factor daily-stock study; ordered training, validation and final."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_tamukai_stocks_jev as prior
from forextester_backtest.tamukai import _atr

base = prior.base
ROOT = base.ROOT
EXPERIMENT = "tamukai_stocks_deep_20260926"
PROTOCOL = ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT / "results"
RULES = {"trend_strength": ("A",), "shallow_pullback": ("B",), "strong_rejection": ("C",),
         "risk_band": ("D",), "trend_shallow": ("A", "B"), "trend_risk": ("A", "D")}
REFERENCES = ("no_dow", "baseline", "buyhold")


def candidate_signals(bars: list[base.Bar], candidate: str) -> list[float | None]:
    if candidate in ("no_dow", "baseline"):
        return prior.candidate_signals(bars, candidate)
    if candidate not in RULES:
        raise ValueError("Unknown candidate")
    stops = prior.candidate_signals(bars, "no_dow")
    averages = base._sma([b.close for b in bars], 21)
    atr = _atr(bars, 14)
    result = [None] * len(bars)
    for i, stop in enumerate(stops):
        if stop is None:
            continue
        bar = bars[i]
        checks = {
            "A": (i >= 25 and atr[i] is not None and atr[i] > 0
                  and (averages[i]-averages[i-5])/atr[i] >= .25),
            "B": all(atr[k] is not None and atr[k] > 0
                     and (bars[k].low-averages[k])/atr[k] >= -1 for k in range(i-3, i)),
            "C": bar.high > bar.low and (bar.close-bar.low)/(bar.high-bar.low) >= .75,
            "D": .02 <= (bar.close-stop)/bar.close <= .04,
        }
        if all(checks[key] for key in RULES[candidate]):
            result[i] = stop
    return result


def qualifies(result: dict, min_trades: int) -> bool:
    return (prior.qualifies(result["main"]["metrics"], min_trades)
            and result["stress"]["metrics"]["net_profit"] > 0)


def choose(results: dict, eligible: list[str]) -> str:
    def order(candidate):
        pf = results[candidate]["main"]["metrics"]["net_pf"]
        return (-float("inf") if pf == "infinity" else -pf, len(RULES[candidate]), candidate)
    return min(eligible, key=order) if eligible else "none"


def evaluate(datasets: dict, candidate: str, start: str, end: str, cost: float, folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    sleeves, by_symbol = {}, {}
    for symbol, bars in datasets.items():
        clipped = [b for b in bars if b.time.date().isoformat() <= end]
        stops = [None]*len(clipped) if candidate == "buyhold" else candidate_signals(clipped, candidate)
        trades, curve = base.simulate(clipped, stops, start, end, cost, buyhold=candidate == "buyhold")
        sleeves[symbol] = trades, curve
        by_symbol[symbol] = prior.compact(base.metrics(trades, curve, 100000))
        base.write_csv(folder / f"{symbol}_trades.csv", [asdict(t) for t in trades], list(base.Trade.__dataclass_fields__))
        base.write_csv(folder / f"{symbol}_equity.csv", curve, ["date", "equity", "cash", "exposed"])
    result = prior.group_result(sleeves, folder / "portfolio_equity.csv")
    result["by_symbol"] = by_symbol
    result["quality_diagnostics"] = {}
    for name, excluded in (("exclude_sony", {"6758.T"}),
                           ("exclude_three_known_issues", {"6758.T", "8306.T", "8035.T"})):
        subset = {s: value for s, value in sleeves.items() if s not in excluded}
        result["quality_diagnostics"][name] = prior.group_result(subset, folder / f"{name}_equity.csv")
    return result


def run(output: Path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    paths = dict(protocol=PROTOCOL, source=Path(__file__), prior_source=Path(prior.__file__),
                 baseline_source=Path(base.__file__), indicators=ROOT / "src/forextester_backtest/tamukai.py",
                 tests=ROOT / "tests/test_tamukai_stocks_deep.py", data_manifest=prior.DATA / "manifest.json")
    paths.update({s: prior.DATA / f"{s}.csv" for s in protocol["symbols"]})
    evidence = {key: base.sha256(path) for key, path in paths.items()}
    output.mkdir(parents=True, exist_ok=True)
    start_record = dict(experiment_id=EXPERIMENT, evidence=evidence,
                        started_at=datetime.now(timezone.utc).isoformat(), status="DESCRIPTIVE_DATA_LIMITED")
    prior.write_json(output / "run_start_manifest.json", start_record)
    datasets = {s: base.read_bars(prior.DATA / f"{s}.csv") for s in protocol["symbols"]}
    dates = [b.time for b in next(iter(datasets.values()))]
    if any([b.time for b in bars] != dates for bars in datasets.values()):
        raise ValueError("Mismatched calendars")

    def stage(name, period, candidates):
        start, end = protocol["periods"][period]
        results = {candidate: {label: evaluate(datasets, candidate, start, end, rate,
                                  output / name / label / candidate)
                                  for label, rate in (("main", .001), ("stress", .002))}
                   for candidate in candidates}
        return dict(**start_record, phase=name, period=[start, end], results=results)

    training = stage("training", "training", [*RULES, *REFERENCES])
    training["eligible_candidates"] = [c for c in RULES if qualifies(training["results"][c], 50)]
    prior.write_json(output / "training.json", training)
    validation = stage("validation", "validation", training["eligible_candidates"])
    validation["eligible_candidates"] = [c for c in training["eligible_candidates"]
                                         if qualifies(validation["results"][c], 100)]
    validation["training_sha256"] = base.sha256(output / "training.json")
    prior.write_json(output / "validation.json", validation)
    selected = choose(validation["results"], validation["eligible_candidates"])
    selection = dict(experiment_id=EXPERIMENT, selected_candidate=selected,
                     training_sha256=base.sha256(output / "training.json"),
                     validation_sha256=base.sha256(output / "validation.json"),
                     rule="validation max PF; fewer conditions; lexical ID", selected_at=datetime.now(timezone.utc).isoformat(),
                     stop_reason="none" if selected != "none" else
                     ("NO_TRAINING_ELIGIBLE" if not training["eligible_candidates"] else "NO_VALIDATION_ELIGIBLE"))
    prior.write_json(output / "selection.json", selection)
    final_stage = stage("selected_final", "final_confirmation", [] if selected == "none" else [selected])
    gates = {}
    if selected != "none":
        final = final_stage["results"][selected]
        gates = dict(performance=qualifies(final, 100),
                     positive_symbols=sum(x["net_profit"] > 0 for x in final["main"]["by_symbol"].values()) >= 6)
    final_stage["gates"] = gates
    final_stage["observational_gate_pass"] = bool(gates) and all(gates.values())
    prior.write_json(output / "selected_final.json", final_stage)
    descriptive = {period: stage(f"reference_{period}", period, REFERENCES)
                   for period in ("validation", "final_confirmation", "continuous")}
    final = dict(**start_record, phase="complete", selection=selection,
                 selected_candidate=selected, selected_final=final_stage,
                 references=descriptive, reference_status="FIXED_DESCRIPTIVE_NOT_ADOPTION_CANDIDATES",
                 completed_at=datetime.now(timezone.utc).isoformat())
    prior.write_json(output / "final.json", final)
    print(f"RESULT_JSON={output / 'final.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    run(parser.parse_args().output)
