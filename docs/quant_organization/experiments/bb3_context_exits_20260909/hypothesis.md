# BB context: finite stop and target experiment

The user explicitly approved expanding the work to stop-loss and take-profit
rules after 18 entry-only rules were rejected. This is a NEW experiment, not
retroactive retuning of those frozen experiments. Prior results and all three
years have been viewed. The final year is not an untouched holdout.

Hypothesis: the moving central SMA can drift against an unstopped position,
turning originally plausible mean reversion into a large loss. A fixed risk
boundary may cap those continuations. A fixed reward target may prevent the
target from drifting against the position. Failure conditions are repeated
small stops in ordinary noise, targets beyond the actual reversion move, and
round-trip costs consuming gross 1.3/1.5 reward-risk expectancy. Favorable limit
orders also suffer adverse selection and unfilled winning reversals.

Compare unchanged no-stop moving-center baseline with exactly 18 combinations:
market or 1-ATR pullback limit (3 bars); stop 5 pips, 10 pips or 1.5 times the
signal's prior ATR; target moving SMA20, fixed gross RR1.3 or fixed gross RR1.5.
No additional trend/session/news filter and no timeframe change. Full exits,
one position per symbol, no averaging or partial profits. Fixed RR1.3/1.5 follows
the user's earlier requested range and current approved exit-scope expansion;
these are not net-of-cost reward-risk ratios.

All orders use confirmed information. Stop risk is frozen when the signal is
created, placed relative to actual entry fill and never widened afterward.
The limit price is also frozen at signal creation. Fixed target is calculated
from actual filled entry and tick-rounded stop distance. Only the moving-center
target updates after a bar closes, taking effect next bar.

Intrabar limit entry cannot credit the same bar's target because target may
have traded before entry. Its stop beyond the entry price can be charged if
reached: the path from an opening price outside the limit to that stop crosses
the entry first. Opening entry permits normal samebar bracket evaluation.
Gaps execute at open; ambiguous intrabar stop and target use stop first.

Train-only selection, no fallback after validation, finite 19-candidate limit.
Use identical nine symbols and two cost models. Research pips pooled across
quote currencies are not account money. No tick execution, variable spread,
swap, liquidity/queue, margin or broker constraints are claimed to be modeled.
