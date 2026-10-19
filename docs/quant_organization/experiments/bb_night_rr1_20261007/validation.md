# Independent validation — BB night RR1

2026-10-07. Final judgment: **不採用 / VERIFIED_REJECTED_CONDITIONAL_CLOCK**. The amended conditional specification and all completed research outputs have been independently reproduced. Actual JST performance remains unverified because source timezone/DST and the user's exact night hours are unconfirmed. Validator ownership is limited to this report and `agent_runs/bb_night_rr1_20261007/verification*` evidence.

## Result-before-spec review

Reviewed `charter.md`, `board.md`, `docs/bb_night_research_plan_20261007.md`, hypothesis and draft protocol before new outcomes.

1. Completed H1 context is available only at H1 close time; 25 consecutive complete M5-observed hours support SMA20 and its five-hour earlier value. No current uncompleted H1 or backfilled missing hour may inform signals. M1 completeness remains a separate known data limitation.
2. Entry eligibility uses the next actual contiguous M5 open and the assumed-clock night window. Each clock/period/arm must replay positions from flat; filtering an old trade file would incorrectly retain daytime occupancy. RR1 exits continue outside the night window, with adverse-first same-bar barriers and actual gap opens.
3. Weekday nights with all seven currencies' 60 expected M5 starts form the predefined observable-night denominator. Zero-entry nights remain; incomplete and missing nights remain separately visible. Full-night coverage is a retrospective reporting flag, never an entry decision. Existing M1-completeness masks provide a stricter supplemental denominator. Exact simultaneous entries are separately deduplicated.
4. GMT0 is the primary fixed source-clock assumption; GMT2/3/9 are sensitivity assumptions. Offset formula, period-calendar conversion, midnight crossing and all-hours reference semantics are explicit. Unknown actual source timezone/DST and provisional 19–24 JST hours require conditional reporting and `adopted=false`.
5. Costs, pip/R sizing, open marks, period-end pending orders and the absence of forced midnight exits are explicit. No account-currency return or independent-risk claim follows from pooled pips/R or simultaneous currencies.

## Completed wording alignment before freeze

- Candidate selection was removed from `search_space`: two new candidates and baseline are fixed and all scenarios remain descriptive. Gates are reported without choosing a winner or a favorable clock.
- Midnight gap exits are now known boundary executions counted separately and not carried after midnight processing. Ordinary stop/target exits within the midnight candle remain boundary-uncertain, with separate strict/possible carry.
- The limitation that frozen baseline origins start at source-calendar 2020 is explicit. Shifted assumed-JST period boundaries can begin during source-calendar 2019; absent historical candidate origins are not missing M5 data.

Result-before-run clarifications were also completed: terminal cache-bar signals without a next open are separately counted as `terminal_unpriced_signals`; no price is invented. An open mark exactly at midnight is right-censored because it precedes observation of midnight-open processing; strict carry requires mark time later than midnight. The director added frequency coverage gates before new P/L: at least 100 M5-complete nights and at least 80% of all weekday nights in each training and validation book. Observable-night counts and missing percentages still remain beside every frequency conclusion.

## Frozen identifiers and completed execution

- Protocol SHA256: `aa339980f0ced8e0843f77918e2a4989474e1f7604a6c64de583e04bf8f12e14`.
- Final result SHA256: `d000a80f3241ced5b66a6db687cc281c6fe2259f354302a44349c2986e472696`.
- Independent reference SHA256: `51bf0387fd1d6a57cabe7a720eefd3ca6c03df019bdddccadccb14490ae320bd`.
- Input identifiers: old seven-cache manifest, seven M1-completeness mask hashes, frozen old baseline signals and new signals; all match the research execution manifest. Its protocol and four source-code/test hashes also match.
- Research output is final `complete=true`, 630 cases, with completed start/finish manifest and final result hash. Independent command `python agent_runs/bb_night_rr1_20261007/verification_reference.py` exited **0** and wrote `agent_runs/bb_night_rr1_20261007/verification_result.json`.

The reference imports no production trading engine. It independently reconstructs hourly membership and causal availability, prior-price efficiency, new signals, next-open eligibility, position occupancy, first price-bar barrier hit, open marks and close MTM. It independently enumerates weekday dates/expected M5 starts and reconstructs all complete/incomplete-night counts, zero nights, exact simultaneous entry deduplication and midnight classifications.

|Verified object|Count|Outcome|
|---|---:|---|
|Cases|630|All match|
|Candidate signals|158,823|All match|
|Closed trade observations / open observations|348,864 / 34|All match; costs/scenarios overlap|
|Individual MTM rows|94,170,708|All match|
|Prefix checks|21|All match|
|Clock/period coverage books|15|All match|
|Night-ledger rows|46,980|All match|
|Combined MTM/aggregate books|90|All match|
|Per-currency year-attribution cells|1,260|All match|

These counts contain repeated cost, clock and policy observations; they are not statistically independent trades. All period gates and twelve clock/arm combined screen statuses match. No candidate or clock was selected after results, and `adopted=false` remains explicit.

## Conditional GMT0 findings

The following assumes source GMT0, no DST, and 19:00–24:00 assumed JST. Periods are 2020–2022 / 2023–2024 / 2025. The third period is descriptive, previously viewed, and not a virgin holdout. All table figures use hypothetical round-trip 1 pip.

|Policy|Mean entries per observed night, by period|Closed PF_R, by period|Net plus open R, by period|
|---|---|---|---|
|Baseline reversal|2.661 / 2.475 / 2.482|0.698 / 0.679 / 0.719|−374.438 / −247.804 / −105.925|
|Range-conditioned reversal|1.582 / 1.441 / 1.525|0.706 / 0.676 / 0.743|−216.837 / −147.043 / −58.414|
|Completed-H1 trend central-line reclaim|10.622 / 10.455 / 10.774|0.718 / 0.676 / 0.670|−1,362.591 / −1,054.514 / −550.942|

The baseline's raw mean meets the requested activity range under this clock assumption, but its cost-after profit is negative. Range conditioning falls below two entries per night and remains unprofitable. Trend reclaim generates more activity than the requested range and also remains unprofitable. No best two or three trades were chosen retrospectively. Deduplicating simultaneous baseline entries yields only 2.173 / 1.969 / 1.973 distinct entry times per observed night.

Primary M5-complete night denominators are 765/783, 510/522 and 257/261 weekdays; stricter all-currency M1-complete night counts are 596, 406 and 229. Missing and partial nights remain distinct from zero-entry complete nights. Both preregistered coverage gates pass for the primary training and validation books; missing coverage does not explain the economic rejection. The GMT2/3/9 sensitivity screens also all fail. All-hours comparisons remain unrestricted-entry/source-calendar references, not actual JST evidence.

Atomic per-currency/period/cost wins, PF, expectancy, DD, open positions and rejections are in `results.json` `summaries`; 90 aggregate books are in `totals`; the 1,260 independently checked yearly entries are in `annual_exit_attribution`. The saved trade/open/MTM and night-ledger files allow reconstruction without relying on this rounded table. Each period starts flat, so concatenated results are not a continuously carried six-year position book. Year tables attribute closed trades by exit-calendar year; they are not separately reset annual simulations.

## Numerical and market-data limitations

Independent direct-sum H1 SMA and the frozen pandas rolling SMA differ by about 1e-14 at some exact-equality boundaries. In the USDJPY diagnostic this changes five candidate comparisons (four direct-sum-only, one frozen-rolling-only). The independently reconstructed hourly windows and direct means agree within 1e-11; exact frozen rolling arithmetic is retained for strict comparisons and the full replay. `verification_float_diagnostic.py` reproduces these boundary examples. No research logic or threshold was changed after P/L.

The data audit verified saved cache/mask/metadata identities and raw source stats, not a fresh full raw-history SHA or full tick/Bid/Ask reconstruction. Partially populated source M1 within an M5 candle remains possible. Actual source timezone/DST is unknown, the 19–24 window is provisional, and the four offsets are hypotheses, not discovered clock settings. Synthetic next-open/chart-OHLC fills and adverse-first same-bar ordering do not prove live execution.

Costs are fixed 1/1.2 pip assumptions; historical GMO spreads, additional actual slippage and swap are not implemented. Longest holding is 1,139 available M5 bars, so omission of overnight costs matters. R and equal-pip scores have no account-currency sizing, leverage or portfolio risk conversion. Simultaneous USD/JPY-linked entries are not independent risks.

## Decision and handoff

**不採用**: zero of two new candidates passes the fixed primary research screen; the reference baseline also fails. Increased frequency does not establish positive expectancy. All completed arithmetic and state paths match the frozen model, while actual-JST applicability remains unverified.

Next owner: research director and quality auditor. Preserve these negative, conditional results and their clock/coverage limitations. No Pine adoption, live-trading approval or parameter reselection follows from this experiment.
