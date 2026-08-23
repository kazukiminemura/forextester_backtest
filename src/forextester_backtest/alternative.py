"""One-hour alternative strategy research with strict full-exit RR 1:1."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import sqrt
from typing import Iterable, Sequence

from .engine import BacktestResult
from .models import Bar, InstrumentMetadata, Trade


@dataclass(frozen=True, slots=True)
class AlternativeConfig:
    """Configuration for a distinct one-hour entry logic."""

    logic: str
    direction: str = "both"
    atr_length: int = 14
    stop_atr: float = 1.0
    channel_length: int = 24
    fast_ema: int = 20
    slow_ema: int = 100
    band_length: int = 20
    band_deviation: float = 2.0

    def __post_init__(self) -> None:
        if self.logic not in ("donchian", "ema-pullback", "bollinger-reversion"):
            raise ValueError("logic は donchian, ema-pullback, bollinger-reversion")
        if self.direction not in ("both", "long", "short"):
            raise ValueError("direction は both, long, short のいずれかです")
        for name in (
            "atr_length",
            "channel_length",
            "fast_ema",
            "slow_ema",
            "band_length",
        ):
            if getattr(self, name) <= 1:
                raise ValueError(f"{name} は2以上にしてください")
        if self.logic == "ema-pullback" and self.fast_ema >= self.slow_ema:
            raise ValueError("fast_ema は slow_ema より短くしてください")
        if self.stop_atr <= 0 or self.band_deviation <= 0:
            raise ValueError("stop_atr と band_deviation は0より大きくしてください")


@dataclass(slots=True)
class _Position:
    direction: int
    entry_time: datetime
    entry_price: float
    stop: float
    target: float
    entry_commission: float


def _ema(values: Sequence[float], length: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < length:
        return result
    value = sum(values[:length]) / length
    result[length - 1] = value
    alpha = 2.0 / (length + 1)
    for index in range(length, len(values)):
        value += alpha * (values[index] - value)
        result[index] = value
    return result


def _atr(bars: Sequence[Bar], length: int) -> list[float | None]:
    result: list[float | None] = [None] * len(bars)
    if len(bars) < length:
        return result
    true_ranges: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        true_ranges.append(
            bar.high - bar.low
            if previous_close is None
            else max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
        previous_close = bar.close
    value = sum(true_ranges[:length]) / length
    result[length - 1] = value
    for index in range(length, len(bars)):
        value = (value * (length - 1) + true_ranges[index]) / length
        result[index] = value
    return result


def _rolling_mean_std(
    values: Sequence[float], length: int
) -> tuple[list[float | None], list[float | None]]:
    means: list[float | None] = [None] * len(values)
    deviations: list[float | None] = [None] * len(values)
    total = 0.0
    total_squared = 0.0
    for index, value in enumerate(values):
        total += value
        total_squared += value * value
        if index >= length:
            old = values[index - length]
            total -= old
            total_squared -= old * old
        if index >= length - 1:
            mean = total / length
            variance = max(total_squared / length - mean * mean, 0.0)
            means[index] = mean
            deviations[index] = sqrt(variance)
    return means, deviations


def _previous_extreme(
    values: Sequence[float], length: int, maximum: bool
) -> list[float | None]:
    """Return the prior ``length``-bar extreme, excluding the current bar."""
    result: list[float | None] = [None] * len(values)
    candidates: deque[int] = deque()
    for index, value in enumerate(values):
        while candidates and candidates[0] < index - length:
            candidates.popleft()
        if candidates:
            result[index] = values[candidates[0]]
        while candidates and (
            value >= values[candidates[-1]]
            if maximum
            else value <= values[candidates[-1]]
        ):
            candidates.pop()
        candidates.append(index)
    return result


def _signals(bars: Sequence[Bar], config: AlternativeConfig) -> list[int]:
    closes = [bar.close for bar in bars]
    signals = [0] * len(bars)
    allow_long = config.direction != "short"
    allow_short = config.direction != "long"

    if config.logic == "donchian":
        upper = _previous_extreme(
            [bar.high for bar in bars], config.channel_length, True
        )
        lower = _previous_extreme(
            [bar.low for bar in bars], config.channel_length, False
        )
        trend = _ema(closes, config.slow_ema)
        for index, bar in enumerate(bars):
            if (
                index == 0
                or upper[index] is None
                or upper[index - 1] is None
                or lower[index] is None
                or lower[index - 1] is None
                or trend[index] is None
            ):
                continue
            if (
                allow_long
                and closes[index - 1] <= upper[index - 1]
                and bar.close > upper[index]
                and bar.close > trend[index]
            ):
                signals[index] = 1
            elif (
                allow_short
                and closes[index - 1] >= lower[index - 1]
                and bar.close < lower[index]
                and bar.close < trend[index]
            ):
                signals[index] = -1
        return signals

    if config.logic == "ema-pullback":
        fast = _ema(closes, config.fast_ema)
        slow = _ema(closes, config.slow_ema)
        for index in range(1, len(bars)):
            if None in (fast[index], fast[index - 1], slow[index]):
                continue
            assert fast[index] is not None and fast[index - 1] is not None
            assert slow[index] is not None
            if (
                allow_long
                and fast[index] > slow[index]
                and fast[index] > fast[index - 1]
                and closes[index - 1] <= fast[index - 1]
                and closes[index] > fast[index]
            ):
                signals[index] = 1
            elif (
                allow_short
                and fast[index] < slow[index]
                and fast[index] < fast[index - 1]
                and closes[index - 1] >= fast[index - 1]
                and closes[index] < fast[index]
            ):
                signals[index] = -1
        return signals

    mean, deviation = _rolling_mean_std(closes, config.band_length)
    for index in range(1, len(bars)):
        if None in (
            mean[index],
            mean[index - 1],
            deviation[index],
            deviation[index - 1],
        ):
            continue
        assert mean[index] is not None and mean[index - 1] is not None
        assert deviation[index] is not None and deviation[index - 1] is not None
        lower_now = mean[index] - config.band_deviation * deviation[index]
        lower_previous = mean[index - 1] - config.band_deviation * deviation[index - 1]
        upper_now = mean[index] + config.band_deviation * deviation[index]
        upper_previous = mean[index - 1] + config.band_deviation * deviation[index - 1]
        if (
            allow_long
            and closes[index - 1] < lower_previous
            and lower_now <= closes[index] < mean[index]
        ):
            signals[index] = 1
        elif (
            allow_short
            and closes[index - 1] > upper_previous
            and mean[index] < closes[index] <= upper_now
        ):
            signals[index] = -1
    return signals


class AlternativeBacktester:
    """Single-position next-bar engine for fixed one-hour, strict-RR1 research."""

    def __init__(
        self,
        metadata: InstrumentMetadata,
        config: AlternativeConfig,
        lots: float = 0.1,
        initial_capital: float = 10_000.0,
    ) -> None:
        if lots <= 0 or initial_capital <= 0:
            raise ValueError("lots と initial_capital は0より大きくしてください")
        self.metadata = metadata
        self.config = config
        self.lots = lots
        self.initial_capital = initial_capital
        self.units = lots * metadata.lot_size

    def run(
        self,
        bars: Iterable[Bar],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> BacktestResult:
        hourly = list(bars)
        if any(
            bar.time.minute != 0 or bar.time.second != 0 or bar.time.microsecond != 0
            for bar in hourly
        ):
            raise ValueError("代替戦略には1時間足を指定してください")
        if len(hourly) > 1 and not any(
            current.time - previous.time == timedelta(hours=1)
            for previous, current in zip(hourly, hourly[1:])
        ):
            raise ValueError("代替戦略には1時間足を指定してください")
        if start and end and start > end:
            raise ValueError("start は end 以前にしてください")

        signals = _signals(hourly, self.config)
        atr = _atr(hourly, self.config.atr_length)
        cash = self.initial_capital
        peak = cash
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        position: _Position | None = None
        trades: list[Trade] = []
        pending_direction = 0
        pending_risk: float | None = None
        first_time: datetime | None = None
        last_bar: Bar | None = None
        active_count = 0

        for index, bar in enumerate(hourly):
            if end is not None and bar.time > end:
                break
            active = start is None or bar.time >= start
            if not active:
                pending_direction = signals[index]
                pending_risk = (
                    atr[index] * self.config.stop_atr
                    if atr[index] is not None
                    else None
                )
                continue
            if first_time is None:
                first_time = bar.time
            last_bar = bar
            active_count += 1

            if position is None and pending_direction and pending_risk:
                position, cash = self._enter(pending_direction, pending_risk, bar, cash)
            pending_direction = 0
            pending_risk = None

            if position is not None:
                exit_price = self._exit_price(position, bar)
                if exit_price is not None:
                    cash, trade = self._close(position, exit_price, bar.time, cash)
                    trades.append(trade)
                    position = None

            equity = cash + self._unrealized(position, bar.close)
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100)

            if position is None and signals[index] and atr[index] is not None:
                pending_direction = signals[index]
                pending_risk = atr[index] * self.config.stop_atr

        if last_bar is not None and position is not None:
            actual_exit = (
                last_bar.close
                if position.direction == 1
                else last_bar.close + self.metadata.spread_price
            )
            cash, trade = self._close(position, actual_exit, last_bar.time, cash)
            trades.append(trade)
            peak = max(peak, cash)
            drawdown = peak - cash
            max_drawdown = max(max_drawdown, drawdown)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100)

        gains = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)
        losses = sum(trade.net_pnl for trade in trades if trade.net_pnl < 0)
        wins = sum(trade.net_pnl > 0 for trade in trades)
        net = cash - self.initial_capital
        return BacktestResult(
            symbol=self.metadata.symbol,
            pnl_currency=self.metadata.pnl_currency,
            start=first_time,
            end=last_bar.time if last_bar else None,
            bars=active_count,
            initial_capital=self.initial_capital,
            final_equity=cash,
            net_profit=net,
            return_pct=net / self.initial_capital * 100,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            trade_count=len(trades),
            winning_trades=wins,
            losing_trades=sum(trade.net_pnl < 0 for trade in trades),
            win_rate_pct=wins / len(trades) * 100 if trades else 0.0,
            gross_profit=gains,
            gross_loss=losses,
            profit_factor=gains / abs(losses) if losses else None,
            trades=tuple(trades),
        )

    def _enter(
        self, direction: int, risk: float, bar: Bar, cash: float
    ) -> tuple[_Position, float]:
        entry = bar.open + self.metadata.spread_price if direction == 1 else bar.open
        commission = self.metadata.commission_per_lot * self.lots
        return (
            _Position(
                direction=direction,
                entry_time=bar.time,
                entry_price=entry,
                stop=entry - direction * risk,
                target=entry + direction * risk,
                entry_commission=commission,
            ),
            cash - commission,
        )

    def _exit_price(self, position: _Position, bar: Bar) -> float | None:
        if position.direction == 1:
            if bar.low <= position.stop:
                return min(bar.open, position.stop)
            if bar.high >= position.target:
                return max(bar.open, position.target)
            return None
        ask_open = bar.open + self.metadata.spread_price
        ask_high = bar.high + self.metadata.spread_price
        ask_low = bar.low + self.metadata.spread_price
        if ask_high >= position.stop:
            return max(ask_open, position.stop)
        if ask_low <= position.target:
            return min(ask_open, position.target)
        return None

    def _close(
        self,
        position: _Position,
        exit_price: float,
        time: datetime,
        cash: float,
    ) -> tuple[float, Trade]:
        gross = position.direction * (exit_price - position.entry_price) * self.units
        exit_commission = self.metadata.commission_per_lot * self.lots
        net = gross - position.entry_commission - exit_commission
        cash += gross - exit_commission
        return cash, Trade(
            direction="long" if position.direction == 1 else "short",
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=time,
            exit_price=exit_price,
            lots=self.lots,
            units=self.units,
            gross_pnl=gross,
            commission=position.entry_commission + exit_commission,
            net_pnl=net,
            initial_stop=position.stop,
            first_target=position.target,
            first_target_reached=(
                exit_price >= position.target
                if position.direction == 1
                else exit_price <= position.target
            ),
        )

    def _unrealized(self, position: _Position | None, bid_close: float) -> float:
        if position is None:
            return 0.0
        actual_exit = (
            bid_close
            if position.direction == 1
            else bid_close + self.metadata.spread_price
        )
        return position.direction * (actual_exit - position.entry_price) * self.units
