"""Frozen day/hour entry gates around the unchanged 20261003 pullback signals.

Source timestamps are naive source-clock seconds, never asserted to be UTC.
The filtered execution loop is adapted from research_yosuga_channel.simulate;
its brackets, cost accounting and occupancy order are preserved. Only new-entry
gates are added. This experiment has no adoption or live-order authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

try:
    from . import research_yosuga_channel as base
except ImportError:
    import research_yosuga_channel as base

ROOT = Path(__file__).resolve().parents[1]
ID = "yosuga_daily_time_20261006"
ARMS = ("baseline", "daily", "hourly", "combined")
SYMBOLS = ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "AUDJPY", "NZDJPY"]
DAILY_RULE = dict(previous_day="previous_calendar_day", min_observed_bars=270,
                  min_complete_bars=260, latest_first_second=1800,
                  earliest_last_second=84300, max_gap_seconds=1800,
                  min_efficiency=0.3, reject_entry_date_change=True)
HOURLY_RULE = dict(bars=12, require_complete=True, min_efficiency=0.3,
                   max_cost_risk=0.2, cost_gate_at=["signal_close", "next_open"])
SELECTION_RULE = dict(period="2020_2022", min_trades=100, min_profit_factor=1.1,
                      min_positive_pairs=4, require_positive_mean=True,
                      require_positive_loo=True, require_positive_stress=True,
                      require_positive_ci=True, tie_break=["mean_net_r_desc", "arm_order"],
                      selectable_arms=list(ARMS[1:]), later_results_do_not_change_selection=True)
PERIODS = [("2020_2022", "2020-01-01", "2023-01-01"),
           ("2023_2024", "2023-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01")]


def validate_protocol(protocol):
    """Reject threshold, baseline, calendar or selection drift before reading data."""
    expected = dict(experiment_id=ID, status="SPEC_FROZEN", candidate_budget=4,
                    arms=list(ARMS), symbols=SYMBOLS, baseline_arm="pullback_rr1",
                    source_clock="naive_source_clock_00:00", daily_rule=DAILY_RULE,
                    hourly_rule=HOURLY_RULE, selection_rule=SELECTION_RULE,
                    selection_order=list(ARMS[1:]), cost_multipliers=[1., 1.5])
    for key, value in expected.items():
        if protocol.get(key) != value:
            raise ValueError(f"Protocol differs from fixed specification: {key}")
    if [(p["label"], p["start"], p["end"]) for p in protocol["periods"]] != PERIODS:
        raise ValueError("Fixed periods differ")
    if protocol["selection_gates"]["bootstrap_seed"] != 20261006 or protocol["selection_gates"]["bootstrap_draws"] != 5000:
        raise ValueError("Fixed bootstrap differs")
    old = json.loads((base.DOC/"protocol.json").read_text(encoding="utf-8"))
    for key in ("structural_rules", "entry_rules", "spread_pips", "data_manifest", "cache_directory"):
        if protocol[key] != old[key]:
            raise ValueError(f"Frozen baseline changed: {key}")
    if protocol["exit_rules"]["reward_risk_ratio"] != 1. or protocol["exit_rules"]["full_exit"] is not True:
        raise ValueError("Full RR1 exit required")
    if base.digest(base.__file__) != old["frozen_identifiers"]["scripts/research_yosuga_channel.py"]:
        raise ValueError("Frozen baseline source hash changed")
    for relative_path, expected_hash in protocol.get("frozen_identifiers", {}).items():
        if base.digest(ROOT/relative_path) != expected_hash:
            raise ValueError(f"Experiment frozen hash differs: {relative_path}")


def context(times, prices, complete):
    """Daily summaries are usable only by a following calendar day's signals.

    The hourly arrays end at the current M5 close. No centered rolling values,
    future day quality, future OHLC or next-open prices enter these features.
    """
    base.validate_prices(times, prices)
    complete = np.asarray(complete, dtype=bool)
    if complete.shape != times.shape:
        raise ValueError("Completeness mask shape differs")
    day_ids = times//86400
    starts = np.r_[0, np.flatnonzero(np.diff(day_ids))+1]
    ends = np.r_[starts[1:], len(times)]
    days = {}
    for a, b in zip(starts, ends):
        day = int(day_ids[a])
        op, close = float(prices[a, 0]), float(prices[b-1, 3])
        span = float(prices[a:b, 1].max()-prices[a:b, 2].min())
        row = dict(day=day, observed_bars=int(b-a), complete_bars=int(complete[a:b].sum()),
                   first_second=int(times[a] % 86400), last_second=int(times[b-1] % 86400),
                   max_gap_seconds=int(np.diff(times[a:b]).max()) if b-a > 1 else 0,
                   direction=int(np.sign(close-op)), efficiency=abs(close-op)/span if span > 0 else 0.)
        row["quality_ok"] = bool(row["observed_bars"] >= 270 and row["complete_bars"] >= 260
                                 and row["first_second"] <= 1800 and row["last_second"] >= 84300
                                 and row["max_gap_seconds"] <= 1800)
        days[day] = row
    n = len(times)
    quality = np.zeros(n, dtype=bool)
    efficiency = np.zeros(n)
    direction = np.zeros(n, dtype=np.int8)
    if n >= 12:
        window = np.lib.stride_tricks.sliding_window_view
        quality[11:] = (times[11:]-times[:-11] == 3300) & window(complete, 12).all(axis=1)
        span = window(prices[:, 1], 12).max(axis=1)-window(prices[:, 2], 12).min(axis=1)
        move = prices[11:, 3]-prices[:-11, 0]
        efficiency[11:] = np.divide(abs(move), span, out=np.zeros_like(move), where=span > 0)
        direction[11:] = np.sign(move).astype(np.int8)
    return dict(days=days, hour_quality=quality, hour_efficiency=efficiency, hour_direction=direction)


def signal_gate(times, prices, signal, ctx, pip, cost, arm):
    """Decision and evidence available at this signal close only."""
    i, side = signal["index"], signal["side"]
    audit = dict(gate_signal_close=int(times[i]+300))
    if arm in ("daily", "combined"):
        if times[i]//86400 != (times[i]+300)//86400:
            return "daily_entry_date_change", audit
        previous_day = int((times[i]+300)//86400)-1
        day = ctx["days"].get(previous_day)
        audit["daily_previous_day"] = previous_day
        if day is None:
            return "daily_missing_previous_day", audit
        audit["daily_evidence"] = day
        if not day["quality_ok"]:
            return "daily_quality", audit
        if day["efficiency"] < .3:
            return "daily_efficiency", audit
        if day["direction"] != side:
            return "daily_direction", audit
    if arm in ("hourly", "combined"):
        audit.update(hour_quality=bool(ctx["hour_quality"][i]),
                     hour_efficiency=float(ctx["hour_efficiency"][i]),
                     hour_direction=int(ctx["hour_direction"][i]))
        if not ctx["hour_quality"][i]:
            return "hourly_quality", audit
        if ctx["hour_efficiency"][i] < .3:
            return "hourly_efficiency", audit
        if ctx["hour_direction"][i] != side:
            return "hourly_direction", audit
        risk_pips = side*(prices[i, 3]-signal["stop"])/pip
        ratio = cost/risk_pips if risk_pips > 0 else None
        audit["signal_cost_risk"] = float(ratio) if ratio is not None else None
        if ratio is None or ratio > .2+1e-12:
            return "signal_cost_risk", audit
    return "allowed", audit


def simulate(times, prices, candidates, turns, pip, tick, arm, cost, start, end, complete, ctx):
    """Execute the unchanged RR1 brackets, adding separate close/open entry gates."""
    if arm not in ARMS or pip <= 0 or tick <= 0 or cost < 0 or start >= end:
        raise ValueError("Invalid simulation arguments")
    if arm == "baseline":
        sim = base.simulate(times, prices, candidates, turns, pip, tick, "pullback_rr1", cost, start, end, complete)
    else:
        first, last = map(int, np.searchsorted(times, [start, end]))
        if first == last:
            raise ValueError("Empty period")
        selected = [s for s in candidates if start <= times[s["setup_index"]] and start <= times[s["index"]] < end]
        by_index = {s["index"]: s for s in selected}
        if len(by_index) != len(selected):
            raise ValueError("Duplicate candidate")
        mtm = np.empty((last-first, 2))
        trades, ledger = [], []
        p = pending = None
        realized = 0.
        for offset, i in enumerate(range(first, last)):
            op, hi, lo, cl = map(float, prices[i])
            if pending is not None:
                s, pending = pending, None
                risk = s["side"]*(op-s["stop"])
                room = s["side"]*(s["line_target"]-op)
                reason = ("entry_gap" if times[i]-times[s["index"]] != 300 else
                          "entry_invalid_risk" if risk < tick-1e-10 else
                          "entry_line_room" if room+1e-10 < risk else "entered")
                if reason == "entered" and arm in ("daily", "combined") and times[i]//86400 != times[s["index"]]//86400:
                    reason = "daily_entry_date_change"
                if reason == "entered" and arm in ("hourly", "combined"):
                    s["entry_cost_risk"] = cost/(risk/pip)
                    if s["entry_cost_risk"] > .2+1e-12:
                        reason = "entry_cost_risk"
                s["status"] = reason
                if reason == "entered":
                    p = dict(s, entry_index=i, entry_time=int(times[i]), entry=op, risk_pips=risk/pip,
                             incomplete_m5_held=0, target=op+s["side"]*risk)
            if p is not None:
                p["incomplete_m5_held"] += int(not complete[i])
                fill = base.exit_fill(p["side"], op, hi, lo, p["stop"], p["target"])
                if fill is None and i == last-1:
                    fill = cl, "period_end"
                if fill is not None:
                    price, reason = fill
                    exit_time = int(times[i]+300 if reason in ("period_end", "stop", "target") else times[i])
                    gross = p["side"]*(price-p["entry"])/pip
                    net = gross-cost
                    carry = max(0, exit_time-p["entry_time"])/86400
                    trades.append(dict(p, exit_index=i, exit_time=exit_time, exit=float(price), exit_reason=reason,
                                       gross_pips=gross, net_pips=net, gross_r=gross/p["risk_pips"],
                                       net_r=net/p["risk_pips"], cost_pips=cost, carry_penalty_pips=carry))
                    realized += net/p["risk_pips"]
                    p = None
            open_r = (p["side"]*(cl-p["entry"])/pip-cost)/p["risk_pips"] if p is not None else 0.
            mtm[offset] = times[i]+300, realized+open_r
            if i in by_index:
                reason, evidence = signal_gate(times, prices, by_index[i], ctx, pip, cost, arm)
                status = ("occupied" if p is not None else "pending_period_end" if i == last-1
                          else "pending" if reason == "allowed" else reason)
                item = dict(by_index[i], **evidence, signal_gate=reason, status=status)
                ledger.append(item)
                if status == "pending":
                    pending = item
        summary = base.trade_metrics(trades)
        summary["trades_exposed_to_incomplete_m5"] = sum(t["incomplete_m5_held"] > 0 for t in trades)
        equity = mtm[:, 1]
        summary["bar_close_mtm_drawdown_r"] = float(np.max(np.maximum.accumulate(np.maximum(equity, 0))-equity))
        summary["candidate_statuses"] = dict(Counter(s["status"] for s in ledger))
        sim = dict(trades=trades, ledger=ledger, summary=summary, mtm=mtm)
    observed = np.unique(times[(times >= start) & (times < end)]//86400)
    traded = sorted({t["entry_time"]//86400 for t in sim["trades"]})
    sim["summary"].update(observed_days=len(observed), trading_days=len(traded),
                          trading_day_fraction=len(traded)/len(observed) if len(observed) else None,
                          observed_day_ids=observed.astype(int).tolist(), trading_day_ids=traded,
                          signal_gate_reasons=dict(Counter(s.get("signal_gate", "allowed") for s in sim["ledger"])))
    return sim


def bootstrap_months(trades, start, end):
    """Same shared-month estimator as the baseline, with this experiment's seed."""
    months = np.arange(np.datetime64(start, "s").astype("datetime64[M]").astype(int),
                       np.datetime64(end, "s").astype("datetime64[M]").astype(int))
    totals, counts = np.zeros(len(months)), np.zeros(len(months))
    for trade in trades:
        month = np.datetime64(trade["entry_time"], "s").astype("datetime64[M]").astype(int)
        j = int(month-months[0])
        totals[j] += trade["net_r"]
        counts[j] += 1
    draws = np.random.default_rng(20261006).integers(0, len(months), size=(5000, len(months)))
    denominator = counts[draws].sum(axis=1)
    estimates = totals[draws].sum(axis=1)[denominator > 0]/denominator[denominator > 0]
    return dict(ci95_mean_r=np.quantile(estimates, [.025, .975]).tolist() if len(estimates) else [None, None],
                monthly_net_r=totals.tolist(), monthly_trades=counts.astype(int).tolist(),
                first_month=str(np.datetime64(start, "s").astype("datetime64[M]")), draws=5000, seed=20261006)


def gates(normal, stress):
    return dict(n100=normal["trades"] >= 100,
                pf110=normal["profit_factor_r"] is not None and normal["profit_factor_r"] >= 1.1,
                mean_positive=normal["mean_net_r"] is not None and normal["mean_net_r"] > 0,
                ci_positive=normal["ci95_mean_r"][0] is not None and normal["ci95_mean_r"][0] > 0,
                positive_pairs4=normal["positive_pairs"] >= 4,
                leave_one_positive=normal["leave_one_pair_min_net_r"] > 0,
                stress_positive=stress["net_r"] > 0)


def select_training(totals):
    """Later rows cannot enter ranking or cause fallback selection."""
    checks, passing = {}, []
    for arm in ARMS[1:]:
        normal = next(r for r in totals if (r["period"], r["arm"], r["cost_multiplier"]) == ("2020_2022", arm, 1.))
        stress = next(r for r in totals if (r["period"], r["arm"], r["cost_multiplier"]) == ("2020_2022", arm, 1.5))
        checks[arm] = gates(normal, stress)
        if all(checks[arm].values()):
            passing.append((normal["mean_net_r"], -ARMS.index(arm), arm))
    return dict(selected=max(passing)[2] if passing else None, checks=checks,
                based_only_on="2020_2022", later_results_change_selection=False)


def run(protocol_path, output):
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    validate_protocol(protocol)
    if output.exists():
        raise FileExistsError("Preserve existing outputs; choose a fresh output directory")
    entries = json.loads((ROOT/protocol["data_manifest"]).read_text(encoding="utf-8"))
    by_symbol = {e["symbol"]: e for e in entries}
    mask_dir = ROOT/protocol["complete_mask_directory"]
    mask_manifest = json.loads((mask_dir/"run_manifest.json").read_text(encoding="utf-8"))
    mask_entries = {e["symbol"]: e for e in mask_manifest["inputs"]}
    output.mkdir(parents=True)
    base.dump(output/"protocol.json", protocol)
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), protocol_sha256=base.digest(protocol_path),
                    code_sha256=base.digest(__file__), tests_sha256=base.digest(ROOT/"tests/test_yosuga_daily_time.py"),
                    baseline_code_sha256=base.digest(base.__file__), data_manifest_sha256=base.digest(ROOT/protocol["data_manifest"]),
                    mask_manifest_sha256=base.digest(mask_dir/"run_manifest.json"), inputs=[])
    base.dump(output/"run_manifest.json", manifest)
    summaries, totals, datasets = [], [], {}
    for symbol in SYMBOLS:
        entry = by_symbol[symbol]
        cache = ROOT/protocol["cache_directory"]/f"{symbol}_features.npz"
        mask_path = mask_dir/f"{symbol}_complete_m5.npz"
        source_mask = mask_entries[symbol]
        if (base.digest(cache) != entry["cache_sha256"] or base.digest(mask_path) != source_mask["mask_sha256"]
                or source_mask["sha256"] != entry["cache_sha256"] or source_mask["raw_sha256"] != entry["raw_sha256"]):
            raise ValueError(f"Cache or saved M1 completeness identity mismatch: {symbol}")
        with np.load(cache, allow_pickle=False) as z:
            times, prices = z["times"].copy(), z["features"][:, :4].copy()
        with np.load(mask_path, allow_pickle=False) as z:
            complete = z["complete"].copy()
        ctx = context(times, prices, complete)
        signal_book, turns, stages = base.signals(times, prices, entry["tick"], complete)
        candidates = signal_book["pullback_rr1"]
        base.dump(output/f"{symbol}_signals.json", candidates)
        base.dump(output/f"{symbol}_days.json", list(ctx["days"].values()))
        base.dump(output/f"{symbol}_stages.json", stages)
        datasets[symbol] = (entry, times, prices, complete, ctx, candidates, turns)
        manifest["inputs"].append(dict(symbol=symbol, cache_sha256=entry["cache_sha256"],
                                       raw_sha256=entry["raw_sha256"], mask_sha256=source_mask["mask_sha256"], bars=len(times)))
        base.dump(output/"run_manifest.json", manifest)
        print(f"PREPARED {symbol}", flush=True)
    selection = None
    for period in protocol["periods"]:
        # Replay no later returns before the training-only selection is saved.
        if period["label"] != "2020_2022" and selection is None:
            raise RuntimeError("Training selection must be saved before later replay")
        start, end = [int(np.datetime64(period[k], "s").astype(int)) for k in ("start", "end")]
        books, curves = {}, {}
        for symbol in SYMBOLS:
            entry, times, prices, complete, ctx, candidates, turns = datasets[symbol]
            for arm in ARMS:
                for multiplier in protocol["cost_multipliers"]:
                    cost = protocol["spread_pips"][symbol]*multiplier
                    sim = simulate(times, prices, candidates, turns, entry["pip"], entry["tick"], arm, cost, start, end, complete, ctx)
                    prefix = f"{symbol}_{period['label']}_{arm}_costx{multiplier:g}"
                    base.dump(output/f"{prefix}_trades.json", sim["trades"])
                    base.dump(output/f"{prefix}_ledger.json", sim["ledger"])
                    np.savez_compressed(output/f"{prefix}_mtm.npz", mtm=sim["mtm"])
                    summaries.append(dict(symbol=symbol, period=period["label"], arm=arm, cost_multiplier=multiplier,
                                          cost_pips=cost, **sim["summary"]))
                    key = (period["label"], arm, multiplier)
                    books.setdefault(key, []).extend(dict(symbol=symbol, **t) for t in sim["trades"])
                    curves.setdefault(key, []).append(sim["mtm"])
            print(f"COMPLETE {period['label']} {symbol}", flush=True)
        for arm in ARMS:
            for multiplier in protocol["cost_multipliers"]:
                key = (period["label"], arm, multiplier)
                rows = [r for r in summaries if (r["period"], r["arm"], r["cost_multiplier"]) == key]
                combined = base.combine_curves(curves[key])
                np.savez_compressed(output/f"{period['label']}_{arm}_costx{multiplier:g}_combined_mtm.npz", mtm=combined)
                metrics = base.trade_metrics(books[key])
                metrics.update(bootstrap_months(books[key], start, end))
                equity = combined[:, 1]
                observed = set().union(*(set(r["observed_day_ids"]) for r in rows))
                traded = set().union(*(set(r["trading_day_ids"]) for r in rows))
                metrics.update(bar_close_mtm_drawdown_r=float(np.max(np.maximum.accumulate(np.maximum(equity, 0))-equity)),
                               positive_pairs=sum(r["net_r"] > 0 for r in rows),
                               leave_one_pair_min_net_r=min(metrics["net_r"]-r["net_r"] for r in rows),
                               observed_days=len(observed), trading_days=len(traded),
                               trading_day_fraction=len(traded)/len(observed) if observed else None,
                               observed_pair_days=sum(r["observed_days"] for r in rows),
                               trading_pair_days=sum(r["trading_days"] for r in rows),
                               candidate_statuses=dict(sum((Counter(r["candidate_statuses"]) for r in rows), Counter())),
                               signal_gate_reasons=dict(sum((Counter(r["signal_gate_reasons"]) for r in rows), Counter())),
                               trades_exposed_to_incomplete_m5=sum(r["trades_exposed_to_incomplete_m5"] for r in rows))
                totals.append(dict(period=key[0], arm=arm, cost_multiplier=multiplier, **metrics))
        if period["label"] == "2020_2022":
            selection = select_training(totals)
            base.dump(output/"training_selection.json", dict(selection, totals=totals,
                      saved_utc=datetime.now(timezone.utc).isoformat()))
            manifest["training_selection_sha256"] = base.digest(output/"training_selection.json")
            base.dump(output/"run_manifest.json", manifest)
    later_screens = {}
    if selection["selected"] is not None:
        arm = selection["selected"]
        for period in protocol["periods"][1:]:
            rows = [r for r in totals if (r["period"], r["arm"]) == (period["label"], arm)]
            later_screens[period["label"]] = gates(next(r for r in rows if r["cost_multiplier"] == 1.),
                                                  next(r for r in rows if r["cost_multiplier"] == 1.5))
    final_confirmation = (dict(arm=selection["selected"], checks=later_screens,
                               status="DESCRIPTIVE_SCREEN_NOT_UNTOUCHED_HOLDOUT",
                               passed=all(all(check.values()) for check in later_screens.values()))
                          if selection["selected"] is not None else None)
    result = dict(experiment_id=ID, status="COMPLETED_DESCRIPTIVE_NOT_ADOPTION", cases=summaries, totals=totals,
                  training_selection=selection, later_descriptive_screens=later_screens,
                  final_confirmation=final_confirmation,
                  cost_population_note="Hourly/combined use scenario-specific costs at both gates; stress can change trades and occupancy.",
                  day_denominator="Unique source-calendar dates with observed M5 in period; combined includes union dates and summed pair-days.",
                  limitations=protocol["limitations"])
    base.dump(output/"results.json", result)
    manifest.update(completed_utc=datetime.now(timezone.utc).isoformat(), results_sha256=base.digest(output/"results.json"), cases=len(summaries))
    base.dump(output/"run_manifest.json", manifest)
    print("RESULT_JSON="+str(output/"results.json"), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=ROOT/"docs/quant_organization/experiments"/ID/"protocol.json")
    parser.add_argument("--output", type=Path, default=ROOT/"agent_runs"/ID/"completed")
    args = parser.parse_args()
    run(args.protocol, args.output)
