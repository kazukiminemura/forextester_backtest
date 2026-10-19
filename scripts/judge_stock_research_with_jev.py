"""Bounded Jev research-result evaluation; never used inside a trade simulation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'agent_runs/tamukai_stocks_jev_20260926'
MODEL = 'jev-1.13.0'
PRICE_PER_MILLION = .042
RESERVATION_USD = 65536 * PRICE_PER_MILLION / 1e6
CANDIDATES = ('no_dow', 'prior_day_breakout', 'sma63_trend')
LIMITATIONS = [
    'Previously examined 2017-2025 data. These are not untouched holdout results.',
    'Ten currently surviving Japanese large caps: selection and survivorship bias.',
    'Yahoo adjusted OHLC; Sony 2025 spin-off adjustment unresolved. Two documented high/low repairs.',
    'Fractional adjusted shares, no dividends/taxes/interest, assumed transaction costs, not executable account returns.',
    'Quality-exclusion portfolios are diagnostics only, not candidates to cherry-pick.',
    'No live trading approval. Model confidence is not trade win probability or evidence of future profit.',
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(response, questions):
    if response.get('model') != MODEL or set(response.get('answers', {})) != set(questions):
        raise ValueError('Unexpected model or question IDs')
    for key, question in questions.items():
        answer = response['answers'][key]
        probabilities = answer['probabilities']
        if answer['type'] != 'choice' or set(probabilities) != set(question['criteria']):
            raise ValueError('Unexpected choice schema')
        values = [*probabilities.values(), answer['confidence']]
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError('Invalid probability')
        # API probabilities are rounded; permit half a cent per option.
        if abs(sum(probabilities.values()) - 1) > .005 * len(probabilities) + 1e-9:
            raise ValueError('Invalid probability sum')
        if answer['choice'] not in probabilities or probabilities[answer['choice']] < max(probabilities.values()) - 1e-9:
            raise ValueError('Choice is not a maximum')
    tokens = response['usage']['input_tokens']
    if type(tokens) is not int or not 0 < tokens <= 65536:
        raise ValueError('Usage exceeds reservation')


def build_request(evidence, phase):
    evidence = compact(evidence)
    if phase == 'training':
        evidence = dict(evidence)
        evidence['results'] = {candidate: {
            cost: {**{k: v for k, v in item.items() if k != 'quality_diagnostics' and (cost == 'main' or k != 'by_symbol')},
                   'quality_diagnostics': {group: row['metrics'] for group, row in item['quality_diagnostics'].items()}}
            for cost, item in results.items()}
            for candidate, results in evidence['results'].items()}
    criteria = {
        'advance': 'Evidence warrants the next independent research check; consistent enough after costs and across years/stocks. Not approval to trade.',
        'reject': 'Observed evidence contradicts a credible edge or the prespecified numeric gates fail. Reject this fixed candidate.',
        'insufficient': 'Cannot evaluate reliably because evidence is missing, unreliable, or too ambiguous; do not advance.',
    }
    if phase == 'training':
        questions = {c: dict(type='choice', instructions=f'Evaluate fixed candidate {c} in results, using only these training results and limitations. What research disposition is justified?', criteria=criteria) for c in CANDIDATES}
        questions['selection'] = dict(type='choice', instructions='Choose at most one eligible candidate for independent later-period evaluation. Consider cost robustness, breadth across stocks and years, and simplicity, not just highest profit. Choose none if no eligible candidate offers credible evidence. Baseline is not selectable.', criteria={
            **{c: f'Select {c} only if listed in eligible_candidates and evidence merits later-period research.' for c in CANDIDATES},
            'none': 'No candidate should advance from the supplied training evidence.',
        })
    else:
        questions = {'evaluation': dict(type='choice', instructions='Evaluate the selected fixed strategy using its independent later-period evidence, numeric gates and limitations. Advance means further fresh-data research, never adoption or live trading.', criteria=criteria)}
    return dict(model=MODEL, state=dict(evidence=evidence, limitations=LIMITATIONS,
        task='Research evaluation only. Arithmetic and hard gates are already computed by deterministic code. Confidence threshold 0.8 is an uncalibrated conservative workflow rule.'), questions=questions)


def compact(value):
    """Keep decision metrics; omit redundant accounting fields, round only API display."""
    omitted = {'initial_capital', 'final_equity', 'average_net_profit', 'exposure_pct'}
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if k not in omitted}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return round(value, 4) if isinstance(value, float) else value


def evaluate(body, phase, output=OUT):
    payload = json.dumps(body, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
    if len(payload) > 28000:
        raise ValueError('Narrow the result evidence before sending (28000-byte ceiling)')
    request_hash = hashlib.sha256(payload).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'jev_{phase}_{request_hash}.json'
    if target.exists():
        record = json.loads(target.read_text(encoding='utf-8'))
        if not record['valid'] or record['request'] != body:
            raise ValueError('Invalid cached evaluation; no automatic retry')
        validate(record['response'], body['questions'])
        return record, target
    lock = output / 'jev.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        ledger_path = output / 'jev_reservations.jsonl'
        rows = [json.loads(line) for line in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
        if len(rows) >= 2 or any(row['phase'] == phase for row in rows):
            raise RuntimeError('Two-call / one-attempt-per-phase cap reached; no automatic retry')
        if (sum(row['reserved_usd'] for row in rows) + RESERVATION_USD) * 200 > 2:
            raise RuntimeError('Research budget exhausted')
        key = os.environ.get('TYPESAFE_API_KEY')
        if not key:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as env:
                key = winreg.QueryValueEx(env, 'TYPESAFE_API_KEY')[0]
        now = datetime.now(timezone.utc).isoformat()
        with ledger_path.open('a', encoding='utf-8') as ledger:
            ledger.write(json.dumps(dict(phase=phase, request_hash=request_hash, reserved_usd=RESERVATION_USD, at=now)) + '\n')
            ledger.flush()
            os.fsync(ledger.fileno())
        record = dict(at=now, request_hash=request_hash, request=body, valid=False,
                      purpose='research_result_evaluation_only', live_trading_authorized=False)
        try:
            request = urllib.request.Request('https://api.typesafe.ai/v1/systemone', payload,
                {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=45) as response:
                record['response'] = json.load(response)
            validate(record['response'], body['questions'])
            record['valid'] = True
            record['usage_usd'] = record['response']['usage']['input_tokens'] * PRICE_PER_MILLION / 1e6
        except Exception as error:
            record['error_type'] = type(error).__name__
        target.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
        if not record['valid']:
            raise RuntimeError(f'Jev evaluation failed; evidence saved at {target}')
        return record, target
    finally:
        os.close(fd)
        lock.unlink()


def selection(evidence, response):
    answer = response['answers']['selection']
    candidate = answer['choice']
    if candidate not in evidence['eligible_candidates'] or answer['confidence'] < .8:
        return 'none'
    assessment = response['answers'][candidate]
    return candidate if assessment['choice'] == 'advance' and assessment['confidence'] >= .8 else 'none'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('training', 'final'), default='training')
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    body = build_request(evidence, args.phase)
    record, target = evaluate(body, args.phase)
    if args.phase == 'training':
        result = dict(experiment_id=evidence['experiment_id'], training_sha256=digest(args.evidence),
                      selected_candidate=selection(evidence, record['response']), selector='jev',
                      jev_evidence=str(target.relative_to(ROOT)), jev_sha256=digest(target),
                      selected_at=datetime.now(timezone.utc).isoformat(), confidence_rule=.8)
        selection_path = OUT / 'selection.json'
        if selection_path.exists():
            prior = json.loads(selection_path.read_text(encoding='utf-8'))
            if any(prior[k] != v for k, v in result.items() if k != 'selected_at'):
                raise RuntimeError('Existing selection differs; refusing overwrite')
        else:
            selection_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    print(json.dumps(dict(evidence=str(target), answers=record['response']['answers'], usage_usd=record['usage_usd'])))
