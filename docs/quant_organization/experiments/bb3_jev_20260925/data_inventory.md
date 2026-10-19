# Data inventory: Jev comparison, 2026-09-25

## Scope and disposition

Read-only verification of the seven existing 2023–2025 feature caches. No API,
strategy simulation, raw-history edits, or adoption decision was performed.
Caches can be reused for a **previously explored, descriptive comparison**,
subject to the limitations below. They are not an untouched holdout.

Primary source: `C:/ForexTester6/data/History/<symbol>/Bars.dat`.
Reader: `HistoryRepository`; cache producer: `scripts/report_bb3_gmo_three_year.py`.
Cache/manifest directory: `agent_runs/bb3_gmo_2023_2025/`.

All caches start at 2022-12-01 00:00:00 and end at 2025-12-31 21:55:00,
in the **unknown source timezone**. December 2022 is warmup; applicable analysis
window is 2023-01-01 inclusive through 2026-01-01 exclusive. Epoch seconds are
arithmetic coordinates, not evidence of UTC. Do not convert them to news or
Japanese trading-session timestamps without independently resolving timezone.

| Pair | Cached M5 rows | Adjacent gaps >300s | Source M1 records | Source first date | Pip / quote | Metadata spread pips |
|---|---:|---:|---:|---|---|---:|
| USDJPY | 230571 | 231 | 8534100 | 2003-05-06 | 0.01 / JPY | 1.2 |
| EURUSD | 230485 | 247 | 8567792 | 2003-05-06 | 0.0001 / USD | 1.1 |
| GBPUSD | 230492 | 231 | 8680197 | 2003-05-06 | 0.0001 / USD | 1.4 |
| AUDUSD | 229752 | 267 | 6286639 | 2009-10-01 | 0.0001 / USD | 1.2 |
| NZDUSD | 229944 | 291 | 8572858 | 2003-08-05 | 0.0001 / USD | 1.4 |
| AUDJPY | 230095 | 299 | 8479694 | 2003-12-02 | 0.01 / JPY | 1.4 |
| NZDJPY | 229926 | 286 | 7624497 | 2006-01-04 | 0.01 / JPY | 1.7 |

Total cached rows: **1,611,265**. All source M1 last timestamps are
2026-09-07 23:59:00 (header/endpoint inspection only, not full-source audit).
Maximum adjacent cached gap is 259500 seconds for each pair. Gaps include
weekends/holidays and potentially missing data; no complete market-calendar
classification or proof of minute completeness was attempted.

## Verified this run

- Every NPZ has exactly `features` and `times`: float64 `(n,15)` and int64 `(n,)`.
- Every count and first/last timestamp matches `data_manifest.json`.
- All seven cache digests match the manifest. Exact digest semantics are
  `sha256(times.tobytes() + features.tobytes())`, **not** NPZ-file or raw-file hash.
- All seven current Bars.dat size/mtime-nanosecond pairs match the manifest.
  Size/mtime matching does not cryptographically authenticate raw contents.
- Full cached-array checks found zero duplicate/non-increasing timestamps,
  non-300-second-aligned timestamps, nonfinite/nonpositive OHLC values, or
  high/low enclosure violations. No feature NaNs remain after row 20.
- Sample-only source comparison: first, midpoint, and last cached M5 bar per
  pair were reread and aggregated through HistoryRepository. All **21/21** time
  and OHLC tuples match exactly. Entire M1/tick history was not rescanned.
- Four current code SHA256 hashes match the cache's `code_hashes.json`:
  report runner, candle_shapes, context_center5, and context_timing.

## Semantics and unresolved limitations

`features` columns are O,H,L,C,SMA20,upper3sigma,lower3sigma,priorATR14,
priorHigh12,priorLow12,buyExplained,sellExplained,buyWick,sellWick,gap.
These are input features, not evidence that the new reversal-entry strategy
has already been tested. That strategy must be replayed separately.

HistoryRepository decodes Bars records as O,C,H,L, then aggregates into
clock-aligned five-minute buckets with open=first, high=max, low=min,
close=last. The timestamp is the **bucket start**; bar information becomes
available only on close. Aggregation does not demand five constituent M1 bars,
so partial buckets are possible. No missing data was filled or substituted.

`info.dat` labels all seven feeds Advanced Data Feed, lot=100000,
ApplyCommission=0 and CommPerLot=0.00; these are local metadata, not a GMO
execution contract. Spread points are converted by decimals (JPY=3,
non-JPY=5). Pip convention is frozen by the cache producer; quote currency is
the last three symbol characters per `InstrumentMetadata.pnl_currency`.
Cached OHLC has no separate Bid/Ask fields. This audit does not establish its
price side with a fresh tick reconstruction, nor historical actual spread.
Lot sizing and account-currency monetary conversion are not supplied by these
feature arrays; pooled pips would be a research score, not account P/L.

The old producer's GMO cost assumptions were 0.2/0.3/0.6/0.4/1.6/0.5/0.6 pips
in table order, with normal-session spreads applied at all hours. Those are
not today's independently checked spread quotes, not metadata spreads, and
not actual 2023–2025 fills. New experiment costs must be explicitly frozen;
do not silently inherit the old report's lack of stops or swaps.

The board and prior 2023–2025 audit show these dates have already been used
for multiple BB studies. No portion is certified unused. EURJPY, GBPJPY and
USDCHF are not added by this audit; their prior Bars/tick concerns are not
resolved here. No live news or external market feed was substituted.

## Reproduction

Read-only PowerShell invocation from repository root (Python with numpy and
the local package importable). The full inspection exited 0 on 2026-09-25.

```powershell
@'
import json, hashlib
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
from forextester_backtest import HistoryRepository
root = Path('agent_runs/bb3_gmo_2023_2025')
repo = HistoryRepository()
epoch = datetime(1970, 1, 1)
for m in json.loads((root/'data_manifest.json').read_text()):
    s = m['symbol']
    z = np.load(root/f'{s}_features.npz')
    f, t = z['features'], z['times']
    assert set(z.files) == {'features', 'times'}
    assert f.shape == (m['bars'], 15) and t.shape == (m['bars'],)
    assert f.dtype == np.float64 and t.dtype == np.int64
    assert hashlib.sha256(t.tobytes()+f.tobytes()).hexdigest() == m['input_sha256']
    st = Path(m['raw_path']).stat()
    assert dict(size=st.st_size, mtime_ns=st.st_mtime_ns) == m['stat']
    assert np.all(np.diff(t)>0) and np.all(t%300==0)
    o = f[:,:4]
    assert np.all(np.isfinite(o)) and np.all(o>0)
    assert np.all(o[:,1]>=np.maximum(o[:,0],o[:,3]))
    assert np.all(o[:,2]<=np.minimum(o[:,0],o[:,3]))
    assert not np.isnan(f[20:]).any()
    assert (epoch+timedelta(seconds=int(t[0]))).isoformat() == m['first']
    assert (epoch+timedelta(seconds=int(t[-1]))).isoformat() == m['last']
    for i in (0, len(t)//2, len(t)-1):
        dt = epoch+timedelta(seconds=int(t[i]))
        b = list(repo.bars(s, dt, dt+timedelta(minutes=5)-timedelta(microseconds=1), '5m'))
        assert len(b)==1 and b[0].time==dt
        np.testing.assert_array_equal(o[i], (b[0].open,b[0].high,b[0].low,b[0].close))
    print(s, len(t), int((np.diff(t)>300).sum()), repo.metadata(s), repo.summary(s))
for p,h in json.loads((root/'code_hashes.json').read_text()).items():
    assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h
print('CACHE_AUDIT_OK')
'@ | python -
```

Next owner: research lead to freeze source-time handling, costs, signal replay,
and descriptive-only interpretation before using Jev judgments.
