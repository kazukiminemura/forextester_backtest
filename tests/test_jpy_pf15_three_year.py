from types import SimpleNamespace
from research_jpy_pf15_three_year import month_index,START,END,WINDOWS


def test_rolling_months():
    for date,expected in [('2023-09-08T00:15:00',0),('2023-10-07T23:45:00',0),
                          ('2023-10-08T00:00:00',1),('2024-09-07T23:45:00',11),
                          ('2024-09-08T00:00:00',12),('2026-09-07T23:45:00',35)]:
        assert month_index(SimpleNamespace(entry_time=date))==expected
    assert START.isoformat()=='2023-09-08T00:00:00'
    assert END.isoformat()=='2026-09-08T00:00:00'
    assert len(WINDOWS)==6
