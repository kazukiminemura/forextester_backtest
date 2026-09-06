"""Conservative minute limit-order fills, fixed expiry and no pre-fill TP credit."""
from bisect import bisect_left
from datetime import timedelta


def limit_trade(quotes, times, placed, side, atr, reference, spread, offset, ttl_hours, anchored):
    expiry = min(placed+timedelta(hours=ttl_hours),placed.replace(hour=16,minute=0,second=0))
    limit = reference-side*offset*atr
    risk, slip = 1.5*atr, spread*.1
    fill_index, entry, at_open = None, None, False
    for i in range(bisect_left(times,placed),len(quotes)):
        bar = quotes[i]
        if bar.time >= expiry:
            break
        op = bar.open+(spread if side==1 else 0)
        extreme = bar.low+spread if side==1 else bar.high
        if side*(extreme-limit) <= 0:
            entry = min(op,limit) if side==1 else max(op,limit)
            at_open = side*(op-limit) <= 0
            fill_index = i
            break
    if fill_index is None:
        return dict(filled=False,expiry=expiry)
    origin = reference if anchored else entry
    stop, target = origin-side*risk, origin+side*2*risk
    deadline = placed.replace(hour=20,minute=0,second=0)
    for j in range(fill_index,len(quotes)):
        bar = quotes[j]
        price_offset = spread if side==-1 else 0
        op, hi, lo = bar.open+price_offset,bar.high+price_offset,bar.low+price_offset
        price, reason = None,None
        if bar.time >= deadline:
            if side*(op-target) >= 0:
                price,reason = target,"target"
            else:
                price,reason = op-side*slip,"stop" if side*(op-stop)<=0 else "time"
        elif (lo<=stop if side==1 else hi>=stop):
            price = (min(op,stop) if side==1 else max(op,stop))-side*slip
            reason = "stop"
        elif (j!=fill_index or at_open) and (hi>=target if side==1 else lo<=target):
            price,reason = target,"target"
        if price is not None:
            return dict(filled=True,entry_time=quotes[fill_index].time,entry=entry,exit_time=bar.time,
                        r=side*(price-entry)/risk,reason=reason,late=int(bar.time>deadline),expiry=expiry)
    raise ValueError("Unresolved limit trade: insufficient minute history")
