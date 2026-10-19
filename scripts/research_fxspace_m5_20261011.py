"""M5 scenario proxy: fixed bounded study, not official FX SPACE reproduction."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
from scripts import research_fxspace_proxy_20261011 as base

core=base.core
metrics=base.metrics
cash_monthly=base.cash_monthly
screen=base.screen
simulate=base.simulate
ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/"docs/quant_organization/experiments/fxspace_m5_20261011"
OUT=ROOT/"agent_runs/fxspace_m5_20261011"
ARMS=("m15_pullback","m15_direct","solo_pullback","solo_direct")
CONTROLS={"m15_pullback":"m15_direct","solo_pullback":"solo_direct"}
DIAGNOSTICS=("reversal_events","created","cancelled","recovered","expired","invalid_m5","no_target","duplicate_support","context_blocked","invalid_bracket")


def signals(data,tick,start,end):
    t,p,complete=data["times"],data["prices"],data["complete"]
    n=len(t)
    result={key:np.full((4,n),np.nan) for key in ("stops","targets","thresholds","scenario_times","support_times","acceleration","strength")}
    result["sides"]=np.zeros((4,n),np.int8)
    result["diagnostics"]=np.zeros((2,len(DIAGNOSTICS)),np.int64)
    f5,f15=base.Frame(300,tick),base.Frame(900,tick)
    higher_t,higher_p,higher_valid=base.aggregate(data,900)
    higher_i=0
    pending=[None,None]
    used=[set(),set()]
    def emit(arm,i,q):
        result["sides"][arm,i]=q["d"]
        for key,source in (("stops","sl"),("targets","tp"),("thresholds","threshold"),("scenario_times","created_time"),("support_times","support_time"),("acceleration","acceleration"),("strength","strength")):
            result[key][arm,i]=q[source]
    for i in range(n):
        if t[i]>=end:break
        now=int(t[i]+300)
        contiguous=i>0 and t[i]==t[i-1]+300 and complete[i] and complete[i-1]
        before=f5.trend
        f5.push(int(t[i]),p[i],bool(complete[i]))
        while higher_i<len(higher_t) and higher_t[higher_i]+900<=now:
            f15.push(int(higher_t[higher_i]),higher_p[higher_i],bool(higher_valid[higher_i]))
            for line in f15.lines:line["strength"]=2
            higher_i+=1
        if t[i]<start:continue
        op,hi,lo,cl=p[i]
        reversal=f5.trend if f5.trend and before==-f5.trend else 0
        for env in (0,1):
            diag=result["diagnostics"][env]
            if reversal:diag[0]+=1
            if not complete[i]:diag[5]+=1
            q=pending[env]
            if q is not None:
                d=q["d"]
                slhit=lo<=q["sl"] if d==1 else hi>=q["sl"]
                tphit=hi>=q["tp"] if d==1 else lo<=q["tp"]
                expired=i-q["created_i"]>12
                cancelled=not contiguous or slhit or tphit or (env==0 and f15.trend!=d) or f5.trend==-d
                if expired or cancelled:
                    diag[4 if expired else 2]+=1
                    pending[env]=None
                else:
                    q["counter"],decision=base.counter_recovery(q["counter"],d,op,cl,p[i-1,1],p[i-1,2])
                    if decision is not None:
                        if decision:
                            emit(2*env,i,q);diag[3]+=1
                        else:diag[2]+=1
                        pending[env]=None
                continue  # A just-cancelled episode cannot rearm on this bar.
            if not reversal or not contiguous or not np.isfinite(f5.atr) or f5.atr<=0:continue
            d=reversal
            if env==0 and f15.trend!=d:
                diag[8]+=1;continue
            points=f5.lows if d==1 else f5.highs
            if not points:
                diag[9]+=1;continue
            pivot=points[-1]
            key=(d,pivot["known"])
            if key in used[env]:
                diag[7]+=1;continue
            band=.1*f5.atr
            obstacle=base.nearest_obstacle(f5.lines+f15.lines,cl,d,band)
            if obstacle is None:
                diag[6]+=1;continue
            offset=max(tick,band)
            sl=base.round_level(pivot["price"]-d*offset,tick,d==-1)
            tp=base.round_level(obstacle["price"]-d*offset,tick,d==-1)
            if d*(cl-sl)<=0 or d*(tp-cl)<=0:
                diag[9]+=1;continue
            used[env].add(key)
            q=dict(d=d,sl=sl,tp=tp,created_i=i,created_time=now,support_time=pivot["known"],
                   threshold=f5.highs[-1]["price"] if d==1 else f5.lows[-1]["price"],
                   counter=0,acceleration=f15.acceleration(d),strength=obstacle["strength"])
            pending[env]=q
            emit(2*env+1,i,q)
            diag[1]+=1
    return result

def run(phase):
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN":
        raise ValueError("Protocol is not frozen")
    for path, expected in protocol["frozen_file_sha256"].items():
        if core.digest(ROOT/path) != expected:
            raise ValueError(f"Frozen source/spec mismatch: {path}")
    prior=protocol["frequency_baseline"]
    if core.digest(ROOT/prior["source"]) != prior["sha256"]:
        raise ValueError("Prior frequency evidence changed")
    target = OUT/phase
    if (target/"results.json").exists():
        raise ValueError("Existing result preserved: use a new experiment for changes")
    phases = list(protocol["periods"])
    candidates = [(arm, float(rr)) for arm in CONTROLS for rr in protocol["exit_rules"]["minimum_reward_risk_ratios"]]
    if phase != "training":
        prev = phases[phases.index(phase)-1]
        approval = json.loads((OUT/f"{phase}_approval.json").read_text(encoding="utf-8"))
        previous = json.loads((OUT/prev/"results.json").read_text(encoding="utf-8"))
        if not approval.get("independent_approved") or previous["selected"] is None:
            raise ValueError("Independent preceding-phase approval and selected configuration required")
        selected = previous["selected"]
        candidates = [(selected["arm"], selected["rr"])]
    configurations = sorted(set(candidates+[(CONTROLS[a], r) for a, r in candidates]))
    start, end = map(core.epoch, protocol["periods"][phase])
    target.mkdir(parents=True, exist_ok=True)
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), phase=phase,
                    files={str(p.relative_to(ROOT)): core.digest(p) for p in [DOC/"protocol.json", DOC/"hypothesis.md", Path(__file__),
                           ROOT/"tests/test_fxspace_m5_20261011.py", Path(base.__file__), ROOT/"scripts/research_new_logic_20261011.py", Path(core.__file__)]}, inputs=[])
    rows_by = {}
    records, accounts = [], {}
    for symbol in protocol["symbols"]:
        path = ROOT/protocol["cache_directory"]/f"{symbol}_m5.npz"
        expected = protocol["input_sha256"][symbol]
        if core.digest(path) != expected:
            raise ValueError(f"Input hash mismatch: {symbol}")
        with np.load(path, allow_pickle=False) as z:
            data = {k: z[k].copy() for k in ("times", "prices", "complete", "starts_at_open", "observed_open_times")}
        # No later-phase bars enter indicator or execution calculations.
        mask = data["times"] < end
        data = {key: value[mask] for key, value in data.items()}
        if np.any(np.diff(data["times"]) <= 0) or not np.isfinite(data["prices"]).all():
            raise ValueError("Invalid cache")
        costs = protocol["cost_and_fill_model"]
        normal_cost = costs["round_trip_pips"][symbol]*costs["pip"][symbol]
        sig = signals(data, costs["tick"][symbol], start, end)
        np.savez_compressed(target/f"{symbol}_signals.npz", times=data["times"], **sig)
        manifest["inputs"].append(dict(symbol=symbol, path=str(path.relative_to(ROOT)), sha256=expected,
                                       phase_signals={a: int(np.count_nonzero(sig["sides"][i])) for i, a in enumerate(ARMS)}, diagnostics={env:dict(zip(DIAGNOSTICS,map(int,sig["diagnostics"][ei]))) for ei,env in enumerate(("m15","solo"))}))
        core.dump(target/"run_manifest.json", manifest)
        for arm, rr in configurations:
            for multiplier in (1, 2):
                cost = normal_cost*multiplier
                rows, _, details = simulate(data, sig, ARMS.index(arm), rr, start, end, cost, normal_cost)
                key = f"{arm}_rr{rr:g}_cost{multiplier}"
                rows_by.setdefault(key, []).extend([dict(symbol=symbol, **x) for x in rows])
                core.save_trades(target/f"{symbol}_{key}.csv", rows)
                r = np.array([x["net_r"] for x in rows])
                np.savez_compressed(target/f"{symbol}_{key}_closed_r_curve.npz", times=np.array([x["exit_time"] for x in rows]), equity_r=np.cumsum(r))
                records.append(dict(symbol=symbol, arm=arm, rr=rr, cost_multiplier=multiplier, **metrics(rows), skipped=details["skipped"],
                                    monthly=core.monthly(rows, start, end), annual=[dict(year=y, **metrics([x for x in rows if core.stamp(x["exit_time"]-(0 if "gap" in x["reason"] else 1))[:4] == str(y)])) for y in range(int(core.stamp(start)[:4]), int(core.stamp(end)[:4]))]))
                if symbol == "USDJPY":
                    cash_rows, curve, account = simulate(data, sig, ARMS.index(arm), rr, start, end, cost, normal_cost, cash=True)
                    core.save_trades(target/f"USDJPY_{key}_cash.csv", cash_rows)
                    np.savez_compressed(target/f"USDJPY_{key}_cash_curve.npz", curve=curve)
                    accounts[key] = dict(**account, **metrics(cash_rows), monthly=cash_monthly(cash_rows, start, end, curve))
    pooled = {}
    for key, rows in rows_by.items():
        rows.sort(key=lambda x: (x["exit_time"], x["symbol"], x["entry_time"]))
        pooled[key] = metrics(rows)
    selections = []
    for arm, rr in (candidates if phase in ("training","validation") else []):
        key = f"{arm}_rr{rr:g}"
        criteria = screen(pooled[key+"_cost1"], pooled[key+"_cost2"], [r for r in records if r["arm"] == arm and r["rr"] == rr and r["cost_multiplier"] == 1],
                          accounts[key+"_cost1"], pooled[f"{CONTROLS[arm]}_rr{rr:g}_cost1"], protocol["acceptance_gates"])
        months=(int(core.stamp(end)[:4])-int(core.stamp(start)[:4]))*12
        baseline=protocol["frequency_baseline"]
        old_count=baseline["trades_by_rr"][f"{rr:g}"]
        new_count=pooled[key+"_cost1"]["trades"]
        criteria["checks"]["frequency_above_prior_training_rate"]=new_count*baseline["baseline_months"]>old_count*months
        criteria["passes"]=all(criteria["checks"].values())
        criteria["frequency_comparison"]=dict(new_monthly=new_count/months,old_training_monthly=old_count/baseline["baseline_months"],same_period_comparison=phase=="training")
        selections.append(dict(arm=arm, rr=rr, **criteria))
    passing = [s for s in selections if s["passes"]]
    passing.sort(key=lambda s: (-pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["pf"], -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["mean_net_r"],
                               -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["trades"], s["arm"], s["rr"]))
    selected = dict(arm=passing[0]["arm"], rr=passing[0]["rr"]) if passing else None
    if phase not in ("training","validation"):
        selected=dict(arm=candidates[0][0],rr=candidates[0][1])
    result = dict(phase=phase, status="SCREEN_PASSED_NEEDS_INDEPENDENT_REVIEW" if selected else "REJECTED_AT_PHASE_SCREEN",
                  selected=selected, screens=selections, records=records, pooled_equal_r=pooled, usdjpy_accounts=accounts,
                  adoption_approved=False, later_periods_used=phase!="training", pristine_holdout=False,
                  account_scope="continuous_2020_2025_no_reset" if phase=="continuous_diagnostic" else "standalone_phase_diagnostic")
    if phase not in ("training","validation"):
        result["status"]="DESCRIPTIVE_COMPLETE_NEEDS_INDEPENDENT_REPLAY"
    core.dump(target/"results.json", result)
    manifest.update(completed_utc=datetime.now(timezone.utc).isoformat(), results_sha256=core.digest(target/"results.json"))
    core.dump(target/"run_manifest.json", manifest)
    print(json.dumps(dict(status=result["status"], selected=selected, result=str(target/"results.json"))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["training", "validation", "final_confirmation", "continuous_diagnostic"], default="training")
    run(parser.parse_args().phase)
