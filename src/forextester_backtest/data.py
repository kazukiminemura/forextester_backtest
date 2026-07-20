from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator

from .models import Bar, DataSummary, InstrumentMetadata, Tick

OLE_EPOCH = datetime(1899, 12, 30)
BAR_STRUCT = struct.Struct("<6d")
TICK_STRUCT = struct.Struct("<3dI")
COUNT_STRUCT = struct.Struct("<I")


class HistoryFormatError(ValueError):
    """Raised when a Forex Tester history file has an unexpected layout."""


def _to_datetime(value: float) -> datetime:
    return OLE_EPOCH + timedelta(days=value)


def _to_ole(value: datetime) -> float:
    return (value - OLE_EPOCH).total_seconds() / 86_400


def parse_timeframe(value: str) -> timedelta:
    value = value.strip().lower()
    units = {"m": 60, "h": 3_600, "d": 86_400}
    if len(value) < 2 or value[-1] not in units:
        raise ValueError("timeframe は 1m, 5m, 1h, 1d の形式で指定してください")
    try:
        amount = int(value[:-1])
    except ValueError as exc:
        raise ValueError("timeframe の数値が不正です") from exc
    if amount <= 0:
        raise ValueError("timeframe は1以上にしてください")
    return timedelta(seconds=amount * units[value[-1]])


@dataclass(frozen=True, slots=True)
class _RecordFile:
    path: Path
    record_size: int

    def count(self) -> int:
        size = self.path.stat().st_size
        if size < 4 or (size - 4) % self.record_size:
            raise HistoryFormatError(f"固定長レコードとして読めません: {self.path}")
        slots = (size - 4) // self.record_size
        with self.path.open("rb") as stream:
            header = COUNT_STRUCT.unpack(stream.read(4))[0]
            if 0 < header <= slots:
                return header
            if slots == 0 or self._timestamp(stream, 0) == 0:
                return 0
            # Some partially imported Bars.dat files have a zero header. Records
            # still occupy a non-zero prefix, so find that prefix safely.
            low, high = 0, slots
            while low < high:
                mid = (low + high) // 2
                if self._timestamp(stream, mid) != 0:
                    low = mid + 1
                else:
                    high = mid
            return low

    def _timestamp(self, stream: BinaryIO, index: int) -> float:
        stream.seek(4 + index * self.record_size)
        raw = stream.read(8)
        return struct.unpack("<d", raw)[0] if len(raw) == 8 else 0.0

    def first_at_or_after(
        self, stream: BinaryIO, count: int, value: datetime | None
    ) -> int:
        if value is None:
            return 0
        target = _to_ole(value)
        low, high = 0, count
        while low < high:
            mid = (low + high) // 2
            if self._timestamp(stream, mid) < target:
                low = mid + 1
            else:
                high = mid
        return low

    def edge_times(self, count: int) -> tuple[datetime | None, datetime | None]:
        if count == 0:
            return None, None
        with self.path.open("rb") as stream:
            return (
                _to_datetime(self._timestamp(stream, 0)),
                _to_datetime(self._timestamp(stream, count - 1)),
            )


class HistoryRepository:
    """Read-only access to one Forex Tester History directory."""

    def __init__(self, root: str | Path = r"C:\ForexTester6\data\History") -> None:
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"Historyディレクトリがありません: {self.root}")

    def symbols(self) -> list[str]:
        return sorted(
            directory.name
            for directory in self.root.iterdir()
            if directory.is_dir() and (directory / "info.dat").is_file()
        )

    def _symbol_dir(self, symbol: str) -> Path:
        requested = symbol.upper()
        matches = [item for item in self.symbols() if item.upper() == requested]
        if not matches:
            raise KeyError(f"銘柄が見つかりません: {symbol}")
        return self.root / matches[0]

    def metadata(self, symbol: str) -> InstrumentMetadata:
        directory = self._symbol_dir(symbol)
        values: dict[str, str] = {}
        with (directory / "info.dat").open("r", encoding="utf-8-sig") as stream:
            for raw_line in stream:
                line = raw_line.strip()
                if not line or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key] = value
        return InstrumentMetadata(directory.name, values)

    def summary(self, symbol: str) -> DataSummary:
        directory = self._symbol_dir(symbol)
        bars = _RecordFile(directory / "Bars.dat", BAR_STRUCT.size)
        ticks = _RecordFile(directory / "ticks.dat", TICK_STRUCT.size)
        bar_count = bars.count()
        tick_count = ticks.count()
        bar_start, bar_end = bars.edge_times(bar_count)
        tick_start, tick_end = ticks.edge_times(tick_count)
        return DataSummary(
            directory.name,
            bar_count,
            bar_start,
            bar_end,
            tick_count,
            tick_start,
            tick_end,
        )

    def bars(
        self,
        symbol: str,
        start: datetime | None = None,
        end: datetime | None = None,
        timeframe: str = "1m",
    ) -> Iterator[Bar]:
        if start and end and start > end:
            raise ValueError("start は end 以前にしてください")
        directory = self._symbol_dir(symbol)
        source = self._raw_bars(directory / "Bars.dat", start, end)
        duration = parse_timeframe(timeframe)
        if duration == timedelta(minutes=1):
            yield from source
        else:
            yield from _aggregate_bars(source, duration)

    def _raw_bars(
        self, path: Path, start: datetime | None, end: datetime | None
    ) -> Iterator[Bar]:
        records = _RecordFile(path, BAR_STRUCT.size)
        count = records.count()
        with path.open("rb", buffering=1024 * 1024) as stream:
            index = records.first_at_or_after(stream, count, start)
            stream.seek(4 + index * BAR_STRUCT.size)
            for _ in range(index, count):
                raw = stream.read(BAR_STRUCT.size)
                if len(raw) != BAR_STRUCT.size:
                    raise HistoryFormatError(f"レコード途中で終了しました: {path}")
                # Forex Tester stores prices as Open, Close, High, Low (not the
                # more common Open, High, Low, Close order).
                ole, open_, close, high, low, volume = BAR_STRUCT.unpack(raw)
                time = _to_datetime(ole)
                if end is not None and time > end:
                    break
                yield Bar(time, open_, high, low, close, volume)

    def ticks(
        self,
        symbol: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Iterator[Tick]:
        if start and end and start > end:
            raise ValueError("start は end 以前にしてください")
        path = self._symbol_dir(symbol) / "ticks.dat"
        records = _RecordFile(path, TICK_STRUCT.size)
        count = records.count()
        with path.open("rb", buffering=1024 * 1024) as stream:
            index = records.first_at_or_after(stream, count, start)
            stream.seek(4 + index * TICK_STRUCT.size)
            for _ in range(index, count):
                raw = stream.read(TICK_STRUCT.size)
                if len(raw) != TICK_STRUCT.size:
                    raise HistoryFormatError(f"レコード途中で終了しました: {path}")
                ole, bid, ask, volume = TICK_STRUCT.unpack(raw)
                time = _to_datetime(ole)
                if end is not None and time > end:
                    break
                yield Tick(time, bid, ask, volume)


def _aggregate_bars(bars: Iterable[Bar], duration: timedelta) -> Iterator[Bar]:
    seconds = int(duration.total_seconds())
    current_bucket: int | None = None
    aggregate: Bar | None = None
    for bar in bars:
        bucket = int((bar.time - OLE_EPOCH).total_seconds()) // seconds
        if current_bucket != bucket:
            if aggregate is not None:
                yield aggregate
            bucket_time = OLE_EPOCH + timedelta(seconds=bucket * seconds)
            aggregate = Bar(
                bucket_time, bar.open, bar.high, bar.low, bar.close, bar.volume
            )
            current_bucket = bucket
        else:
            assert aggregate is not None
            aggregate = Bar(
                aggregate.time,
                aggregate.open,
                max(aggregate.high, bar.high),
                min(aggregate.low, bar.low),
                bar.close,
                aggregate.volume + bar.volume,
            )
    if aggregate is not None:
        yield aggregate
