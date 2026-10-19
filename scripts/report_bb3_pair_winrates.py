"""Fixed current-default BB descriptive report; no optimization or raw-data edits."""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np

from forextester_backtest import HistoryRepository
from scripts.research_bb3_context_center5 import simulate_center, descriptive_stats
from scripts.research_bb3_context_timing import EPOCH, ROOT, aggregate, dump, features, timestamp


def main():
    out = ROOT / 'agent_runs/bb3_pair_winrates_20260919'
    out.mkdir(exist_ok=False)
    symbols = 'USDJPY EURUSD GBPUSD AUDUSD NZDUSD USDCAD USDCHF EURJPY GBPJPY AUDJPY NZDJPY'.split()
    suspect = {'USDCHF', 'EURJPY', 'GBPJPY'}
    cache = ROOT / 'agent_runs/bb3_context_timing_20260909/completed'
    manifests = {m['symbol']: m for m in json.loads((cache / 'data_manifest.json').read_text())}
    start, end = timestamp('2023-09-08'), timestamp('2026-08-31')
    dump(out / 'protocol.json', dict(symbols=symbols, start='2023-09-08', end_exclusive='2026-08-31',
        timeframe='5m', min_center_pips=3, stop=False, cost_pips=1.4,
        exit='moving SMA20, previous confirmed target', entry='next available open',
        optimization=False, forced_end_exit=False, swap=False,
        suspect_symbols=sorted(suspect), source_timezone='unknown stored timestamps',
        data_quality='Prior Bars/tick sample mismatch; suspect symbols descriptive only. Common cutoff precedes GBPJPY scale anomaly.'))
    repo = HistoryRepository()
    rows = []
    for symbol in symbols:
        print('Loading', symbol, flush=True)
        raw = repo.root / symbol / 'Bars.dat'
        before = dict(size=raw.stat().st_size, mtime_ns=raw.stat().st_mtime_ns)
        pip = .01 if symbol.endswith('JPY') else .0001
        cached = symbol in manifests and before == manifests[symbol]['after']
        if cached:
            with np.load(cache / f'{symbol}_features.npz') as data:
                times, f = data['times'], data['features']
            keep = times < end
            times, f = times[keep], f[keep]
        else:
            bars = list(repo.bars(symbol, datetime(2023, 8, 1), datetime(2026, 8, 31) - timedelta(microseconds=1), '5m'))
            times = np.array([int((b.time - EPOCH).total_seconds()) for b in bars], dtype=np.int64)
            ohlc = np.array([(b.open, b.high, b.low, b.close) for b in bars])
            f = features(ohlc, times, pip, 10. ** -repo.metadata(symbol).decimals)
        assert len(times) and times[0] < start and times[-1] < end
        assert np.all(np.diff(times) > 0) and np.all(np.isfinite(f[:, :4])) and np.all(f[:, :4] > 0)
        assert before == dict(size=raw.stat().st_size, mtime_ns=raw.stat().st_mtime_ns)
        trades, diag = simulate_center(f, times, start, end, pip, 1.4, 3.)
        np.savez_compressed(out / f'{symbol}.npz', trades=trades, diagnostic=diag, times=times)
        row = dict(symbol=symbol, reference_only=symbol in suspect,
            raw_path=str(raw), raw_stat=before, reused_verified_cache=cached,
            input_sha256=hashlib.sha256(times.tobytes()+f.tobytes()).hexdigest(),
            **descriptive_stats(trades, diag))
        rows.append(row)
        print(json.dumps(row), flush=True)
    total = aggregate([r for r in rows if not r['reference_only']])
    total['win_rate_pct'] = 100 * total['wins'] / total['trades'] if total['trades'] else None
    dump(out / 'results.json', dict(rows=rows, main_eight_pair_total=total,
        code_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__), ROOT/'scripts/research_bb3_context_center5.py', ROOT/'scripts/research_bb3_context_timing.py', ROOT/'scripts/tradingview/bb3_context_pf_indicator.pine']}))
    print('RESULT_JSON=' + str(out / 'results.json'), flush=True)


if __name__ == '__main__':
    main()
