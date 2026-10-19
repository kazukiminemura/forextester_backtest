"""Separate saved-trade reconciliation for fixed PF search."""
from collections import defaultdict
from datetime import datetime,timedelta
import hashlib
import json
from research_simple_rr13_15 import OUT,ROOT
from research_quant70 import dump
from verify_quant70_results import require,close,summarize


def main():
    read=lambda name:json.loads((OUT/name).read_text(encoding='utf-8'))
    p,r=read('protocol.json'),read('results.json')
    frozen=json.loads((ROOT/'docs/quant_organization/experiments'/p['id']/'protocol.json').read_text(encoding='utf-8'))
    require(p==frozen and p['reward_risks']==[1.3,1.4,1.5],'protocol drift')
    for path,digest in read('code_hashes.json').items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,'code drift')
    require(read('source_before.json')==read('source_after.json'),'history changed')
    records={v['name']:v for v in r['records']}
    expected={s['name']+'__'+w[0] for s in p['candidates'] for w in p['windows']}
    require(set(records)==expected and len(records)==36,'scope')
    windows={w[0]:w[1:] for w in p['windows']}
    groups=defaultdict(list); last_exit={}; count=0
    start,end=map(datetime.fromisoformat,[p['start'],p['end_exclusive']])
    with (OUT/'trades.jsonl').open(encoding='utf-8') as f:
        for line in f:
            t=json.loads(line); key=t['condition'],t['symbol']
            require(key[0] in records and key[1] in p['symbols'],'trade scope')
            st,en,ex=[datetime.fromisoformat(t[k]) for k in ('signal_time','entry_time','exit_time')]
            require(start<=st<en<=ex<end and en-st==timedelta(minutes=15),'period ordering')
            a,b=windows[records[key[0]]['window']]; require(a<=st.hour<b,'clock gate')
            require(key not in last_exit or st>last_exit[key],'overlap'); last_exit[key]=ex
            d=t['direction']; risk=d*(t['entry']-t['stop']); require(d in (-1,1) and risk>0,'risk')
            close(d*(t['target']-t['entry']),risk*records[key[0]]['candidate']['reward_risk'],'RR per candidate')
            close(t['net_r'],d*(t['exit']-t['entry'])/risk,'net R')
            if t['reason'] in ('target','target_gap','stop'):
                close(t['exit'],(t['stop'] if t['reason']=='stop' else t['target'])-d*0.001,'exit cost')
            groups[key].append((t['exit_time'],t['symbol'],t['entry_time'],t['net_r'],t['reason'],t['ambiguous'])); count+=1
    bounds=[datetime(2023+(8+i)//12,(8+i)%12+1,8).isoformat() for i in range(37)]
    def check(rows,expected,months):
        value=summarize(rows,months)
        for k,v in expected.items(): close(v,value[k],k)
        return value
    def qualifies(s,monthly,n):
        return s['trades']>=n and s['profit_factor'] is not None and s['profit_factor']>=1.5 and s['expectancy_r']>0 and s['realized_drawdown_pct']<=10 and all(m['trades']>=10 and m['net_r']>0 for m in monthly)
    for name,rec in records.items():
        all_rows=[]; pair_passes=[]; pair_stats=[]
        for symbol in p['symbols']:
            rows=groups[name,symbol]; all_rows.extend(rows)
            s=check(rows,rec['pairs'][symbol],36); pair_stats.append(s)
            months=[check([t for t in rows if bounds[i]<=t[2]<bounds[i+1]],rec['pair_months'][symbol][i],1) for i in range(36)]
            if qualifies(s,months,360): pair_passes.append(symbol)
        require(pair_passes==rec['pair_passes'],'pair gate')
        s=check(all_rows,rec['summary'],36)
        months=[check([t for t in all_rows if bounds[i]<=t[2]<bounds[i+1]],rec['months'][i],1) for i in range(36)]
        passed=qualifies(s,months,900) and all(v['trades']>=10 for v in pair_stats) and sum(v['net_r']>0 for v in pair_stats)>=4
        require(passed==rec['aggregate_pass'],'aggregate gate')
        for i in range(3):
            check([t for t in all_rows if bounds[i*12]<=t[2]<bounds[(i+1)*12]],rec['years'][i],12)
            for symbol in p['symbols']:
                check([t for t in groups[name,symbol] if bounds[i*12]<=t[2]<bounds[(i+1)*12]],rec['pair_years'][symbol][i],12)
    dump(OUT/'verification.json',{'status':'VERIFIED','saved_trade_rows':count,'conditions':36,'independent_person_review':False})
    print('VERIFIED_ROWS='+str(count))


if __name__=='__main__': main()
