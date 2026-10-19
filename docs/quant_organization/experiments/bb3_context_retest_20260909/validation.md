# Favorable entry limits: VERIFIED_REJECTED

Command: `python -m scripts.research_bb3_context_retest`

Observed final exit code **0** (execution chunk `cb4b38`, completed immediately).
Final output `RESULT_JSON` has `status=REJECTED`, `selected=null`.
`python -m pytest tests/test_bb3_context_retest.py -q`: **9 passed**.

Independent validator completed **VERIFIED_REJECTED**; see sibling `audit.md`
for the full independent replay, hash checks, boundary and prefix evidence.

Frozen protocol, source/input hashes, raw-file snapshot checks, cached feature
source manifest, per-case NPZ trade rows, `results.json`, and selection saved
BEFORE later-period runs are in `agent_runs/bb3_context_retest_20260909/`.

## Training result

All six new limit candidates had negative aggregate closed P/L in both cost
models. No candidate passed train selection; no alternative was evaluated on
validation/final years. Only unchanged baseline was evaluated later, exactly
reproducing the prior experiment. No fallback or parameter expansion occurred.

Training 2023-09-08 through 2024-09-07, 9-pair equal-pip research score:

| Candidate | Trades | PF fixed1.4 | Net fixed1.4 | PF metadata+.2 | Net metadata+.2 | Ambiguous entry bars |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 2,144 | 0.477 | -2,876.400 | 0.439 | -3,177.700 | 0 |
| limit025_ttl2 | 1,462 | 0.508 | -2,188.110 | 0.473 | -2,394.110 | 159 |
| limit025_ttl3 | 1,516 | 0.514 | -2,207.445 | 0.478 | -2,422.445 | 162 |
| limit050_ttl2 | 1,099 | 0.537 | -1,672.740 | 0.502 | -1,832.740 | 93 |
| limit050_ttl3 | 1,191 | 0.550 | -1,709.365 | 0.513 | -1,884.865 | 94 |
| limit100_ttl2 | 573 | 0.606 | -869.745 | 0.574 | -956.245 | 36 |
| limit100_ttl3 | 692 | 0.616 | -968.775 | 0.582 | -1,074.475 | 39 |

Open P/L at training end was zero for all cases, so losses are not hidden in
open positions. Highest-PF candidate had only 2/9 positive pairs in either cost
model, below predeclared 6/9. Mixed-symbol pips are NOT monetary portfolio profit.

## Interpretation and limits

Better entry prices increased PF but did not make net P/L positive. This does
not establish that every possible entry method fails; it rejects these six
predeclared alternatives. Successful immediate reversals can leave limits
unfilled, while adverse continuations fill. All filled losing trades were kept.
Samebar limit/target ambiguity uses target-before-entry convention except known
opening fills; it is not claimed to be a mathematical P/L lower bound. Limit
touches assume fills and ignore queue/liquidity, so tick/broker validation is
still necessary even if a future candidate passes.

No stop was added and no cost/accounting rule changed. Dynamic SMA20 still exits
at a loss when the average drifts against the trade. The final year was viewed
in past work, not a fresh holdout. No Pine modification or live order occurred.

## Independent handoff

`simulate_limit` takes `(features, times, start, end, pip, cost, fraction, ttl,
tick)` and returns the same nine-column trade matrix as the baseline. Its
diagnostics append ambiguous-entry bars, canceled orders, opening fills and
intrabar fills to the original ten fields. All entries/targets/cancellations
can be reconstructed from source cached features and candidate protocol.

Research result is rejection, not adoption approval. The user's requested
positive realized P/L objective remains unmet. The independent `audit.md`
confirms rejection. Local checks are not TradingView compilation/runtime checks.
