# Preparation-extreme stop: finite new experiment

The user requested another stop-rule change. Fixed-pip and ATR-distance exits
in the preceding experiment failed the training gates. This experiment tests
whether invalidating the actual preparation structure is more informative than
a uniform distance from entry. A buy stop is below the lowest low from the
preparation bar THROUGH the confirmed signal bar; a sell stop is above the
highest high over that same closed interval. Add 0.10 or 0.25 times the signal's
prior ATR as a fixed buffer. No post-signal or post-entry extremes enter the SL.

Failure conditions: structural extremes are ordinary noise rather than genuine
invalidation; brief sweeps stop a subsequent reversal; wide preparation ranges
produce excessive risk/remote fixed targets; costs consume the small-range
cases. More geometry alone is not a promised edge. Fixed 10-pip stop comparators
use the exact previous implementation and provide the simple control.

Six cases only: market or unchanged 1-ATR favorable limit/3 bars, each with
structural 0.10/0.25 ATR buffer or fixed 10-pip control. All use full fixed gross
RR1.3, existing confirmed signal/filter rules, nine symbols and both previous
cost models. Entry changes are not added in this experiment. Stops never move.

Pre-outcome data-quality amendment: the independent reviewer found suspicious
GBPJPY 2026-08-31 prices around 2.16 in the cached data. This date is outside
training, but later-period and continuous evaluation must stop, including
controls. Do not silently remove or repair those bars. This experiment can
reject on training failure; any train-selected candidate remains NEEDS_EVIDENCE
until the source issue is resolved with separate authority. In structural
cases, compute RR from the exact entry-to-absolute-SL distance and round the
absolute target outward to ticks; never round risk down before computing RR.
Fixed10 controls retain their original implementation for exact reproduction.

Before outcomes, the director and independent reviewer corrected the proposed
invalid-gap treatment: a valid order filled beyond the structural SL is NOT
erased by cancellation. It enters at open and immediately exits at that same
open, charging the whole round-trip cost. Do not compute an RR target when risk
is nonpositive. A known invalid limit price at signal creation is not submitted.
These gap trades are counted separately and preserve adverse outcomes. Actual
broker stop execution may be worse and is not modeled by this zero-distance
instant-close convention.

All periods were previously viewed. Train-only selection cannot create an
untouched holdout; later evaluation is suspended for the data issue above.
All six candidates failing means this finite experiment stops. No
Pine replacement before independent validation, and no real-money approval.
