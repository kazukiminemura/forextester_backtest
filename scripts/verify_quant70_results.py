"""Independently reconcile saved quant70 trades without rerunning market history."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(value, message):
    if not value:
        raise AssertionError(message)


def close(actual, expected, message):
    if actual is None or expected is None:
        require(actual is expected, message)
    else:
        require(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9),
                f"{message}: {actual} != {expected}")


def summarize(rows, months):
    rows = sorted(rows, key=lambda t: (t[0], t[1], t[2]))
    values = [t[3] for t in rows]
    wins, losses, breakevens = (sum(v > 0 for v in values), sum(v < 0 for v in values), sum(v == 0 for v in values))
    positive = math.fsum(v for v in values if v > 0)
    negative = -math.fsum(v for v in values if v < 0)
    running = high = drawdown = 0.0
    for value in values:
        running += value
        high = max(high, running)
        drawdown = max(drawdown, high-running)
    n = len(rows)
    p = wins/n if n else 0
    z = 1.959963984540054
    denominator = 1+z*z/n if n else 1
    wilson = (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/denominator if n else 0
    normal = [t for t in rows if t[4] != "period_end"]
    return {"trades": n, "wins": wins, "losses": losses, "breakevens": breakevens,
            "net_win_rate_pct": 100*p, "profit_factor": positive/negative if negative else None,
            "net_r": math.fsum(values), "expectancy_r": math.fsum(values)/n if n else None,
            "realized_drawdown_pct": drawdown*0.25, "trades_per_month": n/months,
            "wilson_95_lower_pct": 100*wilson,
            "forced_period_exits": n-len(normal), "ambiguous_trades": sum(t[5] for t in rows),
            "normal_exit_win_rate_pct": 100*sum(t[3]>0 for t in normal)/len(normal) if normal else None}


def qualifies(summary, pairs, period, gates):
    name = "recent" if period == "recent_reference" else period
    minimum_pair = gates["min_trades_each_pair_train" if period == "train" else "min_trades_each_pair_other"]
    return (summary["trades"] >= gates[f"min_{name}_trades"]
            and summary["net_win_rate_pct"] >= gates["net_win_rate_pct"]
            and summary["profit_factor"] is not None and summary["profit_factor"] >= gates["profit_factor"]
            and summary["expectancy_r"] is not None and summary["expectancy_r"] > 0
            and summary["trades_per_month"] >= gates["min_trades_per_month"]
            and summary["realized_drawdown_pct"] <= gates["max_realized_drawdown_pct"]
            and all(p["trades"] >= minimum_pair for p in pairs.values())
            and sum(p["net_r"] > 0 for p in pairs.values()) >= gates["min_positive_pairs"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT/"agent_runs/quant70_20260908")
    args = parser.parse_args()
    output = args.output
    read = lambda name: json.loads((output/name).read_text(encoding="utf-8"))
    protocol, result, selection = read("protocol.json"), read("results.json"), read("selection.json")
    candidates, manifest, hashes = read("candidates.json"), read("data_manifest.json"), read("code_hashes.json")
    expected_paths = {"research_quant70.py": ROOT/"scripts/research_quant70.py",
                      "quant70_signals.py": ROOT/"scripts/quant70_signals.py",
                      "research_strict_rr_portfolio.py": ROOT/"scripts/research_strict_rr_portfolio.py",
                      "data.py": ROOT/"src/forextester_backtest/data.py"}
    require(set(hashes) == set(expected_paths), "source manifest files")
    for name, path in expected_paths.items():
        require(hashlib.sha256(path.read_bytes()).hexdigest() == hashes[name], f"source drift: {name}")
    frozen = ROOT/"docs/quant_organization/experiments/quant70_20260908/protocol.json"
    require(json.loads(frozen.read_text(encoding="utf-8")) == protocol, "protocol drift")
    names = {c["name"] for c in candidates}
    require(len(candidates) == len(names) == protocol["candidate_budget"] == 24, "candidate count")
    records = {r["candidate"]["name"]: r for r in result["records"]}
    require(len(records) == len(result["records"]) == 25, "duplicate or missing record")
    require(set(records) == names | {"baseline_htf_hourly"}, "candidate identities")
    for candidate in candidates:
        require(records[candidate["name"]]["candidate"] == candidate, "candidate drift")
    # This verifier deliberately supports the completed no-selection outcome only.
    require(result["status"] == "REJECTED" and result["selected"] is None, "unexpected selected run")
    require(result["candidate_count"] == 24 and not result["confirmation_evaluated"], "unexpected confirmation state")
    require(not result["live_approved"], "unexpected live approval")
    periods = {p: tuple(datetime.fromisoformat(t) for t in protocol["periods"][p]) for p in ("train", "validation")}
    months = {"train": 108, "validation": 48}
    require(len(manifest) == len(protocol["symbols"]) == 11, "unexpected history loads")
    for key, item in manifest.items():
        require(key.endswith(":2023-01-01"), "confirmation data was prepared")
        require(datetime.fromisoformat(item["end"]) < datetime(2023, 1, 1), "prepared after selection boundary")
        require(float(item["metadata"]["values"]["CommPerLot"]) == 0, "unverified nonzero commission")

    groups = defaultdict(list)
    prior_exit = {}
    reasons = Counter()
    n = 0
    with (output/"trades.jsonl").open(encoding="utf-8") as file:
        for n, line in enumerate(file, 1):
            t = json.loads(line)
            key = (t["candidate"], t["period"], t["symbol"])
            require(key[0] in records and key[1] in periods and key[2] in protocol["symbols"], f"unknown trade key {n}")
            signal, entry, exit_time = [datetime.fromisoformat(t[field]) for field in ("signal_time", "entry_time", "exit_time")]
            start, end = periods[key[1]]
            require(start <= signal < entry <= exit_time < end, f"split crossing or ordering {n}")
            require(entry-signal == timedelta(minutes=15), f"nonadjacent entry {n}")
            require(all(v.minute%15 == 0 and v.second == v.microsecond == 0 for v in (signal, entry, exit_time)), f"unaligned trade {n}")
            require(key not in prior_exit or signal > prior_exit[key], f"overlapping trade or reused signal {n}")
            prior_exit[key] = exit_time
            d = t["direction"]
            require(d in (-1, 1), f"direction {n}")
            risk = d*(t["entry"]-t["stop"])
            require(risk > 0 and all(math.isfinite(t[f]) for f in ("entry", "stop", "target", "exit", "net_r")), f"invalid price {n}")
            close(d*(t["target"]-t["entry"]), risk, f"RR1 {n}")
            close(t["net_r"], d*(t["exit"]-t["entry"])/risk, f"net R {n}")
            require(t["reason"] in {"stop", "target", "stop_gap", "target_gap", "period_end"}, f"reason {n}")
            pip = 0.01 if key[2].endswith("JPY") else 0.0001
            slip = protocol["execution"]["slippage_pips_each_side"]*pip
            if t["reason"] in ("target", "target_gap"):
                close(t["exit"], t["target"]-d*slip, f"TP cost {n}")
            if t["reason"] == "stop":
                close(t["exit"], t["stop"]-d*slip, f"SL cost {n}")
            if t["reason"] == "period_end":
                require(exit_time >= end-timedelta(days=7), f"premature period close {n}")
            if t["reason"] == "stop_gap":
                require(t["net_r"] <= -1, f"nonadverse stop gap {n}")
            groups[key].append((t["exit_time"], key[2], t["entry_time"], t["net_r"], t["reason"], t["ambiguous"]))
            reasons[t["reason"]] += 1

    independent = {}
    eligible = []
    for name, record in records.items():
        require(set(record["periods"]) == set(periods), f"unexpected evaluated periods {name}")
        independent[name] = {"periods": {}, "pairs": {}}
        passed = True
        for period in periods:
            require(set(record["pairs"][period]) == set(protocol["symbols"]), "missing pair summary")
            pair_stats = {}
            combined = []
            for symbol in protocol["symbols"]:
                rows = groups[(name, period, symbol)]
                require(sum(t[4] == "period_end" for t in rows) <= 1, "multiple final closes")
                combined.extend(rows)
                summary = summarize(rows, months[period])
                for field, stored in record["pairs"][period][symbol].items():
                    close(stored, summary[field], f"pair {name}/{period}/{symbol}/{field}")
                pair_stats[symbol] = summary
            summary = summarize(combined, months[period])
            for field, stored in record["periods"][period].items():
                close(stored, summary[field], f"aggregate {name}/{period}/{field}")
            passes = qualifies(summary, pair_stats, period, protocol["gates"])
            require(passes == (not record["rejections"][period]), f"gate disagreement {name}/{period}")
            passed &= passes
            independent[name]["periods"][period] = summary
            independent[name]["pairs"][period] = pair_stats
        if passed and name in names:
            eligible.append(name)
    require(not eligible and result["qualified_count"] == selection["qualified"] == 0, "selection discrepancy")
    require(selection["selected"] is None and selection["basis"] == "train and validation only", "selection basis")
    verification = {"status": "VERIFIED_REJECTED", "source_hashes_match": True,
                    "trade_rows": n, "candidate_count": 24, "baseline_count": 1,
                    "qualified_count": 0, "confirmation_evaluated": False,
                    "reason_counts": dict(reasons), "records": independent,
                    "scope": "Independent saved-trade reconciliation; no second OHLC backtest or tick-order certification."}
    (output/"independent_verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in verification.items() if k != "records"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
