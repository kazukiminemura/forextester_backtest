"""Explicit proxy for undisclosed Tenzoko Himo rules, NOT the original method."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from forextester_backtest.data import HistoryRepository

OUT = Path(__file__).resolve().parent
PROTOCOL = {
    "identity": "Estimated Tenzoko Himo proxy; not a reproduction of the proprietary indicator",
    "symbol": "USDJPY", "timeframe": "15m", "lookback": 20,
    "breakout": "Close above prior 20 highs or below prior 20 lows",
    "anchor_f": "Lowest prior-20 close for upward breakout; highest close for downward breakout; first occurrence on ties",
    "x": "Breakout bar close, frozen for the lifetime of the setup",
    "purity": "direction*(current close-f) / sum(abs(close change)) from anchor to current bar",
    "level": "x + direction*abs(x-f)/purity; updated at close for use starting NEXT bar",
    "primary_min_purity": 0.30, "sensitivity_min_purity": [0.20, 0.40],
    "setup": "One active setup; expires after 96 bars or purity below threshold. Touch uses prior-bar level before current-close invalidation. No same-bar initial touch.",
    "entry": "Touch prior known upper level with Bid high -> short next open; touch lower level with Bid low -> long next open; no EMA filter",
    "exit": "Full exit at TP or SL 1:1, distance 1.5*Wilder ATR14 known at signal close; no time exit; final open position forcibly closed",
    "execution": "Bid OHLC. Long entry Ask, exit Bid; short entry Bid, exit Ask. Fixed metadata spread. SL first if both touched. Gap stop at open, gap TP conservatively at limit price.",
    "costs": "No swap or slippage; metadata commission must be zero",
    "evaluation": "All predeclared thresholds reported. Chronological slices are descriptive, not a fresh holdout. No optimization or candidate selection.",
}


@dataclass
class Setup:
    direction: int
    anchor: int
    born: int
    x: float
    width: float
    level: float


def level_at(close, path, anchor, index, direction, x, width, threshold):
    travel = path[index] - path[anchor]
    purity = direction * (close[index] - close[anchor]) / travel if travel > 0 else 0
    if purity < threshold:
        return None
    return x + direction * width / purity


def exit_fill(direction, entry, risk, open_, high, low, close, final=False):
    """Inputs are executable exit prices: Bid for longs, Ask for shorts."""
    stop, target = entry-direction*risk, entry+direction*risk
    if direction*(open_-stop) <= 0:
        return open_, "gap_stop"
    if direction*(open_-target) >= 0:
        return target, "target"
    stopped = low <= stop if direction == 1 else high >= stop
    targeted = high >= target if direction == 1 else low <= target
    if stopped:
        return stop, "both_stop_first" if targeted else "stop"
    if targeted:
        return target, "target"
    return (close, "end_of_data") if final else None


def features(bars):
    close = np.array([b.close for b in bars])
    high = np.array([b.high for b in bars])
    low = np.array([b.low for b in bars])
    path = np.r_[0, np.cumsum(np.abs(np.diff(close)))]
    tr = np.maximum(high-low, np.maximum(np.abs(high-np.r_[close[0],close[:-1]]), np.abs(low-np.r_[close[0],close[:-1]])))
    atr = np.full(len(bars), np.nan)
    atr[13] = np.mean(tr[:14])
    for i in range(14, len(bars)):
        atr[i] = (13*atr[i-1]+tr[i])/14
    previous_high = np.r_[np.full(20, np.nan), np.max(np.lib.stride_tricks.sliding_window_view(high, 20), axis=1)[:-1]]
    previous_low = np.r_[np.full(20, np.nan), np.min(np.lib.stride_tricks.sliding_window_view(low, 20), axis=1)[:-1]]
    return close, path, atr, previous_high, previous_low


def simulate(bars, data, spread, threshold):
    close, path, atr, previous_high, previous_low = data
    setup = pending = position = None
    trades = []
    for i, bar in enumerate(bars):
        if pending is not None:
            direction, risk, signal_index, signal_level = pending
            position = (direction, risk, bar.open+(spread if direction == 1 else 0), i, signal_index, signal_level)
            pending = None
        if position is not None:
            direction, risk, entry, entry_index, signal_index, signal_level = position
            offset = spread if direction == -1 else 0
            fill = exit_fill(direction, entry, risk, bar.open+offset, bar.high+offset,
                             bar.low+offset, bar.close+offset, i == len(bars)-1)
            if fill is not None:
                price, reason = fill
                pnl = direction*(price-entry)/0.01
                trades.append(dict(direction="long" if direction == 1 else "short",
                    signal_time=str(bars[signal_index].time), signal_level=signal_level,
                    entry_time=str(bars[entry_index].time), exit_time=str(bar.time),
                    entry_price=entry, exit_price=price, risk_pips=risk/0.01,
                    net_pips=pnl, net_r=pnl/(risk/0.01), reason=reason,
                    holding_bars=i-entry_index+1))
                position = None
            else:
                continue
        if i < 250 or i == len(bars)-1:
            continue
        if setup is not None:
            # Only the level fixed at the PREVIOUS close may trigger this bar.
            touch = bar.high >= setup.level if setup.direction == 1 else bar.low <= setup.level
            if touch:
                risk = 1.5*atr[i]
                if risk > spread:
                    pending = (-setup.direction, risk, i, setup.level)
                setup = None
                continue
            updated = level_at(close, path, setup.anchor, i, setup.direction, setup.x, setup.width, threshold)
            if i-setup.born >= 96 or updated is None:
                setup = None
            else:
                setup.level = updated
        if setup is None:
            direction = 1 if bar.close > previous_high[i] else -1 if bar.close < previous_low[i] else 0
            if direction:
                window = close[i-20:i]
                anchor = i-20 + int(np.argmin(window) if direction == 1 else np.argmax(window))
                width = abs(bar.close-close[anchor])
                level = level_at(close, path, anchor, i, direction, bar.close, width, threshold)
                if level is not None:
                    setup = Setup(direction, anchor, i, bar.close, width, level)
    return trades


def stats(trades):
    p = np.array([t["net_pips"] for t in trades])
    wins, losses = int(np.sum(p>1e-8)), int(np.sum(p < -1e-8))
    loss = -float(np.sum(p[p < -1e-8]))
    return dict(trades=len(p), wins=wins, losses=losses, breakevens=len(p)-wins-losses,
        win_rate_pct=100*wins/len(p) if len(p) else None,
        profit_factor=float(np.sum(p[p>1e-8]))/loss if loss else None,
        net_pips=float(np.sum(p)), mean_pips=float(np.mean(p)) if len(p) else None,
        mean_r=float(np.mean([t["net_r"] for t in trades])) if len(p) else None,
        ambiguous_stop_first=sum(t["reason"]=="both_stop_first" for t in trades),
        gap_stops=sum(t["reason"]=="gap_stop" for t in trades),
        forced_exits=sum(t["reason"]=="end_of_data" for t in trades))


def self_check():
    assert exit_fill(1, 100, 1, 100, 102, 98, 100) == (99, "both_stop_first")
    assert exit_fill(-1, 100, 1, 100, 102, 98, 100) == (101, "both_stop_first")
    assert exit_fill(1, 100, 1, 98, 100, 97, 99) == (98, "gap_stop")
    assert exit_fill(-1, 100, 1, 102, 103, 100, 101) == (102, "gap_stop")
    c = np.array([100., 101., 100.5, 102.])
    path = np.r_[0.,np.cumsum(abs(np.diff(c))) ]
    assert abs(level_at(c,path,0,3,1,102,2,.3)-105) < 1e-9


def main():
    self_check()
    (OUT / "estimated_tenzoko_protocol.json").write_text(json.dumps(PROTOCOL,indent=2),encoding="utf-8")
    history = HistoryRepository()
    metadata = history.metadata("USDJPY")
    assert metadata.commission_per_lot == 0
    print("Loading source USDJPY M15 history", flush=True)
    bars = list(history.bars("USDJPY", timeframe="15m"))
    data = features(bars)
    report = dict(protocol=PROTOCOL, start=str(bars[0].time), end=str(bars[-1].time),
                  bars=len(bars), spread_pips=metadata.spread_price/.01, models={})
    periods = [(2003,2018),(2019,2022),(2023,2024),(2025,2026)]
    for threshold in [.30,.20,.40]:
        trades = simulate(bars, data, metadata.spread_price, threshold)
        for t in trades:
            assert t['entry_time'] > t['signal_time']
            assert t['exit_time'] >= t['entry_time']
            if t['reason'] in ('stop','both_stop_first','target'):
                assert abs(abs(t['net_r'])-1)<1e-8
        result = dict(overall=stats(trades),
            periods_by_exit={f"{a}-{b}":stats([t for t in trades if a<=int(t['exit_time'][:4])<=b]) for a,b in periods},
            direction={d:stats([t for t in trades if t['direction']==d]) for d in ('long','short')},
            years_by_exit={str(y):stats([t for t in trades if int(t['exit_time'][:4])==y]) for y in range(2003,2027)})
        assert len(trades)==sum(v['trades'] for v in result['periods_by_exit'].values())
        report['models'][str(threshold)] = result
        if threshold == .30 and trades:
            with (OUT / "estimated_tenzoko_trades.csv").open('w',newline='',encoding='utf-8-sig') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(trades[0]))
                writer.writeheader()
                writer.writerows(trades)
        print(json.dumps({"threshold":threshold, "overall":result['overall'], "periods":result['periods_by_exit']},indent=2),flush=True)
    # Prefix rerun checks that extending history cannot alter already closed trades.
    prefix = 5000
    part = simulate(bars[:prefix], tuple(a[:prefix] for a in data), metadata.spread_price, .30)
    full = simulate(bars, data, metadata.spread_price, .30)
    cutoff = str(bars[prefix-1].time)
    assert [t for t in part if t['exit_time']<cutoff] == [t for t in full if t['exit_time']<cutoff]
    report['checks'] = 'Synthetic exits/purity, next-bar entry, exact nominal RR1, period counts, and prefix invariance passed'
    (OUT / "estimated_tenzoko_results.json").write_text(json.dumps(report,indent=2),encoding='utf-8')
    print("RESULT_JSON="+str(OUT / "estimated_tenzoko_results.json"),flush=True)


if __name__ == '__main__':
    main()
