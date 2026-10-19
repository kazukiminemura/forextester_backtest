# H1 trend and M5 volatility context

Freeze all6 filters before outcome computation. CurrentBB and body-engulf are
the two simple baselines; each adds trend only, volatility only or both.
No candle threshold or exit tuning is allowed in this experiment.

Mean reversion can fail if a local reversal candle opposes persistent H1 flow.
A confirmed SMA20 slope normalized by H1 ATR makes this direction check scale
invariant. It can fail when the H1 trend is late at a real turn or is merely
noise; no causal orderflow claim is made.

Very quiet markets leave little room relative to transaction costs, while
exceptionally volatile M5 bars can reflect continuing repricing. ATR ratios
and a current-range cap reject those regimes. This can also discard profitable
overshoots. Bounds are fixed0.5–2.0 and2.5, not optimized.

Only complete observed H1 candles are used at their actual available close.
SMA/ATR warming, skipped incomplete hours and M5 gaps are explicitly specified
in protocol. Strong-trend boundaries are inclusive; zero/unknown denominators
are not tradable. Rejected entries cancel the preparation rather than wait.

These data and baselines were previously studied. Report descriptive continuous
2023–2025 and annual exit-year results, not independent out-of-sample proof.
Both quoted-spread and +0.2pip stress cases must meet the fixed improvement,
frequency, profitability, per-year and pair-breadth gates. Costs across all hours
are assumed normal spreads, not actual historical spreads; swap is omitted.
Existing no-stop moving-center exit is preserved to isolate context changes,
so high win rate does not establish bounded risk or fixed RR1.
