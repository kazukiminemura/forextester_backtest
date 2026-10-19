"""Behavior tests for causal requests, durable costs, and unchanged RR1 fills; no API."""
import copy
import io
import json
from unittest.mock import patch

import numpy as np
import pytest

from scripts import research_ytt_jev as m


def context():
    prices = np.tile([100., 102., 99., 101.], (40, 1))
    return prices, np.arange(40)*900


def body():
    p, t = context()
    return m.payload(p, t, 25, 1, 98., 100., 1, 1)


def response(tokens=100):
    return dict(model=m.MODEL, answers={'gate': dict(type='choice', choice='accept',
        probabilities={'accept': .8, 'skip': .1, 'uncertain': .1}, confidence=.7)},
        usage={'input_tokens': tokens, 'output_tokens': 30})


def transport(tokens=100):
    return lambda *args, **kwargs: io.BytesIO(json.dumps(response(tokens)).encode())


def test_payload_never_reads_future_prices_or_times():
    p, t = context()
    expected = m.payload(p, t, 25, 1, 98, 100, 1, 1)
    p[26:] = np.nan
    t[26:] = 0
    assert m.payload(p, t, 25, 1, 98, 100, 1, 1) == expected
    assert set(expected['state']) == {'direction', 'confirmed_daily_direction', 'confirmed_weekly_direction',
        'bars_ohlc_mtr', 'recent_gap', 'confirmed_break_level_mtr', 'stop_mtr', 'last_true_range_relative'}
    assert len(expected['state']['bars_ohlc_mtr']) == 24


@pytest.mark.parametrize('side,daily,weekly,stop,level', [(1,-1,1,98,100),(1,1,1,102,100),(1,1,1,98,102)])
def test_payload_rejects_invalid_direction_stop_or_unbroken_level(side,daily,weekly,stop,level):
    p, t = context()
    with pytest.raises(ValueError):
        m.payload(p,t,25,side,stop,level,daily,weekly)


def test_response_contract_rejects_bad_distribution_model_and_nonmaximum():
    for mutate in [lambda x: x.update(model='jev-latest'),
                   lambda x: x['answers']['gate'].update(choice='skip'),
                   lambda x: x['answers']['gate']['probabilities'].update(accept=float('nan'))]:
        r = response()
        mutate(r)
        with pytest.raises(ValueError):
            m.accepted(r)
    assert m.accepted(response())


def test_offline_never_reads_key_or_network(tmp_path):
    with patch.object(m.client, 'api_key', side_effect=AssertionError('key read')):
        assert m.infer([body()], tmp_path)['calls'] == 0
    assert not (tmp_path/'inference.lock').exists()


def test_success_settles_and_cache_prevents_repeat_call(tmp_path):
    with patch.object(m.client, 'api_key', return_value='fake'):
        result = m.infer([body()], tmp_path, live=True, max_calls=1, transport=transport())
        assert result['calls'] == 1
        actual = 100*m.PRICE_PER_MILLION_USD/1e6*m.RESERVE_USDJPY
        assert result['reserved_yen'] == pytest.approx(actual)
        second = m.infer([body()], tmp_path, live=True, max_calls=1,
                         transport=lambda *a, **k: pytest.fail('duplicate HTTP'))
    assert second['calls'] == 0 and second['cache_hits'] == 1
    assert second['reserved_yen'] == pytest.approx(actual)


def test_failure_keeps_full_reservation_and_cannot_retry(tmp_path):
    def fail(*args, **kwargs):
        raise TimeoutError('secret-not-to-save')
    with patch.object(m.client, 'api_key', return_value='fake'):
        first = m.infer([body()], tmp_path, live=True, max_calls=1, transport=fail)
        second = m.infer([body()], tmp_path, live=True, max_calls=1, transport=transport())
    assert first['failures'] == 1 and first['reserved_yen'] == m.RESERVATION_YEN
    assert second['calls'] == 0 and second['reserved_yen'] == m.RESERVATION_YEN
    assert 'secret-not-to-save' not in next((tmp_path/'responses').glob('*.json')).read_text()


def test_budget_reserved_before_sending_and_three_failures_stop(tmp_path):
    jobs = []
    for n in range(6):
        b = body()
        b['state']['stop_mtr'] -= n
        jobs.append(b)
    with patch.object(m.client, 'api_key', return_value='fake'):
        result = m.infer(jobs, tmp_path, live=True, max_calls=6, budget_yen=m.RESERVATION_YEN*2.1,
                         transport=transport(65536))
    assert result['calls'] == 2 and result['reserved_yen'] <= m.RESERVATION_YEN*2.1
    other = tmp_path/'failure'
    def fail(*args, **kwargs):
        raise TimeoutError()
    with patch.object(m.client, 'api_key', return_value='fake'):
        result = m.infer(jobs, other, live=True, max_calls=6, transport=fail)
    assert result['calls'] == result['failures'] == 3


def test_crash_after_response_before_settlement_recovers_from_cache(tmp_path):
    with patch.object(m.client, 'api_key', return_value='fake'):
        m.infer([body()], tmp_path, live=True, max_calls=1, transport=transport())
    ledger = tmp_path/'reservations.jsonl'
    ledger.write_text(ledger.read_text().splitlines()[0]+'\n')
    result = m.infer([body()], tmp_path, live=True, max_calls=1, transport=transport())
    assert result['calls'] == 0
    assert result['reserved_yen'] == pytest.approx(100*.042/1e6*200)
    assert len(ledger.read_text().splitlines()) == 2


def test_pending_crash_reservation_never_refunded_or_retried(tmp_path):
    b = body()
    (tmp_path/'reservations.jsonl').write_text(json.dumps(dict(kind='reserve', hash=m.client.digest(b),
        reserved_yen=m.RESERVATION_YEN))+'\n')
    result = m.infer([b], tmp_path, live=True, max_calls=1,
                     transport=lambda *a, **k: pytest.fail('retry'))
    assert result['calls'] == 0 and result['reserved_yen'] == m.RESERVATION_YEN


def test_settlement_tampering_is_rejected(tmp_path):
    with patch.object(m.client, 'api_key', return_value='fake'):
        m.infer([body()], tmp_path, live=True, max_calls=1, transport=transport())
    ledger = tmp_path/'reservations.jsonl'
    rows = [json.loads(x) for x in ledger.read_text().splitlines()]
    rows[1]['actual_yen'] = 0
    ledger.write_text('\n'.join(json.dumps(x) for x in rows)+'\n')
    with pytest.raises(ValueError, match='Settlement'):
        m.infer([body()], tmp_path, live=True, max_calls=1, transport=transport())


def test_cache_payload_tampering_rejected(tmp_path):
    with patch.object(m.client, 'api_key', return_value='fake'):
        m.infer([body()], tmp_path, live=True, max_calls=1, transport=transport())
    path = next((tmp_path/'responses').glob('*.json'))
    record = json.loads(path.read_text())
    record['request']['state']['direction'] = 'SELL'
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='Cache provenance'):
        m.cached(body(), tmp_path)


def execution():
    t = np.arange(10)*900
    p = np.tile([100.,100.3,99.7,100.1],(10,1))
    complete = np.ones(10,bool)
    side, stops, levels = np.zeros(10,np.int8), np.full(10,np.nan), np.full(10,np.nan)
    side[1], stops[1], levels[1] = 1, 99, 99.9
    return t,p,complete,side,stops,levels


def test_delay_control_identical_to_all_approved_and_cancels_waiting_stop():
    t,p,c,s,sl,lv = execution()
    a = m.delayed_signals(t,p,c,s,sl,lv)
    b = m.delayed_signals(t,p,c,s,sl,lv,{1})
    for x,y in zip(a,b):
        np.testing.assert_equal(x,y)
    assert np.flatnonzero(a[0]).tolist() == [2]
    p[2,2] = 99
    assert not m.delayed_signals(t,p,c,s,sl,lv)[0].any()


def test_delayed_entry_missing_bar_does_not_carry_signal():
    t,p,c,s,sl,lv = execution()
    t[2:] += 900
    assert not m.delayed_signals(t,p,c,s,sl,lv)[0].any()


def test_rr1_exactly_matches_audited_simulator_including_account():
    t,p,c,s,sl,lv = execution()
    p[3,2] = 98
    for cash in (False,True):
        expected = m.core.simulate(t,p,c,c,s,sl,lv,0,9000,.02,cash=cash)
        actual = m.simulate(t,p,c,c,s,sl,lv,0,9000,.02,cash=cash,rr=1.)
        assert actual[0] == expected[0] and actual[2] == expected[2]
        np.testing.assert_equal(actual[1],expected[1])


@pytest.mark.parametrize('rr',[1.,1.5,2.])
def test_rr_changes_full_target_without_changing_stop(rr):
    t,p,c,s,sl,lv = execution()
    p[3] = [100,103,99.7,102]
    rows,_,_ = m.simulate(t,p,c,c,s,sl,lv,0,9000,0.,rr=rr)
    assert len(rows) == 1 and rows[0]['gross_r'] == rr and rows[0]['stop'] == 99


def test_missing_api_coverage_is_not_adopted(tmp_path):
    t,p,c,s,sl,lv = execution()
    offset=m.core.epoch('2020-01-01')
    data = dict(times=t+offset,prices=p,complete=c,starts_at_open=c,observed_open_times=t+offset,
                sides=np.array([s]),stops=np.array([sl]),thresholds=np.array([lv]),bodies={1:body()})
    result=m.evaluate({'USDJPY':data},'training',tmp_path)
    assert result['status'] == 'NEEDS_EVIDENCE' and result['adoption_approved'] is False
    assert result['coverage']['USDJPY']['scored'] == 0
    assert all(r['metrics']['trades'] == 0 for r in result['results'] if r['arm']=='jev')


def test_freeze_roundtrip_and_later_gate(tmp_path):
    m.freeze(tmp_path,{'periods':m.PERIODS},'training')
    m.freeze(tmp_path,{'periods':m.PERIODS},'training')
    with pytest.raises(ValueError,match='changed'):
        m.freeze(tmp_path,{'periods':{}},'training')
    with pytest.raises(ValueError,match='Complete training'):
        m.later_selection(tmp_path)


def test_live_output_cannot_reset_experiment_budget(tmp_path):
    with pytest.raises(ValueError, match='fixed experiment'):
        m.infer([body()], tmp_path, live=True, max_calls=1)


def test_three_failures_remain_stopped_across_restarts(tmp_path):
    jobs=[]
    for n in range(7):
        b=body()
        b['state']['stop_mtr']-=n
        jobs.append(b)
    def fail(*a,**k):
        raise TimeoutError()
    with patch.object(m.client,'api_key',return_value='fake'):
        first=m.infer(jobs[:4],tmp_path,live=True,max_calls=7,transport=fail)
        second=m.infer(jobs[3:],tmp_path,live=True,max_calls=7,transport=transport())
    assert first['calls']==3 and second['calls']==0 and second['failures']==3


@pytest.mark.parametrize('remove_ledger',[False,True])
def test_orphan_response_refuses_budget_reset(tmp_path,remove_ledger):
    with patch.object(m.client,'api_key',return_value='fake'):
        m.infer([body()],tmp_path,live=True,max_calls=1,transport=transport())
    ledger=tmp_path/'reservations.jsonl'
    if remove_ledger:
        ledger.unlink()
    else:
        ledger.write_text('')
    with pytest.raises(ValueError,match='lack durable reservations'):
        m.infer([body()],tmp_path,live=True,max_calls=1,transport=transport())


def test_prepare_cli_serializes_numpy_candidate_count(tmp_path,capsys):
    b=body()
    data={'USDJPY':dict(times=np.array([m.core.epoch('2020-01-01')],dtype=np.int64),
                       bodies={0:b},deterministic_invalid=[])}
    with patch.object(m,'load_data',return_value=(data,{m.client.digest(b):b},{})), \
         patch.object(m.sys,'argv',['research_ytt_jev.py','--prepare-only','--output',str(tmp_path)]):
        m.main()
    manifest=json.loads((tmp_path/'training_candidate_manifest.json').read_text())
    assert manifest['USDJPY']['eligible_candidates']==1
    assert manifest['USDJPY']['candidates'][0]['signal_close_time']==m.core.epoch('2020-01-01')+900
    assert 'PREPARED_NO_API_NO_RESULTS' in capsys.readouterr().out
