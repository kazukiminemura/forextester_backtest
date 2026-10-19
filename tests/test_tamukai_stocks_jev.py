import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "scripts/research_tamukai_stocks_jev.py"
spec = importlib.util.spec_from_file_location("stock_jev", PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def bars(n=70):
    return [m.base.Bar(datetime(2017, 1, 1)+timedelta(days=i), 100+i, 101+i, 99+i, 100+i, 1000)
            for i in range(n)]


class StockJevTests(unittest.TestCase):
    def test_each_condition_change_is_isolated(self):
        rows = bars()
        # Prior-three highs 200, 169, 168; last close 170 only breaks previous-day high.
        rows[-4] = m.base.Bar(rows[-4].time, 160, 200, 100, 160, 1000)
        rows[-3] = m.base.Bar(rows[-3].time, 160, 169, 100, 160, 1000)
        rows[-2] = m.base.Bar(rows[-2].time, 160, 168, 100, 160, 1000)
        rows[-1] = m.base.Bar(rows[-1].time, 169, 171, 168, 170, 1000)
        with patch.object(m.base, "pivot_trend", return_value=[True]*len(rows)):
            self.assertEqual(m.candidate_signals(rows, "prior_day_breakout")[-1], 100)
            self.assertIsNone(m.candidate_signals(rows, "no_dow")[-1])
        rows[-4] = m.base.Bar(rows[-4].time, 160, 167, 100, 160, 1000)
        with patch.object(m.base, "pivot_trend", return_value=[False]*len(rows)):
            self.assertEqual(m.candidate_signals(rows, "no_dow")[-1], 100)
            self.assertEqual(m.candidate_signals(rows, "sma63_trend")[-1], 100)
            self.assertIsNone(m.candidate_signals(rows, "prior_day_breakout")[-1])

    def test_prefix_invariance_and_sma63_warmup(self):
        rows = bars()
        for candidate in m.CANDIDATES:
            full = m.candidate_signals(rows, candidate)
            for n in (23, 40, 62, 63, 69):
                self.assertEqual(m.candidate_signals(rows[:n], candidate), full[:n])
        self.assertTrue(all(x is None for x in m.candidate_signals(rows[:62], "sma63_trend")))
        self.assertEqual(m.candidate_signals(rows, "baseline"), m.base.signals(rows))

    def test_gate_and_selection_cannot_be_overridden(self):
        row = dict(trades=50, net_profit=1, net_pf=1.1, max_drawdown_pct=20)
        self.assertTrue(m.qualifies(row))
        training = dict(eligible_candidates=["no_dow"], results={"no_dow": {"main": {"metrics": row}}})
        selection = dict(experiment_id=m.EXPERIMENT, selector="jev", training_sha256="hash", selected_candidate="no_dow")
        self.assertEqual(m.selected_candidate(selection, training, "hash"), "no_dow")
        with self.assertRaises(ValueError):
            m.selected_candidate(selection, training, "different")
        row["trades"] = 49
        with self.assertRaises(ValueError):
            m.selected_candidate(selection, training, "hash")

        selection["selected_candidate"] = "none"
        self.assertEqual(m.selected_candidate(selection, training, "hash"), "none")
        selection["selected_candidate"] = "baseline"
        with self.assertRaises(ValueError):
            m.selected_candidate(selection, training, "hash")

    def test_evaluation_requires_selection_before_loading_prices(self):
        with patch.object(m, "evidence", return_value={}), patch.object(m.base, "read_bars") as loader:
            with self.assertRaisesRegex(ValueError, "requires hash-bound"):
                m.run("evaluation", Path("unused"))
            loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
