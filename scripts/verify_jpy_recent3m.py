"""Reconcile saved three-month trades with separate aggregation formula."""
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from research_jpy_recent3m import OUT, ROOT
from verify_quant70_results import summarize, close, require
from research_quant70 import dump


def main():
    read=lambda name: json.loads((OUT/name).read_text(encoding='utf-8'))
    p,r=read('protocol.json'),read('results.json')
    frozen=json.loads((ROOT/'docs/quant_organization/experiments'/p['experiment_id']/'protocol.json').read_text(encoding='utf-8'))
    require(p==frozen,'protocol drift')
    for path,digest in read('code_hashes.json').items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,'code drift '+path)
    require(read('source_before.json')==read('source_after.json'),'history changed')
    groups=defaultdict(list); n=0
    records={v['candidate']['name']:v for v in r['records']}
    require(len(records)==36 and {s['name'] for s in p['candidates']}==set(records),'candidate scope')
    with (OUT/'trades.jsonl').open(encoding='utf-8') as f:
        for line in f:
            t=json.loads(line); require(t['candidate'] in records and t['symbol'] in p['symbols'],'scope')
            row=(t['exit_time'],t['symbol'],t['entry_time'],t['net_r'],t['reason'],t['ambiguous'])
            groups[t['candidate'],t['symbol']].append(row); n+=1
    def check(rows,expected,months):
        result=summarize(rows,months)
        for k,v in expected.items(): close(v,result[k],k)
    boundaries=['2026-06-08','2026-07-08','2026-08-08','2026-09-08']
    for name,record in records.items():
        rows=[]
        for symbol in p['symbols']:
            pair=groups[name,symbol]; rows.extend(pair)
            check(pair,record['pairs'][symbol],3)
            for i in range(3):
                check([t for t in pair if boundaries[i]<=t[2]<boundaries[i+1]],record['pair_months'][symbol][i],1)
        check(rows,record['summary'],3)
        for i in range(3):
            check([t for t in rows if boundaries[i]<=t[2]<boundaries[i+1]],record['months'][i],1)
    require(n==r['verified_trade_rows'],'count')
    dump(OUT/'independent_formula_verification.json',{'status':'VERIFIED','saved_trade_rows':n,'independent_person_review':False})
    print('VERIFIED_ROWS='+str(n))


if __name__=='__main__': main()
