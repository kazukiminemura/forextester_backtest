"""Preregistered BB event study; no market/API calls and no strategy adoption."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ID = "bb_event_edge_20261003"
DOC = ROOT / "docs/quant_organization/experiments" / ID
OUT = ROOT / "agent_runs" / ID
sys.path.insert(0, str(ROOT))
HORIZONS = (1, 3, 6, 12)
METRICS = ("return_pips", "return_atr", "mfe_atr", "mae_atr", "fixed_touch", "moving_touch",
           "moving_favorable_atr", "moving_close_atr", "moving_center_shift_atr",
           "entry_beyond_moving_center", "first_passage", "fixed_first_bar", "moving_first_bar")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def calendar(times):
    months = times.astype("datetime64[s]").astype("datetime64[M]").astype(int)
    return months, times // 3600 % 24 // 4


def select_events(f, times):
    """Online origin/control choice: no future prices or coverage inspected."""
    prior = f[:, 7]
    history = pd.Series(prior).shift(1).rolling(288, min_periods=288)
    reference = history.median().to_numpy()
    valid = np.isfinite(f[:, 4:8]).all(axis=1) & np.isfinite(reference) & (prior > 0) & (history.min().to_numpy() > 0)
    ratio = np.divide(prior, reference, out=np.full(len(f), np.nan), where=reference > 0)
    regimes = np.searchsorted((.75, 1.5), ratio, side="right")
    lower, upper = f[:, 2] <= f[:, 6], f[:, 1] >= f[:, 5]
    months, clocks = calendar(times)
    first = int(np.datetime64("2020-01-01", "s").astype(int))
    last = int(np.datetime64("2026-01-01", "s").astype(int))
    latest, origins, sides, controls, reserved = {}, [], [], [], -1
    counts = Counter()
    for t in range(len(f)):
        c = t - 13
        if c >= 0 and valid[c] and not lower[c] and not upper[c]:
            latest[(int(months[c]), int(clocks[c]), int(regimes[c]))] = c
        if not first <= times[t] < last:
            continue
        if lower[t] or upper[t]:
            counts["raw_touch_bars"] += 1
        if not valid[t]:
            counts["invalid_feature_bars"] += 1
            continue
        if lower[t] and upper[t]:
            counts["both_side_touch_bars"] += 1
            continue
        if not lower[t] and not upper[t]:
            continue
        if t <= reserved:
            counts["reserved_touch_bars"] += 1
            continue
        origins.append(t)
        sides.append(1 if lower[t] else -1)
        controls.append(latest.get((int(months[t]), int(clocks[t]), int(regimes[t])), -1))
        reserved = t + 12
    return np.array(origins, dtype=np.int64), np.array(sides, dtype=np.int8), np.array(controls, dtype=np.int64), dict(counts)


def censor_reason(times, origin, horizon, period_end):
    """0 valid, 1 unmatched, 2 insufficient, 3 period boundary, 4 visible gap."""
    if origin < 0:
        return 1
    if origin + horizon >= len(times):
        return 2
    if times[origin+horizon] >= period_end:
        return 3
    return 4 if np.any(np.diff(times[origin:origin+horizon+1]) != 300) else 0


def observe(f, times, origin, side, horizon, period_end):
    """Closed-bar response from next contiguous open; NaNs preserve censoring."""
    result = np.full(len(METRICS), np.nan)
    end = origin + horizon
    if censor_reason(times, origin, horizon, period_end):
        return result
    entry, atr, initial_center = f[origin+1, 0], f[origin, 7], f[origin, 4]
    window = f[origin+1:end+1]
    favorable = side * (window[:, 1 if side == 1 else 2] - entry)
    adverse = side * (window[:, 2 if side == 1 else 1] - entry)
    fixed_hits = np.flatnonzero(favorable >= side * (initial_center - entry))
    moving_hits = np.flatnonzero(favorable >= side * (window[:, 4] - entry))
    first_passage = 0
    for row in window:
        op = side * (row[0] - entry)
        lo = side * (row[2 if side == 1 else 1] - entry)
        hi = side * (row[1 if side == 1 else 2] - entry)
        if op <= -atr:
            first_passage = -1
        elif op >= atr:
            first_passage = 1
        elif lo <= -atr:
            first_passage = -1
        elif hi >= atr:
            first_passage = 1
        if first_passage:
            break
    displacement = side * (window[-1, 3] - entry)
    result[:6] = [displacement, displacement/atr, max(0., float(favorable.max()))/atr,
                  max(0., float(-adverse.min()))/atr, bool(len(fixed_hits)), bool(len(moving_hits))]
    if len(moving_hits):
        k = moving_hits[0]
        result[6:10] = [favorable[k]/atr, side*(window[k, 3]-entry)/atr,
                       side*(window[k, 4]-initial_center)/atr, side*(entry-window[k, 4]) >= 0]
    result[10:] = [first_passage, int(fixed_hits[0])+1 if len(fixed_hits) else 0,
                  int(moving_hits[0])+1 if len(moving_hits) else 0]
    return result


def measure(f, times, origins, sides, controls, pip):
    event, control = np.full((len(origins), len(HORIZONS), len(METRICS)), np.nan), np.full((len(origins), len(HORIZONS), len(METRICS)), np.nan)
    event_reason, control_reason = np.zeros((len(origins),len(HORIZONS)),dtype=np.int8), np.zeros((len(origins),len(HORIZONS)),dtype=np.int8)
    boundary, end = int(np.datetime64("2023-01-01", "s").astype(int)), int(np.datetime64("2026-01-01", "s").astype(int))
    for row, (t, side, c) in enumerate(zip(origins, sides, controls)):
        stop = boundary if times[t] < boundary else end
        for col, h in enumerate(HORIZONS):
            event_reason[row,col] = censor_reason(times,t,h,stop)
            control_reason[row,col] = censor_reason(times,c,h,stop)
            event[row, col] = observe(f, times, t, side, h, stop)
            if c >= 0:
                control[row, col] = observe(f, times, c, side, h, stop)
    event[:, :, 0] /= pip
    control[:, :, 0] /= pip
    return event, control, event_reason, control_reason


def mean_or_none(values):
    valid = values[np.isfinite(values)]
    return float(valid.mean()) if len(valid) else None


def bootstrap(months, values, all_months):
    """Resample whole calendar months jointly across symbols and reused controls."""
    sums = np.array([values[months == month].sum() for month in all_months])
    counts = np.array([np.sum(months == month) for month in all_months])
    draws = np.random.default_rng(20261003).integers(0, len(all_months), size=(10000, len(all_months)))
    numerators, denominators = sums[draws].sum(axis=1), counts[draws].sum(axis=1)
    means = numerators[denominators > 0] / denominators[denominators > 0]
    loo = [(values.sum()-s)/(len(values)-n) for s, n in zip(sums, counts) if len(values) > n]
    return dict(ci95=list(map(float, np.quantile(means, [.025, .975]))) if len(means) else [None, None],
                leave_one_month_out_min=float(min(loo)) if loo else None,
                months=[dict(month=str(np.datetime64(int(m), "M")), n=int(n), total=float(s)) for m,n,s in zip(all_months, counts, sums)])


def summarize(data, start_year, end_year):
    first_month, last_month = (start_year-1970)*12, (end_year-1970)*12
    all_months = np.arange(first_month, last_month)
    per_pair, pooled = {}, []
    for symbol, arrays in data.items():
        mask = (arrays["month"] >= first_month) & (arrays["month"] < last_month)
        per_pair[symbol] = dict(selected=int(mask.sum()))
        pooled.append({k: v[mask] for k,v in arrays.items()})
    flat = {k: np.concatenate([r[k] for r in pooled]) for k in pooled[0]}
    horizons = {}
    for h_index, h in enumerate(HORIZONS):
        event, control = flat["event"][:,h_index], flat["control"][:,h_index]
        valid = np.isfinite(event[:,1])
        paired = valid & np.isfinite(control[:,1])
        delta = event[paired,1]-control[paired,1]
        row = dict(selected=len(event), valid_event=int(valid.sum()), censored_event=int((~valid).sum()),
                   unmatched=int(np.sum(flat["control_index"] < 0)), paired=int(paired.sum()),
                   matched_but_censored=int(np.sum((flat["control_index"] >= 0) & ~paired)),
                   paired_coverage=float(paired.sum()/valid.sum()) if valid.any() else 0.,
                   event_means={m:mean_or_none(event[:,i]) for i,m in enumerate(METRICS)},
                   paired_event_means={m:mean_or_none(event[paired,i]) for i,m in enumerate(METRICS)},
                   paired_control_means={m:mean_or_none(control[paired,i]) for i,m in enumerate(METRICS)},
                   difference_atr_mean=mean_or_none(delta), difference_pips_mean=mean_or_none(event[paired,0]-control[paired,0]),
                   paired_event_after_1pip=mean_or_none(event[paired,0]-1),
                   paired_event_after_1_2pip=mean_or_none(event[paired,0]-1.2),
                   event_first_passage={str(v):int(np.sum(event[valid,10]==v)) for v in (-1,0,1)},
                   control_first_passage={str(v):int(np.sum(control[paired,10]==v)) for v in (-1,0,1)})
        if h == 6:
            row.update(bootstrap(flat["month"][paired], delta, all_months))
            pair_differences, leave_symbol_out = {}, {}
            for number, (symbol, arrays) in enumerate(data.items()):
                rows = pooled[number]
                e, c = rows["event"][:,h_index], rows["control"][:,h_index]
                ok = np.isfinite(e[:,1]) & np.isfinite(c[:,1])
                diff = e[ok,1]-c[ok,1]
                pair_differences[symbol] = mean_or_none(diff)
                valid_e = np.isfinite(e[:,1])
                reuse = Counter(map(int, rows["control_index"][ok]))
                per_pair[symbol].update(valid6=int(valid_e.sum()), paired6=int(ok.sum()),
                    event_gross_atr_mean=mean_or_none(e[ok,1]), control_gross_atr_mean=mean_or_none(c[ok,1]),
                    difference_atr_mean=mean_or_none(diff), event_gross_pips_mean=mean_or_none(e[ok,0]),
                    unique_controls=len(reuse), max_control_reuse=max(reuse.values(),default=0),
                    repeated_control_observations=sum(n-1 for n in reuse.values()))
                n = len(delta)-len(diff)
                leave_symbol_out[symbol] = float((delta.sum()-diff.sum())/n) if n else None
            row["pair_differences"] = pair_differences
            row["leave_one_symbol_out_mean"] = leave_symbol_out
        horizons[str(h)] = row
    primary = horizons["6"]
    gates = dict(paired_count=primary["paired"]>=500, coverage=primary["paired_coverage"]>=.8,
                 gross_positive=(primary["paired_event_means"]["return_atr"] or 0)>0,
                 difference_ci_positive=(primary["ci95"][0] or 0)>0,
                 positive_pairs=sum(v is not None and v>0 for v in primary["pair_differences"].values())>=4,
                 leave_month_out_positive=(primary["leave_one_month_out_min"] or 0)>0)
    return dict(period=[start_year,end_year], horizons=horizons, per_pair=per_pair, gates=gates, stage_a_pass=all(gates.values()))


def run(protocol, protocol_path, output):
    manifest_path, cache = ROOT/protocol["data_manifest"], ROOT/protocol["cache_directory"]
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), protocol_sha256=digest(protocol_path),
                    source_manifest_sha256=digest(manifest_path), code_sha256=digest(__file__),
                    tests_sha256=digest(ROOT/"tests/test_bb_event_edge.py"), data=[])
    write_json(output/"run_manifest.json", manifest)
    data = {}
    for symbol in protocol["symbols"]:
        entry = next(v for v in source_manifest if v["symbol"]==symbol)
        source = cache/f"{symbol}_features.npz"
        actual = digest(source)
        if actual != entry["cache_sha256"]:
            raise ValueError(f"Cache SHA mismatch: {symbol}")
        with np.load(source, allow_pickle=False) as z:
            f,times = z["features"],z["times"]
        origins,sides,controls,counts = select_events(f,times)
        event,control,event_reason,control_reason = measure(f,times,origins,sides,controls,entry["pip"])
        arrays = dict(index=origins, side=sides, control_index=controls, timestamp=times[origins],
                      month=calendar(times[origins])[0], event=event, control=control,
                      event_censor_reason=event_reason,control_censor_reason=control_reason,
                      event_prior_atr=f[origins,7],control_prior_atr=np.where(controls>=0,f[np.maximum(controls,0),7],np.nan))
        np.savez_compressed(output/f"{symbol}_events.npz", **arrays)
        data[symbol] = arrays
        manifest["data"].append(dict(symbol=symbol, cache=str(source.relative_to(ROOT)), cache_sha256=actual,
            event_file_sha256=digest(output/f"{symbol}_events.npz"), rows=len(f), events=len(origins), counts=counts))
        write_json(output/"run_manifest.json",manifest)
        print(f"OBSERVED {symbol}: {len(origins)} episodes",flush=True)
    periods = {"2020_2022":summarize(data,2020,2023), "2023_2025":summarize(data,2023,2026), "all":summarize(data,2020,2026)}
    advance = all(periods[p]["stage_a_pass"] for p in ("2020_2022","2023_2025"))
    annual = {}
    for year in range(2020,2026):
        description = summarize(data,year,year+1)
        annual[str(year)] = {k:description[k] for k in ("horizons","per_pair")}
    result = dict(experiment_id=ID, complete=True, status="STAGE_A_REVIEW_REQUIRED", descriptive_previously_viewed=True,
                  metrics=list(METRICS), horizons=list(HORIZONS), periods=periods, stage_b_permitted_by_numeric_gate=advance,
                  annual_descriptive=annual,censor_reason_codes={"0":"valid","1":"unmatched","2":"insufficient","3":"period_boundary","4":"visible_gap"},
                  stage_b_status="PENDING_EXECUTION_DETAIL_SPEC" if advance else "NOT_RUN_STAGE_A_FAILED",
                  strategy_adopted=False, api_calls=0)
    write_json(output/"results.json",result)
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["results_sha256"] = digest(output/"results.json")
    write_json(output/"run_manifest.json",manifest)
    print("RESULT_JSON="+str(output/"results.json"),flush=True)
    return result


def stage_b_signals(f, times, origins, sides, tick):
    from scripts.research_bb3_jev_engine import round_tick
    arms = ("touch_next_open", "reversal_close_next_open", "breakout_close_next_open")
    signals, reasons = {a:[] for a in arms}, {a:{} for a in arms}
    for t,side in zip(origins,sides):
        t,side = int(t),int(side)
        def emit(arm,index):
            signals[arm].append(dict(index=index,side=side,origin=t,target=round_tick(float(f[index,4]),tick)))
            reasons[arm][t] = "signal"
        emit(arms[0],t)
        for arm in arms[1:]:
            reasons[arm][t] = "expired"
        confirmed = -1
        extreme = f[t,2 if side==1 else 1]
        for i in range(t+1,min(t+12,len(f))):
            cancelled = "gap_cancel" if times[i]-times[i-1]!=300 else "extreme_cancel" if side*(f[i,2 if side==1 else 1]-extreme)<0 else ""
            if cancelled:
                if confirmed<0:
                    reasons[arms[1]][t] = cancelled
                reasons[arms[2]][t] = cancelled
                break
            if confirmed>=0:
                threshold = f[confirmed,1 if side==1 else 2]
                if side*(f[i,3]-threshold)>0:
                    emit(arms[2],i)
                    break
            elif side*(f[i,3]-f[i,0])>0 and f[i,6]<f[i,3]<f[i,5]:
                confirmed = i
                emit(arms[1],i)
    return signals,reasons


def episode_ledger(f,times,origins,signals,reasons,simulation,pip,start,end):
    """Map unchanged simulator trades back to every selected origin, including zeros."""
    trades = {tr["index"]:tr for tr in simulation["trades"]}
    ledger = {int(t):dict(origin=int(t),timestamp=int(times[t]),status=reasons[int(t)],closed_r=0.,open_r=0.,net_r=0.,gross_r=0.,net_pips=0.)
              for t in origins if start<=times[t]<end}
    busy_until, open_count = -1,0
    for s in signals:
        t,i = s["origin"],s["index"]
        if t not in ledger:
            continue
        row = ledger[t]
        row["signal_index"] = i
        if not start<=times[i]<end:
            row["status"] = "signal_after_period_end"
            continue
        if i<busy_until:
            row["status"] = "occupied"
            continue
        j = i+1
        if j>=len(f) or times[j]>=end:
            row["status"] = "pending_period_end"
            continue
        if times[j]-times[i]!=300:
            row["status"] = "entry_gap"
            continue
        room = s["side"]*(s["target"]-f[j,0])/pip
        if room<=0 or room+1e-9<3:
            row["status"] = "entry_room"
            continue
        row.update(entry_index=j,entry_time=int(times[j]),entry_room_pips=float(room))
        if i in trades:
            trade = trades[i]
            busy_until = trade["exit_index"]
            row.update(status="closed",closed_r=trade["net_r"],net_r=trade["net_r"],net_pips=trade["net_pips"],
                       gross_r=trade["net_r"]+trade["cost_pips"]/trade["risk_pips"],
                       exit_index=trade["exit_index"],hold_bars=trade["exit_index"]-j+1)
        else:
            assert simulation["summary"]["open_side"]==s["side"], "Unaccounted fill"
            busy_until = len(f)
            open_count+=1
            row.update(status="open",open_r=simulation["summary"]["open_net_r"],net_r=simulation["summary"]["open_net_r"],
                       net_pips=simulation["summary"]["open_net_pips"],hold_bars=int(np.searchsorted(times,end))-j)
            row["gross_r"] = s["side"]*(f[int(np.searchsorted(times,end))-1,3]-f[j,0])/(room*pip)
    records = list(ledger.values())
    assert sum(r["status"]=="closed" for r in records)==len(trades)
    assert open_count==int(bool(simulation["summary"]["open_side"]))
    np.testing.assert_allclose(sum(r["net_r"] for r in records),simulation["summary"]["net_plus_open_r"],atol=1e-8,rtol=1e-10)
    return records


def run_stage_b(protocol_path,output):
    from scripts.research_bb3_jev_engine import simulate
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"]!="SPEC_FROZEN" or protocol["candidate_budget"]!=3:
        raise ValueError("Stage B must be frozen")
    a = json.loads((OUT/"results.json").read_text(encoding="utf-8"))
    if not a["stage_b_permitted_by_numeric_gate"]:
        raise ValueError("Stage A did not permit Stage B")
    if digest(ROOT/protocol["stage_a_protocol"])!=protocol["stage_a_protocol_sha256"]:
        raise ValueError("Stage A protocol changed")
    if (output/"run_manifest.json").exists():
        raise FileExistsError("Preserve previous Stage B")
    output.mkdir(parents=True,exist_ok=True)
    write_json(output/"protocol.json",protocol)
    a_manifest = json.loads((OUT/"run_manifest.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((ROOT/"agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json").read_text(encoding="utf-8"))
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=digest(protocol_path),
                    stage_a_results_sha256=digest(OUT/"results.json"),code_sha256=digest(__file__),
                    engine_sha256=digest(ROOT/"scripts/research_bb3_jev_engine.py"),tests_sha256=digest(ROOT/"tests/test_bb_event_edge.py"),data=[])
    write_json(output/"run_manifest.json",manifest)
    summaries,books,curves = [],{},{}
    for entry in source_manifest:
        symbol = entry["symbol"]
        cache = ROOT/"agent_runs/bb_alternatives_2020_2025_20260925"/f"{symbol}_features.npz"
        event_path = OUT/f"{symbol}_events.npz"
        expected = next(d for d in a_manifest["data"] if d["symbol"]==symbol)
        if digest(cache)!=entry["cache_sha256"] or digest(event_path)!=expected["event_file_sha256"]:
            raise ValueError(f"Input changed {symbol}")
        with np.load(cache,allow_pickle=False) as z:
            f,times = z["features"],z["times"]
        with np.load(event_path,allow_pickle=False) as z:
            origins,sides = z["index"],z["side"]
        signals,reasons = stage_b_signals(f,times,origins,sides,entry["tick"])
        write_json(output/f"{symbol}_signals.json",signals)
        for first,last in protocol["periods"]:
            label = f"{first}_{last-1}"
            start,end = [int(np.datetime64(f"{y}-01-01","s").astype(int)) for y in (first,last)]
            for arm in protocol["arms"]:
                book_signals=[s for s in signals[arm] if start<=times[s["origin"]]<end]
                for cost in protocol["costs_pips"]:
                    simulation = simulate(f,times,entry["pip"],entry["tick"],book_signals,rr=1.,cost_pips=cost,start=start,end=end,min_center_pips=3.)
                    ledger = episode_ledger(f,times,origins,book_signals,reasons[arm],simulation,entry["pip"],start,end)
                    prefix = f"{symbol}_{label}_{arm}_cost{cost:g}"
                    write_json(output/f"{prefix}_trades.json",simulation["trades"])
                    write_json(output/f"{prefix}_ledger.json",ledger)
                    np.savez_compressed(output/f"{prefix}_mtm.npz",mtm=simulation["mtm"])
                    summaries.append(dict(symbol=symbol,period=label,arm=arm,cost=cost,episodes=len(ledger),
                        statuses=dict(Counter(r["status"] for r in ledger)),max_hold_bars=max((r.get("hold_bars",0) for r in ledger),default=0),
                        **simulation["summary"]))
                    key=(label,arm,cost)
                    books.setdefault(key,[]).extend(dict(symbol=symbol,**r) for r in ledger)
                    curves.setdefault(key,[]).append(simulation["mtm"])
        manifest["data"].append(dict(symbol=symbol,cache_sha256=entry["cache_sha256"],event_sha256=expected["event_file_sha256"]))
        write_json(output/"run_manifest.json",manifest)
        print(f"STAGE_B {symbol}: 12 cases complete",flush=True)
    totals = {}
    for key,ledger in books.items():
        label,arm,cost = key
        rows = [r for r in summaries if (r["period"],r["arm"],r["cost"])==key]
        timeline = np.unique(np.concatenate([curve[:,0] for curve in curves[key]]))
        equity = np.zeros(len(timeline))
        for curve in curves[key]:
            idx = np.searchsorted(curve[:,0],timeline,side="right")-1
            equity += np.where(idx>=0,curve[np.maximum(idx,0),1],0.)
        prefix = f"{label}_{arm}_cost{cost:g}"
        np.savez_compressed(output/f"{prefix}_combined_mtm.npz",mtm=np.column_stack((timeline,equity)))
        n = sum(r["trades"] for r in rows)
        gp,gl = sum(r["gross_profit_r"] for r in rows),sum(r["gross_loss_r"] for r in rows)
        net,open_r = sum(r["net_r"] for r in rows),sum(r["open_net_r"] for r in rows)
        total = dict(episodes=len(ledger),trades=n,win_rate_pct=100*sum(r["wins"] for r in rows)/n if n else None,
            profit_factor_r=gp/gl if gl else None,net_r=net,open_r=open_r,net_plus_open_r=net+open_r,
            gross_r=sum(r["gross_r"] for r in ledger),mean_net_r_per_origin=(net+open_r)/len(ledger),
            positive_pairs=sum(r["net_plus_open_r"]>0 for r in rows),
            max_hold_bars=max(r["max_hold_bars"] for r in rows),open_positions=sum(bool(r["open_side"]) for r in rows),
            statuses=dict(Counter(r["status"] for r in ledger)),
            combined_bar_close_mtm_drawdown_r=float(np.max(np.maximum.accumulate(np.maximum(equity,0))-equity)))
        totals.setdefault(label,{}).setdefault(arm,{})[str(cost)] = total
    comparisons={}
    for first,last in protocol["periods"]:
        label=f"{first}_{last-1}"
        all_months=np.arange((first-1970)*12,(last-1970)*12)
        comparisons[label]={}
        for later,earlier in zip(protocol["arms"][1:],protocol["arms"][:-1]):
            x,y=books[label,later,1.],books[label,earlier,1.]
            assert [(r["symbol"],r["origin"]) for r in x]==[(r["symbol"],r["origin"]) for r in y]
            months=calendar(np.array([r["timestamp"] for r in x]))[0]
            values={}
            for metric in ("net_r","gross_r"):
                delta=np.array([a[metric]-b[metric] for a,b in zip(x,y)])
                values[metric]=dict(mean_difference_per_origin=float(delta.mean()),**bootstrap(months,delta,all_months))
            comparisons[label][later+"_minus_"+earlier]=values
    gates={}
    for arm in protocol["arms"]:
        gates[arm]={}
        for label,by_arm in totals.items():
            base,stress=by_arm[arm]["1.0"],by_arm[arm]["1.2"]
            gates[arm][label]=dict(count=base["trades"]>=100,pf=(base["profit_factor_r"] or 0)>=1.2,
                net=base["net_plus_open_r"]>0,stress=stress["net_plus_open_r"]>0,positive_pairs=base["positive_pairs"]>=4)
    benefit={name:all(comparisons[p][name][metric]["ci95"][0]>0 for p in comparisons for metric in ("net_r","gross_r"))
             for name in next(iter(comparisons.values()))}
    result=dict(complete=True,status="STAGE_B_INDEPENDENT_REVIEW_REQUIRED",cases=len(summaries),summaries=summaries,
                totals=totals,comparisons=comparisons,economic_gates=gates,
                economic_screen_pass={a:all(all(g.values()) for g in periods.values()) for a,periods in gates.items()},
                waiting_beneficial_screen=benefit,strategy_adopted=False,api_calls=0)
    write_json(output/"results.json",result)
    manifest["finished_utc"]=datetime.now(timezone.utc).isoformat()
    manifest["results_sha256"]=digest(output/"results.json")
    write_json(output/"run_manifest.json",manifest)
    print("RESULT_JSON="+str(output/"results.json"),flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol",type=Path,default=DOC/"protocol.json")
    parser.add_argument("--output",type=Path,default=OUT)
    parser.add_argument("--stage-b",action="store_true")
    args = parser.parse_args()
    if args.stage_b:
        run_stage_b(DOC/"protocol_stage_b.json",args.output/"stage_b")
        return
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN" or protocol["experiment_id"] != ID:
        raise ValueError("Requires prereviewed frozen protocol")
    if (args.output/"run_manifest.json").exists():
        raise FileExistsError("Prior experiment preserved; use a distinct output for reruns")
    args.output.mkdir(parents=True,exist_ok=True)
    write_json(args.output/"protocol.json",protocol)
    run(protocol,args.protocol,args.output)


if __name__ == "__main__":
    main()
