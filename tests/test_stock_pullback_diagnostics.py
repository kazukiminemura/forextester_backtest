import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from diagnose_stock_pullbacks import base, describe, enrich


def test_trade_attribution_preserves_accounting_and_session_dates():
    bars = [base.Bar(datetime(2019, 1, d), 100, 103, 97, 100, 10) for d in (4, 7, 8)]
    trade = dict(symbol='X', signal_date='2019-01-04', entry_date='2019-01-07', exit_date='2019-01-08',
                 entry=101, exit=103, stop=99, units=10, entry_cost=1.01, exit_cost=1.03, net_pnl=17.96, reason='target')
    row = enrich(trade, bars)
    assert row['holding_sessions'] == 2
    assert abs(row['gap_pct'] - 1) < 1e-10
    assert abs(row['gross_pnl'] - 20) < 1e-10
    assert abs(row['net_R'] + row['cost_R'] - 1) < 1e-10
    assert describe([row])['trades'] == 1
    assert describe([]) == {'trades': 0}
