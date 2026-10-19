import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "scripts/research_tamukai_stocks_deep.py"
spec = importlib.util.spec_from_file_location("stock_deep", PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def bars(n=80):
    return [m.base.Bar(datetime(2017,1,1)+timedelta(days=i), 98, 101, 97, 100, 1000) for i in range(n)]


class DeepStockTests(unittest.TestCase):
    def test_factor_filters_and_intersections(self):
        rows = bars()
        for i in range(60,80):
            rows[i] = m.base.Bar(rows[i].time, 99, 101, 97, 100+(i-60)/100, 1000)
        stop = [None]*79+[97]
        with patch.object(m.prior, "candidate_signals", return_value=stop):
            self.assertEqual(m.candidate_signals(rows, "risk_band")[-1], 97)
            self.assertIsNone(m.candidate_signals(rows, "trend_strength")[-1])
            self.assertIsNone(m.candidate_signals(rows, "trend_risk")[-1])
            self.assertEqual(m.candidate_signals(rows, "strong_rejection")[-1], 97)
            for combined, first, second in (("trend_shallow","trend_strength","shallow_pullback"),
                                             ("trend_risk","trend_strength","risk_band")):
                lhs=m.candidate_signals(rows, combined)
                a,b=m.candidate_signals(rows, first),m.candidate_signals(rows, second)
                self.assertEqual(lhs, [x if x is not None and y is not None else None for x,y in zip(a,b)])

    def test_cost_band_inclusive_and_uses_signal_close(self):
        rows = bars()
        for stop, expected in ((98, True),(96, True),(98.01,False),(95.99,False)):
            with patch.object(m.prior,"candidate_signals",return_value=[None]*79+[stop]):
                self.assertEqual(m.candidate_signals(rows,"risk_band")[-1] is not None,expected)

    def test_stress_gate_and_deterministic_selection(self):
        metric=dict(trades=100,net_profit=100,net_pf=1.2,max_drawdown_pct=10)
        result=dict(main=dict(metrics=metric),stress=dict(metrics=dict(net_profit=0)))
        self.assertFalse(m.qualifies(result,50))
        result["stress"]["metrics"]["net_profit"]=1
        self.assertTrue(m.qualifies(result,100))
        self.assertEqual(m.choose({},[]),"none")
        choices={key:result for key in ("trend_risk","risk_band","trend_strength")}
        self.assertEqual(m.choose(choices,list(choices)),"risk_band")

    def test_prefix_invariance(self):
        rows=bars()
        for candidate in m.RULES:
            full=m.candidate_signals(rows,candidate)
            for n in (23,24,25,26,60,79):
                self.assertEqual(m.candidate_signals(rows[:n],candidate),full[:n])


if __name__=="__main__":
    unittest.main()
