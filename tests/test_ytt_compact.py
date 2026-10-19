"""Refactor invariants; these checks do not claim Pine compilation."""
from scripts.simplify_ytt_pine import SOURCE, TARGET, CELL, arguments, simplify


def test_reproducible_with_all_inputs_and_price_drawings():
    original = SOURCE.read_text(encoding='utf-8')
    compact = TARGET.read_text(encoding='utf-8')
    assert compact == simplify(original)
    assert [x for x in compact.splitlines() if 'input.' in x] == [x for x in original.splitlines() if 'input.' in x]
    for call in ('line.new(', 'label.new(', 'plot(', 'alertcondition(', 'alert('):
        assert compact.count(call) == original.split('// Multi-symbol reversal scanner')[0].count(call)
    assert CELL in compact  # Helper is not recursively rewritten.


def test_signal_and_fill_blocks_are_unchanged():
    import re
    a, b = (p.read_text(encoding='utf-8') for p in (SOURCE, TARGET))
    for start, end in [('// User-selected analysis filter', 'f_tfName('),
                       ('f_previousSnapshot() =>', 'scan_f_direction('),
                       ('// BB reversal:', '// Multi-symbol reversal scanner')]:
        before = a[a.index(start):a.index(end)] if end in a else ''
        if end == 'f_tfName(':
            before = before[:before.rfind('color candidateColor')]  # Display helpers follow the signal block.
            assert before in b
        elif end == '// Multi-symbol reversal scanner':
            # Table calls are refactored separately; state/ledger prior to stats are verbatim.
            before = before[:before.index('var table BB_winStats')]
            before = re.sub(r'\n{3,}', '\n\n', before)
            assert before in b
        else:
            assert before in b


def test_table_argument_rewrite_preserves_cells_in_order():
    import re
    original = SOURCE.read_text(encoding='utf-8').split('// Multi-symbol reversal scanner')[0]
    compact = TARGET.read_text(encoding='utf-8').replace(CELL, '')
    def cells(source):
        result = []
        for line in source.splitlines():
            match = re.fullmatch(r'\s*(table\.cell|f_cell)\((.*)\)', line)
            if not match:
                continue
            args = arguments(match[2])
            named = dict(x.split('=', 1) for x in args[4:])
            named = {k.strip(): v.strip() for k,v in named.items()}
            if match[1] == 'f_cell':
                named = {'text_color': named.get('ink','color.white'), 'bgcolor': named.get('bg','na'), 'text_size': named.get('font','size.small')}
            for key, default in [('text_color','color.black'), ('bgcolor','na'), ('text_size','size.normal')]:
                named.setdefault(key, default)
            result.append((args[:4], named))
        return result
    assert cells(original) == cells(compact)


def test_scanner_direction_state_matches_shared_function():
    import re
    source = SOURCE.read_text(encoding='utf-8')
    common = source.split('f_state() =>\n',1)[1].split('f_previousState() =>')[0]
    scanner = source.split('scan_f_state() =>\n',1)[1].split('scan_f_previousState() =>')[0]
    common = '\n'.join(x for x in common.splitlines() if not any(v in x for v in ('priorHigh', 'priorLow', 'highText', 'lowText')))
    common += '\n    [direction, lastHigh, lastLow]\n'
    normalize = lambda s: re.sub(r'\s+', '',re.sub(r'//[^\n]*', '', s))
    assert normalize(common) == normalize(scanner)
