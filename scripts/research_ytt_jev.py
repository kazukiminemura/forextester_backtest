"""Frozen YTT D/W M15 Jev research bridge. Offline by default; never places orders."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.request

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / 'scripts'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
from scripts import research_ytt_profit_feasibility as core
from scripts import judge_stock_research_with_jev as contract
import research_bb3_jev as client

MODEL = 'jev-1.13.0'
PRICE_PER_MILLION_USD = .042
RESERVE_USDJPY = 200.
MAX_CONTEXT_TOKENS = 65536
RESERVATION_YEN = MAX_CONTEXT_TOKENS * PRICE_PER_MILLION_USD / 1e6 * RESERVE_USDJPY
SOURCE = ROOT / 'agent_runs/ytt_monthly5_fx_20261009'
OUT = ROOT / 'agent_runs/ytt_jev_20261010'
SYMBOLS = ('USDJPY', 'EURUSD', 'GBPUSD')
PERIODS = {'training': ('2020-01-01', '2023-01-01'),
           'later': ('2023-01-01', '2025-01-01'), 'latest': ('2025-01-01', '2026-01-01')}
SPREAD = {'USDJPY': 1.2, 'EURUSD': 1.1, 'GBPUSD': 1.4}
QUESTION = {
    'type': 'choice',
    'instructions': (
        'Assess the closed-bar FX breakout candidate using only supplied price structure. '
        'Does the sequence show orderly directional continuation beyond the confirmed pivot, '
        'rather than an exhausted surge, rejection or unstable whipsaw? Daily and weekly '
        'confirmed structure directions already agree with the trade. Interpret persistence, '
        'overlapping candles and volatility together. All OHLC offsets use mean true range '
        'units, newest close zero, higher means higher actual price, oldest to newest. '
        'Do not infer news, dates, future bars or profitability. This is a structural '
        'classification, not a probability of winning a trade.'),
    'criteria': {
        'accept': 'Orderly directional continuation through the pivot; no dominant rejection, exhaustion or volatility disruption.',
        'skip': 'Rejection, repeated whipsaw, exhaustion or a disruptive volatility surge dominates the apparent breakout.',
        'uncertain': 'Evidence is mixed, gapped or insufficient to distinguish continuation from failure.'}}


def payload(prices, times, i, side, stop, threshold, daily, weekly):
    """An allowlist of facts available at signal close, never future outcomes/identities."""
    if i < 24 or side not in (-1, 1) or daily != side or weekly != side:
        raise ValueError('Insufficient causal context or no D/W agreement')
    bars = np.asarray(prices[i-23:i+1], float)
    prior_close = prices[i-24:i, 3]
    tr = np.maximum(bars[:, 1]-bars[:, 2], np.maximum(abs(bars[:, 1]-prior_close), abs(bars[:, 2]-prior_close)))
    scale = float(np.mean(tr[-14:]))
    close = float(bars[-1, 3])
    if not np.isfinite(bars).all() or not np.isfinite([stop, threshold, scale]).all() or scale <= 0:
        raise ValueError('Invalid closed-bar prices')
    if side*(close-threshold) <= 0 or side*(close-stop) <= 0:
        raise ValueError('Invalid breakout or stop')
    norm = lambda x: round((float(x)-close)/scale, 5)
    state = dict(direction='BUY' if side == 1 else 'SELL',
                 confirmed_daily_direction=int(daily), confirmed_weekly_direction=int(weekly),
                 bars_ohlc_mtr=[[norm(x) for x in b] for b in bars],
                 recent_gap=bool(np.any(np.diff(times[i-24:i+1]) != 900)),
                 confirmed_break_level_mtr=norm(threshold), stop_mtr=norm(stop),
                 last_true_range_relative=float(round(tr[-1]/scale, 5)))
    body = dict(model=MODEL, state=state, questions={'gate': QUESTION})
    if len(client.encoded(body)) > 12000:
        raise ValueError('Payload exceeds 12000-byte limit')
    return body


def accepted(response):
    contract.validate(response, {'gate': QUESTION})
    a = response['answers']['gate']
    return a['choice'] == 'accept' and a['probabilities']['accept'] >= .5


def cached(body, output):
    target = Path(output) / 'responses' / (client.digest(body)+'.json')
    if not target.exists():
        return None
    record = json.loads(target.read_text(encoding='utf-8'))
    if record.get('hash') != client.digest(body) or record.get('request') != body:
        raise ValueError('Cache provenance mismatch')
    if not record.get('valid'):
        return record
    decision = accepted(record['response'])
    if decision != record.get('accepted') or not 0 <= record.get('seconds', -1) < 900:
        raise ValueError('Invalid cached decision or latency')
    return record


def infer(jobs, output, *, live=False, max_calls=0, budget_yen=90., transport=None):
    """No retries. Durable reservations survive failures and count across phases/runs."""
    if type(max_calls) is not int or not 0 <= max_calls <= 10000 or not math.isfinite(budget_yen) or not 0 < budget_yen <= 90:
        raise ValueError('Invalid call count or 90-yen reservation budget (100 yen authorized)')
    unique = {client.digest(body): body for body in jobs}
    # Caller supplies a frozen, symbol/time-distributed order, unrelated to outcomes.
    ordered = list(unique.items())
    result = {'live': live, 'calls': 0, 'cache_hits': 0, 'reserved_yen': 0., 'failures': 0}
    if not live:
        result['cache_hits'] = sum(cached(body, output) is not None for _, body in ordered)
        result['reserved_yen'] = None  # Offline mode makes no claim about reconciled API spending.
        return result
    if max_calls == 0:
        raise ValueError('--live requires a positive --max-calls')
    output = Path(output)
    if transport is None and output.resolve() != OUT.resolve():
        raise ValueError('Live API budget belongs to the fixed experiment output only')
    (output / 'responses').mkdir(parents=True, exist_ok=True)
    lock = output / 'inference.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        ledger_path = output / 'reservations.jsonl'
        ledger = [json.loads(x) for x in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
        reservations, settlements = {}, {}

        def append_ledger(row):
            with ledger_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row)+'\n')
                f.flush()
                os.fsync(f.fileno())

        for row in ledger:
            h = row['hash']
            if row['kind'] == 'reserve':
                if h in reservations or row['reserved_yen'] != RESERVATION_YEN:
                    raise ValueError('Invalid or duplicate reservation')
                reservations[h] = row['reserved_yen']
            elif row['kind'] == 'settle':
                if h not in reservations or h in settlements:
                    raise ValueError('Invalid or duplicate settlement')
                settlements[h] = row['actual_yen']
            else:
                raise ValueError('Unknown ledger operation')
        saved_responses = {p.stem for p in (output/'responses').glob('*.json')}
        if saved_responses - reservations.keys():
            raise ValueError('Cached responses lack durable reservations; refuse budget reset')
        # Verify settled costs against response bytes, never trust a hand-edited amount.
        # A crash after response persistence but before settlement is recovered here.
        previous_failures = 0
        for h in reservations:
            target = output / 'responses' / (h+'.json')
            record = json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
            actual = None
            if record and record.get('valid'):
                record = cached(record['request'], output)
                if record['hash'] != h:
                    raise ValueError('Response differs from reservation')
                actual = record['response']['usage']['input_tokens']*PRICE_PER_MILLION_USD/1e6*RESERVE_USDJPY
            if h in settlements and (actual is None or settlements[h] != actual):
                raise ValueError('Settlement does not match validated response')
            if actual is not None and h not in settlements:
                append_ledger(dict(kind='settle', hash=h, actual_yen=actual))
                settlements[h] = actual
            if actual is None:
                previous_failures += 1
        result['failures'] = previous_failures
        used = sum(settlements.get(h, amount) for h, amount in reservations.items())
        attempted = set(reservations)
        key = None
        for h, body in ordered:
            if cached(body, output) is not None:
                result['cache_hits'] += 1
                continue
            if h in attempted:
                continue
            if result['calls'] >= max_calls or used + RESERVATION_YEN > budget_yen + 1e-9 or result['failures'] >= 3:
                break
            if key is None:
                key = client.api_key()
            reservation = dict(kind='reserve', hash=h, reserved_yen=RESERVATION_YEN, maximum_tokens=MAX_CONTEXT_TOKENS,
                               usd_per_million=PRICE_PER_MILLION_USD, reserved_usdjpy=RESERVE_USDJPY,
                               at=datetime.now(timezone.utc).isoformat())
            append_ledger(reservation)
            used += RESERVATION_YEN
            attempted.add(h)
            result['calls'] += 1
            record = dict(hash=h, request=body, valid=False, accepted=False,
                          at=datetime.now(timezone.utc).isoformat())
            started = time.perf_counter()
            try:
                request = urllib.request.Request('https://api.typesafe.ai/v1/systemone', client.encoded(body),
                    {'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
                with (transport or urllib.request.urlopen)(request, timeout=45) as response:
                    record['response'] = json.load(response)
                record['accepted'] = accepted(record['response'])
                record['seconds'] = time.perf_counter()-started
                record['valid'] = record['seconds'] < 900
                record['accepted'] &= record['valid']
            except Exception as error:
                record['error_type'] = type(error).__name__
                record['seconds'] = time.perf_counter()-started
            if not record['valid']:
                result['failures'] += 1
            client.write_json(output / 'responses' / (h+'.json'), record)
            if record['valid']:
                actual = record['response']['usage']['input_tokens']*PRICE_PER_MILLION_USD/1e6*RESERVE_USDJPY
                append_ledger(dict(kind='settle', hash=h, actual_yen=actual))
                used += actual-RESERVATION_YEN
            if result['calls'] % 25 == 0:
                print(json.dumps(dict(phase='inference', calls=result['calls'],
                    failures=result['failures'], charged_or_reserved_yen=round(used, 6))), flush=True)
        result['reserved_yen'] = used
        return result
    finally:
        os.close(fd)
        lock.unlink()


def delayed_signals(times, prices, complete, side, stops, thresholds, allowed=None):
    """One M15 bar decision latency, same invalidation for Jev and delay controls."""
    out_side = np.zeros(len(side), np.int8)
    out_stop = np.full(len(side), np.nan)
    out_level = np.full(len(side), np.nan)
    for i in np.flatnonzero(side):
        if allowed is not None and int(i) not in allowed:
            continue
        j = i+1
        if j >= len(side) or times[j] != times[i]+900 or not complete[j]:
            continue
        d, stop = int(side[i]), float(stops[i])
        if (prices[j, 2] <= stop if d == 1 else prices[j, 1] >= stop):
            continue
        if d*(prices[j, 3]-thresholds[i]) <= 0:
            continue
        out_side[j], out_stop[j], out_level[j] = d, stop, thresholds[i]
    return out_side, out_stop, out_level


# Original audited simulator retained here with only frozen RR target extension.
def simulate(times, prices, complete, starts_at_open, side, stops, threshold,
             start, end, cost, cash=False, observed_open_times=None, rr=1.):
    """One position; cash mode is USDJPY only, JPY per base-unit price move."""
    if rr not in (1., 1.5, 2.):
        raise ValueError("RR must be one of the three frozen values")
    indices = np.flatnonzero((times >= start) & (times < end))
    observed_open_times = times if observed_open_times is None else observed_open_times
    rows, curve = [], []
    position = None
    balance = 1_000_000.0
    halted, stop_time = False, ""
    skipped = dict(occupied=0, nonpositive_risk=0, missing_entry=0, zero_quantity=0)
    minimum_equity, peak_equity, intrabar_dd = balance, balance, 0.0
    for k, i in enumerate(indices):
        t = int(times[i])
        op, hi, lo, cl = prices[i]
        gap = i > 0 and (times[i]-times[i-1] != 900 or not starts_at_open[i])
        exit_price, reason = None, ""
        if position is not None and gap:
            exit_price, reason = op, "data_gap_open"
            if position["side"]*(op-position["target"]) > 0:
                exit_price, reason = position["target"], "data_gap_tp_capped"
            if cash and balance + position["qty"]*(position["side"]*(op-position["entry"])-cost) <= 900_000:
                reason = "account_floor_gap"
        if position is None and not halted and i and side[i-1]:
            if gap or times[i] != times[i-1]+900:
                skipped["missing_entry"] += 1
            else:
                d, sl = int(side[i-1]), float(stops[i-1])
                risk = d*(op-sl)
                if not np.isfinite(risk) or risk <= 0:
                    skipped["nonpositive_risk"] += 1
                else:
                    qty = (np.floor(min(balance*.005/(risk+cost), balance*25/op)/1000)*1000
                           if cash else 1.0)
                    if qty <= 0:
                        skipped["zero_quantity"] += 1
                    else:
                        position = dict(entry=op, stop=sl, target=op+d*risk*rr, side=d, risk=risk,
                                        qty=float(qty), entry_time=t, signal_time=int(times[i-1]+900),
                                        threshold=float(threshold[i-1]), entry_index=int(i), incomplete_bars=0)
        elif position is not None and i and side[i-1]:
            skipped["occupied"] += 1
        if position is not None:
            p = position
            effective_stop, stop_reason = p["stop"], "sl"
            if cash:
                floor = p["entry"] + p["side"]*((900_000-balance)/p["qty"]+cost)
                if p["side"]*(floor-effective_stop) >= 0:
                    effective_stop, stop_reason = floor, "account_floor"
            if exit_price is None:
                exit_price, reason = core.fill_bar(op, hi, lo, cl, p["side"], effective_stop, p["target"], stop_reason)
            if not complete[i]:
                p["incomplete_bars"] += 1
                if exit_price is None:
                    exit_price, reason = cl, "incomplete_bar_close"
            if exit_price is None and t % 86400 == 85500:
                exit_price, reason = cl, "daily_close"
            if exit_price is None and i-p["entry_index"]+1 >= 96:
                exit_price, reason = cl, "max_96_bars"
            if exit_price is None and k == len(indices)-1:
                exit_price, reason = cl, "period_end_mark"
            if cash:
                # After a protective exit the remainder of that bar is not exposure.
                adverse = exit_price if exit_price is not None and ("sl" in reason or "account_floor" in reason or "gap" in reason) else (lo if p["side"] == 1 else hi)
                worst = balance+p["qty"]*(p["side"]*(adverse-p["entry"])-cost)
                minimum_equity = min(minimum_equity, worst)
                intrabar_dd = max(intrabar_dd, peak_equity-worst)
            if exit_price is not None:
                gross = p["side"]*(exit_price-p["entry"])
                net = gross-cost
                pnl = net*p["qty"]
                if cash:
                    balance += pnl
                    if reason.startswith("account_floor") or balance <= 900_000+1e-7:
                        halted, stop_time = True, core.stamp(observed_open_times[i] if "gap" in reason else t+900)
                rows.append(dict(**p, exit_time=int(observed_open_times[i]) if "gap" in reason else t+900,
                                 exit_price=float(exit_price), reason=reason, cost_price=cost,
                                 gross_r=float(gross/p["risk"]), net_r=float(net/p["risk"]),
                                 net_price=float(net), pnl_yen=float(pnl) if cash else 0.0,
                                 balance_yen=float(balance) if cash else 0.0))
                position = None
        equity = balance
        if position is not None:
            equity += position["qty"]*(position["side"]*(cl-position["entry"])-cost)
        if cash:
            peak_equity = max(peak_equity, equity)
            minimum_equity = min(minimum_equity, equity)
            curve.append((t+900, equity))
    account = dict(final_equity_yen=balance, net_yen=balance-1_000_000, stopped=halted,
                   stop_time_source=stop_time, minimum_equity_yen=minimum_equity,
                   max_observed_intrabar_drawdown_yen=intrabar_dd, skipped=skipped)
    return rows, np.asarray(curve, dtype=float).reshape(-1, 2), account




def load_data(source, phase):
    start, end = map(core.epoch, PERIODS[phase])
    datasets, jobs, hashes = {}, {}, {}
    for symbol in SYMBOLS:
        paths = {kind: Path(source)/f'{symbol}_{kind}.npz' for kind in ('execution', 'entry900')}
        hashes[symbol] = {key: core.digest(path) for key, path in paths.items()}
        with np.load(paths['execution'], allow_pickle=False) as z:
            data = {k: z[k].copy() for k in z.files}
        with np.load(paths['entry900'], allow_pickle=False) as z:
            entry = {k: z[k].copy() for k in z.files}
        t, p = data['times'], data['prices']
        if np.any(np.diff(t) <= 0) or not np.isfinite(p).all() or len(p) != len(t):
            raise ValueError('Invalid execution input')
        side, stop, level = data['sides'][0], data['stops'][0], data['thresholds'][0]
        bodies, invalid = {}, []
        for i in np.flatnonzero((side != 0) & (t >= core.epoch('2020-01-01')) & (t+900 < end)):
            at = int(np.searchsorted(entry['times'], t[i]))
            if at >= len(entry['times']) or entry['times'][at] != t[i]:
                raise ValueError('Missing matching completed entry bar')
            if at < 24:
                invalid.append(dict(index=int(i), time=int(t[i]), reason='warmup_less_than_24_prior_bars'))
                continue
            if side[i]*(entry['prices'][at, 3]-stop[i]) <= 0:
                invalid.append(dict(index=int(i), time=int(t[i]), reason='nonpositive_signal_close_to_stop_risk'))
                continue
            body = payload(entry['prices'], entry['times'], at, int(side[i]), stop[i], level[i],
                           int(entry['daily'][at]), int(entry['weekly'][at]))
            bodies[int(i)] = body
            if t[i] >= start:
                jobs[client.digest(body)] = body
        data.update(bodies=bodies, deterministic_invalid=invalid)
        datasets[symbol] = data
    # Repeated midpoint subdivision spreads even a short pilot across the time range.
    # Interleave currencies; each request order is fixed before seeing any API answer.
    queues = []
    for data in datasets.values():
        bodies = [b for i, b in data['bodies'].items() if data['times'][i] >= start]
        ordered, intervals = [], [(0, len(bodies))]
        while intervals:
            lo, hi = intervals.pop(0)
            if lo < hi:
                mid = (lo+hi)//2
                ordered.append(bodies[mid])
                intervals.extend([(lo, mid), (mid+1, hi)])
        queues.append(ordered)
    jobs = {}
    for n in range(max(map(len, queues), default=0)):
        for queue in queues:
            if n < len(queue):
                body = queue[n]
                jobs[client.digest(body)] = body
    return datasets, jobs, hashes


def fingerprint(input_hashes):
    return dict(source=core.digest(__file__), core=core.digest(core.__file__),
                api_client=core.digest(client.__file__), contract=core.digest(contract.__file__),
                input_hashes=input_hashes, model=MODEL, question=QUESTION,
                rr=[1., 1.5, 2.], acceptance_probability=.5, delay_bars=1,
                cost_multipliers=[1, 2], period_definitions=PERIODS,
                budget_cap_yen=90., reservation_yen=RESERVATION_YEN)


def freeze(output, evidence, phase):
    evidence = json.loads(json.dumps(evidence))
    target = Path(output) / 'freeze.json'
    if target.exists():
        if json.loads(target.read_text(encoding='utf-8')) != evidence:
            raise ValueError('Source/input/spec changed after freeze; use a new experiment')
    elif phase != 'training':
        raise ValueError('Training freeze required before later evaluation')
    else:
        client.write_json(target, evidence)


def evaluate(datasets, phase, output, selected_rr=(1., 1.5, 2.)):
    start, end = map(core.epoch, PERIODS[phase])
    summaries, coverage = [], {}
    for symbol, data in datasets.items():
        t, p = data['times'], data['prices']
        s, sl, level = data['sides'][0], data['stops'][0], data['thresholds'][0]
        covered, approved = set(), set()
        for i, body in data['bodies'].items():
            record = cached(body, output)
            if record and record.get('valid'):
                covered.add(i)
                if record['accepted']:
                    approved.add(i)
        current = {i for i in data['bodies'] if start <= t[i] < end}
        total, scored, selected = len(current), len(covered & current), len(approved & current)
        invalid = [r for r in data.get('deterministic_invalid', []) if start <= r['time'] < end]
        coverage[symbol] = dict(candidates=total, deterministic_invalid=len(invalid), mechanical_candidates=total+len(invalid),
                                scored=scored, accepted=selected,
                                missing_or_failed=total-scored, fraction=scored/total if total else 0.)
        arms = [('original', 1., (s, sl, level))]
        for name, allowed in [('delay_control', set(data['bodies'])), ('covered_control', covered), ('jev', approved)]:
            shifted = delayed_signals(t, p, data['complete'], s, sl, level, allowed)
            arms += [(name, rr, shifted) for rr in selected_rr]
        for name, rr, signals in arms:
            for multiplier in (1, 2):
                pip = .01 if symbol.endswith('JPY') else .0001
                cost = (SPREAD[symbol]+.4)*pip*multiplier
                rows, _, _ = simulate(t, p, data['complete'], data['starts_at_open'], *signals,
                                     start, end, cost, rr=rr, observed_open_times=data['observed_open_times'])
                m = core.metrics(rows)
                wins, losses = [r['net_r'] for r in rows if r['net_r'] > 0], [-r['net_r'] for r in rows if r['net_r'] < 0]
                m.update(win_rate_pct=100*len(wins)/len(rows) if rows else None,
                         realized_payoff_ratio=float(np.mean(wins)/np.mean(losses)) if wins and losses else None)
                account = None
                if symbol == 'USDJPY':
                    _, _, account = simulate(t, p, data['complete'], data['starts_at_open'], *signals,
                        core.epoch('2020-01-01'), end, cost, cash=True, rr=rr,
                        observed_open_times=data['observed_open_times'])
                    account['candidate_coverage_complete'] = len(covered) == len(data['bodies'])
                    account['account_continuity_evidence'] = len(covered) == len(data['bodies'])
                    account['api_fees_excluded'] = True
                    account['eligible_for_adoption_evaluation'] = False
                summaries.append(dict(symbol=symbol, arm=name, rr=rr, cost_multiplier=multiplier,
                                      metrics=m, usdjpy_account=account))
                core.save_trades(Path(output)/f'{phase}_{symbol}_{name}_rr{rr}_cost{multiplier}.csv', rows)
    all_scored = all(c['candidates'] > 0 and c['scored'] == c['candidates'] for c in coverage.values())
    return dict(phase=phase, status='DESCRIPTIVE_ONLY' if all_scored else 'NEEDS_EVIDENCE',
                adoption_approved=False, coverage=coverage, results=summaries,
                limitations=['Previously viewed data; no untouched holdout.',
                    'Source clock and price side unknown; no swap; assumed spread/slippage.',
                    'API probability is structural confidence, never measured trade win rate.',
                    'Partial-cache Jev results apply only to scored candidates; compare covered_control.',
                    'JPY account uses USDJPY only, 1m initial/900k floor, risk 0.5%, no resets.',
                    'API usage fees are reported separately and excluded from trading P/L.',
                    'Historical response timing does not prove live feed/alert/latency behavior.'])


def later_selection(output):
    """Later data is never evaluated because of a CLI flag alone."""
    training = Path(output)/'training_results.json'
    selection = Path(output)/'selection.json'
    if not training.exists() or not selection.exists():
        raise ValueError('Complete training and independent hash-bound selection required')
    report = json.loads(training.read_text(encoding='utf-8'))
    picked = json.loads(selection.read_text(encoding='utf-8'))
    ratios = picked.get('rr', [])
    if (report['status'] != 'DESCRIPTIVE_ONLY' or picked.get('training_sha256') != core.digest(training)
            or picked.get('independent_review_passed') is not True or not ratios
            or any(type(r) not in (int, float) or r not in (1., 1.5, 2.) for r in ratios)):
        raise ValueError('Incomplete evidence or invalid frozen selection')
    return tuple(ratios)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=PERIODS, default='training')
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--max-calls', type=int, default=0)
    parser.add_argument('--budget-yen', type=float, default=90.)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    selected_rr = later_selection(args.output) if args.phase != 'training' else (1., 1.5, 2.)
    data, jobs, hashes = load_data(args.source, args.phase)
    evidence = fingerprint(hashes)
    freeze(args.output, evidence, args.phase)
    client.write_json(args.output/f'{args.phase}_requests.json', jobs)
    client.write_json(args.output/f'{args.phase}_candidate_manifest.json', {
        symbol: dict(eligible_candidates=int(sum(core.epoch(PERIODS[args.phase][0]) <= d['times'][i] for i in d['bodies'])),
                     deterministic_invalid=d['deterministic_invalid'],
                     candidates=[dict(index=i, signal_close_time=int(d['times'][i]+900), hash=client.digest(b))
                                 for i,b in d['bodies'].items() if d['times'][i] >= core.epoch(PERIODS[args.phase][0])])
        for symbol,d in data.items()})
    if args.prepare_only:
        print(json.dumps(dict(status='PREPARED_NO_API_NO_RESULTS', phase=args.phase, requests=len(jobs))))
        return
    run = infer(jobs.values(), args.output, live=args.live, max_calls=args.max_calls, budget_yen=args.budget_yen)
    result = evaluate(data, args.phase, args.output, selected_rr)
    result.update(inference=run, fingerprint=client.digest(evidence))
    client.write_json(args.output/f'{args.phase}_results.json', result)
    print(json.dumps(dict(status=result['status'], phase=args.phase, coverage=result['coverage'], inference=run)))


if __name__ == '__main__':
    main()
