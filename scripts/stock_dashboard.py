"""Local, read-only dashboard for the saved Japanese equity experiment."""
import argparse
import csv
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from stock_data_cache import CACHE, ROOT, verify

RESULTS = ROOT / 'agent_runs/tamukai_stocks_daily_cached_replay/results'
RESEARCH = ROOT / 'agent_runs/tamukai_stocks_jev_20260926'
DEEP = ROOT / 'agent_runs/tamukai_stocks_deep_20260926'
NAMES = {'7203.T': 'トヨタ自動車', '6758.T': 'ソニーグループ', '8306.T': '三菱UFJ FG',
         '9432.T': 'NTT', '9984.T': 'ソフトバンクG', '6501.T': '日立製作所',
         '6861.T': 'キーエンス', '8035.T': '東京エレクトロン', '8058.T': '三菱商事', '4502.T': '武田薬品工業'}
PERIODS = {'continuous': '2017–2025 / 9年連続', 'training': '2017–2019',
           'validation': '2020–2022', 'final_confirmation': '2023–2025'}
GROUPS = {'all': set(), 'exclude_sony': {'6758.T'},
          'exclude_three_known_issues': {'6758.T', '8306.T', '8035.T'}}


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


class Dashboard:
    def __init__(self, results=RESULTS, data=CACHE):
        self.results, self.data = Path(results), Path(data)
        verify(self.data)
        self.summary()  # Fail visibly at startup if the saved inputs differ.

    def summary(self):
        result = json.loads((self.results / 'summary.json').read_text(encoding='utf-8'))
        for symbol in NAMES:
            actual = hashlib.sha256((self.data / f'{symbol}.csv').read_bytes()).hexdigest()
            if actual != result['data_sha256'][symbol]:
                raise ValueError('保存株価と検証結果の識別子が一致しません。')
        return result

    def options(self, query):
        allowed = {'cost', 'period', 'universe', 'symbol'}
        if set(query) - allowed or any(len(value) != 1 for value in query.values()):
            raise ValueError('選択項目が不正です。')
        cost = query.get('cost', ['main'])[0]
        period = query.get('period', ['continuous'])[0]
        universe = query.get('universe', ['all'])[0]
        symbol = query.get('symbol', ['all'])[0]
        if cost not in ('main', 'stress') or period not in PERIODS or universe not in GROUPS:
            raise ValueError('選択項目が不正です。')
        symbols = [s for s in NAMES if s not in GROUPS[universe]]
        if symbol != 'all' and symbol not in symbols:
            raise ValueError('対象外の銘柄です。')
        return cost, period, universe, symbol, symbols

    def view(self, query):
        cost, period, universe, symbol, symbols = self.options(query)
        summary = self.summary()
        results = summary['periods'][cost][period]
        selected = [symbol] if symbol != 'all' else symbols
        curve_name = f'{symbol}_equity.csv' if symbol != 'all' else (
            'portfolio_equity.csv' if universe == 'all' else f'{universe}_equity.csv')
        def metric(method):
            item = results[method]
            if symbol != 'all':
                return item['by_symbol'][symbol]
            return item if universe == 'all' else item['quality_diagnostics'][universe]
        # Return only displayed scalar metrics, not nested result trees.
        metrics = {k: v for k, v in metric('strategy').items() if not isinstance(v, (dict, list))}
        baseline = {k: v for k, v in metric('buyhold').items() if not isinstance(v, (dict, list))}
        folder = self.results / cost / period
        strategy = csv_rows(folder / 'strategy' / curve_name)
        buyhold = csv_rows(folder / 'buyhold' / curve_name)
        if [r['date'] for r in strategy] != [r['date'] for r in buyhold]:
            raise ValueError('比較曲線の日付が一致しません。')
        curve = [[a['date'], float(a['equity']), float(b['equity'])] for a, b in zip(strategy, buyhold)]
        if not curve or abs(curve[-1][1] - metrics['final_equity']) > .01:
            raise ValueError('保存残高と集計結果が一致しません。')
        annual, previous, previous_baseline = [], metrics['initial_capital'], baseline['initial_capital']
        for year in sorted({r[0][:4] for r in curve}):
            last = next(row for row in reversed(curve) if row[0].startswith(year))
            annual.append({'year': year, 'net_profit': last[1] - previous,
                           'return_pct': 100 * (last[1] / previous - 1),
                           'buyhold_return_pct': 100 * (last[2] / previous_baseline - 1)})
            previous, previous_baseline = last[1], last[2]
        trades = []
        for s in selected:
            for row in csv_rows(folder / 'strategy' / f'{s}_trades.csv'):
                trades.append({'symbol': s, 'name': NAMES[s], **{
                    k: (v if k.endswith('_date') or k == 'reason' else float(v)) for k, v in row.items()}})
        trades.sort(key=lambda r: (r['entry_date'], r['symbol']), reverse=True)
        if len(trades) != metrics['trades']:
            raise ValueError('保存明細の件数が集計と一致しません。')
        manifest = json.loads((self.data / 'manifest.json').read_text(encoding='utf-8'))
        return dict(metrics=metrics, baseline=baseline, curve=curve, annual=annual, trades=trades,
                    symbols=[dict(symbol=s, name=NAMES[s], **results['strategy']['by_symbol'][s]) for s in symbols],
                    selection=dict(cost=cost, period=period, universe=universe, symbol=symbol),
                    meta=dict(experiment=summary['experiment_id'], completed_at=summary['completed_at'],
                              retrieved_at=manifest['retrieved_at'], first=curve[0][0], last=curve[-1][0],
                              sessions=len(curve), dataset='jp_largecap10_20260926', source='Yahoo Finance 日足',
                              numeric_gate_pass=summary['observational_gate_pass'], gates=summary['gates']))

    def prices(self, query):
        if set(query) != {'symbol'} or len(query['symbol']) != 1 or query['symbol'][0] not in NAMES:
            raise ValueError('対象外の銘柄です。')
        self.summary()
        symbol = query['symbol'][0]
        rows = csv_rows(self.data / f'{symbol}.csv')
        return [[r['date'], *[float(r[k]) for k in ('open', 'high', 'low', 'close')]] for r in rows]

    def research(self):
        path = RESEARCH / 'results/training.json'
        if not path.exists():
            return {'available': False}
        training = json.loads(path.read_text(encoding='utf-8'))
        result = dict(available=True, period=training['period'],
                      rows=[dict(candidate=c, main=r['main']['metrics'], stress=r['stress']['metrics'])
                            for c, r in training['results'].items()],
                      eligible=training['eligible_candidates'], selected=None, answers={})
        failed = []
        for evidence in RESEARCH.glob('jev_training_*.json'):
            record = json.loads(evidence.read_text(encoding='utf-8'))
            if not record['valid']:
                failed.append(record['error_type'])
        result['jev_failed'] = bool(failed)
        selected = RESEARCH / 'selection.json'
        if selected.exists():
            selection = json.loads(selected.read_text(encoding='utf-8'))
            if selection['training_sha256'] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError('Jev選抜と訓練結果が一致しません。')
            evidence = (ROOT / selection['jev_evidence']).resolve()
            if not evidence.is_relative_to(RESEARCH.resolve()) or hashlib.sha256(evidence.read_bytes()).hexdigest() != selection['jev_sha256']:
                raise ValueError('Jev評価記録が一致しません。')
            record = json.loads(evidence.read_text(encoding='utf-8'))
            if not record['valid']:
                raise ValueError('Jev評価が未完了です。')
            result.update(selected=selection['selected_candidate'], answers=record['response']['answers'],
                          model=record['response']['model'], usage_jpy_estimate=record['usage_usd'] * 200)
        return result

    def deep_research(self):
        path = DEEP / 'dashboard.json'
        if not path.exists():
            return {'available': False}
        result = json.loads(path.read_text(encoding='utf-8'))
        for name, expected in result['evidence_sha256'].items():
            evidence = (DEEP / name).resolve()
            if not evidence.is_relative_to(DEEP.resolve()) or hashlib.sha256(evidence.read_bytes()).hexdigest() != expected:
                raise ValueError('追加研究の記録が一致しません。')
        return result


def handler_for(dashboard):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            try:
                headers = {}
                if parsed.path == '/' and not parsed.query:
                    body, mime = Path(__file__).with_suffix('.html').read_bytes(), 'text/html; charset=utf-8'
                elif parsed.path == '/api/view':
                    body = json.dumps(dashboard.view(query), ensure_ascii=False, allow_nan=False).encode()
                    mime = 'application/json; charset=utf-8'
                elif parsed.path == '/api/prices':
                    body = json.dumps(dashboard.prices(query), allow_nan=False).encode()
                    mime = 'application/json; charset=utf-8'
                elif parsed.path == '/api/research' and not parsed.query:
                    body = json.dumps(dashboard.research(), ensure_ascii=False, allow_nan=False).encode()
                    mime = 'application/json; charset=utf-8'
                elif parsed.path == '/api/deep' and not parsed.query:
                    body = json.dumps(dashboard.deep_research(), ensure_ascii=False, allow_nan=False).encode()
                    mime = 'application/json; charset=utf-8'
                elif parsed.path == '/api/trades.csv':
                    view = dashboard.view(query)
                    output = io.StringIO(newline='')
                    fields = ['symbol', 'name', 'signal_date', 'entry_date', 'exit_date', 'entry', 'exit',
                              'stop', 'target', 'units', 'entry_cost', 'exit_cost', 'net_pnl', 'return_pct', 'reason']
                    writer = csv.DictWriter(output, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(view['trades'])
                    body, mime = output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8'
                    headers['Content-Disposition'] = 'attachment; filename="stock-trades.csv"'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
            except (ValueError, KeyError):
                self.send_response(400)
                body = json.dumps({'error': '選択または保存データを確認してください。'}, ensure_ascii=False).encode()
                mime = 'application/json; charset=utf-8'
            except OSError:
                self.send_response(503)
                body = json.dumps({'error': '保存結果を読み込めません。データの保存場所を確認してください。'}, ensure_ascii=False).encode()
                mime = 'application/json; charset=utf-8'
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(body)))
            try:
                self.end_headers()
                self.wfile.write(body)
            except ConnectionError:
                pass  # Changing a filter cancels the browser's previous request.

        def log_message(self, *args):
            pass
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8769)
    parser.add_argument('--results', type=Path, default=RESULTS)
    parser.add_argument('--data-dir', type=Path, default=CACHE)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(Dashboard(args.results, args.data_dir)))
    print(f'DASHBOARD_URL=http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
