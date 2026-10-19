"""Independently reconcile the JPY-cross intraday study's saved trades and gates."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path

from verify_quant70_results import close, qualifies, require, summarize

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'docs/quant_organization/experiments/quant70_intraday_jpy_20260908'
SOURCE_PATHS = [ROOT/'scripts'/name for name in (
    'research_quant70_intraday_jpy.py', 'research_quant70_intraday.py', 'quant70_intraday_signals.py',
    'research_quant70.py', 'quant70_signals.py', 'research_strict_rr_portfolio.py')]
SOURCE_PATHS.append(ROOT/'src/forextester_backtest/data.py')
MONTHS = {'train': 108, 'validation': 48, 'confirmation': 24, 'recent_reference': 18}
COMPARISON_FAILURE = '当日状態追加による勝率・期待値の両方の改善なし'


def improves(summary, comparator):
    return (summary['expectancy_r'] is not None and comparator['expectancy_r'] is not None
            and summary['net_win_rate_pct'] > comparator['net_win_rate_pct']
            and summary['expectancy_r'] > comparator['expectancy_r'])


EXPECTED_SYMBOLS = ['AUDJPY', 'CHFJPY', 'EURJPY', 'GBPJPY']
PARENT_EXPERIMENT = ROOT / 'docs/quant_organization/experiments/quant70_intraday_20260908'


def verify_protocol(protocol):
    """Reject scope drift and preserve all gates except proportional breadth."""
    parent = json.loads((PARENT_EXPERIMENT/'protocol.json').read_text(encoding='utf-8'))
    require(protocol['experiment_id'] == 'quant70_intraday_jpy_20260908', 'experiment identity')
    require(protocol['symbols'] == EXPECTED_SYMBOLS, 'JPY cross universe')
    expected_gates = {**parent['gates'], 'min_positive_pairs': math.ceil(8/11*len(EXPECTED_SYMBOLS))}
    require(protocol['gates'] == expected_gates, 'gate drift')
    for field in ('timeframe', 'trend', 'candidate_budget', 'comparator_budget', 'search_space',
                  'periods', 'period_semantics', 'selection', 'stress', 'data_quality',
                  'day_definition', 'comparison', 'live_trading_authorized'):
        require(protocol[field] == parent[field], f'protocol invariant: {field}')
    # The frozen text retains the parent's 11-pair cap. Per-symbol non-overlap
    # below plus the four-symbol universe makes the effective maximum four.
    require(protocol['execution'] == parent['execution'], 'execution drift')

def verify(output):
    read = lambda name: json.loads((output/name).read_text(encoding='utf-8'))
    protocol, result, selection = read('protocol.json'), read('results.json'), read('selection.json')
    candidates, comparators = read('candidates.json'), read('comparators.json')
    manifest, hashes = read('data_manifest.json'), read('code_hashes.json')
    effects = read('context_effects.json')
    require(protocol == json.loads((EXPERIMENT/'protocol.json').read_text(encoding='utf-8')), 'protocol drift')
    for filename, values in (('candidates.json', candidates), ('comparators.json', comparators)):
        prior = ROOT/'agent_runs/quant70_intraday_20260908'/filename
        require(values == json.loads(prior.read_text(encoding='utf-8')), f'parent strategy drift: {filename}')
    require(set(hashes) == {p.name for p in SOURCE_PATHS}, 'source manifest files')
    for path in SOURCE_PATHS:
        require(hashlib.sha256(path.read_bytes()).hexdigest() == hashes[path.name], f'source drift: {path.name}')
    names = {c['name'] for c in candidates}
    comparison_names = {c['name'] for c in comparators}
    require(len(candidates) == len(names) == protocol['candidate_budget'] == 12, 'candidate count')
    require(len(comparators) == len(comparison_names) == 12, 'comparator count')
    require(not names & comparison_names, 'candidate/comparator overlap')
    require(all(c['selectable'] for c in candidates), 'nonselectable candidate')
    require(all(not c['selectable'] for c in comparators), 'selectable comparator')
    require({c['comparison_of'] for c in comparators} == names, 'ablation matching')
    matched = {c['comparison_of']: c['name'] for c in comparators}
    records = {r['candidate']['name']: r for r in result['records']}
    require(len(records) == len(result['records']) == 25, 'duplicate/missing result')
    require(set(records) == names | comparison_names | {'baseline_htf_hourly'}, 'result identities')
    for candidate in candidates + comparators:
        require(records[candidate['name']]['candidate'] == candidate, 'candidate drift')
    require(not records['baseline_htf_hourly']['candidate'].get('selectable', False), 'selectable baseline')
    require(result['candidate_count'] == 12 and not result['live_approved'], 'candidate count/live approval')
    periods = {p: tuple(datetime.fromisoformat(t) for t in times) for p, times in protocol['periods'].items()}
    selected = result['selected']
    require(selected is None or selected in names, 'selected comparator or unknown candidate')
    require(result['confirmation_evaluated'] == (selected is not None), 'confirmation state')
    verify_protocol(protocol)
    for key, item in manifest.items():
        endpoint = datetime.fromisoformat(key.split(':')[1])
        require(datetime.fromisoformat(item['end']) < endpoint, 'data beyond manifest endpoint')
        require(float(item['metadata']['values']['CommPerLot']) == 0, 'unverified commission')
    expected_loads = {f'{s}:2023-01-01' for s in protocol['symbols']}
    if selected is not None:
        expected_loads |= {f'{s}:2026-07-01' for s in protocol['symbols']}
    require(set(manifest) == expected_loads, 'unexpected prepared data')

    groups, reasons, prior_exit = defaultdict(list), Counter(), {}
    count = 0
    with (output/'trades.jsonl').open(encoding='utf-8') as file:
        for count, line in enumerate(file, 1):
            t = json.loads(line)
            name, label, symbol = t['candidate'], t['period'], t['symbol']
            period = label.removesuffix('_stress')
            stress = label.endswith('_stress')
            require(name in records and period in periods and symbol in protocol['symbols'], f'unknown trade {count}')
            require(label in ('train', 'validation') or (name == selected and period in ('confirmation', 'recent_reference')), f'unauthorized evaluation {count}')
            require(not stress or period in ('confirmation', 'recent_reference'), f'unexpected stress {count}')
            signal, entry, end_time = (datetime.fromisoformat(t[f]) for f in ('signal_time', 'entry_time', 'exit_time'))
            start, end = periods[period]
            require(start <= signal < entry <= end_time < end, f'period/ordering {count}')
            require(entry-signal == timedelta(minutes=15), f'entry gap {count}')
            require(all(v.minute % 15 == 0 and v.second == v.microsecond == 0 for v in (signal, entry, end_time)), f'unaligned trade {count}')
            key = name, label, symbol
            require(key not in prior_exit or signal > prior_exit[key], f'overlapping/reused signal {count}')
            prior_exit[key] = end_time
            d = t['direction']
            require(d in (-1, 1), f'direction {count}')
            risk = d*(t['entry']-t['stop'])
            require(risk > 0 and all(math.isfinite(t[f]) for f in ('entry', 'stop', 'target', 'exit', 'net_r')), f'price {count}')
            close(d*(t['target']-t['entry']), risk, f'RR1 {count}')
            close(t['net_r'], d*(t['exit']-t['entry'])/risk, f'net R {count}')
            require(t['reason'] in {'stop', 'target', 'stop_gap', 'target_gap', 'period_end'}, f'reason {count}')
            slip = (0.2 if stress else protocol['execution']['slippage_pips_each_side'])*(0.01 if symbol.endswith('JPY') else 0.0001)
            if t['reason'] in ('target', 'target_gap'):
                close(t['exit'], t['target']-d*slip, f'TP cost {count}')
            elif t['reason'] == 'stop':
                close(t['exit'], t['stop']-d*slip, f'SL cost {count}')
            elif t['reason'] == 'stop_gap':
                require(t['net_r'] <= -1, f'nonadverse stop gap {count}')
            else:
                require(end_time >= end-timedelta(days=7), f'premature final close {count}')
            groups[key].append((t['exit_time'], symbol, t['entry_time'], t['net_r'], t['reason'], t['ambiguous']))
            reasons[t['reason']] += 1

    independent = {}
    for name, record in records.items():
        expected_periods = {'train', 'validation'}
        if name == selected:
            expected_periods |= {'confirmation', 'recent_reference', 'confirmation_stress', 'recent_reference_stress'}
        require(set(record['periods']) == set(record['pairs']) == set(record['rejections']) == expected_periods, f'period coverage {name}')
        independent[name] = {'periods': {}, 'pairs': {}, 'passes': {}}
        for label in sorted(expected_periods):
            period = label.removesuffix('_stress')
            require(set(record['pairs'][label]) == set(protocol['symbols']), f'pair coverage {name}/{label}')
            combined, pair_stats = [], {}
            for symbol in protocol['symbols']:
                rows = groups[(name, label, symbol)]
                require(sum(t[4] == 'period_end' for t in rows) <= 1, 'multiple period closes')
                combined.extend(rows)
                pair_stats[symbol] = summary = summarize(rows, MONTHS[period])
                for field, stored in record['pairs'][label][symbol].items():
                    close(stored, summary[field], f'pair {name}/{label}/{symbol}/{field}')
            summary = summarize(combined, MONTHS[period])
            for field, stored in record['periods'][label].items():
                close(stored, summary[field], f'aggregate {name}/{label}/{field}')
            if label.endswith('_stress'):
                passed = summary['expectancy_r'] is not None and summary['expectancy_r'] > 0 and summary['profit_factor'] is not None and summary['profit_factor'] >= 1.15
            else:
                passed = qualifies(summary, pair_stats, period, protocol['gates'])
            absolute_reasons = [r for r in record['rejections'][label] if r != COMPARISON_FAILURE]
            require(passed == (not absolute_reasons), f'absolute gate {name}/{label}')
            independent[name]['periods'][label] = summary
            independent[name]['pairs'][label] = pair_stats
            independent[name]['passes'][label] = passed

    eligible, absolute_eligible, comparisons = [], [], {}
    effect_rows = {(e['candidate'], e['period']): e for e in effects}
    require(len(effects) == len(effect_rows) == 24, 'context effect count')
    require(set(effect_rows) == {(name, p) for name in names for p in ('train', 'validation')}, 'context effect identities')
    for name in sorted(names):
        absolute = all(independent[name]['passes'][p] for p in ('train', 'validation'))
        if absolute:
            absolute_eligible.append(name)
        comparison = {p: improves(independent[name]['periods'][p], independent[matched[name]]['periods'][p]) for p in ('train', 'validation')}
        comparisons[name] = {'comparator': matched[name], 'passes': comparison}
        for period, passed in comparison.items():
            require(passed == (COMPARISON_FAILURE not in records[name]['rejections'][period]), f'comparison gate {name}/{period}')
            row = effect_rows[name, period]
            require(row['comparator'] == matched[name] and row['passes'] == passed, 'saved comparison identity/pass')
            candidate_summary = independent[name]['periods'][period]
            comparator_summary = independent[matched[name]]['periods'][period]
            close(row['win_rate_delta_pp'], candidate_summary['net_win_rate_pct']-comparator_summary['net_win_rate_pct'], 'win rate effect')
            a, b = candidate_summary['expectancy_r'], comparator_summary['expectancy_r']
            close(row['expectancy_delta_r'], a-b if a is not None and b is not None else None, 'expectancy effect')
        if absolute and all(comparison.values()):
            eligible.append(name)
    winner = max(eligible, key=lambda name: (independent[name]['periods']['validation']['wilson_95_lower_pct'], independent[name]['periods']['validation']['profit_factor'], name)) if eligible else None
    require(selected == winner, 'winner mismatch')
    require(result['qualified_count'] == selection['qualified'] == len(eligible), 'eligible count')
    require(selection['selected'] == (records[winner]['candidate'] if winner else None), 'selection identity')
    require(selection['basis'] == 'train and validation only', 'selection basis')
    passes = bool(winner and all(independent[winner]['passes'].values()))
    require(result['status'] == ('RESEARCH_PASS' if passes else 'REJECTED'), 'final status')
    verification = {'status': 'VERIFIED_'+result['status'], 'source_hashes_match': True,
                    'trade_rows': count, 'candidate_count': 12, 'comparator_count': 12, 'baseline_count': 1,
                    'absolute_qualified_count': len(absolute_eligible), 'qualified_count': len(eligible),
                    'selected': winner, 'confirmation_evaluated': winner is not None,
                    'reason_counts': dict(reasons), 'comparisons': comparisons, 'records': independent,
                    'scope': 'Independent saved-trade reconciliation; no second OHLC backtest or tick-order certification.'}
    (output/'independent_verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return {k: v for k, v in verification.items() if k not in ('records', 'comparisons')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'agent_runs/quant70_intraday_jpy_20260908')
    args = parser.parse_args()
    print(json.dumps(verify(args.output), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
