# DiNapoli-style 3x3 DMA: no verified improvement

## Outcome

All three DMA alternatives failed the predeclared first-segment improvement
gates. No candidate was selected. The crossover case shows a high win rate on
only **9 trades**, which is NOT accepted as evidence that the trading method's
win rate has robustly improved. Existing Pine remains unchanged.

First segment: **2023-09-08 inclusive through 2024-09-08 exclusive**, nine pairs,
current baseline minimum center distance **3 pips**, no stop, dynamic center
full exit. The cases were fixed before outcomes; no threshold, exit or waiting
period was retuned. Only the baseline was evaluated on later segments and the
continuous period because no DMA case qualified for preselection.

| First-segment case | Trades | Win fixed1.4 | PF fixed1.4 | Net fixed1.4 pips | Win metadata+.2 | PF metadata+.2 | Net metadata+.2 pips |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline, no DMA | 1,146 | 61.52% | 0.576 | -1,794.25 | 60.30% | 0.543 | -1,968.85 |
| Favorable DMA side | 15 | 66.67% | 0.673 | -11.17 | 60.00% | 0.593 | -14.57 |
| Samebar DMA crossover | 9 | 77.78% | 5.600 | +11.50 | 66.67% | 3.179 | +8.50 |
| Favorable side + DMA slope | 1 | 0.00% | 0.000 | -12.22 | 0.00% | 0.000 | -12.42 |

Pooled pips are equal-pip research scores across different quote currencies,
**not account-currency monetary profit**. First-segment open P/L is zero for
every case without forced liquidation. The crossover's positive small-sample
net result does not override its failed sample-size and cross-pair gates.

## Why no candidate passed

The frozen first-segment requirements include at least 30 trades AND at least
25% of baseline trade count: with 1,146 baseline trades this means **287 or
more**. DMA-side retained only 1.31%, crossover 0.79%, and side+slope 0.09%.
Thus every variant failed retained-frequency and minimum-count requirements.

- Favorable side improved win rate in only 4/9 pairs instead of the required
  6/9. Its metadata-cost aggregate win rate also decreased versus baseline.
- Crossover improved win rate in only 4/9 pairs and had just 9 trades. Its
  large PF is recorded faithfully but cannot justify relaxing the frozen gates.
- Side+slope had one losing trade, zero improved pairs and worse PF/mean return.

DMA confirmations were checked only at the first otherwise-eligible candidate.
Failure canceled preparation and prohibited samebar rearming; the experiment
did not keep waiting for a future DMA recovery. This combination with a 3-sigma
reversal setup removed almost all trade opportunities. That conclusion applies
to these specified filters, not the entire DiNapoli trading methodology.

### First-segment geometry diagnostic

At the baseline's 1,146 closed-trade signal closes, **1,133 (98.87%)** were
not on the intended trade's favorable DMA side. Signed close-minus-DMA
distance (positive means favorable for that buy/sell) had median **-5.07 pips**
and mean **-6.41 pips**. These measurements use first-segment baseline rows
only, once per pair, and are saved in `training_dma_geometry_diagnostic.json`.
This sample is not the same as each filtered simulator's candidate population:
rejecting an entry changes later position availability.

Inference: the existing BB-return signal usually precedes recovery across
the lagged DMA. Waiting for a subsequent DMA recovery could therefore be a
different state-based hypothesis, but it was **not tested** here and is not
evidence of improved win rate or profit. No additional experiment was run.

## Exact DMA definition

Current-bar DMA is `ta.sma(close, 3)[3]`, or Python
`mean(close[i-5:i-2])`: closes i-5, i-4 and i-3 only. A forward plot shift does
not authorize future data. Favorable side uses strict close>DMA for buys and
close<DMA for sells; cross additionally requires prior close on/equal to the
opposite side of prior DMA. Slope additionally requires strict favorable change
in DMA. Definition follows the provider's close-based SMA3 displaced3 overlay,
not a claim to reproduce all original DiNapoli rules.
[Provider definition](https://www.luxalgo.com/library/indicator/displaced-ma/)

## Unchanged baseline reference, safe common period

Known GBPJPY source-scale corruption on 2026-08-31 and subsequent data are
outside the common exclusive cutoff **2026-08-31** for all nine symbols.
Source files were not repaired, normalized or edited. Arrays were prefix-cut
before DMA generation or simulation. All periods were previously viewed and
must not be described as untouched holdout data.

| Baseline segment | Trades | Fixed1.4 win rate | Fixed1.4 PF | Fixed1.4 net pips | Metadata PF | Metadata net pips |
|---|---:|---:|---:|---:|---:|---:|
| 2023-09-08 to 2024-09-08 exclusive | 1,146 | 61.52% | 0.576 | -1,794.250 | 0.543 | -1,968.850 |
| 2024-09-08 to 2025-09-08 exclusive | 1,837 | 67.66% | 0.879 | -821.485 | 0.828 | -1,189.385 |
| 2025-09-08 to 2026-08-31 exclusive | 1,747 | 66.23% | 0.774 | -1,247.140 | 0.715 | -1,611.040 |
| Continuous 2023-09-08 to cutoff | 4,730 | 65.64% | 0.767 | -3,862.875 | 0.717 | -4,769.275 |

Each independent segment starts flat with indicator warmup. Baseline terminal
open P/L is zero in all rows. Pair-specific drawdowns, win rates and all P/L
fields are retained in `results.json.rows`; pooled drawdown fields mean the
largest single-pair drawdown, not a monetary portfolio drawdown.

## Execution and handoff

- Command: `python -m scripts.research_bb3_context_dinapoli`
- Observed exit **0**, execution chunk `aa0db2`.
- Final `RESULT_JSON`: `NO_VERIFIED_IMPROVEMENT`, `selected=null`,
  `profit_requirement_met=false`.
- 126 case artifacts. All 72 baseline cases exactly matched the previously
  verified center-distance simulator configured at 3 pips.
- `python -m pytest tests/test_bb3_context_dinapoli.py -q`: **16 passed**.
- Frozen protocol/source/Pine/input hashes, source stat checks, safe-prefix and
  DMA hashes, pre-later-period selection, all trade matrices and diagnostics
  are under `agent_runs/bb3_context_dinapoli_20260909/`.
- Independent audit: **VERIFIED_REJECTED**, documented in sibling `audit.md`.
  Session `40595`, chunk `910d25`, exit **0** independently reproduced all
  126 artifacts, 18,970 trade rows and 12 diagnostics; 126 prefix checks and
  72 baseline comparisons matched. Selection was independently `null`.
  Combined current-Pine and DMA tests: **66 passed**.

`simulate_dma(features,times,dma,start,end,pip,cost,dma_mode)` returns the existing
9-column trade matrix and 12 diagnostics (original center simulator's 11 plus
DMA rejection count). `improvement_checks` preserves monetary wins as net>0,
checks PF/mean non-deterioration and sample/pair coverage, and does not equate
improvement with profitability. For any future adoption consideration, both
closed net and closed+open must also be positive in every evaluated period and
both cost cases, plus separate execution/runtime/risk review.

No Pine edit, source-data mutation, git publication or real order was made.
No second candidate was substituted after failure and no extra search occurred.
Local research checks do not verify TradingView runtime or broker profits.
