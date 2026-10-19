"""Intraday-context experiment; reuse the audited RR1 execution engine unchanged."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
from forextester_backtest import HistoryRepository
from research_strict_rr_portfolio import _prepare
from research_quant70 import simulate, stats, quality, rejection_reasons, dump
from quant70_intraday_signals import candidates, comparators, signals, daily_context

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'docs/quant_organization/experiments/quant70_intraday_20260908'


def context_effect(candidate, control):
    """Measure state-gate benefit without changing execution or the entry trigger."""
    win_delta = candidate['net_win_rate_pct'] - control['net_win_rate_pct']
    c, b = candidate['expectancy_r'], control['expectancy_r']
    expectancy_delta = c - b if c is not None and b is not None else None
    return {'win_rate_delta_pp':win_delta, 'expectancy_delta_r':expectancy_delta,
            'passes': bool(win_delta > 0 and expectancy_delta is not None and expectancy_delta > 0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history-dir', default=r'C:\ForexTester6\data\History')
    parser.add_argument('--output', type=Path, default=ROOT/'agent_runs/quant70_intraday_20260908')
    args = parser.parse_args()
    protocol = json.loads((EXPERIMENT/'protocol.json').read_text(encoding='utf-8'))
    specs = candidates()
    assert len(specs) == protocol['candidate_budget']
    baseline = {'name':'baseline_htf_hourly', 'family':'baseline', 'stop_atr':2.0, 'timeframe':'15m'}
    controls = comparators()
    assert len(controls) == protocol['comparator_budget']
    evaluated_specs = [*specs, *controls, baseline]
    assert len({s['name'] for s in evaluated_specs}) == len(evaluated_specs)
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output/'protocol.json', protocol)
    dump(args.output/'candidates.json', specs)
    dump(args.output/'comparators.json', controls)
    dump(args.output/'code_hashes.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
         (Path(__file__), ROOT/'scripts/quant70_intraday_signals.py', ROOT/'scripts/research_quant70.py', ROOT/'scripts/quant70_signals.py', ROOT/'scripts/research_strict_rr_portfolio.py', ROOT/'src/forextester_backtest/data.py')})
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
            context = daily_context(data)
            meta = repository.metadata(symbol)
            if meta.commission_per_lot != 0:
                raise ValueError('nonzero commission currency needs explicit verification')
            history_manifest[f'{symbol}:{last.date()}'] = {**quality(data, datetime(2010,1,1), last), 'metadata': asdict(meta)}
            history_manifest[f'{symbol}:{last.date()}']['day_context'] = {
                'source_calendar_days':int(np.unique(context['day_id']).size),
                'valid_day_bars':int(context['valid_day'].sum()),
                'adr20_available_bars':int(np.isfinite(context['adr20']).sum()),
                'previous_day_levels_available_bars':int(np.isfinite(context['previous_high']).sum()),
                'opening_range_available_bars':int(np.isfinite(context['opening_high']).sum()),
                'intraday_state_eligible_bars':int((context['valid_day'] & np.isfinite(context['adr20']) & (context['adr20'] > 0)).sum())}
            dump(args.output/'data_manifest.json', history_manifest)
            pip = 0.01 if symbol.endswith('JPY') else 0.0001
            for period in periods:
                start, end = period_dates[period]
                subset = [i for i,t in enumerate(data.times) if start <= t < end]
                if not subset or data.times[subset[0]] > start+timedelta(days=7) or data.times[subset[-1]] < end-timedelta(days=7):
                    raise ValueError(f'{symbol}/{period}: missing period edge')
            for spec in selected_specs:
                if spec['family'] == 'baseline':
                    direction = np.where(data.minutes == 0, data.htf_trend, 0).astype(np.int8)
                    direction[:208] = 0
                else:
                    direction = signals(data, spec, context=context)
                for period in periods:
                    start, end = period_dates[period]
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
        # Frozen effect test: adding intraday state must improve both metrics.
        effects = []
        for control in controls:
            candidate = records[control['comparison_of']]
            comparator = records[control['name']]
            for period in ('train', 'validation'):
                effect = context_effect(candidate['periods'][period], comparator['periods'][period])
                effects.append({'candidate': candidate['candidate']['name'], 'comparator':control['name'],
                                'period':period, **effect})
                if not effect['passes']:
                    candidate['rejections'][period].append('当日状態追加による勝率・期待値の両方の改善なし')
        dump(args.output/'context_effects.json', effects)
        qualified = [records[s['name']] for s in specs if not any(records[s['name']]['rejections'].values())]
        winner = max(qualified, key=lambda r:(r['periods']['validation']['wilson_95_lower_pct'],r['periods']['validation']['profit_factor'],r['candidate']['name'])) if qualified else None
        dump(args.output/'selection.json', {'qualified':len(qualified),'selected':winner['candidate'] if winner else None,'basis':'train and validation only'})
        if winner:
            evaluate([winner['candidate']],['confirmation','recent_reference'])
            evaluate([winner['candidate']],['confirmation','recent_reference'],True)
        passed = bool(winner and not any(winner['rejections'].values()))
        payload = {'status':'RESEARCH_PASS' if passed else 'REJECTED', 'selected':winner['candidate']['name'] if winner else None,
                   'candidate_count':len(specs),'comparator_count':len(controls),'qualified_count':len(qualified), 'records':list(records.values()),
                   'confirmation_evaluated':bool(winner), 'live_approved':False}
        dump(args.output/'results.json',payload)
        rows = sorted(records.values(),key=lambda r:r['periods']['validation']['net_win_rate_pct'],reverse=True)
        report = ['# 当日の動きを考慮した勝率70%探索', '', f"判定: {payload['status']}。候補{len(specs)}件、当日状態なし比較{len(controls)}件、単純基準1件、事前基準通過{len(qualified)}件。", '',
                  '勝率は全決済のコスト後利益が正の割合。期間末強制決済も含む。RR1は発注時のTP/SL距離。',
                  '期間は過去の研究で閲覧済みであり真の未使用期間とは保証しない。DDは固定0.25%リスク換算の決済損益のみ。', '',
                  '|候補|学習取引|学習勝率|検証取引|検証勝率|検証PF|検証期待値R|検証Wilson下限|検証判定|',
                  '|---|---:|---:|---:|---:|---:|---:|---:|---|']
        for row in rows:
            t,v=row['periods']['train'],row['periods']['validation']
            report.append(f"|{row['candidate']['name']}|{t['trades']}|{t['net_win_rate_pct']:.2f}%|{v['trades']}|{v['net_win_rate_pct']:.2f}%|{v['profit_factor']}|{v['expectancy_r']}|{v['wilson_95_lower_pct']:.2f}%|{' / '.join(row['rejections']['validation']) or '合格'}|")
        report += ['', '## 当日状態を追加した効果（候補 − 対応比較）', '',
                   '|候補|期間|勝率差pt|期待値差R|両方改善|',
                   '|---|---|---:|---:|---|']
        for effect in effects:
            edge = effect['expectancy_delta_r']
            report.append(f"|{effect['candidate']}|{effect['period']}|{effect['win_rate_delta_pp']:.3f}|{edge if edge is not None else '評価不能'}|{effect['passes']}|")
        report += ['', '当日は時間帯未特定の保存時刻00:00区切り。取引所・NY・JSTの日付とは未確認。',
                   '前日高安・序盤レンジのトリガーは比較にも残し、当日方向・進展・値幅消費ゲートの追加効果だけを比較。']
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
