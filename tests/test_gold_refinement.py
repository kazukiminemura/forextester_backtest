from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from forextester_backtest.models import Bar
from forextester_backtest.gold_signals import features
from forextester_backtest.gold_refinement import ENTRY_MODES, entry_signals, managed_outcome

BASE = datetime(2020,1,1,8)


def bar(i,op=100,hi=100.2,lo=99.8):
    return Bar(BASE+timedelta(hours=i),op,hi,lo,op,1)


def test_breakeven_is_not_retroactively_active_on_trigger_bar():
    result = managed_outcome([bar(0,hi=102,lo=99.8),bar(1,op=102,hi=103.1,lo=100.2)],0,1,1,0,"breakeven")
    assert result[:3] == (1,2,"target")


def test_breakeven_after_cost_is_a_small_loss():
    result = managed_outcome([bar(0,hi=102),bar(1,op=100.7,hi=100.8,lo=100)],0,1,1,.1,"breakeven")
    assert result[1] == pytest.approx(-.01/1.5)


def test_partial_exit_counts_one_trade_and_weighted_profit():
    result = managed_outcome([bar(0,hi=103.5)],0,1,1,0,"half1R")
    assert result[1] == 1.5
    result = managed_outcome([bar(0,hi=102),bar(1,lo=98)],0,1,1,0,"half1R")
    assert result[1] == 0
    result = managed_outcome([bar(0,hi=102),bar(1,op=100.5,lo=99)],0,1,1,0,"half1R_breakeven")
    assert result[1] == .5


def test_stop_first_both_directions_before_partial_target():
    for side in (-1,1):
        result = managed_outcome([bar(0,hi=104,lo=96)],0,side,1,0,"half1R_breakeven")
        assert result[1:3] == (-1,"stop")


def test_deadline_pays_partial_at_limit_then_remaining_at_market():
    result = managed_outcome([bar(0),bar(12,op=102,hi=102.2,lo=101.8)],0,1,1,0,"half1R_breakeven")
    assert result[1] == pytest.approx(.5 + .5*2/1.5)
    assert result[2] == "time"


def test_retest_is_later_than_breakout_and_expires_on_date_change():
    f = pd.DataFrame(dict(open=np.full(210,100.),high=np.full(210,101.),low=np.full(210,99.),close=np.full(210,100.),
                         ema20=np.full(210,99.),ema50=np.full(210,95.),ema200=np.linspace(80,90,210),atr=np.ones(210),
                         prior_high55=np.full(210,104.),prior_low55=np.full(210,96.)))
    f.loc[205,["open","high","low","close"]] = [104.5,106,104.3,105]
    f.loc[206,["open","high","low","close"]] = [104.4,105,103.9,104.8]
    dates = [BASE.date()]*len(f)
    actual = entry_signals(f,dates,"retest3")
    assert actual[205] == 0
    assert actual[206] == 1
    dates[206] += timedelta(days=1)
    assert entry_signals(f,dates,"retest3")[206] == 0


def test_all_entry_modes_are_prefix_causal():
    prices = 100+np.arange(400)*.02+np.sin(np.arange(400)*.08)*3
    bars = [Bar(BASE+timedelta(minutes=30*i),p-.1,p+.2,p-.2,p,1) for i,p in enumerate(prices)]
    full,short = features(bars),features(bars[:300])
    dates = [b.time.date() for b in bars]
    for mode in ENTRY_MODES:
        np.testing.assert_array_equal(entry_signals(full,dates,mode)[:300],entry_signals(short,dates[:300],mode))


@pytest.mark.parametrize("direction", [-1, 1])
def test_refined_pine_conditions_match_selected_entry_logic(direction):
    import re
    from pathlib import Path
    from forextester_backtest.sniper import Technicals
    source = (Path(__file__).resolve().parents[1]/"scripts/tradingview/gold_breakout55_pf_refined.pine").read_text(encoding="utf-8")
    expressions = {name:re.search(rf"^bool {name} = (.+)$",source,re.M)[1].replace("slow[5]","previous_slow") for name in ("ready","buySetup","sellSetup")}
    prices = 100+direction*(np.arange(700)*.03+np.sin(np.arange(700)*.08)*3)
    bars = [Bar(BASE+timedelta(hours=i),p-direction*.25,p+(.05 if direction==1 else .3),
                p-(.3 if direction==1 else .05),p,1) for i,p in enumerate(prices)]
    f = features(bars)
    ta = Technicals(dict(atrLength=14,emaLength=200,rsiLength=14,dmiLength=14,stFactor=3))
    actual,adx = [],[]
    for i,row in f.iterrows():
        ta.update(bars[i])
        adx.append(ta.adx)
        env = dict(bar_index=i,a=row.atr,fast=row.ema50,slow=row.ema200,close=row.close,open=row.open,high=row.high,low=row.low,
                   adx=ta.adx,priorHigh=row.prior_high55,priorLow=row.prior_low55,previous_slow=f.iloc[i-5].ema200 if i>=5 else float("nan"))
        for key,expr in expressions.items():
            env[key] = eval(expr,{"__builtins__":{}},env)
        actual.append(1 if env["buySetup"] else -1 if env["sellSetup"] else 0)
    expected = entry_signals(f,[b.time.date() for b in bars],"impulse")
    expected = np.where(np.asarray(adx)>=18,expected,0)
    assert np.any(expected == direction)
    np.testing.assert_array_equal(actual,expected)


def test_minute_capture_preserves_late_exit_and_next_day_history():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
    from research_gold_minute_execution import capture_days
    quotes = [bar(11),bar(16),bar(36)]
    day1,day2 = quotes[0].time.date(),quotes[1].time.date()
    captured = capture_days(iter(quotes),{day1,day2})
    assert captured[day1] == quotes[:2]
    assert captured[day2] == quotes[1:]
