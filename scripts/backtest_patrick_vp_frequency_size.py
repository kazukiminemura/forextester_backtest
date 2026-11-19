"""Apply the frozen Patrick reversal size rule to every original entry."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import backtest_patrick_vp_reversal_endpoints as endpoints
from backtest_patrick_vp_value_migration import CONTROL, MANIFEST, PERIODS, read_json, source_hashes

base, reference, va = endpoints.base, endpoints.reference, endpoints.va
EXPERIMENT = "patrick_vp_frequency_exits_20261118"
PROTOCOL = endpoints.ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
OUTPUT = endpoints.ROOT / "agent_runs" / (EXPERIMENT + "_sizing")
HISTORICAL_BLOCKS = ("2017-2019", "2020-2022", "2023-2025")


def trade_stats(rows):
    original = np.array([r["original_r"] for r in rows])
    sizes = np.array([r["size"] for r in rows])
    scaled = original * sizes

    def profit_factor(values):
        losses = -values[values < 0].sum()
        return float(values[values > 0].sum() / losses) if losses else None

    return dict(
        trades=len(rows), full_size=int((sizes == 1).sum()), half_size=int((sizes == 0.5).sum()),
        mean_size=float(sizes.mean()) if len(rows) else None,
        control_pf=profit_factor(original), scaled_pf=profit_factor(scaled),
        own_risk_pf=profit_factor(original), win_rate=float((scaled > 0).mean()) if len(rows) else None,
        control_net_r=float(original.sum()), scaled_net_r=float(scaled.sum()),
        mean_scaled_r=float(scaled.mean()) if len(rows) else None,
    )


def summarize(records, periods):
    pooled, per_symbol = [], []
    for period, (start, end) in periods.items():
        left, right = base.stamp(start), base.stamp(end)
        for cost in ("normal", "stress"):
            selected = [r for r in records if r["cost"] == cost and left <= r["entry_utc"] < right]
            totals = dict(period=period, cost=cost, **trade_stats(selected))
            positive = 0
            for symbol in reference.SYMBOLS:
                trades = [r for r in selected if r["symbol"] == symbol]
                by_symbol = trade_stats(trades)
                curve = np.cumsum([0.0, *(r["scaled_r"] for r in trades)])
                per_symbol.append(dict(period=period, cost=cost, symbol=symbol, **by_symbol,
                                       max_closed_dd_r=float((np.maximum.accumulate(curve) - curve).max())))
                positive += by_symbol["scaled_net_r"] > 0
            pooled.append(dict(**totals, positive_pairs=positive))
    return pooled, per_symbol


def sized_entries(symbol, cost, ledger, times, prices):
    entry_times = ledger[:, 0].astype(np.int64)
    indices = np.searchsorted(times, entry_times)
    np.testing.assert_array_equal(times[indices], entry_times)
    records = []
    for row, index in zip(ledger, indices, strict=True):
        observed, direction = endpoints.endpoint_decision(times, prices, index)
        side = int(row[2])
        size = 1.0 if direction == side else 0.5
        records.append(dict(symbol=symbol, cost=cost, entry_utc=int(row[0]), exit_utc=int(row[1]),
                            side=side, entry=float(row[3]), setup=int(row[14]), va_week=int(row[13]),
                            six_observed=observed, pattern=direction, size=size,
                            original_r=float(row[7]), scaled_r=float(row[7]) * size))
    return records


def evaluate(repository, earlier, known_ledgers):
    rows = []
    periods = {"2010-2016": ("2010-01-01", "2017-01-01")} if earlier else PERIODS
    start = base.stamp("2009-10-01" if earlier else "2016-12-20")
    terminal = base.stamp("2017-01-05" if earlier else "2026-08-31")
    for symbol in reference.SYMBOLS:
        times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
        if earlier:
            setups, profiles, first_week, ready, _ = reference.features(times, prices, volume)
            unrestricted = np.ones(len(times), dtype=np.bool_)
        for stress, cost in ((False, "normal"), (True, "stress")):
            if earlier:
                pip = .01 if symbol.endswith("JPY") else .0001
                ledger, counts = va.replay(
                    times, prices, setups, profiles, first_week, ready,
                    base.stamp("2010-01-01"), base.stamp("2017-01-01"), pip, stress,
                    unrestricted, True, 10.0, True, None, 7,
                )
                if counts[0] != counts[1] or counts[2] or np.any(ledger[:, 10] <= 0):
                    raise ValueError(f"Invalid earlier control: {symbol}/{cost}")
            else:
                source = CONTROL / f"{symbol}_{cost}_small_pullback.npy"
                if base.digest(source) != known_ledgers[source.name]:
                    raise ValueError(f"Changed control: {source}")
                ledger = np.load(source, allow_pickle=False)
            rows.extend(sized_entries(symbol, cost, ledger, times, prices))
    pooled, per_symbol = summarize(rows, periods)
    return rows, pooled, per_symbol


def main():
    protocol = read_json(PROTOCOL)
    if (protocol["status"] != "SPEC_FROZEN" or protocol["experiment_id"] != EXPERIMENT
            or protocol["additional_sizing_candidate_budget"] != 1 or protocol["symbols"] != reference.SYMBOLS):
        raise ValueError("Frozen four-arm protocol required")
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    repository = base.HistoryRepository()
    source = source_hashes(repository, read_json(MANIFEST)["manifest"])
    previous = endpoints.OUTPUT / "result.json"
    known_ledgers = read_json(previous)["control_ledger_sha256"]
    rows, pooled, per_symbol = evaluate(repository, False, known_ledgers)
    history = [r for r in pooled if r["period"] in HISTORICAL_BLOCKS]
    passes = sum(r["scaled_pf"] > r["control_pf"] for r in history)
    if passes == len(HISTORICAL_BLOCKS) * 2:
        earlier_rows, earlier_pooled, earlier_symbols = evaluate(repository, True, known_ledgers)
        rows.extend(earlier_rows)
        pooled.extend(earlier_pooled)
        per_symbol.extend(earlier_symbols)
    with TemporaryDirectory(dir=OUTPUT.parent) as temp:
        out = Path(temp) / "result"
        out.mkdir()
        base.write_csv(out / "trades.csv", rows)
        base.write_csv(out / "pooled.csv", pooled)
        base.write_csv(out / "by_symbol.csv", per_symbol)
        result = dict(pf_improvement_cells=passes, matched_control_sha256=known_ledgers,
                      protocol_sha256=base.digest(PROTOCOL), runner_sha256=base.digest(Path(__file__)),
                      endpoint_logic_sha256=base.digest(Path(endpoints.__file__)),
                      baseline_manifest_sha256=base.digest(previous), raw_manifest=source, pooled=pooled)
        (out / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        out.rename(OUTPUT)
    print("RESULT_JSON " + json.dumps(dict(pf_improvement_cells=passes, pooled=pooled)))


if __name__ == "__main__":
    main()
