"""Frozen, limited mechanical proxy of the cited BALLY FX EMA setup."""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

from scripts.research_fxspace_proxy_20261011 import aggregate

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/quant_organization/experiments/bari_video_20261016'
OUT = ROOT / 'agent_runs/bari_video_20261016'
ARMS = ('ema3', 'direct')


def epoch(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def frame_features(times, prices, valid, seconds):
    """At close: use old known pivots for direction, then confirm new 2/2 pivots."""
    n = len(times)
    out = {k: np.full(n, np.nan) for k in ('ema', 'high', 'low')}
    out.update({k: np.zeros(n, np.int8) for k in ('direction', 'reversal', 'agreement', 'cross')})
    out['gap'] = np.zeros(n, bool)
    out['high_known'] = np.full(n, -1, np.int64)
    out['low_known'] = np.full(n, -1, np.int64)
    window, seed = deque(maxlen=5), []
    trend, high, low, hi_known, lo_known, ema = 0, np.nan, np.nan, -1, -1, np.nan
    for i, (t, p, ok) in enumerate(zip(times, prices, valid)):
        adjacent = i > 0 and t == times[i-1]+seconds and valid[i-1] and ok
        out['gap'][i] = not adjacent
        if not adjacent:
            window.clear()
        old_ema, previous = ema, trend
        if ok:
            cl = float(p[3])
            up, down = cl > high, cl < low
            if up and down:
                trend = 0
            elif up:
                trend = 1
            elif down:
                trend = -1
            if adjacent and previous == -trend and trend:
                out['reversal'][i] = trend
            window.append((int(t), float(p[1]), float(p[2])))
            if len(window) == 5:
                b = list(window)
                if all(b[2][1] > b[j][1] for j in (0, 1, 3, 4)):
                    high, hi_known = b[2][1], int(t+seconds)
                if all(b[2][2] < b[j][2] for j in (0, 1, 3, 4)):
                    low, lo_known = b[2][2], int(t+seconds)
            if not np.isfinite(ema):
                seed.append(cl)
                if len(seed) == 25:
                    ema = float(np.mean(seed))
            else:
                ema += (2/26)*(cl-ema)
            if adjacent and np.isfinite(old_ema) and np.isfinite(ema):
                if prices[i-1, 3] <= old_ema and cl > ema:
                    out['cross'][i] = 1
                elif prices[i-1, 3] >= old_ema and cl < ema:
                    out['cross'][i] = -1
                if trend == 1 and cl > ema and ema > old_ema:
                    out['agreement'][i] = 1
                elif trend == -1 and cl < ema and ema < old_ema:
                    out['agreement'][i] = -1
        out['direction'][i] = trend
        out['ema'][i], out['high'][i], out['low'][i] = ema, high, low
        out['high_known'][i], out['low_known'][i] = hi_known, lo_known
    return out


def features(data):
    t, p = data['times'], data['prices']
    result = {300: (t, frame_features(t, p, data['complete'], 300))}
    for seconds in (900, 3600, 14400):
        ht, hp, hv = aggregate(data, seconds)
        result[seconds] = (ht, frame_features(ht, hp, hv, seconds))
    return result


def simulate(data, sig, arm, rr, start, end, cost, account=None):
    """Independent arm/RR path. Entry eligibility never sees entry-bar completeness."""
    t, p = data['times'], data['prices']
    rows, marks = [], []
    pos, pending_gap, halted = None, False, False
    equity = float(account['initial_yen']) if account else 0.0
    floor = float(account['stop_equity_yen']) if account else -np.inf
    peak, max_dd = equity, 0.0
    skipped = dict(occupied=0, missing_open=0, invalid_risk=0, size=0)
    last_i = None

    def close(i, price, reason, at_open=False):
        nonlocal equity, pos, pending_gap, halted, peak, max_dd
        q = pos
        gross = q['d']*(price-q['entry'])
        row = dict(signal_time=q['signal_time'], scenario_time=q['scenario_time'], episode_time=q['episode_time'],
                   entry_time=q['entry_time'], exit_time=int(data['observed_open_times'][i] if at_open else t[i]+300),
                   side=q['d'], entry=q['entry'], stop=q['sl'], target=q['tp'], exit=float(price),
                   risk=q['risk'], cost=float(cost), gross_r=float(gross/q['risk']), net_r=float((gross-cost)/q['risk']),
                   reason=reason, hold_bars=i-q['index']+1, exit_at_observed_open=bool(at_open))
        if account:
            # Entire friction was charged at entry; never deduct it again here.
            equity += q['qty']*gross
            if equity <= floor+1e-7:
                halted = True
            peak = max(peak, equity)
            max_dd = max(max_dd, peak-equity)
            row.update(quantity=q['qty'], fees_yen=q['qty']*cost,
                       pnl_yen=q['qty']*(gross-cost), equity_yen=equity, floor_stop=q['effective_sl'])
        rows.append(row)
        pos, pending_gap = None, False

    for i in np.flatnonzero((t >= start) & (t < end)):
        i = int(i)
        last_i = i
        prior_signal = int(sig['sides'][arm, i-1]) if i > 0 and t[i-1] >= start else 0
        was_open = pos is not None
        if prior_signal and was_open:
            skipped['occupied'] += 1
        if pos is None and prior_signal and not halted:
            # complete[i] is future at the entry instant and is intentionally absent.
            if t[i] != t[i-1]+300 or not data['starts_at_open'][i] or not data['complete'][i-1]:
                skipped['missing_open'] += 1
            else:
                entry, sl, d = float(p[i, 0]), float(sig['stops'][arm, i-1]), prior_signal
                risk = d*(entry-sl)
                if not np.isfinite(risk) or risk <= 0:
                    skipped['invalid_risk'] += 1
                else:
                    qty, effective = 1, sl
                    if account:
                        budget = min(account['risk_fraction']*equity, max(0.0, equity-floor))
                        size_limit = min(budget/(risk+cost), equity*account['max_leverage']/entry)
                        qty = int(np.floor(size_limit/account['quantity_step']+1e-12))*account['quantity_step']
                        if qty > 0:
                            equity -= qty*cost
                            floor_price = entry+d*(floor-equity)/qty
                            effective = max(sl, floor_price) if d == 1 else min(sl, floor_price)
                            max_dd = max(max_dd, peak-equity)
                    if qty <= 0:
                        skipped['size'] += 1
                    else:
                        pos = dict(d=d, sl=sl, effective_sl=effective, tp=entry+d*rr*risk,
                                   entry=entry, risk=risk, qty=qty, index=i, entry_time=int(t[i]),
                                   signal_time=int(t[i-1]+300), scenario_time=int(sig['scenario_times'][arm, i-1]),
                                   episode_time=int(sig['episode_times'][arm, i-1]))
        if pos is None:
            continue
        q, op, hi, lo, cl = pos, *map(float, p[i])
        d, sl, tp = q['d'], q['effective_sl'], q['tp']
        # Resting stops/limits are already known when an opening gap is observed.
        if d*(op-sl) <= 0:
            close(i, op, 'stop_gap', True)
        elif d*(op-tp) >= 0:
            close(i, tp, 'target_gap', True)
        elif pending_gap or (was_open and i > 0 and (t[i] != t[i-1]+300 or not data['starts_at_open'][i])):
            close(i, op, 'missing_next_open', True)
        elif (lo <= sl if d == 1 else hi >= sl):
            reason = 'floor' if account and sl != q['sl'] else 'stop'
            close(i, sl, reason)
        elif (hi >= tp if d == 1 else lo <= tp):
            close(i, tp, 'target')
        elif not data['complete'][i]:
            pending_gap = True
        elif i-q['index']+1 >= 48:
            close(i, cl, 'time')
    if pos is not None and last_i is not None:
        cl, q = float(p[last_i, 3]), pos
        gross = q['d']*(cl-q['entry'])
        mark = dict(entry_time=q['entry_time'], mark_time=int(t[last_i]+300), side=q['d'], entry=q['entry'],
                    mark=cl, stop=q['sl'], target=q['tp'], gross_r=float(gross/q['risk']),
                    net_r=float((gross-cost)/q['risk']), reason='OPEN_MARK', pending_gap=bool(pending_gap))
        if account:
            mark.update(quantity=q['qty'], marked_equity_yen=equity+q['qty']*gross)
        marks.append(mark)
    summary = dict(skipped=skipped, open_marks=marks)
    if account:
        summary.update(initial_yen=account['initial_yen'], cash_equity_yen=equity,
                       marked_equity_yen=marks[-1]['marked_equity_yen'] if marks else equity,
                       halted=halted, max_closed_drawdown_yen=max_dd,
                       accounting='round-trip cost at entry; marked equity separates open P/L; resting floor stop; gap overshoot retained')
    return rows, summary


def metrics(rows):
    r = np.asarray([x['net_r'] for x in rows], float)
    n, wins, losses = len(r), int(np.sum(r > 0)), int(np.sum(r < 0))
    profit, loss = float(r[r > 0].sum()), float(-r[r < 0].sum())
    if n:
        z, phat = 1.959963984540054, wins/n
        center = (phat+z*z/(2*n))/(1+z*z/n)
        half = z*np.sqrt(phat*(1-phat)/n+z*z/(4*n*n))/(1+z*z/n)
        ci = [float(center-half), float(center+half)]
    else:
        ci = [None, None]
    curve = np.r_[0., np.cumsum(r)]
    return dict(trades=n, wins=wins, losses=losses, breakevens=n-wins-losses,
                win_rate=wins/n if n else None, wilson95=ci,
                pf=profit/loss if loss else None, pf_infinite=bool(profit > 0 and loss == 0),
                mean_net_r=float(r.mean()) if n else None, sum_net_r=float(r.sum()),
                realized_avg_win_loss=(profit/wins)/(loss/losses) if wins and losses else None,
                max_closed_dd_r=float(np.max(np.maximum.accumulate(curve)-curve)))


def csv_rows(path, rows):
    fields = list(rows[0]) if rows else ['entry_time', 'exit_time', 'net_r', 'reason']
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def pf_value(m):
    return np.inf if m['pf_infinite'] else (m['pf'] or 0.)


def exit_year(row):
    stamp = row['exit_time']-(not row['exit_at_observed_open'])
    return datetime.fromtimestamp(stamp, timezone.utc).year


def gates(pooled, records, cash, protocol):
    g = protocol['gate']
    out = {}
    for phase in protocol['periods']:
        main = pooled[f'{phase}_ema3_rr1_cost1']
        stress = pooled[f'{phase}_ema3_rr1_cost2']
        control = pooled[f'{phase}_direct_rr1_cost1']
        pair = [r for r in records if r['phase'] == phase and r['arm'] == 'ema3' and r['rr'] == 1 and r['cost_multiplier'] == 1]
        checks = dict(count=main['trades'] >= g['every_period_pooled_trades_min'],
                      per_symbol_count=all(r['trades'] >= g['every_period_symbol_trades_min'] for r in pair),
                      normal_pf=pf_value(main) >= g['normal_pf_min'],
                      normal_mean=main['mean_net_r'] is not None and main['mean_net_r'] > 0,
                      stress_pf=pf_value(stress) > 1,
                      stress_mean=stress['mean_net_r'] is not None and stress['mean_net_r'] > 0,
                      profitable_pairs=sum(r['sum_net_r'] > 0 for r in pair) >= g['profitable_symbols_min'],
                      better_than_direct=main['mean_net_r'] is not None and control['mean_net_r'] is not None and main['mean_net_r'] > control['mean_net_r'],
                      drawdown=main['max_closed_dd_r'] <= g['every_period_primary_pooled_max_closed_dd_r'],
                      continuous_no_halt=not cash['ema3_rr1_cost1']['halted'])
        out[phase] = dict(checks=checks, passed=all(checks.values()))
    return out


def run():
    protocol_path = DOC/'protocol.json'
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    if protocol['status'] != 'SPEC_FROZEN':
        raise ValueError('Protocol must be independently reviewed and frozen before execution')
    for path, expected in protocol['frozen_file_sha256'].items():
        if digest(ROOT/path) != expected:
            raise ValueError(f'Frozen file mismatch: {path}')
    target = OUT/'research'
    target.mkdir(parents=True, exist_ok=False)
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), protocol_sha256=digest(protocol_path),
                    source_sha256=protocol['frozen_file_sha256'], inputs={}, output_sha256={})
    dump(target/'manifest.json', manifest)
    records, pooled_rows, cash_records = [], {}, {}
    for symbol in protocol['symbols']:
        path = ROOT/protocol['cache_directory']/f'{symbol}_m5.npz'
        sha = digest(path)
        if sha != protocol['input_sha256'][symbol]:
            raise ValueError(f'Input mismatch {symbol}')
        manifest['inputs'][symbol] = {'path': str(path.relative_to(ROOT)), 'sha256': sha}
        with np.load(path, allow_pickle=False) as z:
            data = {k: z[k].copy() for k in ('times', 'prices', 'complete', 'starts_at_open', 'observed_open_times')}
        keep = (data['times'] >= epoch(protocol['warmup_start'])) & (data['times'] < epoch(protocol['continuous_period'][1]))
        data = {k: v[keep] for k, v in data.items()}
        if np.any(np.diff(data['times']) <= 0) or not np.isfinite(data['prices']).all():
            raise ValueError('Invalid input OHLC/times')
        prepared = features(data)  # One decompression and one feature pass per symbol.
        for phase, period in protocol['periods'].items():
            start, end = map(epoch, period)
            sig = signals(data, protocol['tick'][symbol], start, end, prepared)
            np.savez_compressed(target/f'{symbol}_{phase}_signals.npz', times=data['times'], **sig)
            for arm_index, arm in enumerate(ARMS):
                for rr in protocol['reward_risk']:
                    # Costs never affect the R-study execution path; reuse fixed fills.
                    gross_rows, detail = simulate(data, sig, arm_index, rr, start, end, 0.)
                    for multiple in protocol['cost_multipliers']:
                        cost = protocol['round_trip_pips'][symbol]*protocol['pip'][symbol]*multiple
                        rows = [dict(r, cost=cost, net_r=r['gross_r']-cost/r['risk']) for r in gross_rows]
                        marks = [dict(r, net_r=r['gross_r']-cost/abs(r['entry']-r['stop'])) for r in detail['open_marks']]
                        key = f'{phase}_{arm}_rr{rr:g}_cost{multiple}'
                        csv_rows(target/f'{symbol}_{key}.csv', rows)
                        pooled_rows.setdefault(key, []).extend(dict(symbol=symbol, **r) for r in rows)
                        annual = []
                        for year in range(int(period[0][:4]), int(period[1][:4])):
                            year_rows = [r for r in rows if exit_year(r) == year]
                            annual.append(dict(year=year, **metrics(year_rows)))
                        records.append(dict(symbol=symbol, phase=phase, arm=arm, rr=rr, cost_multiplier=multiple,
                                            **metrics(rows), annual=annual, open_marks=marks, skipped=detail['skipped']))
        if symbol == protocol['account']['symbol']:
            start, end = map(epoch, protocol['continuous_period'])
            sig = signals(data, protocol['tick'][symbol], start, end, prepared)
            np.savez_compressed(target/f'{symbol}_continuous_signals.npz', times=data['times'], **sig)
            for arm_index, arm in enumerate(ARMS):
                for rr in protocol['reward_risk']:
                    for multiple in (1, 2):
                        cost = protocol['round_trip_pips'][symbol]*protocol['pip'][symbol]*multiple
                        rows, detail = simulate(data, sig, arm_index, rr, start, end, cost, protocol['account'])
                        key = f'{arm}_rr{rr:g}_cost{multiple}'
                        csv_rows(target/f'USDJPY_continuous_account_{key}.csv', rows)
                        cash_records[key] = dict(**detail, **metrics(rows))
    pooled, pooled_annual = {}, {}
    for key, rows in pooled_rows.items():
        rows.sort(key=lambda r: (r['exit_time'], r['symbol'], r['entry_time']))
        pooled[key] = metrics(rows)
        phase = next(p for p in protocol['periods'] if key.startswith(p+'_'))
        period = protocol['periods'][phase]
        pooled_annual[key] = [dict(year=y, **metrics([r for r in rows if exit_year(r) == y]))
                              for y in range(int(period[0][:4]), int(period[1][:4]))]
    checks = gates(pooled, records, cash_records, protocol)
    result = dict(experiment_id=protocol['experiment_id'], records=records, pooled=pooled, pooled_annual=pooled_annual,
                  continuous_usdjpy=cash_records, gates=checks,
                  disposition='RESEARCH_GATES_PASSED_NOT_ADOPTED' if all(v['passed'] for v in checks.values()) else 'REJECTED_DESCRIPTIVE_PROXY',
                  limits='Previously viewed data; mechanical EMA subset, discretionary channels/triangles not reproduced; not a test of creator win-rate claim')
    dump(target/'results.json', result)
    manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['output_sha256'] = {str(p.relative_to(target)): digest(p) for p in sorted(target.iterdir()) if p.name != 'manifest.json'}
    dump(target/'manifest.json', manifest)
    print('RESULT_JSON='+str(target/'results.json'))


def signals(data, tick, start, end, prepared=None):
    """Generate both arms from shared episodes; no execution or P/L input."""
    t, p = data['times'], data['prices']
    n = len(t)
    f = features(data) if prepared is None else prepared
    ix = {s: np.searchsorted(f[s][0]+s, t+300, side='right')-1 for s in (900, 3600, 14400)}
    result = {k: np.full((2, n), np.nan) for k in ('stops', 'scenario_times', 'episode_times', 'stop_known_times')}
    result['sides'] = np.zeros((2, n), np.int8)
    result['h4_direction'] = np.zeros(n, np.int8)
    result['episode_phase'] = np.full(n, -1, np.int8)
    result['cancel_reason'] = np.zeros(n, np.int8)
    # 1 gap, 2 context, 3 stop touch, 4 expired.
    scenario, pending = None, None

    def emit(arm, i, q):
        result['sides'][arm, i] = q['d']
        for key, value in (('stops', 'sl'), ('scenario_times', 'scenario_time'), ('episode_times', 'time'), ('stop_known_times', 'stop_known')):
            result[key][arm, i] = q[value]

    for i in range(n):
        if t[i] < start or t[i] >= end:
            continue
        now = int(t[i]+300)
        j15, j60, j240 = (int(ix[s][i]) for s in (900, 3600, 14400))
        if min(j15, j60) < 0:
            continue
        f5, f15, f60 = f[300][1], f[900][1], f[3600][1]
        h1 = int(f60['agreement'][j60])
        d15, d5 = int(f15['direction'][j15]), int(f5['direction'][i])
        new15 = f[900][0][j15]+900 == now
        new60 = f[3600][0][j60]+3600 == now
        gap = f5['gap'][i] or (new15 and f15['gap'][j15]) or (new60 and f60['gap'][j60])
        if j240 >= 0:
            result['h4_direction'][i] = f[14400][1]['direction'][j240]
        if gap:
            scenario, pending = None, None
            result['cancel_reason'][i] = 1
            continue
        if scenario is not None and (h1 != scenario['d'] or d15 != scenario['d']):
            scenario = None
        had_pending = pending is not None
        if pending is not None:
            q, d = pending, pending['d']
            reason = 2 if h1 != d or d15 != d or d5 != d else 0
            if not reason and (p[i, 2] <= q['sl'] if d == 1 else p[i, 1] >= q['sl']):
                reason = 3
            if not reason and i-q['index'] > 96:
                reason = 4
            if reason:
                pending = None
                result['cancel_reason'][i] = reason
            else:
                expected = d if q['phase'] in (0, 2) else -d
                if int(f5['cross'][i]) == expected:
                    q['phase'] += 1
                    if q['phase'] == 3:
                        emit(0, i, q)
                        pending = None
                result['episode_phase'][i] = q['phase']
        # A new M15 event creates a future scenario, never a same-close M5 episode.
        reversal15 = int(f15['reversal'][j15]) if new15 else 0
        if reversal15 and h1 == reversal15:
            scenario = {'d': reversal15, 'time': now}
        if had_pending or pending is not None or scenario is None:
            continue
        d = scenario['d']
        if now <= scenario['time'] or int(f5['reversal'][i]) != d or h1 != d:
            continue
        point = 'low' if d == 1 else 'high'
        stop_known = int(f15[point+'_known'][j15])
        sl = float(f15[point][j15])-d*tick
        if not np.isfinite(sl) or stop_known > now or d*(p[i, 3]-sl) <= 0:
            continue
        # No valid pending risk envelope if the creation bar has touched its stop.
        if (p[i, 2] <= sl if d == 1 else p[i, 1] >= sl):
            continue
        pending = {'d': d, 'sl': sl, 'index': i, 'time': now, 'scenario_time': scenario['time'], 'stop_known': stop_known, 'phase': 1 if int(f5['cross'][i]) == d else 0}
        result['episode_phase'][i] = pending['phase']
        emit(1, i, pending)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()
