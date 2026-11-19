"""Patrick K10 with an inclusive, same-UTC-week VA filter at both order stages."""
import json
from pathlib import Path

import numpy as np
from numba import njit

import backtest_patrick_reverse_costfilter as baseline

base, reference = baseline.base, baseline.reference
DAY, WEEK = baseline.DAY, baseline.WEEK
close_trade = baseline.close_trade
DELAYED_REACCELERATION = 10
CHANNEL_SLOPE = 11
CHANNEL_WALL = 12


@njit(cache=True)
def passes_preentry_filter(times, prices, i, decision_time, side, decision_open, aligned_move, fill_filter):
    # The fill uses only the current open and the 15 complete preceding bars.
    first = i - 15
    if first < 0:
        return False
    for offset in range(15):
        if times[first + offset] != decision_time + 60 * offset:
            return False
    if fill_filter == 6:
        return side * (prices[i, 0] - prices[i - 5, 0]) > 0

    high = np.max(prices[first:i, 1])
    low = np.min(prices[first:i, 2])
    if fill_filter == 5:
        close = prices[i - 1, 3]
        distance_from_edge = high - close if side == 1 else close - low
        return high > low and distance_from_edge <= (high - low) / 3

    adverse_move = decision_open - low if side == 1 else high - decision_open
    if not max(0.0, adverse_move) <= aligned_move / 2:
        return False
    if fill_filter == 7:
        return True

    first_move = side * (prices[i - 10, 0] - decision_open)
    middle_move = side * (prices[i - 5, 0] - prices[i - 10, 0])
    last_move = side * (prices[i, 0] - prices[i - 5, 0])
    epsilon = 1e-10  # Ignore float subtraction noise at equal quoted moves.
    if fill_filter == 8:
        return (first_move > epsilon and middle_move - first_move > epsilon
                and last_move - middle_move > epsilon)
    return (first_move > epsilon and first_move - middle_move > epsilon
            and last_move > epsilon and last_move - middle_move > epsilon)


@njit(cache=True)
def projected_channel(times, prices, i):
    """Return slope and parallel boundaries from the last 32 complete M15 bars."""
    bar_count = 32
    minutes_per_bar = 15
    first = i - bar_count * minutes_per_bar
    if first < 0:
        return np.nan, np.nan, np.nan
    for minute in range(first, i):
        if times[minute] != times[i] - (i - minute) * 60:
            return np.nan, np.nan, np.nan

    first_close = prices[first + minutes_per_bar - 1, 3]
    mean_x = (bar_count - 1) / 2
    close_sum = covariance_sum = x_squared_sum = 0.0
    for bar in range(bar_count):
        close = prices[first + (bar + 1) * minutes_per_bar - 1, 3] - first_close
        centered_x = bar - mean_x
        close_sum += close
        covariance_sum += centered_x * close
        x_squared_sum += centered_x ** 2
    slope = covariance_sum / x_squared_sum
    intercept = close_sum / bar_count - slope * mean_x

    upper_offset = -np.inf
    lower_offset = np.inf
    for bar in range(bar_count):
        bar_start = first + bar * minutes_per_bar
        fitted = intercept + slope * bar
        for minute in range(bar_start, bar_start + minutes_per_bar):
            upper_offset = max(upper_offset, prices[minute, 1] - first_close - fitted)
            lower_offset = min(lower_offset, prices[minute, 2] - first_close - fitted)
    projected = intercept + slope * bar_count
    return slope, first_close + (projected + upper_offset), first_close + (projected + lower_offset)


@njit(cache=True)
def passes_channel_filter(times, prices, i, side, entry, target, fill_filter):
    slope, upper, lower = projected_channel(times, prices, i)
    if not np.isfinite(slope) or not np.isfinite(upper) or not np.isfinite(lower):
        return False
    if fill_filter == CHANNEL_SLOPE:
        return side * slope > 1e-10
    if side == 1:
        return not entry < upper < target
    return not target < lower < entry


@njit(cache=True)
def should_flip_recent_results(rows, closed, adaptive_rule):
    if adaptive_rule == 1 and closed >= 3:
        return rows[closed - 3, 7] < 0 and rows[closed - 2, 7] < 0 and rows[closed - 1, 7] < 0
    if adaptive_rule == 2 and closed >= 5:
        wins = 0
        for j in range(closed - 5, closed):
            wins += int(rows[j, 7] > 0)
        return wins <= 1
    return False


# Derived from the frozen cost-filter replay. Only candidate and fill guards differ.
@njit(cache=True)
def replay(times, prices, setups, profiles, first_week, ready, begin, end, pip, stress,
           allowed, reverse, min_risk_cost, inside_va, session_decisions=None, fill_filter=0,
           spread_by_session=None, adaptive_rule=0, flip_flags=None, fill_side_mask=None):
    """Replay the fixed strategy or flip eligible fills based on prior closed trades.

    Session spreads, when supplied, are (09:00–03:00, 03:00–09:00) JST in price units.
    The optional flip buffer follows the returned ledger's row order.
    The optional M1 fill-side mask allows its signed side, both sides (2), or neither (0).
    """
    if fill_side_mask is not None and len(fill_side_mask) != len(times):
        raise ValueError('Fill-side mask must match the M1 timeline')
    if spread_by_session is not None:
        if len(spread_by_session) != 2:
            raise ValueError('spread_by_session needs exactly two price widths')
        for value in spread_by_session:
            if not np.isfinite(value) or value < 0:
                raise ValueError('Session spread widths must be finite and nonnegative')
    spread = (2.0 if stress else 1.0) * pip
    slip = (.2 if stress else .1) * pip
    carry = (1.0 if stress else .2) * pip
    filter_cost = spread + 2 * slip + 3 * carry
    delayed = fill_filter == DELAYED_REACCELERATION
    fill_deadline_offset = 45 * 60 if delayed else 15 * 60
    touched = np.zeros(len(setups), dtype=np.bool_)
    used = np.zeros(len(setups), dtype=np.bool_)
    rows = np.zeros((len(setups), 17))  # each setup can be entered at most once
    active = 0
    oldest = 0
    pending = -1
    pending_t = 0
    pending_stop = 0.0
    pending_profile = 0
    pending_low = pending_high = np.nan
    pending_open = 0.0
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
        if spread_by_session is not None:
            jst_second = local % DAY
            spread = spread_by_session[1] if 3 * 3600 <= jst_second < 9 * 3600 else spread_by_session[0]
            filter_cost = spread + 2 * slip + 3 * carry
        decision = ((local // DAY + 3) % 7 < 5 and local % DAY == 8 * 3600
                    if session_decisions is None else session_decisions[i])
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
            wait = t - pending_t
            gap = delayed and times[i - 1] != t - 60
            if (not delayed and wait > 900) or gap:
                missing_active += 1
            if t >= end or touched[pending] or weekend or wait > fill_deadline_offset or gap:
                pending = -1
            elif delayed:
                original_side = setups[pending, 3]
                exit_side = -original_side if reverse else original_side
                quote = o + (spread if exit_side == -1 else 0.0)
                if quote <= min(setups[pending, 7], pending_stop) or quote >= max(setups[pending, 7], pending_stop):
                    pending = -1
        wait = t - pending_t
        fill_due = (20 * 60 <= wait <= fill_deadline_offset and wait % (5 * 60) == 0
                    if delayed else wait == 15 * 60)
        if pending >= 0 and not position and fill_due:
            s = setups[pending]
            planned = o + (spread if s[3] == 1 else 0.0)
            execution_side = -s[3] if reverse else s[3]
            actual = o + (spread if execution_side == 1 else 0.0)
            execution_stop = s[7] if reverse else pending_stop
            execution_target = pending_stop if reverse else s[7]
            original_geometry = s[3] * (s[7] - planned) > 0 and s[3] * (planned - pending_stop) > 0
            execution_geometry = execution_side * (execution_target - actual) > 0 and execution_side * (actual - execution_stop) > 0
            entry_inside = not inside_va or pending_low <= actual <= pending_high
            passes_filter = True
            if fill_filter == 1:
                passes_filter = execution_side * (o - pending_open) >= filter_cost
            elif fill_filter == 2:
                passes_filter = execution_side * (o - pending_open) <= -filter_cost
            elif fill_filter == 3:
                passes_filter = execution_side * (actual - (pending_low + pending_high) / 2) >= 0
            elif fill_filter == 4:
                passes_filter = abs(execution_target - actual) >= .75 * abs(actual - execution_stop)
            elif 5 <= fill_filter <= 9 or fill_filter == CHANNEL_SLOPE or fill_filter == CHANNEL_WALL:
                aligned_move = execution_side * (o - pending_open)
                preentry_mode = fill_filter if fill_filter <= 9 else 7
                passes_filter = aligned_move >= filter_cost and passes_preentry_filter(
                    times, prices, i, pending_t, execution_side, pending_open, aligned_move, preentry_mode
                )
                if passes_filter and fill_filter >= CHANNEL_SLOPE:
                    passes_filter = passes_channel_filter(
                        times, prices, i, execution_side, actual, execution_target, fill_filter
                    )
            elif delayed:
                window_open = prices[i - 15, 0]
                aligned_move = execution_side * (o - window_open)
                passes_filter = aligned_move >= filter_cost and passes_preentry_filter(
                    times, prices, i, t - 15 * 60, execution_side, window_open, aligned_move, 9
                )
            side_allowed = fill_side_mask is None or fill_side_mask[i] == 2 or fill_side_mask[i] == execution_side
            if passes_filter and side_allowed and entry_inside and original_geometry and execution_geometry and (min_risk_cost == 0 or abs(actual - execution_stop) / filter_cost >= min_risk_cost):
                flipped = False
                if adaptive_rule != 0 and should_flip_recent_results(rows, closed, adaptive_rule):
                    flipped_quote = o + (spread if execution_side == -1 else 0.0)
                    if not inside_va or pending_low <= flipped_quote <= pending_high:
                        stop_distance = abs(actual - execution_stop)
                        target_distance = abs(execution_target - actual)
                        execution_side = -execution_side
                        actual = flipped_quote
                        execution_stop = actual - execution_side * stop_distance
                        execution_target = actual + execution_side * target_distance
                        flipped = True
                if flip_flags is not None:
                    flip_flags[closed] = flipped
                side = int(execution_side)
                entered = t
                friday = t // DAY * DAY + ((4 - utc_dow + 7) % 7) * DAY + 20 * 3600
                if friday <= t:
                    friday += WEEK
                deadline = min(t + 3 * DAY, friday)
                entry, stop, target = actual, execution_stop, execution_target
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
            elif not delayed or wait == fill_deadline_offset:
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
                chosen_profile_index = -1
                for back in range(1, 3):
                    pidx = int((week - first_week) // WEEK) - back
                    if pidx < 0 or pidx >= len(profiles):
                        continue
                    level = profiles[pidx, 0 if s[3] == -1 else 1]
                    delta = abs(level - (s[6] if s[3] == -1 else s[5]))
                    if np.isfinite(level) and delta <= 4 * s[4] and delta < distance:
                        best, distance, chosen_week = level, delta, week - back * WEEK
                        chosen_profile_index = pidx
                if not np.isfinite(best):
                    continue
                candidate_stop = max(best, s[6]) + .25 * s[4] if s[3] == -1 else min(best, s[5]) - .25 * s[4]
                quote = o + (spread if s[3] == 1 else 0.0)
                if s[3] * (s[7] - quote) > 0 and s[3] * (quote - candidate_stop) > 0 and abs(quote - best) <= 5 * s[4]:
                    if min_risk_cost > 0:
                        filter_side = -s[3]
                        filter_quote = o + (spread if filter_side == 1 else 0.0)
                        filter_geometry = filter_side * (candidate_stop - filter_quote) > 0 and filter_side * (filter_quote - s[7]) > 0
                        if not filter_geometry or abs(filter_quote - s[7]) / filter_cost < min_risk_cost:
                            continue
                    pending_high, pending_low = profiles[chosen_profile_index, :2]
                    if inside_va and not pending_low <= o + (spread if s[3] == -1 else 0.0) <= pending_high:
                        continue
                    pending, pending_t, pending_stop, pending_profile = j, t, candidate_stop, chosen_week
                    pending_open = o
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
        if delayed and pending >= 0:
            original_side = setups[pending, 3]
            exit_side = -original_side if reverse else original_side
            exit_offset = spread if exit_side == -1 else 0.0
            if l + exit_offset <= min(setups[pending, 7], pending_stop) or h + exit_offset >= max(setups[pending, 7], pending_stop):
                pending = -1
        # Bid extremes can only affect future decisions; never the current open.
        for j in range(oldest, active):
            if t >= setups[j, 2] and ((setups[j, 3] == 1 and h >= setups[j, 7]) or (setups[j, 3] == -1 and l <= setups[j, 7])):
                touched[j] = True
    return rows[:closed], np.array([entries, closed, int(position), int(pending >= 0), decisions, selections, missing_active])


def main():
    prior_dir = baseline.OUT / 'train'
    prior = json.loads((prior_dir / 'result.json').read_text(encoding='utf-8'))
    dates = baseline.STAGE_DATES
    start, begin, end, terminal = (base.stamp(dates[key]) for key in
        ('load_start', 'training_entry_start', 'training_entry_end', 'training_terminal'))
    repository = base.HistoryRepository()
    output = baseline.ROOT / 'agent_runs' / 'patrick_reverse_cost10_inside_va'
    output.mkdir(parents=True, exist_ok=False)
    parts = {}
    summary = []
    for symbol in reference.SYMBOLS:
        for filename, key in [('Bars.dat', 'bars_sha256'), ('info.dat', 'info_sha256')]:
            if base.digest(repository.root / symbol / filename) != prior['manifest'][symbol][key]:
                raise ValueError(f'Source changed: {symbol}/{filename}')
        times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
        setups, profiles, first_week, ready, _ = reference.features(times, prices, volume)
        allowed = np.ones(len(times), dtype=np.bool_)
        pip = .01 if symbol.endswith('JPY') else .0001
        for stress in (False, True):
            scenario = 'stress' if stress else 'normal'
            name = f'{symbol}_{scenario}_C10_trades.npy'
            path = prior_dir / name
            if base.digest(path) != prior['ledger_sha256'][name]:
                raise ValueError(f'Baseline ledger changed: {name}')
            arguments = (times, prices, setups, profiles, first_week, ready, begin, end, pip,
                         stress, allowed, True, 10.)
            original, _ = replay(*arguments, False)
            np.testing.assert_array_equal(original, np.load(path, allow_pickle=False))
            filtered, stats = replay(*arguments, True)
            if len(filtered):
                entries = filtered[:, 0].astype(np.int64)
                side = filtered[:, 2]
                weeks = ((filtered[:, 13].astype(np.int64) - first_week) // WEEK)
                vah, val = profiles[weeks, 0], profiles[weeks, 1]
                selected_quote = prices[np.searchsorted(times, entries - 900), 0] + (side == 1) * pip * (2 if stress else 1)
                fill_quote = filtered[:, 3]
                assert np.all((val <= selected_quote) & (selected_quote <= vah))
                assert np.all((val <= fill_quote) & (fill_quote <= vah))
            np.save(output / name, filtered)
            for mode, ledger in [('baseline', original), ('inside_va', filtered)]:
                parts.setdefault((scenario, mode), []).append(ledger)
                summary.append(dict(symbol=symbol, scenario=scenario, mode=mode,
                                    unresolved=int(stats[2]) if mode == 'inside_va' else 0,
                                    **reference.metrics(ledger)))
        print(f'{symbol}: {len(times)} M1', flush=True)
    pooled = [dict(scenario=scenario, mode=mode, **baseline.pooled_metrics(ledgers))
              for (scenario, mode), ledgers in parts.items()]
    base.write_csv(output / 'summary.csv', summary)
    result = dict(period='2017-01-01 <= Entry UTC < 2020-01-01', pooled=pooled, symbols=summary)
    (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('RESULT_JSON ' + json.dumps(pooled), flush=True)


if __name__ == '__main__':
    main()
