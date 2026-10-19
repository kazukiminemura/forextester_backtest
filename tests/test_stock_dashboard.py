import csv
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import stock_dashboard as dashboard


@unittest.skipUnless((dashboard.RESULTS / 'summary.json').exists(), 'Saved stock experiment required')
class StockDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = dashboard.Dashboard()

    def test_portfolio_matches_saved_trades_and_annual_curve(self):
        view = self.app.view({})
        self.assertEqual(len(view['trades']), view['metrics']['trades'])
        self.assertAlmostEqual(sum(t['net_pnl'] for t in view['trades']), view['metrics']['net_profit'])
        self.assertAlmostEqual(sum(y['net_profit'] for y in view['annual']), view['metrics']['net_profit'])
        self.assertEqual(view['curve'][-1][1], view['metrics']['final_equity'])
        self.assertEqual(view['curve'][-1][2], view['baseline']['final_equity'])
        self.assertEqual(len(view['symbols']), 10)

    def test_cost_period_subset_and_symbol_are_consistent(self):
        query = {'cost': ['stress'], 'period': ['final_confirmation'],
                 'universe': ['exclude_three_known_issues']}
        view = self.app.view(query)
        self.assertEqual(view['metrics']['initial_capital'], 700000)
        self.assertEqual(len(view['symbols']), 7)
        self.assertTrue(all(t['symbol'] not in dashboard.GROUPS['exclude_three_known_issues'] for t in view['trades']))
        self.assertEqual(view['curve'][0][0][:4], '2023')
        query['symbol'] = ['7203.T']
        single = self.app.view(query)
        self.assertEqual(single['metrics']['initial_capital'], 100000)
        self.assertTrue(all(t['symbol'] == '7203.T' for t in single['trades']))
        self.assertAlmostEqual(sum(t['net_pnl'] for t in single['trades']), single['metrics']['net_profit'])
        query['symbol'] = ['6758.T']
        with self.assertRaises(ValueError):
            self.app.view(query)

    def test_http_download_prices_and_route_safety(self):
        server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.handler_for(self.app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/') as response:
                self.assertIn('株式検証ノート', response.read().decode())
                self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
            with urlopen(base + '/api/view?cost=stress&period=validation') as response:
                view = json.load(response)
                self.assertEqual(view['selection']['cost'], 'stress')
            with urlopen(base + '/api/research') as response:
                research = json.load(response)
                if research['available']:
                    self.assertEqual(len(research['rows']), 5)
                    if research['jev_failed']:
                        self.assertEqual(research['answers'], {})
                        self.assertIsNone(research['selected'])
            with urlopen(base + '/api/deep') as response:
                deep = json.load(response)
                if deep['available']:
                    self.assertEqual(len(deep['candidates']), 9)
                    band = next(c for c in deep['candidates'] if c['candidate'] == 'risk_band')
                    self.assertEqual(band['periods']['validation']['main']['trades'], 82)
                    self.assertNotIn('final_confirmation', band['periods'])
                    reference = next(c for c in deep['candidates'] if c['candidate'] == 'no_dow')
                    self.assertEqual(reference['periods']['continuous']['note'], '固定比較・選抜外')
            with urlopen(base + '/api/trades.csv?symbol=7203.T') as response:
                rows = list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
                self.assertTrue(rows)
                self.assertTrue(all(row['symbol'] == '7203.T' for row in rows))
                self.assertIn('attachment', response.headers['Content-Disposition'])
            with urlopen(base + '/api/prices?symbol=7203.T') as response:
                prices = json.load(response)
                self.assertEqual(len(prices), 2314)
                self.assertTrue(all(len(row) == 5 for row in prices))
            for path, status in [('/../AGENTS.md', 404), ('/api/view?period=../../', 400),
                                 ('/api/prices?symbol=../AGENTS', 400), ('/api/view?cost=main&cost=stress', 400),
                                 ('/api/view?unknown=1', 400)]:
                with self.assertRaises(HTTPError) as caught:
                    urlopen(base + path)
                self.assertEqual(caught.exception.code, status)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
