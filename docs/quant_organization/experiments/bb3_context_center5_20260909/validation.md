# Current 5-pip center-distance filter: descriptive profitability check

## Outcome

The current **minCenterPips=5** condition improved the continuous-window PF
relative to min0, but it did **not** produce positive closed P/L. All nine pairs
had negative continuous-window net P/L under both declared cost models. This is
a fixed-setting verification, not strategy optimization or adoption approval.

Common period: **2023-09-08 inclusive through 2026-08-31 exclusive**. No price
from the GBPJPY anomaly day 2026-08-31 or any later date participates. The entire
prefix cutoff is applied to every symbol before simulation. Source data was
not modified, scaled or selectively cleaned; the underlying anomaly remains.

All combined pips below are **equal-pip research scores, not account-currency
monetary profit**. One fixed-unit virtual position per pair; no stop; full exit
at the evolving previously confirmed SMA20; costs deducted once per exit.

| Condition / round-trip cost | Trades | Win rate | PF | Closed net pips | Open net pips | Closed + open |
|---|---:|---:|---:|---:|---:|---:|
| min0 / fixed1.4 | 7,710 | 53.26% | 0.645 | -7,338.870 | -3.300 | -7,342.170 |
| min5 / fixed1.4 | 2,997 | 65.17% | 0.826 | -2,253.755 | 0.000 | -2,253.755 |
| min0 / metadata spread+.2 | 7,710 | 50.80% | 0.592 | -8,682.770 | -3.600 | -8,686.370 |
| min5 / metadata spread+.2 | 2,997 | 64.43% | 0.782 | -2,865.655 | 0.000 | -2,865.655 |

The filtered condition generated fewer trades and higher win rate; neither is
proof of profitability. Average net was -0.752 pips per trade at fixed1.4 and
-0.956 at metadata costs. No end-position loss is hidden from this min5 result:
open P/L happened to be zero at the specified cutoff, without forced exits.

## Independent chronological segments

Each segment starts flat with previously available indicator warmup. They are
descriptive segments of previously viewed data, not train/validation selection.

| Segment | Condition | Trades | Fixed1.4 PF | Fixed1.4 closed pips | Metadata PF | Metadata closed pips |
|---|---|---:|---:|---:|---:|---:|
| 2023-09-08 to 2024-09-08 exclusive | min0 | 2,144 | 0.477 | -2,876.400 | 0.439 | -3,177.700 |
| same | min5 | 678 | 0.618 | -1,189.735 | 0.590 | -1,292.435 |
| 2024-09-08 to 2025-09-08 exclusive | min0 | 2,686 | 0.763 | -1,921.610 | 0.708 | -2,427.710 |
| same | min5 | 1,280 | 0.932 | -388.880 | 0.886 | -658.780 |
| 2025-09-08 to 2026-08-31 exclusive | min0 | 2,880 | 0.641 | -2,540.860 | 0.579 | -3,077.360 |
| same | min5 | 1,039 | 0.837 | -675.140 | 0.784 | -914.440 |

Min5 wins by segment at fixed1.4: 60.03%, 67.50%, 65.64%; at metadata costs:
59.29%, 66.56%, 65.16%. Each min5 segment has zero terminal open P/L. The min0
last partial segment has -3.3 / -3.6 pips open P/L (fixed / metadata); earlier
min0 segments have zero. Full pair/period metrics are retained in results.json.

## Current min5: per-pair continuous results, fixed1.4 costs

Drawdown columns are each pair's own pips drawdown, not portfolio percentages.
Close-MTM includes open mark-to-close P/L; realized DD uses only settled trades.

| Pair | Trades | Win rate | PF | Closed net pips | Close-MTM DD | Realized DD |
|---|---:|---:|---:|---:|---:|---:|
| USDJPY | 480 | 65.83% | 0.860 | -312.140 | 398.160 | 384.660 |
| EURUSD | 228 | 63.60% | 0.693 | -288.045 | 387.520 | 374.745 |
| GBPUSD | 358 | 63.97% | 0.877 | -151.095 | 240.915 | 226.795 |
| AUDUSD | 221 | 59.73% | 0.686 | -205.295 | 248.325 | 244.955 |
| NZDUSD | 157 | 57.32% | 0.578 | -220.490 | 240.200 | 238.320 |
| USDCHF | 169 | 59.17% | 0.618 | -240.315 | 257.365 | 249.315 |
| USDCAD | 253 | 62.45% | 0.632 | -398.835 | 411.925 | 399.110 |
| EURJPY | 547 | 69.65% | 0.932 | -171.300 | 339.690 | 327.395 |
| GBPJPY | 584 | 68.84% | 0.915 | -266.240 | 526.715 | 502.970 |

## Current min5: pair-specific metadata-cost sensitivity

Same fixed signals/trades; only accounting costs differ. No distance threshold
retuning or cost-dependent signal gate is used in this comparison.

| Pair | Round-trip cost pips | Win rate | PF | Closed net pips | Close-MTM DD | Realized DD |
|---|---:|---:|---:|---:|---:|---:|
| USDJPY | 1.4 | 65.83% | 0.860 | -312.140 | 398.160 | 384.660 |
| EURUSD | 1.3 | 64.04% | 0.715 | -265.245 | 369.320 | 356.145 |
| GBPUSD | 1.6 | 62.57% | 0.822 | -222.695 | 262.470 | 255.310 |
| AUDUSD | 1.4 | 59.73% | 0.686 | -205.295 | 248.325 | 244.955 |
| NZDUSD | 1.6 | 56.05% | 0.530 | -251.890 | 268.000 | 266.120 |
| USDCHF | 1.7 | 56.21% | 0.553 | -291.015 | 305.815 | 298.415 |
| USDCAD | 1.7 | 60.47% | 0.573 | -474.735 | 487.550 | 474.735 |
| EURJPY | 1.5 | 69.47% | 0.911 | -226.000 | 376.390 | 364.095 |
| GBPJPY | 2.0 | 67.98% | 0.811 | -616.640 | 793.715 | 770.665 |

## Exact logic and execution evidence

The existing Pine was read in full and hashed. A candidate with signed center
distance plus **1e-9 pips** below the configured minimum cancels its preparation
and cannot rearm on that same bar. This differs from the earlier exploratory
distance filter, which kept waiting. The new simulator implements the current
Pine cancellation behavior, while min0 exactly reproduces the original baseline.
Five pips is measured at signal close; next actual open can already reach the
center and produce an immediate cost loss. Later moving-center exits can also
be losses; no losing trade is omitted.

- Command: `python -m scripts.research_bb3_context_center5`
- Observed execution chunk `76cb6b`, exit **0**, final status **DESCRIPTIVE_COMPLETE**.
- 144 case artifacts; **72 min0 cases** exactly matched original baseline trade
  matrices and first ten diagnostics over the common periods.
- `python -m pytest tests/test_bb3_context_center5.py -q`: **12 passed**.
- Source/cache hashes, current raw-file stat checks, per-symbol used-prefix
  timestamps/hashes and detailed trades are under `agent_runs/bb3_context_center5_20260909/`.
- Independent `audit.md` confirms **VERIFIED_DESCRIPTIVE**: session `69430`,
  exit **0**; all 144 artifacts / 42,828 trade rows and 11 diagnostics matched a
  separate full-bar state-machine replay. All 144 prefix checks and 72 original
  baseline cases matched; source hashes and common-cutoff prefixes were checked.
  Current-Pine structural tests plus new behavior tests: **62 passed**.

This is simulated historical performance, not actual brokerage profit or a
TradingView live-runtime match. The loaded chart/feed/history/settings can
differ. Variable spread, financing, liquidity/queue, margin and live slippage
are not reconstructed. No Pine edit, history repair, optimization, adoption
approval, external publication or actual trading was performed by this task.
