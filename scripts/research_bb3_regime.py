"""Fixed H1 trend / M5 volatility comparisons, explicitly descriptive."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from numba import njit

from scripts.research_bb3_candle_shapes import shape_allowed, simulate_shapes, source_stat, summarize
from scripts.research_bb3_context_timing import ROOT, TRADE_COLUMNS, aggregate, dump, timestamp

SPEC = ROOT / 'docs/quant_organization/experiments/bb3_regime_20260919/protocol.json'
CACHE = ROOT / 'agent_runs/bb3_gmo_2023_2025'
OUT = ROOT / 'agent_runs/bb3_regime_20260919'


@njit(cache=True)
def atr_series(ohlc):
    n = len(ohlc)
    tr = np.empty(n)
    atr = np.full(n, np.nan)
    for i in range(n):
        previous = ohlc[i - 1, 3] if i else ohlc[i, 3]
        tr[i] = max(ohlc[i, 1] - ohlc[i, 2], abs(ohlc[i, 1] - previous), abs(ohlc[i, 2] - previous))
        if i == 13:
            atr[i] = np.mean(tr[:14])
        elif i > 13:
            atr[i] = (atr[i - 1] * 13 + tr[i]) / 14
    return atr, tr


@njit(cache=True)
def regime_features(f, times):
    """M5 rows: slope, ATR/lag100mean, TR/priorATR, latest complete H1 end.

    H1 rows: end, O,H,L,C, ATR14, SMA20, normalized slope.
    """
    n = len(times)
    h = np.empty((n // 12 + 1, 8))
    count = 0
    for i in range(n - 11):
        if times[i] % 3600 != 0:
            continue
        complete = True
        for j in range(12):
            if times[i + j] != times[i] + j * 300:
                complete = False
        if complete:
            h[count] = (float(times[i] + 3600), f[i, 0], np.max(f[i:i + 12, 1]),
                        np.min(f[i:i + 12, 2]), f[i + 11, 3], np.nan, np.nan, np.nan)
            count += 1
    h = h[:count]
    hourly_atr, _ = atr_series(h[:, 1:5])
    for k in range(count):
        h[k, 5] = hourly_atr[k]
        if k >= 19:
            h[k, 6] = np.mean(h[k - 19:k + 1, 4])
        if k >= 22 and hourly_atr[k] > 0:
            h[k, 7] = (h[k, 6] - h[k - 3, 6]) / hourly_atr[k]
    atr, tr = atr_series(f[:, :4])
    r = np.full((n, 4), np.nan)
    k = -1
    for i in range(n):
        decision = times[i] + 300
        while k + 1 < count and h[k + 1, 0] <= decision:
            k += 1
        if k >= 0:
            r[i, 3] = h[k, 0]
            if decision - h[k, 0] < 3600:
                r[i, 0] = h[k, 7]
        if i >= 113:
            denominator = np.mean(atr[i - 100:i])
            if denominator > 0:
                r[i, 1] = atr[i] / denominator
        if i > 0 and atr[i - 1] > 0:
            r[i, 2] = tr[i] / atr[i - 1]
    return r, h


@njit(cache=True)
def regime_allowed(r, i, side, mode):
    if mode == 0:
        return True
    if mode in (1, 3):
        slope = r[i, 0]
        if np.isnan(slope) or side * slope <= -.25:
            return False
    if mode in (2, 3):
        ratio, impulse = r[i, 1:3]
        if not (.5 <= ratio <= 2. and impulse <= 2.5):
            return False
    return True


@njit(cache=True)
def simulate_regime(f, r, times, start, end, pip, cost, shape, regime):
    """Old shape state machine, plus regime failure cancels eligible candidate.

    Diagnostics first12 match shape replay; appended13th is regime rejection.
    """
    trades = np.empty((len(f), 9))
    count = distance_rejections = shape_rejections = regime_rejections = 0
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
                elif not shape_allowed(f, i, armed, shape):
                    cancelled = True
                    shape_rejections += 1
                elif not regime_allowed(r, i, armed, regime):
                    cancelled = True
                    regime_rejections += 1
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
    return trades[:count], np.array([open_net, dd, side, entry, last_close, pending, prep_count, signal_count, entry_i, target, distance_rejections, shape_rejections, regime_rejections])


def value_stats(values):
    gp, gl = float(values[values > 0].sum()), -float(values[values < 0].sum())
    return dict(trades=len(values), wins=int(np.sum(values > 0)),
                win_rate_pct=100 * float(np.mean(values > 0)) if len(values) else None,
                profit_factor=gp / gl if gl else None, net_pips=float(values.sum()))


def comparison_gates(candidate, baseline, protocol):
    rule = protocol['acceptance_gates']
    checks = {}
    for cost in ('normal', 'stress'):
        a, b = candidate[cost], baseline[cost]
        checks[cost + '.count'] = a['trades'] >= max(rule['min_count'], rule['min_relative_count'] * b['trades'])
        checks[cost + '.winrate'] = a['win_rate_pct'] is not None and b['win_rate_pct'] is not None and a['win_rate_pct'] >= b['win_rate_pct'] + rule['winrate_gain_pp']
        checks[cost + '.pf'] = a['profit_factor'] is not None and b['profit_factor'] is not None and a['profit_factor'] >= rule['pf_min'] and a['profit_factor'] > b['profit_factor']
        checks[cost + '.net'] = a['net_pips'] > b['net_pips'] and a['net_plus_open_pips'] > 0
        checks[cost + '.pairs'] = a['positive_pairs'] >= rule['positive_pairs']
        for year in ('2023', '2024', '2025'):
            ay, by = a['annual'][year], b['annual'][year]
            checks[f'{cost}.{year}.net'] = ay['net_pips'] > 0
            checks[f'{cost}.{year}.winrate'] = ay['win_rate_pct'] is not None and by['win_rate_pct'] is not None and ay['win_rate_pct'] >= by['win_rate_pct']
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(SPEC.read_text(encoding='utf-8'))
    assert protocol['status'] == 'SPEC_FROZEN'
    dump(output / 'protocol.json', protocol)
    paths = [SPEC, Path(__file__), ROOT / 'scripts/research_bb3_candle_shapes.py', ROOT / 'scripts/research_bb3_context_center5.py', ROOT / 'scripts/research_bb3_context_timing.py', CACHE / 'data_manifest.json']
    dump(output / 'code_hashes.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    manifests = {m['symbol']: m for m in json.loads((CACHE / 'data_manifest.json').read_text())}
    used, inputs = [], {}
    for symbol in protocol['symbols']:
        m = manifests[symbol]
        raw = Path(m['raw_path'])
        assert source_stat(raw) == m['stat'], 'Raw history changed; cache rejected'
        path = CACHE / f'{symbol}_features.npz'
        with np.load(path) as data:
            f, times = data['features'], data['times']
        digest = hashlib.sha256(times.tobytes() + f.tobytes()).hexdigest()
        assert digest == m['input_sha256'], 'Cached features changed'
        assert times[0] < timestamp('2023-01-01') and times[-1] < timestamp('2026-01-01') and np.all(np.diff(times) > 0)
        r, hourly = regime_features(f, times)
        np.savez_compressed(output / f'{symbol}_features.npz', features=f, times=times, regime=r, hourly=hourly)
        assert source_stat(raw) == m['stat']
        used.append(dict(**m, cached_npz_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         regime_sha256=hashlib.sha256(r.tobytes() + hourly.tobytes()).hexdigest(), complete_hours=len(hourly)))
        inputs[symbol] = f, r, times, .01 if symbol.endswith('JPY') else .0001
        print('FEATURES', symbol, flush=True)
    dump(output / 'data_manifest.json', used)
    rows, summaries, parity = [], {}, 0
    start, end = map(timestamp, protocol['periods']['continuous_descriptive'])
    for variant in protocol['search_space']:
        shape, mode = variant['shape'], variant['regime']
        identity = f's{shape}_r{mode}'
        groups, values, exit_times = {}, {}, {}
        for symbol, (f, r, times, pip) in inputs.items():
            geometry = None
            base_cost = protocol['cost_and_fill_model']['gmo_normal_pips'][symbol]
            for cost_name, cost in (('normal', base_cost), ('stress', base_cost + .2)):
                t, d = simulate_regime(f, r, times, start, end, pip, cost, shape, mode)
                if mode == 0:
                    old, diag = simulate_shapes(f, times, start, end, pip, cost, shape)
                    np.testing.assert_array_equal(t, old)
                    np.testing.assert_array_equal(d[:12], diag)
                    parity += 1
                    if cost_name == 'normal':
                        with np.load(CACHE / f'{symbol}_c{shape}.npz') as saved:
                            np.testing.assert_array_equal(t, saved['trades'])
                            np.testing.assert_array_equal(d[:12], saved['diagnostic'])
                if geometry is not None:
                    np.testing.assert_array_equal(t[:, :8], geometry)
                geometry = t[:, :8].copy()
                artifact = f'{identity}_{symbol}_{cost_name}.npz'
                np.savez_compressed(output / artifact, trades=t, diagnostic=d)
                exits = times[t[:, 4].astype(int)]
                annual = {str(y): value_stats(t[(exits >= timestamp(f'{y}-01-01')) & (exits < timestamp(f'{y + 1}-01-01')), 8]) for y in (2023, 2024, 2025)}
                row = dict(variant=identity, symbol=symbol, cost_case=cost_name, cost_pips=cost,
                           artifact=artifact, annual=annual, regime_rejections=int(d[12]), **summarize(t, d, times))
                rows.append(row)
                groups.setdefault(cost_name, []).append(row)
                values.setdefault(cost_name, []).append(t[:, 8])
                exit_times.setdefault(cost_name, []).append(exits)
        summaries[identity] = {}
        for cost_name, group in groups.items():
            total = aggregate(group)
            total['win_rate_pct'] = 100 * total['wins'] / total['trades'] if total['trades'] else None
            v, ex = np.concatenate(values[cost_name]), np.concatenate(exit_times[cost_name])
            total['annual'] = {str(y): value_stats(v[(ex >= timestamp(f'{y}-01-01')) & (ex < timestamp(f'{y + 1}-01-01'))]) for y in (2023, 2024, 2025)}
            total['largest_pair_mtm_drawdown_pips'] = max(row['bar_close_mtm_drawdown_pips'] for row in group)
            summaries[identity][cost_name] = total
        print('COMPLETE', identity, flush=True)
    checks = {f's{s}_r{r}': comparison_gates(summaries[f's{s}_r{r}'], summaries[f's{s}_r0'], protocol) for s in (0, 3) for r in (1, 2, 3)}
    eligible = [key for key, check in checks.items() if all(check.values())]
    result = dict(status='DESCRIPTIVE_GATES_PASSED_PENDING_AUDIT' if eligible else 'REJECTED_DESCRIPTIVE',
                  eligible=eligible, summaries=summaries, gates=checks, rows=rows,
                  baseline_exact_cases=parity, trade_columns=TRADE_COLUMNS, live_approved=False,
                  scope='Previously viewed descriptive data; not out-of-sample validation')
    dump(output / 'results.json', result)
    print('RESULT_JSON=' + str(output / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
