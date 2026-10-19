"""Finite structural-stop experiment; data-quality-limited to training only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from numba import njit

from scripts.research_bb3_context_timing import ROOT, aggregate, dump, eligible_train, stats, timestamp
from scripts.research_bb3_context_exits import TRADE_COLUMNS, bracket_fill, simulate_exits

SPEC = ROOT / "docs/quant_organization/experiments/bb3_context_structure_stop_20260909/protocol.json"
CACHE = ROOT / "agent_runs/bb3_context_timing_20260909/completed"
OLD = ROOT / "agent_runs/bb3_context_exits_20260909"
OUT = ROOT / "agent_runs/bb3_context_structure_stop_20260909"


@njit(cache=True)
def structural_target(entry, side, risk, tick):
    """Outward absolute-price rounding preserves actual RR, including non-grid fills."""
    raw_ticks = (entry + side * risk * 1.3) / tick
    integer = round(raw_ticks)
    if abs(raw_ticks - integer) < 1e-8:
        raw_ticks = float(integer)
    return (math.ceil(raw_ticks) if side == 1 else math.floor(raw_ticks)) * tick


@njit(cache=True)
def simulate_structure_stop(f, times, start, end, pip, cost, tick, limit_entry, buffer):
    """Absolute preparation-extreme SL and RR1.3. Same 15 trade columns as exits.
    Diagnostics original20 plus invalid-known-limits, breached-fill-exits,
    frozen structural stop, and preparation interval extreme.
    """
    trades = np.empty((len(f), 15))
    count = 0
    side = pending = armed = 0
    prep = signal = entry_i = -1
    entry = target = limit = stop = initial_target = risk = signal_atr = np.nan
    entry_kind = 0
    frozen_stop = extreme = np.nan
    invalid_orders = breached_fills = 0
    prep_count = signal_count = ambiguous_count = cancel_count = open_fills = touch_fills = dual_count = 0
    realized = peak = dd = 0.0
    last_close = np.nan
    for i in range(len(f)):
        if times[i] < start or times[i] >= end:
            continue
        op, hi, lo, cl, mid, upper, lower = f[i, :7]
        last_close = cl
        handled = suppress_target = new_entry = instant_breach = False
        if side == 0 and pending != 0 and i > signal:
            if not limit_entry:
                side, pending, entry, entry_i = pending, 0, op, i
                new_entry, entry_kind = True, 0
                open_fills += 1
            else:
                center_open = op >= target if pending == 1 else op <= target
                center_hit = hi >= target if pending == 1 else lo <= target
                limit_open = op <= limit if pending == 1 else op >= limit
                limit_hit = lo <= limit if pending == 1 else hi >= limit
                if limit_open and pending * (op - frozen_stop) < tick * (1 - 1e-8):
                    side, pending, entry, entry_i = pending, 0, op, i
                    new_entry, entry_kind = True, 1
                    open_fills += 1
                elif center_open:
                    pending, handled = 0, True
                    cancel_count += 1
                elif limit_open or limit_hit:
                    side, pending = pending, 0
                    entry, entry_i = (op if limit_open else limit), i
                    new_entry, suppress_target = True, not limit_open
                    entry_kind = 1 if limit_open else 2
                    if limit_open:
                        open_fills += 1
                    else:
                        touch_fills += 1
                elif center_hit:
                    pending, handled = 0, True
                    cancel_count += 1
                else:
                    explained = f[i, 10] if pending == 1 else f[i, 11]
                    wick = f[i, 12] if pending == 1 else f[i, 13]
                    center_passed = cl >= mid if pending == 1 else cl <= mid
                    opposite = hi >= upper if pending == 1 else lo <= lower
                    if i - signal >= 3 or explained != 0 or wick != 0 or center_passed or opposite or f[i, 14] != 0:
                        pending, handled = 0, True
                        cancel_count += 1
                    else:
                        target = mid
        if new_entry:
            stop = frozen_stop
            risk = side * (entry - stop)
            if risk < tick * (1 - 1e-8):
                instant_breach = True
                breached_fills += 1
                target = initial_target = np.nan
            else:
                target = structural_target(entry, side, risk, tick)
                initial_target = target
                if suppress_target and (hi >= target if side == 1 else lo <= target):
                    ambiguous_count += 1
        if side != 0:
            if instant_breach:
                fill, stopped, dual = entry, True, False
            else:
                fill, stopped, dual = bracket_fill(side, op, hi, lo, target, stop, suppress_target)
            if dual:
                dual_count += 1
            if not np.isnan(fill):
                net = side * (fill - entry) / pip - cost
                trades[count] = (float(side), float(prep), float(signal), float(entry_i), float(i),
                                 entry, fill, target, net, stop, initial_target, risk, signal_atr,
                                 float(entry_kind), 1.0 if stopped else 0.0)
                count += 1
                realized += net
                side, handled = 0, True
                entry = target = stop = initial_target = np.nan
        equity = realized + (side * (cl - entry) / pip - cost if side else 0.0)
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
        ready = side == 0 and pending == 0 and not handled and not np.isnan(mid) and upper > mid and not np.isnan(f[i, 7]) and not np.isnan(f[i, 8])
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
            signal_atr = f[i, 7]
            extreme = np.min(f[prep:i + 1, 2]) if selected == 1 else np.max(f[prep:i + 1, 1])
            raw_stop = extreme - selected * buffer * signal_atr
            frozen_stop = (math.floor(raw_stop / tick) if selected == 1 else math.ceil(raw_stop / tick)) * tick
            raw_limit = cl - selected * signal_atr
            limit = (math.floor(raw_limit / tick) if selected == 1 else math.ceil(raw_limit / tick)) * tick
            signal_count += 1
            if limit_entry and selected * (limit - frozen_stop) < tick * (1 - 1e-8):
                pending = 0
                invalid_orders += 1
    open_net = side * (last_close - entry) / pip - cost if side else 0.0
    return trades[:count], np.array([open_net, dd, side, entry, last_close, pending, prep_count, signal_count,
                                    entry_i, target, ambiguous_count, cancel_count, open_fills, touch_fills,
                                    dual_count, stop, risk, initial_target, signal_atr, entry_kind,
                                    invalid_orders, breached_fills, frozen_stop, extreme])


def descriptive_stats(trades, diagnostic, pip):
    summary = stats(trades, diagnostic)
    risks = trades[:, 11] / pip
    normal_risks = risks[(risks > 0) & np.isfinite(trades[:, 10])]
    equity = np.r_[0., np.cumsum(trades[:, 8])]
    summary.update(average_risk_pips=float(normal_risks.mean()) if len(normal_risks) else None,
                   risk_trade_count=len(normal_risks), total_risk_pips=float(normal_risks.sum()),
                   realized_drawdown_pips=float(np.max(np.maximum.accumulate(equity) - equity)),
                   invalid_known_limits=int(diagnostic[20]) if len(diagnostic) > 20 else 0,
                   breached_fill_exits=int(diagnostic[21]) if len(diagnostic) > 21 else 0,
                   stop_exits=int(trades[:, 14].sum()),
                   ambiguous_entry_bars=int(diagnostic[10]), dual_touch_bars=int(diagnostic[14]))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding='utf-8'))
    manifests = json.loads((CACHE / 'data_manifest.json').read_text(encoding='utf-8'))
    dump(output / 'protocol.json', protocol)
    paths = [SPEC, Path(__file__), ROOT / 'scripts/research_bb3_context_exits.py',
             ROOT / 'scripts/research_bb3_context_timing.py', CACHE / 'data_manifest.json']
    paths.extend(CACHE / f'{s}_features.npz' for s in protocol['symbols'])
    paths.extend(OLD / f'{entry}_sl10_rr13__training__{s}__{cost}.npz'
                 for entry in ('market', 'limit') for s in protocol['symbols']
                 for cost in ('fixed_1p4', 'metadata_spread_plus_0p2'))
    dump(output / 'code_input_hashes.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    inputs, quality = {}, []
    for m in manifests:
        file = Path(protocol['history_directory']) / m['symbol'] / 'Bars.dat'
        if {'size': file.stat().st_size, 'mtime_ns': file.stat().st_mtime_ns} != m['after']:
            raise ValueError('Raw history changed since cached snapshot')
        data = np.load(CACHE / f"{m['symbol']}_features.npz")
        f, times = data['features'], data['times']
        mask = (times >= timestamp('2023-09-08')) & (times < timestamp('2024-09-08'))
        grid = f[:, :4] / m['tick']
        errors = np.abs(grid - np.rint(grid))
        quality.append({'symbol': m['symbol'], 'all_ohlc_off_grid': int((errors > 1e-6).sum()),
                        'training_ohlc_off_grid': int((errors[mask] > 1e-6).sum()),
                        'training_max_grid_error_ticks': float(errors[mask].max())})
        if (errors[mask] > 1e-6).any():
            raise ValueError('Training contains non-tick OHLC; investigate before research')
        spread = float(m['metadata']['values']['spread']) * m['tick'] / m['pip']
        inputs[m['symbol']] = (f, times, m['pip'], m['tick'],
                              {'fixed_1p4': 1.4, 'metadata_spread_plus_0p2': spread + .2})
    dump(output / 'data_manifest.json', manifests)
    dump(output / 'data_quality.json', {'evaluated_period': 'training only',
         'later_period_status': 'NOT_EVALUATED_PRICE_SCALE_ANOMALY_GBPJPY_2026_08_31', 'grid_checks': quality})
    summaries, results, controls_verified = {}, [], 0
    for candidate in protocol['search_space']:
        collected = {}
        for symbol, (f, times, pip, tick, costs) in inputs.items():
            for cost_name, cost in costs.items():
                args = (f, times, timestamp('2023-09-08'), timestamp('2024-09-08'), pip, cost, tick, candidate['entry'] == 'limit')
                if candidate['stop'] == 'fixed10':
                    trades, diagnostic = simulate_exits(*args, 2, 1.3)
                    reference = np.load(OLD / f"{candidate['entry']}_sl10_rr13__training__{symbol}__{cost_name}.npz")
                    np.testing.assert_array_equal(trades, reference['trades'])
                    np.testing.assert_array_equal(diagnostic, reference['diagnostic'])
                    controls_verified += 1
                else:
                    trades, diagnostic = simulate_structure_stop(*args, candidate['buffer'])
                name = f"{candidate['id']}__training__{symbol}__{cost_name}.npz"
                np.savez_compressed(output / name, trades=trades, diagnostic=diagnostic)
                summary = descriptive_stats(trades, diagnostic, pip)
                results.append({'candidate': candidate['id'], 'symbol': symbol, 'period': 'training',
                    'cost_case': cost_name, 'cost_pips': cost, 'artifact': name, **summary})
                collected.setdefault(cost_name, []).append(summary)
        by_cost = {}
        for cost, rows in collected.items():
            combined = aggregate(rows)
            combined['win_rate_pct'] = 100 * combined['wins'] / combined['trades'] if combined['trades'] else None
            nrisk = sum(r['risk_trade_count'] for r in rows)
            combined['average_risk_pips'] = sum(r['total_risk_pips'] for r in rows) / nrisk if nrisk else None
            # Drawdowns are per-pair; this is the largest single-pair DD, not portfolio DD.
            combined['largest_pair_mtm_drawdown_pips'] = max(r['bar_close_mtm_drawdown_pips'] for r in rows)
            combined['largest_pair_realized_drawdown_pips'] = max(r['realized_drawdown_pips'] for r in rows)
            for key in ('invalid_known_limits', 'breached_fill_exits', 'stop_exits', 'ambiguous_entry_bars', 'dual_touch_bars'):
                combined[key] = sum(r[key] for r in rows)
            by_cost[cost] = combined
        summaries[candidate['id']] = by_cost
        print('TRAIN', candidate['id'], json.dumps(by_cost), flush=True)
    eligible = [c for c in protocol['search_space'] if c['stop'] == 'structure' and eligible_train(summaries[c['id']])]
    eligible.sort(key=lambda c: (-min(s['net_pips'] for s in summaries[c['id']].values()), c['id']))
    selected = eligible[0]['id'] if eligible else None
    dump(output / 'selection.json', {'selected': selected, 'eligible_training': [c['id'] for c in eligible],
                                     'later_periods': 'blocked by source-data anomaly, not simulated'})
    status = 'NEEDS_EVIDENCE' if selected else 'REJECTED'
    result = {'status': status, 'selected': selected, 'scope': 'training_only_due_to_later_data_anomaly',
              'control_artifacts_exactly_reproduced': controls_verified, 'trade_columns': TRADE_COLUMNS,
              'summaries': summaries, 'rows': results, 'live_approved': False,
              'limits': 'Training only; raw later GBPJPY price-scale anomaly not corrected; no later-period proof; equal-pip scores not money; TV_UNVERIFIED'}
    dump(output / 'results.json', result)
    print('RESULT_JSON=' + json.dumps({'status': status, 'selected': selected, 'output': str(output)}), flush=True)


if __name__ == '__main__':
    main()
