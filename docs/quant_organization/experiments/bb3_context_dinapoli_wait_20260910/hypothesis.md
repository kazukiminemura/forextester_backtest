# BB candidate followed by bounded DMA recovery

## Hypothesis and necessity

The previous samebar DMA filter removed almost every baseline candidate. A separate waiting state may allow reversal confirmation after the first BB-return candidate, without demanding a crossover at that exact instant. This can fail if delay consumes the remaining mean-reversion distance, creates adverse selection, or removes too many trades. It is not evidence that waiting works.

Compare only current min3 baseline and maximum 3/6 subsequent-bar waits. No stop and full moving SMA20 exit remain user-requested baseline behavior, not the charter default fixed RR. Five-minute bars, both directions, no higher timeframe. DMA uses causal SMA(close,3)[3] as previously defined by [the provider](https://www.luxalgo.com/library/indicator/displaced-ma/).

## Frozen state transition

Original BB preparation and expiry3 create a first otherwise-eligible confirmed candidate after inside-band and minimum3pips checks. Favorable DMA signals immediately; otherwise wait starts with a fixed candidate index. Within the next 3 or 6 bars inclusive, favorable DMA plus inside band and minimum3pips signals at close, entering next available open. Gap, explained move, relevant wick, opposite touch, center passed, distance below3, or deadline exceeded cancels first. Cancellation prevents samebar rearming. Same-side band retouch alone neither cancels nor extends the deadline. Outside-band close alone may wait. Missing/equal DMA never confirms. No new preparation while waiting. Gap cancellation applies before any waiting signal; pending market signals retain existing next-available-open behavior.

## Evaluation and limits

Protocol fixes the same nine pairs, two cost cases, safe exclusive2026-08-31 cutoff, and previously viewed periods. All3 cases use segment1 only for preselection under unchanged winrate/PF/mean/sample/cross-pair gates. Only selected+baseline see later data; no selected means baseline only. Profitability separately requires closed net and net+open positive in every period and cost. No data edits, Pine changes, live approval or fallback optimization.

Diagnostics preserve terminal waiting direction and last origin (origin is active only when direction is nonzero). Cancellation reason counts may overlap on the same bar; total waiting cancellations counts the canceled state once. The reasons are not-ready, gap, explained move, relevant wick, center passed, opposite touch, insufficient distance and expired TTL.
