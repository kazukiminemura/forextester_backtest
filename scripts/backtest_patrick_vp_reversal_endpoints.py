"""Replay Patrick's three-block reversal with exactly observed block endpoints."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import backtest_patrick_reverse_cost10_m15_reversal as original
from backtest_patrick_vp_value_migration import (
    CONTROL,
    MANIFEST,
    PERIODS,
    max_realized_drawdown_r,
    read_json,
    source_hashes,
)

base, reference, baseline, va = original.base, original.reference, original.baseline, original.va
EXPERIMENT = "patrick_vp_reversal_endpoints_20261118"
ROOT = baseline.ROOT
PROTOCOL = ROOT / "docs" / "quant_organization" / "experiments" / EXPERIMENT / "protocol.json"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
ENDPOINT_OFFSETS = np.array([-225, -151, -150, -76, -75, -1], dtype=np.int64) * 60


def validate_protocol():
    protocol = read_json(PROTOCOL)
    if (
        protocol.get("experiment_id") != EXPERIMENT
        or protocol.get("status") != "SPEC_FROZEN"
        or not protocol.get("frozen_at")
        or protocol.get("candidate_budget") != 1
        or protocol.get("symbols") != reference.SYMBOLS
    ):
        raise ValueError("Frozen reversal endpoint protocol required")
    frozen_sources = {
        "original_reversal_sha256": Path(original.__file__),
        "common_replay_sha256": Path(va.__file__),
    }
    for key, path in frozen_sources.items():
        if base.digest(path).lower() != protocol["code_identifier"][key].lower():
            raise ValueError(f"Source differs from frozen protocol: {path}")


def endpoint_decision(times, prices, index):
    """Return endpoint availability and the permitted direction at a fill."""
    stamps = times[index] + ENDPOINT_OFFSETS
    indexes = np.searchsorted(times, stamps)
    if not np.array_equal(times[indexes], stamps):
        return False, 0
    first, second, third = prices[indexes[1::2], 3] - prices[indexes[::2], 0]
    if first < 0 < second and third > 0:
        return True, 1
    if first > 0 > second and third < 0:
        return True, -1
    return True, 0


def fill_masks(times, prices, begin, end):
    endpoints = np.zeros(len(times), dtype=np.int8)
    reversal = np.zeros(len(times), dtype=np.int8)
    # Evaluation begins at UTC midnight. A JST weekday fill is at 23:15 UTC.
    openings = np.arange(begin + 23 * 3600 + 15 * 60, end, va.DAY, dtype=np.int64)
    openings = openings[((openings + 9 * 3600) // va.DAY + 3) % 7 < 5]
    indexes = np.searchsorted(times, openings)
    for index, opening in zip(indexes, openings, strict=True):
        if index == len(times) or times[index] != opening:
            continue
        available, side = endpoint_decision(times, prices, index)
        if available:
            endpoints[index] = 2
            reversal[index] = side
    return endpoints, reversal


def mask_diagnostics(times, prices, begin, end, endpoints, reversal):
    full, original_reversal = original.fill_masks(times, prices, begin, end)
    complete = full == 2
    if not np.all(endpoints[complete] == 2) or not np.array_equal(reversal[complete], original_reversal[complete]):
        raise ValueError("Endpoint mask differs from original reversal on a complete window")
    return dict(
        complete_windows=int(np.count_nonzero(complete)),
        endpoint_windows=int(np.count_nonzero(endpoints)),
        reversal_windows=int(np.count_nonzero(reversal)),
        complete_reversal_windows=int(np.count_nonzero(original_reversal)),
    )


def main():
    validate_protocol()
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    repository = base.HistoryRepository()
    history = source_hashes(repository, read_json(MANIFEST)["manifest"])
    bounds = {label: tuple(map(base.stamp, span)) for label, span in PERIODS.items()}
    start = base.stamp(baseline.STAGE_DATES["load_start"])
    begin = bounds["2017-2025"][0]
    end = bounds["2026_extra"][1]
    terminal = base.stamp("2026-08-31")
    parts, summary, ledger_hashes, control_hashes, replay_counts = {}, [], {}, {}, []
    diagnostics = {}
    with TemporaryDirectory(prefix=EXPERIMENT + "_", dir=OUTPUT.parent) as temp:
        output = Path(temp) / "result"
        output.mkdir()
        for symbol in reference.SYMBOLS:
            times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
            setups, profiles, first_week, ready, _ = reference.features(times, prices, volume)
            allowed = np.ones(len(times), dtype=np.bool_)
            endpoints, reversal = fill_masks(times, prices, begin, end)
            diagnostics[symbol] = mask_diagnostics(times, prices, begin, end, endpoints, reversal)
            pip = .01 if symbol.endswith("JPY") else .0001
            for stress, scenario in ((False, "normal"), (True, "stress")):
                args = (times, prices, setups, profiles, first_week, ready, begin, end,
                        pip, stress, allowed, True, 10., True, None, 7)
                for mode, mask in (("control", None), ("endpoint_control", endpoints), ("reversal", reversal)):
                    ledger, counts = va.replay(*args, fill_side_mask=mask)
                    if counts[0] != counts[1] or counts[2] or np.any(ledger[:, 10] <= 0):
                        raise ValueError(f"Incomplete replay or nonpositive capital: {symbol}/{scenario}/{mode}")
                    entries = ledger[:, 0].astype(np.int64)
                    if not np.all(entries % va.DAY == 23 * 3600 + 15 * 60):
                        raise ValueError(f"Entry outside scheduled fill: {symbol}/{scenario}/{mode}")
                    if mode == "control":
                        previous = CONTROL / f"{symbol}_{scenario}_small_pullback.npy"
                        np.testing.assert_array_equal(ledger, np.load(previous, allow_pickle=False))
                        control_hashes[previous.name] = base.digest(previous)
                    else:
                        expected = 2 if mode == "endpoint_control" else ledger[:, 2]
                        if not np.all(mask[np.searchsorted(times, entries)] == expected):
                            raise ValueError(f"Entry contradicts endpoint mask: {symbol}/{scenario}/{mode}")
                    filename = f"{symbol}_{scenario}_{mode}.npy"
                    np.save(output / filename, ledger, allow_pickle=False)
                    ledger_hashes[filename] = base.digest(output / filename)
                    replay_counts.append(dict(symbol=symbol, scenario=scenario, mode=mode,
                                              entries=int(counts[0]), closed=int(counts[1]),
                                              unresolved=int(counts[2]), pending=int(counts[3])))
                    for period, (left, right) in bounds.items():
                        part = ledger[(entries >= left) & (entries < right)]
                        parts.setdefault((mode, scenario, period), []).append(part)
                        summary.append(dict(symbol=symbol, mode=mode, scenario=scenario, period=period,
                                            **reference.metrics(part), max_realized_drawdown_r=max_realized_drawdown_r(part)))
            print(f"{symbol}: {len(times):,} M1", flush=True)

        pooled = [
            dict(mode=mode, scenario=scenario, period=period, **baseline.pooled_metrics(ledgers),
                 active_symbols=sum(bool(len(ledger)) for ledger in ledgers),
                 positive_symbols=sum(int(ledger[:, 7].sum() > 0) for ledger in ledgers))
            for (mode, scenario, period), ledgers in parts.items()
        ]
        result = dict(
            experiment_id=EXPERIMENT, periods=PERIODS, manifest=history, mask_diagnostics=diagnostics,
            reference_manifest_sha256=base.digest(MANIFEST),
            protocol_sha256=base.digest(PROTOCOL),
            runner_sha256=base.digest(Path(__file__)),
            replay_sha256=base.digest(Path(va.__file__)),
            features_sha256=base.digest(Path(reference.__file__)),
            profile_sha256=base.digest(Path(base.__file__)),
            original_reversal_sha256=base.digest(Path(original.__file__)),
            control_ledger_sha256=control_hashes,
            ledger_sha256=ledger_hashes,
            replay_counts=replay_counts,
            pooled=pooled,
        )
        base.write_csv(output / "summary.csv", summary)
        base.write_csv(output / "pooled.csv", pooled)
        (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        output.rename(OUTPUT)
    print("RESULT_JSON " + json.dumps(pooled), flush=True)


if __name__ == "__main__":
    main()
