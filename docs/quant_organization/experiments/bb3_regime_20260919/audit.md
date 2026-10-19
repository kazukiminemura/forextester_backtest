# Independent audit: fixed BB regime additions

## Pre-result status

`VERIFIED_REJECTED_DESCRIPTIVE`. Auditor read the charter and owns only this
document. No researcher code, protocol, tests, source history or Pine edits.

Reviewed the frozen protocol before implementation/results were available:
SHA256 `03d146bf18e0e28ba478f4ef14220fb44b3047844a33dd1b684be0d1b66ebae0`.

The two reference shapes and six additions are fixed; no parameter search or
unseen-holdout claim is authorized. Period is continuous calendar 2023-2025 with
December 2022 warmup and exit-year summaries. Both costs, matching baselines,
all annual constraints and cross-pair conditions must be retained.

## Causality contract to verify

- H1 comprises exactly twelve aligned consecutive M5 opens in the same hour.
  Its ending time must not exceed the signal M5 close. Trend eligibility also
  requires age strictly below 3,600 seconds, so incomplete hours/weekend gaps
  cannot indefinitely reuse an old trend state.
- H1 rolling calculations use observed complete hours across gaps (no reset);
  this is an explicit modelling choice, not clock-hour interpolation.
- Slope uses the latest completed H1 SMA20 minus that SMA three completed H1
  observations earlier, divided by current completed H1 Wilder ATR14. Exact
  -0.25 BUY and +0.25 SELL thresholds reject. Warmup/nonpositive ATR reject.
- Volatility uses current M5 ATR14 over previous 100 ATR14 observations with
  the current observation excluded; TR/priorATR14 limit is inclusive 2.5.
  Ratio bounds 0.5 and 2.0 are inclusive. Volatility-only has no H1 dependency.
- Failure cancels the first eligible entry preparation without same-bar rearm
  or waiting. Existing shape, context, next-open and moving-center exits remain.

No material design blocker found. Cached M5 timestamps cannot prove that every
underlying M1 exists; the protocol correctly records that limitation. The
all-hours normal-session spread assumption remains optimistic, not actual GMO
historical executions.

## Completed independent evidence

- Read the full implementation, completed results and focused tests. The new
  regime decision is an additional cancellation condition inside the existing
  state machine; it is not a filter applied to already-completed old trades.
- Independently reconstructed aligned H1 OHLC, Wilder ATR14, SMA20 and its
  three-observation change, as well as M5 ATR, lag-100 mean and TR/priorATR.
  Across **1,611,265 M5 rows and 133,773 complete H1 rows**, raw OHLC/end-times
  match exactly and numeric indicator values match at 1e-10 tolerance or better.
  Independently calculated filter Boolean masks agree exactly in both directions
  and all three filtered modes on the entire seven-pair input.
- **49 real-data prefix checks** match exact full-series prefixes for both the
  M5 regime matrix and eligible H1 rows. Cuts include partial hours, first ATR
  readiness, hour boundaries and a gap boundary. Independent scalar cases also
  confirm exact trend/volatility thresholds and volatility-only H1 independence.
- Saved regime/hour arrays exactly match recomputation by the inspected source.
  The pre-result protocol hash above is unchanged. All recorded code and input
  hashes and seven current raw Bars.dat size/mtime values match their manifests.
- Recomputed **112 trade artifacts / 28,686 trade rows** directly from side,
  entry, exit, pip size and cost. All stored P/L values match exactly; counts,
  net-positive wins, PF, net P/L and all per-pair annual rows agree within 1e-9
  pips/floating-point tolerance. All **16 cost/variant aggregates**, their annual
  divisions and positive-pair counts agree. Cost cases have identical first
  eight execution columns, so cost changes do not alter the trade geometry.
- Every recorded filtered entry satisfies its respective signal-bar regime
  rule. Trend entries always have completed H1 end <= signal M5 close and age
  strictly below 3,600 seconds. Trading timestamps remain inside 2023-2025.
- Independently reproduced **28 baseline cases** with the prior shape simulator;
  all trade arrays and the first twelve diagnostics match exactly. Normal-cost
  baseline arrays also match the saved three-year report for both shapes.
- Independently recalculated all **132 gate flags** against the correct matching
  shape baseline, including both costs and every-year conditions. Eligibility
  is empty and the stored result is `REJECTED_DESCRIPTIVE`.
- `python -m pytest tests/test_bb3_regime.py -q`: **30 passed**, exit **0**.
  Tests cover aligned/complete hours, exact availability time, missing-hour
  staleness, Wilder initialization, gaps, excluded-current volatility mean,
  inclusive thresholds, future perturbation, prefix causality, direction
  symmetry, cancellation/no same-bar rearm/new setup and both-cost annual gates.

Commands ran read-only from repository root with `PYTHONPATH=src`. Independent
feature check completed exit **0**, chunk **87f080**, final marker
`VERIFIED_INDEPENDENT_REGIME_FEATURES 1611265 M5 133773 H1_49_PREFIXES_AND_ALL_FILTER_BOOLEAN_MASKS`.
Independent accounting/baseline/tests completed exit **0**, chunk **2311e2**,
final marker `VERIFIED_REGIME_ACCOUNTING 112 traces 28686 trade_rows 28 baselinecases 132 gateflags`.

## Verified descriptive results

| Entry shape / filter | Trades | Normal-cost win rate | Normal-cost PF | Net pips | +0.2-pip PF |
|---|---:|---:|---:|---:|---:|
| Current BB / none | 4,213 | 69.90% | 0.9824 | -224.300 | 0.9180 |
| Current BB / H1 trend | 2,958 | 69.44% | 1.0024 | +21.375 | 0.9365 |
| Current BB / volatility | 3,987 | 69.33% | 0.9432 | -701.300 | 0.8810 |
| Current BB / both | 2,803 | 68.78% | 0.9612 | -329.395 | 0.8974 |
| Engulf / none | 115 | 73.91% | 1.4624 | +101.830 | 1.3482 |
| Engulf / H1 trend | 79 | 74.68% | 1.2436 | +46.190 | 1.1570 |
| Engulf / volatility | 111 | 73.87% | 1.4852 | +102.210 | 1.3694 |
| Engulf / both | 77 | 75.32% | 1.2885 | +51.925 | 1.1987 |

## Findings and handoff

- **High, interpretation:** None of the six additions meets the frozen
  improvement gates. The 75.32% win rate for engulf plus both filters is based on
  77 trades, below the minimum 100, and its PF/total net are worse than unfiltered
  engulf. Volatility-only nudges PF upward but reduces win rate. Selecting a
  better-looking single statistic would be a post-result criterion change.
- **Medium, retained model limits:** Current normal-session spread assumptions
  apply to all historical hours; actual historical spread/slippage/session
  alignment and swap are not verified. Stop remains disabled, source timezone
  unknown, and periods previously viewed. Complete twelve-M5 H1 construction is
  verified but every constituent M1/tick is not authenticated.
- **Resolved implementation defect:** Initial compilation failed on assigning
  a mixed int/float tuple into the H1 float row. The auditor reported it; the
  researcher cast the end timestamp to float before the completed run. All
  later independent checks and tests pass. No threshold or strategy change
  was made to resolve this type error.

Hand off a **verified descriptive rejection**, not an adoption or Pine migration.
This bounded audit independently rebuilt new regime features and accounting,
verified baseline replay and inspected/tests-checked the new state transition.
It did not independently replay the entire filtered state machine over every
bar again, nor verify TradingView, a live broker or execution at stated costs.
No Pine or live-account change was made or approved.
