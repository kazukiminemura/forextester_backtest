"""Frozen four-filter study of the existing BB3 entry; not adoption approval."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
from numba import njit

from forextester_backtest import HistoryRepository
from scripts.research_bb3_context_center5 import descriptive_stats, simulate_center
from scripts.research_bb3_context_timing import (
    EPOCH, ROOT, TRADE_COLUMNS, aggregate, dump, features, timestamp,
)

SPEC = ROOT / 'docs/quant_organization/experiments/bb3_candle_shapes_20260919/protocol.json'
OUT = ROOT / 'agent_runs/bb3_candle_shapes_20260919'
CACHE = ROOT / 'agent_runs/bb3_context_timing_20260909/completed'


@njit(cache=True)
def shape_allowed(f, i, side, mode):
    if mode == 0:
        return True
    op, hi, lo, cl = f[i, :4]
    width = hi - lo
    if width <= 0 or side * (cl - op) <= 0:
        return False
    location = (cl - lo) / width if side == 1 else (hi - cl) / width
    if mode == 1:
        return location >= .65
    if mode == 2:
        return location >= .65 and abs(cl - op) / width >= .5
    if i == 0:
        return False
    prior_open, prior_high, prior_low, prior_close = f[i - 1, :4]
    if mode == 3:
        return (side * (prior_close - prior_open) < 0
                and min(op, cl) <= min(prior_open, prior_close)
                and max(op, cl) >= max(prior_open, prior_close))
    if mode == 4:
        return cl > prior_high if side == 1 else cl < prior_low
    return False


@njit(cache=True)
def simulate_shapes(f, times, start, end, pip, cost, mode):
    """Same center3 state machine; shape failure cancels first eligible signal.

    Diagnostics0:11 equal simulate_center; appended index11 shape rejection.
    """
    trades = np.empty((len(f), 9))
    count = distance_rejections = shape_rejections = 0
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
                elif not shape_allowed(f, i, armed, mode):
                    cancelled = True
                    shape_rejections += 1
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
    return trades[:count], np.array([open_net, dd, side, entry, last_close, pending, prep_count, signal_count, entry_i, target, distance_rejections, shape_rejections])


def source_stat(path):
    stat = path.stat()
    return dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def load_inputs(protocol, output):
    """Reuse only unchanged raw-source caches; fresh-load the other pairs."""
    repo = HistoryRepository()
    manifests = {m['symbol']: m for m in json.loads((CACHE / 'data_manifest.json').read_text())}
    inputs, used = {}, []
    cutoff = timestamp('2026-08-31')
    for symbol in protocol['symbols']:
        print('Loading', symbol, flush=True)
        raw = repo.root / symbol / 'Bars.dat'
        before = source_stat(raw)
        pip = .01 if symbol.endswith('JPY') else .0001
        cached = symbol in manifests and before == manifests[symbol]['after']
        if cached:
            with np.load(CACHE / f'{symbol}_features.npz') as data:
                mask = data['times'] < cutoff
                times, f = data['times'][mask], data['features'][mask]
        else:
            bars = list(repo.bars(symbol, datetime(2023, 8, 1), datetime(2026, 8, 31) - timedelta(microseconds=1), '5m'))
            times = np.array([int((b.time - EPOCH).total_seconds()) for b in bars], dtype=np.int64)
            ohlc = np.array([(b.open, b.high, b.low, b.close) for b in bars])
            f = features(ohlc, times, pip, 10. ** -repo.metadata(symbol).decimals)
        assert len(times) and times[0] < timestamp('2023-09-08') and times[-1] < cutoff
        assert np.all(np.diff(times) > 0) and np.all(np.isfinite(f[:, :4])) and np.all(f[:, :4] > 0)
        assert np.all(f[:, 1] >= np.maximum(f[:, 0], f[:, 3]))
        assert np.all(f[:, 2] <= np.minimum(f[:, 0], f[:, 3]))
        assert before == source_stat(raw), 'Raw source changed during reading'
        np.savez_compressed(output / f'{symbol}_features.npz', times=times, features=f)
        used.append(dict(symbol=symbol, raw_path=str(raw), before=before, after=source_stat(raw),
                         reused_verified_cache=cached, bars=len(times), first=int(times[0]), last=int(times[-1]),
                         input_sha256=hashlib.sha256(times.tobytes() + f.tobytes()).hexdigest()))
        inputs[symbol] = f, times, pip
    dump(output / 'data_manifest.json', used)
    return inputs


def summarize(trades, diag, times):
    result = descriptive_stats(trades, diag)
    durations = (times[trades[:, 4].astype(int)] - times[trades[:, 3].astype(int)]) / 3600
    result.update(shape_rejections=int(diag[11]),
                  mean_holding_hours=float(np.mean(durations)) if len(durations) else None,
                  max_holding_hours=float(np.max(durations)) if len(durations) else None)
    return result


def gates(summary, baseline, period, protocol):
    rules = protocol['acceptance_gates']
    absolute = rules['training_min_trades'] if period == 'training' else rules['later_min_trades']
    checks = {}
    for cost, row in summary.items():
        base = baseline[cost]
        checks[cost + '.count'] = row['trades'] >= max(absolute, rules['relative_count'] * base['trades'])
        checks[cost + '.winrate'] = (row['win_rate_pct'] is not None and base['win_rate_pct'] is not None
                                   and row['win_rate_pct'] >= base['win_rate_pct'] + rules['winrate_gain_percentage_points'])
        checks[cost + '.pf'] = (row['profit_factor'] is not None and base['profit_factor'] is not None
                              and row['profit_factor'] >= rules['pf_min'] and row['profit_factor'] > base['profit_factor'])
        checks[cost + '.net_plus_open'] = row['net_plus_open_pips'] > 0
        checks[cost + '.positive_pairs'] = row['positive_pairs'] >= rules['positive_pairs_min']
    return checks


def evaluate_period(ids, period, protocol, inputs, output, rows):
    start, end = map(timestamp, protocol['periods'][period])
    summaries = {}
    parity = 0
    for mode in ids:
        collected = {}
        for symbol, (f, times, pip) in inputs.items():
            geometry = None
            for cost in protocol['cost_and_fill_model']['round_trip_pips']:
                cost_name = f'{cost:.1f}'
                trades, diag = simulate_shapes(f, times, start, end, pip, cost, mode)
                if mode == 0:
                    old_t, old_d = simulate_center(f, times, start, end, pip, cost, 3.)
                    np.testing.assert_array_equal(trades, old_t)
                    np.testing.assert_array_equal(diag[:11], old_d)
                    parity += 1
                if geometry is not None:
                    np.testing.assert_array_equal(trades[:, :8], geometry)
                geometry = trades[:, :8].copy()
                name = f'c{mode}__{period}__{symbol}__{cost_name}.npz'
                np.savez_compressed(output / name, trades=trades, diagnostic=diag)
                row = dict(candidate=mode, symbol=symbol, period=period, cost=cost_name,
                           artifact=name, **summarize(trades, diag, times))
                rows.append(row)
                collected.setdefault(cost_name, []).append(row)
        summaries[str(mode)] = {}
        for cost, pair_rows in collected.items():
            total = aggregate(pair_rows)
            total['win_rate_pct'] = 100 * total['wins'] / total['trades'] if total['trades'] else None
            total['average_pips'] = total['net_pips'] / total['trades'] if total['trades'] else None
            total['largest_pair_mtm_drawdown_pips'] = max(r['bar_close_mtm_drawdown_pips'] for r in pair_rows)
            total['max_holding_hours'] = max((r['max_holding_hours'] for r in pair_rows if r['max_holding_hours'] is not None), default=None)
            summaries[str(mode)][cost] = total
        print('COMPLETE', period, mode, flush=True)
    return summaries, parity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding='utf-8'))
    assert protocol['status'] == 'SPEC_FROZEN'
    dump(output / 'protocol.json', protocol)
    sources = [SPEC, Path(__file__), ROOT / 'scripts/research_bb3_context_center5.py',
               ROOT / 'scripts/research_bb3_context_timing.py', ROOT / 'src/forextester_backtest/data.py']
    dump(output / 'code_hashes.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    inputs = load_inputs(protocol, output)
    rows = []
    training, parity = evaluate_period(range(5), 'training', protocol, inputs, output, rows)
    checks = {str(i): gates(training[str(i)], training['0'], 'training', protocol) for i in range(1, 5)}
    eligible = [i for i in range(1, 5) if all(checks[str(i)].values())]
    eligible.sort(key=lambda i: (-training[str(i)]['1.4']['win_rate_pct'], -training[str(i)]['1.4']['profit_factor'], i))
    selected = eligible[0] if eligible else None
    result = dict(status='REJECTED_TRAINING_ONLY', selected=selected,
                  summaries={'training': training}, gates={'training': checks}, rows=rows,
                  baseline_cases_exactly_reproduced=parity, trade_columns=TRADE_COLUMNS,
                  live_approved=False, previously_viewed_periods=True)
    if selected is not None:
        for period in ('validation', 'final_confirmation'):
            summary, parity = evaluate_period([0, selected], period, protocol, inputs, output, rows)
            result['baseline_cases_exactly_reproduced'] += parity
            result['summaries'][period] = summary
            check = gates(summary[str(selected)], summary['0'], period, protocol)
            result['gates'][period] = check
            result['status'] = f'REJECTED_{period.upper()}'
            if not all(check.values()):
                break
        else:
            result['status'] = 'GATES_PASSED_PENDING_INDEPENDENT_AUDIT'
    dump(output / 'results.json', result)
    print('RESULT_JSON=' + str(output / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
