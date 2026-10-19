import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/research_tamukai_stocks_daily.py"
spec = importlib.util.spec_from_file_location("stock_daily", PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def bar(day, open=100, high=101, low=99, close=100):
    return m.Bar(datetime(2020, 1, 1) + timedelta(days=day), open, high, low, close, 1000)


class DailyStockTests(unittest.TestCase):
    def test_pivots_confirmation_and_prefix_invariance(self):
        highs = [11, 12, 15, 13, 12, 13, 14, 18, 16, 15, 16, 17]
        lows = [9, 8, 10, 9, 6, 8, 10, 12, 11, 9, 11, 12]
        bars = [bar(i, (h+l)/2, h, l, (h+l)/2) for i, (h,l) in enumerate(zip(highs,lows))]
        trend = m.pivot_trend(bars)
        self.assertFalse(trend[10])
        self.assertTrue(trend[11])  # second higher low confirmed now, not at center 9
        for n in range(1, len(bars)+1):
            self.assertEqual(m.pivot_trend(bars[:n]), trend[:n])
        tied = list(bars)
        tied[10] = bar(10, 11, 16, 9, 11)
        self.assertFalse(m.pivot_trend(tied)[11])

    def test_gap_and_both_hit_priority(self):
        self.assertEqual(m.exit_fill(bar(0, 85, 115, 80, 100), 90, 110), (85, "gap_stop"))
        self.assertEqual(m.exit_fill(bar(0, 115, 120, 85, 100), 90, 110), (115, "gap_target"))
        self.assertEqual(m.exit_fill(bar(0, 100, 115, 85, 100), 90, 110), (90, "stop"))

    def test_cost_cash_entry_day_stop_and_initial_drawdown(self):
        bars = [bar(0), bar(1, 100, 115, 85, 100)]
        trades, curve = m.simulate(bars, [90, None], "2020-01-01", "2020-01-02", .001)
        units = 100000 / 100.1
        self.assertEqual(len(trades), 1)
        self.assertAlmostEqual(trades[0].units, units)
        self.assertAlmostEqual(curve[-1]["cash"], units * 90 * .999)
        self.assertEqual(trades[0].reason, "stop")
        self.assertAlmostEqual(m.metrics(trades, curve, 100000)["max_drawdown_pct"],
                               100 * (1 - units*90*.999/100000))

    def test_end_liquidation_and_no_preperiod_signal(self):
        bars = [bar(0), bar(1), bar(2, 101, 102, 100, 101)]
        trades, curve = m.simulate(bars, [90, None, None], "2020-01-01", "2020-01-03", .001)
        self.assertEqual(trades[0].reason, "period_end")
        self.assertEqual(trades[0].exit, 101)
        self.assertEqual(curve[-1]["cash"], curve[-1]["equity"])
        trades, _ = m.simulate(bars, [90, None, None], "2020-01-02", "2020-01-03", .001)
        self.assertEqual(trades, [])

    def test_skip_invalid_gap_and_exit_close_signal(self):
        bars = [bar(0), bar(1, 89, 101, 88, 100), bar(2, 100, 111, 99, 105),
                bar(3, 100, 111, 99, 105)]
        trades, _ = m.simulate(bars, [90, 90, 90, None], "2020-01-01", "2020-01-04", 0)
        self.assertEqual([t.entry_date for t in trades], ["2020-01-03", "2020-01-04"])
        self.assertTrue(all(t.reason == "target" for t in trades))

    def test_buyhold_costs_and_initial_peak(self):
        trades, curve = m.simulate([bar(0)], [None], "2020-01-01", "2020-01-01", .001, buyhold=True)
        value = 100000 * .999 / 1.001
        self.assertAlmostEqual(curve[0]["equity"], value)
        self.assertAlmostEqual(trades[0].net_pnl, value-100000)
        self.assertGreater(m.metrics(trades, curve, 100000)["max_drawdown_pct"], 0)


if __name__ == "__main__":
    unittest.main()
