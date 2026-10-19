# Current Pine min-center-distance: descriptive profit verification

The user asks to check profitability of the CURRENT Pine indicator, whose
minimum signal-close-to-center distance is now 5 pips. This is not an optimized
new strategy selection. Compare only the fixed user-requested 5-pip condition
with the existing 0-pip control, keeping all other defaults unchanged.

The 5-pip condition may reduce signals with too little gross room to absorb
costs. It does not guarantee 5 pips from the next actual entry, since next-open
gaps and the subsequently moving SMA can change the available distance. It may
also select stronger trends that continue against a mean-reversion position.

Important exact state behavior: on an otherwise eligible confirmed signal,
insufficient center distance CANCELS the preparation and blocks samebar
rearming. It does not keep waiting as the prior exploratory timing-distance
filter did. Compare signed distance + 1e-9 pips against the configured minimum.

Use no stop and full dynamic-center exits, one fixed-unit position, no news
filter, no position sizing or actual brokerage orders. Cost accounting stays
at raw chart-price fills minus one full round-trip cost. Open P/L is separate
from realized PF. Report both fixed1.4 and pair metadata spread+0.2 pips.

Due to the confirmed GBPJPY source-scale anomaly on 2026-08-31, use a common
END EXCLUSIVE 2026-08-31 for ALL nine symbols. Do not repair/remove records or
use anomaly-day/later prices. All used feature arrays are prefix-truncated
before evaluation. Show continuous 2023-09-08 to cutoff and three independent
segments ending at 2024-09-08, 2025-09-08, and cutoff. This period was viewed
before and is not an untouched holdout. No learning/selection/retuning occurs.

Equal-pip aggregate scores across quote currencies are not account-currency
profits. Per-pair results and drawdowns are primary. Local backtests cannot
verify the user's loaded TradingView chart/feed/settings or realized broker P/L.
