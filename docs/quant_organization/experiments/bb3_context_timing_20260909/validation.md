# BB entry timing study: VERIFIED_REJECTED

## Execution evidence

- Command: `python -m scripts.research_bb3_context_timing --output agent_runs/bb3_context_timing_20260909/completed`
- Unified execution session: `52497`, observed final exit code **0**.
- Final output: `RESULT_JSON={"status":"REJECTED","selected":null,...}`.
- Artifacts: `agent_runs/bb3_context_timing_20260909/completed/` contains frozen
  protocol, code hashes, 9 source manifests/features, training selection record,
  per-case trade NPZ files, `results.json`, and training-only cost diagnostics.
- `python -m pytest tests/test_bb3_context_timing.py -q`: **11 passed**.
- Independent validator reported **VERIFIED_REJECTED**: 270 artifacts / 47,196
  trade rows, 20,000 synthetic feature bars, 48 configurations, 269 synthetic
  trades and 144 prefix checks. See sibling `audit.md` for independent evidence.
- Initial direct-script command failed before any outcomes because a Numba
  cached import was unavailable under that invocation. The failure and `-m`
  recovery are preserved in `initial_attempt_failure.json`. Earlier Numba
  boolean/tuple typing fixes did not change the strategy. No results existed
  when these implementation compatibility issues were repaired.

## Predeclared selection result

All 12 candidates (baseline plus 11 timing alternatives) had negative aggregate
training net P/L in both predeclared cost models. No candidate was selected.
Unselected alternatives were NOT run on validation/final/continuous periods.
Only the unchanged baseline received those descriptive evaluations.

Fixed 1.4-pip training examples, 2023-09-08 through 2024-09-07:

| Candidate | Trades | PF | Net pips |
|---|---:|---:|---:|
| baseline | 2,144 | 0.477 | -2,876.400 |
| reversal | 1,612 | 0.402 | -2,337.300 |
| previous_break | 820 | 0.272 | -1,439.740 |
| reversal_distance3 (highest PF, still rejected) | 475 | 0.549 | -961.635 |

Mixed-symbol totals are **equal-pip research scores, not account-currency
profits**. All nine symbols use the same rule; no profitable-symbol selection.

## Baseline continuous 3-year comparison

The period is 2023-09-08 inclusive through 2026-09-08 exclusive. All nine source
series cover the requested endpoints. Stored history timezone is not certified
as UTC. The final year was previously viewed in prior work, not untouched data.

| Cost model | Trades | PF | Closed net pips | Open net pips | Closed + open |
|---|---:|---:|---:|---:|---:|
| fixed 1.4 | 7,761 | 0.641 | -7,488.7752 | -6.1000 | -7,494.8752 |
| metadata spread + 0.2 | 7,761 | 0.589 | -8,842.8752 | -6.4000 | -8,849.2752 |

Open positions are marked to the last close with one full modeled cost, shown
separately and never silently included in PF. Closed plus open is the separate
terminal mark-to-close liquidation estimate, not an actual added exit trade.

Per-pair baseline continuous results, metadata-cost model:

| Pair | Trades | PF | Closed net pips |
|---|---:|---:|---:|
| USDJPY | 843 | 0.772 | -628.9650 |
| EURUSD | 860 | 0.493 | -991.7700 |
| GBPUSD | 944 | 0.525 | -1,176.0400 |
| AUDUSD | 890 | 0.502 | -788.7450 |
| NZDUSD | 876 | 0.339 | -1,144.5250 |
| USDCHF | 720 | 0.348 | -1,036.4600 |
| USDCAD | 869 | 0.383 | -1,450.3800 |
| EURJPY | 912 | 0.827 | -547.4050 |
| GBPJPY | 847 | 0.723 | -1,078.5852 |

## Training-only diagnostic, not additional candidate selection

For fixed 1.4-pip costs, baseline gross average was +0.0584 pips but net average
was -1.3416. Among 1,584 positive-gross trades, 568 (35.86%) became nonpositive
after costs. Reversal confirmation had gross -0.0499 / net -1.4499 pips and
41.52% gross-win cost flips; previous-high/low confirmation had gross -0.3558 /
net -1.7558 and 54.19% flips. This is consistent with delayed market entries
consuming reversion room, but gross losses show costs are not the only problem.
The distance-3 candidate reduced cost flips to 6.39% but gross average remained
-0.6245 pips: more room does not by itself remove persistent-trend losses.
These are training diagnostics only; no new candidate was evaluated here.

## Handoff

The independent validator can import `features`, `simulate`, `timing_allowed`,
and `TRADE_COLUMNS`. Inputs are cached `SYMBOL_features.npz` with `times` and
`features`; per-case NPZ stores `trades` and `diagnostic`. `results.json.rows`
links each NPZ to its candidate, period, symbol, modeled cost, and summary.
`selection_before_validation.json` proves no fallback candidate was selected.

No Pine change, commit, push, or real order was made by this research task.
No adopted profitable entry adjustment exists from this experiment. User goal
remains unmet; research rejection is not a claim of goal completion.
Python behavior checks are not TradingView compile/runtime verification.
