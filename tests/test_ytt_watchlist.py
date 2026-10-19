"""Monitor composition and coverage; these are not Pine runtime tests."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('watch_builder', ROOT / 'scripts/build_ytt_watchlist_pine.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_all_screenshot_symbols_are_covered_once():
    expected = {'XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'EURJPY', 'GBPJPY', 'NZDJPY', 'CADJPY', 'AUDJPY',
                'USDCHF', 'USDCAD', 'NZDUSD', 'EURAUD', 'EURCHF', 'GBPCHF', 'AUDNZD', 'EURGBP', 'AUDUSD'}
    symbols = sum((list(group) for group in builder.GROUPS.values()), [])
    assert len(symbols) == len(set(symbols)) == 18
    assert set(symbols) == expected


def test_each_monitor_is_reproducible_and_within_the_normal_request_budget():
    for group in builder.GROUPS:
        source = builder.watchlist_source(group)
        assert source == (ROOT / f'scripts/tradingview/yosuga_ytt_watchlist_{group}.pine').read_text(encoding='utf-8')
        assert source.count('input.symbol(') == 9
        assert 'for i = 0 to 8' in source
        assert 'array.new_int(9, na)' in source
        assert 'simplePanel, 0, 12, message' in source
        assert 'table.new(position.top_center, 3, 13,' in source
        assert 'Snapshot.new(status[1], priceText[1], d1[1], d2[1], time_close[1])' in source
        if group == 'b':
            assert source.count('request.security(') == 3  # 9 * (entry + two HTFs) = 27
        else:
            assert 'string combinedScanner = "YTT"' in source  # BB multi-symbol requests cannot run
            assert '価格描画＋9銘柄' in source  # <=27 + 8 chart contexts + 1 BB chart = 36
        assert 'newClose and eventNow and not stale' in source
        assert 'ignore_invalid_symbol=true' in source
        if group == 'b':
            assert 'f_tfName(' not in source.replace('scan_f_tfName(', '')
        assert 'simplePanel, 0, 12, 2, 11' not in source


def test_unified_has_full_coverage_and_explicit_request_budget_guard():
    source = builder.unified_source()
    assert source == (ROOT / 'scripts/tradingview/yosuga_ytt_watchlist_unified.pine').read_text(encoding='utf-8')
    assert source.count('input.symbol(') == 18
    assert 'bool valid = watchBudgetValid and chart.is_standard' in source
    assert 'if valid\n        data := request.security' in source
    assert 'array.new_int(18, na)' in source
    assert 'for i = 0 to array.size(symbols) - 1' in source
    assert 'table.new(position.top_center, 3, 22,' in source
    assert 'simplePanel, 0, 21, 2, 21' in source
    assert 'string message = not watchBudgetValid ?' in source
    assert 'string note = not watchBudgetValid ?' in source
