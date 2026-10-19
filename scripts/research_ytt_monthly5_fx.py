"""Three frozen FX cases; completed source-calendar D/W and one continuous JPY account."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import research_ytt_profit_feasibility as core

ID = "ytt_monthly5_fx_20261009"
DOC = ROOT/"docs/quant_organization/experiments"/ID
OUT = ROOT/"agent_runs"/ID
ARMS = ("dw_m15", "dw_h1", "no_htf_h1")
MONDAY_ANCHOR = 4*86400  # 1970-01-05, a Monday in the naive source calendar.


def calendar_bars(times, prices, complete, width, anchor=0):
    """Elapsed observed calendar bars, not fictitious 24/7 complete FX bars."""
    labels = (times-anchor)//width*width+anchor
    starts = np.r_[0, np.flatnonzero(np.diff(labels))+1]
    ends = np.r_[starts[1:], len(times)]
    bars = np.column_stack((prices[starts, 0], np.maximum.reduceat(prices[:, 1], starts),
                            np.minimum.reduceat(prices[:, 2], starts), prices[ends-1, 3]))
    diagnostics = []
    for label, a, b in zip(labels[starts], starts, ends):
        observed_days = np.unique(times[a:b]//86400)
        within_day_missing = 0
        for day in observed_days:
            tt = times[a:b][times[a:b]//86400 == day]
            within_day_missing += int((tt[-1]-tt[0])//300+1-len(tt))
        diagnostics.append(dict(start=int(label), available_at=int(label+width), observed_m5=int(b-a),
            complete_m5=int(complete[a:b].sum()), complete_m5_ratio=float(complete[a:b].mean()),
            observed_calendar_days=len(observed_days), weekdays=sorted({int((d+3)%7) for d in observed_days}),
            within_observed_day_missing_m5=within_day_missing,
            unobserved_calendar_days=int(width//86400-len(observed_days))))
    return labels[starts], bars, diagnostics


def context(entry_times, calendar_times, state, width, anchor=0):
    boundary = (entry_times-anchor)//width*width+anchor
    at = np.searchsorted(calendar_times+width, boundary, side="right")-1
    d = np.zeros(len(entry_times), dtype=np.int8)
    ready = np.zeros(len(entry_times), bool)
    exists = at >= 0
    ix = at[exists]
    ready[exists] = np.isfinite(state["high"][ix]) & np.isfinite(state["low"][ix]) & (state["direction"][ix] != 0)
    d[exists] = state["direction"][ix]
    d[~ready] = 0
    return d, ready


def map_signals(exec_times, event_times, event_width, side, stop, threshold):
    """Place a completed H1 event on its final M15, for entry at next H1 open."""
    final_m15 = event_times+event_width-900
    at = np.searchsorted(exec_times, final_m15)
    if np.any(at >= len(exec_times)) or not np.array_equal(exec_times[at], final_m15):
        raise ValueError("Complete entry bars must have a final M15 execution bar")
    out_side = np.zeros(len(exec_times), np.int8)
    out_stop, out_threshold = np.full(len(exec_times), np.nan), np.full(len(exec_times), np.nan)
    out_side[at], out_stop[at], out_threshold[at] = side, stop, threshold
    return out_side, out_stop, out_threshold


def economic_time(row):
    return row["exit_time"]-(0 if "gap" in row["reason"] else 1)


def in_period(rows, start, end):
    return [r for r in rows if start <= economic_time(r) < end]


def monthly_account(rows, curve, start, end):
    months, prior = [], 1_000_000.0
    for month in core.months(start, end):
        lo = core.epoch(month)
        hi = core.epoch(str(np.datetime64(month, "M")+1))
        known = curve[curve[:, 0] <= hi]
        equity = float(known[-1, 1]) if len(known) else prior
        selected = in_period(rows, lo, hi)
        ret = equity/prior-1 if prior > 0 else None
        months.append(dict(month=month, start_equity_yen=prior, equity_yen=equity,
                           pnl_yen=equity-prior, monthly_return=ret, trades=len(selected),
                           realized_pnl_yen=sum(r["pnl_yen"] for r in selected),
                           reaches_5_percent=ret is not None and ret >= .05,
                           reaches_fixed_50000=equity-prior >= 50000))
        prior = equity
    return months


def return_summary(months):
    returns = [m["monthly_return"] for m in months]
    valid = bool(returns) and all(x is not None and np.isfinite(x) and x > -1 for x in returns)
    g = float(np.expm1(np.log1p(returns).mean())) if valid else None
    without_best = list(returns)
    if valid and len(without_best) > 1:
        without_best.remove(max(without_best))
        g_without = float(np.expm1(np.log1p(without_best).mean()))
    else:
        g_without = None
    consecutive, longest = 0, 0
    for m in months:
        consecutive = 0 if m["reaches_5_percent"] else consecutive+1
        longest = max(longest, consecutive)
    return dict(months=len(months), geometric_monthly_return=g,
                arithmetic_monthly_return=float(np.mean(returns)) if valid else None,
                median_monthly_return=float(np.median(returns)) if valid else None,
                worst_monthly_return=float(min(returns)) if valid else None,
                best_monthly_return=float(max(returns)) if valid else None,
                geometric_without_one_best_month=g_without,
                max_consecutive_months_below_5_percent=longest,
                months_reaching_5_percent=sum(m["reaches_5_percent"] for m in months),
                ratio_months_reaching_5_percent=sum(m["reaches_5_percent"] for m in months)/len(months) if months else 0,
                ratio_months_reaching_fixed_50000=sum(m["reaches_fixed_50000"] for m in months)/len(months) if months else 0,
                every_month_reaches_5_percent=bool(months) and all(m["reaches_5_percent"] for m in months))


def account_window(rows, months, curve, account, start, end):
    selected_months = [m for m in months if core.epoch(m["month"]) >= start and core.epoch(m["month"]) < end]
    selected = in_period(rows, start, end)
    pnl = np.array([r["pnl_yen"] for r in selected])
    positive, negative = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    first = selected_months[0]["start_equity_yen"]
    last = selected_months[-1]["equity_yen"]
    equity = np.r_[first, curve[(curve[:, 0] > start) & (curve[:, 0] <= end), 1]]
    # A close at Jan 1 00:00 belongs to Dec; an open/gap at that time belongs to Jan.
    stop_effective_time = (economic_time(rows[-1]) if rows else core.epoch(account["stop_time_source"])) if account["stopped"] else end
    stopped = bool(account["stopped"] and stop_effective_time < end)
    return dict(**return_summary(selected_months), trades=len(selected), starting_equity_yen=first,
                ending_equity_yen=last, net_yen=last-first, realized_net_yen=float(pnl.sum()),
                pf_jpy=float(positive/negative) if negative else None,
                max_close_drawdown_yen=float((np.maximum.accumulate(equity)-equity).max()),
                halted_by_period_end=stopped, stop_time_source=account["stop_time_source"])


def normal_account_gate(row):
    return dict(geometric_monthly_5pct=row["geometric_monthly_return"] is not None and row["geometric_monthly_return"] >= .05,
                pf_jpy=row["pf_jpy"] is not None and row["pf_jpy"] >= 1.2,
                net_yen=row["net_yen"] > 0, trades=row["trades"] >= 100,
                monthly_median=row["median_monthly_return"] is not None and row["median_monthly_return"] > 0,
                no_stop=not row["halted_by_period_end"])


def prepare(protocol, output, manifest):
    data = {}
    metadata = json.loads((ROOT/protocol["data_manifest"]).read_text(encoding="utf-8"))
    masks = json.loads((ROOT/protocol["complete_m5_directory"]/"run_manifest.json").read_text(encoding="utf-8"))["inputs"]
    old_manifest = json.loads((ROOT/protocol["reference_inputs"]["baseline_manifest"]).read_text(encoding="utf-8"))
    for symbol in protocol["symbols"]:
        m = next(x for x in metadata if x["symbol"] == symbol)
        mask_meta = next(x for x in masks if x["symbol"] == symbol)
        cache = ROOT/protocol["cache_directory"]/f"{symbol}_features.npz"
        mask = ROOT/protocol["complete_m5_directory"]/f"{symbol}_complete_m5.npz"
        hashes = dict(cache_sha256=core.digest(cache), mask_sha256=core.digest(mask))
        old = next(x for x in old_manifest["inputs"] if x["symbol"] == symbol)
        if hashes["cache_sha256"] != m["cache_sha256"] or hashes["mask_sha256"] != mask_meta["mask_sha256"] or any(hashes[k] != old[k] for k in hashes):
            raise ValueError(f"M5 inputs changed: {symbol}")
        with np.load(cache, allow_pickle=False) as z:
            times, prices = z["times"], z["features"][:, :4]
        with np.load(mask, allow_pickle=False) as z:
            complete = z["complete"]
        if len(complete) != len(times) or np.any(np.diff(times) <= 0) or not np.isfinite(prices).all():
            raise ValueError("Invalid aligned M5 data")
        t, p, valid, _, _ = core.aggregate(times, prices, complete, 900)
        actual, exact, raw_hash = core.raw_open_metadata(symbol, m, t)
        if raw_hash != old["raw_sha256"]:
            raise ValueError("Raw data differs from baseline")
        calendar = []
        for label, width, anchor in (("D1", 86400, 0), ("W1", 604800, MONDAY_ANCHOR)):
            ct, cp, quality = calendar_bars(times, prices, complete, width, anchor)
            cs = core.states(cp)
            calendar.append((ct, cs, width, anchor))
            np.savez_compressed(output/f"{symbol}_{label}.npz", times=ct, prices=cp, **cs)
            core.dump(output/f"{symbol}_{label}_coverage.json", quality)
        arm_signals = {}
        for width in (900, 3600):
            et, ep, ev, _, _ = core.aggregate(times, prices, complete, width)
            et, ep = et[ev], ep[ev]
            es = core.states(ep)
            daily, daily_ready = context(et, *calendar[0])
            weekly, weekly_ready = context(et, *calendar[1])
            side, stop, threshold = core.signals(ep, es, daily, weekly, m["tick"])
            arm = "dw_m15" if width == 900 else "dw_h1"
            arm_signals[arm] = map_signals(t, et, width, side[0], stop[0], threshold[0])
            if width == 3600:
                arm_signals["no_htf_h1"] = map_signals(t, et, width, side[1], stop[1], threshold[1])
            np.savez_compressed(output/f"{symbol}_entry{width}.npz", times=et, prices=ep, daily=daily, weekly=weekly,
                                daily_ready=daily_ready, weekly_ready=weekly_ready, sides=side, stops=stop, thresholds=threshold, **es)
        np.savez_compressed(output/f"{symbol}_execution.npz", times=t, prices=p, complete=valid, starts_at_open=exact,
                            observed_open_times=actual, sides=np.array([arm_signals[a][0] for a in ARMS]),
                            stops=np.array([arm_signals[a][1] for a in ARMS]), thresholds=np.array([arm_signals[a][2] for a in ARMS]))
        data[symbol] = dict(times=t, prices=p, complete=valid, starts_at_open=exact, observed_open_times=actual,
                            signals=arm_signals, pip=m["pip"])
        manifest["inputs"].append(dict(symbol=symbol, **hashes, raw_sha256=raw_hash, execution_bars=len(t),
                                       complete_execution_bars=int(valid.sum()), actual_exact_opens=int(exact.sum())))
    return data


def gates(protocol, records, combined, accounts, old):
    lookup_r = {(r["arm"], r["period"], r["cost_multiplier"]): r for r in combined}
    lookup_y = {(r["arm"], r["period"], r["cost_multiplier"]): r for r in accounts}
    result = []
    for arm in protocol["adoption_candidates"]:
        checks = []
        for period, old_period in (("later_descriptive", "validation"), ("latest_descriptive", "latest_descriptive")):
            normal, stress = lookup_y[arm, period, 1], lookup_y[arm, period, 2]
            eligible = [r for r in records if r["arm"] == arm and r["period"] == period and r["cost_multiplier"] == 1]
            positive = sum(r["pf"] is not None and r["pf"] >= 1.2 and r["mean_net_r"] > 0 and r["trades"] >= 100 for r in eligible)
            baseline = (lookup_r["no_htf_h1", period, 1] if arm == "dw_h1" else
                        next(r for r in old["combined_trade_statistics_not_portfolio"] if r["arm"] == "no_htf_baseline" and r["period"] == old_period and r["cost_multiplier"] == 1))
            comparison = lookup_r[arm, period, 1]["mean_net_r"] >= baseline["mean_net_r"]
            checks.append(dict(period=period, normal=normal_account_gate(normal),
                stress=dict(net_yen=stress["net_yen"] > 0, no_stop=not stress["halted_by_period_end"]),
                qualified_currencies=positive, currencies_pass=positive >= 2,
                baseline_mean_net_r=baseline["mean_net_r"], mean_r_comparison=comparison))
        continuous = lookup_y[arm, "continuous", 1]
        g = continuous["geometric_monthly_return"]
        whole = dict(no_stop=not continuous["halted_by_period_end"], geometric_monthly_5pct=g is not None and g >= .05)
        passed = all(whole.values()) and all(all(c["normal"].values()) and all(c["stress"].values()) and c["currencies_pass"] and c["mean_r_comparison"] for c in checks)
        result.append(dict(arm=arm, all_pass=passed, continuous=whole, periods=checks,
                           every_month_5pct=continuous["every_month_reaches_5_percent"],
                           disposition="NEEDS_EVIDENCE" if passed else "GATES_FAILED_PENDING_INDEPENDENT_VALIDATION"))
    return result


def run():
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN" or protocol["candidate_budget"] != 3 or protocol["search_space"] != list(ARMS):
        raise ValueError("Director-frozen 3-case protocol required; draft execution is disabled")
    reference = protocol["reference_inputs"]
    for path_key, sha_key in (("core_code", "core_sha256"), ("baseline_result", "baseline_result_sha256"), ("baseline_manifest", "baseline_manifest_sha256")):
        if core.digest(ROOT/reference[path_key]) != reference[sha_key]:
            raise ValueError(f"Frozen reference changed: {path_key}")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), protocol_sha256=core.digest(DOC/"protocol.json"),
        hypothesis_sha256=core.digest(DOC/"hypothesis.md"), data_inventory_sha256=core.digest(DOC/"data_inventory.md"),
        plan_sha256=core.digest(DOC/"plan.md"), code_sha256=core.digest(__file__),
        tests_sha256=core.digest(ROOT/"tests/test_ytt_monthly5_fx.py"), reference_inputs=reference, inputs=[])
    core.dump(OUT/"run_manifest.json", manifest)
    data = prepare(protocol, OUT, manifest)
    # All input hashes are fixed and persisted before the first P/L simulation.
    core.dump(OUT/"run_manifest.json", manifest)
    start, end = map(core.epoch, protocol["continuous_account"])
    records, accounts, all_trades = [], [], {}
    for symbol, d in data.items():
        for arm in ARMS:
            side, stop, threshold = d["signals"][arm]
            for multiplier in protocol["cost_and_fill_model"]["cost_multipliers"]:
                cost = (protocol["cost_and_fill_model"]["spread_pips"][symbol]+2*protocol["cost_and_fill_model"]["slippage_pips_each_side"])*d["pip"]*multiplier
                args = (d["times"], d["prices"], d["complete"], d["starts_at_open"], side, stop, threshold, start, end, cost)
                name = f"{symbol}_{arm}_cost{multiplier}"
                rows = []
                for period, dates in protocol["periods"].items():
                    period_args = (*args[:7], *map(core.epoch, dates), cost)
                    selected, _, _ = core.simulate(*period_args, observed_open_times=d["observed_open_times"])
                    for row in selected:
                        row["net_pips"] = row["net_price"]/d["pip"]
                        row["period"] = period
                    rows.extend(selected)
                    records.append(dict(symbol=symbol, arm=arm, period=period, cost_multiplier=multiplier,
                                        net_pips=sum(r["net_pips"] for r in selected), **core.metrics(selected)))
                    all_trades.setdefault((arm, period, multiplier), []).extend(selected)
                core.save_trades(OUT/f"{name}.csv", rows)
                monthly_r = []
                for month in core.months(start, end):
                    selected = in_period(rows, core.epoch(month), core.epoch(str(np.datetime64(month, "M")+1)))
                    monthly_r.append(dict(month=month, net_pips=sum(r["net_pips"] for r in selected), **core.metrics(selected)))
                core.dump(OUT/f"{name}_monthly.json", monthly_r)
                if symbol == "USDJPY":
                    cash_rows, curve, account = core.simulate(*args, cash=True, observed_open_times=d["observed_open_times"])
                    name = "JPY_"+name
                    core.save_trades(OUT/f"{name}.csv", cash_rows)
                    np.savez_compressed(OUT/f"{name}_equity.npz", curve=curve)
                    mm = monthly_account(cash_rows, curve, start, end)
                    core.dump(OUT/f"{name}_monthly.json", mm)
                    for period, dates in dict(protocol["periods"], continuous=protocol["continuous_account"]).items():
                        account_row = account_window(cash_rows, mm, curve, account, *map(core.epoch, dates))
                        if multiplier == 2:
                            diagnostic = dict(net_yen=account_row["net_yen"] > 0, no_stop=not account_row["halted_by_period_end"])
                        elif period == "continuous":
                            g = account_row["geometric_monthly_return"]
                            diagnostic = dict(geometric_monthly_5pct=g is not None and g >= .05, no_stop=not account_row["halted_by_period_end"])
                        else:
                            diagnostic = normal_account_gate(account_row)
                        accounts.append(dict(arm=arm, period=period, cost_multiplier=multiplier, **account_row, account_gate_diagnostic=diagnostic))
                    core.dump(OUT/f"{name}_execution_summary.json", account)
        print(f"COMPLETED {symbol}", flush=True)
    combined = [dict(arm=a, period=p, cost_multiplier=c, **core.metrics(sorted(rows, key=lambda r: (r["exit_time"], r["entry_time"]))))
                for (a, p, c), rows in all_trades.items()]
    old = json.loads((ROOT/reference["baseline_result"]).read_text(encoding="utf-8"))
    result = dict(experiment_id=ID, records=records, combined_equal_r_not_yen_portfolio=combined,
        continuous_usdjpy_account_windows=accounts, gates=gates(protocol, records, combined, accounts, old),
        limitations=["Previously viewed periods", "Source-calendar D/W differs from broker feed; no full session calendar", "Swap excluded", "No external account orders", "No monthly return guarantee"])
    core.dump(OUT/"results.json", result)
    manifest.update(completed_utc=datetime.now(timezone.utc).isoformat(), results_sha256=core.digest(OUT/"results.json"))
    core.dump(OUT/"run_manifest.json", manifest)
    print("RESULT_JSON="+str(OUT/"results.json"), flush=True)


if __name__ == "__main__":
    run()
