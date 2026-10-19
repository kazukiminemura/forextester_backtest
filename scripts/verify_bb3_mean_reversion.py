"""Verify saved trades, band observations and separate-formula summaries."""
from pathlib import Path
from datetime import datetime,timedelta
import hashlib,json,math,statistics
from forextester_backtest import HistoryRepository
from verify_quant70_results import require,close

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'agent_runs/bb3_usdjpy_20260908_v2'


def main():
    read=lambda name:json.loads((OUT/name).read_text(encoding='utf-8'))
    p,r=read('protocol.json'),read('results.json')
    for path,digest in read('code_hashes.json').items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,'code drift')
    require(read('source_before.json')==read('source_after.json'),'source changed')
    start,end=map(datetime.fromisoformat,p['period'])
    repo=HistoryRepository(); spread=repo.metadata('USDJPY').spread_price; slip=.001
    bars=list(repo.bars('USDJPY',datetime(2023,8,1),end-timedelta(microseconds=1),'5m'))
    index={b.time.isoformat():i for i,b in enumerate(bars)}
    count=0
    def summary_check(rows,s):
        vals=[t['net_pips'] for t in rows]; wins=sum(v>0 for v in vals)
        profit=math.fsum(v for v in vals if v>0); loss=-math.fsum(v for v in vals if v<0)
        require(len(vals)==s['trades'] and wins==s['wins'],'counts')
        close(s['profit_factor'],profit/loss if loss else None,'PF')
        close(s['win_rate_pct'],100*wins/len(vals) if vals else 0,'win rate')
        close(s['net_pips'],math.fsum(vals),'pips')
        close(s['average_pips'],math.fsum(vals)/len(vals) if vals else None,'mean')
        running=peak=dd=0.
        for v in vals:
            running+=v; peak=max(peak,running); dd=max(dd,peak-running)
        close(s['realized_drawdown_pips'],dd,'DD')
    for case in r['cases']:
        rows=[json.loads(line) for line in (OUT/(case['case']+'_trades.jsonl')).read_text(encoding='utf-8').splitlines()]
        prior=None
        for t in rows:
            st,en,ex=map(datetime.fromisoformat,[t['signal_time'],t['entry_time'],t['exit_time']])
            require(start<=st<en<=ex<end and en-st==timedelta(minutes=5),'ordering')
            require(prior is None or st>prior,'overlap'); prior=ex
            si,ei,xi=[index[t[k]] for k in ['signal_time','entry_time','exit_time']]
            d=t['direction']; require(d in (-1,1),'direction')
            closes=[b.close for b in bars[si-19:si+1]]
            mid=statistics.mean(closes); deviation=statistics.pstdev(closes)
            buy=bars[si].low<=mid-3*deviation; sell=bars[si].high>=mid+3*deviation
            require(buy!=sell and (buy if d==1 else sell),'band signal')
            close(t['entry'],bars[ei].open+(spread if d==1 else 0)+d*slip,'entry cost')
            target=statistics.mean([b.close for b in bars[xi-20:xi]])+(spread if d==-1 else 0)
            close(t['center_order'],target,'causal center')
            close(t['net_pips'],d*(t['exit']-t['entry'])/.01,'net pips')
            if case['stop_pips'] is None: require(t['stop'] is None,'no stop baseline')
            else: close(d*(t['entry']-t['stop'])/.01,case['stop_pips'],'stop distance')
            if t['reason']=='center': close(t['exit'],target-d*slip,'center fill')
            elif t['reason']=='stop': close(t['exit'],t['stop']-d*slip,'stop fill')
            elif t['reason'] in ('stop_gap','center_gap'): close(t['exit'],bars[xi].open+(spread if d==-1 else 0)-d*slip,'gap fill')
            elif t['reason']=='period_end':
                require(xi==len(bars)-1,'forced exit edge')
            else: raise AssertionError('unknown reason')
        summary_check(rows,case['summary'])
        for y in case['years']:
            summary_check([t for t in rows if y['start']<=t['entry_time']<y['end']],y)
        count+=len(rows)
    result={'status':'VERIFIED','saved_trade_rows':count,'independent_person_review':False,
            'scope':'saved signal/entry/exit geometry, causal bands and center, separate summary formula; MTM drawdown/MAE not independently replayed'}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__': main()
