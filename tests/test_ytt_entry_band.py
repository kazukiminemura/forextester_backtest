"""Display contracts, including the unshifted open's explicit time guard."""
from scripts.build_ytt_entry_band import SOURCE, TARGET, BAND, INPUTS, build


def test_only_display_and_snapshot_payload_change():
    source = SOURCE.read_text(encoding='utf-8')
    result = TARGET.read_text(encoding='utf-8')
    assert result == build(source)
    # All existing signal, freshness and alert blocks remain verbatim.
    for start, end in [('f_state() =>', 'f_previousState() =>'),
                       ('// User-selected analysis filter', '// YTT public-feature approximation'),
                       ('f_previousSnapshot() =>', '    Snapshot.new('),
                       ('float entrySeconds =', '// BB reversal: independent research-only')]:
        block = source[source.index(start):source.index(end, source.index(start))]
        block = block.replace('// ALL fields are offset. No developing entry bar or HTF value can escape.',
                              '// Signal/ATR/HTF fields are offset. Only the new bar open/time are unshifted and time-guarded.')
        assert block in result
    assert result.count('request.security(') == source.count('request.security(')
    assert INPUTS in result and BAND in result


def test_band_is_confirmed_scanner_data_for_current_symbol():
    text = TARGET.read_text(encoding='utf-8')
    assert 'array.indexof(symbols, syminfo.tickerid)' in BAND
    assert 'array.get(simpleSnapshots, chartSymbolIndex)' in BAND
    assert 'Snapshot.new(status[1], priceText[1], d1[1], d2[1], time_close[1], displayedPrice[1], ta.atr(14)[1], open, time)' in text
    assert 'openedAt != stamp or nowMs < stamp' in BAND
    assert 'nowMs >= stamp + durationMs' in BAND
    assert 'math.min(entrySeconds * 1000, bandMinutes * 60000)' in BAND
    assert 'state == 3 ? price > lower : price < upper' in BAND
    assert 'box.delete(entryBand)' in BAND and 'xloc=xloc.bar_time' in BAND

