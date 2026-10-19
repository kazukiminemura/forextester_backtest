"""Compose the existing YTT utilities and research-only BB reversal indicator.

Only integration/display settings change. The three standalone sources remain
authoritative for their independent candidate rules; this is not an AND strategy.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent / "tradingview"

# Keep Japanese captions, alert strings and comments byte-for-byte while renaming
# identifiers. Regex word replacement over the entire source would corrupt them.
PINE_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|\b[A-Za-z_]\w*\b')


def rename_identifiers(source: str, names: set[str], prefix: str) -> str:
    return PINE_TOKEN.sub(lambda match: prefix + match[0] if match[0] in names else match[0], source)


def shift_table_rows(source: str, table: str, offset: int) -> str:
    pattern = rf'(table\.cell\({table},\s*[^,]+,\s*)(\d+|row)(\s*,)'
    return re.sub(pattern, lambda m: m[1] + (str(int(m[2]) + offset) if m[2].isdigit() else f'row + {offset}') + m[3], source)


def build_bb(source: str) -> str:
    source = "\n".join(line for line in source.splitlines()
                       if not line.startswith(("//@version", "indicator(", "string scannerPosition =")))
    source = source.replace('bool restrictChart = input.bool(true,', 'bool restrictChart = input.bool(false,')
    source = source.replace('bool showReasons = input.bool(true,', 'bool showReasons = input.bool(false,')
    source = source.replace('bool showWinStats = input.bool(true, "右下に勝率を表示",',
                            'bool showWinStats = input.bool(false, "右上にBB仮想勝率を表示",')
    source = source.replace('bool showScanner = input.bool(true, "通貨一覧を表示", group=gs)',
                            'bool showScanner = combinedScanner == "BB3σ反転"')
    # Both scanners use the same editable eight currency inputs.
    source = re.sub(r'^string scan\d+ = input.symbol\([^\n]+\)\n', '', source, flags=re.M)
    source = source.replace('array.from(scan01, scan02, scan03, scan04, scan05, scan06, scan07, scan08, scan09, scan10, scan11)',
                            'array.from(symbol1, symbol2, symbol3, symbol4, symbol5, symbol6, symbol7, symbol8)')
    source = source.replace('var table scanner = table.new(scannerPosition == "左上" ? position.top_left : position.bottom_left, 6, 13)',
                            'var table scanner = showScanner ? table.new(position.top_center, 6, 11) : na')
    source = source.replace('if barstate.isfirst\n    for i = 0 to 10',
                            'if barstate.isfirst\n    if showScanner\n        table.merge_cells(scanner, 0, 0, 5, 0)\n        table.cell(scanner, 0, 0, "", height=8, bgcolor=color.new(color.black, 100))\n    for i = 0 to 10')
    source = source.replace('table.cell(scanner, col, 0, array.get(notes, col)', 'table.cell(scanner, col, 1, array.get(notes, col)')
    source = source.replace('table.cell(scanner, col, 1, array.get(headers, col)', 'table.cell(scanner, col, 2, array.get(headers, col)')
    source = source.replace('row + 2,', 'row + 3,')
    source = re.sub(r'(array\.new_\w+\()11,', r'\g<1>8,', source)
    source = source.replace('for i = 0 to 10', 'for i = 0 to 7')
    source = source.replace('    if not showScanner\n        table.clear(scanner, 0, 0, 5, 12)\n', '')
    source = source.replace('var table winStats = table.new(position.bottom_right, 2, 7, bgcolor=color.new(color.black, 15))',
                            'var table winStats = candidatePanel')
    source = shift_table_rows(source, 'winStats', 7)
    source = source.replace('table.clear(winStats, 0, 0, 1, 6)', 'table.clear(winStats, 0, 7, 1, 13)')
    source = source.replace('右上にBB仮想勝率を表示', '右欄にBB仮想勝率を表示')
    # All source calls fit one physical line. Only the price visuals move panes;
    # the fill follows its two force-overlay plots without a separate argument.
    source = "\n".join(line[:-1] + ', force_overlay=true)' if re.search(r'\b(?:plot|plotshape|label\.new)\(', line)
                       and line.rstrip().endswith(')') else line for line in source.splitlines())
    source = source.replace('alertcondition(barstate.isconfirmed and', 'alertcondition(bbAlertsEnabled and barstate.isconfirmed and')
    source = source.replace('if barstate.isconfirmed and candidateSide != 0\n    alert(',
                            'if bbAlertsEnabled and barstate.isconfirmed and candidateSide != 0\n    alert(')
    # alert.freq_all is compatible with YTT's per-symbol notifications in this
    # combined script; the original confirmed-bar gate remains unchanged.
    source = source.replace('alert.freq_once_per_bar_close)', 'alert.freq_all)')
    names = set(re.findall(r'^(?:var\s+)?(?:int|float|string|bool|color|table|array<\w+>)\s+(\w+)\s*=', source, re.M))
    names.update(re.findall(r'^(\w+)\([^\n]*\)\s*=>', source, re.M))
    names.update(re.findall(r'^(\w+)\s*=\s*plot\(', source, re.M))
    source = rename_identifiers(source, names, 'BB_')
    # Leave capacity for YTT's 120 level labels, 40 events and current guides.
    # Otherwise BB's historical labels could trigger global GC of a live YTT tag.
    source = "\n".join('    BB_keepHistory(' + line.strip() + ')' if line.startswith('    label.new(')
                       else line for line in source.splitlines())
    history = '''var array<label> BB_historyLabels = array.new<label>()
BB_keepHistory(label item) =>
    array.push(BB_historyLabels, item)
    if array.size(BB_historyLabels) > (combinedSimple ? 0 : 300)
        label.delete(array.shift(BB_historyLabels))
    item

'''
    return history + source


def build() -> str:
    assistant = (ROOT / "yosuga_ytt_assistant.pine").read_text(encoding="utf-8")
    scanner = (ROOT / "yosuga_ytt_fx_scanner.pine").read_text(encoding="utf-8")
    bb = (ROOT / "bb3_reversal_confirmation_indicator.pine").read_text(encoding="utf-8")
    assistant = assistant.replace('indicator("よすが式 分析補助（YTT公開機能の近似）", overlay=true,',
                                  'indicator("よすが式 YTT統合版＋BB3σ反転（分析補助・研究用）", overlay=false,')
    assistant = assistant.replace('max_labels_count=150', 'max_labels_count=500')
    assistant = assistant.replace('\nstring gAuto =', '\nbool combinedSimple = input.bool(true, "シンプル表示（YTTの待ち・新規成立だけ）", group="統合表示")\nstring combinedScanner = input.string("YTT", "通貨一覧", options=["YTT", "BB3σ反転"], group="統合表示")\nbool bbAlertsEnabled = input.bool(false, "BB3σ反転の確定候補を通知対象にする", group="統合表示")\n\nstring gAuto =')
    # All status tables live in the script pane. Price drawings stay on the chart.
    assistant = assistant.replace('table.new(position.bottom_left, 4, 12,', 'table.new(position.top_left, 4, 13,')
    assistant = assistant.replace('table.new(position.bottom_right, 2, 6,', 'table.new(position.top_right, 2, 14,')
    assistant = shift_table_rows(assistant, 'panel', 1)
    assistant = shift_table_rows(assistant, 'candidatePanel', 1)
    # The current-symbol summary duplicates the scanner; user requested its removal.
    assistant = "\n".join(line for line in assistant.splitlines()
                          if 'table.cell(candidatePanel,' not in line)
    assistant = assistant.replace('table.new(position.top_right, 2, 14, bgcolor=color.new(color.black, 10), border_width=1)',
                                  'table.new(position.top_right, 2, 14, bgcolor=color.new(color.black, 100), border_width=0)')
    # Match scanner's legend clearance; align the first content row across columns.
    assistant = assistant.replace('f_row(int row,', '''if barstate.isfirst
    table.merge_cells(panel, 0, 0, 3, 0)
    table.cell(panel, 0, 0, "", height=8, bgcolor=color.new(color.black, 100))
f_row(int row,''')
    assistant = assistant.replace('if barstate.islast\n    table.cell(panel,', 'if barstate.islast and not combinedSimple\n    table.cell(panel,')
    assistant = assistant.replace('if candidateBuyEvent or candidateSellEvent\n    float eventPrice',
                                  'if (candidateBuyEvent or candidateSellEvent) and not combinedSimple\n    float eventPrice')
    assistant = assistant.replace('table.new(position.top_left, 4, 13, bgcolor=color.new(color.black, 15), border_width=1)',
                                  'table.new(position.top_left, 4, 13, bgcolor=color.new(color.black, 100), border_width=0)')
    assistant = assistant.replace('if barstate.islast\n    line.delete(candidateLine)', '''if barstate.isfirst
    table.merge_cells(candidatePanel, 0, 0, 1, 0)
    table.cell(candidatePanel, 0, 0, "", height=8, bgcolor=color.new(color.black, 100))
if barstate.islast
    line.delete(candidateLine)''')
    # Optional manual inputs remain editable without installation-time point picking.
    assistant = assistant.replace("confirm=true", "confirm=false")
    scanner = "\n".join(line for line in scanner.splitlines()
                        if not line.startswith(("//@version", "indicator(", "int leftBars =", "int rightBars =")))
    # Keep standalone scanner implementation intact; namespace only overlapping names.
    scanner = rename_identifiers(scanner, {"f_state", "f_previousState", "f_direction", "f_tfName", "panel"}, "scan_")
    scanner = scanner.replace('var table scan_panel = table.new(position.top_center, 6, 12, bgcolor=color.rgb(25, 29, 39), border_width=1)',
                              'var table scan_panel = combinedScanner == "YTT" and not combinedSimple ? table.new(position.top_center, 6, 12, bgcolor=color.rgb(25, 29, 39), border_width=1) : na')
    scanner = scanner.replace('if barstate.isfirst\n', 'if barstate.isfirst and combinedScanner == "YTT" and not combinedSimple\n')
    scanner = scanner.replace('if barstate.islast\n', 'if barstate.islast and combinedScanner == "YTT" and not combinedSimple\n')
    scanner = scanner.replace('height=4,', 'height=8,')
    scanner = scanner.replace('// Execute on every bar', '''array<Snapshot> simpleSnapshots = array.new<Snapshot>()
array<bool> simpleStale = array.new_bool()
// Execute on every bar''')
    scanner = scanner.replace('    bool eventNow =', '    array.push(simpleSnapshots, data)\n    array.push(simpleStale, stale)\n    bool eventNow =')
    scanner += '''

// Display only; the original confirmed snapshots and notification gates above remain unchanged.
var table simplePanel = combinedScanner == "YTT" and combinedSimple ? table.new(position.top_center, 3, 12, bgcolor=color.new(color.black, 100)) : na
if barstate.isfirst and combinedScanner == "YTT" and combinedSimple
    table.merge_cells(simplePanel, 0, 0, 2, 0)
    table.merge_cells(simplePanel, 0, 1, 2, 1)
    table.merge_cells(simplePanel, 0, 11, 2, 11)
if barstate.islast and combinedScanner == "YTT" and combinedSimple
    table.clear(simplePanel, 0, 0, 2, 11)
    table.cell(simplePanel, 0, 0, "", height=8)
    table.cell(simplePanel, 0, 1, "YTT " + f_tfName(entryTf) + "｜新規成立 → 突破待ち", text_color=color.white, text_size=size.normal)
    table.cell(simplePanel, 0, 2, "通貨", text_color=color.silver)
    table.cell(simplePanel, 1, 2, "タイミング", text_color=color.silver)
    table.cell(simplePanel, 2, 2, "突破価格 / 確定時刻", text_color=color.silver)
    int shown = 0
    int pending = 0
    // New confirmations first, then unconsumed thresholds. Never show old breakouts as entries.
    for priority = 0 to 1
        for i = 0 to 7
            Snapshot item = array.get(simpleSnapshots, i)
            bool fresh = valid and not na(item) and not array.get(simpleStale, i)
            if priority == 0 and not fresh
                pending += 1
            int s = fresh ? item.status : 0
            bool event = s == 3 or s == 4
            bool waiting = s == 1 or s == 2
            if fresh and (priority == 0 ? event : waiting)
                shown += 1
                bool buy = s == 1 or s == 3
                color ink = event ? color.yellow : buy ? color.lime : color.orange
                color bg = event ? color.rgb(65, 52, 15) : color.rgb(30, 38, 48)
                string action = event ? (buy ? "買い候補・直近確定" : "売り候補・直近確定") : (buy ? "買い：終値で超え待ち" : "売り：終値で割れ待ち")
                string price = item.priceText + (event ? " / " + str.format_time(item.closedAt, "HH:mm", "Asia/Tokyo") : "")
                table.cell(simplePanel, 0, shown + 2, str.replace_all(array.get(symbols, i), "OANDA:", ""), text_color=color.white, bgcolor=bg, text_size=size.normal)
                table.cell(simplePanel, 1, shown + 2, action, text_color=ink, bgcolor=bg, text_size=size.normal)
                table.cell(simplePanel, 2, shown + 2, price, text_color=ink, bgcolor=bg, text_size=size.normal)
    string message = not valid ? "時間足設定を確認：チャート足≦判定足＜上位2足" : shown == 0 and pending > 0 ? "データ更新待ち：" + str.tostring(pending) + "通貨（配信・休場を確認）" : shown == 0 ? "現在、新規候補・突破待ちなし（8通貨監視中）" : "待ちでは入らない｜新規成立の確定足だけ確認｜追いかけない" + (pending > 0 ? "｜更新待ち " + str.tostring(pending) : "")
    table.cell(simplePanel, 0, 11, message, text_color=valid ? color.silver : color.orange, text_size=size.small)
'''
    return (assistant.rstrip() + "\n\n// FX scanner: shared pivot settings; separate display pane.\n" + scanner.rstrip()
            + "\n\n// BB reversal: independent research-only candidates and hypothetical RR1 ledger.\n" + build_bb(bb).rstrip() + "\n")


if __name__ == "__main__":
    (ROOT / "yosuga_ytt_combined.pine").write_text(build(), encoding="utf-8", newline="\n")
