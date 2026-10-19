"""No network: response validation, causal state and permanent spending cap."""
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research_bb3_jev as m


def response():
    return dict(model='jev-1.13.0', answers={'gate': dict(type='choice', choice='accept',
        confidence=.7, probabilities={'accept': .8, 'skip': .1, 'uncertain': .1})},
        usage={'input_tokens': 100, 'output_tokens': 30})


def test_response_boundary():
    assert m.validate_response(response())
    bad = response()
    bad['answers']['gate']['probabilities']['accept'] = float('nan')
    with pytest.raises(ValueError):
        m.validate_response(bad)
    bad = response()
    bad['usage']['input_tokens'] = 65537
    with pytest.raises(ValueError):
        m.validate_response(bad)


def test_budget_reservations_persist_and_do_not_retry(tmp_path):
    cfg = dict(reservation_tokens_per_attempt=65536, price_usd_per_million_input_tokens=.042,
               hard_reserved_usd=65536*.042/1e6, max_workers=1, stop_after_failures=3)
    with patch.object(m, 'OUT', tmp_path), patch.object(m, 'api_key', return_value='never-log-this'):
        with patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(m.encoded(response()))) as api:
            m.infer([('a', {}), ('b', {})], cfg)
            assert api.call_count == 1
        with patch.object(m.urllib.request, 'urlopen') as api:
            m.infer([('a', {}), ('b', {})], cfg)
            assert api.call_count == 0
    assert len((tmp_path/'reservations.jsonl').read_text().splitlines()) == 1
    assert 'never-log-this' not in (tmp_path/'responses/a.json').read_text()


def test_failed_request_is_charged_reserved_and_not_retried(tmp_path):
    cfg = dict(reservation_tokens_per_attempt=65536, price_usd_per_million_input_tokens=.042,
               hard_reserved_usd=2.3, max_workers=1, stop_after_failures=3)
    with patch.object(m, 'OUT', tmp_path), patch.object(m, 'api_key', return_value='secret'):
        with patch.object(m.urllib.request, 'urlopen', side_effect=TimeoutError('secret')) as api:
            m.infer([('a', {})], cfg)
            m.infer([('a', {})], cfg)
            assert api.call_count == 1
    stored = json.loads((tmp_path/'responses/a.json').read_text())
    assert not stored['valid']
    assert stored['error_type'] == 'TimeoutError'
    assert 'secret' not in json.dumps(stored)


def test_input_has_no_future_or_identity():
    f, t, p, k = m.load_symbol('USDJPY')
    s = next(s for s in m.candidates(f,t,p,k) if m.START <= t[s['index']] < m.END)
    i = s['index']
    assert m.payload(f,t,s) == m.payload(f[:i+1],t[:i+1],s)
    assert set(m.payload(f,t,s)['state']).isdisjoint({'symbol','date','outcome','net_pips'})
