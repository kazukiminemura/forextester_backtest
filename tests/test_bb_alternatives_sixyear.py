import sys
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import research_bb_alternatives as original
import research_bb_alternatives_sixyear as study


def test_fixed_periods_and_no_strategy_reimplementation():
    spans=study.periods()
    assert list(spans)==["all","2020","2021","2022","2023","2024","2025","overlap"]
    assert spans["all"]==(1577836800,1767225600)
    assert spans["overlap"]==(1672531200,1767225600)
    assert all(spans[str(y)][1]==spans[str(y+1)][0] for y in range(2020,2025))
    assert 7*len(study.POLICIES)*len(study.COSTS)*len(spans)==336
    assert study.execute is original.execute
    assert study.reentry_signals is original.reentry_signals
    assert study.wm_signals is original.wm_signals


def test_normalize_index_shift_but_not_prices():
    a=[dict(index=1,entry_index=2,first=0,target=5.1)]
    b=[dict(index=3,entry_index=4,first=2,target=5.1)]
    assert study.normalize_indices(a,np.array([300,600,900]))==study.normalize_indices(b,np.array([-300,0,300,600,900]))


def test_all_six_years_are_gated():
    totals={}
    for p in study.POLICIES:
        for cost in study.COSTS:
            totals[study.arm_name(p,cost)]={str(y):dict(trades=100,profit_factor_r=1.2,average_r=.1,net_plus_open_r=1,positive_pairs=4) for y in range(2020,2026)}
            totals[study.arm_name(p,cost)]["all"]={"bar_close_mtm_drawdown_r":10}
    assert all(all(g.values()) for g in study.gates_for(totals,"wm").values())
    totals[study.arm_name("wm",1.)]["2020"]["trades"]=99
    assert not study.gates_for(totals,"wm")["2020"]["count"]


def test_overlap_summary_rejects_changed_pl():
    import pytest
    study.assert_summary_equal({"net_r":1.0},{"net_r":1.0})
    with pytest.raises(AssertionError):
        study.assert_summary_equal({"net_r":2.0},{"net_r":1.0})
