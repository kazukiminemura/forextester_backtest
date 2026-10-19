"""Behavior-preserving simplification of the pasted unified YTT indicator."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/tradingview/yosuga_ytt_watchlist_unified.pine'
TARGET = ROOT / 'scripts/tradingview/yosuga_ytt_compact.pine'
CELL = '''f_cell(table panel, int col, int row, string cellText, color ink=color.white, color bg=na, string font=size.small) =>
    table.cell(panel, col, row, cellText, text_color=ink, bgcolor=bg, text_size=font)

'''


def arguments(text):
    """Split Pine arguments without splitting strings or nested expressions."""
    parts, start, depth, quoted, escaped = [], 0, 0, False, False
    for i, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return parts


def simplify(source):
    assert 'string combinedScanner = "YTT"' in source
    assert 'bool BB_showScanner = combinedScanner == "BB3σ反転"' in source
    # That scanner is unreachable; the BB chart, ledger and alerts remain.
    source = source.split('// Multi-symbol reversal scanner\n', 1)[0]
    source = source.replace('string combinedScanner = "YTT"\n', '')
    source = source.replace('combinedScanner == "YTT" and ', '')
    source = re.sub(r'scan_f_state\(\) =>\n.*?(?=scan_f_previousState\(\))',
                    'scan_f_state() =>\n    [d, h, l, structure] = f_state()\n    [d, h, l]\n\n', source, flags=re.S)
    if source.count('f_tfName(') == 1:
        source = re.sub(r'f_tfName\(string tf\) =>\n.*?(?=var line candidateLine)', '', source, flags=re.S)
    source = re.sub(r'^    float displayedCandidatePrice = .*\n', '', source, flags=re.M)
    lines = []
    for line in source.splitlines():
        match = re.fullmatch(r'(\s*)table\.cell\((.*)\)', line)
        if match:
            args = arguments(match[2])
            named = dict(x.split('=', 1) for x in args[4:] if '=' in x)
            named = {k.strip(): v.strip() for k, v in named.items()}
            if len(args) >= 4 and 'text_color' in named and set(named) <= {'text_color', 'text_size', 'bgcolor'}:
                compact = args[:4]
                for key, rename, default in [('text_color', 'ink', 'color.white'), ('bgcolor', 'bg', 'na'), ('text_size', 'font', 'size.small')]:
                    value = named.get(key, 'size.normal' if key == 'text_size' else default)
                    if value != default:
                        compact.append(f'{rename}={value}')
                line = match[1] + 'f_cell(' + ', '.join(compact) + ')'
        lines.append(line)
    compact = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).rstrip() + '\n'
    return compact.replace('f_price(float value) =>', CELL + 'f_price(float value) =>', 1)


if __name__ == '__main__':
    before = SOURCE.read_text(encoding='utf-8')
    after = simplify(before)
    TARGET.write_text(after, encoding='utf-8', newline='\n')
    print(f'{len(before.splitlines())} -> {len(after.splitlines())} lines; {len(before.encode())} -> {len(after.encode())} bytes')
