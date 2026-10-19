# Independent candle-shape audit

## Status and ownership

`VERIFIED_REJECTED_TRAINING_ONLY`. Auditor owns this document only; research
implementation, protocol, raw history and Pine are not edited by the auditor.
Charter read. This audit is not live-trading approval.

## Pre-result design review

Reviewed 2026-09-19 12:04 JST before the candidate implementation/results were
available. Frozen protocol SHA256:
`88fd7a0d4670660f12577662bf0303c978be3830df50e80ef47c332c0946a461`.

- Four fixed candidates plus the unchanged min3 baseline; eight non-quarantined
  pairs, 5-minute bars, independent flat-start periods, two fixed cost cases.
- Shape is tested on the first otherwise eligible signal bar, not the touch
  bar or future entry bar. Rejection cancels the preparation and blocks same-bar
  rearming. Full state replay is required, not filtering prior trade rows.
- Candidate 1: strict directional body and inclusive 0.65 directional close.
  Candidate 2 also requires inclusive 0.5 body/range. Candidate 3 requires a
  strictly opposite previous body and inclusive body enclosure. Candidate 4
  requires a strict directional body and strict previous high/low recovery.
  All filtered candidates reject doji and zero-range bars and mirror BUY/SELL.
- Selection uses only training. Both costs must satisfy the complete win-rate,
  profitability, frequency and 5-of-8-pair gates; maximum one selected candidate.
  Validation failure stops before final, without fallback or threshold changes.
- Previously viewed periods, fixed illustrative costs, omitted swap, no stop,
  unknown source timezone and Bars/ticks quality limits are explicitly retained.

No material design blocker identified. The completed checks below confirm that
all four candidates fail the frozen training gates; no improvement is adopted.

Implementation review before outcomes found no mismatch in the added transition
or filter definitions. A separately written Boolean reference checked **119,990**
shape decisions across both directions and all five modes, plus exact 0.65/0.5
and engulf equality/adjacent-float boundary cases; command exit **0**.

## Completed independent verification

- Read the complete implementation and tests. Shape decisions use only the
  current confirmed candidate and previous bar. The full state machine is
  replayed for each candidate; a rejected old trade does not freeze occupancy
  or prevent a later new setup. No post-hoc filtering of baseline trade rows.
- A separately written Python dictionary-state replay matched **80 artifacts
  and 4,112 trade rows** exactly in all nine trade columns. All twelve diagnostic
  fields matched with absolute tolerance 1e-10, including preparation/signal
  counts, both rejection counts, open mark, next target and bar-close MTM DD.
  Both costs are included; the 4,112 rows are not independent observations.
- Recomputed trade P/L directly from side, entry and exit, then net-positive
  wins, counts, win rates, PF, closed P/L, holding-time means/maxima. Matched all
  per-pair rows, **10 aggregates and all 40 gate flags**. Zero gross loss uses
  undefined PF (`null`), not division by zero or a numeric profitability claim.
- Independently reran all **16 baseline cases** against `simulate_center(...,
  3.0)`: all trade arrays and eleven baseline diagnostics exactly matched.
- Protocol hash remained the pre-result hash above. All recorded code hashes,
  eight saved feature/timestamp hashes and current raw-file size/mtime matched
  their manifests. Raw-source stat equality is not whole-file hash authentication.
- Only training results exist: five cases x eight pairs x two costs. Eligibility
  is empty, `selected` is null, and neither validation nor final-confirmation
  candidate results were generated. Source control flow also stops when no
  training candidate is eligible.
- Independently ran `python -m pytest tests/test_bb3_candle_shapes.py -q`:
  **27 passed**, exit **0**. Covers doji/zero range, inclusive versus strict
  boundaries, short mirror, cancel/no rearm/no wait, a later new setup, gap
  entry/same-bar exit, cost-independent geometry, feature/execution prefix
  causality, both-cost gates and exclusion of open positions from win counts.

Read-only verification commands ran from the repository root with PYTHONPATH=src.
The full independent state/accounting replay completed in session **20776**, exit
**0**, printing `VERIFIED_INDEPENDENT_STATE_REPLAY 80 artifacts 4112 trade_rows`.
The baseline/test command completed in chunk **df0b24**, exit **0**. The first
audit replay attempt stopped after 48 cases because its own PF calculation did
not handle a zero-loss denominator. Only the audit reference was corrected;
the complete 80-case rerun passed without changing researcher code or results.

## Verified results and findings

Training: 2023-09-08 inclusive to 2024-09-08 exclusive. Net win rates include
fixed round-trip costs. No stop and no forced end exit; this is not fixed RR.

| Case | Trades | Win rate, 1.4 pips | PF, 1.4 pips | Net pips, 1.4 | PF, 2.0 pips |
|---|---:|---:|---:|---:|---:|
| Baseline | 1,468 | 66.08% | 0.7523 | -1,045.645 | 0.5756 |
| Directional close65 | 310 | 66.13% | 0.6485 | -327.195 | 0.4859 |
| Body50 + close65 | 173 | 68.21% | 0.5989 | -203.990 | 0.4347 |
| Body engulf | 33 | 72.73% | 1.1485 | +7.405 | 0.7789 |
| Previous-range reclaim | 72 | 70.83% | 1.0291 | +3.965 | 0.7371 |

- **High, interpretation/adoption:** Engulf and range reclaim show higher sample
  win rates, but only 33/72 trades and negative net at the 2.0-pip cost. All four
  fail the frozen count-retention requirement (at least 30% of 1,468 = 440.4,
  hence at least 441 trades) and the stressed-cost profitability gate. Reporting
  72.73% as a verified improved strategy would overstate the evidence.
- **Medium, retained modelling limitations:** No stop, omitted swap/variable
  spreads, unknown source timezone and previously viewed partitions remain.
  A retained trade can last 49 hours, so omitted overnight cost is relevant.
  Eight non-quarantined pairs do not mean all raw ticks have been authenticated.
- **Low, test provenance:** The unrelated historical center5 test still expects
  a Pine default of 5 instead of the user's current 3. This audit did not edit
  or reinterpret that stale contract. The focused 27 tests were run without
  deselection; a blanket full-repository green claim is not made.

No implementation discrepancy found in the independently checked scope. The
correct outcome is rejection of these four fixed additions under these gates,
not proof that no candle-shape method can ever work.

## Handoff

Hand off the **training-only rejection report** to the research director. Do not
adopt or move these four candidates to Pine based on these results. Pine is
unchanged and TradingView runtime is outside this study. The audit used saved
source features and prior feature-function evidence; it did not independently
rebuild every feature from raw M1/ticks, authenticate the entire feed, evaluate
later candidate periods, or verify live broker execution. Research rejection,
Pine output, TradingView verification and live approval remain distinct states.
