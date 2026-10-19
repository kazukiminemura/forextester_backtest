"""Diagnose losses and freeze a small, causal filter search on existing 1H signals."""
import hashlib
import itertools
import json

import numpy as np

from research_sniper_daytrade import OUT, PERIODS, ROOT, SOURCE, metrics, selected
from research_sniper_vip import SYMBOLS

BASE_RULE = (18, 100, 100, (6, 16))


def apply_filter(rows, rule):
    cost, distance, strength = rule
    return rows[(rows[:, 10] <= cost) & (rows[:, 6] >= distance) & (rows[:, 5] >= strength)]


def detailed(rows):
    result = metrics(rows)
    r = rows[:, 3]
    result.update(losses=int((r < 0).sum()), gross_loss_r=float(-r[r < 0].sum()),
                  gross_gain_r=float(r[r > 0].sum()),
                  loss_rate=float((r < 0).mean()*100) if len(r) else None)
    return result


def admitted(data, rule):
    return {s: selected(apply_filter(rows, rule), BASE_RULE) for s, rows in data.items()}


def summarize(data):
    whole = np.concatenate(list(data.values()))
    return [detailed(whole[(whole[:, 2] >= a) & (whole[:, 2] <= b)]) for a, b in PERIODS]


def diagnose(data):
    rows = np.concatenate(list(data.values()))
    groups = {
        "cost_le_0.05_atr": rows[:, 10] <= .05,
        "cost_0.05_to_0.1_atr": (rows[:, 10] > .05) & (rows[:, 10] <= .1),
        "cost_gt_0.1_atr": rows[:, 10] > .1,
        "ema_distance_lt_1": rows[:, 6] < 1,
        "ema_distance_1_to_2": (rows[:, 6] >= 1) & (rows[:, 6] < 2),
        "ema_distance_ge_2": rows[:, 6] >= 2,
        "directional_rsi_lt_55": rows[:, 5] < 55,
        "directional_rsi_55_to_60": (rows[:, 5] >= 55) & (rows[:, 5] < 60),
        "directional_rsi_ge_60": rows[:, 5] >= 60,
        "stop_exit": (rows[:, 9] == 0) & (rows[:, 11] == 0),
        "time_exit": rows[:, 11] == 1,
        "target_exit": rows[:, 9] == 1,
    }
    groups.update({f"entry_hour_{hour}": rows[:, 7] == hour for hour in range(6, 16)})
    groups.update({f"loss_exit_after_{n}_bars": (rows[:, 1]-rows[:, 0] == n) & (rows[:, 3] < 0)
                   for n in range(5)})
    return {name: [detailed(rows[mask & (rows[:, 2] >= a) & (rows[:, 2] <= b)])
                   for a, b in PERIODS] for name, mask in groups.items()}


def overlap(base, filtered):
    result = []
    for a, b in PERIODS:
        removed, introduced = [], []
        for symbol in SYMBOLS:
            old, new = base[symbol], filtered[symbol]
            removed.extend(old[(old[:, 2] >= a) & (old[:, 2] <= b) & ~np.isin(old[:, 0], new[:, 0])])
            introduced.extend(new[(new[:, 2] >= a) & (new[:, 2] <= b) & ~np.isin(new[:, 0], old[:, 0])])
        result.append(dict(skipped_baseline=detailed(np.asarray(removed).reshape(-1, 12)),
                           newly_admitted=detailed(np.asarray(introduced).reshape(-1, 12))))
    return result


def main():
    protocol = dict(timeframe_minutes=60, symbols=SYMBOLS, periods=PERIODS,
                    max_spread_atr=(100, .1, .05), min_ema_distance_atr=(0, 1, 2),
                    min_directional_rsi=(52, 55, 60), candidates=27,
                    baseline="Original Pine setup edges, next open, SL1.5ATR TP3ATR, 4h exit, 06-16h, cooldown5",
                    selection="Development only: min PF, then min mean R; prefer candidates improving loss rate/PF/meanR in both periods",
                    counts=(500, 200, 100, 100), min_retention=.3, min_development_symbol_coverage=6,
                    success="Every period: PF and meanR above baseline; loss rate below baseline; count and retention gates",
                    profitable="Separate flag: PF>1 in every period",
                    limitations="Later aggregate periods previously inspected; not untouched holdout. Constant spread and assumed slippage; broker time zone unknown.")
    (ROOT/'scripts/sniper_loss_protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    previous = json.loads((ROOT/'scripts/sniper_daytrade_results.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert digest == previous['source_sha256'], 'Pine changed; cache cannot be reused'
    data, hashes = {}, {}
    for symbol in SYMBOLS:
        path = OUT/f'{symbol}_60.npz'
        data[symbol] = np.load(path)['rows']
        assert np.isfinite(data[symbol]).all()
        hashes[symbol] = hashlib.sha256(path.read_bytes()).hexdigest()
    base = {s: selected(rows, BASE_RULE) for s, rows in data.items()}
    baseline = summarize(base)
    reference = previous['baselines']['60']['periods']
    for actual, expected in zip(baseline, reference):
        for key, value in expected.items():
            assert np.isclose(actual[key], value), (key, actual, expected)
    development = {s: rows[rows[:, 2] <= 2022] for s, rows in data.items()}
    candidates = []
    for rule in itertools.product(protocol['max_spread_atr'], protocol['min_ema_distance_atr'], protocol['min_directional_rsi']):
        trades = admitted(development, rule)
        stats = summarize(trades)[:2]
        coverage = sum((r[:, 2] >= 2019).sum() >= 20 for r in trades.values())
        eligible = coverage >= 6 and all(m['n'] >= max(n, .3*b['n']) for m, b, n in zip(stats, baseline, (500, 200)))
        improves = eligible and all(m['pf'] > b['pf'] and m['mean_r'] > b['mean_r'] and m['loss_rate'] < b['loss_rate']
                                    for m, b in zip(stats, baseline))
        candidates.append(dict(rule=rule, development=stats, coverage=int(coverage), eligible=bool(eligible), improves=bool(improves)))
    ranked = sorted([c for c in candidates if c['eligible']],
                    key=lambda c: (c['improves'], min(m['pf'] for m in c['development']), min(m['mean_r'] for m in c['development'])), reverse=True)
    if not ranked:
        raise ValueError('No candidate meets sample gates')
    chosen = ranked[0]
    final = admitted(data, chosen['rule'])
    results = summarize(final)
    gates = [m['n'] >= max(n, .3*b['n']) and m['pf'] > b['pf'] and m['mean_r'] > b['mean_r'] and m['loss_rate'] < b['loss_rate']
             for m, b, n in zip(results, baseline, protocol['counts'])]
    payload = dict(protocol=protocol, source_sha256=digest, cache_sha256=hashes, baseline_verified=True,
                   selected=chosen, candidates=candidates, baseline=baseline, results=results,
                   gates=gates, loss_reduction_passed=all(gates), profitable_all_periods=all(m['pf'] > 1 for m in results),
                   diagnostics=diagnose(base), overlap=overlap(base, final),
                   per_symbol={s: dict(baseline=summarize({s: base[s]}), filtered=summarize({s: final[s]})) for s in SYMBOLS})
    path = ROOT/'scripts/sniper_loss_results.json'
    path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')
    print('RESULT_JSON', path)
    print(json.dumps({k: payload[k] for k in ('selected', 'baseline', 'results', 'gates', 'profitable_all_periods')}))


if __name__ == '__main__':
    main()
