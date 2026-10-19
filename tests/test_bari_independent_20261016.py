"""Independent causal replay checks; all inputs are synthetic, not history."""
import numpy as np

from scripts import research_bari_video_20261016 as research
from scripts import validate_bari_video_20261016 as independent


def synthetic(n=4000):
    rng = np.random.default_rng(20261016)
    times = np.arange(n, dtype=np.int64)*300
    close = 150+np.cumsum(rng.normal(0, .1, n))
    op = np.r_[150., close[:-1]]
    price = np.column_stack((op, np.maximum(op, close)+rng.uniform(.01, .08, n),
                             np.minimum(op, close)-rng.uniform(.01, .08, n), close))
    valid = np.ones(n, bool)
    valid[101::191] = False
    times[n//2:] += 900
    return dict(times=times, prices=price, complete=valid, starts_at_open=np.ones(n, bool),
                observed_open_times=times.copy())


def assert_fields_equal(left, right):
    assert left.keys() == right.keys()
    for key in left:
        np.testing.assert_allclose(left[key], right[key], rtol=1e-12, atol=1e-10, equal_nan=True,
                                   err_msg=key)


def test_independent_features_synthetic_gaps_and_prefixes():
    data = synthetic()
    own, other = independent.features(data), research.features(data)
    for width in own:
        np.testing.assert_array_equal(own[width][0], other[width][0])
        assert_fields_equal(own[width][1], other[width][1])
    for length in (1003, 2048):
        cut = {key: value[:length] for key, value in data.items()}
        shortened = independent.features(cut)
        for width, (t, fields) in shortened.items():
            # The final incomplete higher bucket is deliberately not compared.
            finished = t+width <= cut['times'][-1]+300
            full = own[width]
            for key in fields:
                np.testing.assert_allclose(fields[key][finished], full[1][key][:int(finished.sum())],
                                           rtol=1e-12, atol=1e-10, equal_nan=True)


def test_independent_signals_synthetic_and_prefix():
    data = synthetic(18000)
    expected = research.signals(data, .001, 0, 10**9)
    actual = independent.signals(data, .001, 0, 10**9)
    assert_fields_equal(actual, expected)
    for length in (1003, 9007):
        prefix = independent.signals({key: value[:length] for key, value in data.items()}, .001, 0, 10**9)
        assert_fields_equal(prefix, {key: value[..., :length] for key, value in actual.items()})


def test_strict_pivot_confirmed_after_right_two_and_equal_rejected():
    t = np.arange(8)*300
    price = np.array([[8, h, 5, 8] for h in [9, 10, 12, 10, 9, 10, 12, 13]], float)
    valid = np.ones(8, bool)
    state = independent.frame_features(t, price, valid, 300)
    assert np.isnan(state['high'][:4]).all()
    assert state['high'][4] == 12
    assert state['high_known'][4] == 1500
    tied = price.copy()
    tied[3, 1] = 12
    state = independent.frame_features(t, tied, valid, 300)
    assert np.isnan(state['high']).all()


def test_reversal_ema_cross_can_be_phase1_but_simultaneous_m15_cannot():
    data = synthetic(18)
    frames = independent.features(data)
    # Controlled causal state transitions isolate sequencing from indicator math.
    for width, (t, fields) in frames.items():
        for key in ('gap', 'reversal', 'cross'):
            fields[key][:] = 0
        fields['direction'][:] = fields['agreement'][:] = 1
        fields['low'][:] = 100
        fields['low_known'][:] = 0
    f5, f15 = frames[300][1], frames[900][1]
    f15['reversal'][4] = 1  # Close time 4500; M5 row 14.
    f5['reversal'][14] = 1
    f5['reversal'][15] = f5['cross'][15] = 1
    f5['cross'][16] = -1
    f5['cross'][17] = 1
    own = independent.signals(data, .001, 0, 10**9, frames)
    assert own['sides'][1, 14] == 0
    assert own['sides'][1, 15] == 1
    assert own['episode_phase'][15] == 1
    assert own['sides'][0, 17] == 1
    assert_fields_equal(own, research.signals(data, .001, 0, 10**9, frames))


def arbitrary_signals(data):
    n = len(data['times'])
    output = {key: np.full((2, n), np.nan) for key in ('stops', 'scenario_times', 'episode_times')}
    output['sides'] = np.zeros((2, n), np.int8)
    for i in range(1, n-1, 5):
        side = 1 if i % 3 else -1
        output['sides'][:, i] = side
        output['stops'][:, i] = data['prices'][i, 3]-side*.2
        output['scenario_times'][:, i] = data['times'][i]
        output['episode_times'][:, i] = data['times'][i]+300
    return output


def test_independent_execution_fee_floor_gaps_and_all_statistics():
    data = synthetic(1200)
    data['starts_at_open'][70::173] = False
    data['complete'][70::173] = False
    data['observed_open_times'][70::173] += 60
    sig = arbitrary_signals(data)
    account = dict(initial_yen=1_000_000, stop_equity_yen=900_000, risk_fraction=.005,
                   quantity_step=1000, max_leverage=25)
    for cash in (None, account, dict(account, initial_yen=901_100)):
        for rr in (1., 1.5, 2.):
            for cost in (0., .016, .032):
                actual = independent.simulate(data, sig, 0, rr, 0, 10**9, cost, cash)
                expected = research.simulate(data, sig, 0, rr, 0, 10**9, cost, cash)
                independent.compare(actual, expected, f'simulate.{rr}.{cost}.{cash is not None}')
                independent.compare(independent.metrics(actual[0]), research.metrics(expected[0]))


def test_entry_does_not_depend_on_future_completeness_and_open_mark_is_separate():
    data = synthetic(3)
    data['prices'][:] = [110, 111, 109, 110]
    data['times'][:] = [0, 300, 600]
    data['observed_open_times'][:] = data['times']
    signal = arbitrary_signals(data)
    signal['stops'][:, 1] = 100
    data['complete'][2] = False
    rows, summary = independent.simulate(data, signal, 0, 1., 0, 900, .2)
    assert rows == [] and len(summary['open_marks']) == 1
    assert summary['open_marks'][0]['entry_time'] == 600
    assert summary['open_marks'][0]['pending_gap']
    assert independent.metrics(rows)['trades'] == 0
    independent.compare((rows, summary), research.simulate(data, signal, 0, 1., 0, 900, .2))
