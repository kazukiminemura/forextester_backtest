from __future__ import annotations

import struct
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from forextester_backtest.data import OLE_EPOCH, HistoryRepository
from forextester_backtest.engine import BacktestEngine
from forextester_backtest.models import InstrumentMetadata
from forextester_backtest.strategies import SmaCrossoverStrategy


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
            self.repository.ticks(
                "TESTUSD", start=datetime(2024, 1, 1, 0, 0, 1)
            )
        )
        self.assertEqual([11.0, 12.0], [tick.bid for tick in ticks])

    def test_aggregates_timeframe(self) -> None:
        bars = list(self.repository.bars("TESTUSD", timeframe="5m"))
        self.assertEqual(2, len(bars))
        self.assertEqual((10.0, 13.0, 7.0, 8.0, 50.0), (
            bars[0].open,
            bars[0].high,
            bars[0].low,
            bars[0].close,
            bars[0].volume,
        ))


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


if __name__ == "__main__":
    unittest.main()
