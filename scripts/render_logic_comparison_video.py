"""Render saved, AI-free USDJPY trades; no strategy changes or network calls."""
from pathlib import Path
import csv
import hashlib
import json
from datetime import datetime, timezone
import sys

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/logic_comparison_20261010'
YTT = ROOT / 'agent_runs/ytt_monthly5_fx_20261009/USDJPY_dw_m15_cost1.csv'
BB = ROOT / 'agent_runs/bb3_jev_20260925/original_rr1.0_cost1.0_trades.json'
BARS = ROOT / 'agent_runs/bb3_gmo_2023_2025/USDJPY_features.npz'
CTX = ROOT / 'agent_runs/ytt_monthly5_fx_20261009/USDJPY_entry900.npz'
W, H, FPS = 1600, 1000, 12
BG, TEXT, MUTED = '#0c1422', '#eff4fb', '#a6b4c8'
GREEN, RED, GOLD, BLUE = '#32d6ab', '#ff647c', '#ffce65', '#80aaff'
FONT = Path('C:/Windows/Fonts/meiryo.ttc')
FONTS = {n: ImageFont.truetype(str(FONT), n) for n in (16, 19, 22, 26, 34, 46)}


def stamp(t, fmt='%m/%d %H:%M'):
    return datetime.fromtimestamp(int(t), timezone.utc).strftime(fmt)


def text(draw, xy, value, size=22, color=TEXT):
    draw.text(xy, str(value), font=FONTS[size], fill=color)


def normalise(row, bb=False):
    r = dict(row)
    for k in ('entry_time', 'exit_time', 'side'):
        r[k] = int(r[k])
    for k in ('entry', 'stop', 'target', 'net_r'):
        r[k] = float(r[k])
    r['exit_price'] = float(r['exit'] if bb else r['exit_price'])
    r['reason'] = r['exit_reason'] if bb else r['reason']
    # BB stores the exit candle OPEN time, although wick-hit evidence needs its close.
    r['exit_display_time'] = r['exit_time'] + (300 if bb and r['reason'] not in ('gap_stop', 'gap_target') else 0)
    return r


def load():
    ytt = [normalise(r) for r in csv.DictReader(YTT.open())]
    bb = [normalise(r, True) for r in json.loads(BB.read_text()) if r['symbol'] == 'USDJPY']
    with np.load(BARS) as z:
        times, features = z['times'], z['features']
    with np.load(CTX) as z:
        context = {k: z[k].copy() for k in z.files}
    shared = sorted({r['entry_time']//86400 for r in ytt} & {r['entry_time']//86400 for r in bb})[:3]
    assert len(shared) == 3
    return ytt, bb, times, features, context, shared


def card(lines):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    text(d, (90, 105), lines[0], 46, GOLD)
    for n, line in enumerate(lines[1:]):
        text(d, (100, 230+n*85), line, 26)
    text(d, (100, 905), '保存済みの研究取引を再生 / Jevなし / 実取引・収益保証ではありません', 19, MUTED)
    return im


REASONS = {'sl': '損切り', 'stop': '損切り', 'tp': '利確', 'target': '利確',
           'daily_close': '日次決済', 'incomplete_bar_close': '欠損で決済',
           'data_gap_open': 'ギャップ決済', 'gap_stop': 'ギャップ損切り',
           'gap_target': 'ギャップ利確', 'timeout': '時間決済'}


def panel(im, top, name, subtitle, chapter, now, times, f, trades, context, bounds, bb=False):
    d = ImageDraw.Draw(im)
    start, end = chapter*86400, (chapter+1)*86400
    mask = (times >= start) & (times < end)
    ts, bars = times[mask], f[mask]
    left, right, y0, y1 = 70, 1210, top+100, top+340
    visible = ts+300 <= now
    chapter_trades = [r for r in trades if r['entry_time'] < end and r['exit_display_time'] >= start]
    low, high = bounds
    pad = (high-low)*.10
    low, high = low-pad, high+pad
    px = lambda t: left+(t-start)/86400*(right-left)
    py = lambda p: y1-(p-low)/(high-low)*(y1-y0)
    d.rounded_rectangle((35, top, 1565, top+415), radius=16, fill='#131f30')
    text(d, (65, top+14), name, 26, GOLD if bb else BLUE)
    text(d, (65, top+54), subtitle, 19, MUTED)
    for v in np.linspace(low, high, 5):
        y = py(v)
        d.line((left, y, right, y), fill='#29364b')
        text(d, (right-68, y-23), f'{v:.3f}', 16, MUTED)
    for hour in (0, 6, 12, 18, 24):
        x = px(start+hour*3600)
        d.line((x, y0, x, y1), fill='#29364b')
        text(d, (x-20, y1+7), f'{hour:02}:00', 16, MUTED)
    indices = np.flatnonzero(visible)
    # Fixed whole-day axes are for comparison only; no future bars are drawn.
    if bb:
        for col, color in ((4, GOLD), (5, BLUE), (6, BLUE)):
            points = [(px(ts[i]+150), py(bars[i, col])) for i in indices if np.isfinite(bars[i, col]) and low <= bars[i, col] <= high]
            if len(points) > 1:
                d.line(points, fill=color, width=2)
    for i in indices:
        op, hi, lo, cl = bars[i, :4]
        x = px(ts[i]+150)
        color = GREEN if cl >= op else RED
        d.line((x, py(hi), x, py(lo)), fill=color)
        d.rectangle((x-1.6, min(py(op), py(cl)), x+1.6, max(min(py(op), py(cl))+1, max(py(op), py(cl)))), fill=color)
    if not bb:
        j = np.searchsorted(context['times']+900, now, side='right')-1
        if j >= 0:
            for k, color in (('high', RED), ('low', GREEN)):
                p = context[k][j]
                if np.isfinite(p) and low <= p <= high:
                    d.line((left, py(p), px(now), py(p)), fill=color)
            direction = lambda v: '上昇' if v == 1 else '下降' if v == -1 else '未確定'
            text(d, (1260, top+280), f"日足 {direction(context['daily'][j])}", 19)
            text(d, (1260, top+310), f"週足 {direction(context['weekly'][j])}", 19)
    for r in chapter_trades:
        if r['entry_time'] > now:
            continue
        a, b = max(start, r['entry_time']), min(now, r['exit_display_time'], end)
        color = GREEN if r['side'] == 1 else RED
        for k, line_color in (('entry', '#e7edf7'), ('stop', RED), ('target', GREEN)):
            d.line((px(a), py(r[k]), px(b), py(r[k])), fill=line_color, width=2)
        if r['entry_time'] >= start:
            x, y = px(r['entry_time']), py(r['entry'])
            d.polygon([(x, y), (x-7, y+13*r['side']), (x+7, y+13*r['side'])], fill=color)
        if start <= r['exit_display_time'] <= now:
            x, y = px(r['exit_display_time']), py(r['exit_price'])
            d.line((x-6, y-6, x+6, y+6), fill=GOLD, width=3)
            d.line((x-6, y+6, x+6, y-6), fill=GOLD, width=3)
    entered = [r for r in chapter_trades if r['entry_time'] <= now]
    current = entered[-1] if entered else None
    if current:
        closed = current['exit_display_time'] <= now
        text(d, (1250, top+95), '買い' if current['side'] == 1 else '売り', 26, GREEN if current['side'] == 1 else RED)
        text(d, (1250, top+136), f"Entry  {current['entry']:.3f}", 19)
        text(d, (1250, top+170), f"SL      {current['stop']:.3f}", 19, RED)
        text(d, (1250, top+204), f"TP      {current['target']:.3f}", 19, GREEN)
        status = REASONS.get(current['reason'], current['reason']) if closed else '保有中'
        text(d, (1250, top+245), status, 22, GOLD)
        if closed:
            text(d, (1250, top+355), f"結果 {current['net_r']:+.2f} R", 22, GOLD)
    else:
        text(d, (1250, top+110), 'エントリー待ち', 22, MUTED)
    day_entries = sum(start <= r['entry_time'] <= now for r in chapter_trades)
    text(d, (65, top+380), f'当日のエントリー {day_entries}件   ▲買い / ▼売り   ×決済   白=Entry 赤=SL 緑=TP', 19)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ytt, bb, times, features, context, days = load()
    # Confirm the common underlying prices after aggregating 3 M5 candles to M15.
    checks = []
    for day in days:
        start = day*86400
        count = 0
        for i in np.flatnonzero((context['times'] >= start) & (context['times'] < start+86400)):
            tt = context['times'][i]
            part = features[(times >= tt) & (times < tt+900), :4]
            if len(part) == 3:
                aggregate = [part[0, 0], part[:, 1].max(), part[:, 2].min(), part[-1, 3]]
                assert np.allclose(aggregate, context['prices'][i], atol=1e-9, rtol=0)
                count += 1
        checks.append({'date': stamp(start, '%Y-%m-%d'), 'identical_m15_bars': count})
    chapters = []
    frames = 0
    with imageio.get_writer(str(OUT/'ytt_vs_bb3_usdjpy.mp4'), fps=FPS, codec='libx264', quality=8,
                            macro_block_size=1, ffmpeg_params=['-pix_fmt', 'yuv420p', '-movflags', '+faststart']) as writer:
        def append(im, repeat=1):
            nonlocal frames
            pixels = np.asarray(im)
            for _ in range(repeat):
                writer.append_data(pixels)
                frames += 1
        append(card(['YTT順張り vs BB3σ反転', '同じUSDJPYの値動きを、上下で同時に再生します。', '上：YTT / 15分足 + 確定日足・週足の方向一致', '下：BB反転 / 5分足で3σ接触 → 反転足 → 高安突破', '両方RR1。YTTは高安SL、BBは中央線TPからSLを算出。', '取引のある最初の3日。勝ち負けを理由に選んでいません。', '1画面=1日。イベントで一時停止する字幕付き動画です。']), 7*FPS)
        for n, day in enumerate(days, 1):
            start, end = day*86400, (day+1)*86400
            ts = times[(times >= start) & (times < end)]
            chapter_rows = [[r for r in arm if start <= r['entry_time'] < end] for arm in (ytt, bb)]
            bars = features[(times >= start) & (times < end)]
            levels = [r[k] for arm in (ytt, bb) for r in arm if r['entry_time'] < end and r['exit_time'] >= start for k in ('entry', 'stop', 'target')]
            bounds = (min(bars[:, 2].min(), *levels), max(bars[:, 1].max(), *levels))
            chapter = {'date': stamp(start, '%Y-%m-%d'), 'video_start_seconds': frames/FPS,
                       'ytt_trades': chapter_rows[0], 'bb_trades': chapter_rows[1]}
            event_times = {r[k] for arm in (ytt, bb) for r in arm for k in ('entry_time', 'exit_display_time') if start <= r[k] < end}
            previous = start-1
            for now in sorted(set(int(t)+300 for t in ts) | {start, end}):
                im = Image.new('RGB', (W, H), BG)
                d = ImageDraw.Draw(im)
                text(d, (45, 12), f'USDJPY  |  比較 {n}/3  |  {stamp(now, "%Y/%m/%d %H:%M")}  保存データ時刻', 26)
                panel(im, 66, 'YTT 順張り', '15分足で確定高安を終値突破 / 日足・週足の一致 / 費用1.6pips', day, now, times, features, ytt, context, bounds)
                panel(im, 502, 'BB3σ 反転', '5分足で3σ接触 → 帯内反転 → 反転足突破 / 費用1.0pip', day, now, times, features, bb, context, bounds, True)
                text(d, (45, 935), '共通チャートは5分足。1フレームは足全体を表示し、足内の約定順序は再現しません。', 19, MUTED)
                text(d, (45, 966), '時刻はJST未確認 / 軸は1日固定 / 欠損・持ち越しを保持 / 費用が異なるため収益の優劣比較ではありません', 16, MUTED)
                is_event = any(previous < t <= now for t in event_times)
                append(im, 20 if is_event else 1)
                if n == 1 and chapter_rows[1][0]['entry_time']+300 == now:
                    im.save(OUT/'preview.png')
                previous = now
            append(im, 3*FPS)
            chapter['video_end_seconds'] = frames/FPS
            chapters.append(chapter)
            print(json.dumps({'chapter': n, 'date': chapter['date'], 'frames': frames}), flush=True)
        append(card(['見方の違い', 'YTT：上位足と同じ方向へ、高安突破についていく。', 'BB反転：3σの外側から、中央線への戻りを狙う。', 'Entry・SL・TP・決済の位置と保有時間を見比べてください。', 'この3日だけで勝率・期待値・月利は判断できません。', '保存された研究ロジックの再生です。TradingViewの画面録画ではありません。', '両方式とも実運用への採用を確認したものではありません。']), 7*FPS)
    manifest = {'symbol': 'USDJPY', 'fps': FPS, 'frames': frames, 'duration_seconds': frames/FPS,
                'selection': 'Earliest three source-calendar dates with an entry by both; outcomes not used',
                'price_checks': checks, 'chapters': chapters,
                'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (YTT, BB, BARS, CTX)},
                'no_api': True, 'cash_account': False, 'timezone_verified': False}
    manifest['exit_display_rule'] = 'BB non-gap exits appear only at M5 close (stored open+300); YTT already uses close/open as appropriate.'
    (OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(OUT/'ytt_vs_bb3_usdjpy.mp4'), 'seconds': frames/FPS}), flush=True)


if __name__ == '__main__':
    main()
