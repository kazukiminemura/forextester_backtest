"""Causality and execution boundaries for the pre-registered BALLY EMA proxy."""
import numpy as np
from scripts import research_bari_video_20261016 as m


def bars(n=80):
    times = np.arange(n, dtype=np.int64)*300
    return dict(times=times, prices=np.tile([110., 111., 109., 110.], (n, 1)),
                complete=np.ones(n, bool), starts_at_open=np.ones(n, bool), observed_open_times=times.copy())


def episode_case():
    data = bars()
    f = {}
    for s in (300, 900, 3600, 14400):
        times = np.arange(0, data['times'][-1]+1, s)
        n = len(times)
        z = dict(direction=np.ones(n, np.int8), agreement=np.ones(n, np.int8),
                 reversal=np.zeros(n, np.int8), cross=np.zeros(n, np.int8),
                 gap=np.zeros(n, bool), low=np.full(n, 100.), high=np.full(n, 120.),
                 low_known=times.copy(), high_known=times.copy())
        f[s] = (times, z)
    f[900][1]['reversal'][3] = 1  # M15 closes 3600.
    f[300][1]['reversal'][15] = 1  # M5 closes 4800.
    f[300][1]['cross'][[15, 20]] = 1
    f[300][1]['cross'][18] = -1
    return data, f


def test_reversal_cross_counts_and_steps_are_separate():
    data, f = episode_case()
    s = m.signals(data, .01, 0, 999999, f)
    assert np.flatnonzero(s['sides'][1]).tolist() == [15]
    assert np.flatnonzero(s['sides'][0]).tolist() == [20]
    assert s['episode_phase'][15] == 1
    assert s['stops'][0, 20] == 99.99
    f[300][1]['cross'][15] = 0
    s = m.signals(data, .01, 0, 999999, f)
    assert not s['sides'][0].any()  # Being above EMA is not a true cross.


def test_same_close_m15_m5_forbidden_and_context_cannot_resurrect():
    data, f = episode_case()
    f[300][1]['reversal'][15] = 0
    f[300][1]['reversal'][11] = 1  # closes 3600, same as M15
    assert not m.signals(data, .01, 0, 999999, f)['sides'].any()
    data, f = episode_case()
    f[3600][1]['agreement'][0] = 0
    assert not m.signals(data, .01, 0, 999999, f)['sides'].any()


def test_episode_stop_cancel_and_gap_loss():
    data, f = episode_case()
    data['prices'][17, 2] = 99.99
    s = m.signals(data, .01, 0, 999999, f)
    assert not s['sides'][0].any() and s['cancel_reason'][17] == 3
    data, f = episode_case()
    f[300][1]['gap'][17] = True
    s = m.signals(data, .01, 0, 999999, f)
    assert not s['sides'][0].any() and s['cancel_reason'][17] == 1


def test_pivot_lag_and_equal_high_rejected():
    t = np.arange(8)*300
    p = np.column_stack(([1]*8, [2, 3, 5, 3, 2, 6, 7, 8], [0]*8, [1, 1, 1, 1, 1, 6, 6, 7]))
    f = m.frame_features(t, p, np.ones(8, bool), 300)
    assert np.isnan(f['high'][3]) and f['high'][4] == 5
    assert f['high_known'][4] == 1500
    assert f['direction'][4] == 0 and f['direction'][5] == 1
    assert f['reversal'][5] == 0  # first direction is not reversal
    p[3, 1] = 5
    assert np.isnan(m.frame_features(t, p, np.ones(8, bool), 300)['high'][4])


def test_ema_sma_seed_gap_preserves_value_but_disables_cross():
    data = bars(30)
    data['prices'][:, 3] = np.arange(30)+100
    data['complete'][25] = False
    f = m.frame_features(data['times'], data['prices'], data['complete'], 300)
    assert np.isnan(f['ema'][23]) and f['ema'][24] == 112
    assert f['ema'][25] == 112
    assert np.isclose(f['ema'][26], 112+(2/26)*(126-112))
    assert f['cross'][26] == 0 and f['agreement'][26] == 0


def test_prefix_future_cutoff_invariance():
    data = bars(2500)
    rng = np.random.default_rng(41)
    cl = 110+np.cumsum(rng.normal(0, .1, len(data['times'])))
    op = np.r_[cl[0], cl[:-1]]
    data['prices'] = np.column_stack((op, np.maximum(op, cl)+.07, np.minimum(op, cl)-.07, cl))
    all_signals = m.signals(data, .001, 0, 99999999)
    for length in (1888, 2131):
        cut = {k: v[:length] for k, v in data.items()}
        before = m.signals(cut, .001, 0, 99999999)
        for key, value in before.items():
            expected = all_signals[key][:, :length] if value.ndim == 2 else all_signals[key][:length]
            np.testing.assert_array_equal(value, expected)


def trade_case(n=6, stop=100.):
    data = bars(n)
    sig = {k: np.full((2, n), np.nan) for k in ('stops', 'scenario_times', 'episode_times')}
    sig['sides'] = np.zeros((2, n), np.int8)
    sig['sides'][0, 0] = 1
    sig['stops'][0, 0] = stop
    sig['scenario_times'][0, 0] = 0
    sig['episode_times'][0, 0] = 300
    return data, sig


def test_incomplete_entry_bar_not_future_filter_and_later_open_liquidates():
    data, sig = trade_case()
    data['complete'][1] = False
    data['prices'][2, :] = [112, 113, 111, 112]
    rows, info = m.simulate(data, sig, 0, 1, 0, 99999, .2)
    assert len(rows) == 1
    assert rows[0]['entry_time'] == 300 and rows[0]['exit_time'] == 600
    assert rows[0]['reason'] == 'missing_next_open' and rows[0]['exit'] == 112
    assert np.isclose(rows[0]['net_r'], .18)


def test_incomplete_bar_resting_orders_sl_first_and_open_gap_prices():
    data, sig = trade_case()
    data['complete'][1] = False
    data['prices'][1] = [110, 121, 99, 110]
    rows, _ = m.simulate(data, sig, 0, 1, 0, 99999, .2)
    assert rows[0]['exit'] == 100 and rows[0]['reason'] == 'stop'
    for op, expected, reason in ((95, 95, 'stop_gap'), (125, 120, 'target_gap')):
        data, sig = trade_case()
        data['prices'][2] = [op, op+1, op-1, op]
        rows, _ = m.simulate(data, sig, 0, 1, 0, 99999, 0.)
        assert rows[0]['exit'] == expected and rows[0]['reason'] == reason


def test_late_observed_open_is_gap_when_bucket_is_contiguous():
    data, sig = trade_case()
    data['starts_at_open'][2] = False
    data['complete'][2] = False
    data['observed_open_times'][2] += 60
    data['prices'][2] = [112, 113, 111, 112]
    rows, _ = m.simulate(data, sig, 0, 1, 0, 99999, 0.)
    assert rows[0]['exit_time'] == 660 and rows[0]['reason'] == 'missing_next_open'


def test_open_mark_excluded_and_time_exit_at_48():
    data, sig = trade_case(49)
    rows, info = m.simulate(data, sig, 0, 1, 0, 600, .2)
    assert not rows and len(info['open_marks']) == 1
    assert m.metrics(rows)['trades'] == 0
    rows, info = m.simulate(data, sig, 0, 1, 0, 999999, .2)
    assert rows[0]['hold_bars'] == 48 and rows[0]['reason'] == 'time'
    assert not info['open_marks']


def test_cash_fee_once_and_gap_floor_overshoot_permanent_halt():
    account = dict(initial_yen=1_000_000, stop_equity_yen=900_000, risk_fraction=.005,
                   quantity_step=1000, max_leverage=25)
    data, sig = trade_case(stop=109.)
    data['prices'][1] = [110, 111.2, 109.5, 111]
    rows, info = m.simulate(data, sig, 0, 1, 0, 999999, .1, account)
    assert rows[0]['quantity'] == 4000
    assert info['cash_equity_yen'] == 1_003_600
    assert rows[0]['fees_yen'] == 400
    data, sig = trade_case(stop=109.)
    data['prices'][1] = [110, 110.2, 109.5, 110]
    data['prices'][2] = [80, 81, 79, 80]
    sig['sides'][0, 3] = 1
    sig['stops'][0, 3] = 109
    sig['scenario_times'][0, 3] = 0
    sig['episode_times'][0, 3] = 1200
    rows, info = m.simulate(data, sig, 0, 1, 0, 999999, .1, account)
    assert len(rows) == 1 and info['halted']
    assert info['cash_equity_yen'] == 879_600  # Never clamp gap loss to 900,000.


def test_floor_limit_quantities_and_metrics_zero_loss():
    account = dict(initial_yen=901_100, stop_equity_yen=900_000, risk_fraction=.005,
                   quantity_step=1000, max_leverage=25)
    data, sig = trade_case(stop=109.)
    data['prices'][1] = [110, 110.2, 108.9, 109]
    rows, info = m.simulate(data, sig, 0, 1, 0, 999999, .1, account)
    assert rows[0]['quantity'] == 1000 and info['cash_equity_yen'] == 900_000
    assert info['halted']
    stats = m.metrics([{'net_r': 1.}, {'net_r': 2.}])
    assert stats['pf'] is None and stats['pf_infinite'] and m.pf_value(stats) == np.inf
    assert stats['wilson95'][0] < 1 and stats['wilson95'][1] == 1
    assert m.metrics([])['wilson95'] == [None, None]


def test_year_boundary_actual_open_vs_previous_bar_close():
    midnight = m.epoch('2023-01-01')
    assert m.exit_year(dict(exit_time=midnight, exit_at_observed_open=True)) == 2023
    assert m.exit_year(dict(exit_time=midnight, exit_at_observed_open=False)) == 2022
