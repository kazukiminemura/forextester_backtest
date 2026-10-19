"""Six predeclared simple profiles, three fixed RR values; causal signals only."""
import numpy as np
from quant70_signals import _past,_range,_ema,signals as original_signals


def candidates():
    profiles=[]
    for length in (20,40):
        profiles.append({'name':f'simple_ema{length}','family':'simple_ema','length':length})
    for lookback in (8,16):
        profiles.append({'name':f'simple_breakout{lookback}','family':'simple_breakout','lookback':lookback})
        profiles.append({'name':f'compression_expansion_l{lookback}_r0.90_b0.00','family':'compression_expansion',
                         'lookback':lookback,'max_atr_ratio':.9,'breakout_buffer_atr':0.,
                         'min_expansion_atr':1.25,'slow_atr_length':56})
    return [{**p,'name':p['name']+f'_rr{rr:.1f}','reward_risk':rr,'timeframe':'15m','stop_atr':2.}
            for p in profiles for rr in (1.3,1.4,1.5)]


def signals(data,spec):
    if spec['family']=='compression_expansion': return original_signals(data,spec)
    c=data.close
    if spec['family']=='simple_ema':
        length=spec['length']
        if length not in data.ema_cache: data.ema_cache[length]=_ema(c,length)
        e=data.ema_cache[length]
        long=(_past(c)<=_past(e)) & (c>e)
        short=(_past(c)>=_past(e)) & (c<e)
    elif spec['family']=='simple_breakout':
        upper,lower=_range(data,spec['lookback'])
        long=c>upper; short=c<lower
    else: raise ValueError('unknown family')
    valid=np.isfinite(c)&np.isfinite(data.atr)&(data.atr>0)
    valid[:208]=False
    out=np.zeros(len(c),dtype=np.int8)
    out[valid & (data.htf_trend==1) & long]=1
    out[valid & (data.htf_trend==-1) & short]=-1
    return out
