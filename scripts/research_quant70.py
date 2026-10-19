"""Finite quant search with period-isolated, cost-adjusted full-exit RR1 fills."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from forextester_backtest import HistoryRepository
from research_strict_rr_portfolio import _prepare
from quant70_signals import candidates, signals

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'docs/quant_organization/experiments/quant70_20260908'


@dataclass(frozen=True)
class Trade:
    symbol: str
    signal_time: str
    entry_time: str
    exit_time: str
    direction: int
    entry: float
    stop: float
    target: float
    exit: float
    net_r: float
    reason: str
    ambiguous: bool


def simulate(data, directions, symbol, start, end, pip, slip_pips=0.1, spread_scale=1.0):
    """One position per pair; no signal or position may cross a split."""
    spread = data.spread * spread_scale
    slip = pip * slip_pips
    times = data.times
    active = np.asarray([start <= t < end for t in times])
    eligible = np.flatnonzero(active & (directions != 0) & np.isfinite(data.atr))
    final_indices = np.flatnonzero(active)
    if not final_indices.size:
        return []
    last = int(final_indices[-1])
    trades = []
    next_signal = 0
    for raw in eligible:
        i = int(raw)
        if i < next_signal or i + 1 > last:
            continue
        j = i + 1
        if times[j] - times[i] != timedelta(minutes=15):
            continue
        direction = int(directions[i])
        if direction not in (-1, 1):
            raise ValueError('invalid direction')
        entry = float(data.open[j] + (spread if direction == 1 else 0) + direction * slip)
        stop = float(data.close[i] - direction * 2 * data.atr[i] + (spread if direction == -1 else 0))
        risk = direction * (entry - stop)
        if not math.isfinite(risk) or risk <= 0:
            continue
        target = entry + direction * risk
        ambiguous = False
        for k in range(j, last + 1):
            ask = spread if direction == -1 else 0
            opening = float(data.open[k] + ask)
            high, low = float(data.high[k] + ask), float(data.low[k] + ask)
            stop_gap = direction * (opening - stop) <= 0
            tp_gap = direction * (opening - target) >= 0
            hit_stop = low <= stop if direction == 1 else high >= stop
            hit_target = high >= target if direction == 1 else low <= target
            ambiguous = hit_stop and hit_target
            if stop_gap:
                price, reason = opening, 'stop_gap'
            elif tp_gap:
                price, reason = target, 'target_gap'
            elif hit_stop:
                price, reason = stop, 'stop'
            elif hit_target:
                price, reason = target, 'target'
            elif k == last:
                price, reason = float(data.close[k] + ask), 'period_end'
            else:
                continue
            price -= direction * slip
            net_r = direction * (price - entry) / risk
            trades.append(Trade(symbol, times[i].isoformat(), times[j].isoformat(),
                                times[k].isoformat(), direction, entry, stop, target,
                                price, net_r, reason, ambiguous))
            next_signal = k + 1  # No reuse of an exit bar as a new signal.
            break
    return trades


def stats(trades, months):
    rows = sorted(trades, key=lambda t: (t.exit_time, t.symbol, t.entry_time))
    values = np.asarray([t.net_r for t in rows], dtype=float)
    n, wins = len(rows), int(np.sum(values > 0))
    profit, loss = float(values[values > 0].sum()), float(-values[values < 0].sum())
    p = wins / n if n else 0
    z = 1.959963984540054
    lower = ((p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1+z*z/n)) if n else 0
    equity = np.concatenate(([0.0], np.cumsum(values)))
    dd = float(np.max(np.maximum.accumulate(equity)-equity)) * 0.25
    normal = [t for t in rows if t.reason != 'period_end']
    return {'trades': n, 'wins': wins, 'net_win_rate_pct': 100*p,
            'wilson_95_lower_pct': 100*lower, 'profit_factor': profit/loss if loss else None,
            'expectancy_r': float(values.mean()) if n else None, 'net_r': float(values.sum()),
            'realized_drawdown_pct': dd, 'trades_per_month': n/months,
            'forced_period_exits': n-len(normal), 'ambiguous_trades': sum(t.ambiguous for t in rows),
            'normal_exit_win_rate_pct': 100*sum(t.net_r>0 for t in normal)/len(normal) if normal else None}


def rejection_reasons(summary, pair_stats, period, gates):
    failures = []
    if summary['trades'] < gates[f'min_{period}_trades']:
        failures.append('取引数不足')
    if summary['net_win_rate_pct'] < gates['net_win_rate_pct']:
        failures.append('コスト後勝率70%未達')
    if summary['profit_factor'] is None or summary['profit_factor'] < gates['profit_factor']:
        failures.append('PF1.5未達または評価不能')
    if summary['expectancy_r'] is None or summary['expectancy_r'] <= 0:
        failures.append('期待値が正ではない')
    if summary['trades_per_month'] < gates['min_trades_per_month']:
        failures.append('月平均取引数不足')
    if summary['realized_drawdown_pct'] > gates['max_realized_drawdown_pct']:
        failures.append('決済損益DD超過')
    minimum = gates['min_trades_each_pair_train' if period == 'train' else 'min_trades_each_pair_other']
    if any(s['trades'] < minimum for s in pair_stats.values()):
        failures.append('通貨別母数不足')
    if sum(s['net_r'] > 0 for s in pair_stats.values()) < gates['min_positive_pairs']:
        failures.append('利益通貨数不足')
    return failures


def quality(data, start, end):
    if not data.times or data.times[0] > start+timedelta(days=7) or data.times[-1] < end-timedelta(days=7):
        raise ValueError('history edges insufficient')
    a = np.column_stack([data.open, data.high, data.low, data.close])
    if not np.isfinite(a).all() or np.any(a <= 0) or np.any(data.high < np.maximum(data.open, data.close)) or np.any(data.low > np.minimum(data.open, data.close)):
        raise ValueError('invalid OHLC')
    if not math.isfinite(data.spread) or data.spread < 0:
        raise ValueError('invalid spread')
    gaps = []
    for i, time in enumerate(data.times):
        if time.minute % 15 or time.second or time.microsecond:
            raise ValueError('unaligned bar')
        if i:
            delta = time-data.times[i-1]
            if delta.total_seconds() <= 0:
                raise ValueError('duplicate or unordered bar')
            if delta > timedelta(days=7):
                gaps.append([data.times[i-1].isoformat(), time.isoformat()])
    if gaps:
        raise ValueError(f'long interior history gaps: {gaps[:3]}')
    digest = hashlib.sha256(a.tobytes())
    digest.update('|'.join(t.isoformat() for t in data.times).encode())
    return {'bars': len(data.times), 'start': data.times[0].isoformat(),
            'end': data.times[-1].isoformat(), 'sha256': digest.hexdigest(),
            'scope': 'aggregated 15m OHLC/order/edges; incomplete constituent minutes not certified'}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history-dir', default=r'C:\ForexTester6\data\History')
    parser.add_argument('--output', type=Path, default=ROOT/'agent_runs/quant70_20260908')
    args = parser.parse_args()
    protocol = json.loads((EXPERIMENT/'protocol.json').read_text(encoding='utf-8'))
    specs = candidates()
    assert len(specs) == protocol['candidate_budget']
    baseline = {'name':'baseline_htf_hourly', 'family':'baseline', 'stop_atr':2.0, 'timeframe':'15m'}
    evaluated_specs = [*specs, baseline]
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output/'protocol.json', protocol)
    dump(args.output/'candidates.json', specs)
    dump(args.output/'code_hashes.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
         (Path(__file__), ROOT/'scripts/quant70_signals.py', ROOT/'scripts/research_strict_rr_portfolio.py', ROOT/'src/forextester_backtest/data.py')})
    repository = HistoryRepository(args.history_dir)
    symbols = protocol['symbols']
    period_dates = {k: tuple(datetime.fromisoformat(d) for d in v) for k,v in protocol['periods'].items()}
    month_counts = {'train':108, 'validation':48, 'confirmation':24, 'recent_reference':18}
    records = {s['name']: {'candidate':s, 'periods':{}, 'pairs':{}, 'rejections':{}} for s in evaluated_specs}
    history_manifest = {}

    def evaluate(selected_specs, periods, stress=False):
        combined = {s['name']:{p:[] for p in periods} for s in selected_specs}
        for symbol in symbols:
            print(f'Loading {symbol} periods={periods} stress={stress}', flush=True)
            last = max(period_dates[p][1] for p in periods)
            data = _prepare(repository, symbol, last-timedelta(microseconds=1), '15m')
            meta = repository.metadata(symbol)
            if meta.commission_per_lot != 0:
                raise ValueError('nonzero commission currency needs explicit verification')
            history_manifest[f'{symbol}:{last.date()}'] = {**quality(data, datetime(2010,1,1), last), 'metadata': asdict(meta)}
            dump(args.output/'data_manifest.json', history_manifest)
            pip = 0.01 if symbol.endswith('JPY') else 0.0001
            for spec in selected_specs:
                if spec['family'] == 'baseline':
                    direction = np.where(data.minutes == 0, data.htf_trend, 0).astype(np.int8)
                    direction[:208] = 0
                else:
                    direction = signals(data, spec)
                for period in periods:
                    start, end = period_dates[period]
                    subset = [i for i,t in enumerate(data.times) if start <= t < end]
                    if not subset or data.times[subset[0]] > start+timedelta(days=7) or data.times[subset[-1]] < end-timedelta(days=7):
                        raise ValueError(f'{symbol}/{period}: missing period edge')
                    trades = simulate(data, direction, symbol, start, end, pip,
                                      0.2 if stress else 0.1, 1.5 if stress else 1.0)
                    combined[spec['name']][period].extend(trades)
                    label = period+('_stress' if stress else '')
                    records[spec['name']]['pairs'].setdefault(label,{})[symbol] = stats(trades, month_counts[period])
                    # Durable completed trade evidence even if a later pair fails.
                    with (args.output/'trades.jsonl').open('a', encoding='utf-8') as file:
                        for trade in trades:
                            file.write(json.dumps({'candidate':spec['name'], 'period':label, **asdict(trade)}, allow_nan=False)+'\n')
            dump(args.output/'progress.json', {'last_symbol':symbol, 'periods':periods, 'stress':stress})
        for spec in selected_specs:
            record = records[spec['name']]
            for period in periods:
                label = period+('_stress' if stress else '')
                summary = stats(combined[spec['name']][period],month_counts[period])
                record['periods'][label] = summary
                if stress:
                    reasons = [] if summary['expectancy_r'] is not None and summary['expectancy_r']>0 and summary['profit_factor'] is not None and summary['profit_factor']>=1.15 else ['コストストレス不合格']
                else:
                    gate_period = 'recent' if period=='recent_reference' else period
                    reasons = rejection_reasons(summary, record['pairs'][label], gate_period, protocol['gates'])
                record['rejections'][label] = reasons

    try:
        evaluate(evaluated_specs, ['train','validation'])
        qualified = [records[s['name']] for s in specs if not any(records[s['name']]['rejections'].values())]
        winner = max(qualified, key=lambda r:(r['periods']['validation']['wilson_95_lower_pct'],r['periods']['validation']['profit_factor'],r['candidate']['name'])) if qualified else None
        dump(args.output/'selection.json', {'qualified':len(qualified),'selected':winner['candidate'] if winner else None,'basis':'train and validation only'})
        if winner:
            evaluate([winner['candidate']],['confirmation','recent_reference'])
            evaluate([winner['candidate']],['confirmation','recent_reference'],True)
        passed = bool(winner and not any(winner['rejections'].values()))
        payload = {'status':'RESEARCH_PASS' if passed else 'REJECTED', 'selected':winner['candidate']['name'] if winner else None,
                   'candidate_count':len(specs),'qualified_count':len(qualified), 'records':list(records.values()),
                   'confirmation_evaluated':bool(winner), 'live_approved':False}
        dump(args.output/'results.json',payload)
        rows = sorted(records.values(),key=lambda r:r['periods']['validation']['net_win_rate_pct'],reverse=True)
        report = ['# 勝率70%クオンツ探索', '', f"判定: {payload['status']}。候補{len(specs)}件、事前基準通過{len(qualified)}件。", '',
                  '勝率は全決済のコスト後利益が正の割合。期間末強制決済も含む。RR1は発注時のTP/SL距離。',
                  '期間は過去の研究で閲覧済みであり真の未使用期間とは保証しない。DDは固定0.25%リスク換算の決済損益のみ。', '',
                  '|候補|学習取引|学習勝率|検証取引|検証勝率|検証PF|検証期待値R|検証Wilson下限|検証判定|',
                  '|---|---:|---:|---:|---:|---:|---:|---:|---|']
        for row in rows:
            t,v=row['periods']['train'],row['periods']['validation']
            report.append(f"|{row['candidate']['name']}|{t['trades']}|{t['net_win_rate_pct']:.2f}%|{v['trades']}|{v['net_win_rate_pct']:.2f}%|{v['profit_factor']}|{v['expectancy_r']}|{v['wilson_95_lower_pct']:.2f}%|{' / '.join(row['rejections']['validation']) or '合格'}|")
        if not winner:
            report += ['', '学習・検証の基準を通過した候補がないため、2023年以降の確認成績の計算とPine移植は行わなかった。']
        report += ['', '固定スプレッド＋片道0.1pipの滑り。スワップ・変動スプレッド・ポートフォリオ時価DDは未モデル化。',
                   '候補・期間/通貨別成績・元バー指紋・取引一覧は同じ出力ディレクトリ内。']
        (args.output/'report.md').write_text('\n'.join(report),encoding='utf-8')
        print('RESULT_JSON='+json.dumps({'status':payload['status'],'qualified':len(qualified),'output':str(args.output)},ensure_ascii=False),flush=True)
    except Exception as exc:
        dump(args.output/'failure.json',{'type':type(exc).__name__,'message':str(exc)})
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
