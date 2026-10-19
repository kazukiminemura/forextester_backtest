"""Training-only descriptive attribution of already saved stock trades; no tuning."""
from collections import Counter
import csv
import json
from pathlib import Path
from statistics import mean, median

import research_tamukai_stocks_daily as base
from stock_data_cache import CACHE, verify

ROOT = base.ROOT
SOURCE = ROOT / 'agent_runs/tamukai_stocks_jev_20260926/results/training/main'
OUT = ROOT / 'agent_runs/tamukai_stocks_deep_20260926/diagnostics'


def describe(rows):
    if not rows:
        return {'trades': 0}
    gross_win = sum(max(r['gross_pnl'], 0) for r in rows)
    gross_loss = -sum(min(r['gross_pnl'], 0) for r in rows)
    wins = sum(max(r['net_pnl'], 0) for r in rows)
    losses = -sum(min(r['net_pnl'], 0) for r in rows)
    return dict(trades=len(rows), net_pnl=sum(r['net_pnl'] for r in rows),
                gross_pnl=sum(r['gross_pnl'] for r in rows), fees=sum(r['fees'] for r in rows),
                net_pf=wins / losses if losses else 'undefined',
                gross_pf=gross_win / gross_loss if gross_loss else 'undefined',
                win_rate_pct=100 * sum(r['net_pnl'] > 0 for r in rows) / len(rows),
                mean_net_R=mean(r['net_R'] for r in rows), mean_cost_R=mean(r['cost_R'] for r in rows),
                median_stop_pct=median(r['stop_pct'] for r in rows),
                mean_gap_pct=mean(r['gap_pct'] for r in rows), mean_abs_gap_pct=mean(abs(r['gap_pct']) for r in rows),
                median_holding_sessions=median(r['holding_sessions'] for r in rows),
                mean_holding_sessions=mean(r['holding_sessions'] for r in rows),
                same_session_exits=sum(r['holding_sessions'] == 1 for r in rows),
                exit_reasons=dict(Counter(r['reason'] for r in rows)))


def enrich(trade, bars):
    index = {b.time.date().isoformat(): i for i, b in enumerate(bars)}
    si, ei, xi = (index[trade[k]] for k in ('signal_date', 'entry_date', 'exit_date'))
    entry, stop, units = (float(trade[k]) for k in ('entry', 'stop', 'units'))
    risk = units * (entry - stop)
    if not risk > 0 or si >= ei or xi < ei:
        raise ValueError('Invalid saved trade')
    fees = float(trade['entry_cost']) + float(trade['exit_cost'])
    net = float(trade['net_pnl'])
    stop_pct = 100 * (entry - stop) / entry
    return dict(symbol=trade['symbol'], signal_date=trade['signal_date'], entry_date=trade['entry_date'],
                exit_date=trade['exit_date'], reason=trade['reason'], net_pnl=net,
                gross_pnl=net + fees, fees=fees, net_R=net / risk, cost_R=fees / risk,
                stop_pct=stop_pct, gap_pct=100 * (entry / bars[si].close - 1),
                holding_sessions=xi - ei + 1,
                width_bucket='<1%' if stop_pct < 1 else '1-2%' if stop_pct < 2 else '2-4%' if stop_pct < 4 else '>=4%')


def main():
    verify(CACHE)
    OUT.mkdir(parents=True, exist_ok=True)
    result = dict(scope='2017-2019 training only; descriptive bins, not new strategy returns',
                  notes='Fees on actual saved units/fills, not a zero-cost counterfactual. Equal-trade net_R differs from money PF. Gap is signal close to next open, not live slippage.',
                  source_sha256=base.sha256(Path(__file__)), input_sha256={}, results={})
    for candidate in ('baseline', 'no_dow', 'prior_day_breakout', 'sma63_trend'):
        rows = []
        for path in sorted((SOURCE / candidate).glob('*_trades.csv')):
            symbol = path.name.removesuffix('_trades.csv')
            bars = [b for b in base.read_bars(CACHE / f'{symbol}.csv') if b.time.year <= 2019]
            result['input_sha256'][str(path.relative_to(ROOT))] = base.sha256(path)
            with path.open(encoding='utf-8-sig', newline='') as stream:
                rows += [enrich(dict(symbol=symbol, **t), bars) for t in csv.DictReader(stream)]
        if not rows:
            raise ValueError('Expected saved training trades')
        base.write_csv(OUT / f'{candidate}_features.csv', rows, list(rows[0]))
        result['results'][candidate] = dict(overall=describe(rows),
            width={label: describe([r for r in rows if r['width_bucket'] == label]) for label in ('<1%', '1-2%', '2-4%', '>=4%')},
            exits={reason: describe([r for r in rows if r['reason'] == reason]) for reason in sorted({r['reason'] for r in rows})},
            gap={label: describe([r for r in rows if (r['gap_pct'] > 0) == up]) for label, up in [('up', True), ('flat_or_down', False)]})
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result['results'], indent=2))


if __name__ == '__main__':
    main()
