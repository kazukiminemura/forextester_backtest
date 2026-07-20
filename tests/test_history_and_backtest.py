from __future__ import annotations

import struct
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from forextester_backtest.cli import _write_trades
from forextester_backtest.data import OLE_EPOCH, HistoryRepository
from forextester_backtest.engine import BacktestEngine
from forextester_backtest.models import InstrumentMetadata, Trade
from forextester_backtest.presets import automatic_preset_name, resolve_preset
from forextester_backtest.strategies import SmaCrossoverStrategy
from forextester_backtest.tamukai import (
    TamukaiBacktester,
    TamukaiConfig,
    _ArmedOrder,
    _four_hour_bars,
    _pivot_states,
)


def ole(value: datetime) -> float:
    return (value - OLE_EPOCH).total_seconds() / 86_400


class HistoryRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        symbol = root / "TESTUSD"
        symbol.mkdir()
        (symbol / "info.dat").write_text(
            "name=TESTUSD\ndecimals=2\nspread=2\nlot=100\n",
            encoding="utf-8",
        )
        start = datetime(2024, 1, 1)
        bars = [
            (ole(start + timedelta(minutes=i)), price, price, price + 1, price - 1, 10)
            for i, price in enumerate((10.0, 11.0, 12.0, 9.0, 8.0, 13.0))
        ]
        with (symbol / "Bars.dat").open("wb") as stream:
            stream.write(struct.pack("<I", len(bars)))
            for row in bars:
                stream.write(struct.pack("<6d", *row))
        ticks = [
            (ole(start + timedelta(seconds=i)), 10.0 + i, 10.02 + i, 1)
            for i in range(3)
        ]
        with (symbol / "ticks.dat").open("wb") as stream:
            stream.write(struct.pack("<I", len(ticks)))
            for row in ticks:
                stream.write(struct.pack("<3dI", *row))
        self.repository = HistoryRepository(root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_reads_and_filters_fixed_records(self) -> None:
        start = datetime(2024, 1, 1, 0, 2)
        bars = list(self.repository.bars("testusd", start=start))
        self.assertEqual(4, len(bars))
        self.assertEqual(12.0, bars[0].open)
        ticks = list(
            self.repository.ticks("TESTUSD", start=datetime(2024, 1, 1, 0, 0, 1))
        )
        self.assertEqual([11.0, 12.0], [tick.bid for tick in ticks])

    def test_aggregates_timeframe(self) -> None:
        bars = list(self.repository.bars("TESTUSD", timeframe="5m"))
        self.assertEqual(2, len(bars))
        self.assertEqual(
            (10.0, 13.0, 7.0, 8.0, 50.0),
            (
                bars[0].open,
                bars[0].high,
                bars[0].low,
                bars[0].close,
                bars[0].volume,
            ),
        )


class BacktestEngineTest(unittest.TestCase):
    def test_sma_signal_executes_on_next_bar(self) -> None:
        metadata = InstrumentMetadata(
            "TESTUSD", {"decimals": "2", "spread": "0", "lot": "1"}
        )
        start = datetime(2024, 1, 1)
        closes = (1.0, 2.0, 3.0, 4.0)
        from forextester_backtest.models import Bar

        bars = [
            Bar(start + timedelta(minutes=i), price, price, price, price, 1)
            for i, price in enumerate(closes)
        ]
        result = BacktestEngine(metadata, lots=1, initial_capital=100).run(
            bars, SmaCrossoverStrategy(1, 2)
        )
        self.assertEqual(1, result.trade_count)
        self.assertEqual(3.0, result.trades[0].entry_price)
        self.assertEqual(1.0, result.net_profit)


class PresetSelectionTest(unittest.TestCase):
    def test_jpy_cross_takes_precedence_for_usdjpy(self) -> None:
        self.assertEqual("jpy-cross", automatic_preset_name("USDJPY"))
        self.assertEqual("jpy-cross", automatic_preset_name("EURJPY"))

    def test_eurusd_research_values_are_not_shared_with_usd_crosses(self) -> None:
        self.assertEqual("eurusd-research", automatic_preset_name("EURUSD"))
        self.assertEqual("pine", automatic_preset_name("USDCAD"))
        self.assertEqual("pine", automatic_preset_name("GBPUSD"))
        preset = resolve_preset("EURUSD", "auto")
        self.assertEqual(
            ("long", 0.75, 0.5, 1.0),
            (
                preset.direction,
                preset.max_range_atr,
                preset.first_target_r,
                preset.first_target_fraction,
            ),
        )
        self.assertEqual("recent OOS failed", preset.validation)

    def test_non_usd_non_jpy_cross_keeps_pine_defaults(self) -> None:
        self.assertEqual("pine", automatic_preset_name("EURGBP"))
        self.assertEqual("pine", automatic_preset_name("XAUUSD"))
        self.assertEqual("pine", automatic_preset_name("BTCUSD"))
        self.assertEqual("jpy-cross", resolve_preset("EURUSD", "usdjpy-70").name)

    def test_trade_csv_identifies_symbol_and_preset(self) -> None:
        now = datetime(2024, 1, 1)
        trade = Trade("long", now, 1.0, now, 1.1, 0.1, 10_000, 100, 0, 100)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trades.csv"
            _write_trades(path, [trade], "EURUSD", "eurusd-research")
            rows = path.read_text(encoding="utf-8-sig").splitlines()
        self.assertTrue(rows[0].startswith("symbol,preset,direction"))
        self.assertTrue(rows[1].startswith("EURUSD,eurusd-research,long"))

    def test_tradingview_indicator_contains_current_pair_presets(self) -> None:
        path = (
            Path(__file__).parents[1]
            / "scripts"
            / "tradingview"
            / "tamukai_pair_signal_indicator.pine"
        )
        source = path.read_text(encoding="utf-8")
        self.assertTrue(source.startswith("//@version=6\n"))
        self.assertIn('indicator("田向式 ペア別押し目レンジ・シグナル"', source)
        self.assertIn('plot(close, "Compile guard", display=display.none)', source)
        self.assertNotIn("strategy(", source)
        self.assertIn('activePreset == "JPYクロス" ? 1.0', source)
        self.assertIn('activePreset == "EURUSD研究" ? 0.75', source)
        self.assertIn('isXauUsd ? "XAUUSD研究"', source)
        self.assertIn("isXauResearch ? 1.25", source)
        self.assertIn("isXauResearch ? 0.75", source)
        self.assertIn("isXauResearch ? 0.20", source)
        self.assertIn("isXauResearch ? 0.0", source)
        self.assertIn('"注意: OOS -0.484R / 16件"', source)
        self.assertIn("barstate.isconfirmed", source)
        self.assertIn("lookahead=barmerge.lookahead_on", source)
        self.assertIn('"このインジケーターは1時間足専用です', source)
        self.assertIn("i_showTable or not isOneHourChart", source)


class TamukaiBacktesterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = InstrumentMetadata(
            "TESTUSD", {"decimals": "2", "spread": "0", "lot": "1"}
        )

    def test_defaults_match_attached_pine_inputs(self) -> None:
        config = TamukaiConfig()
        self.assertEqual(
            (4, 21, 2, 2, 2),
            (
                config.higher_hours,
                config.htf_sma_length,
                config.htf_pivot_left,
                config.htf_pivot_right,
                config.htf_slope_bars,
            ),
        )
        self.assertEqual(
            (0.03, 21, 3, 12, 0.50, 1.50, 0.25),
            (
                config.min_slope_atr,
                config.ltf_sma_length,
                config.range_bars,
                config.pullback_lookback,
                config.min_pullback_atr,
                config.max_range_atr,
                config.zone_tolerance_atr,
            ),
        )
        self.assertEqual(
            (4.0, 4.0, 1.5, 80.0, 2.5, 2.0, 8),
            (
                config.entry_buffer_pips,
                config.stop_buffer_pips,
                config.min_room_r,
                config.max_risk_pips,
                config.max_risk_atr,
                config.max_chase_atr,
                config.order_expiry_bars,
            ),
        )

    def test_four_hour_state_uses_aligned_buckets(self) -> None:
        from forextester_backtest.models import Bar

        start = datetime(2024, 1, 1)
        hourly = [
            Bar(
                start + timedelta(hours=i),
                float(i),
                float(i + 2),
                float(i - 1),
                float(i + 1),
                1,
            )
            for i in range(8)
        ]
        higher, mapping = _four_hour_bars(hourly)
        self.assertEqual([0, 0, 0, 0, 1, 1, 1, 1], mapping)
        self.assertEqual(2, len(higher))
        self.assertEqual(
            (0.0, 5.0, -1.0, 4.0),
            (
                higher[0].open,
                higher[0].high,
                higher[0].low,
                higher[0].close,
            ),
        )

    def test_pivot_is_not_available_before_right_bar_confirmation(self) -> None:
        from forextester_backtest.models import Bar

        start = datetime(2024, 1, 1)
        highs = (1.0, 2.0, 5.0, 3.0, 2.0)
        bars = [
            Bar(start + timedelta(hours=i), value, value, value - 1, value, 1)
            for i, value in enumerate(highs)
        ]
        states = _pivot_states(bars, 2, 2)
        self.assertIsNone(states[3].last_high)
        self.assertEqual(5.0, states[4].last_high)

    def test_stop_entry_takes_half_at_one_r_then_stops_runner(self) -> None:
        from forextester_backtest.models import Bar

        engine = TamukaiBacktester(self.metadata, lots=1, initial_capital=100)
        engine._armed = _ArmedOrder(1, 0, 100, 90, 100, 90)
        first = Bar(datetime(2024, 1, 1), 95, 111, 89, 105, 1)
        second = Bar(datetime(2024, 1, 1, 1), 100, 101, 89, 90, 1)
        self.assertFalse(engine._process_execution(first))
        self.assertIsNotNone(engine._position)
        assert engine._position is not None
        self.assertTrue(engine._position.first_target_reached)
        self.assertTrue(engine._process_execution(second))
        self.assertEqual(1, len(engine._trades))
        self.assertTrue(engine._trades[0].first_target_reached)
        self.assertAlmostEqual(0.0, engine._trades[0].net_pnl)

    def test_full_target_closes_entire_position(self) -> None:
        from forextester_backtest.models import Bar

        config = TamukaiConfig(first_target_r=0.5, first_target_fraction=1.0)
        engine = TamukaiBacktester(
            self.metadata, config=config, lots=1, initial_capital=100
        )
        engine._armed = _ArmedOrder(1, 0, 100, 90, 100, 90)
        bar = Bar(datetime(2024, 1, 1), 95, 106, 94, 105, 1)
        self.assertTrue(engine._process_execution(bar))
        self.assertEqual(1, len(engine._trades))
        self.assertTrue(engine._trades[0].first_target_reached)
        self.assertAlmostEqual(5.0, engine._trades[0].net_pnl)

    def test_pending_order_waits_for_allowed_entry_hour(self) -> None:
        from forextester_backtest.models import Bar

        config = TamukaiConfig(entry_hours=(1,))
        engine = TamukaiBacktester(
            self.metadata, config=config, lots=1, initial_capital=100
        )
        engine._armed = _ArmedOrder(1, 0, 100, 90, 100, 90)
        blocked = Bar(datetime(2024, 1, 1), 95, 111, 94, 105, 1)
        engine._process_execution(blocked)
        self.assertIsNone(engine._position)
        self.assertIsNotNone(engine._armed)
        allowed = Bar(datetime(2024, 1, 1, 1), 95, 101, 94, 100, 1)
        engine._process_execution(allowed)
        self.assertIsNotNone(engine._position)


if __name__ == "__main__":
    unittest.main()
