"""Current Pine min-center 0/5 fixed comparison, common anomaly-free end cutoff."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from numba import njit

from scripts.research_bb3_context_timing import ROOT, TRADE_COLUMNS, aggregate, dump, simulate, stats, timestamp

SPEC = ROOT / "docs/quant_organization/experiments/bb3_context_center5_20260909/protocol.json"
CACHE = ROOT / "agent_runs/bb3_context_timing_20260909/completed"
OUT = ROOT / "agent_runs/bb3_context_center5_20260909"


@njit(cache=True)
def simulate_center(f, times, start, end, pip, cost, min_center_pips):
    """Return trade matrix and diagnostics. No forced close is added to PF.

    No stop. Failed center distance cancels preparation, never waits for recovery.
    diagnostics: open_net, MTM_drawdown, open_side, entry, last_close,
    pending_side, prep_count, signal_count, open_entry_index, target_next_bar,
    distance_rejections.
    """
    trades = np.empty((len(f), 9))
    count = 0
    distance_rejections = 0
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
                if armed * (mid - cl) / pip + 1e-9 < min_center_pips:
                    cancelled = True
                    distance_rejections += 1
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
    return trades[:count], np.array([open_net, dd, side, entry, last_close, pending, prep_count, signal_count, entry_i, target, distance_rejections])


def descriptive_stats(trades, diagnostic):
    summary = stats(trades, diagnostic)
    equity = np.r_[0., np.cumsum(trades[:, 8])]
    summary['realized_drawdown_pips'] = float(np.max(np.maximum.accumulate(equity) - equity))
    summary['distance_rejections'] = int(diagnostic[10])
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding='utf-8'))
    manifests = json.loads((CACHE / 'data_manifest.json').read_text(encoding='utf-8'))
    dump(output / 'protocol.json', protocol)
    paths = [SPEC, Path(__file__), ROOT / protocol['pine_source'],
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
            raise ValueError('Unsafe common end cutoff')
        # Enforce that only the safe prefix participates in ANY simulation below.
        used_manifest.append({'symbol': m['symbol'], 'bars': len(times), 'first_timestamp': int(times[0]),
            'last_timestamp': int(times[-1]), 'end_exclusive': '2026-08-31',
            'used_prefix_sha256': hashlib.sha256(times.tobytes() + f.tobytes()).hexdigest(),
            'all_used_before_anomaly': bool(np.all(times < cutoff))})
        spread = float(m['metadata']['values']['spread']) * m['tick'] / m['pip']
        inputs[m['symbol']] = (f, times, m['pip'], {'fixed_1p4': 1.4, 'metadata_spread_plus_0p2': spread + .2})
    dump(output / 'data_manifest.json', manifests)
    dump(output / 'used_prefix_manifest.json', used_manifest)
    summaries, results, reproduced = {}, [], 0
    for candidate in protocol['search_space']:
        per_cost = {}
        for period, bounds in protocol['periods'].items():
            collected = {}
            for symbol, (f, times, pip, costs) in inputs.items():
                for cost_name, cost in costs.items():
                    args = (f, times, timestamp(bounds[0]), timestamp(bounds[1]), pip, cost)
                    trades, diagnostic = simulate_center(*args, candidate['min_center_pips'])
                    if candidate['min_center_pips'] == 0:
                        old_trades, old_diag = simulate(*args)
                        np.testing.assert_array_equal(trades, old_trades)
                        np.testing.assert_array_equal(diagnostic[:10], old_diag)
                        reproduced += 1
                    name = f"{candidate['id']}__{period}__{symbol}__{cost_name}.npz"
                    np.savez_compressed(output / name, trades=trades, diagnostic=diagnostic)
                    summary = descriptive_stats(trades, diagnostic)
                    results.append({'candidate': candidate['id'], 'symbol': symbol, 'period': period,
                        'cost_case': cost_name, 'cost_pips': cost, 'artifact': name, **summary})
                    collected.setdefault(cost_name, []).append(summary)
            for cost_name, rows in collected.items():
                combined = aggregate(rows)
                combined['win_rate_pct'] = 100 * combined['wins'] / combined['trades'] if combined['trades'] else None
                combined['average_pips'] = combined['net_pips'] / combined['trades'] if combined['trades'] else None
                combined['largest_pair_mtm_drawdown_pips'] = max(r['bar_close_mtm_drawdown_pips'] for r in rows)
                combined['largest_pair_realized_drawdown_pips'] = max(r['realized_drawdown_pips'] for r in rows)
                combined['distance_rejections'] = sum(r['distance_rejections'] for r in rows)
                per_cost.setdefault(cost_name, {})[period] = combined
            print('COMPLETE', candidate['id'], period, flush=True)
        summaries[candidate['id']] = per_cost
    # This request is a fixed-condition performance check, not candidate selection.
    result = {'status': 'DESCRIPTIVE_COMPLETE', 'optimization_performed': False,
        'baseline_cases_exactly_reproduced': reproduced, 'trade_columns': TRADE_COLUMNS,
        'summaries': summaries, 'rows': results, 'live_approved': False,
        'limits': 'Safe common prefix ends before 2026-08-31; no data repair. Equal-pip scores not account profit. Previously viewed periods, no untouched holdout or TradingView runtime verification.'}
    dump(output / 'results.json', result)
    print('RESULT_JSON=' + json.dumps({'status': result['status'], 'output': str(output)}), flush=True)


if __name__ == '__main__':
    main()

