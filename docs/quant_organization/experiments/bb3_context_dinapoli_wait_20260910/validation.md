# Bounded DMA recovery waiting: no verified improvement

## Outcome

Both frozen waiting variants failed first-segment improvement gates. Neither
was selected; no waiting variant accessed later evaluation periods. Current
Pine is unchanged. No extra candidates or post-result tuning were performed.

Segment1 is 2023-09-08 inclusive to 2024-09-08 exclusive, nine pairs on 5m,
minimum center distance3 pips, no stop and full moving-center exit.

| Case | Trades | Win fixed1.4 | PF fixed1.4 | Mean net pips | Net fixed1.4 pips | Win metadata+.2 | PF metadata+.2 | Net metadata+.2 pips |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 1,146 | 61.52% | 0.576 | -1.566 | -1,794.250 | 60.30% | 0.543 | -1,968.850 |
| Wait up to3 bars | 173 | 57.80% | 0.411 | -2.264 | -391.745 | 55.49% | 0.382 | -419.245 |
| Wait up to6 bars | 301 | 57.48% | 0.493 | -1.593 | -479.425 | 56.15% | 0.458 | -523.025 |

Open net P/L is zero in every first-segment case; no forced close is inserted
into PF. These pooled pips are equal-pip research scores across differing
quote currencies, **not account-currency monetary profit**.

Both waiting cases reduced aggregate win rate, PF and average net at both
cost levels. Wait3 retained15.10% of baseline trades, below25%; wait6 retained
26.27% and passed the frequency gate, but failed quality gates. Pair win rates
improved in only4/9 and3/9 respectively, below6/9. Smaller total loss is not
evidence of improved expectancy when the number of trades falls.

## Waiting-state diagnostic, not a new search

| First-segment diagnostic | Wait3 | Wait6 |
|---|---:|---:|
| Waiting starts | 1,144 | 1,143 |
| Delayed signals | 159 | 287 |
| Canceled waits | 985 | 856 |
| Distance below3 | 495 | 541 |
| Deadline exceeded | 370 | 118 |
| Explained move | 144 | 165 |
| Relevant wick | 49 | 50 |
| Center passed | 71 | 72 |
| Opposite touch | 5 | 5 |
| Gap | 1 | 1 |

Cancellation reason counts can overlap; do not sum them as distinct states.
The additional14 trades in each case signaled immediately at the original
candidate and never entered waiting. Extending the wait increased delayed
entries but did not improve win rate or expectancy. Distance loss is a common
observed cancellation; it does not establish that removing the minimum-distance
constraint would work. That different rule was not tested.

Largest individual-pair realized/close-MTM drawdowns, respectively, were
baseline442.40/478.80, wait3 161.105/172.555, wait6 177.815/191.04 pips at
fixed1.4. These are not portfolio drawdowns and are not frequency-normalized.
All pair/period/cost statistics and terminal waiting states are in
`agent_runs/bb3_context_dinapoli_wait_20260910/results.json`.

## Baseline reference and data constraints

Only the unchanged baseline accessed later segments: fixed1.4 PF/net were
segment2 0.879/-821.485 pips, segment3_partial0.774/-1,247.140, and continuous
0.767/-3,862.875. Metadata continuous PF0.717/net-4,769.275 pips. All baseline
terminal open P/L values were zero. No conclusion about waiting variants in
those later periods is available.

All nine pairs share exclusive cutoff2026-08-31, before the known original
GBPJPY price-scale anomaly. Source history was not repaired or changed.
Raw-file stats and cache hashes were checked, and arrays were prefix-truncated
before DMA generation. All periods have prior exposure and are not untouched
holdouts. Fixed and metadata costs omit variable spread, swaps, liquidity,
margin and live execution uncertainty. No SL can expose large open losses.

## Execution and independent handoff

- Command: `python -m scripts.research_bb3_context_dinapoli_wait`.
- Execution chunk `cae67e`, exit **0**, final `RESULT_JSON` status
  `NO_VERIFIED_IMPROVEMENT`, `selected=null`, profitability requirement false.
- 108 saved case artifacts and72 exact baseline reproductions.
- New17 behavior tests passed; combined new, prior DMA and current Pine tests
  **83 passed**. Static checks do not verify TradingView runtime.
- Input/source/protocol hashes, safe-prefix hashes, pre-later selection,
  trade matrices and24 diagnostics are retained in the artifact directory.
- Independent audit **VERIFIED_REJECTED**, recorded in sibling `audit.md`:
  session `61955`, chunk `103eac`, exit **0**. All108 artifacts,19,868 trade
  rows and24 diagnostics matched the independent state replay;108 prefix
  checks and72 baseline comparisons matched. Input hashes and null selection
  were also reproduced;83 tests passed independently.

API `simulate_wait(f,times,dma,start,end,pip,cost,wait_bars)` returns original
9-column trades and24 diagnostics. The first11 match the verified center
simulator; remaining names are `WAIT_DIAGNOSTICS`. Final origin remains the
last origin, active only when final waiting direction is nonzero. DMA and
improvement checks reuse the hashed prior DMA module; source dependencies
are included in the input hash manifest.

No Pine edit, source mutation, publication, order or adoption approval occurred.
