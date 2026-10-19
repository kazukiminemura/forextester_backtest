from datetime import datetime
from revalidate_quant70_jpy import protocol, month_count, SYMBOLS
from quant70_intraday_signals import candidates, comparators


def test_refreshed_scope_and_execution():
    p = protocol()
    assert SYMBOLS == ['AUDJPY','CHFJPY','EURJPY','GBPJPY','NZDJPY']
    assert p['gates']['min_positive_pairs'] == 4
    assert p['gates']['net_win_rate_pct'] == 70
    assert p['execution']['reward_risk_ratio'] == 1
    assert p['execution']['full_exit']
    assert p['execution']['slippage_pips_each_side'] == 0.1
    assert not p['live_trading_authorized']
    assert 'Diagnostic' in p['selection']


def test_month_counts():
    assert month_count(datetime(2010,1,1),datetime(2019,1,1)) == 108
    assert month_count(datetime(2025,1,1),datetime(2026,9,8)) == 20+7/30


def test_frozen_candidate_budget():
    assert len(candidates()) == len(comparators()) == 12
    assert {c['comparison_of'] for c in comparators()} == {c['name'] for c in candidates()}
