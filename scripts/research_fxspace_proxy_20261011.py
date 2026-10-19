"""Frozen FX SPACE inspired proxy, never official reproduction or live orders."""
from __future__ import annotations
import argparse
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
from scripts import research_ytt_profit_feasibility as core
from scripts.research_new_logic_20261011 import metrics, cash_monthly, screen

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/quant_organization/experiments/fxspace_proxy_20261011"
OUT = ROOT / "agent_runs/fxspace_proxy_20261011"
ARMS = ("pullback", "direct")
CONTROLS = {"pullback": "direct"}


def aggregate(data, seconds):
    """Retain incomplete buckets as explicit invalid observations, never compress time."""
    t, p = data["times"], data["prices"]
    buckets = t // seconds * seconds
    starts = np.flatnonzero(np.r_[True, np.diff(buckets) != 0])
    ends = np.r_[starts[1:]-1, len(t)-1]
    out = np.column_stack((p[starts,0], np.maximum.reduceat(p[:,1], starts), np.minimum.reduceat(p[:,2], starts), p[ends,3]))
    valid = ((ends-starts+1 == seconds//300) & (t[starts] == buckets[starts]) &
             (t[ends] == buckets[starts]+seconds-300) & np.logical_and.reduceat(data["complete"], starts))
    return buckets[starts], out, valid


@dataclass
class Frame:
    seconds: int
    tick: float
    bars: deque = field(default_factory=lambda: deque(maxlen=21))
    highs: deque = field(default_factory=lambda: deque(maxlen=3))
    lows: deque = field(default_factory=lambda: deque(maxlen=3))
    lines: list = field(default_factory=list)
    trend: int = 0
    previous_time: int = -1
    atr: float = float("nan")

    def push(self, t, p, valid=True):
        if not valid or self.previous_time != t-self.seconds:
            self.bars.clear()
            self.atr = float("nan")
            if self.seconds == 300:
                self.trend = 0
        self.previous_time = t
        if not valid:
            return
        self.bars.append((t, *map(float,p)))
        close_t = t+self.seconds
        self.lines = [x for x in self.lines if close_t-x["known"] <= 8*86400 and
                      not (x["kind"] == 1 and p[3] > x["price"]+x["band"]) and
                      not (x["kind"] == -1 and p[3] < x["price"]-x["band"])]
        if len(self.bars) == 21:
            b = np.asarray(self.bars)
            self.atr = float(np.maximum(b[1:,2]-b[1:,3], np.maximum(abs(b[1:,2]-b[:-1,4]),abs(b[1:,3]-b[:-1,4]))).mean())
        if len(self.bars) >= 5:
            b = list(self.bars)[-5:]
            for kind, col, history in ((1,2,self.highs),(-1,3,self.lows)):
                value = b[2][col]
                if all(kind*(value-b[k][col]) > 0 for k in (0,1,3,4)):
                    point = dict(price=value, origin=b[2][0], known=close_t, kind=kind,
                                 band=max(self.tick, .1*self.atr) if np.isfinite(self.atr) else self.tick,
                                 strength=2 if self.seconds==3600 else 1)
                    history.append(point)
                    if np.isfinite(self.atr):
                        self.lines.append(point)
                        same = [x for x in self.lines if x["kind"]==kind]
                        if len(same)>64:
                            self.lines.remove(same[0])
        if self.seconds == 300:
            up = bool(self.highs and p[3] > self.highs[-1]["price"])
            down = bool(self.lows and p[3] < self.lows[-1]["price"])
            if up and down: self.trend = 0
            elif up: self.trend = 1
            elif down: self.trend = -1
        elif len(self.highs)>=2 and len(self.lows)>=2:
            dh=self.highs[-1]["price"]-self.highs[-2]["price"]
            dl=self.lows[-1]["price"]-self.lows[-2]["price"]
            self.trend = 1 if dh>0 and dl>0 else (-1 if dh<0 and dl<0 else 0)

    def acceleration(self, direction):
        points = self.highs if direction==1 else self.lows
        if len(points)<3: return 0
        delta = abs(points[-1]["price"]-points[-2]["price"])-abs(points[-2]["price"]-points[-3]["price"])
        return 1 if delta>self.tick else (-1 if delta < -self.tick else 0)


def nearest_obstacle(lines, close, direction, band):
    """Cluster same-purpose nearby levels, with latest known representative."""
    eligible = sorted([x for x in lines if direction*(x["price"]-close)>0], key=lambda x:x["price"])
    groups=[]
    for x in eligible:
        if groups and x["price"]-groups[-1][-1]["price"]<=band:
            groups[-1].append(x)
        else: groups.append([x])
    reps=[]
    for g in groups:
        item=dict(max(g,key=lambda x:(x["known"],x["strength"])))
        item["strength"]=max(x["strength"] for x in g)
        reps.append(item)
    return min(reps,key=lambda x:direction*(x["price"]-close)) if reps else None


def round_level(value, tick, upward):
    ratio=value/tick
    return float((np.ceil(ratio-1e-9) if upward else np.floor(ratio+1e-9))*tick)


def counter_recovery(counter, direction, op, cl, prior_high, prior_low):
    """None waits; first directional recovery after two counter bars ends the setup."""
    body=direction*(cl-op)
    if body<0: return counter+1,None
    if body>0 and counter>=2:
        return 0,bool(cl>prior_high if direction==1 else cl<prior_low)
    return 0,None


def signals(data, tick, start, end):
    t,p,complete=data["times"],data["prices"],data["complete"]
    n=len(t)
    result={key:np.full((2,n),np.nan) for key in ("stops","targets","thresholds","scenario_times","support_times","acceleration","strength")}
    result["sides"]=np.zeros((2,n),np.int8)
    result["diagnostics"] = np.zeros(8,np.int64) # created, cancelled, reversed, recovery, expiry, invalid_m5, no_target, duplicate
    frames={s:Frame(s,tick) for s in (300,900,3600)}
    grouped={s:aggregate(data,s) for s in (900,3600)}
    pointers={900:0,3600:0}
    pending=None
    used=set()
    def emit(arm,i,state):
        result["sides"][arm,i]=state["d"]
        for key, source in (("stops","sl"),("targets","tp"),("thresholds","threshold"),("scenario_times","created_time"),("support_times","support_time"),("acceleration","acceleration"),("strength","strength")):
            result[key][arm,i]=state[source]
    for i in range(n):
        now=int(t[i]+300)
        if t[i]>=end: break
        contiguous=i>0 and t[i]==t[i-1]+300 and complete[i] and complete[i-1]
        before=frames[300].trend
        frames[300].push(int(t[i]),p[i],bool(complete[i]))
        new_m15=False
        for seconds in (3600,900):
            times,prices,valid=grouped[seconds]
            j=pointers[seconds]
            while j<len(times) and times[j]+seconds<=now:
                frames[seconds].push(int(times[j]),prices[j],bool(valid[j]))
                if seconds==900 and times[j]+seconds==now and valid[j]: new_m15=True
                j+=1
            pointers[seconds]=j
        if t[i]<start: continue
        op,hi,lo,cl=p[i]
        occupied=pending is not None
        if pending is not None:
            q=pending; d=q["d"]
            slhit=lo<=q["sl"] if d==1 else hi>=q["sl"]
            tphit=hi>=q["tp"] if d==1 else lo<=q["tp"]
            expired=i-q["created_i"]>24 or (q["reversal"] is not None and i-q["reversal"]>12)
            if not contiguous or slhit or tphit or frames[3600].trend!=d or expired:
                result["diagnostics"][4 if expired else 1]+=1
                pending=None
            elif q["reversal"] is None:
                if before==-d and frames[300].trend==d:
                    q["reversal"]=i
                    q["threshold"]=frames[300].highs[-1]["price"] if d==1 else frames[300].lows[-1]["price"]
                    emit(1,i,q); result["diagnostics"][2]+=1
            elif i>q["reversal"]:
                if frames[300].trend==-d:
                    pending=None;result["diagnostics"][1]+=1
                else:
                    q["counter"], decision=counter_recovery(q["counter"],d,op,cl,p[i-1,1],p[i-1,2])
                    if decision is not None:
                        if decision:
                            emit(0,i,q);result["diagnostics"][3]+=1
                        pending=None
        if not complete[i]: result["diagnostics"][5]+=1
        if occupied or pending is not None or not new_m15 or not contiguous: continue
        f15,f60=frames[900],frames[3600]
        d=f15.trend
        if not d or f60.trend!=d or not np.isfinite(f15.atr) or f15.atr<=0: continue
        pivot=f15.lows[-1] if d==1 else f15.highs[-1]
        key=(d,pivot["known"])
        if key in used:
            result["diagnostics"][7]+=1;continue
        band=.1*f15.atr
        obstacle=nearest_obstacle(f15.lines+f60.lines,cl,d,band)
        if obstacle is None:
            result["diagnostics"][6]+=1;continue
        offset=max(tick,band)
        sl=round_level(pivot["price"]-d*offset,tick,d==-1)
        tp=round_level(obstacle["price"]-d*offset,tick,d==-1)
        if d*(cl-sl)<=0 or d*(tp-cl)<=0: continue
        used.add(key)
        pending=dict(d=d,sl=sl,tp=tp,created_i=i,created_time=now,support_time=pivot["known"],
                     threshold=np.nan,reversal=None,counter=0,acceleration=f60.acceleration(d),strength=obstacle["strength"])
        result["diagnostics"][0]+=1
    return result


def simulate(data,sig,arm,rr,start,end,cost,normal_cost,cash=False):
    t,p=data["times"],data["prices"]
    complete,exact,observed=data["complete"],data["starts_at_open"],data["observed_open_times"]
    indices=np.flatnonzero((t>=start)&(t<end))
    balance,peak,minimum,drawdown=1e6,1e6,1e6,0.
    rows,curve=[],[]; position=None; halted=False; stop_time=""
    skipped=dict(occupied=0,missing_entry=0,invalid_risk=0,cost_floor=0,insufficient_room=0,zero_quantity=0,daily_cutoff=0)
    for k,i in enumerate(indices):
        now=int(t[i]);op,hi,lo,cl=p[i]
        gap=i>0 and (t[i]!=t[i-1]+300 or not exact[i])
        exit_price=None;reason="";occupied=position is not None
        if occupied and gap:
            exit_price,reason=op,"data_gap_open"
            if position["side"]*(op-position["target"])>0:
                exit_price,reason=position["target"],"data_gap_tp_capped"
        if i and t[i-1]>=start and sig["sides"][arm,i-1] and not halted:
            reject="occupied" if occupied else ("missing_entry" if gap or not complete[i-1] else ("daily_cutoff" if now%86400==86100 else ""))
            d=int(sig["sides"][arm,i-1]);sl=float(sig["stops"][arm,i-1]);tp=float(sig["targets"][arm,i-1])
            risk=d*(op-sl);reward=d*(tp-op)
            if not reject:
                reject="invalid_risk" if not np.isfinite(risk+reward) or risk<=0 else ("cost_floor" if normal_cost/risk>.2+1e-12 else ("insufficient_room" if reward/risk<rr-1e-12 else ""))
            if reject: skipped[reject]+=1
            else:
                qty=float(np.floor(min(balance*.005/(risk+cost),balance*25/op)/1000)*1000) if cash else 1.
                if qty<=0: skipped["zero_quantity"]+=1
                else:
                    position=dict(entry=float(op),stop=sl,target=tp,side=d,risk=float(risk),rr=float(rr),planned_rr=float(reward/risk),qty=qty,
                                  entry_time=now,signal_time=int(t[i-1]+300),entry_index=int(i),incomplete_bars=0,
                                  threshold=float(sig["thresholds"][arm,i-1]),scenario_time=int(sig["scenario_times"][arm,i-1]),support_time=int(sig["support_times"][arm,i-1]),
                                  acceleration=int(sig["acceleration"][arm,i-1]),line_strength=int(sig["strength"][arm,i-1]))
        if position is not None:
            q=position;effective=q["stop"];stop_reason="sl"
            if cash:
                floor=q["entry"]+q["side"]*((900000-balance)/q["qty"]+cost)
                if q["side"]*(floor-effective)>=0: effective,stop_reason=floor,"account_floor"
            if exit_price is None:
                exit_price,reason=core.fill_bar(op,hi,lo,cl,q["side"],effective,q["target"],stop_reason)
            if not complete[i]:
                q["incomplete_bars"]+=1
                if exit_price is None: exit_price,reason=cl,"incomplete_bar_close"
            if exit_price is None and now%86400==86100: exit_price,reason=cl,"daily_close"
            if exit_price is None and i-q["entry_index"]+1>=48: exit_price,reason=cl,"max_48_bars"
            if exit_price is None and k==len(indices)-1: exit_price,reason=cl,"period_end_mark"
            if cash:
                adverse=exit_price if exit_price is not None and ("sl" in reason or "account_floor" in reason or "gap" in reason) else (lo if q["side"]==1 else hi)
                worst=balance+q["qty"]*(q["side"]*(adverse-q["entry"])-cost)
                minimum=min(minimum,worst);drawdown=max(drawdown,peak-worst)
            if exit_price is not None:
                gross=q["side"]*(exit_price-q["entry"]);net=gross-cost
                exit_time=int(observed[i]) if "gap" in reason else now+300
                if cash:
                    balance+=net*q["qty"]
                    if reason.startswith("account_floor") or balance<=900000+1e-7:
                        halted=True;stop_time=core.stamp(exit_time)
                rows.append(dict(**q,exit_time=exit_time,exit_price=float(exit_price),reason=reason,cost_price=cost,gross_r=float(gross/q["risk"]),net_r=float(net/q["risk"]),net_price=float(net),pnl_yen=float(net*q["qty"]) if cash else 0.,balance_yen=balance if cash else 0.))
                position=None
        equity=balance
        if cash and position is not None: equity+=position["qty"]*(position["side"]*(cl-position["entry"])-cost)
        if cash:
            peak=max(peak,equity);minimum=min(minimum,equity);curve.append((now+300,equity))
    return rows,np.array(curve).reshape(-1,2),dict(final_equity_yen=balance,net_yen=balance-1e6,stopped=halted,stop_time_source=stop_time,minimum_equity_yen=minimum,max_observed_intrabar_drawdown_yen=drawdown,skipped=skipped)

def run(phase):
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "SPEC_FROZEN":
        raise ValueError("Protocol is not frozen")
    for path, expected in protocol["frozen_file_sha256"].items():
        if core.digest(ROOT/path) != expected:
            raise ValueError(f"Frozen source/spec mismatch: {path}")
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
                           ROOT/"tests/test_fxspace_proxy_20261011.py", ROOT/"scripts/research_new_logic_20261011.py", Path(core.__file__)]}, inputs=[])
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
                                       phase_signals={a: int(np.count_nonzero(sig["sides"][i])) for i, a in enumerate(ARMS)}))
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
    for arm, rr in candidates:
        key = f"{arm}_rr{rr:g}"
        criteria = screen(pooled[key+"_cost1"], pooled[key+"_cost2"], [r for r in records if r["arm"] == arm and r["rr"] == rr and r["cost_multiplier"] == 1],
                          accounts[key+"_cost1"], pooled[f"{CONTROLS[arm]}_rr{rr:g}_cost1"], protocol["acceptance_gates"])
        selections.append(dict(arm=arm, rr=rr, **criteria))
    passing = [s for s in selections if s["passes"]]
    passing.sort(key=lambda s: (-pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["pf"], -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["mean_net_r"],
                               -pooled[f"{s['arm']}_rr{s['rr']:g}_cost1"]["trades"], s["arm"], s["rr"]))
    selected = dict(arm=passing[0]["arm"], rr=passing[0]["rr"]) if passing else None
    result = dict(phase=phase, status="SCREEN_PASSED_NEEDS_INDEPENDENT_REVIEW" if selected else "REJECTED_AT_PHASE_SCREEN",
                  selected=selected, screens=selections, records=records, pooled_equal_r=pooled, usdjpy_accounts=accounts,
                  adoption_approved=False, later_periods_used=phase!="training", pristine_holdout=False,
                  account_scope="continuous_2020_2025_no_reset" if phase=="continuous_diagnostic" else "standalone_phase_diagnostic")
    core.dump(target/"results.json", result)
    manifest.update(completed_utc=datetime.now(timezone.utc).isoformat(), results_sha256=core.digest(target/"results.json"))
    core.dump(target/"run_manifest.json", manifest)
    print(json.dumps(dict(status=result["status"], selected=selected, result=str(target/"results.json"))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["training", "validation", "final_confirmation", "continuous_diagnostic"], default="training")
    run(parser.parse_args().phase)
