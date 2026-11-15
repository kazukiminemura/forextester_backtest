"""Scan VCP candidates in the published GMO cash-equity market scope."""

import argparse
from datetime import datetime
import io
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin
from xml.etree import ElementTree
from zipfile import ZipFile

from scan_nikkei225_vcp import ROOT, TOKYO, download, report, scan


JPX = 'https://www.jpx.co.jp/markets/statistics-equities/misc/01.html'
MARKETS = {'プライム（内国株式）': 'プライム', 'スタンダード（内国株式）': 'スタンダード',
           'グロース（内国株式）': 'グロース'}
OUTPUT = ROOT / 'artifacts/gmo_vcp_latest.html'


def listings(data):
    with ZipFile(io.BytesIO(data)) as book:
        strings = [''.join(node.itertext()) for node in ElementTree.fromstring(book.read('xl/sharedStrings.xml'))]
        sheet = ElementTree.fromstring(book.read('xl/worksheets/sheet1.xml'))
    rows = []
    for row in sheet.findall('.//{*}sheetData/{*}row'):
        values = {}
        for cell in row.findall('{*}c'):
            column = cell.attrib['r'].rstrip('0123456789')
            if column in {'A', 'B', 'C', 'D'}:
                value = cell.findtext('{*}v')
                if value is not None:
                    values[column] = strings[int(value)] if cell.get('t') == 's' else value
        if values.get('D') in MARKETS and re.fullmatch(r'\d[0-9A-Z]\d[0-9A-Z]', values['B']):
            rows.append((values['A'], values['B'], values['C'], MARKETS[values['D']]))
    dates = {row[0] for row in rows}
    codes = {row[1] for row in rows}
    if len(dates) != 1 or len(codes) != len(rows) or len(codes) < 3000:
        raise ValueError('公式一覧の市場区分・日付・銘柄件数を確認できません')
    day = datetime.strptime(dates.pop(), '%Y%m%d').date()
    return day, {code: (name, market) for _, code, name, market in rows}


def load_listings(path):
    if path:
        return listings(path.read_bytes())
    page = download(JPX).decode('utf-8')
    match = re.search(r'href="([^"<>]*/data_j\.xlsx)"', page)
    if match is None:
        raise ValueError('JPXの公式Excel一覧が見つかりません')
    return listings(download(urljoin(JPX, match[1])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--listings', type=Path, help='Use a previously downloaded official JPX workbook')
    parser.add_argument('--expected-session')
    args = parser.parse_args()
    roster_day, stocks = load_listings(args.listings)
    print(f'JPX {roster_day}: {len(stocks)} domestic common stocks', flush=True)
    now = datetime.now(TOKYO)
    session, rows = scan(now, args.expected_session, sorted(stocks), workers=12, progress=True)
    for row in rows:
        name, row['market'] = stocks[row['code']]
        if 'name' in row:
            row['name'] = name
        else:
            row['listing_name'] = name
    scope = (f'JPX {roster_day}時点の東証プライム・スタンダード・グロースの内国普通株。'
             'GMOクリック証券の公表取扱範囲を使用。銘柄別の現物買付規制は注文前にGMOで確認してください。')
    html = report(session, now, rows, title='GMOクリック証券向け VCP買い候補', scope=scope,
                  command='python -B scripts/scan_gmo_vcp.py', readiness_days=10)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=OUTPUT.parent, delete=False) as stream:
        stream.write(html)
        temporary = Path(stream.name)
    temporary.replace(OUTPUT)
    candidates = [row for row in rows if 'pivot' in row]
    summary = {'session': str(session), 'roster_date': str(roster_day), 'total': len(rows),
               'unavailable': sum('name' not in row for row in rows), 'candidates': candidates}
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    main()
