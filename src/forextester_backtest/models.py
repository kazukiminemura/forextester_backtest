from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class Tick:
    time: datetime
    bid: float
    ask: float
    volume: int


@dataclass(frozen=True, slots=True)
class InstrumentMetadata:
    symbol: str
    values: dict[str, str]

    @property
    def decimals(self) -> int:
        return int(self.values.get("decimals", "5"))

    @property
    def spread_points(self) -> float:
        return float(self.values.get("spread", "0"))

    @property
    def spread_price(self) -> float:
        return self.spread_points * 10 ** (-self.decimals)

    @property
    def lot_size(self) -> float:
        return float(self.values.get("lot", "1"))

    @property
    def commission_per_lot(self) -> float:
        if self.values.get("ApplyCommission", "0") != "1":
            return 0.0
        return float(self.values.get("CommPerLot", "0"))

    @property
    def pnl_currency(self) -> str:
        plain = self.symbol.lstrip("#")
        if len(plain) == 6 and plain.isalpha():
            return plain[-3:].upper()
        return self.values.get("MarginCurrency", "quote currency")


@dataclass(frozen=True, slots=True)
class DataSummary:
    symbol: str
    bar_count: int
    bar_start: datetime | None
    bar_end: datetime | None
    tick_count: int
    tick_start: datetime | None
    tick_end: datetime | None


@dataclass(frozen=True, slots=True)
class Trade:
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    lots: float
    units: float
    gross_pnl: float
    commission: float
    net_pnl: float

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["entry_time"] = self.entry_time.isoformat(sep=" ")
        value["exit_time"] = self.exit_time.isoformat(sep=" ")
        return value
