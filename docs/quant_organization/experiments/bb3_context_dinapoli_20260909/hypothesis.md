# DiNapoli-style 3x3 DMA confirmation for current BB context signals

Current Pine baseline: minimum center distance **3 pips**, no stop, dynamic
SMA20 full exit and all existing confirmed preparation/exclusion rules. The
user requests improving win rate using 3x3. Do not alter exit accounting or
count losses/breakevens as wins to produce a higher percentage.

A displaced SMA3 plotted three bars to the right has the current-bar value
`SMA(close,3)[3]`: mean of close[i-5], close[i-4], close[i-3]. It does NOT use
future closes. This is consistent with the indicator provider's definition
of 3x3 as close-based SMA3 displaced3. This experiment tests simple DMA filters,
not a claim to reproduce the complete authenticated DiNapoli trading system.
[Provider implementation description](https://www.luxalgo.com/library/indicator/displaced-ma/)

Hypothesis: price recovering the past DMA toward the expected mean-reversion
direction can distinguish reversals from continuation. An actual crossover or
a favorable DMA slope may strengthen confirmation. Failure conditions: the
delayed line confirms too late, consumes remaining center distance, or rejects
profitable V-shaped reversals; slope confirmation may leave too few trades.
Therefore test win rate together with PF, mean net return and retained sample
size, not win rate alone. Positive historical net P/L is a separate requirement.

Exactly four cases: unchanged baseline; close on favorable DMA side; samebar
close/DMA crossover; favorable side AND favorable DMA slope. Test only the first
otherwise-eligible candidate. A failed DMA filter cancels its preparation and
prevents samebar rearming; there is no optimized waiting or retry period.

Before outcomes, director and independent reviewer restricted later evaluation:
all four cases use segment1 only for selection. Among DMA cases passing fixed
training improvement gates, select one by worst-cost win-rate uplift, then
worst-cost PF uplift, then ID. Only baseline plus that candidate see later
segments/continuous, without fallback. No selected candidate means baseline-only
later descriptions. All periods were previously viewed; none is an untouched
holdout. Winning research improvement is not real-money approval.

Use the same safe common prefix ending before 2026-08-31 for all nine pairs,
avoiding the known GBPJPY source-scale anomaly. No history repair or deletion.
Costs: fixed1.4 and metadata spread+.2 pips. Mixed quote-currency pips are
equal-pip research scores, not portfolio currency profits. Existing Pine is
read-only pending evidence and director/independent review.
