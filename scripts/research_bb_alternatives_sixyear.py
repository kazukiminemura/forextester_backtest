"""Fixed 2020-2025 extension; existing signal and fill logic is imported unchanged."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

from forextester_backtest import HistoryRepository
# Numba's existing cache names this module by its package-qualified import.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.research_bb3_context_timing import EPOCH, features, timestamp
from research_bb3_jev_engine import CACHE, ROOT, candidates
from research_bb3_jev_refine import add_curve, file_hash, totals_for, write_json, write_progress
from research_bb_alternatives import COSTS, POLICIES, arm_name, bands, execute, reentry_signals, wm_signals

ID = "bb_alternatives_2020_2025_20260925"
DOC = ROOT / "docs/quant_organization/experiments" / ID
OUT = ROOT / "agent_runs" / ID
OLD = ROOT / "agent_runs/bb_alternatives_20260925"
INDEX_FIELDS = ("index", "prep_index", "confirmed_index", "first", "second", "confirmed", "entry_index", "exit_index")


def periods():
    return {"all": (timestamp("2020-01-01"), timestamp("2026-01-01")),
            **{str(y): (timestamp(f"{y}-01-01"), timestamp(f"{y+1}-01-01")) for y in range(2020, 2026)},
            "overlap": (timestamp("2023-01-01"), timestamp("2026-01-01"))}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def source_stat(path):
    s = path.stat()
    return {"bytes": s.st_size, "mtime_ns": s.st_mtime_ns}


def signals_for(f, times, pip, tick, start):
    bb = bands(f[:, 3])
    raw = dict(original=candidates(f, times, pip, tick),
               bb2_reentry=reentry_signals(f, times, bb, tick), wm=wm_signals(f, times, bb, tick))
    return {p: [s for s in ss if start <= times[s["index"]] < timestamp("2026-01-01")]
            for p, ss in raw.items()}


def normalize_indices(items, times):
    return [{k: int(times[v]) if k in INDEX_FIELDS else v for k, v in item.items()} for item in items]


def prepare(protocol, out):
    repo, data, manifest = HistoryRepository(protocol["history_directory"]), {}, []
    for symbol in protocol["symbols"]:
        write_progress(out, "preparing", f"2019年12月から履歴作成・重複照合: {symbol}", completed_jobs=0, total_jobs=336)
        raw = repo.root / symbol / "Bars.dat"
        before, raw_sha = source_stat(raw), digest(raw)
        bars = list(repo.bars(symbol, datetime(2019, 12, 1), datetime(2026, 1, 1)-timedelta(microseconds=1), "5m"))
        times = np.array([int((b.time-EPOCH).total_seconds()) for b in bars], dtype=np.int64)
        ohlc = np.array([(b.open, b.high, b.low, b.close) for b in bars])
        del bars
        if source_stat(raw) != before:
            raise RuntimeError(f"Source changed during read: {symbol}")
        if not (len(times) and times[0] < timestamp("2020-01-01") and times[-1] >= timestamp("2025-12-30")
                and np.all(np.diff(times) > 0) and np.isfinite(ohlc).all() and np.all(ohlc > 0)
                and np.all(ohlc[:, 1] >= np.maximum(ohlc[:, 0], ohlc[:, 3]))
                and np.all(ohlc[:, 2] <= np.minimum(ohlc[:, 0], ohlc[:, 3]))):
            raise ValueError(f"Invalid source coverage/OHLC: {symbol}")
        annual = {str(y): int(np.sum((times >= timestamp(f"{y}-01-01")) & (times < timestamp(f"{y+1}-01-01")))) for y in range(2020, 2026)}
        if min(annual.values()) < 60000:
            raise ValueError(f"Insufficient annual coverage: {symbol}")
        pip, tick = (.01 if symbol.endswith("JPY") else .0001), 10.**-repo.metadata(symbol).decimals
        f = features(ohlc, times, pip, tick)
        np.savez_compressed(out / f"{symbol}_features.npz", features=f, times=times)
        choices = signals_for(f, times, pip, tick, timestamp("2020-01-01"))
        with np.load(CACHE / f"{symbol}_features.npz", allow_pickle=False) as z:
            oldf, oldtimes = z["features"], z["times"]
            a, b = times >= timestamp("2023-01-01"), oldtimes >= timestamp("2023-01-01")
            np.testing.assert_array_equal(times[a], oldtimes[b])
            np.testing.assert_array_equal(f[a, :4], oldf[b, :4])
            np.testing.assert_allclose(f[a], oldf[b], rtol=0, atol=1e-10, equal_nan=True)
            for p, ss in choices.items():
                previous = json.loads((OLD / f"{symbol}_{p}_candidates.json").read_text(encoding="utf-8"))
                overlap = [s for s in ss if times[s["index"]] >= timestamp("2023-01-01")]
                if normalize_indices(overlap, times) != normalize_indices(previous, oldtimes):
                    raise RuntimeError(f"Overlap candidates differ: {symbol}/{p}")
        for policy, ss in choices.items():
            write_json(out / f"{symbol}_{policy}_candidates.json", ss)
        manifest.append(dict(symbol=symbol, raw_path=str(raw), raw_stat=before, raw_sha256=raw_sha,
            metadata_sha256=digest(repo.root / symbol / "info.dat"), bars=len(times), annual_bars=annual,
            first=int(times[0]), last=int(times[-1]), gaps_gt_300=int(np.sum(np.diff(times)>300)),
            cache_sha256=file_hash(out / f"{symbol}_features.npz"), old_cache_sha256=file_hash(CACHE / f"{symbol}_features.npz"),
            overlap_ohlc_exact=True, overlap_features_atol=1e-10, overlap_candidates_exact=True,
            pip=pip, tick=tick))
        write_json(out / "data_manifest.json", manifest)
        data[symbol] = f, times, pip, tick, choices
        print(f"PREPARED {symbol}: {len(times)} M5 bars", flush=True)
    return data


def gates_for(totals, policy):
    gates = {}
    for year in map(str, range(2020, 2026)):
        a, stress = totals[arm_name(policy, 1.)][year], totals[arm_name(policy, 1.2)][year]
        gates[year] = dict(count=a["trades"] >= 100,
            pf=a["profit_factor_r"] is not None and a["profit_factor_r"] >= 1.2,
            average_r=a["average_r"] > 0, cost_stress=stress["net_plus_open_r"] > 0,
            cross_pair=a["positive_pairs"] >= 4)
    gates["continuous"] = dict(drawdown=totals[arm_name(policy, 1.)]["all"]["bar_close_mtm_drawdown_r"]
        <= 1.2*totals[arm_name("original", 1.)]["all"]["bar_close_mtm_drawdown_r"])
    return gates


def assert_summary_equal(actual, expected):
    for key, value in expected.items():
        if key in ("symbol", "selected_policy", "rr", "arm", "year"):
            continue
        if isinstance(value, (int, float)):
            np.testing.assert_allclose(actual[key], value, rtol=1e-10, atol=1e-9, err_msg=key)
        else:
            assert actual[key] == value, key


def run(protocol, protocol_path, out):
    paths = ["scripts/research_bb_alternatives_sixyear.py", "tests/test_bb_alternatives_sixyear.py",
             "scripts/research_bb_alternatives.py", "scripts/research_bb3_jev_engine.py",
             "scripts/research_bb3_jev_refine.py", "scripts/research_bb3_context_timing.py",
             "src/forextester_backtest/data.py", "scripts/tradingview/bb3_reversal_confirmation_indicator.pine"]
    write_json(out / "run_manifest.json", dict(started_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=file_hash(protocol_path), inherited_protocol_sha256=file_hash(ROOT / protocol["inherited_specification"]),
        code_hashes={p: file_hash(ROOT / p) for p in paths}, model_trade_calls=0, model_trade_cache_reads=0))
    data, spans = prepare(protocol, out), periods()
    previous = json.loads((OLD / "results.json").read_text(encoding="utf-8"))
    timelines = {p: np.unique(np.concatenate([v[1][(v[1]>=a)&(v[1]<b)] for v in data.values()])) for p, (a,b) in spans.items()}
    rows, annual, overlap_rows, trades, curves, reconciled = [], [], [], {}, {}, []
    completed, tasks = 0, len(data)*len(POLICIES)*len(COSTS)*len(spans)
    labels = {arm_name(p,c): {"original":"現行BB3", "bb2_reentry":"BB2終値復帰", "wm":"W底/M天井"}[p]+f" / RR1 / {c}pips" for p in POLICIES for c in COSTS}
    for number, (symbol, (f, times, pip, tick, choices)) in enumerate(data.items(), 1):
        for policy in POLICIES:
            for cost in COSTS:
                key = arm_name(policy, cost)
                for period, (start,end) in spans.items():
                    result = execute(f, times, pip, tick, choices[policy], policy, cost, start, end)
                    tags = dict(symbol=symbol, selected_policy=policy, rr=1.)
                    row = dict(tags, arm=key, **result["summary"])
                    if period == "all": rows.append(row)
                    elif period == "overlap": overlap_rows.append(dict(row, year=period))
                    else: annual.append(dict(row, year=int(period)))
                    items = [dict(t, **tags) for t in result["trades"]]
                    trades.setdefault((key,period), []).extend(items)
                    add_curve(curves.setdefault((key,period), np.zeros(len(timelines[period]))), timelines[period], result["mtm"])
                    suffix = key if period == "all" else f"{key}_{period}"
                    np.savez_compressed(out / f"{symbol}_{suffix}_mtm.npz", mtm=result["mtm"])
                    write_json(out / f"{symbol}_{suffix}_trades.json", items)
                    if period == "overlap":
                        oldrow = next(r for r in previous["pair_summaries"] if r["symbol"]==symbol and r["arm"]==key)
                        assert_summary_equal(row, oldrow)
                        olditems = json.loads((OLD / f"{symbol}_{key}_trades.json").read_text(encoding="utf-8"))
                        with np.load(CACHE / f"{symbol}_features.npz", allow_pickle=False) as z:
                            assert normalize_indices(items,times)==normalize_indices(olditems,z["times"]), (symbol,key)
                        with np.load(OLD / f"{symbol}_{key}_mtm.npz", allow_pickle=False) as z:
                            np.testing.assert_allclose(result["mtm"], z["mtm"], rtol=0, atol=1e-9)
                        reconciled.append(dict(symbol=symbol, arm=key, trades=len(items), exact_trades=True, mtm_atol=1e-9))
                    completed += 1
                    write_progress(out,"evaluation",f"{symbol} / {policy} / {period}",completed_jobs=completed,total_jobs=tasks)
        partial = dict(protocol=protocol,complete=False,pair_summaries=rows,annual_pair_summaries=annual,
            overlap_pair_summaries=overlap_rows,totals=totals_for(rows,annual+overlap_rows,trades,curves),arm_labels=labels,
            completed_pairs=number,total_pairs=len(data),model_trade_calls=0,model_trade_cache_reads=0)
        write_json(out / "partial_results.json",partial)
        write_json(out / "overlap_reconciliation.json",reconciled)
        print(f"SIMULATED {symbol} ({number}/{len(data)})",flush=True)
    for (key,period), items in trades.items():
        suffix = key if period=="all" else f"{key}_{period}"
        write_json(out / f"{suffix}_trades.json",items)
        np.savez_compressed(out / f"{suffix}_combined_mtm.npz",mtm=np.column_stack((timelines[period],curves[key,period])))
    gates = {p:gates_for(partial["totals"],p) for p in POLICIES[1:]}
    final = dict(partial,complete=True,gates=gates,numeric_gates_pass={p:all(all(g.values()) for g in v.values()) for p,v in gates.items()},
                 eligible_for_forward_test=False,status="INDEPENDENT_REPLAY_REVIEW_REQUIRED",overlap_reconciled_cases=len(reconciled))
    write_json(out / "results.json",final)
    write_progress(out,"validation","336ケース完了・独立照合待ち",completed_jobs=tasks,total_jobs=tasks)
    print("RESULT_JSON="+str(out / "results.json"),flush=True)
    return final


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol",type=Path,default=DOC / "protocol.json")
    parser.add_argument("--output",type=Path,default=OUT)
    args=parser.parse_args()
    protocol=json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("status")!="SPEC_FROZEN" or protocol.get("experiment_id")!=ID or protocol.get("candidate_budget")!=2:
        raise ValueError("Frozen sixyear extension required")
    args.output.mkdir(parents=True,exist_ok=True)
    if any((args.output/n).exists() for n in ("run_manifest.json","results.json")):
        raise RuntimeError("Refuse to overwrite prior experiment")
    write_json(args.output / "protocol.json",protocol)
    run(protocol,args.protocol,args.output)


if __name__=="__main__":
    main()
