"""Independent daily/hour gates plus previously independent RR1 execution reference.

No production gate/execution functions are used to compute expected outcomes.
The production module is imported only for prefix-invariance tests.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OLD = ROOT/'agent_runs/yosuga_channel_20261003/completed'
DEST = ROOT/'agent_runs/yosuga_daily_time_20261006/independent'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


ref = module('old_independent_reference', OLD.parent/'independent/verify.py')
counts = Counter()


def equal(actual, expected, name):
    ref.check_equal(actual, expected, name, counts)


def days_reference(t, p, complete):
    result = {}
    for day in sorted(set((t//86400).tolist())):
        a, b = np.searchsorted(t, [day*86400, (day+1)*86400])
        part = p[a:b]
        move = part[-1, 3]-part[0, 0]
        span = max(part[:, 1])-min(part[:, 2])
        row = dict(day=day, observed_bars=int(b-a), complete_bars=int(sum(complete[a:b])),
                   first_second=int(t[a]-day*86400), last_second=int(t[b-1]-day*86400),
                   max_gap_seconds=max(map(int, np.diff(t[a:b])), default=0),
                   direction=int(np.sign(move)), efficiency=float(abs(move)/span) if span else 0.)
        row['quality_ok'] = (b-a >= 270 and sum(complete[a:b]) >= 260 and t[a] <= day*86400+1800
                             and t[b-1] >= day*86400+84300 and row['max_gap_seconds'] <= 1800)
        row['quality_ok'] = bool(row['quality_ok'])
        result[day] = row
    return result


def gate_reference(t, p, complete, s, days, pip, cost, arm):
    i, side = s['index'], s['side']
    evidence = dict(gate_signal_close=int(t[i]+300))
    if arm in ('daily', 'combined'):
        if (t[i]+300)//86400 != t[i]//86400:
            return 'daily_entry_date_change', evidence
        prior = int((t[i]+300)//86400)-1
        evidence['daily_previous_day'] = prior
        if prior not in days:
            return 'daily_missing_previous_day', evidence
        d = days[prior]
        evidence['daily_evidence'] = d
        if not d['quality_ok']:
            return 'daily_quality', evidence
        if d['efficiency'] < 0.3:
            return 'daily_efficiency', evidence
        if d['direction'] != side:
            return 'daily_direction', evidence
    if arm in ('hourly', 'combined'):
        if i >= 11:
            view = p[i-11:i+1]
            quality = bool(np.all(np.diff(t[i-11:i+1]) == 300) and all(complete[i-11:i+1]))
            move = view[-1, 3]-view[0, 0]
            span = max(view[:, 1])-min(view[:, 2])
            efficiency = float(abs(move)/span) if span else 0.
            direction = int(np.sign(move))
        else:
            quality, efficiency, direction = False, 0., 0
        evidence.update(hour_quality=quality, hour_efficiency=efficiency, hour_direction=direction)
        if not quality:
            return 'hourly_quality', evidence
        if efficiency < 0.3:
            return 'hourly_efficiency', evidence
        if direction != side:
            return 'hourly_direction', evidence
        risk = side*(p[i, 3]-s['stop'])/pip
        ratio = float(cost/risk) if risk > 0 else None
        evidence['signal_cost_risk'] = ratio
        if ratio is None or ratio > .2+1e-12:
            return 'signal_cost_risk', evidence
    return 'allowed', evidence


def next_gate(t, p, s, pip, tick, arm, cost):
    i = s['index']+1
    risk = s['side']*(p[i, 0]-s['stop'])
    room = s['side']*(s['line_target']-p[i, 0])
    if t[i]-t[i-1] != 300:
        return 'entry_gap', {}
    if risk < tick-1e-10:
        return 'entry_invalid_risk', {}
    if room+1e-10 < risk:
        return 'entry_line_room', {}
    if arm in ('daily', 'combined') and t[i]//86400 != t[i-1]//86400:
        return 'daily_entry_date_change', {}
    if arm in ('hourly', 'combined'):
        audit = dict(entry_cost_risk=float(cost/(risk/pip)))
        return ('entry_cost_risk' if audit['entry_cost_risk'] > .2+1e-12 else 'entered'), audit
    return 'entered', {}


def replay_reference(t, p, complete, signals, turns, days, pip, tick, arm, cost, start, end):
    last = int(np.searchsorted(t, end))
    selected = [s for s in signals if start <= t[s['setup_index']] and start <= t[s['index']] < end]
    filtered = []
    evidence = {}
    for s in selected:
        i = s['index']
        reason, audit = ('allowed', {}) if arm == 'baseline' else gate_reference(t, p, complete, s, days, pip, cost, arm)
        evidence[i] = (reason, audit)
        if reason == 'allowed' and i < last-1 and next_gate(t, p, s, pip, tick, arm, cost)[0] == 'entered':
            filtered.append(s)
    trades, _, curve = ref.replay(t, p, filtered, turns, pip, tick, 'pullback_rr1', cost, start, end, complete)
    trade_by_signal = {r['index']: r for r in trades}
    ledger = []
    occupied_until = -1
    for s in selected:
        i = s['index']
        reason, audit = evidence[i]
        row = dict(s)
        if arm != 'baseline':
            row.update(audit, signal_gate=reason)
        if i < occupied_until:
            status = 'occupied'
        elif i == last-1:
            status = 'pending_period_end'
        elif reason != 'allowed':
            status = reason
        else:
            status, entry_audit = next_gate(t, p, s, pip, tick, arm, cost)
            row.update(entry_audit)
        row['status'] = status
        ledger.append(row)
        if status == 'entered':
            assert i in trade_by_signal
            trade = trade_by_signal[i]
            occupied_until = trade['exit_index']
            trade.update(row)
    return trades, ledger, curve


def bootstrap(trades, start, end):
    first = np.datetime64(start, 's').astype('datetime64[M]')
    n = int(np.datetime64(end, 's').astype('datetime64[M]').astype(int)-first.astype(int))
    totals = np.zeros(n); sample_counts = np.zeros(n, dtype=int)
    for r in trades:
        month = int(np.datetime64(r['entry_time'], 's').astype('datetime64[M]').astype(int)-first.astype(int))
        totals[month] += r['net_r']; sample_counts[month] += 1
    rng = np.random.default_rng(20261006)
    estimates = []
    for sample in rng.integers(n, size=(5000, n)):
        weights = np.bincount(sample, minlength=n)
        denom = int(weights @ sample_counts)
        if denom:
            estimates.append(float(weights @ totals)/denom)
    return dict(ci95_mean_r=np.quantile(estimates, [.025, .975]).tolist() if estimates else [None, None],
                monthly_net_r=totals.tolist(), monthly_trades=sample_counts.tolist(),
                first_month=str(first), draws=5000, seed=20261006)


def checks(normal, stress):
    return dict(n100=normal['trades'] >= 100, pf110=normal['profit_factor_r'] is not None and normal['profit_factor_r'] >= 1.1,
                mean_positive=normal['mean_net_r'] is not None and normal['mean_net_r'] > 0,
                ci_positive=normal['ci95_mean_r'][0] is not None and normal['ci95_mean_r'][0] > 0,
                positive_pairs4=normal['positive_pairs'] >= 4, leave_one_positive=normal['leave_one_pair_min_net_r'] > 0,
                stress_positive=stress['net_r'] > 0)


def run(output):
    DEST.mkdir(parents=True, exist_ok=True)
    manifest, protocol, result = [ref.read(output/name) for name in ('run_manifest.json', 'protocol.json', 'results.json')]
    assert 'completed_utc' in manifest
    assert ref.sha(output/'results.json') == manifest['results_sha256']
    assert ref.sha(ROOT/'scripts/research_yosuga_daily_time.py') == manifest['code_sha256']
    assert ref.sha(ROOT/'tests/test_yosuga_daily_time.py') == manifest['tests_sha256']
    assert ref.sha(ROOT/'scripts/research_yosuga_channel.py') == manifest['baseline_code_sha256']
    source = ROOT/'docs/quant_organization/experiments/yosuga_daily_time_20261006/protocol.json'
    assert ref.sha(source) == manifest['protocol_sha256']
    equal(protocol, ref.read(source), 'protocol')
    for path, digest in protocol['frozen_identifiers'].items():
        assert ref.sha(ROOT/path) == digest, path
    entries = {e['symbol']: e for e in ref.read(ROOT/protocol['data_manifest'])}
    old_manifest = ref.read(OLD/'run_manifest.json')
    mask_ids = {e['symbol']: e['mask_sha256'] for e in old_manifest['inputs']}
    sys.path.insert(0, str(ROOT/'scripts'))
    production = module('production_for_prefix_tests', ROOT/'scripts/research_yosuga_daily_time.py')
    generated, expected_cases, curves = {}, [], {}
    for symbol in protocol['symbols']:
        entry = entries[symbol]
        path = ROOT/protocol['cache_directory']/f'{symbol}_features.npz'
        assert ref.sha(path) == entry['cache_sha256']
        mask_path = OLD/f'{symbol}_complete_m5.npz'
        assert ref.sha(mask_path) == mask_ids[symbol]
        with np.load(path) as z:
            t, p = z['times'], z['features'][:, :4]
        complete = np.load(mask_path)['complete']
        signals = ref.read(OLD/f'{symbol}_signals.json')['pullback_rr1']
        equal(ref.read(output/f'{symbol}_signals.json'), signals, symbol+'unchanged_signals')
        turns = np.load(OLD/f'{symbol}_turns.npz')['turns']
        days = days_reference(t, p, complete)
        equal(ref.read(output/f'{symbol}_days.json'), list(days.values()), symbol+'daily_features')
        full_context = production.context(t, p, complete)
        # Full future-bearing arrays must produce identical decisions to truncated
        # information available at eight distinct candidate closes per symbol.
        for position in np.unique(np.linspace(0, len(signals)-1, min(8, len(signals)), dtype=int)):
            s = signals[position]; i = s['index']
            prefix_context = production.context(t[:i+1], p[:i+1], complete[:i+1])
            for arm in protocol['arms'][1:]:
                a = production.signal_gate(t, p, s, full_context, entry['pip'], protocol['spread_pips'][symbol], arm)
                b = production.signal_gate(t[:i+1], p[:i+1], s, prefix_context, entry['pip'], protocol['spread_pips'][symbol], arm)
                equal(a, b, symbol+'prefix_'+arm)
                counts['prefix_checks'] += 1
        for period in protocol['periods']:
            start, end = [int(np.datetime64(period[k], 's').astype(int)) for k in ('start', 'end')]
            for arm in protocol['arms']:
                for cost_multiplier in protocol['cost_multipliers']:
                    cost = protocol['spread_pips'][symbol]*cost_multiplier
                    trades, ledger, curve = replay_reference(t, p, complete, signals, turns, days, entry['pip'], entry['tick'], arm, cost, start, end)
                    prefix = f"{symbol}_{period['label']}_{arm}_costx{cost_multiplier:g}"
                    equal(ref.read(output/f'{prefix}_trades.json'), trades, prefix+'trades')
                    equal(ref.read(output/f'{prefix}_ledger.json'), ledger, prefix+'ledger')
                    equal(np.load(output/f'{prefix}_mtm.npz')['mtm'], curve, prefix+'mtm')
                    if arm == 'baseline':
                        old_prefix = prefix.replace('_baseline_', '_pullback_rr1_')
                        equal(ref.read(output/f'{prefix}_trades.json'), ref.read(OLD/f'{old_prefix}_trades.json'), prefix+'original_baseline_trades')
                        equal(ref.read(output/f'{prefix}_ledger.json'), ref.read(OLD/f'{old_prefix}_ledger.json'), prefix+'original_baseline_ledger')
                        equal(np.load(output/f'{prefix}_mtm.npz')['mtm'], np.load(OLD/f'{old_prefix}_mtm.npz')['mtm'], prefix+'original_baseline_mtm')
                        counts['baseline_cases'] += 1
                    observed = sorted(set((t[(t >= start) & (t < end)]//86400).tolist()))
                    traded = sorted(set(r['entry_time']//86400 for r in trades))
                    stats = dict(ref.metrics(trades), bar_close_mtm_drawdown_r=ref.dd(curve),
                                 candidate_statuses=dict(Counter(r['status'] for r in ledger)),
                                 signal_gate_reasons=dict(Counter(r.get('signal_gate', 'allowed') for r in ledger)),
                                 trades_exposed_to_incomplete_m5=sum(r['incomplete_m5_held'] > 0 for r in trades),
                                 observed_days=len(observed), trading_days=len(traded), trading_day_fraction=len(traded)/len(observed),
                                 observed_day_ids=observed, trading_day_ids=traded)
                    row = dict(symbol=symbol, period=period['label'], arm=arm, cost_multiplier=cost_multiplier, cost_pips=cost, **stats)
                    equal(next(r for r in result['cases'] if all(r[k] == row[k] for k in ('symbol', 'period', 'arm', 'cost_multiplier'))), row, prefix+'summary')
                    expected_cases.append(row)
                    key = (period['label'], arm, cost_multiplier)
                    generated.setdefault(key, []).extend(dict(symbol=symbol, **r) for r in trades)
                    curves.setdefault(key, []).append(curve)
                    counts['cases'] += 1; counts['trades'] += len(trades); counts['ledger_rows'] += len(ledger)
        counts['symbols'] += 1; counts['m5_bars'] += len(t)
        ref.put(DEST/'progress.json', dict(counts))
        print('VERIFIED '+symbol, flush=True)
    expected_totals = []
    for period in protocol['periods']:
        start, end = [int(np.datetime64(period[k], 's').astype(int)) for k in ('start', 'end')]
        for arm in protocol['arms']:
            for multiplier in protocol['cost_multipliers']:
                key = (period['label'], arm, multiplier)
                items = [r for r in expected_cases if (r['period'], r['arm'], r['cost_multiplier']) == key]
                all_t = np.unique(np.concatenate([c[:, 0] for c in curves[key]]))
                equity = np.zeros(len(all_t))
                for c in curves[key]:
                    loc = np.searchsorted(c[:, 0], all_t, side='right')-1
                    valid = loc >= 0
                    equity[valid] += c[loc[valid], 1]
                curve = np.column_stack((all_t, equity))
                equal(np.load(output/f"{key[0]}_{arm}_costx{multiplier:g}_combined_mtm.npz")['mtm'], curve, str(key)+'combined_curve')
                observed = set().union(*(set(r['observed_day_ids']) for r in items))
                traded = set().union(*(set(r['trading_day_ids']) for r in items))
                stats = ref.metrics(generated[key])
                stats.update(bootstrap(generated[key], start, end), bar_close_mtm_drawdown_r=ref.dd(curve),
                             positive_pairs=sum(r['net_r'] > 0 for r in items),
                             leave_one_pair_min_net_r=min(stats['net_r']-r['net_r'] for r in items),
                             observed_days=len(observed), trading_days=len(traded), trading_day_fraction=len(traded)/len(observed),
                             observed_pair_days=sum(r['observed_days'] for r in items), trading_pair_days=sum(r['trading_days'] for r in items),
                             candidate_statuses=dict(sum((Counter(r['candidate_statuses']) for r in items), Counter())),
                             signal_gate_reasons=dict(sum((Counter(r['signal_gate_reasons']) for r in items), Counter())),
                             trades_exposed_to_incomplete_m5=sum(r['trades_exposed_to_incomplete_m5'] for r in items))
                row = dict(period=key[0], arm=arm, cost_multiplier=multiplier, **stats)
                equal(next(r for r in result['totals'] if (r['period'], r['arm'], r['cost_multiplier']) == key), row, str(key)+'total')
                expected_totals.append(row)
    lookup = {(r['period'], r['arm'], r['cost_multiplier']): r for r in expected_totals}
    train_checks, eligible = {}, []
    for arm in protocol['arms'][1:]:
        normal, stress = lookup[('2020_2022', arm, 1.)], lookup[('2020_2022', arm, 1.5)]
        train_checks[arm] = checks(normal, stress)
        if all(train_checks[arm].values()):
            eligible.append((normal['mean_net_r'], -protocol['arms'].index(arm), arm))
    selection = dict(selected=max(eligible)[2] if eligible else None, checks=train_checks,
                     based_only_on='2020_2022', later_results_change_selection=False)
    equal(result['training_selection'], selection, 'selection')
    saved_selection = ref.read(output/'training_selection.json')
    equal({k: saved_selection[k] for k in selection}, selection, 'persisted_selection')
    equal(saved_selection['totals'], [r for r in expected_totals if r['period'] == '2020_2022'], 'persisted_training_totals')
    assert ref.sha(output/'training_selection.json') == manifest['training_selection_sha256']
    assert manifest['started_utc'] < saved_selection['saved_utc'] < manifest['completed_utc']
    if selection['selected'] is None:
        assert result['final_confirmation'] is None
    chosen = selection['selected']
    later = ({q['label']: checks(lookup[(q['label'], chosen, 1.)], lookup[(q['label'], chosen, 1.5)])
              for q in protocol['periods'][1:]} if chosen else {})
    equal(result['later_descriptive_screens'], later, 'later_screens')
    report = dict(status='ALL_MATCH', verdict='不採用' if selection['selected'] is None else '要後期判定', counts=dict(counts),
                  production_results_sha256=ref.sha(output/'results.json'), verifier_sha256=ref.sha(__file__),
                  old_independent_reference_sha256=ref.sha(OLD.parent/'independent/verify.py'),
                  training_selection=selection, cases=expected_cases, totals=expected_totals,
                  limitations=['No threshold sensitivity; 0.30 and coverage criteria fixed.',
                               'Source clock/quote side unresolved; historical variable spread/slippage/swap unimplemented.',
                               'Signals reuse independently verified frozen 20261003 saved candidates; not freshly reconstructed here.',
                               'All periods previously viewed. No live approval.'])
    ref.put(DEST/'verification.json', report)
    print('ALL_MATCH '+str(DEST/'verification.json'), flush=True)


def synthetic():
    fixture = module('synthetic_fixtures', ROOT/'tests/test_yosuga_daily_time.py')
    case_count = 0
    for side in (1, -1):
        for mutation in ('none', 'incomplete_entry', 'gap_stop', 'gap_target', 'both', 'time_gap'):
            t, p, c = fixture.sample()
            if mutation == 'incomplete_entry':
                c[311] = False
            if mutation == 'gap_stop':
                p[312] = [101, 102, 100, 101.5]
            if mutation == 'gap_target':
                p[312] = [105, 106, 104, 105.5]
            if mutation == 'both':
                p[312] = [103.31, 105, 101, 103.3]
            if mutation == 'time_gap':
                t[311:] += 300
            if side == -1:
                p = 300-p[:, [0, 2, 1, 3]]
            signals = [fixture.signal(t, p, i=i, side=side) for i in (310, 320)]
            days = days_reference(t, p, c)
            for arm in fixture.y.ARMS:
                for cost in (.1, .15):
                    actual = fixture.run_sim(t, p, c, arm=arm, candidates=signals, cost=cost)
                    trades, ledger, curve = replay_reference(t, p, c, signals, np.zeros(len(t)), days,
                                                             1., .01, arm, cost, int(t[0]), int(t[-1]+300))
                    label = str((side, mutation, arm, cost))
                    equal(actual['trades'], trades, label+'trades')
                    equal(actual['ledger'], ledger, label+'ledger')
                    equal(actual['mtm'], curve, label+'mtm')
                    case_count += 1
    DEST.mkdir(parents=True, exist_ok=True)
    ref.put(DEST/'synthetic_checks.json', dict(status='ALL_MATCH', cases=case_count, counts=dict(counts),
                                             verifier_sha256=ref.sha(__file__),
                                             production_sha256=ref.sha(ROOT/'scripts/research_yosuga_daily_time.py')))
    print('SYNTHETIC_ALL_MATCH', case_count)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'agent_runs/yosuga_daily_time_20261006/completed')
    parser.add_argument('--synthetic', action='store_true')
    args = parser.parse_args()
    synthetic() if args.synthetic else run(args.output)
