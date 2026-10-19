"""Fixed existing purple-marker rule, independently checked without tuning."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
import hashlib
import json

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from research_sniper_daytrade import OUT, ROOT, SOURCE, selected
from research_sniper_losses import BASE_RULE, summarize, overlap
from research_sniper_vip import SYMBOLS


def run_symbol(symbol):
    repo = HistoryRepository(r'C:\ForexTester6\data\History')
    spread = repo.metadata(symbol).spread_price
    rows = np.load(OUT/f'{symbol}_60.npz')['rows']
    bars = list(_aggregate_bars(repo.bars(symbol, datetime(2009, 1, 1), datetime(2026, 7, 17, 23, 59, 59), '5m'), timedelta(hours=1)))
    assert spread > 0 and (rows[:, 10] > 0).all()
    purple = []
    for row in rows:
        i = int(row[0])
        atr = spread / row[10]
        bar = bars[i-1]
        # Existing Pine: ADX minimum18 + 7, absolute candle body >= .5ATR.
        purple.append(row[4] >= 25 and abs(bar.close-bar.open) >= .5*atr)
    filtered = selected(rows[np.asarray(purple)], BASE_RULE)
    return symbol, selected(rows, BASE_RULE), filtered


def main():
    previous = json.loads((ROOT/'scripts/sniper_loss_results.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == previous['source_sha256']
    for symbol, digest in previous['cache_sha256'].items():
        assert hashlib.sha256((OUT/f'{symbol}_60.npz').read_bytes()).hexdigest() == digest
    protocol = dict(rule='Existing purple marker: ADX>=25 and absolute body>=0.5ATR; original EMA filter ON',
                    tuning=False, selection=False, source_sha256=previous['source_sha256'],
                    disclosure='Fixed descriptive audit after inspecting the separate loss-filter results; not a new untouched holdout.')
    (ROOT/'scripts/sniper_purple_protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    base, filtered = {}, {}
    with ProcessPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(run_symbol, s) for s in SYMBOLS]):
            symbol, b, f = future.result()
            base[symbol], filtered[symbol] = b, f
            print('DONE', symbol, len(b), len(f), flush=True)
    # Preserve symbol ordering for reproducible aggregation.
    base = {s: base[s] for s in SYMBOLS}
    filtered = {s: filtered[s] for s in SYMBOLS}
    baseline, results = summarize(base), summarize(filtered)
    for actual, expected in zip(baseline, previous['baseline']):
        assert all(np.isclose(actual[k], v) for k, v in expected.items())
    gates = [m['n'] >= max(n, .3*b['n']) and m['pf'] > b['pf'] and m['mean_r'] > b['mean_r'] and m['loss_rate'] < b['loss_rate']
             for m, b, n in zip(results, baseline, (500, 200, 100, 100))]
    result = dict(protocol=protocol, baseline=baseline, results=results, gates=gates,
                  loss_reduction_passed=all(gates), profitable_all_periods=all(m['pf'] > 1 for m in results),
                  overlap=overlap(base, filtered),
                  per_symbol={s: dict(baseline=summarize({s: base[s]}), filtered=summarize({s: filtered[s]})) for s in SYMBOLS})
    path = ROOT/'scripts/sniper_purple_results.json'
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print('RESULT_JSON', path, flush=True)
    print(json.dumps(dict(results=results, gates=gates)), flush=True)


if __name__ == '__main__':
    main()
