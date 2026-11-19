"""Fixed Patrick VA proxy: 08:00 Japan, causal H4/M15, original M1 fills.

This is a volume-profile proxy and a news-unfiltered research variant, not an
exact replication of an identified TradingView indicator. All prices are Bid;
Ask is Bid plus the fixed scenario spread. No market-data downloads occur.
"""
from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import file_digest
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forextester_backtest.data import BAR_STRUCT, HistoryRepository, _RecordFile

DAY = 86400
WEEK = 7 * DAY
OLE_UNIX = 25569


@dataclass
class Bars:
    times: np.ndarray
    ohlc: np.ndarray
    volume: np.ndarray
    counts: np.ndarray


@dataclass(frozen=True)
class Setup:
    key: str
    impulse_start: int
    completed: int
    side: int
    atr: float
    lower: float
    upper: float
    target: float


@dataclass(frozen=True)
class Order:
    setup: Setup
    created: int
    active: int
    expires: int
    entry: float
    stop: float
    target: float
    profile_week: int


def stamp(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


def iso(value):
    return datetime.fromtimestamp(int(value), timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def week_start(at):
    return ((int(at) // DAY + 3) // 7 * 7 - 3) * DAY


def aggregate(times, ohlc, volume, minutes):
    if not len(times):
        return Bars(np.array([], dtype=np.int64), np.empty((0, 4)), np.array([]), np.array([], dtype=int))
    duration = minutes * 60
    buckets = times // duration * duration
    starts = np.r_[0, np.flatnonzero(np.diff(buckets)) + 1]
    ends = np.r_[starts[1:], len(times)]
    values = np.column_stack((ohlc[starts, 0], np.maximum.reduceat(ohlc[:, 1], starts),
                              np.minimum.reduceat(ohlc[:, 2], starts), ohlc[ends - 1, 3]))
    return Bars(buckets[starts], values, np.add.reduceat(volume, starts), ends - starts)


def wilder_atr(ohlc, period=20):
    result = np.full(len(ohlc), np.nan)
    if len(ohlc) < period:
        return result
    previous = np.r_[ohlc[0, 3], ohlc[:-1, 3]]
    tr = np.maximum(ohlc[:, 1] - ohlc[:, 2], np.maximum(abs(ohlc[:, 1] - previous), abs(ohlc[:, 2] - previous)))
    result[period - 1] = np.mean(tr[:period])
    for i in range(period, len(ohlc)):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period
    return result


def volume_profile(ohlc, volume, bins=100):
    """Typical-price allocation; contiguous 70% VA, lower-price tie breaks."""
    if (not len(ohlc) or not np.isfinite(volume).all() or (volume < 0).any()
            or volume.sum() <= 0 or not np.isfinite(ohlc).all()):
        return None
    low, high = float(ohlc[:, 2].min()), float(ohlc[:, 1].max())
    if high <= low:
        return None
    width = (high - low) / bins
    typical = ohlc[:, 1:].mean(axis=1)
    indices = np.clip(np.floor((typical - low) / width).astype(int), 0, bins - 1)
    weights = np.bincount(indices, weights=volume, minlength=bins)
    poc = int(weights.argmax())
    left = right = poc
    total, threshold = float(weights[poc]), float(weights.sum()) * .7
    while total < threshold:
        if right == bins - 1 or (left > 0 and weights[left - 1] >= weights[right + 1]):
            left -= 1
            total += weights[left]
        else:
            right += 1
            total += weights[right]
    return {"val": low + left * width, "vah": low + (right + 1) * width,
            "poc": low + (poc + .5) * width, "total_volume": float(weights.sum()),
            "value_volume": float(total), "rows": len(ohlc)}


def build_profiles(times, ohlc, volume):
    weeks = ((times // DAY + 3) // 7 * 7 - 3) * DAY
    starts = np.r_[0, np.flatnonzero(np.diff(weeks)) + 1]
    ends = np.r_[starts[1:], len(times)]
    return {int(weeks[a]): volume_profile(ohlc[a:b], volume[a:b]) for a, b in zip(starts, ends)}


def detect_setups(h4):
    atr = wilder_atr(h4.ohlc)
    setups = []
    for end in range(28, len(h4.times)):
        first = end - 8
        if not np.all(np.diff(h4.times[first:end + 1]) == 14400):
            continue
        a = float(atr[first - 1])
        if not np.isfinite(a) or a <= 0:
            continue
        impulse, ranging = h4.ohlc[first:first + 3], h4.ohlc[first + 3:end + 1]
        change = float(impulse[-1, 3] - impulse[0, 0])
        lower, upper = float(ranging[:, 2].min()), float(ranging[:, 1].max())
        if abs(change) < 2 * a or upper - lower > a:
            continue
        side = -1 if change > 0 else 1
        if ((side == -1 and lower < impulse[0, 0] + change * .5)
                or (side == 1 and upper > impulse[0, 0] + change * .5)):
            continue
        origin = float(impulse[:, 2].min() if side == -1 else impulse[:, 1].max())
        start = int(h4.times[first])
        setups.append(Setup(f"{start}:{side}", start, int(h4.times[end]) + 14400,
                            side, a, lower, upper, origin))
    return setups


def invalid_since(setup, m15, until):
    """Completed M15 closes invalidate the range; completed extrema invalidate TP."""
    ends = m15.times + 900
    lo, hi = np.searchsorted(ends, [setup.completed, until], side="right")
    bars = m15.ohlc[lo:hi]
    if not len(bars):
        return None
    if np.any((bars[:, 3] < setup.lower - .1 * setup.atr)
              | (bars[:, 3] > setup.upper + .1 * setup.atr)):
        return "range_invalidated"
    if ((setup.side == -1 and np.any(bars[:, 2] <= setup.target))
            or (setup.side == 1 and np.any(bars[:, 1] >= setup.target))):
        return "target_already_touched"
    return None


def select_order(at, setups, profiles, m15, used, spread, current_bid, audit=None):
    available = [s for s in setups if at - DAY <= s.completed <= at]
    if not available:
        return None, "no_recent_setup"
    reasons = []
    for setup in sorted(available, key=lambda s: (s.completed, s.impulse_start), reverse=True):
        order, reason = order_for_setup(at, setup, profiles, m15, used, spread, current_bid)
        if audit is not None:
            audit.append({"time": iso(at), "reason": reason, "setup_key": setup.key, "record_type": "candidate"})
        if order is not None:
            return order, reason
        reasons.append(reason)
    return None, reasons[0]


def order_for_setup(at, setup, profiles, m15, used, spread, current_bid):
    if setup.key in used:
        return None, "setup_already_filled"
    reason = invalid_since(setup, m15, at)
    if reason:
        return None, reason
    current_week = week_start(at)
    matches = []
    for week in (current_week - WEEK, current_week - 2 * WEEK):
        profile = profiles.get(week)
        if profile is None:
            continue
        entry = profile["vah" if setup.side == -1 else "val"]
        distance = abs(entry - (setup.upper if setup.side == -1 else setup.lower))
        if distance <= .1 * setup.atr:
            matches.append((distance, -week, entry, week))
    if not matches:
        return None, "no_valid_matching_profile"
    _, _, entry, week = min(matches)
    stop = (max(entry, setup.upper) + .25 * setup.atr if setup.side == -1
            else min(entry, setup.lower) - .25 * setup.atr)
    if setup.side * (setup.target - entry) <= 0:
        return None, "target_wrong_side"
    if ((setup.side == -1 and current_bid >= entry)
            or (setup.side == 1 and current_bid + spread <= entry)):
        return None, "entry_already_passed"
    return Order(setup, at, at + 900, at + DAY, float(entry), float(stop), setup.target, week), "ordered"


def entry_fill(side, entry, bar, spread):
    # Limits never receive fictitious favorable gap improvement.
    return entry if (bar[2] + spread <= entry if side == 1 else bar[1] >= entry) else None


def exit_fill(side, stop, target, bar, spread, allow_target=True):
    opening, high, low, _ = bar + (spread if side == -1 else 0)
    if (opening <= stop if side == 1 else opening >= stop):
        return float(opening), "stop_gap"
    if allow_target and (opening >= target if side == 1 else opening <= target):
        return target, "target_gap"
    hit_stop = low <= stop if side == 1 else high >= stop
    hit_target = high >= target if side == 1 else low <= target
    if hit_stop:
        return stop, "both_stop_first" if hit_target else "stop"
    if allow_target and hit_target:
        # A favorable TP gap is credited only at the fixed target.
        return target, "target"
    return None


def forced_time(entry):
    deadline = entry + 3 * DAY
    day = entry // DAY * DAY
    weekday = datetime.fromtimestamp(entry, timezone.utc).weekday()
    friday = day + ((4 - weekday) % 7) * DAY + 20 * 3600
    if friday <= entry:
        friday += WEEK
    return min(deadline, friday)


def weekend_block(at):
    day = datetime.fromtimestamp(at, timezone.utc)
    return (day.weekday() == 4 and day.hour >= 20) or day.weekday() == 5 or (day.weekday() == 6 and day.hour < 23)


def daily_schedule(start, end):
    at = start // DAY * DAY + 23 * 3600  # Japan 08:00, no DST.
    if at < start:
        at += DAY
    while at < end:
        if datetime.fromtimestamp(at + 9*3600, timezone.utc).weekday() < 5:
            yield at
        at += DAY


def replay(times, ohlc, setups, profiles, m15, cost, pip, start, end, exit_tail_end=None):
    """One independent account and one position per pair; all timestamps UTC."""
    spread = cost["spread_pips"] * pip
    slip = cost["slip_pips"] * pip
    carry = cost["carry_pips_per_day"] * pip
    schedule = set(daily_schedule(start, end))
    m15_ends = m15.times + 900
    m15_cursor = 0
    used, pending, position = set(), None, None
    equity = 100.0
    trades, events = [], []

    def close(at, price, reason):
        nonlocal position, equity
        order, entered, denominator, capital = position
        days = (at - entered) / DAY
        gross = order.setup.side * (price - order.entry)
        net = gross - 2 * slip - days * carry
        net_r = net / denominator
        pnl = capital * .01 * net_r
        equity += pnl
        trades.append({"setup_key": order.setup.key, "side": order.setup.side,
                       "signal_time": iso(order.setup.completed), "order_time": iso(order.created),
                       "entry_time": iso(entered), "exit_time": iso(at), "entry": order.entry,
                       "stop": order.stop, "target": order.target, "exit": float(price),
                       "risk_denominator": denominator, "holding_days": days,
                       "net_r": net_r, "gross_price_pnl": gross, "slippage_price_cost": 2 * slip,
                       "carry_price_cost": days * carry, "pnl": pnl, "equity_before": capital,
                       "equity": equity, "reason": reason})
        position = None

    terminal_end = end if exit_tail_end is None else exit_tail_end
    previous_bar = None
    for at, bar in zip(times, ohlc):
        at = int(at)
        if at < start:
            continue
        if at >= terminal_end:
            break
        busy_at_schedule = position is not None
        # Existing positions: known opening exits before intraminute extrema.
        if position:
            order, entered, _, _ = position
            if at >= forced_time(entered):
                close(at, bar[0] + (spread if order.setup.side == -1 else 0), "time_exit")
                busy_at_schedule = False
            else:
                fill = exit_fill(order.setup.side, order.stop, order.target, bar, spread)
                if fill:
                    if fill[1] in ("stop_gap", "target_gap"):
                        close(at, *fill)
                        busy_at_schedule = False
                    else:
                        close(at + 60, *fill)
        if pending and at >= end:
            pending = None
        if pending and weekend_block(at):
            events.append({"time": iso(at), "reason": "friday_weekend_cancel", "setup_key": pending.setup.key})
            pending = None
        if pending and at >= pending.expires:
            events.append({"time": iso(at), "reason": "order_expired", "setup_key": pending.setup.key})
            pending = None
        if pending and previous_bar is not None:
            previous_at, previous = previous_bar
            if previous_at >= pending.created and (previous[2] <= pending.target if pending.setup.side == -1 else previous[1] >= pending.target):
                events.append({"time": iso(at), "reason": "target_already_touched", "setup_key": pending.setup.key})
                pending = None
        # Consume all newly available closes, including after a missing boundary
        # M1. A missing 23:15 observation must not hide the known 23:15 close at
        # the next 23:16 open. Earlier closes cannot invalidate a later order.
        first_unprocessed = m15_cursor
        while m15_cursor < len(m15_ends) and m15_ends[m15_cursor] <= at:
            m15_cursor += 1
        if pending:
            for index in range(first_unprocessed, m15_cursor):
                if m15_ends[index] <= pending.created:
                    continue
                row = m15.ohlc[index]
                s = pending.setup
                reason = ("range_invalidated" if row[3] < s.lower - .1*s.atr or row[3] > s.upper + .1*s.atr
                          else "target_already_touched" if (row[2] <= s.target if s.side == -1 else row[1] >= s.target)
                          else None)
                if reason:
                    events.append({"time": iso(at), "reason": reason, "setup_key": s.key,
                                   "known_m15_close": iso(m15_ends[index])})
                    pending = None
                    break
        if pending and position is None and at >= pending.active and not weekend_block(at):
            fill = entry_fill(pending.setup.side, pending.entry, bar, spread)
            if fill is not None:
                denominator = abs(pending.entry - pending.stop) + spread + 2 * slip + 3 * carry
                position = (pending, at, denominator, equity)
                used.add(pending.setup.key)
                events.append({"time": iso(at), "reason": "filled", "setup_key": pending.setup.key})
                # TP-only touch in the entry minute has unknown order: defer it.
                immediate = exit_fill(pending.setup.side, pending.stop, pending.target, bar, spread, False)
                pending = None
                if immediate:
                    close(at + 60, *immediate)
        if at in schedule:
            pending = None  # previous daily order has expired, never stack orders.
            if position or busy_at_schedule:
                events.append({"time": iso(at), "reason": "position_busy"})
            else:
                pending, reason = select_order(at, setups, profiles, m15, used, spread, float(bar[0]), events)
                event = {"time": iso(at), "reason": reason}
                if pending:
                    event.update({"setup_key": pending.setup.key, "entry": pending.entry,
                                  "stop": pending.stop, "target": pending.target,
                                  "active": iso(pending.active), "profile_week": iso(pending.profile_week)})
                events.append(event)
        previous_bar = (at, bar)
    # Right censoring is reported separately and excluded from closed-trade P/L.
    valid = np.flatnonzero((times >= start) & (times < terminal_end))
    if position and len(valid):
        i = int(valid[-1])
        order = position[0]
        events.append({"time": iso(int(times[i])+60), "reason": "unresolved_terminal_position",
                       "setup_key": order.setup.key, "entry_time": iso(position[1]),
                       "entry": order.entry, "stop": order.stop, "target": order.target,
                       "last_mark": float(ohlc[i,3]+(spread if order.setup.side == -1 else 0)),
                       "risk_denominator": position[2]})
    missing = schedule - set(int(x) for x in times[(times >= start) & (times < end)])
    events.extend({"time": iso(x), "reason": "missing_exact_schedule_m1"} for x in sorted(missing))
    return trades, events


def summary(trades):
    r = np.array([t["net_r"] for t in trades])
    pnl = np.array([t["pnl"] for t in trades])
    losses, gains = -pnl[pnl < 0].sum(), pnl[pnl > 0].sum()
    initial = trades[0].get("equity_before", 100.) if trades else 100.
    curve = np.r_[initial, initial + np.cumsum(pnl)]
    peak = np.maximum.accumulate(curve)
    r_losses, r_gains = -r[r < 0].sum(), r[r > 0].sum()
    return {"trades": len(trades), "wins": int((r > 0).sum()), "losses": int((r < 0).sum()),
            "breakevens": int((r == 0).sum()), "win_rate": float((r > 0).mean()) if len(r) else None,
            "profit_factor_account_pnl": float(gains / losses) if losses else None,
            "profit_factor_r": float(r_gains / r_losses) if r_losses else None,
            "net_r": float(r.sum()), "mean_r": float(r.mean()) if len(r) else None,
            "net_profit": float(pnl.sum()), "starting_equity": float(initial), "ending_equity": float(curve[-1]),
            "max_closed_equity_drawdown_pct": float(np.max((peak-curve)/peak)*100)}


def tick_weights(times, cache_path):
    """Cache times are integer Unix MINUTES; caller times are Unix SECONDS.

    Missing tick-minute records remain NaN; never replace them with 0/1.
    """
    with np.load(cache_path, allow_pickle=False) as cache:
        known, counts = cache["times"], cache["counts"]
        if (known.dtype.kind not in "iu" or counts.dtype.kind not in "iu"
                or known.shape != counts.shape or known.ndim != 1
                or np.any(np.diff(known) <= 0) or np.any(counts <= 0)):
            raise ValueError("Invalid minute tick count cache")
        known = known * 60  # Explicit audited cache contract; no unit guessing.
        indices = np.searchsorted(known, times)
        matched = indices < len(known)
        matched[matched] &= known[indices[matched]] == times[matched]
        weights = np.full(len(times), np.nan)
        weights[matched] = counts[indices[matched]]
    return weights


def profile_weights(times, saved_volume, volume_source, cache_path=None):
    if volume_source == "stored_bar_volume":
        return np.asarray(saved_volume)
    if volume_source == "actual_tick_count" and cache_path is not None:
        return tick_weights(times, cache_path)
    raise ValueError("Explicit supported profile volume source required")


def load_minutes(repository, symbol, start, end):
    path = repository.root / symbol / "Bars.dat"
    count = _RecordFile(path, BAR_STRUCT.size).count()
    full = np.memmap(path, mode="r", dtype="<f8", offset=4, shape=(count, 6))
    limits = np.array([start, end]) / DAY + OLE_UNIX
    left, right = np.searchsorted(full[:, 0], limits)
    raw = full[left:right]
    times = np.rint((raw[:, 0] - OLE_UNIX) * DAY).astype(np.int64)
    ohlc = np.asarray(raw[:, [1, 3, 4, 2]])
    volume = np.asarray(raw[:, 5])
    if (not len(times) or np.any(np.diff(times) <= 0) or np.any(times % 60)
            or not np.isfinite(ohlc).all() or (ohlc <= 0).any()
            or np.any(ohlc[:, 1] < np.maximum(ohlc[:, 0], ohlc[:, 3]))
            or np.any(ohlc[:, 2] > np.minimum(ohlc[:, 0], ohlc[:, 3]))):
        raise ValueError(f"Invalid source M1 prices/time: {symbol}")
    return times, ohlc, volume


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path, help="Frozen JSON protocol, no downloads")
    parser.add_argument("--output", required=True, type=Path, help="New output directory; existing paths are refused")
    args = parser.parse_args()
    protocol_bytes = args.protocol.read_bytes()
    p = json.loads(protocol_bytes)
    if p.get("status") != "SPEC_FROZEN" or p.get("strategy_version") != "patrick_vp_jst_v1":
        raise ValueError("A SPEC_FROZEN patrick_vp_jst_v1 protocol is required")
    start, end = stamp(p["start"]), stamp(p["end"])
    if end <= start:
        raise ValueError("Invalid period")
    repository = HistoryRepository(p["history_directory"])
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "protocol.json").write_bytes(protocol_bytes)
    warmup = stamp(p["warmup_start"])
    tail_end = stamp(p["exit_tail_end"])
    if not warmup < start < end <= tail_end:
        raise ValueError("Invalid warmup/evaluation/tail boundaries")
    manifest, results, all_trades, all_events, all_setups = {}, {}, [], [], []
    source_paths = [repository.root / s / n for s in p["symbols"] for n in ("Bars.dat", "info.dat")]
    volume_source = p["volume_source"]
    if volume_source == "actual_tick_count":
        source_paths += [Path(p["tick_counts"][s]) for s in p["symbols"]]
    before = {str(x): digest(x) for x in source_paths}
    for symbol in p["symbols"]:
        print(f"Loading {symbol}", flush=True)
        times, prices, saved_volume = load_minutes(repository, symbol, warmup, tail_end)
        cache_path = p.get("tick_counts", {}).get(symbol)
        volume = profile_weights(times, saved_volume, volume_source, cache_path)
        h4 = aggregate(times, prices, volume, 240)
        m15 = aggregate(times, prices, volume, 15)
        setups = detect_setups(h4)
        profiles = build_profiles(times, prices, volume)
        manifest[symbol] = {"rows": len(times), "first": iso(times[0]), "last": iso(times[-1]),
                            "max_gap_seconds": int(np.max(np.diff(times))), "negative_stored_volume_rows": int((saved_volume < 0).sum()),
                            "volume_source": volume_source,
                            "nonfinite_profile_weight_minutes": int((~np.isfinite(volume)).sum()),
                            "invalid_profile_weeks": [iso(w) for w,v in profiles.items() if v is None],
                            "h4_rows": len(h4.times), "complete_h4_rows": int((h4.counts == 240).sum()),
                            "observed_m15_rows": len(m15.times), "setups_detected_including_warmup_tail": len(setups),
                            "setups_completed_in_entry_window": sum(start <= s.completed < end for s in setups)}
        all_setups.extend({"symbol": symbol, **asdict(s)} for s in setups)
        pip = .01 if symbol.endswith("JPY") else .0001
        for scenario in p["costs"]:
            name = scenario["name"]
            cost = {k: scenario[k] for k in ("spread_pips", "slip_pips", "carry_pips_per_day")}
            if any(not np.isfinite(v) or v < 0 for v in cost.values()):
                raise ValueError("Negative/nonfinite scenario cost")
            trades, events = replay(times, prices, setups, profiles, m15, cost, pip, start, end, tail_end)
            all_trades.extend({"symbol": symbol, "cost": name, **t} for t in trades)
            all_events.extend({"symbol": symbol, "cost": name, **e} for e in events)
            years = range(datetime.fromtimestamp(start,timezone.utc).year,
                          datetime.fromtimestamp(end-1,timezone.utc).year+1)
            periods = {"2017_2020": (2017, 2021), "2021_2022": (2021, 2023), "2023_2024": (2023, 2025)}
            results[f"{symbol}:{name}"] = {"summary": summary(trades),
                "by_entry_year": {str(y): summary([t for t in trades if int(t["entry_time"][:4]) == y]) for y in years},
                "by_entry_period": {label: summary([t for t in trades if first <= int(t["entry_time"][:4]) < last])
                                    for label, (first, last) in periods.items()},
                "unresolved_terminal_positions": [e for e in events if e["reason"] == "unresolved_terminal_position"],
                "reasons": {reason: sum(e["reason"] == reason for e in events) for reason in sorted({e["reason"] for e in events})}}
        del times, prices, volume, saved_volume
    after = {str(x): digest(x) for x in source_paths}
    if before != after or args.protocol.read_bytes() != protocol_bytes:
        raise RuntimeError("Input data or protocol changed during run")
    write_csv(args.output / "trades.csv", all_trades)
    write_csv(args.output / "orders_and_rejections.csv", all_events)
    write_csv(args.output / "setups.csv", all_setups)
    pooled = {}
    for scenario in p["costs"]:
        name = scenario["name"]
        trades = [t for t in all_trades if t["cost"] == name]
        r = np.array([t["net_r"] for t in trades])
        loss = -r[r < 0].sum()
        pooled[name] = {"trades": len(r), "net_r": float(r.sum()),
                        "mean_r": float(r.mean()) if len(r) else None,
                        "profit_factor_r": float(r[r > 0].sum()/loss) if loss else None,
                        "wins": int((r > 0).sum()), "win_rate": float((r > 0).mean()) if len(r) else None}
    payload = {"strategy_version": p["strategy_version"], "news_filter": "not_applied_missing_historical_calendar",
               "volume_proxy": ("stored_bar_volume_unknown_provenance_at_m1_typical_price" if volume_source == "stored_bar_volume"
                                else "original_tick_record_count_per_m1_at_m1_typical_price_not_tick_price_histogram"),
               "price_type": "assumed_bid_ohlc", "cost_type": "assumed_sensitivity_not_observed_execution",
               "adoption_status": "descriptive_only_no_adoption", "results": results,
               "pooled_trade_r_descriptive_not_shared_portfolio": pooled}
    for name, data in (("results.json", payload), ("manifest.json", manifest), ("source_sha256.json", before)):
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print("RESULT_JSON=" + json.dumps(payload, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
