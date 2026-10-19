# BB event edge research — 2020–2025

Status: developer execution completed; independent validation and quality sign-off are separate documents. Every economic candidate failed the preregistered screen. No strategy adoption.

## Question and fixed experiment

Does a BB20/3-sigma touch predict a meaningful reversal before deciding how to enter? Seven cached Forex Tester M5 series were SHA-verified. A touch is observed on a closed candle; all measured movement begins at the next contiguous open. One selected origin reserves the next12bars, producing56,212origins across2020–2025. No context/wick filter was applied. All years were previously viewed, so this is descriptive replication, not an untouched holdout.

Stage A fixed six-bar movement as primary before execution, with1/3/12bar secondary responses. A prior non-touch control was matched on symbol, YYYY-MM, source-clock4-hourbucket and past-only ATR regime. All seven currencies share each resampled month in the10,000draw confidence calculation. Stage B details were frozen after the conditional Stage A gate passed and before any Stage B P/L was evaluated.

## Stage A: a small gross response, below the assumed friction

| Period | Paired origins | Coverage of valid6 | Reversal mean ATR | Control difference ATR,95% interval | Gross mean pips | After1pip |
|---|---:|---:|---:|---|---:|---:|
|2020–2022|27,217|96.67%|0.07187|0.11393 [0.06024,0.16644]|0.19997|−0.80003|
|2023–2025|26,220|96.21%|0.17293|0.21328 [0.16098,0.26441]|0.45968|−0.54032|
|Combined descriptive|53,437|96.45%|0.12146|0.16268 [0.12317,0.20160]|0.32740|−0.67260|

Both periods met the preregistered mechanism screen: paired count/coverage, positive mean, positive difference confidence lower bound, at least4positive currency differences and positive leave-one-month-out differences. This only permitted Stage B; it did not establish economic profitability. The1pip subtraction here is a fixed-horizon movement sensitivity, not a simulated strategy return.

On paired6bar observations, average maximum favorable/adverse excursions were1.836/1.773priorATR. Initial-center contacts occurred in33.96%, moving-center contacts in42.56%. The moving center can approach price; its contact is not proof of favorable executable displacement. Across all valid6bar events, symmetric1ATR first passage was favorable26,587, adverse26,014, unresolved2,805; same-bar both-hit is adverse first.

| Symbol | Paired6 | Mean gross reversal pips | Control difference ATR |
|---|---:|---:|---:|
|USDJPY|8,150|0.04880|0.05243|
|EURUSD|7,742|0.12937|0.12217|
|GBPUSD|7,664|0.45808|0.12103|
|AUDUSD|7,401|0.34710|0.17188|
|NZDUSD|7,113|0.38144|0.23108|
|AUDJPY|7,818|0.37574|0.17120|
|NZDJPY|7,549|0.57833|0.28324|

The control association is confounded: the future touch's direction signs recent past price movement, and control windows can overlap the BB formation window. Its negative baseline is not an independent prediction of future reversal. No matching method was changed after seeing results. This is why the direct economic Stage B is essential.

## Stage B: waiting reduced activity and costs, not profitable trade quality

The same56,212origins were followed under exactly three policies. All use next-open fills, signal-time fixed center TP, mirrored RR1 full-exit SL, minimum3pip room and hypothetical round-trip1pip (stress1.2). Reversal requires a later directional close inside bands; breakout requires a still later close beyond that reversal candle's high/low. Origin-extreme breach cancels before confirmation. No-entry origins remain zero in policy comparisons.

Each three-year book starts flat. The six-year values below sum those two books, not one continuous six-year position book. PF and win rate use closed trades; net+open includes separately marked end positions. Pips/R are research scores, not currency-account returns.

| Policy | Closed trades | Win rate | Closed PF_R | Net+open R | Gross R before cost |
|---|---:|---:|---:|---:|---:|
|Touch next open|41,346|52.14%|0.8342|−3,743.77|1,797.80|
|Reversal close next open|16,292|51.17%|0.7572|−2,252.36|385.74|
|Breakout close next open|4,885|49.74%|0.6842|−919.92|−32.10|

| Period | Policy | Closed | PF_R | Net+open R | Stress net+open R | Combined close-MTM DD R |
|---|---|---:|---:|---:|---:|---:|
|2020–2022|Touch|21,378|0.8284|−2,006.82|−2,569.35|2,063.25|
|2020–2022|Reversal|8,598|0.7341|−1,322.89|−1,599.27|1,327.55|
|2020–2022|Breakout|2,630|0.6771|−508.37|−603.87|514.53|
|2023–2025|Touch|19,968|0.8405|−1,736.95|−2,282.73|1,743.36|
|2023–2025|Reversal|7,694|0.7840|−929.48|−1,180.71|935.88|
|2023–2025|Breakout|2,255|0.6926|−411.55|−493.62|413.03|

All7currency books were net+open negative in every policy/period. Cost-stress results were also negative. Economic next-research screen passed0/3.

| Policy difference | Period | Net R/origin difference [95%CI] | Gross R/origin difference [95%CI] |
|---|---|---|---|
|Reversal−Touch|2020–2022|+0.02395 [0.00984,0.03822]|−0.02615 [−0.03948,−0.01203]|
|Reversal−Touch|2023–2025|+0.02920 [0.01804,0.04017]|−0.02406 [−0.03490,−0.01354]|
|Breakout−Reversal|2020–2022|+0.02852 [0.02130,0.03568]|−0.00315 [−0.00986,0.00350]|
|Breakout−Reversal|2023–2025|+0.01873 [0.01322,0.02418]|−0.01186 [−0.01729,−0.00656]|

Waiting lowered the loss per origin largely by avoiding trades/costs. Gross advantage did not improve, and conditional trade PF fell. The preregistered requirement that waiting improve both gross and net with positive confidence bounds failed for both comparisons. Signal-time targets differ, so these are differences between complete confirmation-and-target policies, not causal effects of delay alone. A hypothetical never-enter policy would score0R/origin and exceed all three net outcomes.

## Calendar-year closed-trade attribution

These are exit-year slices of the two fixed books, not newly initialized annual tests. Open marks are excluded from this table.

|Year|Touch: count / win% / PF_R / netR|Reversal: count / win% / PF_R / netR|Breakout: count / win% / PF_R / netR|
|---|---|---|---|
|2020|7,262 /50.70 /0.7912 /−848.76|3,022 /49.77 /0.7178 /−497.38|931 /47.80 /0.6358 /−209.32|
|2021|6,654 /52.89 /0.8302 /−614.11|2,407 /51.02 /0.7247 /−384.21|672 /47.92 /0.6129 /−163.03|
|2022|7,462 /52.02 /0.8643 /−545.29|3,169 /50.21 /0.7571 /−442.08|1,027 /51.90 /0.7648 /−136.02|
|2023|7,019 /52.07 /0.8371 /−625.71|2,783 /50.88 /0.7474 /−402.29|777 /50.71 /0.7119 /−131.05|
|2024|6,207 /52.28 /0.8214 /−606.70|2,271 /51.83 /0.7696 /−294.63|692 /47.25 /0.6168 /−166.43|
|2025|6,742 /53.00 /0.8618 /−504.53|2,640 /53.83 /0.8375 /−232.56|786 /52.04 /0.7464 /−114.08|

## Reproduction and handoff

- Stage A: `python scripts/research_bb_event_edge.py` → exit0, `agent_runs/bb_event_edge_20261003/results.json`.
- Stage B: `python scripts/research_bb_event_edge.py --stage-b` → exit0, `agent_runs/bb_event_edge_20261003/stage_b/results.json`,84cases.
- Checks: `python -m pytest tests/test_bb_event_edge.py -q` →11passed, exit0. Boundary checks cover next open, cancellation priority, control censoring, previous-window validity, all-origin zeros, gap/period handling and month resampling.
- Existing outputs cannot be overwritten. For reproduction use `--output agent_runs/bb_event_edge_20261003_replay`; Stage B uses the preserved original Stage A origins and writes to that output's `stage_b/`.
- Original Stage A source/test snapshots are `source_stage_a.py` and `tests_stage_a.py` in the original run directory. Their hashes match the Stage A start manifest, while the current runner adds Stage B. Frozen protocols, code hashes, input hashes and final result hashes are retained.
- Input manifest: `agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json`. Origin/control arrays and all horizon measurements/reasons are in each `*_events.npz`; Stage B signal lists, complete per-origin ledgers, trades and close-MTM curves are saved per case.
- Independent validator owns `validation.md` and verification evidence; quality reviewer owns `audit.md` and `data_inventory.md`. Developer does not approve adoption.

Limitations: source timezone and price side unknown; M5 can hide partial M1 buckets; same-bar SL-first approximates unknown intrabar order; costs are fixed assumptions, not historical GMO executions. Longest hold3,474available M5bars; swap is not modeled. Origin-month resampling does not fully capture dependence of positions held across months. All periods previously viewed. No new paid AI/API calls, orders, Pine changes or Git publication.
