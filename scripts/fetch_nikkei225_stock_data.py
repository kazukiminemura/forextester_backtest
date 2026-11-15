"""Capture a fixed current Nikkei 225 cohort and its Yahoo daily history."""

import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import math
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DIRECTORY = Path('data/stocks/yahoo/nikkei225_current_20261115')
CACHE = Path('data/stocks/yahoo/jp_largecap10_20261115')
ROSTER_URL = 'https://indexes.nikkei.co.jp/en/nkave/index/component?idx=nk225'
CHART_URL = ('https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
             '?period1=1388534400&period2=1767225600&interval=1d&events=div%2Csplits')
FIELDS = ('open', 'high', 'low', 'close', 'volume')
TOKYO = timezone(timedelta(hours=9))


class ComponentCodes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.codes = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            code = ''.join(self.cell).strip()
            if re.fullmatch(r'\d[0-9A-Z]\d[0-9A-Z]', code):
                self.codes.append(f'{code}.T')
            self.cell = None


def write_bytes(path, data):
    temp = path.with_suffix(path.suffix + '.part')
    temp.write_bytes(data)
    temp.replace(path)


def download(url):
    for attempt, delay in enumerate((1, 4, 0)):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
                return response.read()
        except HTTPError as error:
            if attempt == 2 or error.code not in {429, 500, 502, 503, 504}:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(delay)


def roster(*, fetch=False):
    roster_path = DIRECTORY / 'constituents.html'
    extract_path = DIRECTORY / 'constituents_codes.txt'
    if extract_path.exists():
        roster_path = extract_path
        codes = [f'{code}.T' for code in roster_path.read_text(encoding='utf-8-sig').split()]
    else:
        if fetch and not roster_path.exists():
            write_bytes(roster_path, download(ROSTER_URL))
        html = roster_path.read_text(encoding='utf-8')
        parser = ComponentCodes()
        parser.feed(html)
        codes = parser.codes
        if not re.search(r'Nov\s*/\s*13\s*/\s*2026', html):
            raise ValueError('Official roster has an unexpected update date')
    if len(codes) != 225 or len(set(codes)) != 225 or any(not re.fullmatch(r'\d[0-9A-Z]\d[0-9A-Z]\.T', code) for code in codes):
        raise ValueError(f'Expected 225 distinct constituent codes, parsed {len(codes)}')
    return sorted(codes), roster_path


def capture_symbol(symbol, cache):
    path = DIRECTORY / f'{symbol}.json'
    if path.is_file():
        return None
    if symbol in cache:
        write_bytes(path, (CACHE / path.name).read_bytes())
        return None
    try:
        raw = download(CHART_URL.format(symbol=symbol))
    except HTTPError as error:
        if error.code not in {404, 422}:
            raise
        write_bytes(DIRECTORY / f'{symbol}.error.json', error.read())
        return {'http_status': error.code, 'reason': 'Yahoo chart unavailable'}
    write_bytes(path, raw)
    return None


def capture():
    from stock_data_cache import verify

    DIRECTORY.mkdir(parents=True, exist_ok=True)
    if (DIRECTORY / 'manifest.json').exists():
        raise FileExistsError('Completed Nikkei snapshot already exists')
    symbols, roster_path = roster(fetch=True)
    verify(CACHE)
    cached = json.loads((CACHE / 'manifest.json').read_bytes())
    cached = sorted(set(symbols) & set(cached['symbols']))
    omissions = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for offset in range(0, len(symbols), 4):
            group = symbols[offset:offset + 4]
            results = executor.map(capture_symbol, group, [cached] * len(group))
            for symbol, omitted in zip(group, results):
                if omitted is not None:
                    omissions[symbol] = omitted
            if offset % 20 == 0 or offset + len(group) == len(symbols):
                print(f'{offset + len(group)}/{len(symbols)} charts checked; {len(omissions)} unavailable', flush=True)
    receipt = {'retrieved_at': datetime.now(timezone.utc).isoformat(), 'requested': symbols,
               'constituents_file': roster_path.name, 'constituents_sha256': digest(roster_path.read_bytes()),
               'reused_previous_snapshot': cached, 'omissions': omissions}
    write_bytes(DIRECTORY / 'capture.json', json.dumps(receipt, indent=2).encode('utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def iso_date(timestamp):
    return datetime.fromtimestamp(timestamp, TOKYO).date().isoformat()


def convert(symbol, raw, calendar, calendar_set):
    chart = json.loads(raw)['chart']
    if chart['error'] or not chart['result']:
        raise ValueError(f'Yahoo chart error {chart["error"]}')
    result = chart['result'][0]
    meta = result['meta']
    if (meta['symbol'], meta['currency'], meta['exchangeTimezoneName']) != (symbol, 'JPY', 'Asia/Tokyo'):
        raise ValueError('Unexpected chart symbol, currency or exchange timezone')
    dates = [iso_date(timestamp) for timestamp in result['timestamp']]
    if dates != sorted(set(dates)):
        raise ValueError('Duplicate or out-of-order exchange dates')
    quotes = result['indicators']['quote'][0]
    rows = []
    excluded = []
    for date, values in zip(dates, zip(*(quotes[key] for key in FIELDS), strict=True), strict=True):
        if date < calendar[0] or date > calendar[-1]:
            continue
        op, hi, lo, close, volume = values
        if volume == 0:
            if date in calendar_set:
                excluded.append({'date': date, 'reason': 'zero volume'})
            continue
        if date not in calendar_set:
            raise ValueError(f'Nonzero or unknown-volume row on non-reference date {date}')
        if not all(isinstance(v, (float, int)) and math.isfinite(v) and v > 0 for v in values):
            excluded.append({'date': date, 'reason': 'missing or invalid OHLCV'})
            continue
        if not lo <= min(op, close) <= max(op, close) <= hi:
            excluded.append({'date': date, 'reason': 'invalid OHLC envelope'})
            continue
        rows.append((date, *values))
    if not rows:
        raise ValueError('No usable history in requested CSV window')
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('date', *FIELDS))
    writer.writerows(rows)
    return output.getvalue().encode('utf-8'), {
        'events': result.get('events', {}), 'exchange_timezone': meta['exchangeTimezoneName'],
        'first_trade_date_from_yahoo': iso_date(meta['firstTradeDate']) if meta.get('firstTradeDate') else None,
        'excluded_rows': excluded, 'repairs': [],
    }


def prepare():
    from stock_data_cache import verify

    if (DIRECTORY / 'manifest.json').exists():
        raise FileExistsError('Completed Nikkei snapshot already exists')
    capture_path = DIRECTORY / 'capture.json'
    receipt = json.loads(capture_path.read_bytes())
    verify(CACHE)
    reference = json.loads((CACHE / 'manifest.json').read_bytes())
    with (CACHE / '7203.T.csv').open(newline='') as source:
        calendar = tuple(row['date'] for row in csv.DictReader(source))
    calendar_set = set(calendar)
    symbols, roster_path = roster()
    if (symbols != receipt['requested'] or digest(roster_path.read_bytes()) != receipt['constituents_sha256']
            or len(calendar) != 2314):
        raise ValueError('Roster capture or verified reference calendar mismatch')
    records = {}
    omissions = receipt['omissions']
    for symbol in symbols:
        if symbol in omissions:
            continue
        raw = (DIRECTORY / f'{symbol}.json').read_bytes()
        if symbol in receipt['reused_previous_snapshot']:
            record = reference['symbols'][symbol]
            if digest(raw) != record['raw_sha256']:
                raise ValueError(f'{symbol}: copied raw cache hash mismatch')
            csv_bytes = (CACHE / f'{symbol}.csv').read_bytes()
        else:
            try:
                csv_bytes, record = convert(symbol, raw, calendar, calendar_set)
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                omissions[symbol] = {'reason': str(error), 'raw_sha256': digest(raw)}
                continue
        dates = [row['date'] for row in csv.DictReader(io.StringIO(csv_bytes.decode('utf-8')))]
        date_set = set(dates)
        if dates != sorted(date_set) or not date_set.issubset(calendar_set):
            raise ValueError(f'{symbol}: CSV has duplicate, out-of-order or non-reference dates')
        first, last = dates[0], dates[-1]
        records[symbol] = {**record, 'url': CHART_URL.format(symbol=symbol),
                           'rows': len(dates), 'first': first, 'last': last,
                           'raw_sha256': digest(raw), 'csv_sha256': digest(csv_bytes),
                           'missing_dates_inside_coverage': sorted(day for day in calendar_set - date_set if first < day < last),
                           'leading_reference_days': sum(day < first for day in calendar),
                           'trailing_reference_days': sum(day > last for day in calendar)}
        write_bytes(DIRECTORY / f'{symbol}.csv', csv_bytes)
    if set(records) & set(omissions) or set(records) | set(omissions) != set(symbols):
        raise ValueError('Input membership and data record keys differ')
    manifest = {**receipt, 'omissions': omissions, 'universe': '2026-11-13 fixed current Nikkei 225 membership',
                'constituents_url': ROSTER_URL,
                'reference_calendar_csv_sha256': reference['symbols']['7203.T']['csv_sha256'],
                'csv_period': [calendar[0], calendar[-1]], 'reference_session_count': len(calendar),
                'price_basis': 'Yahoo quote OHLC, split-adjusted according to source, with no Adj Close scaling',
                'quality_policy': 'Zero, invalid or missing OHLCV bars excluded; existing two prior data repairs retained; no fill or new synthetic repairs',
                'symbols': records}
    write_bytes(DIRECTORY / 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
    gaps = sum(bool(record['missing_dates_inside_coverage']) for record in records.values())
    reasons = Counter(record['reason'] for record in omissions.values())
    print(f'DATA_READY {len(records)}/{len(symbols)} charts; {gaps} with internal gaps; omissions {dict(reasons)}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--capture', action='store_true')
    actions.add_argument('--prepare', action='store_true')
    if parser.parse_args().capture:
        capture()
    else:
        prepare()
