"""Two nine-symbol monitors, preserving the existing confirmed YTT snapshots."""
from pathlib import Path
import re
from build_ytt_combined_pine import build

ROOT = Path(__file__).resolve().parent / "tradingview"
GROUPS = {
    "a": ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "EURJPY", "GBPJPY", "NZDJPY", "CADJPY", "AUDJPY"),
    "b": ("USDCHF", "USDCAD", "NZDUSD", "EURAUD", "EURCHF", "GBPCHF", "AUDNZD", "EURGBP", "AUDUSD"),
}


def watchlist_source(group: str) -> str:
    assistant, remainder = build().split('// FX scanner: shared pivot settings; separate display pane.\n', 1)
    source, bb = remainder.split('// BB reversal: independent research-only', 1)
    inputs = '\n'.join(f'string symbol{i} = input.symbol("OANDA:{symbol}", "銘柄{i}", group=gSymbols)'
                       for i, symbol in enumerate(GROUPS[group], 1))
    source = re.sub(r'string symbol1 = input.symbol[^\n]+(?:\nstring symbol\d+ = input.symbol[^\n]+)*', inputs, source)
    source = source.replace('symbol7, symbol8)', 'symbol7, symbol8, symbol9)')
    source = source.replace('array.new_int(8,', 'array.new_int(9,')
    source = source.replace('for i = 0 to 7', 'for i = 0 to 8')
    source = source.replace('table.new(position.top_center, 3, 12,', 'table.new(position.top_center, 3, 13,')
    source = source.replace('simplePanel, 0, 11', 'simplePanel, 0, 12')
    source = source.replace('simplePanel, 0, 12, 2, 11', 'simplePanel, 0, 12, 2, 12')
    source = source.replace('simplePanel, 0, 0, 2, 11', 'simplePanel, 0, 0, 2, 12')
    source = source.replace('top_center, 6, 12,', 'top_center, 6, 13,')
    source = source.replace('scan_panel, 0, 11, 5, 11', 'scan_panel, 0, 12, 5, 12')
    source = source.replace('scan_panel, 0, 11, note', 'scan_panel, 0, 12, note')
    source = source.replace('YTT " + f_tfName(entryTf)', f'YTT {group.upper()}・9銘柄 " + f_tfName(entryTf)')
    source = source.replace('8通貨監視中', '9銘柄監視中')
    source = source.replace('新規候補・突破待ちなし', '新規候補・突破待ちなし')
    # Standalone scanner uses its own timeframe-caption function, not the chart assistant's.
    source = re.sub(r'(?<!scan_)\bf_tfName\(', 'scan_f_tfName(', source)
    if group == 'a':
        assistant = assistant.replace('よすが式 YTT統合版＋BB3σ反転（分析補助・研究用）', 'YTT 18銘柄監視 A（価格描画＋9銘柄）')
        assistant = assistant.replace('string combinedScanner = input.string("YTT", "通貨一覧", options=["YTT", "BB3σ反転"], group="統合表示")',
                                      'string combinedScanner = "YTT"')
        return assistant + source + '// BB reversal: independent research-only' + bb
    prefix = f'''//@version=6
indicator("YTT 18銘柄監視 {group.upper()}（9銘柄・分析候補）", overlay=false, dynamic_requests=true)
bool combinedSimple = true
string combinedScanner = "YTT"
int leftBars = input.int(2, "左側ピボット本数", minval=1, maxval=20)
int rightBars = input.int(2, "右側確定本数", minval=1, maxval=20)
'''
    return prefix + source.rstrip() + '\n'


def unified_source() -> str:
    """All 18 unchanged nested contexts need 54 requests; chart visuals add <=9."""
    assistant, remainder = watchlist_source('a').split('string gRules =', 1)
    scanner, bb = ('string gRules =' + remainder).split('// BB reversal: independent research-only', 1)
    assistant = assistant.replace('YTT 18銘柄監視 A（価格描画＋9銘柄）', 'YTT 18銘柄統合（高安・チャネル・BB）')
    assistant = assistant.replace('string combinedScanner = "YTT"', '''string combinedScanner = "YTT"
string watchScope = input.string("A：前半9銘柄", "監視範囲", options=["全18銘柄", "A：前半9銘柄", "B：後半9銘柄"], group="統合表示")
bool supports64 = input.bool(false, "64件の取得に対応するプランを利用中", group="統合表示", tooltip="全18銘柄には54件＋価格描画最大9件が必要です。Basicなど40件上限のプランではONにしないでください。")
bool watchBudgetValid = watchScope != "全18銘柄" or supports64''')
    additional = '\n'.join(f'string symbol{i} = input.symbol("OANDA:{symbol}", "銘柄{i}", group=gSymbols)'
                           for i, symbol in enumerate(GROUPS['b'], 10))
    scanner = scanner.replace('// One object per currency', additional + '\n\n// One object per currency')
    scanner = scanner.replace('array<string> symbols = array.from(symbol1, symbol2, symbol3, symbol4, symbol5, symbol6, symbol7, symbol8, symbol9)', '''array<string> symbols = watchScope == "全18銘柄" ? array.from(symbol1, symbol2, symbol3, symbol4, symbol5, symbol6, symbol7, symbol8, symbol9, symbol10, symbol11, symbol12, symbol13, symbol14, symbol15, symbol16, symbol17, symbol18) : watchScope == "A：前半9銘柄" ? array.from(symbol1, symbol2, symbol3, symbol4, symbol5, symbol6, symbol7, symbol8, symbol9) : array.from(symbol10, symbol11, symbol12, symbol13, symbol14, symbol15, symbol16, symbol17, symbol18)''')
    scanner = scanner.replace('bool valid = chart.is_standard', 'bool valid = watchBudgetValid and chart.is_standard')
    scanner = scanner.replace('array.new_int(9,', 'array.new_int(18,')
    scanner = scanner.replace('for i = 0 to 8', 'for i = 0 to array.size(symbols) - 1')
    scanner = scanner.replace('top_center, 3, 13,', 'top_center, 3, 22,')
    scanner = scanner.replace('top_center, 6, 13,', 'top_center, 6, 22,')
    scanner = scanner.replace('simplePanel, 0, 12, 2, 12', 'simplePanel, 0, 21, 2, 21')
    scanner = scanner.replace('simplePanel, 0, 0, 2, 12', 'simplePanel, 0, 0, 2, 21')
    scanner = scanner.replace('simplePanel, 0, 12, message', 'simplePanel, 0, 21, message')
    scanner = scanner.replace('scan_panel, 0, 12, 5, 12', 'scan_panel, 0, 21, 5, 21')
    scanner = scanner.replace('scan_panel, 0, 12, note', 'scan_panel, 0, 21, note')
    scanner = scanner.replace('YTT A・9銘柄 " +', 'YTT " + str.tostring(array.size(symbols)) + "/18銘柄 " +')
    scanner = scanner.replace('9銘柄監視中', '選択銘柄監視中')
    warning = '"全18の同時監視には64件対応プランが必要｜現在は監視停止"'
    scanner = scanner.replace('string message = not valid ?', f'string message = not watchBudgetValid ? {warning} : not valid ?')
    scanner = scanner.replace('string note = valid ?', f'string note = not watchBudgetValid ? {warning} : valid ?')
    # Entry references remain visible independently of the compact scanner table.
    assistant = assistant.replace('string combinedScanner = "YTT"', 'bool showYttEntryHistory = input.bool(true, "YTTの過去Entryを残す（成立の次足始値・参考）", group="統合表示", tooltip="現在のチャート足で上位足合意・終値突破が確定した次足の始値を記録します。実注文・約定履歴ではありません。休場や欠損で次足が連続しない場合は表示しません。")\nint keepYttEntries = input.int(50, "YTT Entryの保持件数", minval=10, maxval=100, group="統合表示")\n' + 'string combinedScanner = "YTT"', 1)
    assistant = assistant.replace('float candidatePrice =', '// Previous bar is confirmed; the next contiguous bar\'s open is fixed from its first update.\n// Independent of the compact scanner UI, and never substitutes threshold for entry price.\nvar array<label> yttEntryHistory = array.new<label>()\nbool yttHistoryBuy = candidateBuyEvent[1]\nbool yttHistorySell = candidateSellEvent[1]\nbool yttHistoryContiguous = not na(time_close[1]) and time == time_close[1]\nif showYttEntryHistory and yttHistoryContiguous and (yttHistoryBuy or yttHistorySell)\n    float historyThreshold = yttHistoryBuy ? candidatePriorHigh[1] : candidatePriorLow[1]\n    string historyCaption = (yttHistoryBuy ? "YTT 買い Entry（参考）\\n" : "YTT 売り Entry（参考）\\n") + f_price(open)\n    array.push(yttEntryHistory, label.new(time, open, historyCaption, xloc=xloc.bar_time,\n         style=yttHistoryBuy ? label.style_label_up : label.style_label_down,\n         color=yttHistoryBuy ? color.green : color.red, textcolor=color.white, size=size.small,\n         tooltip="成立の次足始値。突破基準 " + f_price(historyThreshold) + "\\n実注文・約定履歴ではありません。", force_overlay=true))\n    if array.size(yttEntryHistory) > keepYttEntries\n        label.delete(array.shift(yttEntryHistory))\n\n' + 'float candidatePrice =', 1)
    return assistant + scanner + '// BB reversal: independent research-only' + bb


if __name__ == '__main__':
    for group in GROUPS:
        (ROOT / f'yosuga_ytt_watchlist_{group}.pine').write_text(watchlist_source(group), encoding='utf-8', newline='\n')
    (ROOT / 'yosuga_ytt_watchlist_unified.pine').write_text(unified_source(), encoding='utf-8', newline='\n')
