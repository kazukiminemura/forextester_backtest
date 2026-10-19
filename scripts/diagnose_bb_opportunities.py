"""Read-only replay of frozen BB opportunities and existing trade cost erosion."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_bb3_jev_engine import ROOT, candidates, round_tick, simulate

ID = "bb_reconsider_20261001"
SOURCE = ROOT / "agent_runs/bb_alternatives_2020_2025_20260925"
OUT = ROOT / "agent_runs" / ID
DOC = ROOT / "docs/quant_organization/experiments" / ID
START, END = 1577836800, 1767225600
ARM = "original_rr1.0_cost1.0"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def diagnose(f, times, pip, tick, start=START, end=END):
    """Instrument the frozen state machine; exclusive reasons use Pine order."""
    counts, signals = Counter(), []
    side, prepared, confirmed = 0, -1, -1
    threshold = cancel = math.nan
    ready_all = np.isfinite(f[:, [4, 5, 6, 7, 8]]).all(axis=1) & (f[:, 5] > f[:, 4])
    for i, row in enumerate(f):
        op, hi, lo, cl, mid, upper, lower = row[:7]
        in_period = start <= times[i] < end
        def count(key):
            if in_period:
                counts[key] += 1
        ready = ready_all[i]
        buy, sell = lo <= lower, hi >= upper
        count("bars")
        if ready and (buy or sell):
            count("touch_bars")
            if side:
                count("touch_while_setup_active")
        consumed = False
        if side:
            explained = row[10 if side == 1 else 11] != 0
            wick = row[12 if side == 1 else 13] != 0
            reasons = [(not ready, "not_ready"),
                       (i > 0 and times[i]-times[i-1] > 300, "gap"),
                       (lo < cancel if side == 1 else hi > cancel, "extreme_update"),
                       (explained, "impulse"), (wick, "wick"),
                       (sell if side == 1 else buy, "opposite_touch"),
                       (i-prepared > 12, "expiry")]
            reason = next((name for test, name in reasons if test), "")
            consumed = bool(reason)
            if reason:
                count("cancel_" + reason)
                count("cancel_after_confirmation" if confirmed >= 0 else "cancel_before_confirmation")
            else:
                if confirmed >= 0 and i > confirmed:
                    broken = hi > threshold if side == 1 else lo < threshold
                    if broken:
                        count("breakout_reached")
                        reference = max(op, threshold+tick) if side == 1 else min(op, threshold-tick)
                        room = side*(f[i-1, 4]-reference)/pip
                        if math.isfinite(room) and room+1e-9 >= 3:
                            count("candidates")
                            signals.append(dict(index=i, side=side, prep_index=prepared,
                                confirmed_index=confirmed, target=round_tick(mid, tick),
                                reference=float(reference), threshold=float(threshold), cancel_level=float(cancel)))
                        else:
                            count("breakout_room_rejected")
                        consumed = True
                elif confirmed < 0 and i > prepared and side*(cl-op)>0 and lower<cl<upper:
                    confirmed, threshold = i, hi if side == 1 else lo
                    count("confirmation_reached")
            if consumed:
                side, prepared, confirmed = 0, -1, -1
                threshold = cancel = math.nan
        if not side and not consumed and ready and (buy or sell):
            count("eligible_idle_touch")
            reason = ("both" if buy and sell else "impulse" if row[10 if buy else 11] != 0
                      else "wick" if row[12 if buy else 13] != 0 else "")
            if reason:
                count("initial_reject_"+reason)
            else:
                side, prepared = (1 if buy else -1), i
                cancel = lo if side == 1 else hi
                count("prepared")
    return dict(counts), [s for s in signals if start <= times[s["index"]] < end]


def trade_stats(trades, months=72, pairs=1):
    if not trades:
        return {"trades": 0}
    risk = np.array([t["risk_pips"] for t in trades])
    net = np.array([t["net_pips"] for t in trades])
    costs = np.array([t["cost_pips"] for t in trades])
    gross = net + costs
    gross_r, net_r = gross/risk, net/risk
    def pf(v):
        loss = -v[v<0].sum()
        return float(v[v>0].sum()/loss) if loss else None
    return dict(trades=len(trades), trades_per_pair_month=len(trades)/(months*pairs),
        win_rate_pct=float(100*np.mean(net>1e-9)), gross_pips=float(gross.sum()), net_pips=float(net.sum()),
        gross_r=float(gross_r.sum()), net_r=float(net_r.sum()), cost_r=float((costs/risk).sum()),
        gross_pf_pips=pf(gross), net_pf_pips=pf(net), gross_pf_r=pf(gross_r), net_pf_r=pf(net_r),
        average_gross_pips=float(gross.mean()), average_net_pips=float(net.mean()),
        risk_pips_quantiles=dict(zip(["min", "p25", "median", "p75", "max"], map(float,np.quantile(risk,[0,.25,.5,.75,1])))),
        average_cost_fraction_of_r=float(np.mean(costs/risk)),
        mean_break_even_win_rate_pct=float(np.mean((1+costs/risk)/2)*100),
        risk_below5_count=int(np.sum(risk<5-1e-9)), risk_below10_count=int(np.sum(risk<10-1e-9)),
        exit_reasons=dict(Counter(t["exit_reason"] for t in trades)))


def main():
    protocol = json.loads((DOC/"protocol.json").read_text(encoding="utf-8"))
    assert protocol["candidate_budget"] == 0 and protocol["status"] == "SPEC_FROZEN"
    if (OUT/"results.json").exists():
        raise RuntimeError("Refuse to overwrite completed diagnosis")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SOURCE/"data_manifest.json").read_text(encoding="utf-8"))
    rows, all_trades, total_counts, identities = [], [], Counter(), []
    for m in manifest:
        symbol = m["symbol"]
        path = SOURCE/f"{symbol}_features.npz"
        cache_hash = digest(path)
        assert cache_hash == m["cache_sha256"], symbol
        with np.load(path, allow_pickle=False) as z:
            f, times = z["features"], z["times"]
        pip, tick = m["pip"], m["tick"]
        counts, signals = diagnose(f,times,pip,tick)
        original = [s for s in candidates(f,times,pip,tick) if START <= times[s["index"]] < END]
        saved = json.loads((SOURCE/f"{symbol}_original_candidates.json").read_text(encoding="utf-8"))
        assert signals == original == saved, symbol
        replay = simulate(f,times,pip,tick,signals,start=START,end=END)
        saved_trades = json.loads((SOURCE/f"{symbol}_{ARM}_trades.json").read_text(encoding="utf-8"))
        stripped = [{k:v for k,v in t.items() if k not in ("symbol","selected_policy","rr")} for t in saved_trades]
        assert replay["trades"] == stripped, symbol
        entry = {k:replay["summary"][k] for k in ("accepted_candidates","occupied_candidates","rejected_entry_gap","rejected_entry_room","open_side","pending_side")}
        entry["filled"] = len(saved_trades)+int(entry["open_side"] != 0)
        total_counts.update(counts)
        all_trades.extend(saved_trades)
        rows.append(dict(symbol=symbol,stages=counts,execution=entry,performance=trade_stats(saved_trades)))
        identities.append(dict(symbol=symbol,cache_sha256=cache_hash,
            saved_candidates_sha256=digest(SOURCE/f"{symbol}_original_candidates.json"),
            saved_trades_sha256=digest(SOURCE/f"{symbol}_{ARM}_trades.json"),
            raw_sha256_inherited=m["raw_sha256"], raw_rehashed=False, pip=pip,tick=tick))
        print(symbol, counts, entry, flush=True)
    assert len(all_trades) == 1225
    total = trade_stats(all_trades,pairs=len(rows))
    result = dict(status="DIAGNOSIS_REPLAY_MATCHED",protocol=protocol,
        input_identities=identities, pairs=rows, aggregate_stages=dict(total_counts), aggregate_performance=total,
        candidate_replay_exact=True, trade_replay_exact=True,
        annual_existing_trades={str(y):trade_stats([t for t in all_trades if np.datetime64(t["entry_time"],"s").astype("datetime64[Y]").astype(int)+1970 == y],months=12,pairs=len(rows)) for y in range(2020,2026)},
        code_sha256=digest(Path(__file__)), protocol_sha256=digest(DOC/"protocol.json"),
        notes=["Counts describe event time, not independent opportunities; repeated touches are correlated.",
               "Exclusive rejection reasons use Pine precedence; removing one reason does not guarantee recovered trades.",
               "Previously viewed 2020-2025; descriptive diagnosis, not new out-of-sample evidence.",
               "No Jev calls. No new strategy tested. Risk equals target distance at RR1.",
               "Mean break-even win rate assumes symmetric full exits and constant within-trade cost; gaps may differ."])
    (OUT/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RESULT_JSON="+str(OUT/"results.json"),flush=True)


if __name__ == "__main__":
    main()
