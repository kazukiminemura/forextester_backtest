"""Three fixed TP1 protection variants; preserve the original Sniper entries."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
import hashlib
import json

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.sniper_defense import MODES, defensive_outcome
from research_sniper_daytrade import OUT, ROOT, SOURCE, outcome, selected
from research_sniper_losses import BASE_RULE, summarize
from research_sniper_vip import SYMBOLS


def run_symbol(symbol):
    repo = HistoryRepository(r'C:\ForexTester6\data\History')
    spread = repo.metadata(symbol).spread_price
    rows = np.load(OUT/f'{symbol}_60.npz')['rows']
    bars = list(_aggregate_bars(repo.bars(symbol, datetime(2009, 1, 1), datetime(2026, 7, 17, 23, 59, 59), '5m'), timedelta(hours=1)))
    ema, value = [], bars[0].close
    for bar in bars:
        value += (bar.close-value)*2/101
        ema.append(value)
    variants = {mode: [] for mode in MODES}
    for row in rows:
        i = int(row[0])
        atr = spread/row[10]
        side = 1 if bars[i-1].close > ema[i-1] else -1
        original = outcome(bars, i, side, atr, spread, 60)
        assert original is not None
        assert original[0] == row[1] and np.isclose(original[1], row[3], atol=1e-9)
        for mode in MODES:
            result = defensive_outcome(bars, i, side, atr, spread, mode)
            assert result is not None
            j, r, reason, late = result
            updated = row.copy()
            updated[[1, 2, 3, 8, 9, 11]] = j, bars[j].time.year, r, late, reason == 'target', reason == 'time'
            variants[mode].append(updated)
    return symbol, {mode: selected(np.asarray(v).reshape(-1, 12), BASE_RULE) for mode, v in variants.items()}


def main():
    prior = json.loads((ROOT/'scripts/sniper_loss_results.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == prior['source_sha256']
    for symbol, digest in prior['cache_sha256'].items():
        assert hashlib.sha256((OUT/f'{symbol}_60.npz').read_bytes()).hexdigest() == digest
    protocol = dict(modes=MODES, tp1_atr=1, tp3_atr=3, stop_atr=1.5, deadline_hours=4,
                    stop_change='Next bar only; stop first if ambiguous',
                    selection='Choose maximum minimum PF on 2010-2018 and 2019-2022 only; no entry filtering',
                    baseline_audit='Reconstruct each original cost-aware trade and require equality before testing exits',
                    limitations='Hypotheses motivated by original loss diagnostics; later periods repeatedly viewed; not untouched holdout')
    (ROOT/'scripts/sniper_defense_protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    data = {mode: {} for mode in MODES}
    with ProcessPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(run_symbol, s) for s in SYMBOLS]):
            symbol, variants = future.result()
            for mode in MODES:
                data[mode][symbol] = variants[mode]
            print('DONE', symbol, flush=True)
    development = {mode: summarize({s: data[mode][s][data[mode][s][:, 2] <= 2022] for s in SYMBOLS})[:2] for mode in MODES}
    chosen = max(MODES, key=lambda mode: min(m['pf'] for m in development[mode]))
    final = summarize({s: data[chosen][s] for s in SYMBOLS})
    gates = [m['n'] >= n and m['pf'] > b['pf'] and m['mean_r'] > b['mean_r'] and m['gross_loss_r'] < b['gross_loss_r']
             for m, b, n in zip(final, prior['baseline'], (500, 200, 100, 100))]
    result = dict(protocol=protocol, selected=chosen, development=development, baseline=prior['baseline'],
                  results=final, gates=gates, loss_reduction_passed=all(gates),
                  profitable_all_periods=all(m['pf'] > 1 for m in final), source_sha256=prior['source_sha256'],
                  per_symbol={s: summarize({s: data[chosen][s]}) for s in SYMBOLS})
    path = ROOT/'scripts/sniper_defense_results.json'
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print('RESULT_JSON', path, flush=True)
    print(json.dumps(dict(selected=chosen, results=final, gates=gates)), flush=True)


if __name__ == '__main__':
    main()
