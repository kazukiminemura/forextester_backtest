"""Independent RR1 accounting examples; not execution of Pine or a backtest."""
import pytest
from pathlib import Path


def ledger(bars, cost=1.0):
    """Bars: (open, high, low, close, signal, center, gap); pip=1 for examples."""
    position = pending = None
    results = []
    for op, hi, lo, cl, signal, center, gap in bars:
        if pending:
            direction, target = pending
            if not gap and direction * (target - op) >= 3:
                position = direction, op, target, 2 * op - target
            pending = None
        if position:
            direction, entry, target, stop = position
            if direction * (op - stop) <= 0 or direction * (op - target) >= 0:
                fill = op
            elif (lo <= stop if direction == 1 else hi >= stop):
                fill = stop
            elif (hi >= target if direction == 1 else lo <= target):
                fill = target
            else:
                fill = None
            if fill is not None:
                results.append(direction * (fill - entry) - cost)
                position = None
        if not position and signal:
            pending = signal, center
    floating = position[0] * (bars[-1][3] - position[1]) - cost if position else 0
    return results, floating


@pytest.mark.parametrize('direction', [1, -1])
def test_next_open_fixed_rr1_and_entry_bar_stop_priority(direction):
    bars = [(100, 110, 90, 100, 1, 105, False),  # signal-bar extremes not executed
            (100, 106, 94, 101, 0, 120, False)]
    if direction == -1:
        bars = [(200-o, 200-l, 200-h, 200-c, -s, 200-t, g) for o,h,l,c,s,t,g in bars]
    assert ledger(bars) == ([-6], 0)


def test_fixed_target_not_following_center_and_gap_exit():
    initial = [(100, 101, 99, 100, 1, 105, False),
               (100, 102, 99, 101, 0, 110, False)]
    assert ledger(initial + [(101, 106, 100, 102, 0, 110, False)]) == ([4], 0)
    assert ledger(initial + [(90, 94, 89, 91, 0, 110, True)]) == ([-11], 0)
    assert ledger(initial + [(108, 109, 90, 100, 0, 110, True)]) == ([7], 0)


@pytest.mark.parametrize('op,gap', [(103, False), (105, False), (106, False), (100, True)])
def test_pending_invalid_room_or_missing_bar_not_counted(op, gap):
    assert ledger([(100,101,99,100,1,105,False), (op,110,90,100,0,105,gap)]) == ([],0)


def test_open_trade_not_a_win_and_overlap_ignored():
    bars = [(100,101,99,100,1,105,False), (100,102,99,101,-1,95,False),
            (101,103,99,102,0,110,False)]
    assert ledger(bars) == ([],1)
    results, _ = ledger(bars + [(102,105,101,104,0,120,False)], cost=5)
    assert results == [0]
    assert sum(value > 0 for value in results) == 0


def test_close_can_queue_new_signal_for_next_bar():
    bars = [(100,101,99,100,1,105,False), (100,106,99,105,-1,100,False),
            (105,106,99,100,0,100,False)]
    assert ledger(bars) == ([4,4],0)


def test_pine_rr1_contract_and_separate_candidate_stream():
    path = Path(__file__).resolve().parents[1] / 'scripts/tradingview/bb3_reversal_confirmation_indicator.pine'
    s = path.read_text(encoding='utf-8')
    core = s.split('// Chart-only constant-memory ledger;',1)[1].split('plot(basis,',1)[0]
    for token in ['if barstate.isconfirmed', 'time == statsPendingTime',
                  'statsEntry := open', 'statsTarget := statsPendingTarget',
                  'statsStop := 2 * statsEntry - statsTarget',
                  'stopAtOpen or targetAtOpen ? open : stopTouched ? statsStop : targetTouched ? statsTarget : na',
                  'statsClosed += 1', 'statsWins += statsNetPips > 1e-9 ? 1 : 0',
                  'statsPendingTarget := math.round_to_mintick(basis)',
                  'statsPendingTime := time_close', '100.0 * statsWins / statsClosed']:
        assert token in core
    assert core.index('if statsSide == 0 and statsPendingSide != 0') < core.index('if statsSide != 0') < core.index('if statsSide == 0 and candidateSide != 0')
    assert 'candidateSide :=' not in core
    assert core.count('statsTarget :=') == 2  # entry and clear only; never chase center
    assert 'request.security(' not in core


def test_fractional_pip_breakeven_is_not_counted_as_win():
    theoretical_zero = (150.003 - 150.0) / .01 - .3
    assert abs(theoretical_zero) < 1e-9
    assert not theoretical_zero > 1e-9
