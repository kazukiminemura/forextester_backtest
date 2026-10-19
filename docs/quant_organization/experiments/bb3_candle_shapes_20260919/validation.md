# Research handoff: candle-shape BB study

- Experiment: `bb3_candle_shapes_20260919`
- Owner: quant research. Next: independent validator/auditor, then director.
- Research status: `REJECTED_TRAINING_ONLY`; candidate selected: none.
- No live orders, account connection, Pine change, commit or push.

## Frozen inputs and scope

`protocol.json` and `hypothesis.md` were saved before candidate outcomes.
The runner saves exact protocol, source SHA256 and unchanged raw-file stats.
Eight symbols: USDJPY, EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, AUDJPY, NZDJPY.
USDCHF/EURJPY/GBPJPY are excluded for prior data-quality concerns.
Training is 2023-09-08 inclusive to 2024-09-08 exclusive, source-local timestamps.
Features warm from August2023; simulation starts flat at each period boundary.
This partition therefore differs from the previously reported continuous
three-year total. Later periods are previously viewed, not untouched holdout.

Only four fixed entry-shape filters were compared with baseline; no tuning.
Existing stop-OFF moving-center full exit is retained, not claimed as fixed RR1.

## Commands and completion evidence

```powershell
python -m pytest tests/test_bb3_candle_shapes.py -q
python -m scripts.research_bb3_candle_shapes
```

Both exit0; tests27 passed. Runner completed and emitted
`RESULT_JSON=C:\Users\minemura\projects\forextester_backtest\agent_runs\bb3_candle_shapes_20260919\results.json`.
Broader behavioral suite (new shapes, old center5, old timing) produced49 passes
and1 pre-existing stale Pine contract failure: old
`test_current_pine_contract_and_fixed_cutoff_protocol` expects default5pips,
whereas the user subsequently changed the live source to3pips. No unrelated
Pine or legacy test was modified. With only that stale contract deselected,
all49 behavioral tests passed (one deselected).
To independently repeat without overwriting evidence:

```powershell
python -m scripts.research_bb3_candle_shapes --output agent_runs/bb3_candle_shapes_20260919/reproduction
```

## Training outcomes after fixed1.4 pips round-trip cost

|Rule|Decisions closed|Net wins|Win rate|PF|Net pips|
|---|---:|---:|---:|---:|---:|
|Baseline|1468|970|66.0763%|0.7523|-1045.645|
|Directional body and close location >=65%|310|205|66.1290%|0.6485|-327.195|
|Above plus body/range >=50%|173|118|68.2081%|0.5989|-203.990|
|Opposite previous body engulfed|33|24|72.7273%|1.1485|7.405|
|Previous full range reclaimed|72|51|70.8333%|1.0291|3.965|

All candidates fail the precommitted frequency gate (at least30% of1468,
therefore at least441 closed trades). The two filters that exceeded70% are
sparse training observations, not established win probabilities.
At2.0 pips total cost engulf becomes66.67%/PF0.7789/-12.395 pips and range
reclaim becomes68.06%/PF0.7371/-39.235 pips. They also fail stress profitability
and pair breadth (4/8 and3/8 positive). No candidate proceeds to validation
or final confirmation; no fallback or threshold adjustment was performed.

## Checks and artifacts

- `scripts/research_bb3_candle_shapes.py`: separate candle predicate, replay,
  data loader, aggregation and gates. Stateful cancellation, not post-filtering.
- `tests/test_bb3_candle_shapes.py`: exact threshold and opposite/doji/zero-range
  tests, BUY/SELL symmetry, failed setup no same-bar rearm/no waiting, fresh
  later setup with changed occupancy, next available open gaps, source feature
  prefix and trade prefix causality, no forced close, both-cost geometry.
- Runner verifies16 baseline executions (8 pairs x2 costs) reproduce all old
  trade values and first11 diagnostics exactly against `simulate_center(...,3)`.
- `agent_runs/bb3_candle_shapes_20260919/`: results, protocol, source hashes,
  data manifest,8 saved feature arrays,80 per-candidate/cost/pair trade arrays.
- Six pairs reuse raw-stat-matching prior caches; AUDJPY/NZDJPY are fresh-loaded.
- End cutoff is exclusive2026-08-31 for all stored features, before known
  anomalous GBPJPY episode (that pair also excluded).

Independent audit is still required. Research owner does not approve adoption.
Equal-pip aggregate is not account-currency profit, omitted swap and stop-OFF
exposure remain material. Baseline/first two filters' maximum observed holding
time is49h; most profitable-looking sparse subsets still cannot support adoption.
