from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from forextester_backtest.gold_signals import FAMILIES, features, signals
from forextester_backtest.models import Bar


def test_future_bars_cannot_change_prior_signals_or_features():
    prices = 100 + np.arange(350)*.02 + np.sin(np.arange(350)*.17)*2
    bars = [Bar(datetime(2020,1,1)+timedelta(minutes=15*i),p-.1,p+.4,p-.4,p,1) for i,p in enumerate(prices)]
    short = features(bars[:280])
    full = features(bars)
    pd.testing.assert_frame_equal(short,full.iloc[:280])
    for family in FAMILIES:
        np.testing.assert_array_equal(signals(short,family),signals(full,family)[:280])


def test_donchian_window_excludes_signal_bar():
    bars = [Bar(datetime(2020,1,1)+timedelta(hours=i),100,101,99,100,1) for i in range(210)]
    bars[-1] = Bar(bars[-1].time,100,110,99,108,1)
    f = features(bars)
    assert f.iloc[-1].prior_high20 == 101
    assert f.iloc[-1].prior_high55 == 101


def test_direction_mirrors_and_unknown_family_rejected():
    f = pd.DataFrame(dict(open=np.full(210,100.),high=np.full(210,101.),low=np.full(210,99.),close=np.full(210,100.),
                         ema20=np.full(210,99.),ema50=np.full(210,95.),ema200=np.linspace(80,90,210),atr=np.ones(210),
                         prior_high20=np.full(210,104.),prior_low20=np.full(210,96.)))
    f.loc[209,"close"] = 105
    assert signals(f,"breakout20")[-1] == 1
    reflected = f.copy()
    reflected["high"],reflected["low"] = 200-f.low,200-f.high
    reflected["prior_high20"],reflected["prior_low20"] = 200-f.prior_low20,200-f.prior_high20
    for key in ("open","close","ema20","ema50","ema200"):
        reflected[key] = 200-f[key]
    assert signals(reflected,"breakout20")[-1] == -1
    import pytest
    with pytest.raises(ValueError):
        signals(f,"unknown")


def test_exported_pine_signal_expressions_match_research():
    """Evaluate the actual exported conditions; this is not an official Pine compile."""
    import re
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]/"scripts/tradingview/gold_breakout55_pf_candidate.pine").read_text(encoding="utf-8")
    expressions = {name: re.search(rf"^bool {name} = (.+)$",source,re.M)[1].replace("slow[5]","previous_slow") for name in ("ready","buySetup","sellSetup")}
    prices = 100 + np.arange(700)*.03 + np.sin(np.arange(700)*.08)*3
    bars = [Bar(datetime(2020,1,1)+timedelta(hours=i),p-.05,p+.1,p-.1,p,1) for i,p in enumerate(prices)]
    f = features(bars)
    actual = []
    for i,row in f.iterrows():
        env = dict(bar_index=i,a=row.atr,fast=row.ema50,slow=row.ema200,close=row.close,
                   priorHigh=row.prior_high55,priorLow=row.prior_low55,
                   previous_slow=f.iloc[i-5].ema200 if i>=5 else float("nan"))
        for key,expr in expressions.items():
            env[key] = eval(expr,{"__builtins__":{}},env)
        actual.append(1 if env["buySetup"] else -1 if env["sellSetup"] else 0)
    expected = signals(f,"breakout55")
    assert np.any(expected)
    np.testing.assert_array_equal(actual,expected)
