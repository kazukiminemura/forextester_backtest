# Evening opportunity research — fixed draft

Goal: test whether a single frozen FX policy provides an average of at least2opportunities per observable assumed-JST weekday evening, while retaining positive after-cost expectancy. More than3is reported as above the desired activity, not a reason to choose the best trades after the fact.

Prior evidence matters: unfiltered BB3 touch/confirmation/breakout and simple BB2 recovery were all unprofitable after the assumed costs. We therefore fix only two new mechanisms: low directional efficiency might isolate range reversion; completed-H1 trend with M5 central-line recovery might capture continuation after a pullback. Both can fail through trend regime errors, insufficient movement relative to costs, low nightly coverage or correlated simultaneous signals.

The baseline is the exact saved Stage B reversal policy, replayed under entry restrictions. RangeBB adds one prior-only efficiency condition. Trend recovery has a different symmetric ATR bracket, so its comparison is a whole-policy comparison, not a causal attribution solely to trend direction. All exits are full RR1 before fees.

The actual History clock and DST remain UNKNOWN. GMT0 is a primary hypothesis and GMT2/3/9 are fixed sensitivity cases. No clock is inferred from profit. The19–24window is provisional. Conditional results cannot establish actual-JST feasibility or adoption while those assumptions are unconfirmed.

Saved data, masks, signals and proven execution arithmetic are reused. New code consists of one runner and one behavior-test module; no shared-engine, raw-history, old-research or Pine edits. No paid model calls. Specification review and freeze precede P/L execution.
