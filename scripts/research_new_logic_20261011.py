"""Bounded price-box hypotheses. Existing source data read-only; no external calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from scripts import research_ytt_profit_feasibility as core

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/quant_organization/experiments/new_logic_20261011"
OUT = ROOT / "agent_runs/new_logic_20261011"
ARMS = ("compression_retest", "compression_direct", "failed_excursion", "inside_edge_bounce")
CONTROLS = {ARMS[0]: ARMS[1], ARMS[2]: ARMS[3]}


def signals(times, prices, complete, tick, start, end):
    """Closed-bar signals with fresh phase episodes, constant-time fixed windows."""
    n = len(times)
    side = np.zeros((4, n), np.int8)
    stop = np.full((4, n), np.nan)
    atr_out = np.full((4, n), np.nan)
    room = np.full((4, n), np.nan)
    threshold = np.full((4, n), np.nan)
    pending = None
    last_range = [-1000000, -1000000]
    tr = prices[:, 1] - prices[:, 2]
    tr[1:] = np.maximum(tr[1:], np.maximum(abs(prices[1:, 1]-prices[:-1, 3]), abs(prices[1:, 2]-prices[:-1, 3])))

    def emit(arm, i, d, atr, level, middle=np.nan):
        side[arm, i] = d
        stop[arm, i] = prices[i, 2]-tick if d == 1 else prices[i, 1]+tick
        atr_out[arm, i], threshold[arm, i], room[arm, i] = atr, level, middle

    for i in np.flatnonzero((times >= start) & (times < end)):
        if i < 25 or not complete[i-25:i+1].all() or not (np.diff(times[i-25:i+1]) == 900).all():
            pending = None
            last_range = [-1000000, -1000000]
            continue
        op, hi, lo, cl = prices[i]
        if pending is not None:
            d, level, frozen_atr, arm_i = pending
            touch = lo <= level if d == 1 else hi >= level
            if touch:
                if d*(cl-level) > 0 and d*(cl-op) > 0:
                    emit(0, i, d, frozen_atr, level)
                pending = None
            elif i-arm_i >= 6 or d*(cl-level) <= 0:
                pending = None
            # Never replace/arm on a bar processed by an existing episode.
            process_breakout = False
        else:
            process_breakout = True
        prior = prices[i-24:i]
        upper, lower = prior[:, 1].max(), prior[:, 2].min()
        width, atr = upper-lower, float(tr[i-20:i].mean())
        if width <= 0 or atr <= 0:
            continue
        if process_breakout and width <= 3*atr:
            direction = 1 if cl > upper and cl-op >= .5*atr else (-1 if cl < lower and op-cl >= .5*atr else 0)
            if direction:
                level = upper if direction == 1 else lower
                pending = (direction, level, atr, i)
                emit(1, i, direction, atr, level)
        changes = np.abs(np.diff(prices[i-25:i, 3])).sum()
        efficiency = abs(prices[i-1, 3]-prices[i-25, 3])/changes if changes else 0.0
        if not (3*atr <= width <= 8*atr and efficiency <= .25):
            continue
        middle = (upper+lower)/2
        for arm in (2, 3):
            if i-last_range[arm-2] < 24:
                continue
            lower_touch = lo < lower if arm == 2 else lower <= lo <= lower+.1*width
            upper_touch = hi > upper if arm == 2 else upper-.1*width <= hi <= upper
            direction = (1 if lower_touch and lower < cl < middle and cl > op and hi < upper else
                         -1 if upper_touch and middle < cl < upper and cl < op and lo > lower else 0)
            if direction:
                emit(arm, i, direction, atr, lower if direction == 1 else upper, middle)
                last_range[arm-2] = i
    return dict(sides=side, stops=stop, atrs=atr_out, rooms=room, thresholds=threshold)


def simulate(data, sig, arm, rr, start, end, cost, normal_cost, cash=False):
    """Reuse audited protective fills, with this experiment's 16-bar/risk gates."""
    times, prices = data["times"], data["prices"]
    complete, exact = data["complete"], data["starts_at_open"]
    observed = data["observed_open_times"]
    side, stops, atrs, rooms, levels = (sig[key][arm] for key in ("sides", "stops", "atrs", "rooms", "thresholds"))
    indices = np.flatnonzero((times >= start) & (times < end))
    position = None
    balance, peak, minimum, intrabar_dd = 1e6, 1e6, 1e6, 0.0
    rows, curve = [], []
    halted, stop_time = False, ""
    skipped = dict(occupied=0, missing_entry=0, invalid_risk=0, cost_floor=0, atr_ceiling=0, insufficient_room=0, zero_quantity=0)
    for k, i in enumerate(indices):
        t = int(times[i])
        op, hi, lo, cl = prices[i]
        gap = i > 0 and (times[i]-times[i-1] != 900 or not exact[i])
        exit_price, reason = None, ""
        occupied_at_open = position is not None
        if occupied_at_open and gap:
            exit_price, reason = op, "data_gap_open"
            if position["side"]*(op-position["target"]) > 0:
                exit_price, reason = position["target"], "data_gap_tp_capped"
        if i and times[i-1] >= start and side[i-1] and not halted:
            if occupied_at_open:
                skipped["occupied"] += 1
            elif gap or times[i] != times[i-1]+900:
                skipped["missing_entry"] += 1
            else:
                d, sl = int(side[i-1]), float(stops[i-1])
                risk = d*(op-sl)
                reject = ("invalid_risk" if not np.isfinite(risk) or risk <= 0 else
                          "cost_floor" if risk < 10*normal_cost else
                          "atr_ceiling" if risk > 2*atrs[i-1] else
                          "insufficient_room" if np.isfinite(rooms[i-1]) and d*(rooms[i-1]-op) < 2*risk else "")
                if reject:
                    skipped[reject] += 1
                else:
                    qty = float(np.floor(min(balance*.005/(risk+cost), balance*25/op)/1000)*1000) if cash else 1.0
                    if qty <= 0:
                        skipped["zero_quantity"] += 1
                    else:
                        position = dict(entry=float(op), stop=sl, target=float(op+d*rr*risk), side=d, risk=float(risk), rr=float(rr),
                                        qty=qty, entry_time=t, signal_time=int(times[i-1]+900), threshold=float(levels[i-1]),
                                        entry_index=int(i), incomplete_bars=0)
        if position is not None:
            p = position
            effective_stop, stop_reason = p["stop"], "sl"
            if cash:
                floor = p["entry"] + p["side"]*((900000-balance)/p["qty"]+cost)
                if p["side"]*(floor-effective_stop) >= 0:
                    effective_stop, stop_reason = floor, "account_floor"
            if exit_price is None:
                exit_price, reason = core.fill_bar(op, hi, lo, cl, p["side"], effective_stop, p["target"], stop_reason)
            if not complete[i]:
                p["incomplete_bars"] += 1
                if exit_price is None:
                    exit_price, reason = cl, "incomplete_bar_close"
            if exit_price is None and t % 86400 == 85500:
                exit_price, reason = cl, "daily_close"
            if exit_price is None and i-p["entry_index"]+1 >= 16:
                exit_price, reason = cl, "max_16_bars"
            if exit_price is None and k == len(indices)-1:
                exit_price, reason = cl, "period_end_mark"
            if cash:
                adverse = exit_price if exit_price is not None and ("sl" in reason or "account_floor" in reason or "gap" in reason) else (lo if p["side"] == 1 else hi)
                worst = balance+p["qty"]*(p["side"]*(adverse-p["entry"])-cost)
                minimum = min(minimum, worst)
                intrabar_dd = max(intrabar_dd, peak-worst)
            if exit_price is not None:
                gross = p["side"]*(exit_price-p["entry"])
                net = gross-cost
                if cash:
                    balance += net*p["qty"]
                    if reason.startswith("account_floor") or balance <= 900000+1e-7:
                        halted = True
                        stop_time = core.stamp(observed[i] if "gap" in reason else t+900)
                rows.append(dict(**p, exit_time=int(observed[i]) if "gap" in reason else t+900, exit_price=float(exit_price),
                                 reason=reason, cost_price=cost, gross_r=float(gross/p["risk"]), net_r=float(net/p["risk"]),
                                 net_price=float(net), pnl_yen=float(net*p["qty"]) if cash else 0.0, balance_yen=balance if cash else 0.0))
                position = None
        equity = balance
        if cash and position is not None:
            equity += position["qty"]*(position["side"]*(cl-position["entry"])-cost)
        if cash:
            peak, minimum = max(peak, equity), min(minimum, equity)
            curve.append((t+900, equity))
    return rows, np.array(curve).reshape(-1, 2), dict(final_equity_yen=balance, net_yen=balance-1e6, stopped=halted,
        stop_time_source=stop_time, minimum_equity_yen=minimum, max_observed_intrabar_drawdown_yen=intrabar_dd, skipped=skipped)


def metrics(rows):
    result = core.metrics(rows)
    r = np.array([x["net_r"] for x in rows])
    wins, losses = r[r > 0], r[r < 0]
    result.update(win_rate=float(len(wins)/len(r)) if len(r) else None,
                  realized_payoff_rr=float(wins.mean()/abs(losses.mean())) if len(wins) and len(losses) else None,
                  mean_win_r=float(wins.mean()) if len(wins) else None, mean_loss_r=float(losses.mean()) if len(losses) else None,
                  reason_counts={reason: sum(r["reason"] == reason for r in rows) for reason in sorted({r["reason"] for r in rows})})
    return result


def cash_monthly(rows, start, end, curve):
    months = core.monthly(rows, start, end, cash=True, curve=curve)
    prior = 1e6
    for row in months:
        row.pop("goal_met", None)  # The imported old study had a different monthly goal.
        row["monthly_return"] = row["equity_yen"]/prior-1 if prior > 0 else None
        row["reaches_5_percent"] = row["monthly_return"] is not None and row["monthly_return"] >= .05
        prior = row["equity_yen"]
    return months


def screen(normal, stress, per_symbol, account, control, gates):
    positives = [max(0, row["net_r"]) for row in per_symbol]
    concentration = max(positives)/sum(positives) if sum(positives) else 1.0
    checks = dict(count=normal["trades"] >= gates["aggregate_trades_min"],
                  per_symbol_count=all(x["trades"] >= gates["per_symbol_trades_min"] for x in per_symbol),
                  normal_pf=normal["pf"] is not None and normal["pf"] >= gates["normal_pf_min"],
                  normal_mean=normal["mean_net_r"] > 0,
                  stress_pf=stress["pf"] is not None and stress["pf"] > gates["stress_pf_strict_min"],
                  stress_mean=stress["mean_net_r"] > 0,
                  profitable_symbols=sum(x["net_r"] > 0 for x in per_symbol) >= gates["profitable_symbols_min"],
                  concentration=concentration <= gates["max_positive_symbol_contribution"],
                  no_usdjpy_halt=not account["stopped"],
                  above_control=normal["mean_net_r"] > control["mean_net_r"])
    return dict(passes=all(checks.values()), checks=checks, positive_symbol_concentration=concentration)


def run(phase):
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN":
        raise ValueError("Protocol is not frozen")
    target = OUT/phase
    if (target/"results.json").exists():
        raise ValueError("Existing result preserved: use a new experiment for changes")
    phases = list(protocol["periods"])
    candidates = [(arm, float(rr)) for arm in CONTROLS for rr in protocol["exit_rules"]["reward_risk_ratios"]]
    if phase != "training":
        prev = phases[phases.index(phase)-1]
        approval = json.loads((OUT/f"{phase}_approval.json").read_text(encoding="utf-8"))
        previous = json.loads((OUT/prev/"results.json").read_text(encoding="utf-8"))
        if not approval.get("independent_approved") or previous["selected"] is None:
            raise ValueError("Independent preceding-phase approval and selected configuration required")
        selected = previous["selected"]
        candidates = [(selected["arm"], selected["rr"])]
    configurations = sorted(set(candidates+[(CONTROLS[a], r) for a, r in candidates]))
    start, end = map(core.epoch, protocol["periods"][phase])
    target.mkdir(parents=True, exist_ok=True)
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), phase=phase,
                    files={str(p.relative_to(ROOT)): core.digest(p) for p in [DOC/"protocol.json", DOC/"hypothesis.md", Path(__file__),
                           ROOT/"tests/test_new_logic_20261011.py", Path(core.__file__)]}, inputs=[])
    rows_by = {}
    records, accounts = [], {}
    for symbol in protocol["symbols"]:
        path = ROOT/protocol["cache_directory"]/f"{symbol}_execution.npz"
        expected = protocol["input_sha256"][symbol]
        if core.digest(path) != expected:
            raise ValueError(f"Input hash mismatch: {symbol}")
        with np.load(path, allow_pickle=False) as z:
            data = {k: z[k].copy() for k in ("times", "prices", "complete", "starts_at_open", "observed_open_times")}
        # No later-phase bars enter indicator or execution calculations.
        mask = data["times"] < end
        data = {key: value[mask] for key, value in data.items()}
        if np.any(np.diff(data["times"]) <= 0) or not np.isfinite(data["prices"]).all():
            raise ValueError("Invalid cache")
        costs = protocol["cost_and_fill_model"]
        normal_cost = costs["round_trip_pips"][symbol]*costs["pip"][symbol]
        sig = signals(data["times"], data["prices"], data["complete"], costs["tick"][symbol], start, end)
        np.savez_compressed(target/f"{symbol}_signals.npz", times=data["times"], **sig)
        manifest["inputs"].append(dict(symbol=symbol, path=str(path.relative_to(ROOT)), sha256=expected,
                                       phase_signals={a: int(np.count_nonzero(sig["sides"][i])) for i, a in enumerate(ARMS)}))
        core.dump(target/"run_manifest.json", manifest)
        for arm, rr in configurations:
            for multiplier in (1, 2):
                cost = normal_cost*multiplier
                rows, _, details = simulate(data, sig, ARMS.index(arm), rr, start, end, cost, normal_cost)
                key = f"{arm}_rr{rr:g}_cost{multiplier}"
                rows_by.setdefault(key, []).extend([dict(symbol=symbol, **x) for x in rows])
                core.save_trades(target/f"{symbol}_{key}.csv", rows)
                r = np.array([x["net_r"] for x in rows])
                np.savez_compressed(target/f"{symbol}_{key}_closed_r_curve.npz", times=np.array([x["exit_time"] for x in rows]), equity_r=np.cumsum(r))
                records.append(dict(symbol=symbol, arm=arm, rr=rr, cost_multiplier=multiplier, **metrics(rows), skipped=details["skipped"],
                                    monthly=core.monthly(rows, start, end), annual=[dict(year=y, **metrics([x for x in rows if core.stamp(x["exit_time"]-(0 if "gap" in x["reason"] else 1))[:4] == str(y)])) for y in range(int(core.stamp(start)[:4]), int(core.stamp(end)[:4]))]))
                if symbol == "USDJPY":
                    cash_rows, curve, account = simulate(data, sig, ARMS.index(arm), rr, start, end, cost, normal_cost, cash=True)
                    core.save_trades(target/f"USDJPY_{key}_cash.csv", cash_rows)
                    np.savez_compressed(target/f"USDJPY_{key}_cash_curve.npz", curve=curve)
                    accounts[key] = dict(**account, **metrics(cash_rows), monthly=cash_monthly(cash_rows, start, end, curve))
    pooled = {}
    for key, rows in rows_by.items():
        rows.sort(key=lambda x: (x["exit_time"], x["symbol"], x["entry_time"]))
        pooled[key] = metrics(rows)
    selections = []
    for arm, rr in candidates:
        key = f"{arm}_rr{rr:g}"
        criteria = screen(pooled[key+"_cost1"], pooled[key+"_cost2"], [r for r in records if r["arm"] == arm and r["rr"] == rr and r["cost_multiplier"] == 1],
                          accounts[key+"_cost1"], pooled[f"{CONTROLS[arm]}_rr{rr:g}_cost1"], protocol["acceptance_gates"])
        selections.append(dict(arm=arm, rr=rr, **criteria))
    passing = [s for s in selections if s["passes"]]
    passing.sort(key=lambda s: (-pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["pf"], -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["mean_net_r"],
                               -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["trades"], s["arm"], s["rr"]))
    selected = dict(arm=passing[0]["arm"], rr=passing[0]["rr"]) if passing else None
    result = dict(phase=phase, status="SCREEN_PASSED_NEEDS_INDEPENDENT_REVIEW" if selected else "REJECTED_AT_PHASE_SCREEN",
                  selected=selected, screens=selections, records=records, pooled_equal_r=pooled, usdjpy_accounts=accounts,
                  adoption_approved=False, later_periods_used=False, pristine_holdout=False)
    core.dump(target/"results.json", result)
    manifest.update(completed_utc=datetime.now(timezone.utc).isoformat(), results_sha256=core.digest(target/"results.json"))
    core.dump(target/"run_manifest.json", manifest)
    print(json.dumps(dict(status=result["status"], selected=selected, result=str(target/"results.json"))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["training", "validation", "final_confirmation"], default="training")
    run(parser.parse_args().phase)
