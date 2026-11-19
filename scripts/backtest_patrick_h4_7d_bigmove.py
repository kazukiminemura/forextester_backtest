"""Fixed latest-completed-H4 range filters at JST08 decision; original M1 replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
from numba import njit

import backtest_patrick_h4_7d as reference

base = reference.base
ROOT = reference.ROOT
EXPERIMENT = 'patrick_h4_7d_bigmove_20261107'
DOC = ROOT / 'docs/quant_organization/experiments' / EXPERIMENT
OUT = ROOT / 'agent_runs' / EXPERIMENT
PREVIOUS = ROOT / 'agent_runs/patrick_h4_7d_winrate_20261107_v2'
THRESHOLDS = (0., 1., 2., 3.)
DAY, WEEK = reference.DAY, reference.WEEK
close_trade = reference.close_trade
PERIODS = reference.PERIODS[:3]
DATES = dict(load_start='2009-10-01', entry_start='2017-01-01',
             entry_end='2026-01-01', terminal='2026-01-05')


def latest_h4_ratios(times, prices, volume):
    """Last H4 observable at each current M1 open, divided by ATR before that H4."""
    if not len(times):
        return np.empty(0)
    h4 = base.aggregate(times, prices, volume, 240)
    current = np.searchsorted(h4.times, times // reference.H4 * reference.H4)
    latest = current - 1
    before = latest - 1
    ratios = np.full(len(times), np.nan)
    atr = base.wilder_atr(h4.ohlc)
    valid = before >= 0
    positions = np.flatnonzero(valid)
    last, prior = latest[valid], before[valid]
    known = (h4.times[last] + reference.H4 <= times[valid]) & np.isfinite(atr[prior]) & (atr[prior] > 0)
    positions, last, prior = positions[known], last[known], prior[known]
    ratios[positions] = (h4.ohlc[last, 1] - h4.ohlc[last, 2]) / atr[prior]
    return ratios


def decision_mask(ratios, threshold):
    if threshold not in THRESHOLDS:
        raise ValueError('Threshold outside fixed candidate budget')
    return np.ones(len(ratios), dtype=np.bool_) if threshold == 0 else np.isfinite(ratios) & (ratios >= threshold)


def validate_protocol(protocol, symbols):
    if protocol.get('status') != 'SPEC_FROZEN' or not protocol.get('frozen_at'):
        raise ValueError('Frozen protocol required before economic replay')
    if protocol.get('thresholds_atr') != list(THRESHOLDS) or protocol.get('dates') != DATES:
        raise ValueError('Candidate thresholds or dates differ from fixed contract')
    if protocol.get('symbols') != reference.SYMBOLS or not symbols or len(set(symbols)) != len(symbols):
        raise ValueError('Frozen symbols must be original16; requested symbols unique/nonempty')
    if not set(symbols) <= set(protocol['symbols']):
        raise ValueError('Requested symbol outside frozen universe')
    identifiers = protocol['code_identifier']
    sources = dict(pine_sha256=reference.PINE, runner_sha256=Path(__file__),
                   reference_runner_sha256=Path(reference.__file__), base_helper_sha256=Path(base.__file__))
    for key, path in sources.items():
        if base.digest(path) != identifiers[key]:
            raise ValueError(f'{key} differs from frozen protocol')
    if identifiers['pine_sha256'] != reference.PINE_SHA:
        raise ValueError('Final recovered H4_7D Pine identity required')


def baseline_comparison(rows, previous_rows, begin, end):
    previous = previous_rows[(previous_rows[:, 0] >= begin) & (previous_rows[:, 0] < end)]
    same = np.array_equal(rows, previous)
    return dict(matches=same, current_closed=len(rows), previous_closed=len(previous),
                compared_columns=17, max_absolute_difference=float(np.max(np.abs(rows - previous)))
                if rows.shape == previous.shape and len(rows) else (0. if rows.shape == previous.shape else None))


@njit(cache=True)
def replay(times, prices, setups, profiles, first_week, ready, begin, end, pip, stress, allowed):
    spread = (2.0 if stress else 1.0) * pip
    slip = (.2 if stress else .1) * pip
    carry = (1.0 if stress else .2) * pip
    touched = np.zeros(len(setups), dtype=np.bool_)
    used = np.zeros(len(setups), dtype=np.bool_)
    rows = np.zeros((len(setups), 17))  # each setup can be entered at most once
    active = 0
    oldest = 0
    pending = -1
    pending_t = 0
    pending_stop = 0.0
    pending_profile = 0
    position = False
    entered = 0
    deadline = 0
    side = 0
    entry = stop = target = denominator = capital = 0.0
    profile = key = 0.0
    equity = 100.0
    closed = entries = decisions = selections = missing_active = 0
    for i in range(len(times)):
        t = times[i]
        o, h, l = prices[i, 0], prices[i, 1], prices[i, 2]
        while active < len(setups) and setups[active, 0] <= t:
            active += 1
        while oldest < active and setups[oldest, 1] < t - WEEK:
            oldest += 1
        week = ((t // DAY + 3) // 7 * 7 - 3) * DAY
        utc_dow = (t // DAY + 3) % 7  # Monday=0
        minute_of_day = (t % DAY) // 60
        local = t + 9 * 3600
        decision = (local // DAY + 3) % 7 < 5 and local % DAY == 8 * 3600
        weekend = utc_dow == 5 or (utc_dow == 4 and minute_of_day >= 1200) or (utc_dow == 6 and minute_of_day < 1380)
        # Existing position OPEN path precedes selection and current M1 extremes.
        if position:
            quote = o + (spread if side == -1 else 0.0)
            reason = 0
            if t >= deadline:
                reason = 1
            elif (side == 1 and quote <= stop) or (side == -1 and quote >= stop):
                reason = 2
            elif (side == 1 and quote >= target) or (side == -1 and quote <= target):
                reason = 3
                quote = target
            if reason:
                equity = close_trade(rows, closed, entered, t, side, entry, stop, target,
                                     quote, denominator, capital, equity, pip, slip, carry, profile, key, reason)
                closed += 1
                position = False
        if pending >= 0:
            if t > pending_t + 900:
                missing_active += 1
            if t >= end or touched[pending] or weekend or t > pending_t + 900:
                pending = -1
        if pending >= 0 and not position and t == pending_t + 900:
            s = setups[pending]
            actual = o + (spread if s[3] == 1 else 0.0)
            if s[3] * (s[7] - actual) > 0 and s[3] * (actual - pending_stop) > 0:
                side = int(s[3])
                entered = t
                friday = t // DAY * DAY + ((4 - utc_dow + 7) % 7) * DAY + 20 * 3600
                if friday <= t:
                    friday += WEEK
                deadline = min(t + 3 * DAY, friday)
                entry, stop, target = actual, pending_stop, s[7]
                denominator = abs(entry - stop) + spread + 2 * slip + 3 * carry
                capital = equity
                position = True
                entries += 1
                used[pending] = True
                key, profile = s[1], pending_profile
                quote = o + (spread if side == -1 else 0.0)
                if (side == 1 and quote <= stop) or (side == -1 and quote >= stop):
                    equity = close_trade(rows, closed, entered, t, side, entry, stop, target,
                                         quote, denominator, capital, equity, pip, slip, carry, profile, key, 2)
                    closed += 1
                    position = False
            pending = -1
        if decision and allowed[i] and t >= ready and begin <= t < end and not position:
            decisions += 1
            pending = -1
            for j in range(active - 1, oldest - 1, -1):
                s = setups[j]
                if s[1] < t - WEEK or s[2] > t or used[j] or touched[j]:
                    continue
                best = np.nan
                distance = np.inf
                chosen_week = 0
                for back in range(1, 3):
                    pidx = int((week - first_week) // WEEK) - back
                    if pidx < 0 or pidx >= len(profiles):
                        continue
                    level = profiles[pidx, 0 if s[3] == -1 else 1]
                    delta = abs(level - (s[6] if s[3] == -1 else s[5]))
                    if np.isfinite(level) and delta <= 4 * s[4] and delta < distance:
                        best, distance, chosen_week = level, delta, week - back * WEEK
                if not np.isfinite(best):
                    continue
                candidate_stop = max(best, s[6]) + .25 * s[4] if s[3] == -1 else min(best, s[5]) - .25 * s[4]
                quote = o + (spread if s[3] == 1 else 0.0)
                if s[3] * (s[7] - quote) > 0 and s[3] * (quote - candidate_stop) > 0 and abs(quote - best) <= 5 * s[4]:
                    pending, pending_t, pending_stop, pending_profile = j, t, candidate_stop, chosen_week
                    selections += 1
                    break
        if position:
            exit_h = h + (spread if side == -1 else 0.0)
            exit_l = l + (spread if side == -1 else 0.0)
            stop_hit = exit_l <= stop if side == 1 else exit_h >= stop
            target_hit = exit_h >= target if side == 1 else exit_l <= target
            if stop_hit or target_hit:
                reason = (5 if target_hit else 4) if stop_hit else 6
                quote = stop if stop_hit else target
                equity = close_trade(rows, closed, entered, t + 60, side, entry, stop, target,
                                     quote, denominator, capital, equity, pip, slip, carry, profile, key, reason)
                closed += 1
                position = False
        # Bid extremes can only affect future decisions; never the current open.
        for j in range(oldest, active):
            if t >= setups[j, 2] and ((setups[j, 3] == 1 and h >= setups[j, 7]) or (setups[j, 3] == -1 and l <= setups[j, 7])):
                touched[j] = True
    return rows[:closed], np.array([entries, closed, int(position), int(pending >= 0), decisions, selections, missing_active])



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='+', default=reference.SYMBOLS)
    args = parser.parse_args()
    protocol_path = DOC / 'protocol.json'
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    validate_protocol(protocol, args.symbols)
    previous_manifest = json.loads((PREVIOUS / 'result.json').read_text(encoding='utf-8'))['manifest']
    OUT.mkdir(parents=True, exist_ok=False)
    repository = base.HistoryRepository()
    start, terminal = base.stamp(DATES['load_start']), base.stamp(DATES['terminal'])
    begin, end = base.stamp(DATES['entry_start']), base.stamp(DATES['entry_end'])
    manifest, results, pooled, checks = {}, [], {}, []
    for symbol in args.symbols:
        tick = time.perf_counter()
        bars_sha = base.digest(repository.root / symbol / 'Bars.dat')
        info_sha = base.digest(repository.root / symbol / 'info.dat')
        previous_input = previous_manifest[symbol]
        if bars_sha != previous_input['bars_sha256'] or info_sha != previous_input['info_sha256']:
            raise ValueError(f'{symbol} source differs from baseline study')
        times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
        setups, profiles, first_week, ready, quality = reference.features(times, prices, volume)
        ratios = latest_h4_ratios(times, prices, volume)
        manifest[symbol] = dict(bars_sha256=bars_sha, info_sha256=info_sha,
                                observed_first=base.iso(times[0]), observed_last=base.iso(times[-1]),
                                m1_rows=len(times), **quality)
        pip = .01 if symbol.endswith('JPY') else .0001
        for threshold in THRESHOLDS:
            allowed = decision_mask(ratios, threshold)
            for stress in [False, True]:
                scenario = 'stress' if stress else 'normal'
                rows, stats = replay(times, prices, setups, profiles, first_week, ready,
                                     begin, end, pip, stress, allowed)
                tag = f'{symbol}_{scenario}_A{threshold:g}'
                np.save(OUT / f'{tag}_trades.npy', rows)
                records = reference.trade_records(rows, symbol, scenario)
                for record in records:
                    record['threshold_atr'] = threshold
                base.write_csv(OUT / f'{tag}_trades.csv', records)
                if threshold == 0:
                    old_path = PREVIOUS / f'{symbol}_{scenario}_trades.npy'
                    check = baseline_comparison(rows, np.load(old_path, allow_pickle=False), begin, end)
                    checks.append(dict(symbol=symbol, scenario=scenario, previous_sha256=base.digest(old_path), **check))
                    if not check['matches']:
                        raise ValueError(f'{tag} baseline differs from previous17-column ledger')
                result = dict(symbol=symbol, scenario=scenario, threshold_atr=threshold, period='all',
                              **reference.metrics(rows), total_setups=len(setups),
                              entries=int(stats[0]), unresolved=int(stats[2]), pending=int(stats[3]),
                              decisions=int(stats[4]), selections=int(stats[5]), missing_0815=int(stats[6]))
                results.append(result)
                pooled.setdefault((threshold, scenario, 'all'), []).append(rows)
                for label, left, right in PERIODS:
                    part = rows[(rows[:, 0] >= base.stamp(left)) & (rows[:, 0] < base.stamp(right))]
                    results.append(dict(symbol=symbol, scenario=scenario, threshold_atr=threshold,
                                        period=label, **reference.metrics(part)))
                    pooled.setdefault((threshold, scenario, label), []).append(part)
        print(json.dumps(dict(symbol=symbol, m1=len(times), setups=len(setups),
                              seconds=round(time.perf_counter() - tick, 2))), flush=True)
    aggregated = []
    for (threshold, scenario, period), parts in pooled.items():
        metrics = reference.metrics(np.concatenate(parts))
        for key in ['equity_end', 'max_closed_drawdown_pct', 'pf_equity']:
            metrics.pop(key)
        aggregated.append(dict(threshold_atr=threshold, scenario=scenario, period=period, **metrics))
    base.write_csv(OUT / 'summary.csv', results)
    base.write_csv(OUT / 'pooled.csv', aggregated)
    base.write_csv(OUT / 'baseline_comparison.csv', checks)
    output = dict(experiment_id=EXPERIMENT, status='COMPLETED_DESCRIPTIVE',
                  code_identifier=protocol['code_identifier'], protocol_sha256=base.digest(protocol_path),
                  dates=DATES, thresholds_atr=THRESHOLDS, manifest=manifest,
                  baseline_comparison=checks, results=results, pooled=aggregated)
    (OUT / 'result.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print('RESULT_JSON=' + json.dumps(aggregated), flush=True)


if __name__ == '__main__':
    main()
