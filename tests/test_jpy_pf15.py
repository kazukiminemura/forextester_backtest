import numpy as np
from research_jpy_pf15 import filter_entries,screen,WINDOWS


def test_signal_clock_edges_and_no_mutation():
    d=np.array([1,-1,1,-1]); hours=np.array([0,7,8,23])
    np.testing.assert_array_equal(filter_entries(d,hours,0,8),[1,-1,0,0])
    np.testing.assert_array_equal(filter_entries(d,hours,8,24),[0,0,1,-1])
    np.testing.assert_array_equal(d,[1,-1,1,-1])
    assert len(WINDOWS)==6


def test_pf_screen_does_not_require_seventy_percent():
    s={'trades':90,'net_win_rate_pct':61,'profit_factor':1.55,'expectancy_r':0.2,'realized_drawdown_pct':5}
    months=[{'trades':30,'net_r':1}]*3
    assert screen(s,months,75)
    assert not screen({**s,'profit_factor':1.49},months,75)
    assert not screen({**s,'trades':29},months,30)
    assert not screen(s,[*months[:2],{'trades':30,'net_r':-1}],75)
