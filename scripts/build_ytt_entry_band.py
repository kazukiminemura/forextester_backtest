"""Add a display-only entry reference band to the existing confirmed scanner."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/tradingview/yosuga_ytt_compact.pine'
TARGET = ROOT / 'scripts/tradingview/yosuga_ytt_entry_band.pine'

INPUTS = '''
string bandGroup = "エントリー参考帯（売買条件は変更しない）"
bool showEntryBand = input.bool(true, "現在の銘柄に参考帯を表示", group=bandGroup)
float bandAtrWidth = input.float(0.2, "帯の幅：判定足の確定ATR14倍率", minval=0.01, maxval=1, step=0.01, group=bandGroup, tooltip="突破価格から順方向への参考幅。初期値0.2は表示の仮設定で、検証済みの許容滑り・有利な約定範囲ではありません。")
int bandMinutes = input.int(5, "成立後の表示期限（分）", minval=1, maxval=60, group=bandGroup, tooltip="判定足の1本分を上限とします。期限内でも約定や利益は保証されません。")
'''

BAND = '''
// Display-only: use the CURRENT CHART SYMBOL's confirmed scanner result, not its chart-foot pivots.
// 0=waiting, 1=reference window, 2=expired, 3=outside/re-crossed, 4=no eligible result.
f_bandStatus(int state, int stamp, int openedAt, int nowMs, int durationMs, float lower, float upper, float nextOpen, float price) =>
    bool event = state == 3 or state == 4
    bool inRange = nextOpen >= lower and nextOpen <= upper and price >= lower and price <= upper and (state == 3 ? price > lower : price < upper)
    state == 1 or state == 2 ? 0 : not event or na(stamp) or na(openedAt) or openedAt != stamp or nowMs < stamp ? 4 : nowMs >= stamp + durationMs ? 2 : inRange ? 1 : 3

var box entryBand = na
var label entryBandCaption = na
if barstate.islast
    box.delete(entryBand)
    label.delete(entryBandCaption)
    if showEntryBand
        int chartSymbolIndex = array.indexof(symbols, syminfo.tickerid)
        Snapshot bandData = chartSymbolIndex >= 0 ? array.get(simpleSnapshots, chartSymbolIndex) : na
        bool bandReady = valid and not na(bandData) and not array.get(simpleStale, chartSymbolIndex) and not na(bandData.threshold) and not na(bandData.confirmedAtr)
        int bandState = bandReady ? bandData.status : 0
        bool bandBuy = bandState == 1 or bandState == 3
        float bandBase = bandReady ? bandData.threshold : close
        float bandWidth = bandReady ? math.max(syminfo.mintick, bandData.confirmedAtr * bandAtrWidth) : 0
        float bandLower = bandBuy ? bandBase : bandBase - bandWidth
        float bandUpper = bandBuy ? bandBase + bandWidth : bandBase
        int bandDuration = int(math.min(entrySeconds * 1000, bandMinutes * 60000))
        int bandNow = timenow  // Live-only window; replay/history must not pretend an old candidate is live.
        int displayState = bandReady ? f_bandStatus(bandState, bandData.closedAt, bandData.openedAt, bandNow, bandDuration, bandLower, bandUpper, bandData.nextOpen, close) : 4
        color bandInk = displayState == 0 ? color.orange : displayState == 1 ? (bandBuy ? color.green : color.red) : color.gray
        string bandAction = displayState == 0 ? "準備帯・終値突破待ち" : displayState == 1 ? "成立直後の参考帯" : displayState == 2 ? "時間切れ・追わない" : displayState == 3 ? "範囲外・追わない" : "見送り・参考帯なし"
        string bandDetail = not valid ? "判定足・上位足の設定を確認" : chartSymbolIndex < 0 ? "この銘柄は監視範囲外（A/B設定を確認）" : not bandReady ? "データ更新待ち／配信・休場を確認" : bandState == 5 or bandState == 6 ? "突破済・次の新規成立を待つ" : "上位足一致と新規成立を待つ"
        int bandRight = time_close
        if displayState != 4
            // Directional range includes the threshold as a boundary, not a trigger.
            entryBand := box.new(left=bandData.closedAt, top=bandUpper, right=bandRight, bottom=bandLower, xloc=xloc.bar_time,
                 border_color=bandInk, border_style=displayState == 0 ? line.style_dashed : line.style_solid, bgcolor=color.new(bandInk, 85), force_overlay=true)
            bandDetail := (bandBuy ? "買い " : "売り ") + f_price(bandLower) + " ～ " + f_price(bandUpper)
        string bandTooltip = "判定足 " + scan_f_tfName(entryTf) + "。参考帯は売買条件・SL・TPではありません。幅と期限は未検証の表示設定です。成立後も終値突破の基準と次足始値が帯内か確認します。過去の候補を現在の成立として表示しません。"
        entryBandCaption := label.new(bandRight, displayState == 4 ? close : (bandUpper + bandLower) / 2, scan_f_tfName(entryTf) + "｜" + bandAction + "\\n" + bandDetail,
             xloc=xloc.bar_time, style=label.style_label_right, color=bandInk, textcolor=color.white, size=size.normal, tooltip=bandTooltip, force_overlay=true)

'''


def build(source):
    source = source.replace('YTT 18銘柄統合（高安・チャネル・BB）', 'YTT 統合＋エントリー参考帯', 1)
    source = source.replace('max_labels_count=500,', 'max_labels_count=500, max_boxes_count=10,', 1)
    source = source.replace('string gRules =', INPUTS + '\nstring gRules =', 1)
    source = source.replace('    int closedAt\n', '    int closedAt\n    float threshold\n    float confirmedAtr\n    float nextOpen\n    int openedAt\n', 1)
    old = 'Snapshot.new(status[1], priceText[1], d1[1], d2[1], time_close[1])'
    assert source.count(old) == 1
    # No developing H/L/close/ATR: only the new judgment bar's open/time are unshifted.
    source = source.replace(old, old[:-1] + ', displayedPrice[1], ta.atr(14)[1], open, time)')
    source = source.replace('// ALL fields are offset. No developing entry bar or HTF value can escape.',
                            '// Signal/ATR/HTF fields are offset. Only the new bar open/time are unshifted and time-guarded.')
    return source.replace('// BB reversal: independent research-only', BAND + '// BB reversal: independent research-only', 1)


if __name__ == '__main__':
    TARGET.write_text(build(SOURCE.read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
    print(TARGET)
