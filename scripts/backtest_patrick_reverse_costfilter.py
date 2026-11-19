"""Frozen train-first swap-reverse risk/cost filters; no candidate later-period scan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
from numba import njit

import backtest_patrick_h4_7d_reverse as swapped

bigmove, reference, base = swapped.bigmove, swapped.reference, swapped.base
ROOT = reference.ROOT
EXPERIMENT = 'patrick_reverse_costfilter_20261107'
DOC = ROOT / 'docs/quant_organization/experiments' / EXPERIMENT
OUT = ROOT / 'agent_runs' / EXPERIMENT
PREVIOUS = swapped.OUT
THRESHOLDS = (0., 5., 10., 20.)
STAGE_DATES = dict(load_start='2009-10-01', training_entry_start='2017-01-01',
                   training_entry_end='2020-01-01', training_terminal='2020-01-05',
                   evaluation_entry_start='2017-01-01', evaluation_entry_end='2026-01-01',
                   evaluation_terminal='2026-01-05')
PERIODS = [('training', '2017-01-01', '2020-01-01'),
           ('validation', '2020-01-01', '2023-01-01'),
           ('final', '2023-01-01', '2026-01-01')]
DAY, WEEK = reference.DAY, reference.WEEK
close_trade = reference.close_trade


def validate_protocol(protocol):
    if protocol.get('status') != 'SPEC_FROZEN' or not protocol.get('frozen_at'):
        raise ValueError('Frozen protocol required before economic replay')
    if (protocol.get('thresholds_risk_cost') != list(THRESHOLDS)
            or protocol.get('stage_dates') != STAGE_DATES
            or protocol.get('reverse_mode') != 'swap_absolute_levels'
            or protocol.get('h4_gate') != 'OFF' or protocol.get('symbols') != reference.SYMBOLS):
        raise ValueError('Fixed threshold/date/side/H4/universe contract required')
    sources = dict(pine_sha256=reference.PINE, runner_sha256=Path(__file__),
                   swap_runner_sha256=Path(swapped.__file__), bigmove_runner_sha256=Path(bigmove.__file__),
                   reference_runner_sha256=Path(reference.__file__), base_helper_sha256=Path(base.__file__))
    for key, path in sources.items():
        if base.digest(path) != protocol['code_identifier'][key]:
            raise ValueError(f'{key} differs from frozen protocol')
    if protocol['code_identifier']['pine_sha256'] != reference.PINE_SHA:
        raise ValueError('Final recovered H4_7D Pine identity required')


@njit(cache=True)
def replay(times, prices, setups, profiles, first_week, ready, begin, end, pip, stress, allowed, reverse, min_risk_cost):
    spread = (2.0 if stress else 1.0) * pip
    slip = (.2 if stress else .1) * pip
    carry = (1.0 if stress else .2) * pip
    filter_cost = spread + 2 * slip + 3 * carry
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
            planned = o + (spread if s[3] == 1 else 0.0)
            execution_side = -s[3] if reverse else s[3]
            actual = o + (spread if execution_side == 1 else 0.0)
            execution_stop = s[7] if reverse else pending_stop
            execution_target = pending_stop if reverse else s[7]
            original_geometry = s[3] * (s[7] - planned) > 0 and s[3] * (planned - pending_stop) > 0
            execution_geometry = execution_side * (execution_target - actual) > 0 and execution_side * (actual - execution_stop) > 0
            if original_geometry and execution_geometry and (min_risk_cost == 0 or abs(actual - execution_stop) / filter_cost >= min_risk_cost):
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
                    if min_risk_cost > 0:
                        filter_side = -s[3]
                        filter_quote = o + (spread if filter_side == 1 else 0.0)
                        filter_geometry = filter_side * (candidate_stop - filter_quote) > 0 and filter_side * (filter_quote - s[7]) > 0
                        if not filter_geometry or abs(filter_quote - s[7]) / filter_cost < min_risk_cost:
                            continue
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


def pooled_metrics(parts):
    metrics = reference.metrics(np.concatenate(parts))
    for key in ['equity_end', 'max_closed_drawdown_pct', 'pf_equity']:
        metrics.pop(key)
    return metrics


def selection_recommendation(results, pooled):
    """Use only frozen training aggregates; never inspect candidate later periods."""
    training = {(row['threshold_risk_cost'], row['scenario']): row
                for row in pooled if row['period'] == 'training'}
    candidates = []
    for threshold in THRESHOLDS[1:]:
        gates = {}
        scores = []
        for scenario in ['normal', 'stress']:
            item, baseline = training[threshold, scenario], training[0., scenario]
            pf, mean = item['pf_r'], item['mean_r']
            gates[f'{scenario}_pf_ge_1'] = pf is not None and pf >= 1.
            gates[f'{scenario}_mean_positive'] = mean is not None and mean > 0.
            gates[f'{scenario}_pf_improved'] = (pf is not None and baseline['pf_r'] is not None
                                               and pf > baseline['pf_r'])
            gates[f'{scenario}_mean_improved'] = (mean is not None and baseline['mean_r'] is not None
                                                 and mean > baseline['mean_r'])
            scores.append(mean)
        normal = training[threshold, 'normal']
        required = max(500., training[0., 'normal']['closed'] * .2)
        positive_symbols = sum(row['net_r'] > 0 for row in results
                               if row['period'] == 'training' and row['scenario'] == 'normal'
                               and row['threshold_risk_cost'] == threshold)
        gates['normal_count'] = normal['closed'] >= required
        gates['normal_positive_symbols'] = positive_symbols >= 8
        candidates.append(dict(threshold_risk_cost=threshold, eligible=all(gates.values()),
                               gates=gates, normal_closed=normal['closed'], required_closed=required,
                               normal_positive_symbols=positive_symbols,
                               score=min(scores) if all(value is not None for value in scores) else None))
    eligible = [item for item in candidates if item['eligible']]
    best = max(eligible, key=lambda row: (row['score'], row['normal_closed'], -row['threshold_risk_cost'])) if eligible else None
    return dict(selected=best['threshold_risk_cost'] if best else None, candidates=candidates)


def validate_selection(selection, train_result, train_sha, protocol_sha):
    if (selection.get('protocol_sha256') != protocol_sha or selection.get('train_result_sha256') != train_sha
            or not selection.get('frozen_at')):
        raise ValueError('Selection must seal exact training result and frozen protocol')
    if (train_result.get('stage') != 'train' or train_result.get('status') != 'COMPLETED_DESCRIPTIVE'
            or train_result.get('protocol_sha256') != protocol_sha):
        raise ValueError('Completed training from the same frozen protocol required')
    selected = selection.get('selected')
    if selected is None:
        raise ValueError('No candidate selected; later periods must remain unevaluated')
    expected = selection_recommendation(train_result['results'], train_result['pooled'])['selected']
    if selection.get('status') != 'SELECTED' or selected not in THRESHOLDS[1:] or selected != expected:
        raise ValueError('One eligible training-selected threshold required')
    return selected


def later_gates(results, pooled, previous_pooled, selected):
    checks = []
    for label in ['validation', 'final']:
        gates = {}
        for scenario in ['normal', 'stress']:
            item = next(row for row in pooled if row['period'] == label and row['scenario'] == scenario)
            baseline = next(row for row in previous_pooled if row['period'] == label and row['scenario'] == scenario)
            pf, mean = item['pf_r'], item['mean_r']
            gates[f'{scenario}_pf_ge_1'] = pf is not None and pf >= 1.
            gates[f'{scenario}_mean_positive'] = mean is not None and mean > 0.
            gates[f'{scenario}_pf_improved'] = pf is not None and baseline['pf_r'] is not None and pf > baseline['pf_r']
            gates[f'{scenario}_mean_improved'] = mean is not None and baseline['mean_r'] is not None and mean > baseline['mean_r']
        normal = next(row for row in pooled if row['period'] == label and row['scenario'] == 'normal')
        positive_symbols = sum(row['net_r'] > 0 for row in results
                               if row['period'] == label and row['scenario'] == 'normal')
        gates['normal_count'] = normal['closed'] >= 200
        gates['normal_positive_symbols'] = positive_symbols >= 8
        checks.append(dict(period=label, threshold_risk_cost=selected,
                           passes=all(gates.values()), gates=gates, normal_positive_symbols=positive_symbols))
    return dict(passes=all(row['passes'] for row in checks), periods=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['train', 'evaluate'], required=True)
    args = parser.parse_args()
    protocol_path = DOC / 'protocol.json'
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    validate_protocol(protocol)
    protocol_sha = base.digest(protocol_path)
    selected = None
    if args.stage == 'evaluate':
        train_path = OUT / 'train/result.json'
        train_result = json.loads(train_path.read_text(encoding='utf-8'))
        selection_path = DOC / 'selection.json'
        selection = json.loads(selection_path.read_text(encoding='utf-8'))
        selected = validate_selection(selection, train_result, base.digest(train_path), protocol_sha)
        thresholds = [selected]
        begin = base.stamp(STAGE_DATES['evaluation_entry_start'])
        end = base.stamp(STAGE_DATES['evaluation_entry_end'])
        terminal = base.stamp(STAGE_DATES['evaluation_terminal'])
        periods = PERIODS + [('all', STAGE_DATES['evaluation_entry_start'], STAGE_DATES['evaluation_entry_end'])]
    else:
        thresholds = THRESHOLDS
        begin = base.stamp(STAGE_DATES['training_entry_start'])
        end = base.stamp(STAGE_DATES['training_entry_end'])
        terminal = base.stamp(STAGE_DATES['training_terminal'])
        periods = PERIODS[:1]
    output_dir = OUT / args.stage
    output_dir.mkdir(parents=True, exist_ok=False)
    previous_path = PREVIOUS / 'result.json'
    previous_manifest = json.loads(previous_path.read_text(encoding='utf-8'))['manifest']
    repository = base.HistoryRepository()
    start = base.stamp(STAGE_DATES['load_start'])
    manifest, results, pooled_parts, checks, previous_parts, ledger_sha256 = {}, [], {}, [], {}, {}
    for symbol in reference.SYMBOLS:
        tick = time.perf_counter()
        bars_sha = base.digest(repository.root / symbol / 'Bars.dat')
        info_sha = base.digest(repository.root / symbol / 'info.dat')
        previous_input = previous_manifest[symbol]
        if bars_sha != previous_input['bars_sha256'] or info_sha != previous_input['info_sha256']:
            raise ValueError(f'{symbol} source differs from original swap study')
        times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
        setups, profiles, first_week, ready, quality = reference.features(times, prices, volume)
        manifest[symbol] = dict(bars_sha256=bars_sha, info_sha256=info_sha,
                                observed_first=base.iso(times[0]), observed_last=base.iso(times[-1]),
                                m1_rows=len(times), **quality)
        allowed = np.ones(len(times), dtype=np.bool_)  #H4 big-move gate permanently OFF
        pip = .01 if symbol.endswith('JPY') else .0001
        for stress in [False, True]:
            scenario = 'stress' if stress else 'normal'
            old_path = PREVIOUS / f'{symbol}_{scenario}_A0_reverse_trades.npy'
            old_rows = np.load(old_path, allow_pickle=False)
            for label, left, right in periods:
                part = old_rows[(old_rows[:, 0] >= base.stamp(left)) & (old_rows[:, 0] < base.stamp(right))]
                previous_parts.setdefault((scenario, label), []).append(part)
            for threshold in thresholds:
                rows, stats = replay(times, prices, setups, profiles, first_week, ready,
                                     begin, end, pip, stress, allowed, True, threshold)
                tag = f'{symbol}_{scenario}_C{threshold:g}'
                np.save(output_dir / f'{tag}_trades.npy', rows)
                ledger_sha256[f'{tag}_trades.npy'] = base.digest(output_dir / f'{tag}_trades.npy')
                records = reference.trade_records(rows, symbol, scenario)
                for record in records:
                    record['threshold_risk_cost'] = threshold
                base.write_csv(output_dir / f'{tag}_trades.csv', records)
                if args.stage == 'train' and threshold == 0:
                    check = bigmove.baseline_comparison(rows, old_rows, begin, end)
                    checks.append(dict(symbol=symbol, scenario=scenario, check='previous_swap_OFF_training',
                                       compared_sha256=base.digest(old_path), **check))
                    if not check['matches']:
                        raise ValueError(f'{tag} differs from previous swap OFF17-column training ledger')
                if args.stage == 'evaluate':
                    train_rows_path = OUT / 'train' / f'{tag}_trades.npy'
                    if base.digest(train_rows_path) != train_result['ledger_sha256'][train_rows_path.name]:
                        raise ValueError(f'{tag} selected training ledger differs from sealed artifact hash')
                    training_rows = rows[(rows[:, 0] >= base.stamp(PERIODS[0][1]))
                                         & (rows[:, 0] < base.stamp(PERIODS[0][2]))]
                    check = bigmove.baseline_comparison(training_rows,
                                                       np.load(train_rows_path, allow_pickle=False),
                                                       base.stamp(PERIODS[0][1]), base.stamp(PERIODS[0][2]))
                    checks.append(dict(symbol=symbol, scenario=scenario, check='sealed_selected_training',
                                       compared_sha256=base.digest(train_rows_path), **check))
                    if not check['matches']:
                        raise ValueError(f'{tag} selected training ledger changed during continuation')
                for label, left, right in periods:
                    part = rows[(rows[:, 0] >= base.stamp(left)) & (rows[:, 0] < base.stamp(right))]
                    result = dict(symbol=symbol, scenario=scenario, threshold_risk_cost=threshold,
                                  period=label, **reference.metrics(part))
                    if label == ('training' if args.stage == 'train' else 'all'):
                        result.update(total_setups=len(setups), entries=int(stats[0]), unresolved=int(stats[2]),
                                      pending=int(stats[3]), decisions=int(stats[4]), selections=int(stats[5]),
                                      missing_0815=int(stats[6]))
                    results.append(result)
                    pooled_parts.setdefault((threshold, scenario, label), []).append(part)
        print(json.dumps(dict(symbol=symbol, stage=args.stage, m1=len(times),
                              seconds=round(time.perf_counter() - tick, 2))), flush=True)
    pooled = [dict(threshold_risk_cost=threshold, scenario=scenario, period=label, **pooled_metrics(parts))
              for (threshold, scenario, label), parts in pooled_parts.items()]
    previous_pooled = [dict(provenance='previous_saved_swap_OFF_ledger', scenario=scenario,
                            period=label, **pooled_metrics(parts))
                       for (scenario, label), parts in previous_parts.items()]
    output = dict(experiment_id=EXPERIMENT, stage=args.stage, status='COMPLETED_DESCRIPTIVE',
                  code_identifier=protocol['code_identifier'], protocol_sha256=protocol_sha,
                  previous_result_sha256=base.digest(previous_path), thresholds_risk_cost=list(thresholds),
                  manifest=manifest, ledger_sha256=ledger_sha256, comparisons=checks, results=results, pooled=pooled,
                  previous_saved_baseline_pooled=previous_pooled)
    if args.stage == 'train':
        output['selection_recommendation'] = selection_recommendation(results, pooled)
        output['later_candidate_periods_evaluated'] = False
    else:
        output['selection_sha256'] = base.digest(selection_path)
        output['train_result_sha256'] = base.digest(train_path)
        output['later_validation'] = later_gates(results, pooled, previous_pooled, selected)
    base.write_csv(output_dir / 'summary.csv', results)
    base.write_csv(output_dir / 'pooled.csv', pooled)
    base.write_csv(output_dir / 'previous_saved_baseline_pooled.csv', previous_pooled)
    base.write_csv(output_dir / 'comparisons.csv', checks)
    (output_dir / 'result.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print('RESULT_JSON=' + json.dumps(output.get('selection_recommendation', output.get('later_validation'))), flush=True)


if __name__ == '__main__':
    main()


