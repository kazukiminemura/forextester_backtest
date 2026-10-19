# BB trade opportunity diagnosis, 2020-2025

Status: DIAGNOSIS_REPLAY_MATCHED; independent review pending. No new trading strategy was tested or adopted.

Seven frozen M5 caches match their inherited SHA256 identifiers. Every emitted candidate dictionary matches both the current research engine and the saved original candidate list. Replayed trade dictionaries match all 1,225 existing continuous-six-year trades exactly. This establishes the diagnosis against the stored Python baseline; it does not establish that a user's live TradingView chart uses these exact defaults or matches its feed.

## Where opportunities disappear

Counts are totals across USDJPY, EURUSD, GBPUSD, AUDUSD, NZDUSD, AUDJPY, NZDJPY, from 2020-01-01 through 2025-12-31. Warmup uses December 2019. Each row describes a state transition/event, not an independent market opportunity.

|Stage|Count|Interpretation|
|---|---:|---|
|M5 bars|3,139,023|Reporting period, excludes warmup|
|At least one 3-sigma wick touch|105,845|3.37% of bars; touches themselves are not extremely scarce|
|Touch while a setup is already active|6,200|Not a new setup|
|Idle touch examined for preparation|99,645|Starting denominator for context exclusions|
|Initial impulse exclusion|70,996|71.25% of idle touches|
|Initial long-wick exclusion|9,981|10.02%; counted only after impulse exclusion|
|Initial both-band exclusion|486|0.49%; first-priority initial exclusion|
|Preparation accepted|18,182|18.25% of idle touches|
|Later directional inside-band candle confirmed|10,269|56.48% of preparations|
|Later strict breakout reached|7,610|74.11% of confirmations|
|Breakout rejected for less than 3pip to prior center|5,952|78.21% of breakouts|
|Candidate reported at breakout close|1,658|21.79% of breakouts|
|Candidate ignored during existing holding|1|One position per pair|
|Next-open time-gap rejection|2|Requires contiguous M5 bar|
|Next-open target-room rejection|430|Signal-close center to actual next-open price must still be at least 3pip|
|Filled and closed|1,225|All filled positions closed by the end|

Preparation cancellations total 10,572: extreme update 9,167; opposite-band touch 815; long wick 200; impulse 137; missing-time gap 133; expiry 120. Of these, 7,913 occurred before confirmation and 2,659 afterwards. Expiry is only 1.14% of cancellations, so merely increasing the 12-bar expiry has little direct headroom.

Cancellation classifications are mutually exclusive and follow Pine's priority: readiness, gap, extreme update, impulse, wick, opposite touch, expiry. A bar may satisfy several conditions but only the first reason is counted. The initial rejection priority is both-band, impulse, wick. Thus the initial and active-setup impulse counts are not a causal estimate of the trades recovered by removing that filter. The prior-center breakout room and signal-center next-open room are different checks; no reference price is treated as an actual fill.

## Frequency and cost erosion

|Pair|Closed trades in 6 years|Average per month|
|---|---:|---:|
|USDJPY|205|2.85|
|EURUSD|127|1.76|
|GBPUSD|200|2.78|
|AUDUSD|144|2.00|
|NZDUSD|119|1.65|
|AUDJPY|233|3.24|
|NZDJPY|197|2.74|
|Seven-pair total|1,225|17.01|

Mean per pair per month is 2.43. This is an unconditional historical average, not a promise of evenly distributed opportunities.

With symmetric RR1 and hypothetical 1pip round-trip cost:

- Win rate: 50.20%.
- Gross profit: +344.80 pip-score / +14.9185 R; net: -880.20 pip-score / -212.2775 R.
- Gross PF_R: 1.0244; net PF_R: 0.7080. PF in pips differs: 1.0863 before costs and 0.8088 after costs.
- Mean gross movement per trade: +0.2815 pip, less than the assumed 1pip cost; mean net movement: -0.7185 pip.
- Median initial SL and TP width: 5.5 pips; interquartile range 4.2-7.8 pips. 499/1,225 trades have risk below 5pip; 1,061 have risk below 10pip, using 1e-9 pip tolerance at the boundary. First-run raw float comparisons counted 510/1,064; revision 2 corrects only these descriptive buckets and preserves the initial artifact.
- Mean cost divided by initial risk: 18.55%, totaling 227.1960 R of cost. Under symmetric ordinary full exits, the mean corresponding break-even win probability is 59.27%; actual gap exits can differ.

The current sample has only a small gross R surplus. Increasing count alone does not resolve the cost deficit. Equal-pip and equal-initial-R totals are research scores, not deposit-currency earnings. Costs here are the inherited hypothetical 1pip, not historical GMO bid/ask execution. All seven pairs lose in net R.

## At most three next hypotheses (not tested)

Each proposal changes one component, preserves both directions, full RR1, next-contiguous-open fills, one position per pair, fixed target/stop and existing conservative intrabar accounting. They are proposed experiment designs, not performance claims. Any follow-up must freeze its exact specification, finite comparison count, cost model and gates before running. Existing 2020-2025 data are already viewed; later comparisons on those dates remain descriptive.

1. **Measure the impulse filter's marginal value.** M5, no higher-timeframe filter. Compare the current baseline with only high/low-and-round-number impulse exclusions disabled; retain wick exclusion, touch-extreme cancellation, directional close confirmation, later breakout and both room checks. Hypothesis: the current impulse proxy classifies ordinary three-sigma excursions as explained moves, discarding many potential reversals. It fails if the recovered cohort continues trending and has inferior cost-adjusted returns or drawdown. Exclusion count alone does not predict this result.
2. **Enter after the directional inside-band close without the extra breakout wait.** M5, no higher timeframe. Retain all initial/context and extreme-update rules; after a qualifying reversal candle closes, queue a next-open candidate with that candle's center as fixed target, require at least 3pip actual room and mirror the stop for RR1. The former breakout/prior-center check disappears with the breakout stage. Hypothesis: one less confirmation stage preserves return-to-center distance and reduces cost as a fraction of target width. It fails if earlier reversal attempts suffer enough renewed movement to offset the extra room.
3. **Move the unchanged state-machine specification to M15.** No higher-timeframe filter; rebuild M15 OHLC and features causally from the saved/source history with alignment and gap checks. Keep BB20/3sigma, expiry12 bars, context lengths and room thresholds in their stated units, later confirmation/breakout, next-M15-open fill, fixed center target and RR1. Hypothesis: larger typical price distances reduce fixed-pip cost burden. It fails if frequency becomes unusably low, average gross expectancy deteriorates or larger holding costs remove the benefit. M15 is not assumed to increase count; assess it on net expectancy and usable frequency jointly.

The three proposals must be compared with the same baseline; no cascading combination or search-until-passing is authorized by this diagnosis. Any financial-cost setting needs its own frozen sensitivity check. The current diagnosis gives no basis to adopt one of them.

## Reproduction and handoff

Commands from repository root:

```text
python -m pytest tests/test_bb_opportunity_diagnosis.py -q
python scripts/diagnose_bb_opportunities.py
```

The original runner exited 0; the original five behavior tests passed. The runner refuses to overwrite an existing completed results file. It verifies cache identities, emits an artifact once, and performs no external API call or raw-data write. Independent review can invoke `diagnose()` and `trade_stats()` directly without re-running artifact creation. Final artifact: `agent_runs/bb_reconsider_20261001/results.v2.json`; the initial `results.json` remains preserved. Revision 2 only recalculates risk buckets from the saved trades; it does not rerun candidate generation or fills. It records the initial artifact hash, both code hashes, and the 1e-9 pip tolerance. A sixth boundary-behavior test covers floating-point noise around exactly 5 and 10 pips. Source identity, candidate/trade hashes and protocol hash remain included. Raw Bars.dat hashes are inherited labels; this diagnostic run did not rehash or re-download raw history.

Verification scope: prefix behavior, cancellation precedence, gap priority, first-break room rejection, cost decomposition, full existing candidate/trade equality. Next owner: independent validator for all counters/cost formulas; quality auditor for source identity and claim scope.
