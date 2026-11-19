"""Replay three partial exits on the current Patrick VP entries."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from numba import njit

from backtest_patrick_vp_value_migration import (
    CONTROL,
    MANIFEST,
    PERIODS,
    base,
    baseline,
    read_json,
    reference,
    source_hashes,
    va,
)

EXPERIMENT = "patrick_vp_frequency_exits_20261118"
ROOT = baseline.ROOT
PROTOCOL = ROOT / "docs" / "quant_organization" / "experiments" / EXPERIMENT / "protocol.json"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
JST_OFFSET = 9 * 3600
SESSION_CLOSE = 17 * 3600
DAY = 86400
MODES = ("control", "halfway_tp", "jst17", "jst17_nonpositive")
PARTIAL_FRACTION = 0.5


def validate_protocol():
    protocol = read_json(PROTOCOL)
    if (
        protocol.get("experiment_id") != EXPERIMENT
        or protocol.get("status") != "SPEC_FROZEN"
        or not protocol.get("frozen_at")
        or protocol.get("candidate_budget") != len(MODES) - 1
        or protocol.get("symbols") != reference.SYMBOLS
    ):
        raise ValueError("Frozen Patrick VP partial exits protocol required")
    if base.digest(Path(va.__file__)).lower() != protocol["code_identifier"]["common_replay_sha256"].lower():
        raise ValueError("Common replay differs from the frozen protocol")
    return protocol


@njit(cache=True)
def halfway_exit(times, prices, trade, spread):
    """Return the first partial limit fill within the original position lifetime."""
    entered, closed, side, entry, stop, target = trade[:6]
    midpoint = entry + (target - entry) / 2
    quote_offset = spread if side == -1 else 0.0
    left = np.searchsorted(times, entered)
    right = np.searchsorted(times, closed)
    # A resting partial limit is also filled if the original TP is hit at the open.
    if trade[15] == 3:
        right += 1
    for i in range(left, right):
        opening = prices[i, 0] + quote_offset
        if side * (opening - midpoint) >= 0:
            return times[i], midpoint
        favorable = prices[i, 1 if side == 1 else 2] + quote_offset
        adverse = prices[i, 2 if side == 1 else 1] + quote_offset
        if side * (adverse - stop) > 0 and side * (favorable - midpoint) >= 0:
            return times[i] + 60, midpoint
    return 0, np.nan


@njit(cache=True)
def session_exit(times, prices, trade, spread):
    """Return the first same-day opening at or after the fixed JST time."""
    entered, closed, side = trade[:3]
    local_midnight = ((entered + JST_OFFSET) // DAY) * DAY - JST_OFFSET
    i = np.searchsorted(times, local_midnight + SESSION_CLOSE)
    if i < len(times) and times[i] < min(closed, local_midnight + DAY):
        return times[i], prices[i, 0] + (spread if side == -1 else 0.0)
    return 0, np.nan


@njit(cache=True)
def partial_exits(times, prices, ledger, pip, stress):
    """Aligned events (timestamp, execution quote, full-size-equivalent net R)."""
    spread = (2.0 if stress else 1.0) * pip
    slip = (.2 if stress else .1) * pip
    carry = (1.0 if stress else .2) * pip
    events = np.full((4, len(ledger), 3), np.nan)
    events[:, :, 0] = 0
    for j in range(len(ledger)):
        trade = ledger[j]
        midpoint_at, midpoint_quote = halfway_exit(times, prices, trade, spread)
        session_at, session_quote = session_exit(times, prices, trade, spread)
        for mode, at, quote in ((1, midpoint_at, midpoint_quote), (2, session_at, session_quote)):
            if at == 0:
                continue
            net = trade[2] * (quote - trade[3]) - 2 * slip - (at - trade[0]) / DAY * carry
            events[mode, j, 0] = at
            events[mode, j, 1] = quote
            events[mode, j, 2] = net / trade[16]
            if mode == 2 and net <= 0.0:
                events[3, j] = events[2, j]
    return events


def combine_legs(ledger, events, pip, fraction=PARTIAL_FRACTION):
    """Keep each position as one row and compound the weighted trade outcomes."""
    combined = ledger.copy()
    affected = events[:, 0] != 0
    partial = events[affected]
    if fraction and affected.any():
        gross = combined[affected, 2] * (partial[:, 1] - combined[affected, 3]) / pip
        net = partial[:, 2] * combined[affected, 16] / pip
        combined[affected, 7:10] = (
            (1 - fraction) * combined[affected, 7:10]
            + fraction * np.column_stack((partial[:, 2], gross, net))
        )
    equity = 100.0
    for row in combined:
        row[10] = equity
        row[11] = equity * .01 * row[7]
        equity += row[11]
        row[12] = equity
    return combined


def realized_events(ledger, events, original, currency=False):
    """Return times and realized contributions, splitting around partial exits."""
    affected = events[:, 0] != 0
    remainder = original[:, 7] * np.where(affected, 1 - PARTIAL_FRACTION, 1.0)
    partial = events[affected, 2] * PARTIAL_FRACTION
    if currency:
        remainder = remainder * (ledger[:, 10] * .01)
        partial = partial * (ledger[affected, 10] * .01)
    return np.column_stack((np.r_[ledger[:, 1], events[affected, 0]], np.r_[remainder, partial]))


def event_drawdown(events, initial=None):
    """Measure realized drawdown after summing contributions at identical times."""
    if not len(events):
        return 0.0
    events = events[np.argsort(events[:, 0], kind="stable")]
    starts = np.r_[0, np.flatnonzero(np.diff(events[:, 0])) + 1]
    changes = np.add.reduceat(events[:, 1], starts)
    curve = np.r_[0.0, np.cumsum(changes)]
    if initial is not None:
        curve += initial
    peak = np.maximum.accumulate(curve)
    drawdown = peak - curve
    if initial is not None:
        drawdown = drawdown / peak * 100
    return float(drawdown.max())


def symbols_periods(periods, mode, scenario, symbol, ledger, events, original, parts):
    for period, (left, right) in periods.items():
        mask = (left <= ledger[:, 0]) & (ledger[:, 0] < right)
        subset, partial, bases = ledger[mask], events[mask], original[mask]
        realized_r = realized_events(subset, partial, bases)
        realized_money = realized_events(subset, partial, bases, currency=True)
        part = (subset, partial, realized_r)
        parts.setdefault((mode, scenario, period), []).append(part)
        yield dict(
            symbol=symbol, mode=mode, scenario=scenario, period=period,
            **reference.metrics(subset),
            partial_count=int(np.count_nonzero(partial[:, 0])),
            max_realized_drawdown_r=event_drawdown(realized_r),
            max_realized_drawdown_pct=event_drawdown(realized_money, subset[0, 10] if len(subset) else 100.0),
        )


def pooled_outputs(parts):
    monthly = []
    pooled = []
    month_labels = {}
    for period, (left, right) in PERIODS.items():
        first = np.datetime64(left, "M")
        last = (np.datetime64(right, "D") - np.timedelta64(1, "D")).astype("datetime64[M]")
        month_labels[period] = np.arange(first, last + np.timedelta64(1, "M"), dtype="datetime64[M]")
    for (mode, scenario, period), entries in parts.items():
        ledgers, partials, realized = zip(*entries, strict=True)
        metrics = baseline.pooled_metrics(ledgers)
        active = sum(bool(len(rows)) for rows in ledgers)
        positive = sum(int(rows[:, 7].sum() > 0) for rows in ledgers)
        months = month_labels[period]
        entered = np.concatenate([rows[:, 0] for rows in ledgers])
        groups = entered.astype("datetime64[s]").astype("datetime64[M]").astype(np.int64) - months[0].astype(np.int64)
        counts = np.bincount(groups, minlength=len(months))
        for month, count in zip(months, counts, strict=True):
            monthly.append(dict(mode=mode, scenario=scenario, period=period, month_utc=str(month), trades=int(count)))
        pooled.append(dict(
            mode=mode, scenario=scenario, period=period, **metrics, active_symbols=active, positive_symbols=positive,
            months=len(months), trades_per_month=metrics["closed"] / len(months), months_without_trades=int((counts == 0).sum()),
            partial_count=sum(int(np.count_nonzero(events[:, 0])) for events in partials),
            max_realized_drawdown_r=event_drawdown(np.concatenate(realized)),
        ))
    return pooled, monthly


def main():
    validate_protocol()
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    repository = base.HistoryRepository()
    history = source_hashes(repository, read_json(MANIFEST)["manifest"])
    periods = {label: tuple(map(base.stamp, span)) for label, span in PERIODS.items()}
    start = base.stamp(baseline.STAGE_DATES["load_start"])
    begin, end, terminal = map(base.stamp, ("2017-01-01", "2026-08-28", "2026-08-31"))
    parts, summary, ledger_hashes, control_hashes, replay_counts = {}, [], {}, {}, []
    with TemporaryDirectory(prefix=EXPERIMENT + "_", dir=OUTPUT.parent) as temp:
        output = Path(temp) / "result"
        output.mkdir()
        for symbol in reference.SYMBOLS:
            times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
            setups, profiles, first_week, ready, _ = reference.features(times, prices, volume)
            allowed = np.ones(len(times), dtype=np.bool_)
            pip = .01 if symbol.endswith("JPY") else .0001
            for stress, scenario in ((False, "normal"), (True, "stress")):
                control, counts = va.replay(
                    times, prices, setups, profiles, first_week, ready, begin, end, pip, stress,
                    allowed, True, 10., True, None, 7,
                )
                if counts[0] != counts[1] or counts[2] or counts[3] or np.any(control[:, 10] <= 0):
                    raise ValueError(f"Incomplete control replay: {symbol}/{scenario}")
                previous = CONTROL / f"{symbol}_{scenario}_small_pullback.npy"
                np.testing.assert_array_equal(control, np.load(previous, allow_pickle=False))
                control_hashes[previous.name] = base.digest(previous)
                replay_counts.append(dict(symbol=symbol, scenario=scenario, m1_rows=len(times), entered=int(counts[0]),
                                          closed=int(counts[1]), unresolved=int(counts[2]), pending=int(counts[3])))
                all_events = partial_exits(times, prices, control, pip, stress)
                for mode, events in zip(MODES, all_events, strict=True):
                    np.testing.assert_array_equal(combine_legs(control, events, pip, fraction=0.), control)
                    ledger = combine_legs(control, events, pip)
                    if (np.any(ledger[:, 10] <= 0) or np.any(events[:, 0] > control[:, 1])
                            or not np.array_equal(ledger[:, :7], control[:, :7])):
                        raise ValueError(f"Invalid partial exit or altered entries: {symbol}/{scenario}/{mode}")
                    prefix = f"{symbol}_{scenario}_{mode}"
                    for filename, rows in ((f"{prefix}.npy", ledger), (f"{prefix}_partial.npy", events)):
                        path = output / filename
                        np.save(path, rows, allow_pickle=False)
                        ledger_hashes[filename] = base.digest(path)
                    summary.extend(symbols_periods(periods, mode, scenario, symbol, ledger, events, control, parts))
            print(f"{symbol}: {len(times):,} M1", flush=True)

        pooled, monthly = pooled_outputs(parts)
        result = dict(
            experiment_id=EXPERIMENT, periods=PERIODS, mode_order=MODES, partial_fraction=PARTIAL_FRACTION,
            manifest=history, protocol_sha256=base.digest(PROTOCOL), runner_sha256=base.digest(Path(__file__)),
            source_manifest_sha256=base.digest(MANIFEST), replay_sha256=base.digest(Path(va.__file__)),
            features_sha256=base.digest(Path(reference.__file__)), bars_reader_sha256=base.digest(Path(base.__file__)),
            control_ledger_sha256=control_hashes, output_sha256=ledger_hashes, replay_counts=replay_counts,
            partial_columns=["partial_time_utc", "exit_quote", "net_r_if_full_size"],
            no_partial=["timestamp 0", "price NaN", "R NaN"],
            pooled=pooled,
        )
        base.write_csv(output / "summary.csv", summary)
        base.write_csv(output / "pooled.csv", pooled)
        base.write_csv(output / "monthly.csv", monthly)
        (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        output.rename(OUTPUT)
    print("RESULT_JSON " + json.dumps([row for row in pooled if row["period"] in ("2017-2025", "2026_extra")]), flush=True)


if __name__ == "__main__":
    main()
