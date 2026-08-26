from __future__ import annotations

import struct
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from forextester_backtest.alternative import AlternativeBacktester, AlternativeConfig
from forextester_backtest.cli import _write_trades, build_parser
from forextester_backtest.data import OLE_EPOCH, HistoryRepository
from forextester_backtest.engine import BacktestEngine
from forextester_backtest.models import Bar, InstrumentMetadata, Trade
from forextester_backtest.presets import automatic_preset_name, resolve_preset
from forextester_backtest.strategies import SmaCrossoverStrategy
from forextester_backtest.tamukai import (
    TamukaiBacktester,
    TamukaiConfig,
    _ArmedOrder,
    _dmi,
    _four_hour_bars,
    _pivot_states,
)


def ole(value: datetime) -> float:
    return (value - OLE_EPOCH).total_seconds() / 86_400


class AlternativeBacktesterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = InstrumentMetadata(
            "USDJPY", {"decimals": "3", "spread": "0", "lot": "1"}
        )

    def test_donchian_enters_next_hour_and_resolves_same_bar_as_stop(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar(start, 10.0, 11.0, 9.0, 10.0, 1.0),
            Bar(start + timedelta(hours=1), 10.0, 11.0, 9.0, 10.0, 1.0),
            Bar(start + timedelta(hours=2), 10.0, 12.0, 10.0, 11.5, 1.0),
            Bar(start + timedelta(hours=3), 11.5, 14.0, 8.0, 12.0, 1.0),
        ]
        config = AlternativeConfig(
            logic="donchian",
            direction="long",
            atr_length=2,
            channel_length=2,
            slow_ema=2,
            stop_atr=1.0,
        )

        result = AlternativeBacktester(self.metadata, config, lots=1.0).run(bars)

        self.assertEqual(1, result.trade_count)
        trade = result.trades[0]
        self.assertEqual(start + timedelta(hours=3), trade.entry_time)
        self.assertLess(trade.net_pnl, 0)
        self.assertEqual(trade.initial_stop, trade.exit_price)
        self.assertAlmostEqual(
            trade.entry_price - trade.initial_stop,
            trade.first_target - trade.entry_price,
        )

    def test_rejects_non_hourly_input(self) -> None:
        config = AlternativeConfig(logic="donchian")
        bars = [Bar(datetime(2024, 1, 1, 0, 30), 1, 2, 0, 1, 1)]
        with self.assertRaisesRegex(ValueError, "1時間足"):
            AlternativeBacktester(self.metadata, config).run(bars)

        four_hour_bars = [
            Bar(datetime(2024, 1, 1, hour), 1, 2, 0, 1, 1) for hour in (0, 4, 8)
        ]
        with self.assertRaisesRegex(ValueError, "1時間足"):
            AlternativeBacktester(self.metadata, config).run(four_hour_bars)


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
    def test_backtest_defaults_to_fifteen_minute_entries(self) -> None:
        args = build_parser().parse_args(["backtest", "USDJPY"])
        self.assertEqual("15m", args.entry_timeframe)
        self.assertTrue(args.false_breakout_filter)

    def test_jpy_cross_takes_precedence_for_usdjpy(self) -> None:
        self.assertEqual("jpy-cross", automatic_preset_name("USDJPY"))
        self.assertEqual("jpy-cross", automatic_preset_name("EURJPY"))
        preset = resolve_preset("USDJPY", "auto")
        self.assertEqual(
            (0.03, 1.0, 1.5, 1.0, 1.0, "long"),
            (
                preset.min_slope_atr,
                preset.max_range_atr,
                preset.min_room_r,
                preset.first_target_r,
                preset.first_target_fraction,
                preset.direction,
            ),
        )

    def test_jpy_frequency_is_explicit_and_keeps_strict_rr1(self) -> None:
        preset = resolve_preset("USDJPY", "jpy-frequency")
        self.assertEqual(
            (0.03, 1.0, 1.0, 1.0, 1.0, "long"),
            (
                preset.min_slope_atr,
                preset.max_range_atr,
                preset.min_room_r,
                preset.first_target_r,
                preset.first_target_fraction,
                preset.direction,
            ),
        )

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
        self.assertIn('indicator("田向式 ペア別押し目レンジ・シグナル RR1 15m v5"', source)
        self.assertIn('plot(close, "Compile guard", display=display.none)', source)
        self.assertNotIn("strategy(", source)
        self.assertIn('activePreset == "JPYクロス" or isJpyFrequency ? 1.0', source)
        self.assertIn('activePreset == "JPY頻度優先"', source)
        self.assertIn('"15m再検証前"', source)
        self.assertIn('activePreset == "EURUSD研究" ? 0.75', source)
        self.assertIn('isXauUsd ? "XAUUSD研究"', source)
        self.assertIn("isXauResearch ? 1.0", source)
        self.assertIn("isXauResearch ? 4", source)
        self.assertIn("isXauResearch ? 0.06", source)
        self.assertIn("isXauResearch ? 0.25", source)
        self.assertIn("isXauResearch ? 0.40", source)
        self.assertIn("isXauResearch ? 2.0", source)
        self.assertIn("isXauResearch ? 0.0", source)
        self.assertIn('input.float(0.0, "トレンド判定の最低4H ADX（0=無効）"', source)
        self.assertNotIn("i_customTargetR", source)
        self.assertNotIn("i_customTargetFraction", source)
        self.assertNotIn("firstTargetReached", source)
        self.assertIn("float fixedTargetR = 1.0", source)
        self.assertIn('"Pending TP 1:1"', source)
        self.assertIn('"RR 1:1 / 100%"', source)
        self.assertIn('"田向式 RR1 15m v5"', source)
        self.assertIn("table.new(position.top_right, 2, 12", source)
        self.assertIn("barstate.isconfirmed", source)
        self.assertIn('input.bool(true, "だまし回避（終値抜け後、次足始値でEntry）"', source)
        self.assertIn("close >= armedEntry", source)
        self.assertIn("close <= armedEntry", source)
        self.assertIn("virtualEntry := open", source)
        self.assertIn('text="終値確認\\n次足ENTRY"', source)
        self.assertIn('"ENTRY BUY"', source)
        self.assertIn('"ENTRY SELL"', source)
        self.assertIn("str.tostring(signalEntryPrice, format.mintick)", source)
        self.assertIn("line entryLevelLine = line.new", source)
        self.assertIn("line targetLevelLine = line.new", source)
        self.assertIn("line stopLevelLine = line.new", source)
        self.assertIn("color=color.yellow, width=4", source)
        self.assertIn('"黄色 ENTRY BUY/SELL = ここで入る"', source)
        self.assertIn('"Entry候補（まだ待つ）"', source)
        self.assertIn('"ENTRY実行価格"', source)
        self.assertIn('"Pending entry (not executed)"', source)
        self.assertIn("while array.size(tradeEntryLabels) > i_historyTradeCount", source)
        self.assertIn("lookahead=barmerge.lookahead_on", source)
        self.assertIn('"このインジケーターは15分足専用です', source)
        self.assertIn("i_showTable or not isFifteenMinuteChart", source)
        self.assertIn('symbol, "15", f_scanLtfPack', source)
        self.assertNotIn("isOneHourChart", source)
        self.assertNotIn("isThirtyMinuteChart", source)
        self.assertIn("ta.dmi(i_htfAdxLen, i_htfAdxSmoothing)", source)
        self.assertIn("htfAdx >= i_minHtfAdx", source)
        self.assertIn("scanHtfAdx >= i_minHtfAdx", source)
        self.assertIn("4H RANGE / ADX", source)

    def test_tradingview_indicator_includes_opportunity_scanner(self) -> None:
        path = (
            Path(__file__).parents[1]
            / "scripts"
            / "tradingview"
            / "tamukai_pair_signal_indicator.pine"
        )
        source = path.read_text(encoding="utf-8")
        self.assertEqual(10, source.count("input.symbol("))
        self.assertEqual(10, source.count("= f_scanPair(i_scanSymbol"))
        self.assertIn('state == 2 ? "BUY待ち"', source)
        self.assertIn('state == -2 ? "SELL待ち"', source)
        self.assertIn('"Entry候補"', source)
        self.assertIn("alertcondition(scanNewChance", source)
        scanner_path = path.with_name("tamukai_opportunity_scanner.pine")
        self.assertFalse(scanner_path.exists())

    def test_rebuilt_yosuga_indicator_is_strict_rr1_and_five_minute(self) -> None:
        path = (
            Path(__file__).parents[1]
            / "scripts"
            / "tradingview"
            / "yosuga_5m_rebuilt_indicator.pine"
        )
        source = path.read_text(encoding="utf-8")
        self.assertTrue(source.startswith("//@version=6\n"))
        self.assertIn('indicator("よすが式 4H・15m・5m 再構築 RR1 v2"', source)
        self.assertIn("dynamic_requests=true", source)
        self.assertNotIn("strategy(", source)
        self.assertIn("timeframe.multiplier == 5", source)
        self.assertIn('input.timeframe("240", "環境認識"', source)
        self.assertIn('input.timeframe("15", "押し戻り判断"', source)
        self.assertEqual(5, source.count("request.security("))
        self.assertIn("lookahead=barmerge.lookahead_on", source)
        self.assertIn("lastHigh[1]", source)
        self.assertIn("activeTarget := activeEntry + risk * positionDirection", source)
        self.assertIn('table.cell(stats, 1, 8, "1:1固定")', source)
        self.assertIn('plotshape(newBuy, "BUY entry"', source)
        self.assertIn('plotshape(newSell, "SELL entry"', source)
        self.assertIn('"勝率"', source)
        self.assertEqual(12, source.count("input.symbol("))
        self.assertEqual(12, source.count("= f_scanPair(i_scanSymbol"))
        self.assertIn('state == 3 ? "BUY候補"', source)
        self.assertIn('state == -3 ? "SELL候補"', source)
        self.assertIn('state == 2 ? "押し目待ち"', source)
        self.assertIn('state == -2 ? "戻り待ち"', source)
        self.assertIn("table.new(position.bottom_right, 4, 13", source)
        self.assertIn("alertcondition(scannerNewChance", source)

class TamukaiBacktesterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = InstrumentMetadata(
            "TESTUSD", {"decimals": "2", "spread": "0", "lot": "1"}
        )

    def test_defaults_match_attached_pine_inputs(self) -> None:
        config = TamukaiConfig()
        self.assertEqual(15, config.entry_minutes)
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
        self.assertEqual((14, 14, 0.0), (
            config.htf_adx_length,
            config.htf_adx_smoothing,
            config.min_htf_adx,
        ))
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

    def test_fifteen_minute_config_accepts_only_fifteen_minute_bars(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar(start, 100, 101, 99, 100, 1),
            Bar(start + timedelta(minutes=15), 100, 101, 99, 100, 1),
        ]
        result = TamukaiBacktester(self.metadata, TamukaiConfig()).run(bars)
        self.assertEqual(2, result.bars)
        with self.assertRaisesRegex(ValueError, "30分足"):
            TamukaiBacktester(
                self.metadata, TamukaiConfig(entry_minutes=30)
            ).run(bars)

    def test_dmi_identifies_a_strong_directional_move(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar(
                start + timedelta(hours=4 * index),
                100 + index,
                102 + index,
                99 + index,
                101 + index,
                1,
            )
            for index in range(40)
        ]

        plus_di, minus_di, adx = _dmi(bars)

        self.assertIsNotNone(adx[-1])
        self.assertGreater(adx[-1] or 0.0, 20.0)
        self.assertGreater(plus_di[-1] or 0.0, minus_di[-1] or 0.0)

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

        engine = TamukaiBacktester(
            self.metadata,
            TamukaiConfig(require_breakout_close=False),
            lots=1,
            initial_capital=100,
        )
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

        config = TamukaiConfig(
            first_target_r=0.5,
            first_target_fraction=1.0,
            require_breakout_close=False,
        )
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

        config = TamukaiConfig(entry_hours=(1,), require_breakout_close=False)
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

    def test_false_breakout_filter_rejects_wick_only_break(self) -> None:
        from forextester_backtest.models import Bar

        engine = TamukaiBacktester(self.metadata, lots=1, initial_capital=100)
        engine._armed = _ArmedOrder(1, 0, 100, 90, 100, 90)
        wick_only = Bar(datetime(2024, 1, 1), 95, 105, 94, 99, 1)

        engine._process_execution(wick_only)

        self.assertIsNone(engine._position)
        self.assertIsNotNone(engine._armed)
        assert engine._armed is not None
        self.assertFalse(engine._armed.breakout_confirmed)

    def test_false_breakout_filter_enters_next_bar_after_close_confirmation(self) -> None:
        from forextester_backtest.models import Bar

        engine = TamukaiBacktester(self.metadata, lots=1, initial_capital=100)
        engine._armed = _ArmedOrder(1, 0, 100, 90, 100, 90)
        confirmation = Bar(datetime(2024, 1, 1), 95, 105, 94, 101, 1)
        next_bar = Bar(datetime(2024, 1, 1, 0, 15), 102, 103, 101, 102, 1)

        engine._process_execution(confirmation)
        self.assertIsNone(engine._position)
        assert engine._armed is not None
        self.assertTrue(engine._armed.breakout_confirmed)

        engine._process_execution(next_bar)

        self.assertIsNotNone(engine._position)
        assert engine._position is not None
        self.assertEqual(next_bar.time, engine._position.entry_time)
        self.assertEqual(102, engine._position.entry_chart_price)

    def test_false_breakout_filter_cancels_entry_if_next_open_crosses_stop(self) -> None:
        from forextester_backtest.models import Bar

        engine = TamukaiBacktester(self.metadata, lots=1, initial_capital=100)
        engine._armed = _ArmedOrder(1, 0, 100, 90, 100, 90, True)
        gap_below_stop = Bar(datetime(2024, 1, 1), 89, 95, 88, 94, 1)

        engine._process_execution(gap_below_stop)

        self.assertIsNone(engine._position)
        self.assertIsNone(engine._armed)


if __name__ == "__main__":
    unittest.main()
