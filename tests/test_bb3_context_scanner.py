"""Scanner source contracts and boundary models; NOT a Pine runtime/compiler."""
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/tradingview/bb3_context_pf_indicator.pine'
FULL = PATH.read_text(encoding='utf-8')
CORE, SCANNER = FULL.split('// Multi-symbol opportunity scanner', 1)
SNAPSHOT = SCANNER.split('scannerSnapshot() =>', 1)[1].split('scannerName(', 1)[0]


def test_requests_are_confirmed_local_symbol_snapshots():
    assert SCANNER.count('input.symbol(') == 11
    assert SCANNER.count('request.security(') == 1
    assert 'request.security(symbol, timeframe.period, scannerSnapshot(),' in SCANNER
    assert 'lookahead=barmerge.lookahead_on, ignore_invalid_symbol=true' in SCANNER
    assert '[state[1], distance[1], time_close[1], skip[1], winningTrades[1], closedTrades[1]]' in SNAPSHOT
    assert 'barstate.isconfirmed' not in SNAPSHOT
    assert 'barstate.isconfirmed' not in SCANNER.split('scannerSnapshot() =>')[0]
    assert 'calc_bars_count=' not in SCANNER  # Do not truncate occupancy history silently.
    assert '(syminfo.currency == "JPY" ? 0.01 : 0.0001)' in SNAPSHOT
    assert 'slPips * unit / syminfo.mintick' in SNAPSHOT
    assert 'roundPips * unit / syminfo.mintick' in SNAPSHOT


def test_remote_state_keeps_chart_filters_and_occupancy():
    for text in ['ta.sma(close, length)', 'ta.stdev(close, length, true)',
                 'ta.highest(high[1], lookback)', 'ta.lowest(low[1], lookback)',
                 'ta.atr(14)[1]', 'bar_index - preparationBar > expiry',
                 'preparation * (center - close) / unit + 1e-9 < minCenterPips',
                 'skip != "" or signal != 0',
                 'positionSide == 0 and queuedSide == 0 and not closed',
                 'stop := useStop ? open - positionSide * ticks * syminfo.mintick : na',
                 'exitFill(positionSide, open, high, low, target, stop)',
                 'if not canPrepare or sourceGap']:
        assert text in SNAPSHOT
    assert SNAPSHOT.count('= scannerImpulse(') == 4
    assert SNAPSHOT.count('longWick(') == 2
    assert SNAPSHOT.index('exitFill(') < SNAPSHOT.index('target := center')
    for forbidden in ['label.new(', 'table.', 'alert(', 'grossProfit', 'closedCount']:
        assert forbidden not in SNAPSHOT


def test_ranking_ui_and_chart_pf_remain_separate():
    assert 'scannerPosition = input.string("左下", "一覧の位置"' in SCANNER
    for text in ['position.top_left : position.bottom_left',
                 'array.indexof(scannerSymbols, symbol) < i',
                 'symbol == "" ? syminfo.tickerid : symbol',
                 'scannerRank(array.get(scannerStates',
                 '"BUY信号"', '"SELL信号"', '"買い準備"', '"売り準備"',
                 '"データなし"', '"更新待ち（古い）"', '"中央線幅 pips"',
                 '"Asia/Tokyo"', 'table.clear(scanner, 0, 0, 5, 12)']:
        assert text in SCANNER
    assert CORE.count('tableRow(notice,') == 9
    assert CORE.count('alertcondition(') == 3
    assert 'grossProfit +=' not in SCANNER
    assert 'grossLoss +=' not in SCANNER


def test_notification_guard_source():
    for text in ['scannerAlerts = input.bool(false',
                 'varip array<int> scannerNotified',
                 'bool seed = barstate.isrealtime and not na(stamp)',
                 'and not seed and math.abs(state) == 3',
                 'stamp != array.get(scannerNotified, i)',
                 'array.set(scannerNotified, i, stamp)', 'alert.freq_all',
                 'timenow - stamp > timeframe.in_seconds() * 2000',
                 'state := na(state) or na(stamp) ? 6 : stale ? 7 : state']:
        assert text in SCANNER


def displayed_state(state, stamp, now, seconds=300):
    if state is None or stamp is None:
        return 6
    return 7 if now - stamp > seconds * 2000 or stamp > now else state


def test_scanner_win_rate_accounting_and_display():
    settlement = SNAPSHOT.split('if not na(price)', 1)[1].split('else', 1)[0]
    assert 'closedTrades += 1' in settlement
    assert 'winningTrades += tradePips(positionSide, filledEntry, price, unit, costPips) > 0 ? 1 : 0' in settlement
    assert settlement.index('tradePips(') < settlement.index('positionSide := 0')
    assert 'filledEntry := open' in SNAPSHOT
    assert SNAPSHOT.count('closedTrades +=') == 1
    for token in ['position.bottom_left, 6, 13)', '"勝率", "決済数"',
                  'statsReady and trades > 0', '100.0 * wins / trades',
                  'array.set(scannerWins, i, wins)', 'array.set(scannerClosed, i, trades)',
                  'table.cell(scanner, 4, row + 2, rate',
                  'table.cell(scanner, 5, row + 2, statsReady']:
        assert token in SCANNER


@pytest.mark.parametrize('side,unit,entry,exit_price,cost,win', [
    (1, .01, 150, 150.03, 1.4, True),
    (-1, .0001, 1.1, 1.0997, 1.4, True),
    (1, .01, 150, 150.01, 1.4, False),
    (-1, .0001, 1.1, 1.1003, 1.4, False),
    (1, .01, 150, 150, 0, False),
])
def test_scanner_net_win_boundary_reference(side, unit, entry, exit_price, cost, win):
    assert (side * (exit_price - entry) / unit - cost > 0) is win


@pytest.mark.parametrize('state,stamp,now,expected', [
    (3, 1000000, 1000000, 3), (-3, 1000000, 1300000, -3),
    (2, 1000000, 1600000, 2), (3, 1000000, 1600001, 7),
    (-3, 1000000, 1000000 + 86400000 * 2, 7),
    (3, 1000001, 1000000, 7), (None, None, 1000000, 6),
])
def test_stale_and_missing_boundary_reference(state, stamp, now, expected):
    assert displayed_state(state, stamp, now) == expected


def test_per_symbol_notification_reference_seeds_and_deduplicates():
    last = [0, 0]
    def update(index, state, stamp, now):
        state = displayed_state(state, stamp, now)
        seed = stamp is not None and last[index] == 0
        if seed:
            last[index] = stamp
        notify = not seed and abs(state) == 3 and stamp != last[index]
        if notify:
            last[index] = stamp
        return notify
    assert not update(0, 3, 1000000, 1000000)  # Existing signal on attachment.
    assert not update(1, -3, 1000000, 1000000)
    assert update(0, 3, 1300000, 1300000)
    assert not update(0, 3, 1300000, 1300000)  # Same source bar, another tick.
    assert update(1, -3, 1300000, 1300000)  # Another pair can notify same tick.
    assert not update(0, 3, 1600000, 2300001)  # Stale signal never alerts.


def test_stable_opportunity_sort_reference():
    def rank(state):
        return {3: 0, 2: 1, 1: 2}.get(abs(state), 3 if state == 4 else 4 if state == 0 else 5)
    states = [0, 7, 2, -3, 1, 3, -2, 4, 6]
    assert sorted(range(len(states)), key=lambda i: rank(states[i])) == [3, 5, 2, 6, 4, 7, 0, 1, 8]
