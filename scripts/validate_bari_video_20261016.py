"""Independent replay of the frozen BALLY EMA approximation; no strategy edits."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/quant_organization/experiments/bari_video_20261016'
OUT = ROOT / 'agent_runs/bari_video_20261016'
ARMS = ('ema3', 'direct')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def epoch(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def aggregate(data, seconds):
    times, prices, valid = data['times'], data['prices'], data['complete']
    bucket = times // seconds * seconds
    cuts = np.r_[0, np.flatnonzero(np.diff(bucket)) + 1, len(times)]
    rows, stamps, complete = [], [], []
    for a, b in zip(cuts[:-1], cuts[1:]):
        stamp = int(bucket[a])
        stamps.append(stamp)
        rows.append([prices[a, 0], prices[a:b, 1].max(), prices[a:b, 2].min(), prices[b-1, 3]])
        complete.append(b-a == seconds//300 and times[a] == stamp and
                        times[b-1] == stamp+seconds-300 and bool(valid[a:b].all()))
    return np.array(stamps, np.int64), np.array(rows), np.array(complete, bool)


def frame_features(times, prices, valid, seconds):
    """Alternative state implementation; no call into research feature functions."""
    n = len(times)
    result = {key: np.full(n, np.nan) for key in ('ema', 'high', 'low')}
    result.update({key: np.zeros(n, np.int8) for key in ('direction', 'reversal', 'agreement', 'cross')})
    result['gap'] = np.ones(n, bool)
    for key in ('high_known', 'low_known'):
        result[key] = np.full(n, -1, np.int64)
    extrema = [math.nan, math.nan]
    known = [-1, -1]
    direction, moving_average, run = 0, math.nan, 0
    initialization = []
    for i in range(n):
        contiguous = bool(i > 0 and valid[i] and valid[i-1] and times[i]-times[i-1] == seconds)
        result['gap'][i] = not contiguous
        run = run+1 if contiguous else int(valid[i])
        if valid[i]:
            closing = float(prices[i, 3])
            old_direction, previous_average = direction, moving_average
            above, below = closing > extrema[0], closing < extrema[1]
            if above or below:
                direction = 0 if above and below else 1 if above else -1
            if contiguous and old_direction * direction == -1:
                result['reversal'][i] = direction
            if run >= 5:
                surroundings = [i-4, i-3, i-1, i]
                if prices[i-2, 1] > prices[surroundings, 1].max():
                    extrema[0], known[0] = prices[i-2, 1], int(times[i]+seconds)
                if prices[i-2, 2] < prices[surroundings, 2].min():
                    extrema[1], known[1] = prices[i-2, 2], int(times[i]+seconds)
            if math.isnan(moving_average):
                initialization.append(closing)
                if len(initialization) == 25:
                    moving_average = sum(initialization)/25
            else:
                moving_average = previous_average+(closing-previous_average)/13
            if contiguous and math.isfinite(previous_average):
                before = prices[i-1, 3]-previous_average
                after = closing-moving_average
                if before <= 0 < after:
                    result['cross'][i] = 1
                elif before >= 0 > after:
                    result['cross'][i] = -1
                if direction*after > 0 and direction*(moving_average-previous_average) > 0:
                    result['agreement'][i] = direction
        for key, value in zip(('high', 'low', 'high_known', 'low_known'), (*extrema, *known)):
            result[key][i] = value
        result['ema'][i], result['direction'][i] = moving_average, direction
    return result


def features(data):
    result = {}
    for seconds in (300, 900, 3600, 14400):
        t, p, v = ((data['times'], data['prices'], data['complete']) if seconds == 300
                   else aggregate(data, seconds))
        result[seconds] = (t, frame_features(t, p, v, seconds))
    return result


def signals(data, tick, start, end, prepared=None):
    """Advance closed higher bars by pointers; independently form the two signals."""
    frames = features(data) if prepared is None else prepared
    n = len(data['times'])
    output = {k: np.full((2, n), np.nan) for k in ('stops', 'scenario_times', 'episode_times', 'stop_known_times')}
    output['sides'] = np.zeros((2, n), np.int8)
    output['h4_direction'] = np.zeros(n, np.int8)
    output['episode_phase'] = np.full(n, -1, np.int8)
    output['cancel_reason'] = np.zeros(n, np.int8)
    index = {900: -1, 3600: -1, 14400: -1}
    scenario_side, scenario_time, episode = 0, -1, None
    m5 = frames[300][1]

    def record(arm, row, entry):
        output['sides'][arm, row] = entry['side']
        for key, field in (('stops', 'stop'), ('scenario_times', 'scenario'),
                           ('episode_times', 'known'), ('stop_known_times', 'stop_known')):
            output[key][arm, row] = entry[field]

    for i, timestamp in enumerate(data['times']):
        now = int(timestamp)+300
        for width in index:
            stamps = frames[width][0]
            while index[width]+1 < len(stamps) and stamps[index[width]+1]+width <= now:
                index[width] += 1
        if timestamp < start or timestamp >= end or min(index[900], index[3600]) < 0:
            continue
        j, k, h = index[900], index[3600], index[14400]
        m15, h1 = frames[900][1], frames[3600][1]
        new15, new60 = frames[900][0][j]+900 == now, frames[3600][0][k]+3600 == now
        if h >= 0:
            output['h4_direction'][i] = frames[14400][1]['direction'][h]
        agreement, medium, small = int(h1['agreement'][k]), int(m15['direction'][j]), int(m5['direction'][i])
        if m5['gap'][i] or (new15 and m15['gap'][j]) or (new60 and h1['gap'][k]):
            episode, scenario_side = None, 0
            output['cancel_reason'][i] = 1
            continue
        if scenario_side and (agreement != scenario_side or medium != scenario_side):
            scenario_side = 0
        occupied_at_start = episode is not None
        if occupied_at_start:
            side = episode['side']
            lo, hi = data['prices'][i, 2], data['prices'][i, 1]
            status = (2 if (agreement, medium, small) != (side, side, side) else
                      3 if min(side*lo, side*hi) <= side*episode['stop'] else
                      4 if i-episode['index'] > 96 else 0)
            if status:
                episode = None
                output['cancel_reason'][i] = status
            else:
                target_cross = side * (1 if episode['stage'] != 1 else -1)
                if m5['cross'][i] == target_cross:
                    episode['stage'] += 1
                output['episode_phase'][i] = episode['stage']
                if episode['stage'] == 3:
                    record(0, i, episode)
                    episode = None
        if new15 and m15['reversal'][j] and m15['reversal'][j] == agreement:
            scenario_side, scenario_time = agreement, now
        if occupied_at_start or not scenario_side or episode is not None:
            continue
        side = scenario_side
        if now == scenario_time or m5['reversal'][i] != side or agreement != side:
            continue
        point = 'low' if side > 0 else 'high'
        price, known = m15[point][j]-side*tick, int(m15[point+'_known'][j])
        if not math.isfinite(price) or known > now or side*(data['prices'][i, 3]-price) <= 0:
            continue
        if min(side*data['prices'][i, 1], side*data['prices'][i, 2]) <= side*price:
            continue
        episode = dict(side=side, stop=price, index=i, known=now, scenario=scenario_time,
                       stop_known=known, stage=int(m5['cross'][i] == side))
        output['episode_phase'][i] = episode['stage']
        record(1, i, episode)
    return output


def simulate(data, sig, arm, rr, start, end, cost, account=None):
    """Signed-price execution, separately reconstructed from the protocol."""
    balance = float(account['initial_yen']) if account else 0.
    floor = float(account['stop_equity_yen']) if account else -math.inf
    peak, drawdown = balance, 0.
    stopped, position, liquidation_wait = False, None, False
    rows, open_marks = [], []
    skipped = dict(occupied=0, missing_open=0, invalid_risk=0, size=0)
    stamps, prices = data['times'], data['prices']
    last = None
    for i in np.flatnonzero((stamps >= start) & (stamps < end)):
        i, last = int(i), int(i)
        entry_signal = int(sig['sides'][arm, i-1]) if i and stamps[i-1] >= start else 0
        already_open = position is not None
        if entry_signal and already_open:
            skipped['occupied'] += 1
        elif entry_signal and not stopped:
            eligible = stamps[i]-stamps[i-1] == 300 and data['starts_at_open'][i] and data['complete'][i-1]
            if not eligible:
                skipped['missing_open'] += 1
            else:
                side, entry, stop = entry_signal, float(prices[i, 0]), float(sig['stops'][arm, i-1])
                risk = side*(entry-stop)
                if not math.isfinite(risk) or risk <= 0:
                    skipped['invalid_risk'] += 1
                else:
                    units, protection = 1, stop
                    if account:
                        cash_at_risk = max(0., min(account['risk_fraction']*balance, balance-floor))
                        allowable = min(cash_at_risk/(risk+cost), balance*account['max_leverage']/entry)
                        units = int(math.floor(allowable/account['quantity_step']+1e-12))*account['quantity_step']
                        if units > 0:
                            balance -= units*cost
                            signed_floor = side*entry-(balance-floor)/units
                            protection = side*max(side*stop, signed_floor)
                            drawdown = max(drawdown, peak-balance)
                    if units <= 0:
                        skipped['size'] += 1
                    else:
                        position = dict(side=side, entry=entry, stop=stop, protection=protection,
                                        target=entry+side*rr*risk, risk=risk, quantity=units, index=i,
                                        entry_time=int(stamps[i]), signal_time=int(stamps[i-1]+300),
                                        scenario_time=int(sig['scenario_times'][arm, i-1]),
                                        episode_time=int(sig['episode_times'][arm, i-1]))
        if position is None:
            continue
        trade = position
        side = trade['side']
        signed_open = side*float(prices[i, 0])
        signed_stop, signed_target = side*trade['protection'], side*trade['target']
        minimum = min(side*float(prices[i, 1]), side*float(prices[i, 2]))
        maximum = max(side*float(prices[i, 1]), side*float(prices[i, 2]))
        exit_price, reason, opening_fill = None, '', False
        if signed_open <= signed_stop:
            exit_price, reason, opening_fill = float(prices[i, 0]), 'stop_gap', True
        elif signed_open >= signed_target:
            exit_price, reason, opening_fill = trade['target'], 'target_gap', True
        elif liquidation_wait or (already_open and i and (stamps[i]-stamps[i-1] != 300 or not data['starts_at_open'][i])):
            exit_price, reason, opening_fill = float(prices[i, 0]), 'missing_next_open', True
        elif minimum <= signed_stop:
            exit_price = trade['protection']
            reason = 'floor' if account and trade['protection'] != trade['stop'] else 'stop'
        elif maximum >= signed_target:
            exit_price, reason = trade['target'], 'target'
        elif not data['complete'][i]:
            liquidation_wait = True
        elif i-trade['index'] >= 47:
            exit_price, reason = float(prices[i, 3]), 'time'
        if exit_price is None:
            continue
        gross = side*(exit_price-trade['entry'])
        row = dict(signal_time=trade['signal_time'], scenario_time=trade['scenario_time'],
                   episode_time=trade['episode_time'], entry_time=trade['entry_time'],
                   exit_time=int(data['observed_open_times'][i] if opening_fill else stamps[i]+300),
                   side=side, entry=trade['entry'], stop=trade['stop'], target=trade['target'],
                   exit=exit_price, risk=trade['risk'], cost=float(cost), gross_r=gross/trade['risk'],
                   net_r=(gross-cost)/trade['risk'], reason=reason, hold_bars=i-trade['index']+1,
                   exit_at_observed_open=bool(opening_fill))
        if account:
            balance += trade['quantity']*gross
            stopped = stopped or balance <= floor+1e-7
            peak = max(peak, balance)
            drawdown = max(drawdown, peak-balance)
            row.update(quantity=trade['quantity'], fees_yen=trade['quantity']*cost,
                       pnl_yen=trade['quantity']*(gross-cost), equity_yen=balance,
                       floor_stop=trade['protection'])
        rows.append(row)
        position, liquidation_wait = None, False
    if position is not None and last is not None:
        trade = position
        price = float(prices[last, 3])
        delta = trade['side']*(price-trade['entry'])
        mark = dict(entry_time=trade['entry_time'], mark_time=int(stamps[last]+300), side=trade['side'],
                    entry=trade['entry'], mark=price, stop=trade['stop'], target=trade['target'],
                    gross_r=delta/trade['risk'], net_r=(delta-cost)/trade['risk'],
                    reason='OPEN_MARK', pending_gap=bool(liquidation_wait))
        if account:
            mark.update(quantity=trade['quantity'], marked_equity_yen=balance+trade['quantity']*delta)
        open_marks.append(mark)
    summary = dict(skipped=skipped, open_marks=open_marks)
    if account:
        summary.update(initial_yen=account['initial_yen'], cash_equity_yen=balance,
                       marked_equity_yen=open_marks[-1]['marked_equity_yen'] if open_marks else balance,
                       halted=stopped, max_closed_drawdown_yen=drawdown,
                       accounting='round-trip cost at entry; marked equity separates open P/L; resting floor stop; gap overshoot retained')
    return rows, summary


def compare(actual, expected, location='root'):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), (location, actual.keys(), expected.keys())
        for key in expected:
            compare(actual[key], expected[key], f'{location}.{key}')
    elif isinstance(expected, (tuple, list)):
        assert len(actual) == len(expected), (location, len(actual), len(expected))
        for i, value in enumerate(expected):
            compare(actual[i], value, f'{location}[{i}]')
    elif isinstance(expected, (bool, np.bool_)):
        assert actual == expected or actual == str(bool(expected)), (location, actual, expected)
    elif isinstance(expected, (int, float, np.number)):
        x, y = float(actual), float(expected)
        assert (math.isnan(x) and math.isnan(y)) or math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-7), (location, x, y)
    else:
        assert actual == expected, (location, actual, expected)


def metrics(rows):
    values = [r['net_r'] for r in rows]
    positive, negative = [x for x in values if x > 0], [x for x in values if x < 0]
    n, w, lost = len(values), len(positive), len(negative)
    gains, losses = sum(positive), -sum(negative)
    cumulative, peak, dd = 0., 0., 0.
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        dd = max(dd, peak-cumulative)
    interval = [None, None]
    if n:
        z = 1.959963984540054
        denominator = 1+z*z/n
        center = (w/n+z*z/(2*n))/denominator
        radius = z*math.sqrt((w/n)*(1-w/n)/n+z*z/(4*n*n))/denominator
        interval = [center-radius, center+radius]
    return dict(trades=n, wins=w, losses=lost, breakevens=n-w-lost,
                win_rate=w/n if n else None, wilson95=interval,
                pf=gains/losses if losses else None, pf_infinite=bool(gains > 0 and losses == 0),
                mean_net_r=sum(values)/n if n else None, sum_net_r=float(sum(values)),
                realized_avg_win_loss=(gains/w)/(losses/lost) if w and lost else None,
                max_closed_dd_r=dd)


def gates(pooled, records, accounts, protocol):
    criteria = protocol['gate']
    result = {}
    def pf(stats):
        return math.inf if stats['pf_infinite'] else stats['pf'] or 0
    for phase in protocol['periods']:
        normal = pooled[f'{phase}_ema3_rr1_cost1']
        stress = pooled[f'{phase}_ema3_rr1_cost2']
        baseline = pooled[f'{phase}_direct_rr1_cost1']
        pairs = [r for r in records if (r['phase'], r['arm'], r['rr'], r['cost_multiplier']) == (phase, 'ema3', 1, 1)]
        checks = dict(count=normal['trades'] >= criteria['every_period_pooled_trades_min'],
                      per_symbol_count=all(r['trades'] >= criteria['every_period_symbol_trades_min'] for r in pairs),
                      normal_pf=pf(normal) >= criteria['normal_pf_min'],
                      normal_mean=(normal['mean_net_r'] or 0) > criteria['normal_mean_net_r_min_exclusive'],
                      stress_pf=pf(stress) > criteria['stress_pf_min_exclusive'],
                      stress_mean=(stress['mean_net_r'] or 0) > criteria['stress_mean_net_r_min_exclusive'],
                      profitable_pairs=sum(r['sum_net_r'] > 0 for r in pairs) >= criteria['profitable_symbols_min'],
                      better_than_direct=normal['mean_net_r'] is not None and baseline['mean_net_r'] is not None and normal['mean_net_r'] > baseline['mean_net_r'],
                      drawdown=normal['max_closed_dd_r'] <= criteria['every_period_primary_pooled_max_closed_dd_r'],
                      continuous_no_halt=not accounts['ema3_rr1_cost1']['halted'])
        result[phase] = dict(checks=checks, passed=all(checks.values()))
    return result


def assert_signal_archive(path, actual, times):
    with np.load(path, allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved['times'], times)
        assert set(saved.files) == set(actual) | {'times'}
        for key, value in actual.items():
            np.testing.assert_allclose(saved[key], value, rtol=1e-12, atol=1e-10, equal_nan=True,
                                       err_msg=f'{path.name}.{key}')


def check_csv(path, rows):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        saved = list(csv.DictReader(stream))
    compare(saved, rows, path.name)


def run():
    started = datetime.now(timezone.utc).isoformat()
    protocol_file = DOC/'protocol.json'
    protocol = json.loads(protocol_file.read_text(encoding='utf-8'))
    assert protocol['status'] == 'SPEC_FROZEN'
    research = OUT/'research'
    manifest = json.loads((research/'manifest.json').read_text(encoding='utf-8'))
    assert manifest.get('finished_utc'), 'Research output is incomplete'
    assert digest(protocol_file) == manifest['protocol_sha256']
    for path, sha in protocol['frozen_file_sha256'].items():
        assert digest(ROOT/path) == sha, f'Frozen source drift: {path}'
    for path, sha in manifest['output_sha256'].items():
        assert digest(research/path) == sha, f'Output drift: {path}'
    actual = json.loads((research/'results.json').read_text(encoding='utf-8'))
    records, pooled_rows, accounts = [], {}, {}
    counts = dict(input_rows=0, signal_observations=0, trade_observations=0, prefix_checks=0, open_marks=0)
    for symbol in protocol['symbols']:
        path = ROOT/protocol['cache_directory']/f'{symbol}_m5.npz'
        assert digest(path) == protocol['input_sha256'][symbol]
        with np.load(path, allow_pickle=False) as archive:
            selected = (archive['times'] >= epoch(protocol['warmup_start'])) & (archive['times'] < epoch(protocol['continuous_period'][1]))
            data = {key: archive[key][selected] for key in archive.files}
        counts['input_rows'] += len(data['times'])
        prepared = features(data)
        for phase, period in protocol['periods'].items():
            start, end = map(epoch, period)
            sig = signals(data, protocol['tick'][symbol], start, end, prepared)
            assert_signal_archive(research/f'{symbol}_{phase}_signals.npz', sig, data['times'])
            counts['signal_observations'] += int(np.count_nonzero(sig['sides']))
            for a, arm in enumerate(ARMS):
                for rr in protocol['reward_risk']:
                    for multiple in protocol['cost_multipliers']:
                        cost = protocol['round_trip_pips'][symbol]*protocol['pip'][symbol]*multiple
                        rows, detail = simulate(data, sig, a, rr, start, end, cost)
                        key = f'{phase}_{arm}_rr{rr:g}_cost{multiple}'
                        check_csv(research/f'{symbol}_{key}.csv', rows)
                        counts['trade_observations'] += len(rows)
                        counts['open_marks'] += len(detail['open_marks'])
                        pooled_rows.setdefault(key, []).extend(dict(symbol=symbol, **r) for r in rows)
                        annual = []
                        for year in range(int(period[0][:4]), int(period[1][:4])):
                            chosen = [r for r in rows if epoch(f'{year}-01-01') <= r['exit_time']-(0 if r['reason'] in ('stop_gap', 'target_gap', 'missing_next_open') else 1) < epoch(f'{year+1}-01-01')]
                            annual.append(dict(year=year, **metrics(chosen)))
                        record = dict(symbol=symbol, phase=phase, arm=arm, rr=rr, cost_multiplier=multiple,
                                      **metrics(rows), annual=annual, open_marks=detail['open_marks'], skipped=detail['skipped'])
                        stored = next(r for r in actual['records'] if (r['symbol'], r['phase'], r['arm'], r['rr'], r['cost_multiplier']) == (symbol, phase, arm, rr, multiple))
                        compare(stored, record, f'{symbol}.{key}')
                        records.append(record)
        start, end = map(epoch, protocol['continuous_period'])
        continuous = signals(data, protocol['tick'][symbol], start, end, prepared)
        for length in (10_001, 100_003, 300_007):
            if length >= len(data['times']):
                continue
            cut = {key: value[:length] for key, value in data.items()}
            prefix = signals(cut, protocol['tick'][symbol], start, end)
            for key, value in prefix.items():
                np.testing.assert_allclose(value, continuous[key][..., :length], rtol=1e-12, atol=1e-10, equal_nan=True,
                                           err_msg=f'prefix.{symbol}.{length}.{key}')
            counts['prefix_checks'] += 1
        if symbol == protocol['account']['symbol']:
            assert_signal_archive(research/f'{symbol}_continuous_signals.npz', continuous, data['times'])
            for a, arm in enumerate(ARMS):
                for rr in protocol['reward_risk']:
                    for multiple in (1, 2):
                        cost = protocol['round_trip_pips'][symbol]*protocol['pip'][symbol]*multiple
                        rows, detail = simulate(data, continuous, a, rr, start, end, cost, protocol['account'])
                        key = f'{arm}_rr{rr:g}_cost{multiple}'
                        check_csv(research/f'USDJPY_continuous_account_{key}.csv', rows)
                        accounts[key] = dict(**detail, **metrics(rows))
                        compare(actual['continuous_usdjpy'][key], accounts[key], f'account.{key}')
                        counts['trade_observations'] += len(rows)
        print(f'INDEPENDENT_REPLAY_OK {symbol}', flush=True)
    pooled = {}
    for key, rows in pooled_rows.items():
        rows.sort(key=lambda row: (row['exit_time'], row['symbol'], row['entry_time']))
        pooled[key] = metrics(rows)
    compare(actual['pooled'], pooled, 'pooled')
    checked_gates = gates(pooled, records, accounts, protocol)
    compare(actual['gates'], checked_gates, 'gates')
    target = OUT/'independent'
    target.mkdir(parents=True, exist_ok=False)
    result = dict(status='ALL_MATCH', started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                  protocol_sha256=digest(protocol_file), research_results_sha256=digest(research/'results.json'),
                  validator_sha256=digest(Path(__file__)), counts=counts, gates=checked_gates,
                  records=records, pooled=pooled, continuous_usdjpy=accounts)
    path = target/'results.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print('INDEPENDENT_RESULT_JSON='+str(path), flush=True)


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
