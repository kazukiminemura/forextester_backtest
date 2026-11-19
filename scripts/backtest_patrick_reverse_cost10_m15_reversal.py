"""Compare Patrick K10 small-pullback with a fixed 15-M15 reversal at fill."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from numba import njit

import backtest_patrick_reverse_cost10_inside_va as va

base, reference, baseline = va.base, va.reference, va.baseline
DAY = va.DAY
EXPERIMENT = "patrick_cost10_m15_reversal"
PROTOCOL = baseline.ROOT / "docs/quant_organization/experiments" / EXPERIMENT / "protocol.json"
OUT = baseline.ROOT / "agent_runs" / EXPERIMENT
PRIOR = baseline.ROOT / "agent_runs/patrick_cost10_va_preentry_shape"


@njit(cache=True)
def complete_window(times, i):
    if i < 225 or times[i] % 900 != 0:
        return False
    first = i - 225
    for minute in range(first, i):
        if times[minute] != times[i] - (i - minute) * 60:
            return False
    return True


@njit(cache=True)
def reversal_side(times, prices, i):
    """Return the side of a -,+,+ pattern across three closed 75-minute blocks."""
    if not complete_window(times, i):
        return 0
    first = i - 225
    # Each block is five completed M15 candles. Use the first open and last close.
    first_move = prices[first + 74, 3] - prices[first, 0]
    second_move = prices[first + 149, 3] - prices[first + 75, 0]
    third_move = prices[i - 1, 3] - prices[i - 75, 0]
    if first_move < 0 < second_move and third_move > 0:
        return 1
    if first_move > 0 > second_move and third_move < 0:
        return -1
    return 0


def fill_masks(times, prices, begin, end):
    # 08:15 JST is 23:15 UTC on the preceding calendar day.
    openings = np.arange(begin + 23 * 3600 + 15 * 60, end, DAY, dtype=np.int64)
    weekdays = ((openings + 9 * 3600) // DAY + 3) % 7
    openings = openings[weekdays < 5]
    indexes = np.searchsorted(times, openings)
    indexes = indexes[(indexes < len(times)) & (times[np.minimum(indexes, len(times) - 1)] == openings)]
    full = np.zeros(len(times), dtype=np.int8)
    directional = np.zeros(len(times), dtype=np.int8)
    for i in indexes:
        if complete_window(times, i):
            full[i] = 2
            directional[i] = reversal_side(times, prices, i)
    return full, directional


def overlap(control, candidate):
    columns = [0, 2, 13, 14]  # Entry time, side, profile week, setup start.
    control_keys = set(map(tuple, control[:, columns]))
    candidate_keys = set(map(tuple, candidate[:, columns]))
    new_times = len(set(candidate[:, 0]) - set(control[:, 0]))
    return dict(shared_trade_keys=len(control_keys & candidate_keys),
                new_trade_keys=len(candidate_keys - control_keys),
                dropped_trade_keys=len(control_keys - candidate_keys), new_entry_times=new_times)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8-sig"))
    if (protocol["experiment_id"] != EXPERIMENT or protocol["status"] != "FROZEN_DESCRIPTIVE_REPLAY"
            or protocol["candidate_budget"] != 1 or protocol["symbols"] != reference.SYMBOLS
            or not protocol["frozen_at"] or not protocol["diagnostic_control"]):
        raise ValueError("Frozen protocol and full-window attribution control required")
    dates = baseline.STAGE_DATES
    start, begin = (base.stamp(dates[key]) for key in ("load_start", "evaluation_entry_start"))
    end, terminal = map(base.stamp, ("2026-08-28", "2026-08-31"))
    periods = [*baseline.PERIODS, ("all", "2017-01-01", "2026-01-01"),
               ("2026_extra", "2026-01-05", "2026-08-28")]
    period_stamps = [(label, base.stamp(left), base.stamp(right)) for label, left, right in periods]
    source_path = baseline.PREVIOUS / "result.json"
    source_manifest = json.loads(source_path.read_text(encoding="utf-8-sig"))["manifest"]
    repository = base.HistoryRepository()
    OUT.mkdir(parents=True, exist_ok=False)
    manifest, ledger_sha256, parts, summary, comparisons, overlaps = {}, {}, {}, [], [], []
    for symbol in reference.SYMBOLS:
        started = time.perf_counter()
        hashes = dict(bars_sha256=base.digest(repository.root / symbol / "Bars.dat"),
                      info_sha256=base.digest(repository.root / symbol / "info.dat"))
        if any(value != source_manifest[symbol][key] for key, value in hashes.items()):
            raise ValueError(f"Source differs from prior manifest: {symbol}")
        times, prices, volume = base.load_minutes(repository, symbol, start, terminal)
        setups, profiles, first_week, ready, quality = reference.features(times, prices, volume)
        manifest[symbol] = dict(**hashes, observed_first=base.iso(times[0]), observed_last=base.iso(times[-1]),
                                m1_rows=len(times), **quality)
        pip = .01 if symbol.endswith("JPY") else .0001
        allowed = np.ones(len(times), dtype=np.bool_)
        full, directional = fill_masks(times, prices, begin, end)
        for stress in (False, True):
            scenario = "stress" if stress else "normal"
            control_parts = {}
            for name, mask in (("baseline", None), ("full_window", full), ("m15_reversal", directional)):
                ledger, stats = va.replay(times, prices, setups, profiles, first_week, ready,
                                          begin, end, pip, stress, allowed, True, 10., True, None, 7,
                                          fill_side_mask=mask)
                if stats[0] != stats[1] or stats[2] or np.any(ledger[:, 10] <= 0):
                    raise ValueError(f"Unresolved entries or invalid equity: {symbol}/{scenario}/{name}")
                entries = ledger[:, 0].astype(np.int64)
                if np.any((entries + 9 * 3600) % DAY != 8 * 3600 + 15 * 60):
                    raise ValueError(f"Trade outside the exact 08:15 fill: {symbol}/{scenario}/{name}")
                if name == "baseline":
                    prior_path = PRIOR / f"{symbol}_{scenario}_small_pullback.npy"
                    np.testing.assert_array_equal(ledger, np.load(prior_path, allow_pickle=False),
                                                  err_msg=f"Baseline differs from {prior_path}")
                    comparisons.append(dict(symbol=symbol, scenario=scenario, source=prior_path.name,
                                            source_sha256=base.digest(prior_path), rows=len(ledger),
                                            columns=17, matches=True))
                else:
                    indexes = np.searchsorted(times, entries)
                    permitted = mask[indexes]
                    expected = 2 if name == "full_window" else ledger[:, 2]
                    if not np.all(permitted == expected):
                        raise ValueError(f"Trade fails mask: {symbol}/{scenario}/{name}")
                path = OUT / f"{symbol}_{scenario}_{name}.npy"
                np.save(path, ledger, allow_pickle=False)
                ledger_sha256[path.name] = base.digest(path)
                for label, left, right in period_stamps:
                    part = ledger[(entries >= left) & (entries < right)]
                    parts.setdefault((name, scenario, label), []).append(part)
                    summary.append(dict(symbol=symbol, filter=name, scenario=scenario,
                                        period=label, **reference.metrics(part)))
                    if name == "baseline":
                        control_parts[label] = part
                    else:
                        overlaps.append(dict(symbol=symbol, filter=name, scenario=scenario, period=label,
                                             **overlap(control_parts[label], part)))
        print(json.dumps(dict(symbol=symbol, m1=len(times), seconds=round(time.perf_counter() - started, 2))),
              flush=True)

    pooled = [dict(filter=name, scenario=scenario, period=label, pairs_with_trades=sum(bool(len(rows)) for rows in ledgers),
                   **baseline.pooled_metrics(ledgers))
              for (name, scenario, label), ledgers in parts.items()]
    evidence = dict(experiment_id=EXPERIMENT, status="COMPLETED_DESCRIPTIVE",
                    runner_sha256=base.digest(Path(__file__)), replay_sha256=base.digest(Path(va.__file__)),
                    protocol_sha256=base.digest(PROTOCOL), source_result_sha256=base.digest(source_path),
                    manifest=manifest, ledger_sha256=ledger_sha256, comparisons=comparisons,
                    summary=summary, pooled=pooled, overlaps=overlaps)
    base.write_csv(OUT / "summary.csv", summary)
    base.write_csv(OUT / "pooled.csv", pooled)
    base.write_csv(OUT / "comparisons.csv", comparisons)
    base.write_csv(OUT / "overlap.csv", overlaps)
    (OUT / "result.json").write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("RESULT_JSON " + json.dumps([row for row in pooled if row["period"] in ("all", "2026_extra")]),
          flush=True)


if __name__ == "__main__":
    main()

