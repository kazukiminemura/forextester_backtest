"""Bounded, replayable Jev experiment. No orders and no Pine changes."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
import urllib.request

import numpy as np
from research_bb3_jev_engine import ROOT, START, END, load_symbol, candidates, simulate

DOC = ROOT / 'docs/quant_organization/experiments/bb3_jev_20260925'
OUT = ROOT / 'agent_runs/bb3_jev_20260925'
QUESTION = {
    'type': 'choice',
    'instructions': (
        'Assess this closed-bar FX mean-reversion candidate using only the supplied evidence. '
        'Does the recent price sequence show credible exhaustion of the adverse move and recovery '
        'in the proposed trade direction, rather than continuing adverse momentum? '
        'The mechanical setup already touched a 3-sigma band, formed a later reversal candle, '
        'and later broke that candle extreme intrabar. A wick-only break need not be sustained. '
        'Interpret the sequence and trend/volatility context together. Do not infer news, dates, '
        'future candles or profitability. All price offsets are in prior ATR units; higher means '
        'higher actual price, not trade-aligned. Bars run oldest to newest, newest close is zero.'
    ),
    'criteria': {
        'accept': 'Credible stabilization and directional recovery; adverse pressure appears to fade, with no dominant contradictory trend or volatility shock.',
        'skip': 'Persistent adverse trend, renewed adverse pressure, fragile failed recovery, or unstable volatility dominates the apparent reversal.',
        'uncertain': 'Evidence is mixed, insufficient, disrupted by gaps, or does not clearly support either interpretation.'
    }
}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def progress(phase, message):
    write_json(OUT/'progress.json', dict(phase=phase, message=message,
               updated_utc=datetime.now(timezone.utc).isoformat()))


def payload(f, times, signal, model='jev-1.13.0'):
    i = signal['index']
    atr, anchor = float(f[i, 7]), float(f[i, 3])
    if i < 120 or not math.isfinite(atr) or atr <= 0:
        raise ValueError('Insufficient causal context')
    scale = lambda x: round((float(x) - anchor) / atr, 4)
    state = dict(
        direction='BUY' if signal['side'] == 1 else 'SELL',
        bars_ohlc_atr=[[scale(v) for v in row] for row in f[i-11:i+1, :4]],
        recent_gap=bool(np.any(np.diff(times[i-119:i+1]) != 300)),
        center_atr=scale(f[i, 4]), upper_atr=scale(f[i, 5]), lower_atr=scale(f[i, 6]),
        center_change_12bars_atr=round(float(f[i, 4]-f[i-12, 4])/atr, 4),
        mean60_atr=scale(np.mean(f[i-59:i+1, 3])),
        atr_ratio_to_prior100=round(atr/float(np.mean(f[i-100:i, 7])), 4),
        setup_age_bars=i-signal['prep_index'], reversal_age_bars=i-signal['confirmed_index'],
        reversal_break_atr=scale(signal['threshold']), cancellation_atr=scale(signal['cancel_level'])
    )
    result = dict(model=model, state=state, questions={'gate': QUESTION})
    if len(encoded(result)) > 8000:
        raise ValueError('Payload exceeds frozen limit')
    return result


def validate_response(response):
    if response.get('model') != 'jev-1.13.0':
        raise ValueError('Model differs from pinned model')
    answer = response['answers']['gate']
    probs = answer['probabilities']
    if answer['type'] != 'choice' or set(probs) != set(QUESTION['criteria']):
        raise ValueError('Unexpected response contract')
    values = [*probs.values(), answer['confidence']]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        raise ValueError('Invalid probabilities')
    if abs(sum(probs.values()) - 1) > .001 or answer['choice'] not in probs:
        raise ValueError('Invalid choice distribution')
    if probs[answer['choice']] < max(probs.values()) - 1e-9:
        raise ValueError('Choice is not maximum')
    tokens = response['usage']['input_tokens']
    if type(tokens) is not int or not 0 < tokens <= 65536:
        raise ValueError('Usage exceeds reservation or is invalid')
    return answer['choice'] == 'accept' and probs['accept'] >= .5


def api_key():
    key = os.environ.get('TYPESAFE_API_KEY')
    if not key and os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as env:
            key = winreg.QueryValueEx(env, 'TYPESAFE_API_KEY')[0]
    if not key:
        raise RuntimeError('API key unavailable')
    return key


def infer(jobs, cfg):
    """Exclusive process lock plus permanent max-context reservations, no retries."""
    cache = OUT / 'responses'
    cache.mkdir(exist_ok=True)
    lock_path = OUT / 'inference.lock'
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        key, mutex = api_key(), threading.Lock()
        ledger_path = OUT / 'reservations.jsonl'
        reserved = [json.loads(x) for x in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
        state = {'used': len(reserved), 'failures': 0}
        attempted = {r['hash'] for r in reserved}
        unit_usd = cfg['reservation_tokens_per_attempt'] * cfg['price_usd_per_million_input_tokens'] / 1e6

        def one(job):
            h, body = job
            target = cache / (h + '.json')
            with mutex:
                if target.exists() or h in attempted:
                    return
                if state['failures'] >= cfg['stop_after_failures']:
                    return
                if (state['used'] + 1) * unit_usd > cfg['hard_reserved_usd']:
                    return
                # Persist before sending; crashes/timeouts never refund this reservation.
                with ledger_path.open('a', encoding='utf-8') as ledger:
                    ledger.write(json.dumps(dict(hash=h, reserved_usd=unit_usd,
                                                 at=datetime.now(timezone.utc).isoformat())) + '\n')
                    ledger.flush()
                    os.fsync(ledger.fileno())
                attempted.add(h)
                state['used'] += 1
            started = time.perf_counter()
            record = dict(hash=h, request=body, started_utc=datetime.now(timezone.utc).isoformat())
            try:
                req = urllib.request.Request('https://api.typesafe.ai/v1/systemone', encoded(body),
                    {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=45) as result:
                    record['response'] = json.load(result)
                record['accepted'] = validate_response(record['response'])
                record['valid'] = True
            except Exception as error:
                record.update(valid=False, accepted=False, error_type=type(error).__name__)
                # Never store exception bodies/headers: they can contain secrets.
                if hasattr(error, 'code'):
                    record['http_status'] = error.code
                with mutex:
                    state['failures'] += 1
            record['seconds'] = time.perf_counter() - started
            record['finished_utc'] = datetime.now(timezone.utc).isoformat()
            if record['seconds'] >= 300:
                record['accepted'] = False
                record['valid'] = False
            write_json(target, record)
            with mutex:
                progress('inference', f"Jev応答保存 {len(list(cache.glob('*.json')))} / {len(jobs)}")
        with ThreadPoolExecutor(max_workers=cfg['max_workers']) as pool:
            for n, _ in enumerate(pool.map(one, jobs), 1):
                if n % 50 == 0:
                    print(json.dumps(dict(processed=n, **state)), flush=True)
    finally:
        os.close(lock_fd)
        lock_path.unlink()


def aggregate(trades):
    n = len(trades)
    p = [x['net_pips'] for x in trades]
    r = [x['net_r'] for x in trades]
    gp, gl = sum(v for v in p if v > 0), -sum(v for v in p if v < 0)
    rp, rl = sum(v for v in r if v > 0), -sum(v for v in r if v < 0)
    return dict(trades=n, win_rate_pct=100*sum(v > 1e-9 for v in p)/n if n else 0,
                profit_factor=gp/gl if gl else None, profit_factor_r=rp/rl if rl else None,
                net_pips=sum(p), net_r=sum(r),
                average_r=sum(r)/n if n else 0)


def report(data, protocol, jobs):
    responses = {h: json.loads((OUT/'responses'/f'{h}.json').read_text())
                 for h in jobs if (OUT/'responses'/f'{h}.json').exists()}
    valid = sum(bool(v.get('valid')) for v in responses.values())
    rows, all_trades, annual_trades, annual_rows, curves = [], {}, {}, [], {}
    progress('backtest', 'RR別・年別の損益を集計中')
    for symbol, (f, times, pip, tick, signals, hashes) in data.items():
        allowed = {i for i, h in hashes.items() if responses.get(h, {}).get('valid') and responses[h]['accepted']}
        arms = [('original', 1., 1, None)]
        arms += [(group, rr, 2, allowed if group == 'jev' else None)
                 for group in ('delay_control', 'jev') for rr in (1., 1.3, 1.5)]
        for group, rr, delay, gate in arms:
            for cost in (1., 1.2):
                key = f'{group}_rr{rr}_cost{cost}'
                result = simulate(f, times, pip, tick, signals, allowed=gate,
                                  rr=rr, entry_delay=delay, cost_pips=cost)
                ts = [dict(t, symbol=symbol) for t in result['trades']]
                all_trades.setdefault(key, []).extend(ts)
                rows.append(dict(symbol=symbol, arm=key, **result['summary']))
                np.savez_compressed(OUT/f'{symbol}_{key}_mtm.npz', mtm=result['mtm'])
                for year in (2023, 2024, 2025):
                    start = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
                    end = int(datetime(year+1, 1, 1, tzinfo=timezone.utc).timestamp())
                    annual = simulate(f, times, pip, tick, signals, allowed=gate,
                        rr=rr, entry_delay=delay, cost_pips=cost, start=start, end=end)
                    annual_trades.setdefault((key, year), []).extend(dict(t, symbol=symbol) for t in annual['trades'])
                    annual_rows.append(dict(symbol=symbol, arm=key, year=year, **annual['summary']))
                    curves.setdefault((key, year), []).append(annual['mtm'])
                    np.savez_compressed(OUT/f'{symbol}_{key}_{year}_mtm.npz', mtm=annual['mtm'])
        print('Simulated ' + symbol, flush=True)
        progress('backtest', '年別集計済み: ' + symbol)
    totals = {}
    for key, trades in all_trades.items():
        totals[key] = {'all': aggregate(trades)}
        for year in (2023, 2024, 2025):
            subset = annual_trades[key, year]
            stats = aggregate(subset)
            pair_rows = [r for r in annual_rows if r['arm']==key and r['year']==year]
            # Align cumulative marked equity by last observation; no look-ahead interpolation.
            series = curves[key, year]
            timeline = np.unique(np.concatenate([s[:, 0] for s in series]))
            equity = np.zeros(len(timeline))
            for s in series:
                idx = np.searchsorted(s[:, 0], timeline, side='right')-1
                equity += np.where(idx >= 0, s[np.maximum(idx, 0), 1], 0)
            peaks = np.maximum.accumulate(np.maximum(equity, 0))
            stats.update(open_net_r=sum(r['open_net_r'] for r in pair_rows),
                net_plus_open_r=sum(r['net_plus_open_r'] for r in pair_rows),
                bar_close_mtm_drawdown_r=float(np.max(peaks-equity)),
                positive_pairs=sum(r['net_plus_open_r'] > 0 for r in pair_rows))
            totals[key][str(year)] = stats
            write_json(OUT/f'{key}_{year}_trades.json', subset)
        write_json(OUT/f'{key}_trades.json', trades)
    ledger = [json.loads(x) for x in (OUT/'reservations.jsonl').read_text().splitlines()] if (OUT/'reservations.jsonl').exists() else []
    tokens = sum(v.get('response', {}).get('usage', {}).get('input_tokens', 0) for v in responses.values())
    summary = dict(protocol=protocol, candidates=sum(len(v[4]) for v in data.values()),
        unique_requests=len(jobs), responses=len(responses), valid_responses=valid,
        accepted_responses=sum(bool(v.get('accepted')) for v in responses.values()),
        complete=valid==len(jobs), input_tokens=tokens,
        estimated_usd=tokens*.042/1e6, reserved_usd=sum(r['reserved_usd'] for r in ledger),
        pair_summaries=rows, annual_pair_summaries=annual_rows, totals=totals)
    chosen = max((1., 1.3, 1.5), key=lambda rr: totals[f'jev_rr{rr}_cost1.0']['2023']['average_r'])
    gates = {}
    for year in ('2024', '2025'):
        a = totals[f'jev_rr{chosen}_cost1.0'][year]
        b = totals['original_rr1.0_cost1.0'][year]
        c = totals[f'delay_control_rr{chosen}_cost1.0'][year]
        gates[year] = dict(coverage=summary['complete'], count=a['trades']>=100,
            frequency=a['trades']>=.7*b['trades'],
            win_rate=a['win_rate_pct']>=max(b['win_rate_pct'], c['win_rate_pct'])+2,
            pf=a['profit_factor_r'] is not None and a['profit_factor_r']>=max(1.2, b['profit_factor_r'] or 0, c['profit_factor_r'] or 0),
            average_r=a['average_r']>max(b['average_r'], c['average_r']),
            net_r=a['net_plus_open_r']>max(b['net_plus_open_r'], c['net_plus_open_r']),
            drawdown=a['bar_close_mtm_drawdown_r']<=1.2*b['bar_close_mtm_drawdown_r'],
            cost_stress=totals[f'jev_rr{chosen}_cost1.2'][year]['net_plus_open_r']>0,
            cross_pair=a['positive_pairs']>=4)
    summary.update(selected_rr_from_2023=chosen, gates=gates,
                   eligible_for_forward_test=all(all(x.values()) for x in gates.values()))
    write_json(OUT/'results.json', summary)
    progress('validation', '集計完了・独立監査待ち')
    print('RESULT_JSON=' + str(OUT/'results.json'), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--infer', action='store_true', help='Paid API calls within frozen budget')
    parser.add_argument('--report', action='store_true', help='Local replay only')
    args = parser.parse_args()
    protocol = json.loads((DOC/'protocol.json').read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    data, jobs = {}, {}
    for symbol in protocol['symbols']:
        f, times, pip, tick = load_symbol(symbol)
        signals = [s for s in candidates(f, times, pip, tick) if START <= times[s['index']] < END]
        hashes = {}
        for signal in signals:
            body = payload(f, times, signal)
            h = digest(body)
            jobs[h] = body
            hashes[signal['index']] = h
        data[symbol] = (f, times, pip, tick, signals, hashes)
    manifest = dict(protocol_sha=digest(protocol), question=QUESTION, payload_hashes=sorted(jobs),
        code_hashes={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                     ('scripts/research_bb3_jev.py', 'scripts/research_bb3_jev_engine.py',
                      'scripts/tradingview/bb3_reversal_confirmation_indicator.pine')},
        candidates={s: len(v[4]) for s, v in data.items()})
    manifest_path = OUT/'run_manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise RuntimeError('Frozen manifest differs; do not mix experiments')
    write_json(manifest_path, manifest)
    write_json(OUT/'candidates.json', {s: [dict(x, payload_hash=v[5][x['index']],
        signal_time=int(v[1][x['index']]), available_time=int(v[1][x['index']])+300) for x in v[4]] for s,v in data.items()})
    print(json.dumps(dict(candidates=manifest['candidates'], requests=len(jobs))), flush=True)
    if args.infer:
        infer(list(jobs.items()), protocol['api'])
    if args.report:
        report(data, protocol, jobs)


if __name__ == '__main__':
    main()
