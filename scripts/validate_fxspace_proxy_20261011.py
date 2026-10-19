"""Independent literal replay for the frozen FX SPACE proxy; no strategy edits."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "agent_runs/fxspace_proxy_20261011"
DOC = ROOT / "docs/quant_organization/experiments/fxspace_proxy_20261011"


def aggregate(data, width):
    t, p = data["times"], data["prices"]
    starts = np.r_[0, np.flatnonzero(np.diff(t//width))+1]
    ends = np.r_[starts[1:], len(t)]
    result = []
    for a, b in zip(starts, ends):
        stamp = int(t[a]//width*width)
        complete = (b-a == width//300 and t[a] == stamp and
                    t[b-1] == stamp+width-300 and bool(data["complete"][a:b].all()))
        result.append((stamp, np.array([p[a, 0], max(p[a:b, 1]), min(p[a:b, 2]), p[b-1, 3]]), complete))
    return result


class IndependentFrame:
    def __init__(self, width, tick):
        self.width, self.tick = width, tick
        self.observed = []
        self.highs, self.lows, self.lines = [], [], []
        self.last = None
        self.trend = 0
        self.atr = math.nan

    def consume(self, stamp, price, complete):
        if not complete or self.last is None or stamp-self.last != self.width:
            self.observed = []
            self.atr = math.nan
            if self.width == 300:
                self.trend = 0
        self.last = stamp
        if not complete:
            return
        self.observed.append((stamp, price))
        self.observed = self.observed[-21:]
        known = stamp+self.width
        remaining = []
        for line in self.lines:
            breached = line["kind"]*(price[3]-line["price"]) > line["band"]
            if known-line["known"] <= 8*86400 and not breached:
                remaining.append(line)
        self.lines = remaining
        if len(self.observed) == 21:
            self.atr = sum(max(row[1][1]-row[1][2], abs(row[1][1]-prior[1][3]),
                               abs(row[1][2]-prior[1][3]))
                           for prior, row in zip(self.observed, self.observed[1:]))/20
        if len(self.observed) >= 5:
            latest = self.observed[-5:]
            for kind, col, points in ((1, 1, self.highs), (-1, 2, self.lows)):
                center = latest[2][1][col]
                neighbors = [latest[j][1][col] for j in (0, 1, 3, 4)]
                if all(kind*(center-neighbor) > 0 for neighbor in neighbors):
                    line = dict(price=float(center), origin=int(latest[2][0]), known=known,
                                kind=kind, band=max(self.tick, .1*self.atr) if math.isfinite(self.atr) else self.tick,
                                strength=2 if self.width == 3600 else 1)
                    points.append(line)
                    del points[:-3]
                    if math.isfinite(self.atr):
                        self.lines.append(line)
                        indices = [i for i, x in enumerate(self.lines) if x["kind"] == kind]
                        if len(indices) > 64:
                            self.lines.pop(indices[0])
        if self.width == 300:
            buy = bool(self.highs and price[3] > self.highs[-1]["price"])
            sell = bool(self.lows and price[3] < self.lows[-1]["price"])
            if buy and sell:
                self.trend = 0
            elif buy:
                self.trend = 1
            elif sell:
                self.trend = -1
        elif len(self.highs) >= 2 and len(self.lows) >= 2:
            dh = self.highs[-1]["price"]-self.highs[-2]["price"]
            dl = self.lows[-1]["price"]-self.lows[-2]["price"]
            self.trend = 1 if dh > 0 and dl > 0 else -1 if dh < 0 and dl < 0 else 0


def events_from_ohlc(data, tick, start, end):
    higher = {w: aggregate(data, w) for w in (900, 3600)}
    pointers = {900: 0, 3600: 0}
    states = {w: IndependentFrame(w, tick) for w in (300, 900, 3600)}
    used, scenario = set(), None
    output = {"pullback": {}, "direct": {}}
    t, bars, good = data["times"], data["prices"], data["complete"]
    for i in range(len(t)):
        if t[i] >= end:
            break
        close_time = int(t[i])+300
        before = states[300].trend
        states[300].consume(int(t[i]), bars[i], bool(good[i]))
        is_new_m15 = False
        for w in (3600, 900):
            j = pointers[w]
            while j < len(higher[w]) and higher[w][j][0]+w <= close_time:
                stamp, price, complete = higher[w][j]
                states[w].consume(stamp, price, complete)
                if w == 900 and stamp+w == close_time and complete:
                    is_new_m15 = True
                j += 1
            pointers[w] = j
        if t[i] < start:
            continue
        op, hi, lo, cl = bars[i]
        contiguous = bool(i and t[i]-t[i-1] == 300 and good[i] and good[i-1])
        existed = scenario is not None
        if existed:
            q = scenario
            d = q["side"]
            invalid = (not contiguous or
                       (lo <= q["stop"] if d == 1 else hi >= q["stop"]) or
                       (hi >= q["target"] if d == 1 else lo <= q["target"]) or
                       states[3600].trend != d or i-q["created_i"] > 24 or
                       (q["reversal"] is not None and i-q["reversal"] > 12))
            if invalid:
                scenario = None
            elif q["reversal"] is None:
                if before == -d and states[300].trend == d:
                    q["reversal"] = i
                    pts = states[300].highs if d == 1 else states[300].lows
                    q["threshold"] = pts[-1]["price"]
                    output["direct"][i] = dict(q)
            elif states[300].trend == -d:
                scenario = None
            elif d*(cl-op) < 0:
                q["counter"] += 1
            elif d*(cl-op) > 0 and q["counter"] >= 2:
                if (cl > bars[i-1, 1] if d == 1 else cl < bars[i-1, 2]):
                    output["pullback"][i] = dict(q)
                scenario = None
            else:
                q["counter"] = 0
        if existed or scenario is not None or not is_new_m15 or not contiguous:
            continue
        f15, f60 = states[900], states[3600]
        d = f15.trend
        if not d or f60.trend != d or not math.isfinite(f15.atr) or f15.atr <= 0:
            continue
        support = (f15.lows if d == 1 else f15.highs)[-1]
        key = (d, support["known"])
        if key in used:
            continue
        band = .1*f15.atr
        candidates = sorted((x for x in f15.lines+f60.lines if d*(x["price"]-cl) > 0), key=lambda x: x["price"])
        groups = []
        for line in candidates:
            if groups and line["price"]-groups[-1][-1]["price"] <= band:
                groups[-1].append(line)
            else:
                groups.append([line])
        representatives = []
        for group in groups:
            representative = dict(sorted(group, key=lambda x: (-x["known"], -x["strength"]))[0])
            representative["strength"] = max(x["strength"] for x in group)
            representatives.append(representative)
        if not representatives:
            continue
        obstacle = min(representatives, key=lambda x: d*(x["price"]-cl))
        offset = max(tick, band)
        def rounded(v):
            return (math.floor(v/tick+1e-9) if d == 1 else math.ceil(v/tick-1e-9))*tick
        sl, tp = rounded(support["price"]-d*offset), rounded(obstacle["price"]-d*offset)
        if d*(cl-sl) <= 0 or d*(tp-cl) <= 0:
            continue
        points = f60.highs if d == 1 else f60.lows
        acc = 0
        if len(points) == 3:
            delta = abs(points[2]["price"]-points[1]["price"])-abs(points[1]["price"]-points[0]["price"])
            acc = 1 if delta > tick else -1 if delta < -tick else 0
        used.add(key)
        scenario = dict(side=d, stop=sl, target=tp, created_i=i, scenario_time=close_time,
                        support_time=support["known"], threshold=math.nan, reversal=None,
                        counter=0, acceleration=acc, line_strength=obstacle["strength"])
    return output


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(rows):
    values = [r["net_r"] for r in rows]
    pos = sum(v for v in values if v > 0)
    neg = -sum(v for v in values if v < 0)
    wins = sum(v > 0 for v in values)
    losses = sum(v < 0 for v in values)
    peak = total = drawdown = 0.
    for value in values:
        total += value
        peak = max(peak, total)
        drawdown = max(drawdown, peak-total)
    return dict(trades=len(values), wins=wins,
                win_rate=wins/len(values) if values else None,
                pf=pos/neg if neg else None,
                net_r=sum(values), mean_net_r=sum(values)/len(values) if values else 0.,
                realized_payoff_rr=(pos/wins)/(neg/losses) if wins and losses else None,
                mean_win_r=pos/wins if wins else None, mean_loss_r=-neg/losses if losses else None,
                max_closed_trade_dd_r=drawdown,
                incomplete_exposed_trades=sum(r["incomplete_bars"] > 0 for r in rows),
                reason_counts={reason: sum(r["reason"] == reason for r in rows) for reason in sorted({r["reason"] for r in rows})})


def replay(data, events, min_rr, cost, normal_cost, start, end, cash=False):
    """Sequential fills from independent events. Cost units are quote-price units."""
    ts, bars = data["times"], data["prices"]
    selected = np.flatnonzero((ts >= start) & (ts < end))
    trades, curve = [], []
    balance = 1_000_000.
    minimum = peak = balance
    drawdown = 0.
    halted = False
    position = None
    skipped = dict(occupied=0, missing_entry=0, invalid_risk=0, insufficient_room=0,
                   cost_floor=0, zero_quantity=0, daily_cutoff=0)
    halt_time = None
    for i in selected:
        clock = int(ts[i])
        op, hi, lo, cl = map(float, bars[i])
        gap = i == 0 or clock != int(ts[i-1])+300 or not data["starts_at_open"][i]
        previous = events.get(i-1) if i and int(ts[i-1]) >= start else None
        had_position = position is not None
        exit_price = reason = None
        if had_position and gap:
            exit_price = op
            reason = "data_gap_open"
            if position["side"]*(op-position["target"]) > 0:
                exit_price, reason = position["target"], "data_gap_tp_capped"
        if had_position:
            skipped["occupied"] += int(previous is not None)
        elif previous is not None and not halted:
            side = previous["side"]
            stop, target = previous["stop"], previous["target"]
            risk = side*(op-stop)
            reward = side*(target-op)
            if gap or not data["complete"][i-1]:
                skipped["missing_entry"] += 1
            elif clock % 86400 == 86100:
                skipped["daily_cutoff"] += 1
            elif not math.isfinite(risk+reward) or risk <= 0:
                skipped["invalid_risk"] += 1
            elif normal_cost/risk > .20+1e-12:
                skipped["cost_floor"] += 1
            elif reward/risk < min_rr-1e-12:
                skipped["insufficient_room"] += 1
            else:
                quantity = (math.floor(min(.005*balance/(risk+cost),
                                          25*balance/op)/1000)*1000 if cash else 1.)
                if quantity <= 0:
                    skipped["zero_quantity"] += 1
                else:
                    position = dict(side=side, entry=op, stop=stop, target=target,
                                    risk=risk, qty=quantity, entry_index=int(i),
                                    entry_time=clock, signal_time=int(ts[i-1])+300,
                                    planned_rr=reward/risk, rr=min_rr, incomplete_bars=0,
                                    **{k: previous[k] for k in ("threshold", "scenario_time", "support_time", "acceleration", "line_strength")})
        if position is not None:
            p = position
            side = p["side"]
            protective_stop = side*p["stop"]
            stop_reason = "sl"
            if cash:
                floor = side*p["entry"]+(900_000-balance)/p["qty"]+cost
                if floor >= protective_stop:
                    protective_stop, stop_reason = floor, "account_floor"
            if exit_price is None:
                if side*op <= protective_stop:
                    exit_price, reason = op, stop_reason+"_gap"
                elif side*(op-p["target"]) >= 0:
                    exit_price, reason = p["target"], "tp_gap_capped"
                elif min(side*hi, side*lo) <= protective_stop:
                    exit_price, reason = side*protective_stop, stop_reason
                elif max(side*hi, side*lo) >= side*p["target"]:
                    exit_price, reason = p["target"], "tp"
            if not data["complete"][i]:
                p["incomplete_bars"] += 1
                if exit_price is None:
                    exit_price, reason = cl, "incomplete_bar_close"
            if exit_price is None and clock % 86400 == 86100:
                exit_price, reason = cl, "daily_close"
            if exit_price is None and i-p["entry_index"]+1 >= 48:
                exit_price, reason = cl, "max_48_bars"
            if exit_price is None and i == selected[-1]:
                exit_price, reason = cl, "period_end_mark"
            if cash:
                protective = reason is not None and any(s in reason for s in ("sl", "gap", "account_floor"))
                adverse = exit_price if protective else (lo if side == 1 else hi)
                worst = balance+p["qty"]*(side*(adverse-p["entry"])-cost)
                minimum = min(minimum, worst)
                drawdown = max(drawdown, peak-worst)
            if exit_price is not None:
                gross = side*(exit_price-p["entry"])
                net = gross-cost
                balance += p["qty"]*net if cash else 0
                exit_time = int(data["observed_open_times"][i]) if "gap" in reason else clock+300
                row = dict(p, exit_price=float(exit_price), exit_time=exit_time,
                           reason=reason, gross_r=gross/p["risk"], net_r=net/p["risk"],
                           net_price=net, cost_price=cost, pnl_yen=net*p["qty"] if cash else 0.,
                           balance_yen=balance if cash else 0.)
                trades.append(row)
                position = None
                if cash and (reason.startswith("account_floor") or balance <= 900_000+1e-7):
                    halted, halt_time = True, exit_time
        equity = balance
        if cash and position:
            equity += position["qty"]*(position["side"]*(cl-position["entry"])-cost)
        peak = max(peak, equity)
        minimum = min(minimum, equity)
        curve.append((clock+300, equity))
    account = dict(final_equity_yen=balance, net_yen=balance-1_000_000,
                   stopped=halted, stop_time_source=stamp(halt_time) if halt_time else "", minimum_equity_yen=minimum,
                   max_observed_intrabar_drawdown_yen=drawdown, skipped=skipped)
    return trades, curve, account, skipped


def epoch(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def monthly(rows, start, end, curve=None):
    cursor = datetime.fromtimestamp(start, timezone.utc).replace(day=1)
    result, prior = [], 1_000_000.
    while cursor.timestamp() < end:
        month = cursor.strftime("%Y-%m")
        nxt = cursor.replace(year=cursor.year+1, month=1) if cursor.month == 12 else cursor.replace(month=cursor.month+1)
        subset = [r for r in rows if stamp(r["exit_time"]-(0 if "gap" in r["reason"] else 1))[:7] == month]
        summary = metrics(subset)
        base_keys = ("trades", "net_r", "mean_net_r", "pf", "wins", "max_closed_trade_dd_r", "incomplete_exposed_trades")
        row = dict(month=month, **{k: summary[k] for k in base_keys})
        if curve is not None:
            values = [eq for time, eq in curve if time <= nxt.timestamp()]
            equity = values[-1] if values else prior
            ret = equity/prior-1 if prior > 0 else None
            row.update(pnl_yen=equity-prior, equity_yen=equity, monthly_return=ret,
                       reaches_5_percent=ret is not None and ret >= .05)
            prior = equity
        result.append(row)
        cursor = nxt
    return result


def independent_screen(normal, stress, per_symbol, account, control, gates):
    positives = [max(0, r["net_r"]) for r in per_symbol]
    concentration = max(positives)/sum(positives) if sum(positives) else 1.
    checks = dict(count=normal["trades"] >= gates["aggregate_trades_min"],
                  per_symbol_count=min(r["trades"] for r in per_symbol) >= gates["per_symbol_trades_min"],
                  normal_pf=normal["pf"] is not None and normal["pf"] >= gates["normal_pf_min"],
                  normal_mean=normal["mean_net_r"] > 0,
                  stress_pf=stress["pf"] is not None and stress["pf"] > gates["stress_pf_strict_min"],
                  stress_mean=stress["mean_net_r"] > 0,
                  profitable_symbols=sum(r["net_r"] > 0 for r in per_symbol) >= gates["profitable_symbols_min"],
                  concentration=concentration <= gates["max_positive_symbol_contribution"],
                  no_usdjpy_halt=not account["stopped"],
                  above_control=normal["mean_net_r"] > control["mean_net_r"])
    return dict(passes=all(checks.values()), checks=checks, positive_symbol_concentration=concentration)


COMPARISONS = 0


def compare(actual, expected, location):
    global COMPARISONS
    if isinstance(expected, dict):
        for key, value in expected.items():
            compare(actual[key], value, f"{location}.{key}")
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), (location, len(actual), len(expected))
        for j, value in enumerate(expected):
            compare(actual[j], value, f"{location}[{j}]")
    elif expected is None or isinstance(expected, (str, bool)):
        assert actual == expected, (location, actual, expected)
        COMPARISONS += 1
    else:
        assert math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-7), (location, actual, expected)
        COMPARISONS += 1


def synthetic_checks():
    """Compare execution boundaries with injected intents, separate from data counts."""
    from scripts import research_fxspace_proxy_20261011 as production
    rng = np.random.default_rng(20261011)
    cases = rows_compared = 0
    reasons = set()
    for case in range(30):
        n = 300
        times = np.arange(n, dtype=np.int64)*300+epoch("2020-01-01")
        close = 150+np.cumsum(rng.normal(0, .075, n))
        op = np.r_[close[0], close[:-1]]
        if case % 2:
            op[80] += .7
        high = np.maximum(op, close)+rng.random(n)*.10
        low = np.minimum(op, close)-rng.random(n)*.10
        prices = np.column_stack((op, high, low, close))
        complete = np.ones(n, bool)
        complete[100] = False
        if case % 3 == 0:
            times[151:] += 300
        exact = np.ones(n, bool)
        exact[200] = False
        observed = times.copy()
        observed[200] += 60
        data = dict(times=times, prices=prices, complete=complete, starts_at_open=exact, observed_open_times=observed)
        sig = {k: np.zeros((2, n)) for k in ("sides", "stops", "targets", "thresholds", "scenario_times", "support_times", "acceleration", "strength")}
        events = {}
        for i in range(2, n-1, 3):
            side = 1 if rng.random() > .5 else -1
            risk = rng.uniform(.03, .6)
            stop, target = close[i]-side*risk, close[i]+side*risk*rng.uniform(1., 3.)
            event = dict(side=side, stop=stop, target=target, threshold=close[i],
                         scenario_time=int(times[i]-600), support_time=int(times[i]-3600), acceleration=0, line_strength=1)
            events[i] = event
            for source, own in (("sides", "side"), ("stops", "stop"), ("targets", "target"), ("thresholds", "threshold"),
                                ("scenario_times", "scenario_time"), ("support_times", "support_time"), ("acceleration", "acceleration"), ("strength", "line_strength")):
                sig[source][0, i] = event[own]
        for rr in (1.5, 2.):
            for cash in (False, True):
                for multiplier in (1., 2.):
                    cost = .016*multiplier
                    expected, curve, account, _ = replay(data, events, rr, cost, .016, int(times[0]), int(times[-1])+300, cash)
                    actual, actual_curve, actual_account = production.simulate(data, sig, 0, rr, int(times[0]), int(times[-1])+300, cost, .016, cash)
                    compare(actual, expected, f"synthetic.{case}.{rr}.{cash}.{multiplier}")
                    compare(actual_account, account, "synthetic.account")
                    if cash:
                        np.testing.assert_allclose(actual_curve, curve, rtol=1e-9, atol=1e-7)
                    rows_compared += len(expected)
                    reasons.update(r["reason"] for r in expected)
                    cases += 1
    n = 180
    times = np.arange(n, dtype=np.int64)*300+epoch("2020-01-01")
    data = dict(times=times, prices=np.tile([150., 150.01, 149.8, 150.], (n, 1)),
                complete=np.ones(n, bool), starts_at_open=np.ones(n, bool), observed_open_times=times.copy())
    sig = {k: np.zeros((2, n)) for k in ("sides", "stops", "targets", "thresholds", "scenario_times", "support_times", "acceleration", "strength")}
    events = {}
    for i in range(2, n-1):
        events[i] = dict(side=1, stop=149.92, target=150.24, threshold=150., scenario_time=int(times[i]),
                         support_time=int(times[i]-600), acceleration=0, line_strength=1)
        for source, own in (("sides", "side"), ("stops", "stop"), ("targets", "target"), ("thresholds", "threshold"),
                            ("scenario_times", "scenario_time"), ("support_times", "support_time"), ("acceleration", "acceleration"), ("strength", "line_strength")):
            sig[source][0, i] = events[i][own]
    expected, curve, account, _ = replay(data, events, 2., .016, .016, int(times[0]), int(times[-1])+300, True)
    actual, actual_curve, actual_account = production.simulate(data, sig, 0, 2., int(times[0]), int(times[-1])+300, .016, .016, True)
    compare(actual, expected, "synthetic.account_floor_trades")
    compare(actual_account, account, "synthetic.account_floor")
    assert account["stopped"] and expected[-1]["reason"].startswith("account_floor")
    np.testing.assert_allclose(actual_curve, curve, rtol=1e-9, atol=1e-7)
    reasons.update(r["reason"] for r in expected)
    rows_compared += len(expected)
    cases += 1
    return dict(seed=20261011, cases=cases, trade_observations=rows_compared, exit_reasons=sorted(reasons))


def run(phase):
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    target = OUT/phase
    actual = json.loads((target/"results.json").read_text(encoding="utf-8"))
    manifest = json.loads((target/"run_manifest.json").read_text(encoding="utf-8"))
    assert manifest.get("completed_utc"), "Research has not completed"
    assert digest(target/"results.json") == manifest["results_sha256"]
    for path, sha in manifest["files"].items():
        assert digest(ROOT/path) == sha, f"Frozen source drift: {path}"
    synthetic = synthetic_checks()
    start, end = map(epoch, protocol["periods"][phase])
    configurations = sorted({(r["arm"], r["rr"]) for r in actual["records"]})
    pooled_rows, accounts, records = {}, {}, []
    count = total_signals = total_bars = prefix_checks = 0
    for symbol in protocol["symbols"]:
        path = OUT/f"{symbol}_m5.npz"
        assert digest(path) == protocol["input_sha256"][symbol]
        with np.load(path, allow_pickle=False) as saved:
            data = {k: saved[k][saved["times"] < end] for k in saved.files}
        total_bars += len(data["times"])
        costs = protocol["cost_and_fill_model"]
        normal = costs["round_trip_pips"][symbol]*costs["pip"][symbol]
        generated = events_from_ohlc(data, costs["tick"][symbol], start, end)
        with np.load(target/f"{symbol}_signals.npz", allow_pickle=False) as signals:
            assert np.array_equal(signals["times"], data["times"])
            for a, arm in enumerate(("pullback", "direct")):
                indices = np.flatnonzero(signals["sides"][a])
                assert list(indices) == list(generated[arm]), f"{symbol}.{arm}.indices"
                for i in indices:
                    event = generated[arm][i]
                    mapping = {"sides": "side", "stops": "stop", "targets": "target", "thresholds": "threshold",
                               "scenario_times": "scenario_time", "support_times": "support_time", "acceleration": "acceleration", "strength": "line_strength"}
                    for source, own in mapping.items():
                        compare(signals[source][a, i], event[own], f"{symbol}.{arm}.signal.{i}.{own}")
                total_signals += len(indices)
        for length in (10_001, 20_002, 30_007):
            if length >= len(data["times"]):
                continue
            prefix_data = {k: val[:length] for k, val in data.items()}
            prefix = events_from_ohlc(prefix_data, costs["tick"][symbol], start, end)
            for arm in generated:
                expected = {i: row for i, row in generated[arm].items() if i < length}
                assert list(prefix[arm]) == list(expected), (symbol, arm, length, "prefix indices")
                for i, event in prefix[arm].items():
                    compare(expected[i], event, f"{symbol}.{arm}.prefix.{length}.{i}")
            prefix_checks += 1
        for arm, rr in configurations:
            for mul in (1, 2):
                key = f"{arm}_rr{rr:g}_cost{mul}"
                rows, _, _, skipped = replay(data, generated[arm], rr, normal*mul, normal, start, end)
                with (target/f"{symbol}_{key}.csv").open(encoding="utf-8", newline="") as stream:
                    compare(list(csv.DictReader(stream)), rows, f"{symbol}.{key}.csv")
                count += len(rows)
                pooled_rows.setdefault(key, []).extend(dict(symbol=symbol, **r) for r in rows)
                record = dict(symbol=symbol, arm=arm, rr=rr, cost_multiplier=mul, **metrics(rows), skipped=skipped,
                              monthly=monthly(rows, start, end),
                              annual=[dict(year=y, **metrics([r for r in rows if int(stamp(r["exit_time"]-(0 if "gap" in r["reason"] else 1))[:4]) == y]))
                                      for y in range(int(stamp(start)[:4]), int(stamp(end)[:4]))])
                existing = next(r for r in actual["records"] if (r["symbol"], r["arm"], r["rr"], r["cost_multiplier"]) == (symbol, arm, rr, mul))
                compare(existing, record, f"{symbol}.{key}.record")
                records.append(record)
                with np.load(target/f"{symbol}_{key}_closed_r_curve.npz") as curve:
                    assert np.array_equal(curve["times"], [r["exit_time"] for r in rows])
                    np.testing.assert_allclose(curve["equity_r"], np.cumsum([r["net_r"] for r in rows]), rtol=1e-9, atol=1e-7)
                if symbol == "USDJPY":
                    cash_rows, cash_curve, account, _ = replay(data, generated[arm], rr, normal*mul, normal, start, end, True)
                    with (target/f"{symbol}_{key}_cash.csv").open(encoding="utf-8", newline="") as stream:
                        compare(list(csv.DictReader(stream)), cash_rows, f"{key}.cash_csv")
                    count += len(cash_rows)
                    with np.load(target/f"{symbol}_{key}_cash_curve.npz") as curve:
                        np.testing.assert_allclose(curve["curve"], cash_curve, rtol=1e-9, atol=1e-7)
                    accounts[key] = dict(**account, **metrics(cash_rows), monthly=monthly(cash_rows, start, end, cash_curve))
                    compare(actual["usdjpy_accounts"][key], accounts[key], f"{key}.account")
        print(f"INDEPENDENT_REPLAY_OK {symbol}", flush=True)
    pooled = {}
    for key, rows in pooled_rows.items():
        rows.sort(key=lambda r: (r["exit_time"], r["symbol"], r["entry_time"]))
        pooled[key] = metrics(rows)
    compare(actual["pooled_equal_r"], pooled, "pooled")
    screens = []
    for item in actual["screens"]:
        arm, rr = item["arm"], item["rr"]
        key = f"{arm}_rr{rr:g}"
        computed = dict(arm=arm, rr=rr, **independent_screen(pooled[key+"_cost1"], pooled[key+"_cost2"],
                        [r for r in records if (r["arm"], r["rr"], r["cost_multiplier"]) == (arm, rr, 1)],
                        accounts[key+"_cost1"], pooled[f"direct_rr{rr:g}_cost1"], protocol["acceptance_gates"]))
        compare(item, computed, f"{key}.screen")
        screens.append(computed)
    passing = [s for s in screens if s["passes"]]
    passing.sort(key=lambda s: (-pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["pf"], -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["mean_net_r"],
                               -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["trades"], s["rr"]))
    selected = {k: passing[0][k] for k in ("arm", "rr")} if passing else None
    compare(actual["selected"], selected, "selected")
    evidence = dict(status="ALL_MATCH", phase=phase, selected=selected, trade_observations=count,
                    signal_observations=total_signals, input_m5_rows=total_bars, compared_scalar_values=COMPARISONS,
                    prefix_future_block_checks=prefix_checks,
                    synthetic_boundary_checks=synthetic,
                    validator_sha256=digest(__file__), result_sha256=digest(target/"results.json"),
                    completed_utc=datetime.now(timezone.utc).isoformat(), screens=screens)
    (target/"independent_validation.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="training")
    run(parser.parse_args().phase)
