import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta
from forextester_backtest.agents import Candidate, Gate, ResearchAgent, ValidationAgent, run
from forextester_backtest.models import Bar, InstrumentMetadata


class FakeModel:
    def __init__(self, reply):
        self.reply = reply

    def respond(self, instructions, evidence):
        return self.reply


class SyntheticHistory:
    root = Path(".")

    def symbols(self):
        return ["USDJPY", "EURUSD"]

    def metadata(self, symbol):
        return InstrumentMetadata(symbol, {"decimals": "5", "spread": "10", "lot": "100000"})

    def bars(self, symbol, start, end, timeframe):
        while start <= end:
            yield Bar(start, 1.1, 1.101, 1.099, 1.1, 1)
            start += timedelta(minutes=15)


class TradingAgentTests(unittest.TestCase):
    def test_rejects_unsafe_model_parameters(self):
        for reply in ('[{"first_target_r":2}]', '[{"max_range_atr":NaN}]',
                      '[{"direction":"shell"}]', '[]', '[{"max_range_atr":true}]'):
            with self.assertRaises((ValueError, TypeError)):
                ResearchAgent(FakeModel(reply)).propose()

    def test_rr_is_full_exit(self):
        config = Candidate().config()
        self.assertEqual((1, 1), (config.first_target_r, config.first_target_fraction))

    def test_gate_rejects_missing_and_nonfinite(self):
        good = dict(trade_count=100, net_profit=10, profit_factor=1.3, max_drawdown_pct=5)
        self.assertEqual([], Gate().reasons(good))
        for key in good:
            for value in (None, float('nan'), float('inf')):
                self.assertTrue(Gate().reasons({**good, key: value}))
        self.assertEqual('REJECTED', ValidationAgent(Gate()).review([])['status'])

    def test_research_pass_never_approves_live(self):
        result = ValidationAgent(Gate()).review([dict(symbol='USDJPY', period='train', metrics=dict(
            trade_count=100, net_profit=10, profit_factor=1.3, max_drawdown_pct=5))])
        self.assertEqual('RESEARCH_PASS', result['status'])
        self.assertFalse(result['live_approved'])

    def test_full_pipeline_records_rejected_runs_and_unique_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            dates = [datetime(2024, 1, day) for day in (1, 3, 5, 7)]
            directory = run(SyntheticHistory(), ['USDJPY', 'EURUSD'], dates, Path(folder))
            data = json.loads((directory / 'results.json').read_text(encoding='utf-8'))
            self.assertEqual(3, len(data['results']))
            self.assertTrue(all(r['review']['status'] == 'REJECTED' for r in data['results']))
            self.assertTrue(all(len(r['results']) == 6 for r in data['results']))
            events = [json.loads(line) for line in (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual('completed', events[-1]['event'])
            self.assertTrue((directory / 'report.md').exists())

    def test_rejects_overlap_and_duplicate_symbols(self):
        dates = [datetime(2024, 1, day) for day in (1, 2, 2, 4)]
        with self.assertRaises(ValueError):
            run(SyntheticHistory(), ['USDJPY', 'EURUSD'], dates, Path('unused'))


if __name__ == '__main__':
    unittest.main()
