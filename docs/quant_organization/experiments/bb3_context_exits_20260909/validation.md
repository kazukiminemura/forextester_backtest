# BB stop/target experiment: VERIFIED_REJECTED

## Execution

- Command: `python -m scripts.research_bb3_context_exits`
- Observed exit code **0**, execution chunk `dc5110` (no continuing session).
- Final `RESULT_JSON`: `status=REJECTED`, `selected=null`.
- `python -m pytest tests/test_bb3_context_exits.py -q`: **36 passed**, including
  all 18 stop/target/entry combinations checked for closed-trade prefix invariance.
- Frozen inputs/code/protocol hashes, source stat checks, 9-pair manifest,
  pre-validation selection and all per-case trade NPZ files are stored in
  `agent_runs/bb3_context_exits_20260909/`.
- Independent reviewer completed **VERIFIED_REJECTED**, session `29760`, exit
  **0**. See sibling `audit.md`: 396 artifacts / 80,208 trade rows, including
  49,164 stop/target trade rows reproduced by a separate full-bar state machine;
  324 prefix checks, 598 ambiguous-entry bars, 504 dual touches and 23,708 stop
  exits matched. Counts include duplicated cost scenarios, not independent
  market observations.

## Result

All 19 candidates had negative aggregate training net P/L in BOTH predeclared
cost cases. There is no selected candidate, no validation fallback, and no
additional optimization. Only unchanged baseline accessed later-period
descriptive evaluations; candidate results below are training only.

Training: 2023-09-08 inclusive through 2024-09-08 exclusive. Nine-symbol totals
are equal-pip research scores, **not account-currency monetary profits**.

| Candidate | Trades | PF fixed1.4 | Net fixed1.4 pips | PF metadata+.2 | Net metadata+.2 pips |
|---|---:|---:|---:|---:|---:|
| baseline | 2,144 | 0.477 | -2,876.400 | 0.439 | -3,177.700 |
| market_sl5_center | 2,167 | 0.424 | -2,890.735 | 0.387 | -3,195.535 |
| market_sl5_rr13 | 2,048 | 0.633 | -2,706.300 | 0.602 | -2,995.400 |
| market_sl5_rr15 | 2,031 | 0.638 | -2,841.700 | 0.610 | -3,130.300 |
| market_sl10_center | 2,148 | 0.434 | -3,145.395 | 0.399 | -3,446.895 |
| market_sl10_rr13 | 1,823 | 0.779 | -2,617.800 | 0.760 | -2,879.100 |
| market_sl10_rr15 | 1,794 | 0.781 | -2,713.600 | 0.764 | -2,970.600 |
| market_slatr_center | 2,174 | 0.436 | -3,134.120 | 0.401 | -3,439.920 |
| market_slatr_rr13 | 2,112 | 0.653 | -2,648.300 | 0.623 | -2,944.900 |
| market_slatr_rr15 | 2,092 | 0.678 | -2,590.100 | 0.649 | -2,885.500 |
| limit_sl5_center | 694 | 0.545 | -947.015 | 0.507 | -1,053.215 |
| limit_sl5_rr13 | 690 | 0.663 | -822.800 | 0.629 | -928.000 |
| limit_sl5_rr15 | 689 | 0.689 | -804.900 | 0.656 | -909.900 |
| limit_sl10_center | 693 | 0.615 | -888.140 | 0.578 | -994.040 |
| limit_sl10_rr13 | 672 | 0.763 | -1,041.400 | 0.743 | -1,144.000 |
| limit_sl10_rr15 | 671 | 0.804 | -901.300 | 0.784 | -1,003.700 |
| limit_slatr_center | 696 | 0.592 | -921.490 | 0.556 | -1,027.490 |
| limit_slatr_rr13 | 694 | 0.693 | -760.400 | 0.658 | -866.000 |
| limit_slatr_rr15 | 694 | 0.676 | -867.700 | 0.645 | -973.300 |

Highest-PF alternative is a 1-ATR favorable pullback limit, 10-pip fixed stop
and fixed gross RR1.5 target. It has only **1/9 profitable pairs** in either
cost case, not the predeclared 6/9. Its aggregate net is negative, so it is NOT
a replacement recommendation. All training cases have zero terminal open P/L;
the negative results are not concealed in unclosed positions.

## Model details and limitations

SL risk is fixed when the confirmed signal occurs and placed relative to actual
entry fill. ATR is the signal bar's prior ATR, not a fill-time/future ATR. Risk
distance is rounded up to ticks, fixed reward is rounded up to ticks, and the
actual gross RR is at least 1.3/1.5 but not the same as net-of-cost RR. Dynamic
center is the only target updated during holding. No partial exits or widened
stops occur. Original no-stop center baseline is preserved as a separate case.

Stop is live on the entry bar. Open gaps use actual open. Intrabar stop/target
dual touch uses stop first. Intrabar limit entry never receives samebar target
credit; a stop beyond entry remains causally reachable and is charged. Known
opening limit fills allow normal samebar target/stop evaluation. Ambiguity,
stop-exit and cancellation counts are retained in each result row.

The studied three years are previously viewed. No tick-level execution,
variable spread, financing, queue/liquidity, margin or broker constraints are
modeled. Ideal limit-touch fills and OHLC ordering are explicit assumptions.
Closed plus cost-adjusted open P/L is separate from PF; no forced final trade
was added to improve or worsen reported PF.

## Independent handoff

Entry point `simulate_exits(features,times,start,end,pip,cost,tick,limit_entry,
stop_mode,rr)`: stop modes 1/2/3 = fixed5/fixed10/signalATR1.5; rr=0 is center,
otherwise 1.3/1.5 fixed. Trade matrix has original 9 columns plus stop,
initial_target, risk_price, signal_prior_atr, entry_kind and stopped. Entry kind
0/1/2 is market/open-limit/intrabar-limit. Diagnostics append ambiguity,
cancellation, open/touch fills, dual touches and active risk/bracket fields.
The baseline retains its original 9-column/10-diagnostic format and unchanged
implementation. `results.json` explicitly records both column contracts.

No Pine edit, git commit/push or live trading was performed. The user's positive
realized-profit goal remains unmet. Independent `audit.md` confirms rejection;
no adoption claim is made by the researcher. Python tests are not TradingView runtime tests.
