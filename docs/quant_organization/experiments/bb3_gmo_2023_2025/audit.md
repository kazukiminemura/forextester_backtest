# Independent audit: calendar 2023-2025 BB/GMO descriptive report

## Judgment

**VERIFIED_DESCRIPTIVE**: the requested three-calendar-year accounting is
verified within the model below. This is not adoption approval, an untouched
holdout, a TradingView runtime test or a broker-execution validation.
Auditor read the charter and changed only this audit document.

## Inspected inputs and execution

- Runner: `scripts/report_bb3_gmo_three_year.py`.
- Protocol/results/manifests and 35 trade arrays:
  `agent_runs/bb3_gmo_2023_2025/`.
- Strategy state logic remains `research_bb3_candle_shapes.simulate_shapes`;
  its full independent state replay is recorded in the previous candle-shape
  experiment audit. This turn did not repeat that full alternative simulator.
- Independent audit ran from the repository root with `PYTHONPATH=src`, exit
  **0**, chunk **395c01**. Final marker:
  `VERIFIED_35_TRACES 6127 TRADES_105_ANNUAL_ROWS_7_BASELINES_7_RAW_STATS_HASHES`.

## Coverage and timing verification

All seven saved feature arrays start at **2022-12-01 00:00** and end at
**2025-12-31 21:55**, in the unknown source timezone. The December 2022 bars
initialize indicators only. Trading starts at 2023-01-01 inclusive and stops
before 2026-01-01. The runner reads the raw repository afresh and contains no
reuse of the old August 2023-start cache.

| Pair | 5-minute bars in January-June 2023 | First baseline entry, source time |
|---|---:|---|
| USDJPY | 37,426 | 2023-01-02 05:30 |
| EURUSD | 37,370 | 2023-01-02 04:15 |
| GBPUSD | 37,422 | 2023-01-01 23:25 |
| AUDUSD | 37,379 | 2023-01-05 02:00 |
| NZDUSD | 37,323 | 2023-01-05 04:05 |
| AUDJPY | 37,156 | 2023-01-03 18:15 |
| NZDJPY | 37,086 | 2023-01-02 05:30 |

Every pair/candidate has entries in the first half of 2023. All entry/exit
timestamps are inside the requested trade window and exit is not before entry.
The saved arrays lie on the five-minute grid. These checks do not classify every
missing clock minute as a true missing quote or authenticate the complete feed.

Source inspection confirms **one continuous simulation per pair/candidate**,
with no annual restart and no forced year/end liquidation. The 105 annual rows
group already-completed trades by exit-bar year. Counts, wins and P/L add back
to each continuous trace. No actual year-crossing position occurred in these
saved traces, so live year-cross behavior is established here by source flow,
not by observing a crossing trade in this sample.

## Independent checks

- Recomputed all **6,127 trade rows in 35 arrays** from side, entry, exit, pip
  size and the specified pair cost. Exact stored trade P/L match.
- Recomputed counts, wins, win rates, PF and net at pair, annual and total
  level; **105 annual rows and five aggregates** match within 1e-9 pips/
  floating-point tolerance. Recomputed pair and total +0.2-pip cost sensitivity.
- Recomputed terminal open marks from final close and diagnostic position state;
  all ending positions are flat and open P/L is zero, without forced closure.
- Independently reran **seven baseline cases** with `simulate_center(...,3.0)`;
  all nine trade columns and eleven baseline diagnostics exactly match.
- All recorded code hashes, seven feature/timestamp hashes and current raw
  Bars.dat size/mtime match. Size/mtime matching is not a full raw-file hash.

## Verified three-year totals

| Case | Trades | Wins | Net win rate | PF | Net pips | PF with +0.2 pips |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 4,213 | 2,945 | 69.90% | 0.9824 | -224.300 | 0.9180 |
| Directional close65 | 1,004 | 719 | 71.61% | 1.0153 | +42.395 | 0.9440 |
| Body50 + close65 | 539 | 391 | 72.54% | 1.1141 | +148.805 | 1.0307 |
| Body engulf | 115 | 85 | 73.91% | 1.4624 | +101.830 | 1.3482 |
| Previous-range reclaim | 256 | 181 | 70.70% | 0.8798 | -83.200 | 0.8100 |

## Findings and limitations

- **High, model interpretation:** The current advertised normal-session spreads
  are applied to *all* historical hours. Unknown source timezone prevents matching
  execution to the advertised Japanese-time session. These are optimistic fixed-
  cost scenarios, not observed 2023-2025 GMO execution or historical spreads.
  The main agent supplied/verified the official rate source; this independent
  audit verified the supplied constants and arithmetic, not the web page again.
- **Medium, inference:** All five previously fixed conditions are shown on user-
  requested dates without retuning or new adoption gates. This descriptive
  expansion does not erase the previous study's failed frequency/robustness
  gates. Engulf's 115 trades across seven pairs/three years remain limited;
  its 2023 PF is 1.0142 on 40 trades and net +1.23 pips, so the strongest full-
  period PF does not show a stable edge in every year.
- **Medium, omitted risks:** Stops remain disabled, swaps and variable spreads
  are omitted, and pips summed across pairs are research scores, not account-
  currency portfolio money. No SL rule, Pine setting or live account was changed.
- **Low, provenance:** The protocol is written before data load in the runner;
  source hashes are written at the end. Current hashes match, but this audit did
  not capture its own pre-run protocol/source hash before the report executed.

No material accounting or calendar-scope discrepancy was found. Hand off as a
**three-year fixed-condition descriptive result with the above limitations**;
no Pine adoption or live-trading authorization follows from this audit.
