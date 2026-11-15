"""Refresh the Nikkei 225 VCP candidate report from Yahoo Finance daily bars."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html import escape
import json
from math import isfinite
import re
from urllib.parse import quote

from fetch_nikkei225_stock_data import CHART_URL, TOKYO, download
from research_jlaw_vcp import Bar, ROOT, signals


ROSTER = ROOT / 'data/stocks/yahoo/nikkei225_current_20261115/constituents_codes.txt'
OUTPUT = ROOT / 'artifacts/nikkei225_vcp_latest.html'
ROSTER_DATE = '2026-11-13'


def chart(symbol, start, end):
    base = CHART_URL.split('?')[0].format(symbol=quote(symbol, safe=''))
    params = f'period1={int(start.timestamp())}&period2={int(end.timestamp())}&interval=1d'
    result = json.loads(download(f'{base}?{params}'))['chart']['result'][0]
    meta = result['meta']
    if meta['symbol'] != symbol or meta['currency'] != 'JPY' or meta['exchangeTimezoneName'] != 'Asia/Tokyo':
        raise ValueError('銘柄・通貨・時刻の識別情報が不一致')
    return result


def sessions(result, cutoff):
    dates = [datetime.fromtimestamp(stamp, TOKYO).date() for stamp in result['timestamp']]
    if dates != sorted(set(dates)):
        raise ValueError('日付の重複または順序異常')
    return {day: i for i, day in enumerate(dates) if day <= cutoff}


def evaluate(code, result, expected):
    dates = sessions(result, expected[-1])
    prices = result['indicators']['quote'][0]
    meta = result['meta']
    name = meta.get('longName') or meta.get('shortName') or code
    bars = []
    # Stop at the nearest unusable session so the clean suffix gives the waiting time.
    for day in reversed(expected):
        issue = ''
        i = dates.get(day)
        if i is None:
            return {'code': code, 'listing_name': name, 'status': f'日足未取得（{day}）',
                    'clean_bars': len(bars)}
        op, hi, lo, close, volume = (prices[key][i] for key in ('open', 'high', 'low', 'close', 'volume'))
        values = (op, hi, lo, close, volume)
        if volume == 0:
            issue = '出来高ゼロ'
        elif (not all(isinstance(value, (int, float)) and isfinite(value) and value > 0 for value in values)
                or not lo <= min(op, close) <= max(op, close) <= hi):
            issue = '日足の価格・出来高が不正'
        if issue:
            return {'code': code, 'listing_name': name, 'status': f'{issue}（{day}）',
                    'clean_bars': len(bars)}
        bars.append(Bar(datetime.combine(day, datetime.min.time()), *values))
    bars.reverse()
    row = {'code': code, 'name': name, 'status': '候補なし'}
    signal = signals(bars)[-1]
    if signal and signal.qualifies('vcp_relaxed'):
        close = bars[-1].close
        row.update(status='厳格' if signal.qualifies('vcp_strict') else '緩和', close=close,
                   pivot=signal.pivot, stop=signal.stop, max_open=signal.stop / 0.92,
                   risk_pct=(close - signal.stop) / close * 100,
                   volume_multiple=bars[-1].volume / (sum(bar.volume for bar in bars[-51:-1]) / 50))
    return row


def scan(now, expected_session, codes=None, *, workers=4, progress=False):
    if codes is None:
        codes = ROSTER.read_text(encoding='utf-8').split()
        if len(codes) != 225:
            raise ValueError('構成銘柄リストが225件ではありません')
    if len(set(codes)) != len(codes) or any(not re.fullmatch(r'\d[0-9A-Z]\d[0-9A-Z]', c) for c in codes):
        raise ValueError('銘柄コードが重複または不正です')
    start = now - timedelta(days=440)
    cutoff = now.date() if now.hour >= 16 else now.date() - timedelta(days=1)
    reference = chart('^N225', start, now)
    expected = list(sessions(reference, cutoff))[-252:]
    if len(expected) != 252 or (expected_session and expected[-1].isoformat() != expected_session):
        raise ValueError(f'日経平均の参照日足が不足、または指定の確定日と不一致（最終日 {expected[-1:]}）')
    if (now.date() - expected[-1]).days > 7:
        raise ValueError(f'参照日足が古すぎます（{expected[-1]}）')

    def check(code):
        try:
            return evaluate(code, chart(f'{code}.T', start, now), expected)
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            return {'code': code, 'status': f'取得・判定エラー（{error}）'}

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(check, codes):
            rows.append(row)
            if progress and len(rows) % 250 == 0:
                print(f'{len(rows)}/{len(codes)} checked', flush=True)
    return expected[-1], rows


def report(session, now, rows, *, title='日経225 VCP買い候補',
           scope=f'構成は日経公式の{ROSTER_DATE}時点。', command='python -B scripts/scan_nikkei225_vcp.py',
           readiness_days=0):
    candidates = sorted((row for row in rows if 'pivot' in row), key=lambda row: (row['status'] != '厳格', row['code']))
    errors = [row for row in rows if 'name' not in row]
    eligible = len(rows) - len(errors)
    if not eligible:
        raise ValueError('判定できた銘柄がありません。既存の一覧は保持します。')
    strict = sum(row['status'] == '厳格' for row in candidates)

    def chart_link(code):
        return f'<a href="https://www.tradingview.com/chart/?symbol=TSE%3A{code}&amp;interval=D">{code}</a>'

    readiness = ''
    if readiness_days:
        soon = sorted((r for r in errors if 1 <= 252 - r.get('clean_bars', 0) <= readiness_days),
                      key=lambda r: (-r['clean_bars'], r['code']))
        waiting_rows = ''.join(
            f'<tr><td>{chart_link(r["code"])}　{escape(r["listing_name"])}</td>'
            f'<td><strong>あと {252 - r["clean_bars"]}営業日</strong></td><td>{r["clean_bars"]} / 252本</td>'
            f'<td>{escape(r["status"])}</td></tr>' for r in soon
        )
        waiting_table = ('<div class="scroll"><table><thead><tr><th>銘柄</th><th>判定までの目安</th>'
                         '<th>連続した有効日足</th><th>最も新しい不足理由</th></tr></thead>'
                         f'<tbody>{waiting_rows}</tbody></table></div>') if soon else '<p>該当銘柄はありません。</p>'
        readiness = (f'<section class="card" aria-labelledby="readiness"><h2 id="readiness">もうすぐ判定できる銘柄 {len(soon)}件</h2>'
                     f'<p class="meta">あと{readiness_days}営業日以内。有効な日足が途切れず、過去データの補完がない場合の目安です。'
                     f'252本がそろった時点で買い条件を判定します。</p>{waiting_table}</section>')

    results = ''.join(
        f'<tr><td>{chart_link(r["code"])}　{escape(r["name"])}<br><small>{escape(r.get("market", ""))}</small></td><td>{r["status"]}</td>'
        f'<td>{r["close"]:,.2f}</td><td>&gt; {r["pivot"]:,.2f}<br>≤ {r["max_open"]:,.4f}</td>'
        f'<td>{r["stop"]:,.2f} <small>({r["risk_pct"]:.2f}%)</small></td><td>{r["volume_multiple"]:.2f}倍</td></tr>'
        for r in candidates
    )
    table = ('<div class="scroll"><table><thead><tr><th>銘柄</th><th>VCP</th><th>終値</th>'
             '<th>翌日始値の条件</th><th>損切り（対終値）</th><th>出来高</th></tr></thead>'
             f'<tbody>{results}</tbody></table></div>') if candidates else (
                 '<p class="empty">判定済み銘柄に買い候補はありません。</p>')
    unavailable = ''.join(f'<li>{chart_link(r["code"])}　{escape(r["status"])}</li>' for r in errors)
    all_rows = ''.join(f'<li>{chart_link(r["code"])}　{escape(r.get("name", ""))}　{escape(r["status"])}</li>' for r in rows)
    return f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{color-scheme:dark;font:16px/1.6 system-ui,sans-serif;background:#101820;color:#e7edf4}}body{{max-width:68rem;margin:auto;padding:clamp(1rem,4vw,3rem)}}
h1,h2,p{{margin:0 0 .7rem}}h1{{font-size:clamp(1.7rem,5vw,2.5rem)}}.meta,small{{color:#adbfcf}}.card,details{{background:#192631;border:1px solid #344655;border-radius:12px;padding:1rem;margin:1rem 0}}
a{{color:#8ee5cd}}a:focus-visible,summary:focus-visible{{outline:2px solid #8ee5cd;outline-offset:3px}}summary{{cursor:pointer;padding:.4rem 0}}.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:42rem;text-align:left}}th,td{{padding:.65rem;border-bottom:1px solid #344655}}th{{color:#adbfcf}}td{{font-variant-numeric:tabular-nums}}.empty{{padding:.75rem 0}}code{{overflow-wrap:anywhere}}
</style><main><h1>{escape(title)}</h1><p class="meta">確定日足 <strong>{session}</strong>　取得 {now:%Y-%m-%d %H:%M} JST</p>
<section class="card"><h2>買い候補 {len(candidates)}件</h2><p>厳格 {strict}件・緩和のみ {len(candidates)-strict}件　｜　{len(rows):,}銘柄中 {eligible:,}件判定・{len(errors):,}件未判定</p>{table}
<p class="meta">終値時点のテクニカル候補。翌営業日の始値がブレイク水準より高く、損切り幅が8%以内の場合に買い。価格は円、上限は丸め表示。利確は実際の始値から損切り幅の3倍。</p></section>
{readiness}
{f'<details><summary>未判定の銘柄（{len(errors)}件）</summary><ul>{unavailable}</ul></details>' if errors else ''}
<details><summary>全{len(rows):,}銘柄の判定を表示</summary><ul>{all_rows}</ul></details>
<p class="meta">Yahoo Financeの日足。{escape(scope)} 東証の当日分は16:00 JST以降に判定。</p>
<p class="meta">更新コマンド <code>{escape(command)}</code></p></main></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-session', help='Fail unless this is the latest confirmed session (YYYY-MM-DD)')
    args = parser.parse_args()
    now = datetime.now(TOKYO)
    session, rows = scan(now, args.expected_session)
    html = report(session, now, rows)
    temporary = OUTPUT.with_suffix('.tmp')
    temporary.write_text(html, encoding='utf-8')
    temporary.replace(OUTPUT)
    candidates = [row for row in rows if 'pivot' in row]
    unavailable = [row for row in rows if 'name' not in row]
    print(json.dumps({'session': str(session), 'candidates': candidates, 'unavailable': unavailable,
                      'report': str(OUTPUT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
