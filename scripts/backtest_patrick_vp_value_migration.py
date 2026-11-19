"""Replay one fixed Patrick VP weekly value-area migration filter."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import backtest_patrick_reverse_cost10_inside_va as va

base, reference, baseline = va.base, va.reference, va.baseline
EXPERIMENT = "patrick_vp_value_migration_20261118"
ROOT = baseline.ROOT
PROTOCOL = ROOT / "docs" / "quant_organization" / "experiments" / EXPERIMENT / "protocol.json"
OUTPUT = ROOT / "agent_runs" / EXPERIMENT
CONTROL = ROOT / "agent_runs" / "patrick_cost10_va_preentry_shape"
MANIFEST = baseline.PREVIOUS / "result.json"
FILL_DELAY = 15 * 60
PERIODS = {
    "2017-2019": ("2017-01-01", "2020-01-01"),
    "2020-2022": ("2020-01-01", "2023-01-01"),
    "2023-2025": ("2023-01-01", "2026-01-01"),
    "2017-2025": ("2017-01-01", "2026-01-01"),
    "2026_extra": ("2026-01-05", "2026-08-28"),
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol():
    protocol = read_json(PROTOCOL)
    if (
        protocol.get("experiment_id") != EXPERIMENT
        or protocol.get("status") != "SPEC_FROZEN"
        or not protocol.get("frozen_at")
        or protocol.get("candidate_budget") != 1
        or protocol.get("symbols") != reference.SYMBOLS
    ):
        raise ValueError("Frozen Patrick VP experiment protocol required")
    frozen_sources = {
        "common_replay_sha256": Path(va.__file__),
        "h4_and_profile_features_sha256": Path(reference.__file__),
    }
    for key, path in frozen_sources.items():
        if base.digest(path).lower() != protocol["code_identifier"][key].lower():
            raise ValueError(f"Source differs from frozen protocol: {path}")


def migration_side_mask(times, profiles, first_week):
    """Select the direction of the last two completed UTC week VA midpoints."""
    eligible = np.zeros(len(times), dtype=np.int8)
    # At a fill minute, the cutoff concerns the UTC week at decision time.
    week_starts = first_week + np.arange(len(profiles) + 1, dtype=np.int64) * va.WEEK
    indices = np.searchsorted(times, week_starts + FILL_DELAY, side="left")
    for week in range(2, len(profiles)):
        prior = profiles[week - 2:week]
        if not np.isfinite(prior).all() or not np.all(prior[:, 0] > prior[:, 1]):
            continue
        older, newer = prior.mean(axis=1)
        side = int(newer > older) - int(newer < older)
        eligible[indices[week]:indices[week + 1]] = side
    return eligible


def max_realized_drawdown_r(ledger):
    curve = np.concatenate(([0.0], np.cumsum(ledger[:, 7])))
    return float((np.maximum.accumulate(curve) - curve).max())


def source_hashes(repository, manifest):
    paths = (("Bars.dat", "bars_sha256"), ("info.dat", "info_sha256"))
    actual = {}
    for symbol in reference.SYMBOLS:
        actual[symbol] = {}
        for filename, key in paths:
            digest = base.digest(repository.root / symbol / filename)
            if digest != manifest[symbol][key]:
                raise ValueError(f"Source changed: {symbol}/{filename}")
            actual[symbol][key] = digest
    return actual


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
    with TemporaryDirectory(prefix=EXPERIMENT + "_", dir=OUTPUT.parent) as temp:
        output = Path(temp) / "result"
        output.mkdir()
        for symbol in reference.SYMBOLS:
            times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
            setups, profiles, first_week, ready, _ = reference.features(times, prices, volume)
            allowed = np.ones(len(times), dtype=np.bool_)
            mask = migration_side_mask(times, profiles, first_week)
            pip = .01 if symbol.endswith("JPY") else .0001
            for stress, scenario in ((False, "normal"), (True, "stress")):
                args = (times, prices, setups, profiles, first_week, ready, begin, end,
                        pip, stress, allowed, True, 10., True, None, 7)
                for mode, fill_mask in (("control", None), ("migration", mask)):
                    ledger, counts = va.replay(*args, fill_side_mask=fill_mask)
                    if counts[0] != counts[1] or counts[2] or np.any(ledger[:, 10] <= 0):
                        raise ValueError(f"Incomplete replay or nonpositive capital: {symbol}/{scenario}/{mode}")
                    entries = ledger[:, 0].astype(np.int64)
                    if mode == "control":
                        previous = CONTROL / f"{symbol}_{scenario}_small_pullback.npy"
                        np.testing.assert_array_equal(ledger, np.load(previous, allow_pickle=False))
                        control_hashes[previous.name] = base.digest(previous)
                    elif not np.array_equal(mask[np.searchsorted(times, entries)], ledger[:, 2]):
                        raise ValueError(f"VA migration side mismatch: {symbol}/{scenario}")
                    filename = f"{symbol}_{scenario}_{mode}.npy"
                    np.save(output / filename, ledger, allow_pickle=False)
                    ledger_hashes[filename] = base.digest(output / filename)
                    replay_counts.append(dict(symbol=symbol, scenario=scenario, mode=mode,
                                              entries=int(counts[0]), closed=int(counts[1]),
                                              unresolved=int(counts[2]), pending=int(counts[3]),
                                              decisions=int(counts[4]), selections=int(counts[5]),
                                              missing_active=int(counts[6])))
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
            experiment_id=EXPERIMENT,
            periods=PERIODS,
            load_start=baseline.STAGE_DATES["load_start"],
            entry_end="2026-08-28",
            terminal="2026-08-31",
            manifest=history,
            reference_manifest_sha256=base.digest(MANIFEST),
            protocol_sha256=base.digest(PROTOCOL),
            runner_sha256=base.digest(Path(__file__)),
            replay_sha256=base.digest(Path(va.__file__)),
            features_sha256=base.digest(Path(reference.__file__)),
            profile_sha256=base.digest(Path(base.__file__)),
            control_ledger_sha256=control_hashes,
            ledger_sha256=ledger_hashes,
            replay_counts=replay_counts,
            pooled=pooled,
        )
        base.write_csv(output / "summary.csv", summary)
        base.write_csv(output / "pooled.csv", pooled)
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        output.rename(OUTPUT)
    print("RESULT_JSON " + json.dumps(pooled), flush=True)


if __name__ == "__main__":
    main()
