# BB event edge: preregistered mechanism study

The question is whether BB3 touches contain economically usable short-horizon reversal information before adding entry filters. Temporary order imbalance could reverse; genuine repricing or persistent trends could continue. BB distance alone cannot distinguish these mechanisms.

One event definition, one historical matching method and a primary six-bar response are fixed before execution in protocol.json. Matching on past volatility and clock time reduces two obvious composition differences, but does not identify a causal effect: trend, news and unobserved liquidity remain confounders. The non-touch control uses the event direction, which is an association benchmark and not a tradable control strategy.

Stage A compares displacement from the next executable open, MFE/MAE and initial-center versus moving-center contacts. No future outcome is used to choose an origin or match. Month clusters share all currencies to avoid treating synchronous USD/JPY shocks as independent evidence. Coverage and control reuse are explicit. Previously inspected 2020–2025 data provide descriptive replication only.

If the preregistered Stage A screen passes in both three-year periods, Stage B compares three confirmation delays on the same origin population with RR1 and no-entry zero outcomes. A failed screen stops this experiment; we do not search different horizons/bands until significance appears. This is a development artifact, not adoption approval.

Ponytail: reuse the SHA-verified cached OHLC/BB/priorATR and installed NumPy/pandas; one runner and one behavior-test module. No paid AI, source-history mutation or Pine changes.

Stage B was permitted by the preregistered Stage A screen. Its execution details and economic research screens were frozen in protocol_stage_b.json before any Stage B P/L execution, after main/validator/quality review. This is a conditional second stage already specified before Stage A; no alternative bands, horizons or matching methods were searched. Stage B compares three complete entry-and-target policies; because each uses its signal-time center, it does not isolate a causal effect of waiting alone.

The prior-control comparison has an important mechanical limitation: assigning the future touch's reversal direction to recent past control windows tends to sign the preceding move negatively. Many control windows also overlap the BB20 formation window. This makes the measured difference an association benchmark, not independent evidence of future profit. Stage B economic calculations are therefore required even when Stage A passes.
