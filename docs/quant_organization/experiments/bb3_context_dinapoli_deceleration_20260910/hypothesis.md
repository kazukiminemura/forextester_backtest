# DMA adverse-momentum deceleration without delayed entry

## Refutable hypothesis

Requiring price to recover across the lagged DMA removed most trades; waiting for recovery failed the prior gates. At the existing BB-return candidate, a favorable change in DMA velocity might instead identify weakening adverse momentum without consuming extra entry distance. This may fail because the displaced short average is noisy, its acceleration changes too late, or the filter retains unprofitable reversals. This is a newly proposed DMA-derived filter, not an authenticated original DiNapoli rule.

## Frozen comparison

The first filter accepts both weakening adverse velocity and increasing favorable velocity. It is not exclusively deceleration of an adverse move. Floating-point values extremely close to zero can change sign with rounding; the exact stated subtraction order is part of the frozen model.

Exactly baseline and two alternatives. Let v=DMA[i]-DMA[i-1], pv=DMA[i-1]-DMA[i-2], side=+1 buy/-1 sell. Deceleration requires side*(v-pv)>0. No-adverse-acceleration accepts side*v>=0 OR the deceleration condition. Zero acceleration alone fails deceleration; zero velocity passes the second case when all three DMA values are finite. No tuned numerical epsilon, extra smoothers, price-side condition, or wait. DMA remains SMA(close,3)[3] with older closes only, sourced as in the prior [provider definition](https://www.luxalgo.com/library/indicator/displaced-ma/).

Both rules require DMA[i:i-3:-1] finite. Evaluate only at the first otherwise eligible confirmed BB candidate after inside-band/min3pips and existing impulse/wick checks. Failure cancels preparation and prevents samebar rearming. Success signals immediately and enters next available open. No SL and full moving-center exit remain the user-requested baseline, not the generic charter fixed RR.

## Evaluation and limits

Same nine pairs,5m,no higher timeframe, two costs, unchanged min3 and common exclusive2026-08-31 cutoff. The source anomaly is not repaired. Segment1-only selection, later baseline+selected only, unchanged win/PF/mean/frequency/6pair gates, no fallback. All periods are previously viewed. Positive closed net AND net+open in every period/cost is a separate requirement for considering adoption, not automatic approval. This finite3case experiment stops when completed, even if every rule fails. Existing Pine, prior studies and raw data stay read-only.
