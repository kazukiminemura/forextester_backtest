# Structure-based stop: VERIFIED_REJECTED_TRAINING_ONLY

## Execution and scope

- Command: `python -m scripts.research_bb3_context_structure_stop`
- Observed exit code **0**, chunk `4c65d5` (completed, no live session).
- Final `RESULT_JSON`: `status=REJECTED`, `selected=null`.
- `python -m pytest tests/test_bb3_context_structure_stop.py -q`: **16 passed**.
- Six cases, nine pairs, two cost models = **108** training artifacts.
- All **36** fixed-10-pip control artifacts exactly reproduced the previous
  exits experiment's trade matrices and diagnostics (`assert_array_equal`).
- Results, code/input hashes, manifest checks, data-quality report and selection
  are under `agent_runs/bb3_context_structure_stop_20260909/`.
- Independent reviewer completed **VERIFIED_REJECTED_TRAINING_ONLY**, session
  `48289`, exit **0**. See sibling `audit.md`: 108 artifacts / 15,112 trade rows,
  including 10,122 structural-stop rows independently replayed bar by bar;
  all 24 diagnostics, 36 controls and 72 prefix checks matched. The 66
  breached-fill cost losses and 4,204 invalid-known-order cases remained
  accounted for. Counts include duplicate cost models, not independent samples.

Training only: **2023-09-08 inclusive through 2024-09-08 exclusive**. There was
NO validation, final-year, or continuous-period evaluation in this experiment.

Before results, the independent reviewer found a source-price scale anomaly in
GBPJPY on **2026-08-31**: prices near 2.16 amid surrounding prices near 216,
consistent with a suspected 1/100 scale error. It exists in original Bars.dat,
not merely the cache. It is outside this training window. The director amended
the protocol before outcomes to stop all later-period evaluation, including
controls. No bars were deleted, normalized or rewritten. New adoption would
need separately authorized data resolution; none qualified even on training.
See sibling `audit.md` for original-source evidence and independent checks.

## Predeclared six-case result

All four new structural-stop candidates failed positive training P/L in both
cost models. Both fixed-10-pip comparators were also negative. No candidate was
selected, no condition was retuned and no additional exploration was run.

The table pools **equal-pip research scores**, not account-currency money.
TP is fixed gross RR1.3 in every row. Structural buffers are frozen fractions
of signal-time prior ATR beyond the full preparation-to-signal extreme.

| Entry / stop | Trades | PF fixed1.4 | Net fixed1.4 pips | PF metadata+.2 | Net metadata+.2 pips | Win rate fixed1.4 | Mean normal risk pips |
|---|---:|---:|---:|---:|---:|---:|---:|
| Market / fixed10 | 1,823 | 0.779 | -2,617.80 | 0.760 | -2,879.10 | 43.34% | 10.00 |
| Limit / fixed10 | 672 | 0.763 | -1,041.40 | 0.743 | -1,144.00 | 42.86% | 10.00 |
| Market / structure +0.10ATR | 2,142 | 0.562 | -2,806.10 | 0.529 | -3,105.10 | 38.33% | 3.92 |
| Market / structure +0.25ATR | 2,111 | 0.590 | -2,847.70 | 0.559 | -3,142.80 | 40.17% | 4.43 |
| Limit / structure +0.10ATR | 374 | 0.512 | -416.10 | 0.468 | -476.40 | 29.41% | 2.53 |
| Limit / structure +0.25ATR | 434 | 0.521 | -492.00 | 0.479 | -559.40 | 29.72% | 2.69 |

Mean risk includes only normally established, closed brackets. Nonpositive-risk
gap fills are excluded from that mean, but their full costs and counts remain
in ALL closed P/L, win rate and PF calculations. Training-end open P/L was zero
for every case. The highest-PF new structural rule still has 0/9 profitable
pairs; the two structural-limit rules have only 1/9, below the 6/9 gate.

## Drawdown and gap diagnostics

These are the **largest individual-pair** drawdowns within each case, not an
account-currency or combined-portfolio drawdown. All values use fixed1.4 costs.

| Entry / stop | Largest pair close-MTM DD pips | Largest pair realized DD pips | Known invalid limits omitted before order | Gap-breached fills charged |
|---|---:|---:|---:|---:|
| Market / fixed10 | 632.50 | 624.10 | 0 | 0 |
| Limit / fixed10 | 315.60 | 301.70 | 0 | 0 |
| Market / structure +0.10ATR | 559.00 | 558.40 | 0 | 14 |
| Market / structure +0.25ATR | 644.20 | 634.50 | 0 | 11 |
| Limit / structure +0.10ATR | 88.80 | 83.40 | 1,149 | 3 |
| Limit / structure +0.25ATR | 96.10 | 93.10 | 953 | 5 |

Fewer trades reduce absolute aggregate losses/DD in some cases; this does not
establish better expectancy. Structural stops are substantially narrower than
the 10-pip controls here, increasing costs relative to risk and increasing
stop-outs. Limit orders frequently lie beyond the known structural stop and
are correctly not submitted. Adverse gaps of otherwise valid orders are not
erased: entry and immediate stop exit both use open and debit one full cost.
Actual broker execution can be worse than this deterministic convention.

## Reproduction and handoff

`simulate_structure_stop(features,times,start,end,pip,cost,tick,limit_entry,
buffer)` returns the previous exits experiment's 15-column trade matrix and
24 diagnostics: previous 20 plus invalid-known-limit count, breached-fill exit
count, frozen structural stop and preparation-interval extreme. For breached
fills the RR/target fields are NaN and risk can be nonpositive; this is explicit
evidence, not a missing normal target. The average normal-risk statistic filters
those cases while PF never filters their losses.

Signal-time ATR and extreme boundaries are fixed; no post-signal low/high can
widen SL. Absolute TP is rounded outward from actual entry-to-stop risk so
off-grid fills cannot reduce gross RR1.3. Training OHLC grid checks passed for
all nine symbols. Controls use the original implementation exactly. Only future
data repair, not a rounding workaround, could resolve the later GBPJPY anomaly.

No Pine/source-history/board edits, commit/push or live order was performed by
this research task. The positive-realized-profit objective remains unmet. The
researcher does not approve adoption; independent audit confirms training-only
rejection. Python tests are not TradingView runtime verification.
