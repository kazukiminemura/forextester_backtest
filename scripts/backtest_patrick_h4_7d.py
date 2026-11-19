"""Frozen Patrick H4_7D Pine replica on read-only Forex Tester M1.

Stored timestamps are ASSUMED UTC, prices ASSUMED Bid. No fitting or downloads.
The existing Pine uses a structural target, not a fixed reward/risk ratio.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
from numba import njit

import backtest_patrick_vp_jst as base

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'patrick_h4_7d_winrate_20261107'
DOC = ROOT / 'docs/quant_organization/experiments' / EXPERIMENT
OUT = ROOT / 'agent_runs' / (EXPERIMENT + '_v2')
SYMBOLS = ['AUDJPY', 'AUDUSD', 'CHFJPY', 'EURCHF', 'EURGBP', 'EURHKD',
           'EURJPY', 'EURUSD', 'GBPCHF', 'GBPJPY', 'GBPUSD', 'NZDJPY',
           'NZDUSD', 'USDCAD', 'USDCHF', 'USDJPY']
DAY, WEEK, H4 = 86400, 604800, 14400
PINE = ROOT / 'scripts/tradingview/patrick_vp_jst_weekly_indicator.pine'
PINE_SHA = 'dc31af681b043540f8566b02f41921ec925a9606b4955b46c54e026b32b2f0f9'
REASONS = {1: 'time', 2: 'SL gap', 3: 'TP gap', 4: 'SL', 5: 'SL/TP both -> SL', 6: 'TP'}
PERIODS = [('2017-2019', '2017-01-01', '2020-01-01'),
           ('2020-2022', '2020-01-01', '2023-01-01'),
           ('2023-2025', '2023-01-01', '2026-01-01'),
           ('2026', '2026-01-01', '2026-09-08')]


def features(times, prices, volume):
    """Precompute completed features; availability is next actual M1, not nominal end."""
    h4 = base.aggregate(times, prices, volume, 240)
    atr = base.wilder_atr(h4.ohlc)
    # This matches finishH4->detect exactly, including the accepted initial partial H4.
    first_minutes = np.searchsorted(times, h4.times)
    setups = []
    for last in range(5, len(h4.times) - 1):
        first = last - 4
        a = atr[first - 1]
        if not np.isfinite(a) or a <= 0 or not np.all(np.diff(h4.times[first:last + 1]) == H4):
            continue
        impulse = h4.ohlc[first:first + 3]
        ranging = h4.ohlc[first + 3:last + 1]
        change = impulse[-1, 3] - impulse[0, 0]
        lower, upper = ranging[:, 2].min(), ranging[:, 1].max()
        side = -1 if change > 0 else 1
        if abs(change) < .5 * a or upper - lower > 4 * a:
            continue
        if (side == -1 and lower < impulse[0, 0] + change * .5) or (side == 1 and upper > impulse[0, 0] + change * .5):
            continue
        target = impulse[:, 2].min() if side == -1 else impulse[:, 1].max()
        setups.append([times[first_minutes[last + 1]], h4.times[first],
                       h4.times[last] + H4, side, a, lower, upper, target])
    weeks = ((times // DAY + 3) // 7 * 7 - 3) * DAY
    starts = np.r_[0, np.flatnonzero(np.diff(weeks)) + 1]
    ends = np.r_[starts[1:], len(times)]
    first_week = int(weeks[0])
    profiles = np.full((int((weeks[-1] - first_week) // WEEK) + 1, 2), np.nan)
    valid_weeks = 0
    invalid_volume_weeks = 0
    for k, (left, right) in enumerate(zip(starts, ends)):
        if k == len(starts) - 1 or (k == 0 and times[0] != first_week):
            continue
        p = base.volume_profile(prices[left:right], volume[left:right])
        if p is not None:
            profiles[int((weeks[left] - first_week) // WEEK)] = [p['vah'], p['val']]
            valid_weeks += 1
        elif not np.isfinite(volume[left:right]).all() or (volume[left:right] < 0).any():
            invalid_volume_weeks += 1
    ready_index = 2 if times[0] == first_week else 3
    ready = int(weeks[starts[ready_index]]) if len(starts) > ready_index else 2**62
    return (np.asarray(setups, dtype=float).reshape((-1, 8)), profiles, first_week,
            ready, {'setups': len(setups), 'valid_completed_weeks': valid_weeks,
                    'invalid_volume_weeks': invalid_volume_weeks,
                    'negative_volume_rows': int((volume < 0).sum())})


@njit(cache=True)
def close_trade(rows, n, entered, at, side, entry, stop, target, quote, denominator,
                capital, equity, pip, slip, carry, profile, key, reason):
    gross = side * (quote - entry)
    net = gross - 2 * slip - (at - entered) / DAY * carry
    r = net / denominator
    pnl = capital * .01 * r
    equity += pnl
    rows[n] = np.array([entered, at, side, entry, stop, target, quote, r,
                        gross / pip, net / pip, capital, pnl, equity, profile,
                        key, reason, denominator])
    return equity


@njit(cache=True)
def replay(times, prices, setups, profiles, first_week, ready, begin, end, pip, stress):
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
        if decision and t >= ready and begin <= t < end and not position:
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


def trade_records(rows, symbol, scenario):
    names = ['entry_time', 'exit_time', 'side', 'entry', 'stop', 'target', 'exit',
             'net_r', 'gross_pips', 'net_pips', 'equity_before', 'pnl', 'equity_after',
             'profile_week', 'setup_start', 'reason', 'risk_denominator']
    records = []
    for row in rows:
        record = dict(zip(names, row.tolist()))
        for name in ['entry_time', 'exit_time', 'profile_week', 'setup_start']:
            record[name] = base.iso(record[name])
        record['reason'] = REASONS[int(record['reason'])]
        record.update(symbol=symbol, scenario=scenario)
        records.append(record)
    return records


def metrics(rows):
    r = rows[:, 7]
    pnl = rows[:, 11]
    initial = rows[0, 10] if len(rows) else 100.
    curve = np.r_[initial, initial + np.cumsum(pnl)]
    peaks = np.maximum.accumulate(curve)
    losses = -r[r < 0].sum()
    account_losses = -pnl[pnl < 0].sum()
    # Pine counts pnl>0, not R>0. They differ if anomalous gaps make capital negative.
    return dict(closed=len(rows), wins=int((pnl > 0).sum()), losses=int((pnl < 0).sum()),
                breakevens=int((pnl == 0).sum()), win_rate=float((pnl > 0).mean()) if len(r) else None,
                r_positive_count=int((r > 0).sum()),
                r_positive_rate=float((r > 0).mean()) if len(r) else None,
                nonpositive_entry_capital=int((rows[:, 10] <= 0).sum()),
                pf_r=float(r[r > 0].sum() / losses) if losses else None,
                pf_equity=float(pnl[pnl > 0].sum() / account_losses) if account_losses else None,
                mean_r=float(r.mean()) if len(r) else None, net_r=float(r.sum()),
                net_pips=float(rows[:, 9].sum()), equity_end=float(curve[-1]),
                max_closed_drawdown_pct=float(((peaks - curve) / peaks).max() * 100))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', nargs='+', default=SYMBOLS)
    args = parser.parse_args()
    protocol = json.loads((DOC / 'protocol.json').read_text(encoding='utf-8'))
    if protocol['status'] != 'SPEC_FROZEN' or base.digest(PINE) != PINE_SHA:
        raise ValueError('Frozen protocol and recovered final Pine required')
    if base.digest(__file__) != protocol['code_identifier']['runner_sha256']:
        raise ValueError('Runner differs from frozen protocol')
    if base.digest(base.__file__) != protocol['code_identifier']['base_helper_sha256']:
        raise ValueError('Reused helper differs from frozen protocol')
    if not set(args.symbols) <= set(protocol['symbols']):
        raise ValueError('Symbols outside frozen protocol')
    OUT.mkdir(parents=True, exist_ok=True)
    repository = base.HistoryRepository()
    start, terminal = base.stamp('2009-10-01'), base.stamp('2026-09-08')
    begin = base.stamp('2017-01-01')
    manifest, results, pooled, all_records = {}, [], {}, []
    for symbol in args.symbols:
        tick = time.perf_counter()
        times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
        features_args = features(times, prices, volume)
        setup, profiles, first_week, ready, quality = features_args
        manifest[symbol] = dict(bars_sha256=base.digest(repository.root / symbol / 'Bars.dat'),
                                info_sha256=base.digest(repository.root / symbol / 'info.dat'),
                                observed_first=base.iso(times[0]), observed_last=base.iso(times[-1]),
                                m1_rows=len(times), **quality)
        pip = .01 if symbol.endswith('JPY') else .0001
        for stress in [False, True]:
            scenario = 'stress' if stress else 'normal'
            rows, stats = replay(times, prices, setup, profiles, first_week, ready, begin, terminal, pip, stress)
            np.save(OUT / f'{symbol}_{scenario}_trades.npy', rows)
            records = trade_records(rows, symbol, scenario)
            base.write_csv(OUT / f'{symbol}_{scenario}_trades.csv', records)
            all_records.extend(records)
            result = dict(symbol=symbol, scenario=scenario, period='all', **metrics(rows),
                          entries=int(stats[0]), unresolved=int(stats[2]), pending=int(stats[3]),
                          decisions=int(stats[4]), selections=int(stats[5]), missing_0815=int(stats[6]))
            results.append(result)
            pooled.setdefault((scenario, 'all'), []).append(rows)
            for label, left, right in PERIODS:
                selected = rows[(rows[:, 0] >= base.stamp(left)) & (rows[:, 0] < base.stamp(right))]
                results.append(dict(symbol=symbol, scenario=scenario, period=label, **metrics(selected)))
                pooled.setdefault((scenario, label), []).append(selected)
        print(json.dumps({'symbol': symbol, 'm1': len(times), 'setups': len(setup),
                          'normal_closed': results[-10]['closed'], 'seconds': round(time.perf_counter() - tick, 2)}), flush=True)
    aggregated = []
    for (scenario, label), parts in pooled.items():
        combined = np.concatenate(parts)
        m = metrics(combined)
        # Per-symbol independent unit equity cannot form a portfolio account/DD.
        for k in ['equity_end', 'max_closed_drawdown_pct', 'pf_equity']:
            m.pop(k)
        aggregated.append(dict(scenario=scenario, period=label, **m))
    base.write_csv(OUT / 'summary.csv', results)
    base.write_csv(OUT / 'pooled.csv', aggregated)
    base.write_csv(OUT / 'trades.csv', all_records)
    output = dict(experiment_id=EXPERIMENT, status='COMPLETED_DESCRIPTIVE',
                  pine_sha256=PINE_SHA, runner_sha256=base.digest(__file__),
                  protocol_sha256=base.digest(DOC / 'protocol.json'),
                  assumptions=protocol['cost_and_fill_model'], manifest=manifest,
                  results=results, pooled=aggregated)
    (OUT / 'result.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print('RESULT_JSON=' + json.dumps(aggregated), flush=True)


if __name__ == '__main__':
    main()
