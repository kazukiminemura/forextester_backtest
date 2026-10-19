import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('jev_dashboard', Path(__file__).parents[1] / 'scripts/bb3_jev_dashboard.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def test_aggregation_and_route_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = dashboard.Status(root)
            self.assertIsNone(status.snapshot()['total'])
            self.assertEqual(status.snapshot()['totals'], {})
            h = 'a'*64
            (root/'responses').mkdir()
            for name, value in {
                'run_manifest.json': {'candidates': {'USDJPY': 2}, 'payload_hashes': [h, 'b'*64]},
                'candidates.json': {'USDJPY': [{'payload_hash': h}, {'payload_hash': 'b'*64}]},
                f'responses/{h}.json': {'valid': True, 'accepted': True, 'request': {'secret': 'DO_NOT_EXPOSE'}, 'response': {'usage': {'input_tokens': 1000}}},
            }.items():
                (root/name).write_text(json.dumps(value), encoding='utf-8')
            (root/'reservations.jsonl').write_text(json.dumps({'reserved_usd': .1})+'\n', encoding='utf-8')
            snapshot = status.snapshot()
            self.assertEqual(snapshot['processed'], 1)
            self.assertEqual(snapshot['unprocessed'], 1)
            self.assertEqual(snapshot['pairs'][0]['accepted'], 1)
            self.assertAlmostEqual(snapshot['estimated_yen'], .0084)
            self.assertAlmostEqual(snapshot['reserved_yen'], 20)
            self.assertNotIn('DO_NOT_EXPOSE', json.dumps(snapshot))
            server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.handler_for(status))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}'
                with urllib.request.urlopen(url+'/api/status') as response:
                    self.assertEqual(json.load(response)['processed'], 1)
                with urllib.request.urlopen(url+'/') as response:
                    self.assertIn('Jev'.encode(), response.read())
                for route in ('/../run_manifest.json', '/responses/'+h+'.json', '/api/status?file=secret'):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(url+route)
                    self.assertEqual(error.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_partial_files_and_zero_trades(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'candidates.json').write_text('{', encoding='utf-8')
            (root/'results.json').write_text(json.dumps({'complete': False, 'totals': {'jev_rr1.0_cost1.0': {'all': {'trades': 0, 'win_rate_pct': 0, 'profit_factor': None}}}}), encoding='utf-8')
            snapshot = dashboard.Status(root).snapshot()
            self.assertEqual(snapshot['phase'], 'incomplete')
            self.assertIsNone(snapshot['totals']['jev_rr1.0_cost1.0']['all']['profit_factor'])
            (root/'progress.json').write_text(json.dumps({'phase': 'validation'}), encoding='utf-8')
            (root/'responses').mkdir()
            (root/'responses'/('c'*64+'.json')).write_text(json.dumps({'valid': False, 'accepted': False, 'error_type': 'ValueError'}), encoding='utf-8')
            snapshot = dashboard.Status(root).snapshot()
            self.assertEqual(snapshot['phase'], 'validation')
            self.assertEqual(snapshot['inconsistent'], 1)
            self.assertEqual(snapshot['request_failed'], 0)

    def test_alternatives_are_separate_and_whitelist_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            initial = Path(directory)/'initial'
            initial.mkdir()
            alternatives = Path(directory)/'bb_alternatives_20260925'
            alternatives.mkdir()
            (alternatives/'progress.json').write_text(json.dumps({'phase': 'backtest', 'message': '集計中', 'completed_jobs': 7, 'total_jobs': 168}), encoding='utf-8')
            status = dashboard.Status(initial)
            self.assertEqual(status.snapshot()['alternatives']['completed_jobs'], 7)
            (alternatives/'results.json').write_text(json.dumps({'complete': True, 'numeric_gates_pass': {'wm': False, 'secret': 'DO_NOT_EXPOSE'}, 'totals': {'wm_rr1.0_cost1.0': {'all': {'trades': 20, 'profit_factor_r': .8, 'request': 'DO_NOT_EXPOSE'}}}}), encoding='utf-8')
            snapshot = status.snapshot()
            self.assertIsNone(snapshot['research'])
            self.assertEqual(snapshot['totals'], {})
            self.assertEqual(snapshot['alternatives']['total_jobs'], 168)
            self.assertEqual(snapshot['alternatives']['numeric_gates_pass'], {'wm': False})
            self.assertEqual(snapshot['alternatives']['totals']['wm_rr1.0_cost1.0']['all']['trades'], 20)
            self.assertNotIn('DO_NOT_EXPOSE', json.dumps(snapshot))

    def test_refinement_keeps_initial_cost_and_whitelists_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            initial = Path(directory)/'initial'
            initial.mkdir()
            refinement = Path(directory)/'bb3_jev_refine_20260925'
            refinement.mkdir()
            (initial/'reservations.jsonl').write_text(json.dumps({'reserved_usd': .1})+'\n', encoding='utf-8')
            (refinement/'progress.json').write_text(json.dumps({'phase': 'backtest', 'message': '集計中', 'completed_jobs': 7, 'total_jobs': 21}), encoding='utf-8')
            (refinement/('code_review_'+'a'*64+'.json')).write_text(json.dumps({'valid': True, 'request': {'code': 'DO_NOT_EXPOSE'}, 'response': {'usage': {'input_tokens': 2000}}}), encoding='utf-8')
            (refinement/'code_review_reservations.jsonl').write_text(json.dumps({'reserved_usd': .02})+'\n', encoding='utf-8')
            (refinement/'results.json').write_text(json.dumps({'complete': False, 'request': 'DO_NOT_EXPOSE', 'arm_labels': {'close_hold_noai_rr1.0_cost1.0': '終値確認'}, 'totals': {'close_hold_noai_rr1.0_cost1.0': {'all': {'trades': 20, 'profit_factor_r': 1.1}}}}), encoding='utf-8')
            snapshot = dashboard.Status(initial).snapshot()
            self.assertEqual(snapshot['reserved_yen'], 20)
            self.assertEqual(snapshot['research']['completed_jobs'], 7)
            self.assertEqual(snapshot['research']['review_calls'], 1)
            self.assertAlmostEqual(snapshot['research']['review_estimated_yen'], .0168)
            self.assertAlmostEqual(snapshot['research']['total_reserved_yen'], 24)
            self.assertEqual(snapshot['research']['phase'], 'backtest')
            self.assertEqual(snapshot['research']['totals']['close_hold_noai_rr1.0_cost1.0']['all']['profit_factor_r'], 1.1)
            self.assertNotIn('DO_NOT_EXPOSE', json.dumps(snapshot))

    def test_sixyear_progress_does_not_show_old_three_year_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root/'bb_alternatives_20260925'
            old.mkdir()
            (old/'results.json').write_text(json.dumps({'complete': True, 'totals': {'old': {}}}))
            new = root/'bb_alternatives_2020_2025_20260925'
            new.mkdir()
            (new/'progress.json').write_text(json.dumps({'phase':'preparing','completed_jobs':0,'total_jobs':336}))
            s = dashboard.Status(root/'initial').snapshot()['alternatives']
            self.assertEqual(s['start_year'], 2020)
            self.assertEqual(s['totals'], {})
            self.assertEqual(s['completed_jobs'], 0)


if __name__ == '__main__':
    unittest.main()
