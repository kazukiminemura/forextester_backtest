# BB context entry timing: frozen finite experiment

The current Pine indicator is the baseline, not an authenticated WEMOF rule.
The user requests entry timing changes, not an accounting change. Keep the
existing confirmed 5 minute BB20 population 3 sigma preparation, long-wick and
impulse exclusions, next available open fills, dynamic central SMA full exit,
and no stop by default. This user-specific exit supersedes the generic RR1
research default. No higher timeframe, news, session or symbol optimization.

Hypothesis: waiting for a directional reversal close, or a close beyond a
previous/preparation candle extreme, may avoid continuation immediately after
a band touch. Requiring remaining center distance of 2 or 3 round-trip costs
may avoid small gross gains consumed by costs. Extending preparation expiry
from 3 to 6 bars permits confirmed reversals without entering on the touch.
Failure conditions: trending regimes continue after weak reversals; stronger
confirmation arrives too late and consumes the remaining reversion distance;
moving SMA exits can realize losses; no stop can conceal losses in open trades.

Exactly 12 candidates including baseline are frozen in protocol.json before
loading price outcomes. Train-only selection is followed by validation and a
previously viewed third-year check, without retuning. No result guarantees a
positive future return or a positive TradingView window/broker dataset.

All return thresholds use the configured round-trip cost, so cost sensitivity
can change eligible trades. Report both fixed 1.4 pips and metadata spread +
0.2 pips. They are two predeclared stress models, not optimized parameters.
Use per-period fresh portfolios and pre-period indicator warmup. Also save
continuous 3-year portfolios for direct comparison with the Pine history.
Unclosed mark-to-close P/L (one full cost deducted) and net plus that P/L are
reported separately; never erase or force a losing trade into PF.

Mixed-symbol pips totals describe an equal-unit research basket, not an
account-currency portfolio return. Historical source timezone is retained as
stored and is not asserted to be UTC. OHLC aggregation may contain incomplete
5-minute bars, as in the existing HistoryRepository implementation. No swaps,
variable spread, bid/ask execution, leverage or broker constraints are modeled.
