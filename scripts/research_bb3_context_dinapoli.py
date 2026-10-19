"""Finite DiNapoli-style SMA3[3] confirmation comparison; no live approval."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from numba import njit

from scripts.research_bb3_context_timing import ROOT, TRADE_COLUMNS, aggregate, dump, timestamp
from scripts.research_bb3_context_center5 import descriptive_stats, simulate_center

SPEC = ROOT / "docs/quant_organization/experiments/bb3_context_dinapoli_20260909/protocol.json"
CACHE = ROOT / "agent_runs/bb3_context_timing_20260909/completed"
OUT = ROOT / "agent_runs/bb3_context_dinapoli_20260909"


@njit(cache=True)
def displaced_sma3(close):
    """Value at current bar of SMA3 plotted forward3; never a future MA."""
    result = np.full(len(close), np.nan)
    for i in range(5, len(close)):
        result[i] = np.mean(close[i - 5:i - 2])
    return result


@njit(cache=True)
def dma_allows(f, dma, i, side, mode):
    if mode == 0:
        return True
    if not np.isfinite(dma[i]) or not side * (f[i, 3] - dma[i]) > 0:
        return False
    if mode == 1:
        return True
    if i == 0 or not np.isfinite(dma[i - 1]):
        return False
    if mode == 2:
        return side * (f[i - 1, 3] - dma[i - 1]) <= 0
    return side * (dma[i] - dma[i - 1]) > 0


@njit(cache=True)
def simulate_dma(f, times, dma, start, end, pip, cost, dma_mode):
    """Return trade matrix and diagnostics. No forced close is added to PF.

    No stop. Failed center distance cancels preparation, never waits for recovery.
    diagnostics: open_net, MTM_drawdown, open_side, entry, last_close,
    pending_side, prep_count, signal_count, open_entry_index, target_next_bar,
    distance_rejections, dma_rejections.
    """
    trades = np.empty((len(f), 9))
    count = 0
    distance_rejections = dma_rejections = 0
    side = pending = armed = 0
    prep = signal = entry_i = -1
    entry = target = np.nan
    prep_count = signal_count = 0
    realized = peak = dd = 0.0
    last_close = np.nan
    for i in range(len(f)):
        if times[i] < start or times[i] >= end:
            continue
        op, hi, lo, cl, mid, upper, lower = f[i, :7]
        last_close = cl
        exited = False
        if side == 0 and pending != 0 and i > signal:
            side, pending = pending, 0
            entry, entry_i = op, i
        if side != 0:
            gap_target = op >= target if side == 1 else op <= target
            hit_target = hi >= target if side == 1 else lo <= target
            fill = op if gap_target else target if hit_target else np.nan
            if not np.isnan(fill):
                net = side * (fill - entry) / pip - cost
                trades[count] = (float(side), float(prep), float(signal), float(entry_i), float(i), entry, fill, target, net)
                count += 1
                realized += net
                side, exited = 0, True
                entry = target = np.nan
            else:
                target = mid
        equity = realized + (side * (cl - entry) / pip - cost if side else 0.0)
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
        ready = side == 0 and pending == 0 and not exited and not np.isnan(mid) and upper > mid and not np.isnan(f[i, 7]) and not np.isnan(f[i, 8])
        touch_buy, touch_sell = lo <= lower, hi >= upper
        if not ready or f[i, 14] != 0:
            armed = 0
        cancelled = False
        selected = 0
        if ready and armed != 0:
            explained = f[i, 10] if armed == 1 else f[i, 11]
            wick = f[i, 12] if armed == 1 else f[i, 13]
            center_passed = cl >= mid if armed == 1 else cl <= mid
            opposite = touch_sell if armed == 1 else touch_buy
            cancelled = explained != 0 or wick != 0 or i - prep > 3 or center_passed or opposite
            if not cancelled and i > prep and cl > lower and cl < upper:
                if armed * (mid - cl) / pip + 1e-9 < 3.0:
                    cancelled = True
                    distance_rejections += 1
                elif not dma_allows(f, dma, i, armed, dma_mode):
                    cancelled = True
                    dma_rejections += 1
                else:
                    selected = armed
            if cancelled or selected != 0:
                armed = 0
        if ready and armed == 0 and not cancelled and selected == 0 and (touch_buy or touch_sell):
            explained = f[i, 10] if touch_buy else f[i, 11]
            wick = f[i, 12] if touch_buy else f[i, 13]
            if not (touch_buy and touch_sell) and explained == 0 and wick == 0:
                armed = 1 if touch_buy else -1
                prep = i
                prep_count += 1
        if selected:
            pending, signal, target = selected, i, mid
            signal_count += 1
    open_net = side * (last_close - entry) / pip - cost if side else 0.0
    return trades[:count], np.array([open_net, dd, side, entry, last_close, pending, prep_count, signal_count, entry_i, target, distance_rejections, dma_rejections])


def improvement_checks(candidate, baseline, candidate_rows, baseline_rows, period):
    """All inputs already fixed. No reclassification of wins or ignored costs."""
    checks, deltas = {}, {}
    for cost, by_period in candidate.items():
        c, b = by_period[period], baseline[cost][period]
        prefix = cost + '.' + period
        finite = all(c[k] is not None and b[k] is not None for k in ('win_rate_pct', 'profit_factor', 'average_pips'))
        checks[prefix + '.finite_statistics'] = finite
        if finite:
            win_gain = c['win_rate_pct'] - b['win_rate_pct']
            pf_gain = c['profit_factor'] - b['profit_factor']
            avg_gain = c['average_pips'] - b['average_pips']
            checks[prefix + '.winrate_up'] = win_gain > 1e-12
            checks[prefix + '.pf_not_lower'] = pf_gain >= -1e-12
            checks[prefix + '.average_not_lower'] = avg_gain >= -1e-9
            deltas[cost] = {'winrate_pp': win_gain, 'pf': pf_gain, 'average_pips': avg_gain}
        else:
            checks[prefix + '.winrate_up'] = checks[prefix + '.pf_not_lower'] = checks[prefix + '.average_not_lower'] = False
        checks[prefix + '.minimum_count'] = c['trades'] >= (100 if period == 'continuous' else 30)
        checks[prefix + '.sample_retained'] = c['trades'] >= .25 * b['trades']
        bpairs = {r['symbol']: r for r in baseline_rows if r['period'] == period and r['cost_case'] == cost}
        cpairs = [r for r in candidate_rows if r['period'] == period and r['cost_case'] == cost]
        improved_pairs = sum(r['trades'] > 0 and bpairs[r['symbol']]['trades'] > 0 and
            r['win_rate_pct'] > bpairs[r['symbol']]['win_rate_pct'] + 1e-12 for r in cpairs)
        checks[prefix + '.six_pairs_winrate_up'] = improved_pairs >= 6
        if cost in deltas:
            deltas[cost]['improved_pairs'] = improved_pairs
    return checks, deltas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding='utf-8'))
    manifests = json.loads((CACHE / 'data_manifest.json').read_text(encoding='utf-8'))
    dump(output / 'protocol.json', protocol)
    paths = [SPEC, Path(__file__), ROOT / protocol['pine_source'], ROOT / 'scripts/research_bb3_context_center5.py',
             ROOT / 'scripts/research_bb3_context_timing.py', CACHE / 'data_manifest.json']
    paths.extend(CACHE / f'{s}_features.npz' for s in protocol['symbols'])
    dump(output / 'code_input_hashes.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    inputs, used_manifest = {}, []
    cutoff = timestamp('2026-08-31')
    for m in manifests:
        file = Path(protocol['history_directory']) / m['symbol'] / 'Bars.dat'
        if {'size': file.stat().st_size, 'mtime_ns': file.stat().st_mtime_ns} != m['after']:
            raise ValueError('Raw history changed since cached snapshot')
        data = np.load(CACHE / f"{m['symbol']}_features.npz")
        end_index = int(np.searchsorted(data['times'], cutoff, side='left'))
        f, times = data['features'][:end_index].copy(), data['times'][:end_index].copy()
        if len(times) == 0 or times[-1] >= cutoff:
            raise ValueError('Unsafe end cutoff')
        dma = displaced_sma3(f[:, 3])
        used_manifest.append({'symbol': m['symbol'], 'bars': len(times), 'last_timestamp': int(times[-1]),
            'used_prefix_sha256': hashlib.sha256(times.tobytes() + f.tobytes()).hexdigest(),
            'dma_sha256': hashlib.sha256(dma.tobytes()).hexdigest(), 'all_before_cutoff': bool(np.all(times < cutoff))})
        spread = float(m['metadata']['values']['spread']) * m['tick'] / m['pip']
        inputs[m['symbol']] = (f, times, dma, m['pip'], {'fixed_1p4': 1.4, 'metadata_spread_plus_0p2': spread + .2})
    dump(output / 'data_manifest.json', manifests)
    dump(output / 'used_prefix_manifest.json', used_manifest)
    summaries, rows, reproduced = {}, [], 0

    def run(candidate, period):
        nonlocal reproduced
        bounds = protocol['periods'][period]
        collected = {}
        for symbol, (f, times, dma, pip, costs) in inputs.items():
            for cost_name, cost in costs.items():
                start, end = timestamp(bounds[0]), timestamp(bounds[1])
                trades, diag = simulate_dma(f, times, dma, start, end, pip, cost, candidate['dma_mode'])
                if candidate['dma_mode'] == 0:
                    ref, ref_diag = simulate_center(f, times, start, end, pip, cost, 3.)
                    np.testing.assert_array_equal(trades, ref)
                    np.testing.assert_array_equal(diag[:11], ref_diag)
                    reproduced += 1
                name = f"{candidate['id']}__{period}__{symbol}__{cost_name}.npz"
                np.savez_compressed(output / name, trades=trades, diagnostic=diag)
                s = descriptive_stats(trades, diag)
                s['dma_rejections'] = int(diag[11])
                rows.append({'candidate': candidate['id'], 'period': period, 'symbol': symbol,
                             'cost_case': cost_name, 'cost_pips': cost, 'artifact': name, **s})
                collected.setdefault(cost_name, []).append(s)
        for cost, values in collected.items():
            a = aggregate(values)
            a['win_rate_pct'] = 100 * a['wins'] / a['trades'] if a['trades'] else None
            a['average_pips'] = a['net_pips'] / a['trades'] if a['trades'] else None
            a['distance_rejections'] = sum(v['distance_rejections'] for v in values)
            a['dma_rejections'] = sum(v['dma_rejections'] for v in values)
            a['largest_pair_mtm_drawdown_pips'] = max(v['bar_close_mtm_drawdown_pips'] for v in values)
            a['largest_pair_realized_drawdown_pips'] = max(v['realized_drawdown_pips'] for v in values)
            summaries.setdefault(candidate['id'], {}).setdefault(cost, {})[period] = a
        print('COMPLETE', candidate['id'], period, flush=True)

    candidates = protocol['search_space']
    for c in candidates:
        run(c, 'segment1')
    baseline_rows = [r for r in rows if r['candidate'] == 'baseline']
    training_checks, training_deltas, eligible = {}, {}, []
    for c in candidates[1:]:
        candidate_rows = [r for r in rows if r['candidate'] == c['id']]
        checks, deltas = improvement_checks(summaries[c['id']], summaries['baseline'], candidate_rows, baseline_rows, 'segment1')
        training_checks[c['id']], training_deltas[c['id']] = checks, deltas
        if all(checks.values()):
            eligible.append(c)
    eligible.sort(key=lambda c: (-min(d['winrate_pp'] for d in training_deltas[c['id']].values()),
                                -min(d['pf'] for d in training_deltas[c['id']].values()), c['id']))
    selected = eligible[0]['id'] if eligible else None
    dump(output / 'selection_before_later_periods.json', {'selected': selected, 'eligible': [c['id'] for c in eligible],
        'training_checks': training_checks, 'training_deltas': training_deltas, 'training_summaries': summaries})
    for c in (c for c in candidates if c['id'] in ('baseline', selected)):
        for period in ('segment2', 'segment3_partial', 'continuous'):
            run(c, period)
    later_checks, later_deltas, profit_checks = {}, {}, {}
    if selected:
        baseline_rows = [r for r in rows if r['candidate'] == 'baseline']
        candidate_rows = [r for r in rows if r['candidate'] == selected]
        for period in ('segment2', 'segment3_partial', 'continuous'):
            checks, deltas = improvement_checks(summaries[selected], summaries['baseline'], candidate_rows, baseline_rows, period)
            later_checks.update(checks)
            later_deltas[period] = deltas
        for cost, periods in summaries[selected].items():
            for period, a in periods.items():
                profit_checks[cost + '.' + period + '.closed_net_positive'] = a['net_pips'] > 0
                profit_checks[cost + '.' + period + '.net_plus_open_positive'] = a['net_plus_open_pips'] > 0
    improved = bool(selected) and all(later_checks.values())
    result = {'status': 'IMPROVEMENT_CHECK_PASSED' if improved else 'NO_VERIFIED_IMPROVEMENT',
        'selected': selected, 'improvement_passed': improved,
        'profit_requirement_met': bool(selected) and all(profit_checks.values()),
        'training_checks': training_checks, 'training_deltas': training_deltas,
        'later_checks': later_checks, 'later_deltas': later_deltas, 'profit_checks': profit_checks,
        'baseline_cases_exactly_reproduced': reproduced, 'trade_columns': TRADE_COLUMNS,
        'summaries': summaries, 'rows': rows, 'live_approved': False,
        'limits': 'Previously viewed data, safe prefix cutoff, research improvement differs from profitability/adoption; equal-pip score not money; TV_UNVERIFIED'}
    dump(output / 'results.json', result)
    print('RESULT_JSON=' + json.dumps({'status': result['status'], 'selected': selected,
        'profit_requirement_met': result['profit_requirement_met'], 'output': str(output)}), flush=True)


if __name__ == '__main__':
    main()
