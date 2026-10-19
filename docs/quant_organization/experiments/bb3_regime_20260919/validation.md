# BB context regime research handoff

- Experiment: `bb3_regime_20260919`; research owner to independent auditor.
- Result: `REJECTED_DESCRIPTIVE`; eligible variants: none.
- No Pine modification, orders, external account connection, commit or push.

## Frozen scope and evidence

Six fixed filters plus two baselines, all shared across seven symbols.
Confirmed complete H1 trend, M5 relative ATR, or both; currentBB and body-engulf
each serve as their matching baseline. No tuning or fallback after results.
Continuous2023-01-01 through2026-01-01 exclusive, warmup from2022-12-01.
Annual results group closed trades by exit bar year; positions do not restart
at January boundaries. All dates are previously viewed, explicitly descriptive.

Raw Bars.dat sizes/mtime and saved feature SHA256 matched the prior GMO report.
Exact source hash, copied protocol and data provenance are saved before outcome
calculation. Complete H1 means all12 aligned M5 opens; this cannot establish
underlying M1 completeness. Stale H1 at age>=3600seconds rejects trend filters.

## Commands

```powershell
python -m pytest tests/test_bb3_regime.py -q
python -m scripts.research_bb3_regime
```

Tests30 passed, exit0. Runner exit0,9.74sec, terminal emitted:
`RESULT_JSON=C:\Users\minemura\projects\forextester_backtest\agent_runs\bb3_regime_20260919\results.json`.
Initial development tests caught an invalid test-module import and Numba mixed
int/float tuple assignment; both corrected before any empirical outcomes.

Reproduce safely without overwriting prior output:

```powershell
python -m scripts.research_bb3_regime --output agent_runs/bb3_regime_20260919/reproduction
```

## Continuous descriptive results: quoted normal-session cost assumptions

|Variant|Closed|Win rate|PF|Net pips|
|---|---:|---:|---:|---:|
|CurrentBB baseline|4213|69.903%|0.9824|-224.300|
|CurrentBB+H1 trend|2958|69.439%|1.0024|21.375|
|CurrentBB+volatility|3987|69.325%|0.9432|-701.300|
|CurrentBB+both|2803|68.783%|0.9612|-329.395|
|Body-engulf baseline|115|73.913%|1.4624|101.830|
|Body-engulf+H1 trend|79|74.684%|1.2436|46.190|
|Body-engulf+volatility|111|73.874%|1.4852|102.210|
|Body-engulf+both|77|75.325%|1.2885|51.925|

Highest observed win rate75.325% is only1.412 percentage points above its
matching engulf baseline, below the predeclared2-point gain. Its77 trades fall
below100, PF/net deteriorate and2023/2024 are loss-making. The volatility-only
engulf variant slightly raises PF but lowers win rate and loses money in2023.
All six filters fail the frozen improvement gates; none establishes improvement
under both costs and every-year checks. Full per-symbol, cost and year figures
and every boolean gate are in results.json; no aggregate win rate is a forecast.

## Verified locally, pending independent audit

-30 tests cover exact H1 completion/availability, missing/misaligned hours,
  stale-hour age boundary, SMA slope, ATR seed and lag100 denominator, nan
  warmup, inclusive thresholds, future perturbations/prefixes, direction
  symmetry, cancellation/no same-bar rearm and newly available later setups.
-28 baseline runs match all prior shape-trade fields and12 diagnostic fields;
 14 normal-cost baseline outputs also match prior saved GMO report artifacts.
-Both costs use identical entry/exit geometry, with per-symbol normal spreads
 and normal+0.2pips stress. Saved arrays cover112 full trade/diagnostic cases.
-7 full features/times/regime/hourly caches include hashes and provenance.
-Source owner does not approve adoption; independent audit owns its conclusion.

Normal GMO spread assumptions applied all hours are not actual historical
spreads. Timestamp timezone is unknown, swap is omitted, and stop remains OFF
with moving-center full exits, not a fixed RR strategy. Equal-pip totals are not
account-currency portfolio returns. Pine should remain unchanged after rejection.
