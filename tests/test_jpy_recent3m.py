from types import SimpleNamespace
from research_jpy_recent3m import month_index, passes


def test_entry_month_boundaries():
    for date,index in [('2026-06-08T00:15:00',0),('2026-07-07T23:45:00',0),
                       ('2026-07-08T00:00:00',1),('2026-08-08T00:00:00',2),('2026-09-07T23:45:00',2)]:
        assert month_index(SimpleNamespace(entry_time=date))==index


def test_screen_rejects_sparse_or_losing_month():
    summary={'trades':75,'net_win_rate_pct':70,'profit_factor':1.5,'expectancy_r':0.3,'realized_drawdown_pct':5}
    months=[{'trades':25,'net_r':1} for _ in range(3)]
    assert passes(summary,months,75)
    assert not passes({**summary,'trades':74},months,75)
    assert not passes(summary,[*months[:2],{'trades':9,'net_r':1}],75)
    assert not passes(summary,[*months[:2],{'trades':25,'net_r':0}],75)
    assert not passes({**summary,'profit_factor':None},months,75)
