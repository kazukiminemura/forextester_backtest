"""Snapshot public Japanese daily stock history for the fixed research universe."""
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'agent_runs/tamukai_stocks_daily_20260926/data'
SYMBOLS = ['7203.T', '6758.T', '8306.T', '9432.T', '9984.T',
           '6501.T', '6861.T', '8035.T', '8058.T', '4502.T']


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'price_basis': 'Yahoo back-adjusted OHLC; no adjclose rescaling; Sony spin-off adjustment unresolved',
                'raw_period': ['2014-01-01', '2026-01-01 exclusive'],
                'csv_period': ['2016-07-12', '2026-01-01 exclusive'],
                'evaluation_period': ['2017-01-01', '2026-01-01 exclusive'],
                'quality_policy': 'Zero-volume rows excluded; early missing sessions avoided; two known high/low errors enclosed to open/close with secondary-source support',
                'symbols': {}}
    # Capture all source responses before quality checks; preserve failed inputs too.
    for symbol in SYMBOLS:
        url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
               '?period1=1388534400&period2=1767225600&interval=1d&events=div%2Csplits')
        raw_path = DEST / f'{symbol}.json'
        if raw_path.exists():
            raw = raw_path.read_bytes()
        else:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60) as response:
                raw = response.read()
            raw_path.write_bytes(raw)
    for symbol in SYMBOLS:
        url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
               '?period1=1388534400&period2=1767225600&interval=1d&events=div%2Csplits')
        raw = (DEST / f'{symbol}.json').read_bytes()
        payload = json.loads(raw)
        if payload['chart']['error']:
            raise ValueError(payload['chart']['error'])
        result = payload['chart']['result'][0]
        if result['meta']['currency'] != 'JPY':
            raise ValueError(f'{symbol}: non-JPY')
        quotes = result['indicators']['quote'][0]
        rows, previous_date, excluded, repairs = [], '', [], []
        for i, timestamp in enumerate(result['timestamp']):
            date = datetime.fromtimestamp(timestamp, timezone(timedelta(hours=9))).date().isoformat()
            prices = [quotes[k][i] for k in ('open', 'high', 'low', 'close')]
            if quotes['volume'][i] == 0 or date < '2016-07-12':
                excluded.append({'date': date, 'reason': 'zero_volume' if quotes['volume'][i] == 0 else 'before_warmup'})
                continue
            if not all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0 for x in prices):
                raise ValueError(f'{symbol} {date}: invalid OHLC')
            op, hi, lo, cl = prices
            if (symbol, date) in {('8306.T', '2022-05-17'), ('8035.T', '2022-05-17')}:
                fixed = [op, max(hi, op, cl), min(lo, op, cl), cl]
                repairs.append({'date': date, 'original_ohlc': prices, 'derived_ohlc': fixed,
                                'policy': 'high/low envelope extension, secondary-source supported, original JSON untouched',
                                'source': f'https://minkabu.jp/stock/{symbol[:4]}/daily_bar?page=54'})
                prices = fixed
                op, hi, lo, cl = prices
            if not lo <= min(op, cl) <= max(op, cl) <= hi or date <= previous_date:
                raise ValueError(f'{symbol} {date}: invalid OHLC order or duplicate date')
            if not '2014-01-01' <= date < '2026-01-01':
                raise ValueError(f'{symbol} {date}: outside requested interval')
            rows.append([date, *prices, quotes['volume'][i]])
            previous_date = date
        if len(rows) < 2200:
            raise ValueError(f'{symbol}: insufficient history {len(rows)}')
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['date', 'open', 'high', 'low', 'close', 'volume'])
        writer.writerows(rows)
        csv_bytes = stream.getvalue().encode('utf-8')
        (DEST / f'{symbol}.csv').write_bytes(csv_bytes)
        manifest['symbols'][symbol] = {
            'url': url, 'rows': len(rows), 'first': rows[0][0], 'last': rows[-1][0],
            'raw_sha256': hashlib.sha256(raw).hexdigest(),
            'csv_sha256': hashlib.sha256(csv_bytes).hexdigest(),
            'events': result.get('events', {}),
            'excluded_rows': excluded, 'repairs': repairs,
            'exchange_timezone': result['meta'].get('exchangeTimezoneName'),
        }
        print(f'{symbol}: {len(rows)} rows {rows[0][0]}..{rows[-1][0]}', flush=True)
    calendars = []
    for symbol in SYMBOLS:
        with (DEST / f'{symbol}.csv').open(newline='') as source:
            calendars.append({row['date'] for row in csv.DictReader(source)})
    if any(dates != calendars[0] for dates in calendars[1:]):
        raise ValueError('Symbol trading calendars differ; investigate before backtest')
    manifest['common_calendar_rows'] = len(calendars[0])
    (DEST / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('DATA_READY', flush=True)


if __name__ == '__main__':
    main()
