# Candle shape confirmation for the current BB3 strategy

Frozen before candidate outcomes: 2026-09-19 12:02 JST. Protocol is authoritative.

The user asks for a candle-shape improvement to the existing BB strategy, not
a replacement exit. Keep the currently requested moving-center full exit and
stop OFF to isolate shape effects; this study does not claim fixed RR1.

## Falsifiable hypotheses

1. A body in the proposed reversal direction, closing within the final35% of
   its range, indicates sustained rejection rather than a weak mid-range close.
2. Requiring that body to occupy at least half the range additionally rejects
   indecision; it may also reject early profitable turns.
3. Engulfing the previous opposite body indicates reversal of short-term flow.
4. Closing beyond the previous full range indicates stronger recovery but may
   consume the profit distance and enter too late.

Long/short mirror exactly. No pinbar candidate: existing touch-side long-wick
exclusion remains unchanged. These are conditional OHLC hypotheses, not proof
of participants' intentions. They fail during continuing trends, news shocks,
range-expansion false reversals, or when extra confirmation consumes the edge.

The comparison is the unfiltered baseline. Only four fixed candidates, no
threshold sweep. Each is a stateful replay, not ex-post filtering of baseline
trades: after a rejection a later new setup may be traded. The first eligible
signal either passes or cancels the setup; this is not a waiting strategy.

Use the same eight non-quarantined pairs and two fixed round-trip costs. Periods
are previously viewed, not an untouched test. Only training selects a candidate;
at most one candidate proceeds and validation failure ends the experiment.
The previous-range reclaim family already appeared in prior timing mode2
research under different distance/waiting rules; it is not a novel hypothesis
on previously untouched data. Current four candidates remain fixed.
Thresholds and selection gates are in protocol.json. Reject the improvement
claim unless wins after costs improve by at least2 points, profitability and
frequency gates pass at both costs, and at least5 pairs are positive.

No stop and omitted swap are material risks. A higher observed win rate alone
cannot authorize live use or Pine adoption. Independent audit owns that decision.
