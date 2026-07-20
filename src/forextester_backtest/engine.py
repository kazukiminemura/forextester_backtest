from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .models import Bar, InstrumentMetadata, Trade
from .strategies import Strategy


@dataclass(frozen=True, slots=True)
class BacktestResult:
    symbol: str
    pnl_currency: str
    start: datetime | None
    end: datetime | None
    bars: int
    initial_capital: float
    final_equity: float
    net_profit: float
    return_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    trades: tuple[Trade, ...]

    def as_dict(self, include_trades: bool = False) -> dict[str, object]:
        result: dict[str, object] = {
            "symbol": self.symbol,
            "pnl_currency": self.pnl_currency,
            "start": self.start.isoformat(sep=" ") if self.start else None,
            "end": self.end.isoformat(sep=" ") if self.end else None,
            "bars": self.bars,
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
            "net_profit": self.net_profit,
            "return_pct": self.return_pct,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "trade_count": self.trade_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": self.win_rate_pct,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
        }
        if include_trades:
            result["trades"] = [trade.as_dict() for trade in self.trades]
        return result


@dataclass(slots=True)
class _OpenPosition:
    direction: int
    entry_time: datetime
    entry_price: float
    entry_commission: float


class BacktestEngine:
    """Single-position, next-bar execution engine."""

    def __init__(
        self,
        metadata: InstrumentMetadata,
        lots: float = 0.1,
        initial_capital: float = 10_000.0,
    ) -> None:
        if lots <= 0:
            raise ValueError("lots は0より大きくしてください")
        if initial_capital <= 0:
            raise ValueError("initial_capital は0より大きくしてください")
        self.metadata = metadata
        self.lots = lots
        self.initial_capital = initial_capital
        self.units = lots * metadata.lot_size

    def run(self, bars: Iterable[Bar], strategy: Strategy) -> BacktestResult:
        cash = self.initial_capital
        position: _OpenPosition | None = None
        pending_target: int | None = None
        trades: list[Trade] = []
        first_time: datetime | None = None
        last_bar: Bar | None = None
        count = 0
        peak = cash
        max_drawdown = 0.0
        max_drawdown_pct = 0.0

        for bar in bars:
            if first_time is None:
                first_time = bar.time
            last_bar = bar
            count += 1

            if pending_target is not None:
                cash, position = self._rebalance(
                    pending_target, bar.time, bar.open, cash, position, trades
                )

            equity = cash + self._unrealized(position, bar.close)
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100)

            target = strategy.on_bar(bar)
            if target not in (-1, 0, 1):
                raise ValueError("strategy target は -1, 0, 1 のいずれかです")
            pending_target = target

        if last_bar is not None and position is not None:
            cash, position = self._rebalance(
                0, last_bar.time, last_bar.close, cash, position, trades
            )
            peak = max(peak, cash)
            max_drawdown = max(max_drawdown, peak - cash)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, (peak - cash) / peak * 100)

        net_profit = cash - self.initial_capital
        wins = [trade.net_pnl for trade in trades if trade.net_pnl > 0]
        losses = [trade.net_pnl for trade in trades if trade.net_pnl < 0]
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = gross_profit / abs(gross_loss) if gross_loss else None
        return BacktestResult(
            symbol=self.metadata.symbol,
            pnl_currency=self.metadata.pnl_currency,
            start=first_time,
            end=last_bar.time if last_bar else None,
            bars=count,
            initial_capital=self.initial_capital,
            final_equity=cash,
            net_profit=net_profit,
            return_pct=net_profit / self.initial_capital * 100,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            trade_count=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate_pct=(len(wins) / len(trades) * 100) if trades else 0.0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            trades=tuple(trades),
        )

    def _price(self, direction: int, bid_price: float) -> float:
        # Positive direction means a buy at Ask; negative means a sell at Bid.
        return bid_price + self.metadata.spread_price if direction > 0 else bid_price

    def _unrealized(self, position: _OpenPosition | None, bid_close: float) -> float:
        if position is None:
            return 0.0
        exit_price = self._price(-position.direction, bid_close)
        gross = position.direction * (exit_price - position.entry_price) * self.units
        return gross - position.entry_commission

    def _rebalance(
        self,
        target: int,
        time: datetime,
        bid_price: float,
        cash: float,
        position: _OpenPosition | None,
        trades: list[Trade],
    ) -> tuple[float, _OpenPosition | None]:
        current = position.direction if position else 0
        if target == current:
            return cash, position
        commission = self.metadata.commission_per_lot * self.lots
        if position is not None:
            exit_price = self._price(-position.direction, bid_price)
            gross = position.direction * (exit_price - position.entry_price) * self.units
            total_commission = position.entry_commission + commission
            net = gross - total_commission
            cash += net
            trades.append(
                Trade(
                    "long" if position.direction > 0 else "short",
                    position.entry_time,
                    position.entry_price,
                    time,
                    exit_price,
                    self.lots,
                    self.units,
                    gross,
                    total_commission,
                    net,
                )
            )
            position = None
        if target != 0:
            entry_price = self._price(target, bid_price)
            position = _OpenPosition(target, time, entry_price, commission)
        return cash, position
