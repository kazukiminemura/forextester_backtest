"""Frozen two-arm descriptive study. No orders, search, or adoption authority."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ID = "ytt_profit_feasibility_20261009"
DOC = ROOT / "docs/quant_organization/experiments" / ID
OUT = ROOT / "agent_runs" / ID
ARMS = ("h1_h4_agreement", "no_htf_baseline")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def epoch(text):
    # Naive source-clock labels only: no claim about the provider's timezone.
    return int(np.datetime64(text, "s").astype(np.int64))


def stamp(value):
    return str(np.datetime64(int(value), "s"))


def aggregate(times, prices, complete, width):
    """Keep incomplete buckets for execution; expose completeness for indicators."""
    labels = times // width * width
    starts = np.r_[0, np.flatnonzero(np.diff(labels)) + 1]
    ends = np.r_[starts[1:], len(times)]
    bars = np.column_stack((prices[starts, 0], np.maximum.reduceat(prices[:, 1], starts),
                            np.minimum.reduceat(prices[:, 2], starts), prices[ends-1, 3]))
    valid = ((ends-starts == width//300) & (times[starts] == labels[starts])
             & (times[ends-1] == labels[starts]+width-300)
             & np.logical_and.reduceat(complete, starts))
    return labels[starts], bars, valid, times[starts] == labels[starts], times[starts]


def actual_open_times(raw_times, bucket_labels, width=900):
    """The first actually observed M1, never the resampler's bucket label."""
    at = np.searchsorted(raw_times, bucket_labels)
    if np.any(at >= len(raw_times)):
        raise ValueError("Missing raw open time")
    observed = raw_times[at]
    if np.any(observed >= bucket_labels+width):
        raise ValueError("Raw timestamps do not cover saved buckets")
    return observed, observed == bucket_labels


def raw_open_metadata(symbol, metadata, labels):
    from forextester_backtest.data import HistoryRepository, _to_ole

    raw = Path(metadata["raw_path"])
    raw_hash = digest(raw)
    if raw_hash != metadata["raw_sha256"]:
        raise ValueError(f"Raw input changed: {symbol}")
    count = HistoryRepository(raw.parent.parent).summary(symbol).bar_count
    a = np.memmap(raw, mode="r", dtype="<f8", offset=4, shape=(count, 6))
    ole_epoch = _to_ole(datetime(1970, 1, 1))
    lo, hi = np.searchsorted(a[:, 0], [(labels[0]-1)/86400+ole_epoch, (labels[-1]+901)/86400+ole_epoch])
    raw_times = np.rint((a[lo:hi, 0]-ole_epoch)*86400).astype(np.int64)
    observed, exact = actual_open_times(raw_times, labels)
    return observed, exact, raw_hash


def states(prices):
    """f_state order on observed complete bars; tie rule explicitly approximate."""
    n = len(prices)
    high, low = np.full(n, np.nan), np.full(n, np.nan)
    ph, pl = np.zeros(n, bool), np.zeros(n, bool)
    direction = np.zeros(n, np.int8)
    hh, ll, d = np.nan, np.nan, 0
    for i in range(n):
        c = prices[i, 3]
        if i:
            up = c > hh and prices[i-1, 3] <= hh
            down = c < ll and prices[i-1, 3] >= ll
            if up != down:
                d = 1 if up else -1
        if i >= 4:
            k = i-2
            ph[i] = (prices[k, 1] >= prices[k-2:k, 1].max()
                     and prices[k, 1] > prices[k+1:i+1, 1].max())
            pl[i] = (prices[k, 2] <= prices[k-2:k, 2].min()
                     and prices[k, 2] < prices[k+1:i+1, 2].min())
            if ph[i]:
                hh = prices[k, 1]
            if pl[i]:
                ll = prices[k, 2]
        high[i], low[i], direction[i] = hh, ll, d
    return dict(high=high, low=low, direction=direction, new_high=ph, new_low=pl)


def previous_htf(m15_times, htf_times, htf_direction, width):
    boundary = m15_times // width * width
    at = np.searchsorted(htf_times + width, boundary, side="right") - 1
    return np.where(at >= 0, htf_direction[np.maximum(at, 0)], 0)


def signals(prices, state, h1, h4, tick):
    """Events use old pivot and old consumed flag; every break consumes it."""
    n = len(prices)
    side = np.zeros((2, n), np.int8)
    stop = np.full((2, n), np.nan)
    threshold = np.full((2, n), np.nan)
    used_h = used_l = False
    for i in range(1, n):
        h, l = state["high"][i-1], state["low"][i-1]
        c, prev = prices[i, 3], prices[i-1, 3]
        up = not used_h and c > h and prev <= h
        down = not used_l and c < l and prev >= l
        for arm in range(2):
            if up and (arm == 1 or h1[i] == h4[i] == 1):
                side[arm, i], stop[arm, i], threshold[arm, i] = 1, l-tick, h
            elif down and (arm == 1 or h1[i] == h4[i] == -1):
                side[arm, i], stop[arm, i], threshold[arm, i] = -1, h+tick, l
        used_h |= bool(c > h)
        used_l |= bool(c < l)
        if state["new_high"][i]:
            used_h = bool(c > state["high"][i])
        if state["new_low"][i]:
            used_l = bool(c < state["low"][i])
    return side, stop, threshold


def fill_bar(op, hi, lo, cl, side, stop, target, stop_reason="sl"):
    if side*(op-stop) <= 0:
        return op, stop_reason+"_gap"
    if side*(op-target) >= 0:
        return target, "tp_gap_capped"
    if (lo <= stop if side == 1 else hi >= stop):
        return stop, stop_reason
    if (hi >= target if side == 1 else lo <= target):
        return target, "tp"
    return None, ""


def simulate(times, prices, complete, starts_at_open, side, stops, threshold,
             start, end, cost, cash=False, observed_open_times=None):
    """One position; cash mode is USDJPY only, JPY per base-unit price move."""
    indices = np.flatnonzero((times >= start) & (times < end))
    observed_open_times = times if observed_open_times is None else observed_open_times
    rows, curve = [], []
    position = None
    balance = 1_000_000.0
    halted, stop_time = False, ""
    skipped = dict(occupied=0, nonpositive_risk=0, missing_entry=0, zero_quantity=0)
    minimum_equity, peak_equity, intrabar_dd = balance, balance, 0.0
    for k, i in enumerate(indices):
        t = int(times[i])
        op, hi, lo, cl = prices[i]
        gap = i > 0 and (times[i]-times[i-1] != 900 or not starts_at_open[i])
        exit_price, reason = None, ""
        if position is not None and gap:
            exit_price, reason = op, "data_gap_open"
            if position["side"]*(op-position["target"]) > 0:
                exit_price, reason = position["target"], "data_gap_tp_capped"
            if cash and balance + position["qty"]*(position["side"]*(op-position["entry"])-cost) <= 900_000:
                reason = "account_floor_gap"
        if position is None and not halted and i and side[i-1]:
            if gap or times[i] != times[i-1]+900:
                skipped["missing_entry"] += 1
            else:
                d, sl = int(side[i-1]), float(stops[i-1])
                risk = d*(op-sl)
                if not np.isfinite(risk) or risk <= 0:
                    skipped["nonpositive_risk"] += 1
                else:
                    qty = (np.floor(min(balance*.005/(risk+cost), balance*25/op)/1000)*1000
                           if cash else 1.0)
                    if qty <= 0:
                        skipped["zero_quantity"] += 1
                    else:
                        position = dict(entry=op, stop=sl, target=op+d*risk, side=d, risk=risk,
                                        qty=float(qty), entry_time=t, signal_time=int(times[i-1]+900),
                                        threshold=float(threshold[i-1]), entry_index=int(i), incomplete_bars=0)
        elif position is not None and i and side[i-1]:
            skipped["occupied"] += 1
        if position is not None:
            p = position
            effective_stop, stop_reason = p["stop"], "sl"
            if cash:
                floor = p["entry"] + p["side"]*((900_000-balance)/p["qty"]+cost)
                if p["side"]*(floor-effective_stop) >= 0:
                    effective_stop, stop_reason = floor, "account_floor"
            if exit_price is None:
                exit_price, reason = fill_bar(op, hi, lo, cl, p["side"], effective_stop, p["target"], stop_reason)
            if not complete[i]:
                p["incomplete_bars"] += 1
                if exit_price is None:
                    exit_price, reason = cl, "incomplete_bar_close"
            if exit_price is None and t % 86400 == 85500:
                exit_price, reason = cl, "daily_close"
            if exit_price is None and i-p["entry_index"]+1 >= 96:
                exit_price, reason = cl, "max_96_bars"
            if exit_price is None and k == len(indices)-1:
                exit_price, reason = cl, "period_end_mark"
            if cash:
                # After a protective exit the remainder of that bar is not exposure.
                adverse = exit_price if exit_price is not None and ("sl" in reason or "account_floor" in reason or "gap" in reason) else (lo if p["side"] == 1 else hi)
                worst = balance+p["qty"]*(p["side"]*(adverse-p["entry"])-cost)
                minimum_equity = min(minimum_equity, worst)
                intrabar_dd = max(intrabar_dd, peak_equity-worst)
            if exit_price is not None:
                gross = p["side"]*(exit_price-p["entry"])
                net = gross-cost
                pnl = net*p["qty"]
                if cash:
                    balance += pnl
                    if reason.startswith("account_floor") or balance <= 900_000+1e-7:
                        halted, stop_time = True, stamp(observed_open_times[i] if "gap" in reason else t+900)
                rows.append(dict(**p, exit_time=int(observed_open_times[i]) if "gap" in reason else t+900,
                                 exit_price=float(exit_price), reason=reason, cost_price=cost,
                                 gross_r=float(gross/p["risk"]), net_r=float(net/p["risk"]),
                                 net_price=float(net), pnl_yen=float(pnl) if cash else 0.0,
                                 balance_yen=float(balance) if cash else 0.0))
                position = None
        equity = balance
        if position is not None:
            equity += position["qty"]*(position["side"]*(cl-position["entry"])-cost)
        if cash:
            peak_equity = max(peak_equity, equity)
            minimum_equity = min(minimum_equity, equity)
            curve.append((t+900, equity))
    account = dict(final_equity_yen=balance, net_yen=balance-1_000_000, stopped=halted,
                   stop_time_source=stop_time, minimum_equity_yen=minimum_equity,
                   max_observed_intrabar_drawdown_yen=intrabar_dd, skipped=skipped)
    return rows, np.asarray(curve, dtype=float).reshape(-1, 2), account


def metrics(rows):
    r = np.array([x["net_r"] for x in rows])
    positive, negative = r[r > 0].sum(), -r[r < 0].sum()
    cumulative = np.r_[0.0, np.cumsum(r)]
    return dict(trades=len(rows), net_r=float(r.sum()), mean_net_r=float(r.mean()) if len(r) else 0.0,
                pf=float(positive/negative) if negative else None,
                wins=int((r > 0).sum()), max_closed_trade_dd_r=float((np.maximum.accumulate(cumulative)-cumulative).max()),
                incomplete_exposed_trades=sum(x["incomplete_bars"] > 0 for x in rows))


def months(start, end):
    first = np.datetime64(stamp(start)[:7], "M")
    last = np.datetime64(stamp(end)[:7], "M")
    return [str(x) for x in np.arange(first, last, dtype="datetime64[M]")]


def monthly(rows, start, end, cash=False, curve=None):
    result, prior = [], 1_000_000.0
    for month in months(start, end):
        selected = [r for r in rows if stamp(r["exit_time"]-(0 if "gap" in r["reason"] else 1))[:7] == month]
        row = dict(month=month, **metrics(selected))
        if cash:
            boundary = epoch(str(np.datetime64(month, "M")+1))
            available = curve[curve[:, 0] <= boundary]
            equity = float(available[-1, 1]) if len(available) else prior
            row.update(pnl_yen=equity-prior, equity_yen=equity, goal_met=equity-prior >= 3_000_000)
            prior = equity
        result.append(row)
    return result


def save_trades(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        fields = list(rows[0]) if rows else ["entry_time", "exit_time", "net_r"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run():
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN" or protocol["candidate_budget"] != 2:
        raise ValueError("A frozen two-arm protocol is required")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), protocol_sha256=digest(DOC/"protocol.json"),
                    code_sha256=digest(__file__), tests_sha256=digest(ROOT/"tests/test_ytt_profit_feasibility.py"),
                    hypothesis_sha256=digest(DOC/"hypothesis.md"), data_inventory_sha256=digest(DOC/"data_inventory.md"),
                    plan_sha256=digest(DOC/"plan.md"), inputs=[])
    dump(OUT/"run_manifest.json", manifest)
    meta = json.loads((ROOT/protocol["data_manifest"]).read_text(encoding="utf-8"))
    masks = json.loads((ROOT/protocol["complete_m5_directory"]/"run_manifest.json").read_text(encoding="utf-8"))["inputs"]
    records, cash_records, all_trades = [], [], {}
    for symbol in protocol["symbols"]:
        m = next(x for x in meta if x["symbol"] == symbol)
        mask_info = next(x for x in masks if x["symbol"] == symbol)
        cache = ROOT/protocol["cache_directory"]/f"{symbol}_features.npz"
        mask = ROOT/protocol["complete_m5_directory"]/f"{symbol}_complete_m5.npz"
        if digest(cache) != m["cache_sha256"] or digest(mask) != mask_info["mask_sha256"]:
            raise ValueError(f"Input hash mismatch: {symbol}")
        with np.load(cache, allow_pickle=False) as z:
            times, prices = z["times"], z["features"][:, :4]
        with np.load(mask, allow_pickle=False) as z:
            complete = z["complete"]
        if len(complete) != len(times) or np.any(np.diff(times) <= 0) or not np.isfinite(prices).all():
            raise ValueError("Invalid aligned input")
        t, p, valid, at_open, observed_open_times = aggregate(times, prices, complete, 900)
        observed_open_times, at_open, raw_hash = raw_open_metadata(symbol, m, t)
        selected = np.flatnonzero(valid)
        state = states(p[valid])
        htfs = []
        for width in (3600, 14400):
            ht, hp, hv, _, _ = aggregate(times, prices, complete, width)
            hs = states(hp[hv])
            htfs.append(previous_htf(t[valid], ht[hv], hs["direction"], width))
            np.savez_compressed(OUT/f"{symbol}_{width}_states.npz", times=ht[hv], prices=hp[hv], **hs)
        ss, sl, levels = signals(p[valid], state, *htfs, m["tick"])
        sides, stops, thresholds = np.zeros((2, len(t)), np.int8), np.full((2, len(t)), np.nan), np.full((2, len(t)), np.nan)
        sides[:, selected], stops[:, selected], thresholds[:, selected] = ss, sl, levels
        np.savez_compressed(OUT/f"{symbol}_prepared.npz", times=t, prices=p, complete=valid, starts_at_open=at_open,
                            observed_open_times=observed_open_times,
                            sides=sides, stops=stops, thresholds=thresholds, complete_indices=selected,
                            h1=htfs[0], h4=htfs[1], **state)
        manifest["inputs"].append(dict(symbol=symbol, cache_sha256=digest(cache), mask_sha256=digest(mask),
                                       raw_sha256=raw_hash, exact_open_count=int(at_open.sum()),
                                       m15_total=len(t), m15_complete=int(valid.sum())))
        for arm_index, arm in enumerate(ARMS):
            for multiplier in (1, 2):
                cost = (protocol["cost_and_fill_model"]["spread_pips"][symbol]+.4)*m["pip"]*multiplier
                for period, dates in protocol["periods"].items():
                    start, end = map(epoch, dates)
                    rows, _, _ = simulate(t, p, valid, at_open, sides[arm_index], stops[arm_index], thresholds[arm_index], start, end, cost, observed_open_times=observed_open_times)
                    name = f"{symbol}_{arm}_{period}_cost{multiplier}"
                    save_trades(OUT/f"{name}.csv", rows)
                    dump(OUT/f"{name}_monthly.json", monthly(rows, start, end))
                    records.append(dict(symbol=symbol, arm=arm, period=period, cost_multiplier=multiplier, **metrics(rows)))
                    all_trades.setdefault((arm, period, multiplier), []).extend(rows)
                if symbol == "USDJPY":
                    periods = dict(protocol["periods"], continuous=["2020-01-01", "2026-01-01"])
                    for period, dates in periods.items():
                        start, end = map(epoch, dates)
                        rows, curve, account = simulate(t, p, valid, at_open, sides[arm_index], stops[arm_index], thresholds[arm_index], start, end, cost, cash=True, observed_open_times=observed_open_times)
                        name = f"JPY_USDJPY_{arm}_{period}_cost{multiplier}"
                        save_trades(OUT/f"{name}.csv", rows)
                        np.savez_compressed(OUT/f"{name}_equity.npz", curve=curve)
                        mm = monthly(rows, start, end, cash=True, curve=curve)
                        dump(OUT/f"{name}_monthly.json", mm)
                        profit = np.array([x["pnl_yen"] for x in mm])
                        close_eq = np.r_[1_000_000, curve[:, 1]]
                        cash_records.append(dict(arm=arm, period=period, cost_multiplier=multiplier,
                            **account, **metrics(rows), max_close_drawdown_yen=float((np.maximum.accumulate(close_eq)-close_eq).max()),
                            months=len(mm), months_reaching_3m=int((profit >= 3_000_000).sum()),
                            monthly_median_yen=float(np.median(profit)), monthly_best_yen=float(profit.max()), monthly_worst_yen=float(profit.min())))
        print(f"COMPLETED {symbol}", flush=True)
    combined = [dict(arm=a, period=p, cost_multiplier=c, **metrics(sorted(rows, key=lambda r: (r["exit_time"], r["entry_time"]))))
                for (a, p, c), rows in all_trades.items()]
    gate_rows = []
    for period in ("validation", "latest_descriptive"):
        normal = next(r for r in combined if r["arm"] == ARMS[0] and r["period"] == period and r["cost_multiplier"] == 1)
        stress = next(r for r in combined if r["arm"] == ARMS[0] and r["period"] == period and r["cost_multiplier"] == 2)
        baseline = next(r for r in combined if r["arm"] == ARMS[1] and r["period"] == period and r["cost_multiplier"] == 1)
        profitable = sum(r["net_r"] > 0 for r in records if r["arm"] == ARMS[0] and r["period"] == period and r["cost_multiplier"] == 1)
        gates = dict(count=normal["trades"] >= 100, pf=normal["pf"] is not None and normal["pf"] >= 1.2,
                     net=normal["net_r"] > 0, stress=stress["net_r"] > 0, currencies=profitable >= 2,
                     baseline=normal["mean_net_r"] >= baseline["mean_net_r"])
        gate_rows.append(dict(period=period, gates=gates, all_pass=all(gates.values()), profitable_currencies=profitable))
    result = dict(experiment_id=ID, researcher_disposition="NEEDS_EVIDENCE" if all(r["all_pass"] for r in gate_rows) else "GATES_FAILED_PENDING_INDEPENDENT_VALIDATION",
                  records=records, combined_trade_statistics_not_portfolio=combined, gates=gate_rows, usd_jpy_accounts=cash_records,
                  limitations=["All periods previously viewed", "Swap omitted and source timezone unknown", "Pine tie behavior not runtime-confirmed", "Complete-bar feed differs from TradingView", "No live orders; no guaranteed future income"])
    dump(OUT/"results.json", result)
    manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["results_sha256"] = digest(OUT/"results.json")
    dump(OUT/"run_manifest.json", manifest)
    print("RESULT_JSON="+str(OUT/"results.json"), flush=True)


if __name__ == "__main__":
    run()
