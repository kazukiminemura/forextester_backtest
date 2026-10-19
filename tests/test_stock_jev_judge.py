"""No paid API calls in tests."""
import copy
import importlib.util
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location('stock_judge', Path(__file__).resolve().parents[1] / 'scripts/judge_stock_research_with_jev.py')
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


def response_for(body):
    return {'model': judge.MODEL, 'usage': {'input_tokens': 100}, 'answers': {
        key: {'type': 'choice', 'choice': next(iter(q['criteria'])), 'confidence': 1.,
              'probabilities': {c: float(i == 0) for i, c in enumerate(q['criteria'])}}
        for key, q in body['questions'].items()}}


def test_response_contract_and_selection_fail_closed():
    evidence = {'eligible_candidates': ['no_dow'], 'results': {}}
    body = judge.build_request(evidence, 'training')
    response = response_for(body)
    judge.validate(response, body['questions'])
    assert judge.selection(evidence, response) == 'no_dow'
    assert judge.selection({'eligible_candidates': []}, response) == 'none'
    response['answers']['no_dow']['confidence'] = .79
    assert judge.selection(evidence, response) == 'none'
    for mutation in ('model', 'nan', 'choice', 'usage', 'extra'):
        broken = copy.deepcopy(response)
        if mutation == 'model': broken['model'] = 'unknown'
        if mutation == 'nan': broken['answers']['selection']['confidence'] = float('nan')
        if mutation == 'choice': broken['answers']['selection']['choice'] = 'none'
        if mutation == 'usage': broken['usage']['input_tokens'] = True
        if mutation == 'extra': broken['answers']['extra'] = {}
        with pytest.raises(ValueError): judge.validate(broken, body['questions'])


def test_failure_is_reserved_and_not_retried():
    body = judge.build_request({'eligible_candidates': [], 'results': {}}, 'training')
    with tempfile.TemporaryDirectory() as folder, patch.dict(judge.os.environ, {'TYPESAFE_API_KEY': 'test-only'}), patch.object(judge.urllib.request, 'urlopen', side_effect=TimeoutError) as call:
        with pytest.raises(RuntimeError): judge.evaluate(body, 'training', Path(folder))
        with pytest.raises(ValueError): judge.evaluate(body, 'training', Path(folder))
        body['state']['extra'] = 'changed evidence'
        with pytest.raises(RuntimeError): judge.evaluate(body, 'training', Path(folder))
        assert call.call_count == 1
        assert len((Path(folder) / 'jev_reservations.jsonl').read_text().splitlines()) == 1
