# DMA velocity-change filters: no verified win-rate improvement

## Outcome

Both alternatives failed the frozen first-segment win-rate improvement gates.
PF and average net improved but remained negative expectancy, while win rate
decreased in both cost cases. No candidate was selected, no alternative was
evaluated in later periods, and existing Pine was not changed.

Segment1:2023-09-08 inclusive to2024-09-08 exclusive, nine pairs,5m, current
min3pips baseline, no stop and full moving SMA20 exit.

| Case | Trades | Win fixed1.4 | PF fixed1.4 | Mean net pips | Net fixed1.4 pips | Win metadata+.2 | PF metadata+.2 | Net metadata+.2 pips |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 1,146 | 61.52% | 0.576 | -1.566 | -1,794.250 | 60.30% | 0.543 | -1,968.850 |
| Favorable acceleration | 420 | 60.95% | 0.667 | -1.079 | -453.335 | 60.24% | 0.626 | -517.535 |
| Favorable/nonadverse velocity OR favorable acceleration | 505 | 60.79% | 0.612 | -1.331 | -672.135 | 60.20% | 0.575 | -748.335 |

Every first-segment terminal open net is zero. No forced liquidation is added
to PF. Pooled pips are equal-pip research scores across quote currencies,
**not account-currency monetary profit**. Both candidates retain more than25%
of baseline trades and exceed30, so the failure is not just sparse sampling.
Favorable acceleration improved pair win rates in5/9 pairs at both costs;
the second filter in4/9 fixed and3/9 metadata, below the required6/9.

Largest single-pair realized/close-MTM drawdown at fixed1.4, respectively:
baseline442.40/478.80, acceleration203.38/212.925, second194.625/204.17 pips.
These are not monetary portfolio drawdowns. All individual pair/period/cost
results, diagnostic counts, open P/L and drawdowns are preserved in
`agent_runs/bb3_context_dinapoli_deceleration_20260910/results.json`.

## Exact rule and numerical limits

The first filter computes `v=D[i]-D[i-1]`, `pv=D[i-1]-D[i-2]`, then
`side*(v-pv)>0`. It includes favorable acceleration as well as weakening
adverse velocity, not exclusively adverse deceleration. The second accepts
`side*v>=0 OR side*(v-pv)>0`. Both require all three DMA values finite.
There is no extra delay, price-side gate, epsilon or post-result retuning.
Failure at the first otherwise-eligible candidate cancels preparation and
prevents samebar rearming. DMA remains causal SMA(close,3)[3]. This added
acceleration filter is a research hypothesis, not claimed as an original
DiNapoli rule.

Near-zero floating-point acceleration is sensitive to price representation
and arithmetic order. The difference-of-differences order was fixed before
outcomes, and no epsilon was fitted. The auditor separately identified31
baseline signal samples whose tick-exact acceleration is zero: the float
formula produced6 tiny positive,9 tiny negative and16 exact zeros. This is
a numerical-portability limitation, not authority to change the frozen rule.
No Pine runtime equivalence is claimed.

## Data and baseline reference

All nine inputs use the common exclusive2026-08-31 cutoff, before the known
GBPJPY source-scale anomaly. Raw history stats/cache hashes were checked;
safe prefixes were cut before DMA construction. Source prices were not
corrected, and all periods were previously viewed, not untouched holdouts.
The costs omit variable spread, swaps, margin and execution liquidity.
No stop-loss leaves potentially large open-loss risk.

Only baseline ran later: fixed1.4 segment2 PF0.879/net-821.485 pips,
segment3_partial PF0.774/net-1,247.140, continuous PF0.767/net-3,862.875.
Metadata continuous PF0.717/net-4,769.275. Baseline terminal open P/L is zero
throughout. No later-period evidence for either acceleration filter exists.

## Execution and handoff

- `python -m scripts.research_bb3_context_dinapoli_deceleration`: chunk
  `1acae7`, exit **0**, final `RESULT_JSON=NO_VERIFIED_IMPROVEMENT`, selected
  null, separate profitability requirement false.
- 108 case artifacts and72 exact baseline comparisons; all source/input
  hashes, pre-later selection, trade matrices and12 diagnostics saved.
- New15 tests passed; new+prior DMA+current Pine **81 tests passed**.
- Independent audit **VERIFIED_REJECTED**, recorded in sibling `audit.md`:
  session `15737`, chunk `64fd32`, exit **0**. All108 artifacts,20,770 trade
  rows and12 diagnostics independently matched, as did108 prefix checks,
  72 baseline comparisons and null selection. Near-zero diagnostic also
  reproduced. Including waiting-state tests, the independent suite passed
  **98 tests**.

API `acceleration_allows(dma,i,side,mode)` isolates the filter;
`simulate_dma(f,times,dma,start,end,pip,cost,dma_mode)` retains the prior
9 trade columns and12 diagnostics. Causal DMA and unchanged selection gates
reuse the hashed prior module. Independent reviewer owns only `audit.md`.
No prior research, Pine, raw history, unrelated daily-study file or board was
modified. No publication, real order, approval or additional search occurred.
