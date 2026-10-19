"""Read-only independent accounting audit; writes only a new audit result."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/quant_organization/experiments/bari_video_20261016'
RUN = ROOT / 'agent_runs/bari_video_20261016/research'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def near(a, b):
    assert (a is None and b is None) or (a is not None and b is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-8)), (a, b)


def stats(rows):
    r = [x['net_r'] for x in rows]
    winners = [x for x in r if x > 0]
    losers = [-x for x in r if x < 0]
    n, w, l = len(r), len(winners), len(losers)
    profit, loss = math.fsum(winners), math.fsum(losers)
    equity = high = dd = 0.
    for x in r:
        equity += x
        high = max(high, equity)
        dd = max(dd, high-equity)
    interval = [None, None]
    if n:
        z = 1.959963984540054
        z2 = z*z
        midpoint = (w+z2/2)/(n+z2)
        radius = z*math.sqrt(w*(n-w)/n+z2/4)/(n+z2)
        interval = [midpoint-radius, midpoint+radius]
    return dict(trades=n, wins=w, losses=l, breakevens=n-w-l,
                win_rate=w/n if n else None, wilson95=interval,
                pf=profit/loss if loss else None, pf_infinite=profit > 0 and loss == 0,
                mean_net_r=math.fsum(r)/n if n else None, sum_net_r=math.fsum(r),
                realized_avg_win_loss=(profit/w)/(loss/l) if w and l else None,
                max_closed_dd_r=dd)


def check_stats(rows, record):
    for key, value in stats(rows).items():
        if isinstance(value, list):
            for actual, expected in zip(value, record[key]):
                near(actual, expected)
        elif isinstance(value, bool):
            assert value == record[key]
        else:
            near(value, record[key])


def rows_at(path):
    with path.open(encoding='utf-8', newline='') as f:
        return [{key: value if key == 'reason' else value == 'True' if key == 'exit_at_observed_open' else float(value) for key, value in row.items()}
                for row in csv.DictReader(f)]


def run():
    protocol, manifest, result = load(DOC/'protocol.json'), load(RUN/'manifest.json'), load(RUN/'results.json')
    assert manifest['protocol_sha256'] == sha(DOC/'protocol.json')
    for path, expected in protocol['frozen_file_sha256'].items():
        assert sha(ROOT/path) == expected, path
    for symbol, expected in protocol['input_sha256'].items():
        assert sha(ROOT/protocol['cache_directory']/f'{symbol}_m5.npz') == expected, symbol
    for path, expected in manifest['output_sha256'].items():
        assert sha(RUN/path) == expected, path
    assert datetime.fromisoformat(manifest['started_utc']) <= datetime.fromisoformat(manifest['finished_utc'])
    freeze = protocol['frozen_at']
    assert freeze is not None, 'Missing documented freeze timestamp'
    assert datetime.fromisoformat(freeze.replace('Z', '+00:00')) < datetime.fromisoformat(manifest['started_utc'])
    pool, row_count = {}, 0
    for record in result['records']:
        symbol, phase, arm, rr, multiple = (record[k] for k in ('symbol', 'phase', 'arm', 'rr', 'cost_multiplier'))
        key = f'{phase}_{arm}_rr{rr:g}_cost{multiple}'
        rows = rows_at(RUN/f'{symbol}_{key}.csv')
        row_count += len(rows)
        cost = protocol['round_trip_pips'][symbol]*protocol['pip'][symbol]*multiple
        prior_exit = -math.inf
        for row in rows:
            assert row['reason'] != 'OPEN_MARK'
            assert row['scenario_time'] < row['episode_time'] <= row['signal_time'] == row['entry_time'] <= row['exit_time']
            assert row['entry_time'] >= prior_exit
            prior_exit = row['exit_time']
            near(row['risk'], row['side']*(row['entry']-row['stop']))
            assert row['risk'] > 0
            near(row['target'], row['entry']+row['side']*rr*row['risk'])
            near(row['cost'], cost)
            near(row['gross_r'], row['side']*(row['exit']-row['entry'])/row['risk'])
            near(row['net_r'], row['gross_r']-cost/row['risk'])
        check_stats(rows, record)
        for annual in record['annual']:
            yr = annual['year']
            subset = [row for row in rows if datetime.fromtimestamp(row['exit_time']-(0 if row['exit_at_observed_open'] else 1), timezone.utc).year == yr]
            check_stats(subset, annual)
        for mark in record['open_marks']:
            assert mark['reason'] == 'OPEN_MARK'
            risk = abs(mark['entry']-mark['stop'])
            near(mark['gross_r'], mark['side']*(mark['mark']-mark['entry'])/risk)
            near(mark['net_r'], mark['gross_r']-cost/risk)
        pool.setdefault(key, []).extend(dict(symbol=symbol, **row) for row in rows)
    for key, rows in pool.items():
        rows.sort(key=lambda x: (x['exit_time'], x['symbol'], x['entry_time']))
        check_stats(rows, result['pooled'][key])
        for annual in result['pooled_annual'][key]:
            subset = [row for row in rows if datetime.fromtimestamp(row['exit_time']-(0 if row['exit_at_observed_open'] else 1), timezone.utc).year == annual['year']]
            check_stats(subset, annual)
    account_rows = 0
    for key, record in result['continuous_usdjpy'].items():
        rows = rows_at(RUN/f'USDJPY_continuous_account_{key}.csv')
        account_rows += len(rows)
        cash, peak, dd = float(protocol['account']['initial_yen']), float(protocol['account']['initial_yen']), 0.
        floor, halted = protocol['account']['stop_equity_yen'], False
        for row in rows:
            assert not halted
            qty = row['quantity']
            assert qty > 0 and qty % protocol['account']['quantity_step'] == 0
            assert qty*row['entry'] <= cash*protocol['account']['max_leverage']+1e-7
            assert qty*(row['risk']+row['cost']) <= min(cash*protocol['account']['risk_fraction'], cash-floor)+1e-7
            near(row['fees_yen'], qty*row['cost'])
            near(row['pnl_yen'], qty*row['side']*(row['exit']-row['entry'])-row['fees_yen'])
            near(row['gross_r'], row['side']*(row['exit']-row['entry'])/row['risk'])
            near(row['net_r'], row['gross_r']-row['cost']/row['risk'])
            after_fee = cash-row['fees_yen']
            fprice = row['entry']+row['side']*(floor-after_fee)/qty
            expected_stop = max(row['stop'], fprice) if row['side'] == 1 else min(row['stop'], fprice)
            near(row['floor_stop'], expected_stop)
            dd = max(dd, peak-after_fee)
            cash += row['pnl_yen']
            near(cash, row['equity_yen'])
            peak = max(peak, cash)
            dd = max(dd, peak-cash)
            halted = cash <= floor+1e-7
        for mark in record['open_marks']:
            multiple = int(key.rsplit('cost', 1)[1])
            cost = protocol['round_trip_pips']['USDJPY']*protocol['pip']['USDJPY']*multiple
            cash -= mark['quantity']*cost
            dd = max(dd, peak-cash)
            near(mark['marked_equity_yen'], cash+mark['quantity']*mark['side']*(mark['mark']-mark['entry']))
        near(cash, record['cash_equity_yen'])
        near(dd, record['max_closed_drawdown_yen'])
        assert halted == record['halted']
        check_stats(rows, record)
    gate = protocol['gate']
    for phase, reported in result['gates'].items():
        a = result['pooled'][f'{phase}_ema3_rr1_cost1']
        b = result['pooled'][f'{phase}_ema3_rr1_cost2']
        c = result['pooled'][f'{phase}_direct_rr1_cost1']
        pairs = [r for r in result['records'] if r['phase'] == phase and r['arm'] == 'ema3' and r['rr'] == 1 and r['cost_multiplier'] == 1]
        assert len(pairs) == len(protocol['symbols'])
        pf = lambda r: math.inf if r['pf_infinite'] else r['pf'] or 0.
        checks = dict(count=a['trades'] >= gate['every_period_pooled_trades_min'],
                      per_symbol_count=all(r['trades'] >= gate['every_period_symbol_trades_min'] for r in pairs),
                      normal_pf=pf(a) >= gate['normal_pf_min'],
                      normal_mean=a['mean_net_r'] is not None and a['mean_net_r'] > gate['normal_mean_net_r_min_exclusive'],
                      stress_pf=pf(b) > gate['stress_pf_min_exclusive'],
                      stress_mean=b['mean_net_r'] is not None and b['mean_net_r'] > gate['stress_mean_net_r_min_exclusive'],
                      profitable_pairs=sum(r['sum_net_r'] > 0 for r in pairs) >= gate['profitable_symbols_min'],
                      better_than_direct=a['mean_net_r'] is not None and c['mean_net_r'] is not None and a['mean_net_r'] > c['mean_net_r'],
                      drawdown=a['max_closed_dd_r'] <= gate['every_period_primary_pooled_max_closed_dd_r'],
                      continuous_no_halt=not result['continuous_usdjpy']['ema3_rr1_cost1']['halted'])
        assert checks == reported['checks'] and all(checks.values()) == reported['passed']
    evidence = dict(status='AUDIT_ACCOUNTING_MATCH', records=len(result['records']), csv_rows=row_count,
                    pooled=len(pool), accounts=len(result['continuous_usdjpy']), account_rows=account_rows,
                    protocol_sha256=sha(DOC/'protocol.json'), research_results_sha256=sha(RUN/'results.json'),
                    script_sha256=sha(Path(__file__)), limits='Accounting and hashes; full signal replay delegated to independent validator; research adoption not implied')
    target = RUN.parent/'quality_accounting.json'
    with target.open('x', encoding='utf-8') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print(json.dumps(evidence))


if __name__ == '__main__':
    run()
