"""Independent M5 scenario replay; frozen prior validator handles accounting."""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from scripts import validate_fxspace_proxy_20261011 as reference

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "agent_runs/fxspace_m5_20261011"
DOC = ROOT / "docs/quant_organization/experiments/fxspace_m5_20261011"
ARMS = ("m15_pullback", "m15_direct", "solo_pullback", "solo_direct")
BASELINES = {"m15_pullback": "m15_direct", "solo_pullback": "solo_direct"}


def monthly(rows, start, end, curve=None):
    """Same frozen accounting; calculate each month cutoff once, not per curve point."""
    cursor = datetime.fromtimestamp(start, timezone.utc).replace(day=1)
    result, prior = [], 1_000_000.
    while cursor.timestamp() < end:
        month = cursor.strftime("%Y-%m")
        nxt = cursor.replace(year=cursor.year+1, month=1) if cursor.month == 12 else cursor.replace(month=cursor.month+1)
        subset = [r for r in rows if reference.stamp(r["exit_time"]-(0 if "gap" in r["reason"] else 1))[:7] == month]
        summary = reference.metrics(subset)
        keys = ("trades", "net_r", "mean_net_r", "pf", "wins", "max_closed_trade_dd_r", "incomplete_exposed_trades")
        row = dict(month=month, **{k: summary[k] for k in keys})
        if curve is not None:
            cutoff = nxt.timestamp()
            values = [eq for time, eq in curve if time <= cutoff]
            equity = values[-1] if values else prior
            ret = equity/prior-1 if prior > 0 else None
            row.update(pnl_yen=equity-prior, equity_yen=equity, monthly_return=ret,
                       reaches_5_percent=ret is not None and ret >= .05)
            prior = equity
        result.append(row)
        cursor = nxt
    return result


def events_from_ohlc(data, tick, start, end):
    grouped = reference.aggregate(data, 900)
    pointer = 0
    m5 = reference.IndependentFrame(300, tick)
    m15 = reference.IndependentFrame(900, tick)
    pending = {"m15": None, "solo": None}
    used = {context: set() for context in pending}
    output = {arm: {} for arm in ARMS}
    times, bars, valid = data["times"], data["prices"], data["complete"]
    for i in range(len(times)):
        if times[i] >= end:
            break
        now = int(times[i])+300
        previous_direction = m5.trend
        m5.consume(int(times[i]), bars[i], bool(valid[i]))
        while pointer < len(grouped) and grouped[pointer][0]+900 <= now:
            stamp, price, complete = grouped[pointer]
            m15.consume(stamp, price, complete)
            pointer += 1
        if times[i] < start:
            continue
        op, high, low, close = bars[i]
        continuous = bool(i and times[i]-times[i-1] == 300 and valid[i] and valid[i-1])
        for context in ("m15", "solo"):
            scenario = pending[context]
            if scenario is not None:
                d = scenario["side"]
                cancelled = (not continuous or i-scenario["created_i"] > 12 or
                             (low <= scenario["stop"] if d == 1 else high >= scenario["stop"]) or
                             (high >= scenario["target"] if d == 1 else low <= scenario["target"]) or
                             m5.trend == -d or (context == "m15" and m15.trend != d))
                if cancelled:
                    pending[context] = None
                elif d*(close-op) < 0:
                    scenario["counter"] += 1
                elif d*(close-op) > 0 and scenario["counter"] >= 2:
                    if (close > bars[i-1, 1] if d == 1 else close < bars[i-1, 2]):
                        output[context+"_pullback"][i] = dict(scenario)
                    pending[context] = None
                else:
                    scenario["counter"] = 0
                continue
            d = m5.trend
            if not continuous or not d or previous_direction != -d or not math.isfinite(m5.atr) or m5.atr <= 0:
                continue
            if context == "m15" and m15.trend != d:
                continue
            pivots = m5.lows if d == 1 else m5.highs
            if not pivots:
                continue
            support = pivots[-1]
            support_key = (d, support["known"])
            if support_key in used[context]:
                continue
            candidates = [dict(x, strength=1) for x in m5.lines]+[dict(x, strength=2) for x in m15.lines]
            candidates = sorted((x for x in candidates if d*(x["price"]-close) > 0), key=lambda x: x["price"])
            band = .1*m5.atr
            clusters = []
            for line in candidates:
                if clusters and line["price"]-clusters[-1][-1]["price"] <= band:
                    clusters[-1].append(line)
                else:
                    clusters.append([line])
            if not clusters:
                continue
            representatives = []
            for cluster in clusters:
                representative = dict(sorted(cluster, key=lambda x: (-x["known"], -x["strength"]))[0])
                representative["strength"] = max(x["strength"] for x in cluster)
                representatives.append(representative)
            obstacle = min(representatives, key=lambda x: d*(x["price"]-close))
            offset = max(tick, band)
            def rounded(value):
                return (math.floor(value/tick+1e-9) if d == 1 else math.ceil(value/tick-1e-9))*tick
            stop = rounded(support["price"]-d*offset)
            target = rounded(obstacle["price"]-d*offset)
            if d*(close-stop) <= 0 or d*(target-close) <= 0:
                continue
            same_side = m15.highs if d == 1 else m15.lows
            acceleration = 0
            if len(same_side) == 3:
                delta = abs(same_side[2]["price"]-same_side[1]["price"])-abs(same_side[1]["price"]-same_side[0]["price"])
                acceleration = 1 if delta > tick else -1 if delta < -tick else 0
            scenario = dict(side=d, stop=stop, target=target, created_i=i, scenario_time=now,
                            support_time=support["known"], threshold=(m5.highs if d == 1 else m5.lows)[-1]["price"],
                            counter=0, acceleration=acceleration, line_strength=obstacle["strength"])
            used[context].add(support_key)
            output[context+"_direct"][i] = dict(scenario)
            pending[context] = scenario
    return output


def run(phase):
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    folder = OUT/phase
    actual = json.loads((folder/"results.json").read_text(encoding="utf-8"))
    manifest = json.loads((folder/"run_manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("completed_utc"), "Research incomplete"
    assert reference.digest(folder/"results.json") == manifest["results_sha256"]
    for path, sha in manifest["files"].items():
        assert reference.digest(ROOT/path) == sha, f"Frozen source drift: {path}"
    baseline = protocol["frequency_baseline"]
    assert reference.digest(ROOT/baseline["source"]) == baseline["sha256"]
    start, end = map(reference.epoch, protocol["periods"][phase])
    configs = sorted({(r["arm"], r["rr"]) for r in actual["records"]})
    counts = dict(input_m5_rows=0, signal_observations=0, trade_observations=0, prefix_future_block_checks=0)
    pooled_rows, records, accounts = {}, [], {}
    for symbol in protocol["symbols"]:
        path = ROOT/protocol["cache_directory"]/f"{symbol}_m5.npz"
        assert reference.digest(path) == protocol["input_sha256"][symbol]
        with np.load(path, allow_pickle=False) as saved:
            data = {k: saved[k][saved["times"] < end] for k in saved.files}
        counts["input_m5_rows"] += len(data["times"])
        costs = protocol["cost_and_fill_model"]
        normal_cost = costs["round_trip_pips"][symbol]*costs["pip"][symbol]
        events = events_from_ohlc(data, costs["tick"][symbol], start, end)
        with np.load(folder/f"{symbol}_signals.npz", allow_pickle=False) as archive:
            saved = {key: archive[key] for key in archive.files}
            assert np.array_equal(saved["times"], data["times"])
            mapping = {"sides": "side", "stops": "stop", "targets": "target", "thresholds": "threshold",
                       "scenario_times": "scenario_time", "support_times": "support_time", "acceleration": "acceleration", "strength": "line_strength"}
            for a, arm in enumerate(ARMS):
                indices = np.flatnonzero(saved["sides"][a])
                assert list(indices) == list(events[arm]), (symbol, arm, "signal indices")
                for i in indices:
                    for source, own in mapping.items():
                        reference.compare(saved[source][a, i], events[arm][i][own], f"{symbol}.{arm}.{i}.{own}")
                counts["signal_observations"] += len(indices)
        for length in (10_001, 20_002, 30_007):
            if length >= len(data["times"]):
                continue
            prefix = events_from_ohlc({k: value[:length] for k, value in data.items()}, costs["tick"][symbol], start, end)
            for arm in ARMS:
                expected = {i: row for i, row in events[arm].items() if i < length}
                assert list(prefix[arm]) == list(expected), (symbol, arm, length, "prefix")
                for i, row in expected.items():
                    reference.compare(prefix[arm][i], row, f"prefix.{symbol}.{arm}.{length}.{i}")
            counts["prefix_future_block_checks"] += 1
        for arm, rr in configs:
            for multiplier in (1, 2):
                key = f"{arm}_rr{rr:g}_cost{multiplier}"
                rows, _, _, skipped = reference.replay(data, events[arm], rr, normal_cost*multiplier, normal_cost, start, end)
                with (folder/f"{symbol}_{key}.csv").open(encoding="utf-8", newline="") as stream:
                    reference.compare(list(csv.DictReader(stream)), rows, f"{symbol}.{key}.csv")
                counts["trade_observations"] += len(rows)
                pooled_rows.setdefault(key, []).extend(dict(symbol=symbol, **r) for r in rows)
                record = dict(symbol=symbol, arm=arm, rr=rr, cost_multiplier=multiplier, **reference.metrics(rows),
                              skipped=skipped, monthly=monthly(rows, start, end),
                              annual=[dict(year=y, **reference.metrics([r for r in rows if int(reference.stamp(r["exit_time"]-(0 if "gap" in r["reason"] else 1))[:4]) == y]))
                                      for y in range(int(reference.stamp(start)[:4]), int(reference.stamp(end)[:4]))])
                stored = next(r for r in actual["records"] if (r["symbol"], r["arm"], r["rr"], r["cost_multiplier"]) == (symbol, arm, rr, multiplier))
                reference.compare(stored, record, f"{symbol}.{key}.record")
                records.append(record)
                with np.load(folder/f"{symbol}_{key}_closed_r_curve.npz") as curve:
                    assert np.array_equal(curve["times"], [r["exit_time"] for r in rows])
                    np.testing.assert_allclose(curve["equity_r"], np.cumsum([r["net_r"] for r in rows]), rtol=1e-9, atol=1e-7)
                if symbol == "USDJPY":
                    cash_rows, cash_curve, account, _ = reference.replay(data, events[arm], rr, normal_cost*multiplier, normal_cost, start, end, True)
                    with (folder/f"{symbol}_{key}_cash.csv").open(encoding="utf-8", newline="") as stream:
                        reference.compare(list(csv.DictReader(stream)), cash_rows, f"{key}.cash_csv")
                    counts["trade_observations"] += len(cash_rows)
                    with np.load(folder/f"{symbol}_{key}_cash_curve.npz") as curve:
                        np.testing.assert_allclose(curve["curve"], cash_curve, rtol=1e-9, atol=1e-7)
                    accounts[key] = dict(**account, **reference.metrics(cash_rows), monthly=monthly(cash_rows, start, end, cash_curve))
                    reference.compare(actual["usdjpy_accounts"][key], accounts[key], f"{key}.account")
        print(f"INDEPENDENT_REPLAY_OK {symbol}", flush=True)
    pooled = {}
    for key, rows in pooled_rows.items():
        rows.sort(key=lambda r: (r["exit_time"], r["symbol"], r["entry_time"]))
        pooled[key] = reference.metrics(rows)
    reference.compare(actual["pooled_equal_r"], pooled, "pooled")
    screens = []
    months = (datetime.fromtimestamp(end, timezone.utc).year-datetime.fromtimestamp(start, timezone.utc).year)*12
    for item in actual["screens"]:
        arm, rr = item["arm"], item["rr"]
        key = f"{arm}_rr{rr:g}"
        checked = reference.independent_screen(pooled[key+"_cost1"], pooled[key+"_cost2"],
                  [r for r in records if (r["arm"], r["rr"], r["cost_multiplier"]) == (arm, rr, 1)],
                  accounts[key+"_cost1"], pooled[f"{BASELINES[arm]}_rr{rr:g}_cost1"], protocol["acceptance_gates"])
        checked["checks"]["frequency_above_prior_training_rate"] = pooled[key+"_cost1"]["trades"]/months > baseline["trades_by_rr"][f"{rr:g}"]/baseline["baseline_months"]
        checked["passes"] = all(checked["checks"].values())
        checked["frequency_comparison"] = dict(new_monthly=pooled[key+"_cost1"]["trades"]/months,
                  old_training_monthly=baseline["trades_by_rr"][f"{rr:g}"]/baseline["baseline_months"],
                  same_period_comparison=phase == "training")
        computed = dict(arm=arm, rr=rr, **checked)
        reference.compare(item, computed, f"{key}.screen")
        screens.append(computed)
    passing = [s for s in screens if s["passes"]]
    passing.sort(key=lambda s: (-pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["pf"],
                               -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["mean_net_r"],
                               -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["trades"], s["arm"], s["rr"]))
    selected = {k: passing[0][k] for k in ("arm", "rr")} if passing else None
    if phase not in ("training", "validation"):
        previous_phase = "validation" if phase == "final_confirmation" else "final_confirmation"
        previous = json.loads((OUT/previous_phase/"results.json").read_text(encoding="utf-8"))
        selected = previous["selected"]
        assert not actual["screens"], "Descriptive phase must not apply a new selection gate"
    reference.compare(actual["selected"], selected, "selected")
    evidence = dict(status="ALL_MATCH", phase=phase, selected=selected, **counts,
                    compared_scalar_values=reference.COMPARISONS, validator_sha256=reference.digest(__file__),
                    inherited_validator_sha256=reference.digest(reference.__file__),
                    monthly_equivalence_evidence_sha256=reference.digest(folder/"independent_monthly_equivalence.json"),
                    result_sha256=reference.digest(folder/"results.json"),
                    completed_utc=datetime.now(timezone.utc).isoformat(), screens=screens)
    (folder/"independent_validation.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="training")
    run(parser.parse_args().phase)
