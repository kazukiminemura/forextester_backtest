"""Jev code-review evidence only. Never called by candidate generation/backtests."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'agent_runs/bb3_jev_refine_20260925'
OLD = ROOT/'agent_runs/bb3_jev_20260925'
UNIT_USD = 65536*.042/1e6


def validate(response):
    if response.get('model') != 'jev-1.13.0':
        raise ValueError('Wrong model')
    if set(response.get('answers', {})) != {'causality', 'selection', 'separation'}:
        raise ValueError('Unexpected question IDs')
    for answer in response['answers'].values():
        probs = answer['probabilities']
        if answer['type'] != 'choice' or set(probs) != {'supports', 'contradicts', 'insufficient'}:
            raise ValueError('Invalid choice contract')
        if any(type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1
               for p in [*probs.values(), answer['confidence']]):
            raise ValueError('Invalid numeric probability')
        # Three independently rounded 2-decimal probabilities can total .99 or 1.01.
        if abs(sum(probs.values())-1) > .015 or answer['choice'] not in probs:
            raise ValueError('Invalid probability sum/choice')
        if probs[answer['choice']] < max(probs.values()) - 1e-9:
            raise ValueError('Choice disagrees with maximum probability')
    n = response['usage']['input_tokens']
    if type(n) is not int or not 0<n<=65536:
        raise ValueError('Usage outside reservation')


def main(source_path=None, tests_path=None, claims=None):
    source_path = source_path or ROOT/'scripts/research_bb3_jev_refine.py'
    source = source_path.read_text(encoding='utf-8-sig')
    ast.parse(source)
    tests = (tests_path or ROOT/'tests/test_bb3_jev_refine.py').read_text(encoding='utf-8-sig')
    claims = claims or {
        'causality': 'Policy filtering uses only candidate-close or earlier bars. Entry minimum room is checked at the actual next-bar open, not leaked into the earlier signal.',
        'selection': 'Selection uses only 2023 results, at least30 closes, RR-first then simpler-policy ties; selection.json is saved before evaluating later periods.',
        'separation': 'Every trade is determined by numeric rules and the simulator. No Jev response/cache affects entries or exits. Jev code review is external to the backtest.'
    }
    body = dict(model='jev-1.13.0', state=dict(python_source=source, tests=tests,
        context='Read-only review of a research harness. Imported simulator is separately tested; missing source may warrant insufficient. Do not judge profitability or recommend trades.'),
        questions={k: dict(type='choice', instructions='Does the supplied code support this claim? '+claim,
            criteria={'supports':'Code supports this claim within the visible scope.',
                      'contradicts':'Visible code violates this claim.',
                      'insufficient':'Not enough visible evidence to establish it.'}) for k,claim in claims.items()})
    payload = json.dumps(body, sort_keys=True, ensure_ascii=True).encode()
    if len(payload)>28000:
        raise ValueError('Code review context too large; narrow scope before sending')
    h = hashlib.sha256(payload).hexdigest()
    OUT.mkdir(exist_ok=True, parents=True)
    target = OUT/f'code_review_{h}.json'
    if target.exists():
        print('REVIEW_CACHED='+str(target))
        return
    lock = OUT/'code_review.lock'
    fd = os.open(lock, os.O_EXCL|os.O_CREAT|os.O_WRONLY)
    try:
        old = [json.loads(x) for x in (OLD/'reservations.jsonl').read_text().splitlines()]
        ledger_path = OUT/'code_review_reservations.jsonl'
        new = [json.loads(x) for x in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
        if any(x['hash']==h for x in new):
            raise RuntimeError('Previously attempted review cannot be retried automatically')
        if len(new)>=3 or sum(x['reserved_usd'] for x in old+new)+UNIT_USD>2.30:
            raise RuntimeError('Combined user budget or code-review attempt cap reached')
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as env:
            key = os.environ.get('TYPESAFE_API_KEY') or winreg.QueryValueEx(env,'TYPESAFE_API_KEY')[0]
        now = datetime.now(timezone.utc).isoformat()
        with ledger_path.open('a',encoding='utf-8') as ledger:
            ledger.write(json.dumps(dict(hash=h,reserved_usd=UNIT_USD,at=now))+'\n')
            ledger.flush()
            os.fsync(ledger.fileno())
        record = dict(request_hash=h, request=body, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                      purpose='code_review_only', at=now, advisory_only=True)
        try:
            request = urllib.request.Request('https://api.typesafe.ai/v1/systemone',payload,
                       {'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=45) as response:
                record['response'] = json.load(response)
            validate(record['response'])
            record['valid'] = True
        except Exception as error:
            record.update(valid=False,error_type=type(error).__name__)
        target.write_text(json.dumps(record,indent=2),encoding='utf-8')
        print('REVIEW_JSON='+str(target))
        print(json.dumps(dict(valid=record['valid'], answers=record.get('response',{}).get('answers',{}),
                              usage=record.get('response',{}).get('usage',{}))))
    finally:
        os.close(fd)
        lock.unlink()


if __name__=='__main__':
    main()
