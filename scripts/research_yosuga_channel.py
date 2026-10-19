"""Frozen, source-labelled horizontal-line approximation of the Yosuga method.

No network, AI inference, parameter search, or adoption authority. Prices are
chart OHLC; the explicit cost model is not executable bid/ask tick replay.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ID = "yosuga_channel_20261003"
DOC = ROOT / "docs/quant_organization/experiments" / ID
OUT = ROOT / "agent_runs" / ID / "completed"
ARMS = ("pullback_rr1", "pullback_line_exit", "immediate_turn_rr1")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def validate_prices(times, prices):
    if times.ndim != 1 or prices.shape != (len(times), 4) or not len(times):
        raise ValueError("Expected nonempty aligned N timestamps and Nx4 OHLC")
    if np.any(np.diff(times) <= 0) or np.any(times % 300) or not np.isfinite(prices).all():
        raise ValueError("Unordered/non-M5 timestamps or nonfinite prices")
    o, h, l, c = prices.T
    if np.any(prices <= 0) or np.any(h < np.maximum(o, c)) or np.any(l > np.minimum(o, c)) or np.any(h < l):
        raise ValueError("Invalid OHLC envelope")


def aggregate_m15(times, prices, complete_m5=None):
    """Only exact, complete M5 triplets; availability is final child's close."""
    labels = times // 900 * 900
    starts = np.r_[0, np.flatnonzero(np.diff(labels)) + 1]
    ends = np.r_[starts[1:] - 1, len(times) - 1]
    complete = ((ends - starts == 2) & (times[starts] == labels[starts])
                & (times[ends] == labels[starts] + 600))
    if complete_m5 is not None:
        valid = np.flatnonzero(complete)
        complete[valid] &= np.all(np.column_stack([complete_m5[starts[valid]+j] for j in range(3)]), axis=1)
    starts, ends = starts[complete], ends[complete]
    if not len(starts):
        return np.array([], dtype=np.int64), np.empty((0, 4)), np.array([], dtype=np.int64)
    bars = np.column_stack((prices[starts, 0], np.maximum.reduce([prices[starts+j, 1] for j in range(3)]),
                            np.minimum.reduce([prices[starts+j, 2] for j in range(3)]), prices[ends, 3]))
    return times[starts], bars, ends


def structure(times, prices, width, complete=None):
    """Strict 2-left/2-right pivots and close crosses, evaluated at each close.

    A pivot at k is first available at k+2. Initial break initializes direction;
    only a subsequent opposite break is a reversal. A gap resets structure.
    """
    n = len(times)
    direction, turn = np.zeros(n, dtype=np.int8), np.zeros(n, dtype=np.int8)
    high, low = np.full(n, np.nan), np.full(n, np.nan)
    high_origin, low_origin = np.full(n, -1, dtype=int), np.full(n, -1, dtype=int)
    confirmed_high, confirmed_low = np.full(n, -1, dtype=int), np.full(n, -1, dtype=int)
    broken = np.full(n, np.nan)
    trend, hp, lp, ho, lo = 0, np.nan, np.nan, -1, -1
    complete = np.ones(n, dtype=bool) if complete is None else np.asarray(complete, dtype=bool)
    for i in range(n):
        if not complete[i] or (i and (times[i] - times[i-1] != width or not complete[i-1])):
            trend, hp, lp, ho, lo = 0, np.nan, np.nan, -1, -1
        if i >= 4 and times[i] - times[i-4] == width*4 and complete[i-4:i+1].all():
            k = i-2
            neighbors = [k-2, k-1, k+1, k+2]
            is_high = all(prices[k, 1] > prices[j, 1] for j in neighbors)
            is_low = all(prices[k, 2] < prices[j, 2] for j in neighbors)
            # A dual outside-bar pivot has no observable ordering; omit both.
            if is_high and not is_low:
                hp, ho, confirmed_high[i] = prices[k, 1], k, k
            if is_low and not is_high:
                lp, lo, confirmed_low[i] = prices[k, 2], k, k
        if i and times[i] - times[i-1] == width and complete[i] and complete[i-1]:
            up = np.isfinite(hp) and prices[i-1, 3] <= hp < prices[i, 3]
            down = np.isfinite(lp) and prices[i-1, 3] >= lp > prices[i, 3]
            if up != down:
                new = 1 if up else -1
                if trend == -new:
                    turn[i], broken[i] = new, hp if new == 1 else lp
                trend = new
        direction[i], high[i], low[i], high_origin[i], low_origin[i] = trend, hp, lp, ho, lo
    return dict(direction=direction, turn=turn, high=high, low=low, high_origin=high_origin,
                low_origin=low_origin, confirmed_high=confirmed_high, confirmed_low=confirmed_low, broken=broken)


def candidate(index, side, stop, setup, turn_i, pullback_origin, pullback_confirm, times, prices, lines, tick):
    """Select nearest *known* forward M15 line; common signal-close room gate."""
    close = float(prices[index, 3])
    risk = side*(close-stop)
    if risk < tick - 1e-10:
        return None, "signal_invalid_risk"
    forward = [(side*(price-close), price, origin, confirmed) for price, origin, confirmed in lines
               if side*(price-close) > 1e-10]
    if not forward:
        return None, "no_forward_line"
    room, target, origin, confirmed = min(forward)
    target -= side*tick
    room -= tick
    if room + 1e-10 < risk:
        return None, "signal_line_room"
    return dict(index=int(index), side=int(side), stop=float(stop), line_target=float(target),
                signal_time=int(times[index]+300), setup_index=int(setup["index"]),
                setup_level=float(setup["level"]), retest_index=int(setup["retest"]), turn_index=int(turn_i),
                pullback_origin=int(pullback_origin), pullback_confirm=int(pullback_confirm),
                line_origin=int(origin), line_confirm=int(confirmed)), "signal"


def signals(times, prices, tick, complete=None):
    validate_prices(times, prices)
    complete = np.ones(len(times), dtype=bool) if complete is None else np.asarray(complete, dtype=bool)
    t15, p15, ends = aggregate_m15(times, prices, complete)
    m5, m15 = structure(times, prices, 300, complete), structure(t15, p15, 900)
    at15 = {int(end): j for j, end in enumerate(ends)}
    result = {arm: [] for arm in ARMS}
    counts = Counter()
    setups = {"pullback": None, "immediate": None}
    lines = []
    for i in range(len(times)):
        if not complete[i] or (i and times[i] - times[i-1] != 300):
            counts["gap_cancel"] += sum(s is not None for s in setups.values())
            setups = {"pullback": None, "immediate": None}
        if not complete[i]:
            counts["incomplete_m5"] += 1
            continue
        if i in at15:
            j = at15[i]
            for kind, col in (("confirmed_high", 1), ("confirmed_low", 2)):
                k = int(m15[kind][j])
                if k >= 0:
                    lines.append((float(p15[k, col]), int(ends[k]), i, k))
            lines = [line for line in lines if line[3] >= j-95]
            side = int(m15["turn"][j])
            if side:
                counts["m15_reversals"] += 1
                setups = {name: dict(index=i, side=side, level=float(m15["broken"][j]),
                                     retest=-1, turn=-1, turn_stop=np.nan, pullback=-1,
                                     confirmed=-1, stop=np.nan) for name in setups}
        for name in tuple(setups):
            s = setups[name]
            if s is None:
                continue
            side = s["side"]
            if i-s["index"] > 36:
                counts[f"{name}_expiry"] += 1
                setups[name] = None
                continue
            # The reversal candle cannot itself count as the subsequent retest.
            if i > s["index"] and s["retest"] < 0 and prices[i, 2] <= s["level"] <= prices[i, 1]:
                s["retest"] = i
                counts[f"{name}_retest"] += 1
            if s["retest"] < 0:
                continue
            if s["turn"] >= 0 and int(m5["turn"][i]) == -side:
                counts[f"{name}_opposite_turn_cancel"] += 1
                setups[name] = None
                continue
            if s["turn"] < 0 and int(m5["turn"][i]) == side:
                ref = float(m5["low" if side == 1 else "high"][i])
                if not np.isfinite(ref):
                    counts[f"{name}_missing_turn_pivot"] += 1
                    setups[name] = None
                    continue
                s["turn"], s["turn_stop"] = i, ref
                counts[f"{name}_m5_turn"] += 1
                if name == "immediate":
                    item, reason = candidate(i, side, ref-side*tick, s, i, -1, -1, times, prices,
                                             [line[:3] for line in lines], tick)
                    counts[f"{name}_{reason}"] += 1
                    if item is not None:
                        result["immediate_turn_rr1"].append(item)
                    setups[name] = None
                    continue
            if name != "pullback" or s["turn"] < 0:
                continue
            if s["pullback"] < 0:
                k = int(m5["confirmed_low" if side == 1 else "confirmed_high"][i])
                if k > s["turn"]:
                    extreme = float(prices[k, 2 if side == 1 else 1])
                    if side*(extreme-s["turn_stop"]) > 0:
                        s["pullback"], s["confirmed"], s["stop"] = k, i, extreme-side*tick
                        counts["pullback_confirmed"] += 1
            if s["pullback"] >= 0:
                extreme = s["stop"] + side*tick
                if side*(prices[i, 2 if side == 1 else 1]-extreme) < 0:
                    counts["pullback_extreme_cancel"] += 1
                    setups[name] = None
                    continue
                if side*(prices[i, 3]-prices[i-1, 1 if side == 1 else 2]) > 0:
                    item, reason = candidate(i, side, s["stop"], s, s["turn"], s["pullback"],
                                             s["confirmed"], times, prices, [line[:3] for line in lines], tick)
                    counts[f"pullback_{reason}"] += 1
                    if item is not None:
                        result["pullback_rr1"].append(item)
                        result["pullback_line_exit"].append(dict(item))
                    setups[name] = None
    return result, m5["turn"], dict(counts)


def exit_fill(side, op, hi, lo, stop, target):
    if side*(op-stop) <= 0:
        return op, "gap_stop"
    if side*(op-target) >= 0:
        return op, "gap_target"
    if (lo <= stop if side == 1 else hi >= stop):
        return stop, "stop"
    if (hi >= target if side == 1 else lo <= target):
        return target, "target"
    return None


def trade_metrics(trades):
    r = np.array([t["net_r"] for t in trades])
    pips = np.array([t["net_pips"] for t in trades])
    gp, gl = float(r[r > 0].sum()), float(-r[r < 0].sum())
    carry = np.array([t["carry_penalty_pips"] / t["risk_pips"] for t in trades])
    return dict(trades=len(trades), wins=int(np.sum(r > 0)), win_rate_pct=float(np.mean(r > 0)*100) if len(r) else None,
                gross_profit_r=gp, gross_loss_r=gl, profit_factor_r=gp/gl if gl else None,
                gross_r=float(sum(t["gross_r"] for t in trades)), net_r=float(r.sum()),
                mean_net_r=float(r.mean()) if len(r) else None, net_pips=float(pips.sum()),
                mean_net_pips=float(pips.mean()) if len(r) else None,
                carry_1pip_per_day_net_r=float((r-carry).sum()),
                carry_1pip_per_day_net_pips=float(sum(t["net_pips"]-t["carry_penalty_pips"] for t in trades)),
                exit_reasons=dict(Counter(t["exit_reason"] for t in trades)))


def simulate(times, prices, candidates, turns, pip, tick, arm, cost, start, end, complete=None):
    """Independent arm/pair, next-open entry, fixed initial risk and complete exits."""
    if arm not in ARMS or pip <= 0 or tick <= 0 or cost < 0 or start >= end:
        raise ValueError("Invalid simulation arguments")
    first, last = map(int, np.searchsorted(times, [start, end]))
    complete = np.ones(len(times), dtype=bool) if complete is None else np.asarray(complete, dtype=bool)
    if first == last:
        raise ValueError("Empty period")
    by_index = {s["index"]: s for s in candidates if start <= times[s["setup_index"]] and start <= times[s["index"]] < end}
    if len(by_index) != len([s for s in candidates if start <= times[s["setup_index"]] and start <= times[s["index"]] < end]):
        raise ValueError("Duplicate candidate")
    mtm = np.empty((last-first, 2))
    trades, ledger = [], []
    p = pending = None
    reversal_exit = False
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
            s["status"] = reason
            if reason == "entered":
                p = dict(s, entry_index=i, entry_time=int(times[i]), entry=op, risk_pips=risk/pip,
                         incomplete_m5_held=0, target=s["line_target"] if arm == "pullback_line_exit" else op+s["side"]*risk)
        if p is not None:
            p["incomplete_m5_held"] += int(not complete[i])
            fill = exit_fill(p["side"], op, hi, lo, p["stop"], p["target"])
            # At a scheduled reversal exit, opening gap brackets precede market exit;
            # intrabar brackets occur later than the scheduled opening market fill.
            if reversal_exit and (fill is None or fill[1] not in ("gap_stop", "gap_target")):
                fill = op, "opposite_turn"
            if fill is None and i == last-1:
                fill = cl, "period_end"
            if fill is not None:
                price, reason = fill
                exit_time = int(times[i]+300 if reason == "period_end" else times[i])
                # Intrabar duration unknown; closing timestamp is conservative for carry.
                if reason in ("stop", "target"):
                    exit_time += 300
                gross = p["side"]*(price-p["entry"])/pip
                net = gross-cost
                carry = max(0, exit_time-p["entry_time"])/86400
                trades.append(dict(p, exit_index=i, exit_time=exit_time, exit=float(price), exit_reason=reason,
                                   gross_pips=gross, net_pips=net, gross_r=gross/p["risk_pips"],
                                   net_r=net/p["risk_pips"], cost_pips=cost, carry_penalty_pips=carry))
                realized += net/p["risk_pips"]
                p = None
        reversal_exit = bool(p is not None and arm == "pullback_line_exit" and turns[i] == -p["side"])
        open_r = (p["side"]*(cl-p["entry"])/pip-cost)/p["risk_pips"] if p is not None else 0.
        mtm[offset] = times[i]+300, realized+open_r
        if i in by_index:
            item = dict(by_index[i], status="occupied" if p is not None else "pending_period_end" if i == last-1 else "pending")
            ledger.append(item)
            if p is None and i < last-1:
                pending = item
    summary = trade_metrics(trades)
    summary["trades_exposed_to_incomplete_m5"] = sum(t["incomplete_m5_held"] > 0 for t in trades)
    equity = mtm[:, 1]
    summary["bar_close_mtm_drawdown_r"] = float(np.max(np.maximum.accumulate(np.maximum(equity, 0))-equity))
    summary["candidate_statuses"] = dict(Counter(s["status"] for s in ledger))
    return dict(trades=trades, ledger=ledger, summary=summary, mtm=mtm)


def m1_completeness(entry, times):
    """Read-only source count mask; never silently discard observed exit prices."""
    path = Path(entry["raw_path"])
    if digest(path) != entry["raw_sha256"]:
        raise ValueError("Raw M1 source hash mismatch")
    count = (path.stat().st_size-4)//48
    raw = np.memmap(path, mode="r", dtype="<f8", offset=4, shape=(count, 6))
    # OLE day zero 1899-12-30; Unix day zero 1970-01-01, 25569 days apart.
    # OLE floats can sit infinitesimally below an exact second. Read a one-second
    # guard, round once, then apply integer bounds so the first M1 is not lost.
    a, b = np.searchsorted(raw[:, 0], [(times[0]-1)/86400+25569, (times[-1]+301)/86400+25569])
    t = np.rint((raw[a:b, 0]-25569)*86400).astype(np.int64)
    t = t[(t >= times[0]) & (t < times[-1]+300)]
    if np.any(t % 60) or np.any(np.diff(t) <= 0):
        raise ValueError("Invalid raw M1 timestamps")
    bucket = t//300*300
    starts = np.r_[0, np.flatnonzero(np.diff(bucket))+1]
    ends = np.r_[starts[1:], len(t)]
    if not np.array_equal(bucket[starts], times):
        raise ValueError("M1/M5 timestamp alignment mismatch")
    complete = (ends-starts == 5) & (t[starts] == times) & (t[ends-1] == times+240)
    return complete


def bootstrap_months(trades, start, end):
    """Calendar months shared across pairs preserve synchronous dependence."""
    months = np.arange(np.datetime64(start, "s").astype("datetime64[M]").astype(int),
                       np.datetime64(end, "s").astype("datetime64[M]").astype(int))
    totals, counts = np.zeros(len(months)), np.zeros(len(months))
    for t in trades:
        month = np.datetime64(t["entry_time"], "s").astype("datetime64[M]").astype(int)
        j = int(month-months[0])
        totals[j] += t["net_r"]
        counts[j] += 1
    rng = np.random.default_rng(20261003)
    draws = rng.integers(0, len(months), size=(5000, len(months)))
    denom = counts[draws].sum(axis=1)
    estimates = totals[draws].sum(axis=1)[denom > 0]/denom[denom > 0]
    return dict(ci95_mean_r=np.quantile(estimates, [.025, .975]).tolist() if len(estimates) else [None, None],
                monthly_net_r=totals.tolist(), monthly_trades=counts.astype(int).tolist(),
                first_month=str(np.datetime64(start, "s").astype("datetime64[M]")), draws=5000, seed=20261003)


def combine_curves(curves):
    times = np.unique(np.concatenate([c[:, 0] for c in curves]))
    equity = np.zeros(len(times))
    for curve in curves:
        indices = np.searchsorted(curve[:, 0], times, side="right")-1
        equity += np.where(indices >= 0, curve[np.maximum(indices, 0), 1], 0.)
    return np.column_stack((times, equity))


def run(protocol_path, output):
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN" or protocol["candidate_budget"] != 3 or protocol["arms"] != list(ARMS):
        raise ValueError("Expected frozen three-arm protocol")
    if output.exists():
        raise FileExistsError("Preserve existing outputs; choose a fresh output directory")
    output.mkdir(parents=True)
    dump(output/"protocol.json", protocol)
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), protocol_sha256=digest(protocol_path),
                    code_sha256=digest(__file__), tests_sha256=digest(ROOT/"tests/test_yosuga_channel.py"), inputs=[])
    dump(output/"run_manifest.json", manifest)
    entries = json.loads((ROOT/protocol["data_manifest"]).read_text(encoding="utf-8"))
    summaries, books, curves = [], {}, {}
    for entry in entries:
        symbol = entry["symbol"]
        if symbol not in protocol["symbols"]:
            continue
        path = ROOT/protocol["cache_directory"]/f"{symbol}_features.npz"
        if digest(path) != entry["cache_sha256"]:
            raise ValueError(f"Input hash mismatch: {symbol}")
        with np.load(path, allow_pickle=False) as z:
            times, prices = z["times"].copy(), z["features"][:, :4].copy()
        complete = m1_completeness(entry, times)
        np.savez_compressed(output/f"{symbol}_complete_m5.npz", complete=complete)
        signal_book, turns, stages = signals(times, prices, entry["tick"], complete)
        dump(output/f"{symbol}_signals.json", signal_book)
        dump(output/f"{symbol}_stages.json", stages)
        np.savez_compressed(output/f"{symbol}_turns.npz", turns=turns)
        for period in protocol["periods"]:
            start, end = [int(np.datetime64(period[k], "s").astype(int)) for k in ("start", "end")]
            for arm in ARMS:
                for multiplier in protocol["cost_multipliers"]:
                    cost = protocol["spread_pips"][symbol]*multiplier
                    sim = simulate(times, prices, signal_book[arm], turns, entry["pip"], entry["tick"], arm, cost, start, end, complete)
                    prefix = f"{symbol}_{period['label']}_{arm}_costx{multiplier:g}"
                    dump(output/f"{prefix}_trades.json", sim["trades"])
                    dump(output/f"{prefix}_ledger.json", sim["ledger"])
                    np.savez_compressed(output/f"{prefix}_mtm.npz", mtm=sim["mtm"])
                    summaries.append(dict(symbol=symbol, period=period["label"], arm=arm, cost_multiplier=multiplier, cost_pips=cost, **sim["summary"]))
                    key = (period["label"], arm, multiplier)
                    books.setdefault(key, []).extend(dict(symbol=symbol, **t) for t in sim["trades"])
                    curves.setdefault(key, []).append(sim["mtm"])
        manifest["inputs"].append(dict(symbol=symbol, sha256=entry["cache_sha256"], raw_sha256=entry["raw_sha256"], bars=len(times),
                                       complete_m5=int(complete.sum()), mask_sha256=digest(output/f"{symbol}_complete_m5.npz")))
        dump(output/"run_manifest.json", manifest)
        print(f"COMPLETE {symbol}", flush=True)
    totals = []
    for period in protocol["periods"]:
        start, end = [int(np.datetime64(period[k], "s").astype(int)) for k in ("start", "end")]
        for arm in ARMS:
            for multiplier in protocol["cost_multipliers"]:
                key = (period["label"], arm, multiplier)
                rows = [r for r in summaries if (r["period"], r["arm"], r["cost_multiplier"]) == key]
                combined = combine_curves(curves[key])
                np.savez_compressed(output/f"{period['label']}_{arm}_costx{multiplier:g}_combined_mtm.npz", mtm=combined)
                metrics = trade_metrics(books[key])
                metrics.update(bootstrap_months(books[key], start, end))
                equity = combined[:, 1]
                metrics["bar_close_mtm_drawdown_r"] = float(np.max(np.maximum.accumulate(np.maximum(equity, 0))-equity))
                metrics["positive_pairs"] = sum(r["net_r"] > 0 for r in rows)
                metrics["leave_one_pair_min_net_r"] = min(metrics["net_r"]-r["net_r"] for r in rows)
                metrics["trades_exposed_to_incomplete_m5"] = sum(r["trades_exposed_to_incomplete_m5"] for r in rows)
                totals.append(dict(period=key[0], arm=arm, cost_multiplier=multiplier, **metrics))
    screens = {}
    for arm in ARMS:
        checks = {}
        for period in protocol["periods"][1:]:
            base = next(r for r in totals if r["period"] == period["label"] and r["arm"] == arm and r["cost_multiplier"] == 1.)
            stress = next(r for r in totals if r["period"] == period["label"] and r["arm"] == arm and r["cost_multiplier"] == 1.5)
            checks[period["label"]] = dict(n100=base["trades"] >= 100, pf110=base["profit_factor_r"] is not None and base["profit_factor_r"] >= 1.10,
                mean_positive=base["mean_net_r"] is not None and base["mean_net_r"] > 0,
                ci_positive=base["ci95_mean_r"][0] is not None and base["ci95_mean_r"][0] > 0,
                positive_pairs4=base["positive_pairs"] >= 4, leave_one_positive=base["leave_one_pair_min_net_r"] > 0,
                stress_positive=stress["net_r"] > 0)
        screens[arm] = dict(checks=checks, passed=all(all(c.values()) for c in checks.values()))
    result = dict(experiment_id=ID, status="COMPLETED_DESCRIPTIVE_NOT_ADOPTION", cases=summaries, totals=totals, screens=screens,
                  limitations=protocol["limitations"])
    dump(output/"results.json", result)
    manifest.update(completed_utc=datetime.now(timezone.utc).isoformat(), results_sha256=digest(output/"results.json"), cases=len(summaries))
    dump(output/"run_manifest.json", manifest)
    print("RESULT_JSON="+str(output/"results.json"), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DOC/"protocol.json")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    run(args.protocol, args.output)
