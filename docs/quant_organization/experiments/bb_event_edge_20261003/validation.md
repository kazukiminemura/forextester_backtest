# Independent validation — BB event edge

2026-10-03. Final judgment: **不採用 / VERIFIED_REJECTED_DESCRIPTIVE**. Stage A is independently reproduced and its predefined continuation screen passes. Stage B is independently reproduced and all three economic screens plus both waiting-benefit screens fail. Neither stage approves live trading.

## Frozen inputs and reproduction

- Protocol A SHA256: `2e47941a0d983b3b8921b930cda2f4973331e284836ba307e5462286613444bb`.
- Input ledger: `agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json`; seven saved feature caches are SHA256-checked against the execution manifest.
- Frozen research snapshot: `agent_runs/bb_event_edge_20261003/source_stage_a.py` and `tests_stage_a.py`. No strategy or selection criteria were changed by the validator.
- Independent evidence: `agent_runs/bb_event_edge_20261003/verification_result.json`, `verification_secondary.json` and their matching `.py` reference scripts.
- Commands: `python agent_runs/bb_event_edge_20261003/verification_reference.py` and `python agent_runs/bb_event_edge_20261003/verification_secondary.py`; both processes exited 0. Research final `results.json` has `complete=true`, final manifest timestamps and matching SHA256.

## Stage A checks

Independently reconstructed BB20 population bands and prior Wilder ATR14 from 3,182,106 cached OHLC rows, with absolute tolerance 1e-11. An exact-price center contact can change at floating-point rounding differences around 2.8e-14; after confirming the causal reconstruction, the frozen cache values are retained for exact touch comparisons. No future price enters the selected origin or control.

The independent binary-search control selector and 13-bar reservation sequence reproduce all 56,212 origins, sides and selected controls. Latest eligible controls use the same currency/month/four-hour bucket/past ATR band, end no later than t-13, inherit the event side, allow recorded reuse, and are never replaced after an unfavorable or censored outcome.

All 5,846,048 event/control numeric observations agree, including four horizons, favorable/adverse excursions, fixed/moving-center contacts, first contact decomposition, and adverse-first ATR barrier ordering. Twenty-eight prefix cases reproduce the online selections. Three reporting periods, 468 mean fields, common-month bootstrap confidence intervals, leave-month-out statistics and continuation gates agree. Secondary verification checks 450,695 items: timestamp/month/ATR identities, all missing-data reasons, six yearly slices and reuse accounting.

|Previously viewed period|Paired six-bar observations|Coverage|Event less control, ATR units|Monthly-cluster 95% interval|Event movement less 1 pip|
|---|---:|---:|---:|---|---:|
|2020–2022|27,217|96.67%|0.11393|[0.06024, 0.16644]|−0.80003 pip|
|2023–2025|26,220|96.21%|0.21328|[0.16098, 0.26441]|−0.54032 pip|

Both predefined Stage A continuation screens pass. Event movement after hypothetical costs is negative in both periods. These horizon observations have no trade win rate, portfolio drawdown or executable PF; those belong to Stage B.

## Interpretation and unresolved limits

The control is historical and inherits the later event direction. Its price window may overlap the 20-close window that defines the later BB event. A preceding trend can therefore mechanically make the signed control return negative. The observed difference is a conditional association, not a causal effect or an independently tradable prediction. This was identified during review, and matching was not modified after viewing results.

Joint calendar-month resampling keeps contemporaneous currency shocks and repeated controls together. It does not establish independence across months or remove all serial dependence. Both three-year periods were previously viewed; neither is a virgin holdout. M5 source candles, incomplete M1 coverage, unknown source clock and hypothetical 1/1.2 pip costs retain the inherited data limitations. No account sizing or currency conversion is present, and ATR/pip scores are not account profits.

## Stage B prereview

The additive three-arm contract was reviewed before execution: same Stage A origin ledger; touch / reversal close / later close breakout; next contiguous open; cancellation before confirmation on the same bar; fixed signal-time center; minimum actual room 3 pips; full exit RR1; one position per currency and arm; two independent three-year books; no-entry origins remain zero; end-open P/L is separate. Waiting-benefit screens and economic-continuation screens are distinct. No best-arm selection or deployment approval is permitted.

## Stage B independent execution and results

The research process exited 0 and final Stage B result SHA256 is `b6cb8898ea9951b74f33c8e8e71325ff7e0361d9996025ec189bbf358e7503d2`. Protocol B SHA256 is `fe630f09a035bb563b43cbb2da91e885774bdcf14a3970bbfc8c0a4573438715`. Frozen source/test snapshots are under `agent_runs/bb_event_edge_20261003/stage_b/`; their hashes, the unchanged execution engine hash and protocol hash match the start manifest.

Reproduction commands, both exit 0:

- `python agent_runs/bb_event_edge_20261003/verification_stage_b.py`
- `python agent_runs/bb_event_edge_20261003/verification_stage_b_totals.py`

The independent reference does not call the research simulation engine. It reconstructs signals and cancellation, scans each candidate's future prices for the first adverse/favorable barrier hit, reconstructs the full origin ledger and rebuilds close mark-to-market. Full matches: **84 cases, 103,300 candidate signals, 125,046 closed-trade observations, 337,272 origin-ledger rows, 18,834,138 individual MTM rows, 28 prefix cases, 12 combined MTM curves**, and paired gross/net waiting-difference confidence intervals. Trade observations include the two cost scenarios and are not distinct market opportunities. A separate 62,619-check pass verifies aggregate PF/wins/positive pairs/statuses/open positions/maximum holding, exact +0.2 pip stress attribution, waiting-benefit booleans and all 18 exit-year attribution rows.

|Book|Policy|Closed|Win rate|Cost-after PF_R|Average closed R|Net plus open R|Close-MTM DD R|
|---|---|---:|---:|---:|---:|---:|---:|
|2020–2022|Touch next open|21,378|51.84%|0.8284|−0.09394|−2,006.82|2,063.25|
|2020–2022|Reversal close next open|8,598|50.28%|0.7341|−0.15395|−1,322.89|1,327.55|
|2020–2022|Breakout close next open|2,630|49.43%|0.6771|−0.19330|−508.37|514.53|
|2023–2025|Touch next open|19,968|52.45%|0.8405|−0.08699|−1,736.95|1,743.36|
|2023–2025|Reversal close next open|7,694|52.17%|0.7840|−0.12081|−929.48|935.88|
|2023–2025|Breakout close next open|2,255|50.11%|0.6926|−0.18251|−411.55|413.03|

Complete per-currency/per-book/per-cost trade counts, win rates, PF, expected R and DD are in the independently checked `stage_b/results.json` `summaries` array. Each of the seven currencies has negative net-plus-open R in every policy/book at 1 pip. Stress at 1.2 pip is also negative. Three positions remain open at the end of the first books (two touch, one reversal); none at the end of the second. Closed PF excludes these open marks. Six-year totals sum two flat-start three-year books, not one continuous six-year portfolio. Yearly results are exit-year attribution, not new annual reset simulations.

Reversal minus touch has positive cost-after R per-origin differences but negative gross differences in both periods. Breakout minus reversal also fails the required positive gross-difference confidence bound. Waiting reduces costly activity without establishing profitable trade quality; no-entry zeros are included, and target prices change with signal timing, so this is a complete-policy comparison rather than the isolated causal effect of delay. The zero-trade policy has 0 R and exceeds all three measured net outcomes.

Evidence files: `verification_stage_b.json`, `verification_stage_b_totals.json`, and their saved reference scripts, all under the Stage A run directory. No production/research strategy code, original data, old experiment, or adoption criterion was changed by this validator.

## Decision and handoff

**不採用**. Zero of three economic candidates and zero of two waiting-benefit comparisons pass the preregistered criteria. The small gross response at the fixed six-bar horizon is below hypothetical transaction friction; significant past-control differences cannot establish an independent profitable forecast. Stage A's label is continuation-screen-only, not strategy research acceptance.

Unimplemented costs include historical bid/ask spreads, extra real slippage and swap. Maximum holding is 3,474 available M5 bars, so swap omission is material; clock gaps can make elapsed calendar time longer. Quantity and account-currency sizing are absent, and cross-currency R scores are standardized hypothetical initial-risk units. These limitations do not turn negative results into adoption evidence.

Next owner: research director and quality auditor. Preserve the negative experiment and report its limits. Further hypotheses require a new preregistered experiment; no Pine handoff or live approval follows this result.
