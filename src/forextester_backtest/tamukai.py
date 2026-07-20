# This file is subject to the Mozilla Public License 2.0.
"""Backtester derived from tamukai_1h_pullback_range_strategy.pine.

Source:
https://github.com/kazukiminemura/chart_analyser_y/blob/main/scrips/
tamukai_1h_pullback_range_strategy.pine

The implementation keeps the trading rules while replacing TradingView's
broker emulator with an explicit OHLC-path model and Forex Tester spread.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from .engine import BacktestResult
from .models import Bar, InstrumentMetadata, Trade


@dataclass(frozen=True, slots=True)
class TamukaiConfig:
    higher_hours: int = 4
    htf_sma_length: int = 21
    htf_pivot_left: int = 2
    htf_pivot_right: int = 2
    htf_slope_bars: int = 2
    min_slope_atr: float = 0.03
    ltf_sma_length: int = 21
    range_bars: int = 3
    pullback_lookback: int = 12
    min_pullback_atr: float = 0.50
    max_range_atr: float = 1.50
    zone_tolerance_atr: float = 0.25
    ltf_pivot_left: int = 2
    ltf_pivot_right: int = 2
    entry_buffer_pips: float = 4.0
    stop_buffer_pips: float = 4.0
    min_room_r: float = 1.5
    max_risk_pips: float = 80.0
    max_risk_atr: float = 2.5
    max_chase_atr: float = 2.0
    order_expiry_bars: int = 8
    allow_entries: bool = True
    min_range_atr: float = 0.0
    first_target_r: float = 1.0
    first_target_fraction: float = 0.5
    move_stop_to_break_even: bool = False
    direction: str = "both"
    entry_hours: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        integer_fields = (
            "higher_hours",
            "htf_sma_length",
            "htf_pivot_left",
            "htf_pivot_right",
            "htf_slope_bars",
            "ltf_sma_length",
            "range_bars",
            "pullback_lookback",
            "ltf_pivot_left",
            "ltf_pivot_right",
            "order_expiry_bars",
        )
        for name in integer_fields:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} は1以上にしてください")
        if self.higher_hours > 24 or 24 % self.higher_hours:
            raise ValueError(
                "higher_hours は24の約数（1, 2, 3, 4, 6, 8, 12, 24）にしてください"
            )
        if self.range_bars < 2:
            raise ValueError("range_bars は2以上にしてください")
        non_negative = (
            "min_slope_atr",
            "min_pullback_atr",
            "zone_tolerance_atr",
            "entry_buffer_pips",
            "stop_buffer_pips",
            "max_risk_pips",
            "min_range_atr",
        )
        for name in non_negative:
            if getattr(self, name) < 0:
                raise ValueError(f"{name} は0以上にしてください")
        positive = ("max_range_atr", "min_room_r", "max_risk_atr", "max_chase_atr")
        for name in positive:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} は0より大きくしてください")
        if self.first_target_r <= 0:
            raise ValueError("first_target_r は0より大きくしてください")
        if not 0 < self.first_target_fraction <= 1:
            raise ValueError("first_target_fraction は0より大きく1以下にしてください")
        if self.min_range_atr > self.max_range_atr:
            raise ValueError("min_range_atr は max_range_atr 以下にしてください")
        if self.direction not in ("both", "long", "short"):
            raise ValueError("direction は both, long, short のいずれかです")
        if self.entry_hours is not None and any(
            hour < 0 or hour > 23 for hour in self.entry_hours
        ):
            raise ValueError("entry_hours は0から23で指定してください")


@dataclass(frozen=True, slots=True)
class _PivotState:
    last_high: float | None = None
    previous_high: float | None = None
    last_low: float | None = None
    previous_low: float | None = None


@dataclass(slots=True)
class _ArmedOrder:
    direction: int
    armed_at: int
    range_high: float
    range_low: float
    entry: float
    stop: float


@dataclass(slots=True)
class _Position:
    direction: int
    entry_time: datetime
    entry_chart_price: float
    entry_price: float
    initial_stop: float
    runner_stop: float
    first_target: float
    initial_units: float
    remaining_units: float
    commission: float
    realized_gross: float = 0.0
    exit_value: float = 0.0
    first_target_reached: bool = False


def _sma(values: Sequence[float], length: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= length:
            total -= values[index - length]
        if index >= length - 1:
            result[index] = total / length
    return result


def _atr(bars: Sequence[Bar], length: int = 14) -> list[float | None]:
    if not bars:
        return []
    true_ranges: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            value = bar.high - bar.low
        else:
            value = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        true_ranges.append(value)
        previous_close = bar.close
    result: list[float | None] = [None] * len(bars)
    if len(bars) < length:
        return result
    current = sum(true_ranges[:length]) / length
    result[length - 1] = current
    for index in range(length, len(bars)):
        current = (current * (length - 1) + true_ranges[index]) / length
        result[index] = current
    return result


def _pivot_states(bars: Sequence[Bar], left: int, right: int) -> list[_PivotState]:
    result: list[_PivotState] = []
    last_high: float | None = None
    previous_high: float | None = None
    last_low: float | None = None
    previous_low: float | None = None
    for index in range(len(bars)):
        candidate_index = index - right
        if candidate_index >= left:
            candidate = bars[candidate_index]
            left_bars = bars[candidate_index - left : candidate_index]
            right_bars = bars[candidate_index + 1 : candidate_index + right + 1]
            # Pine pivots resolve ties toward the right side. These asymmetric
            # comparisons reproduce that behavior without using future bars
            # before the right-side confirmation count has elapsed.
            is_high = all(candidate.high > item.high for item in left_bars) and all(
                candidate.high >= item.high for item in right_bars
            )
            is_low = all(candidate.low < item.low for item in left_bars) and all(
                candidate.low <= item.low for item in right_bars
            )
            if is_high:
                previous_high, last_high = last_high, candidate.high
            if is_low:
                previous_low, last_low = last_low, candidate.low
        result.append(_PivotState(last_high, previous_high, last_low, previous_low))
    return result


def _four_hour_bars(
    hourly: Sequence[Bar], higher_hours: int = 4
) -> tuple[list[Bar], list[int]]:
    higher: list[Bar] = []
    mapping: list[int] = []
    bucket: datetime | None = None
    for bar in hourly:
        bar_bucket = bar.time.replace(
            hour=bar.time.hour - bar.time.hour % higher_hours,
            minute=0,
            second=0,
            microsecond=0,
        )
        if bucket != bar_bucket:
            higher.append(
                Bar(bar_bucket, bar.open, bar.high, bar.low, bar.close, bar.volume)
            )
            bucket = bar_bucket
        else:
            previous = higher[-1]
            higher[-1] = Bar(
                previous.time,
                previous.open,
                max(previous.high, bar.high),
                min(previous.low, bar.low),
                bar.close,
                previous.volume + bar.volume,
            )
        mapping.append(len(higher) - 1)
    return higher, mapping


class TamukaiBacktester:
    """4H Dow trend plus 1H pullback-range stop-order backtester."""

    def __init__(
        self,
        metadata: InstrumentMetadata,
        config: TamukaiConfig | None = None,
        lots: float = 0.1,
        initial_capital: float = 10_000.0,
    ) -> None:
        if lots <= 0:
            raise ValueError("lots は0より大きくしてください")
        if initial_capital <= 0:
            raise ValueError("initial_capital は0より大きくしてください")
        self.metadata = metadata
        self.config = config or TamukaiConfig()
        self.lots = lots
        self.initial_capital = initial_capital
        self.units = lots * metadata.lot_size
        self.min_tick = 10 ** (-metadata.decimals)
        plain = metadata.symbol.lstrip("#")
        self.pip_size = (
            self.min_tick * 10 if len(plain) == 6 and plain.isalpha() else self.min_tick
        )
        self.entry_buffer = self.config.entry_buffer_pips * self.pip_size
        self.stop_buffer = self.config.stop_buffer_pips * self.pip_size
        self._cash = initial_capital
        self._armed: _ArmedOrder | None = None
        self._position: _Position | None = None
        self._trades: list[Trade] = []

    def run(
        self,
        bars: Iterable[Bar],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> BacktestResult:
        self._cash = self.initial_capital
        self._armed = None
        self._position = None
        self._trades = []
        hourly = list(bars)
        if not hourly:
            return self._result(None, None, 0, 0.0, 0.0)
        if any(
            bar.time.minute != 0 or bar.time.second != 0 or bar.time.microsecond != 0
            for bar in hourly
        ):
            raise ValueError("田向式戦略には1時間足を指定してください")
        if start and end and start > end:
            raise ValueError("start は end 以前にしてください")

        higher, higher_map = _four_hour_bars(hourly, self.config.higher_hours)
        htf_closes = [bar.close for bar in higher]
        htf_sma = _sma(htf_closes, self.config.htf_sma_length)
        htf_atr = _atr(higher)
        htf_pivots = _pivot_states(
            higher, self.config.htf_pivot_left, self.config.htf_pivot_right
        )
        ltf_closes = [bar.close for bar in hourly]
        ltf_sma = _sma(ltf_closes, self.config.ltf_sma_length)
        ltf_atr = _atr(hourly)
        ltf_pivots = _pivot_states(
            hourly, self.config.ltf_pivot_left, self.config.ltf_pivot_right
        )

        first_time: datetime | None = None
        last_bar: Bar | None = None
        active_count = 0
        peak = self.initial_capital
        max_drawdown = 0.0
        max_drawdown_pct = 0.0

        for index, bar in enumerate(hourly):
            if end is not None and bar.time > end:
                break
            active = start is None or bar.time >= start
            if not active:
                continue
            if first_time is None:
                first_time = bar.time
            last_bar = bar
            active_count += 1

            htf_index = higher_map[index] - 1
            bias = self._higher_bias(htf_index, higher, htf_sma, htf_atr, htf_pivots)
            closed_this_bar = self._process_execution(bar, ltf_pivots[index])
            self._update_runner(bar.close, ltf_pivots[index])

            if self._position is None and not closed_this_bar:
                self._update_pending_and_setup(
                    index,
                    bar,
                    hourly,
                    ltf_sma[index],
                    ltf_atr[index],
                    bias,
                )

            equity = self._cash + self._unrealized(bar.close)
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100)

        if last_bar is not None and self._position is not None:
            self._exit_units(
                last_bar.close,
                self._position.remaining_units,
                last_bar.time,
            )
            peak = max(peak, self._cash)
            drawdown = peak - self._cash
            max_drawdown = max(max_drawdown, drawdown)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, drawdown / peak * 100)

        return self._result(
            first_time,
            last_bar.time if last_bar else None,
            active_count,
            max_drawdown,
            max_drawdown_pct,
        )

    def _higher_bias(
        self,
        index: int,
        bars: Sequence[Bar],
        sma: Sequence[float | None],
        atr: Sequence[float | None],
        pivots: Sequence[_PivotState],
    ) -> tuple[bool, bool, bool, bool, _PivotState] | None:
        past_index = index - self.config.htf_slope_bars
        if (
            index < 0
            or past_index < 0
            or sma[index] is None
            or sma[past_index] is None
            or atr[index] is None
        ):
            return None
        pivot = pivots[index]
        if None in (
            pivot.last_high,
            pivot.previous_high,
            pivot.last_low,
            pivot.previous_low,
        ):
            return None
        assert pivot.last_high is not None and pivot.previous_high is not None
        assert pivot.last_low is not None and pivot.previous_low is not None
        assert (
            sma[index] is not None
            and sma[past_index] is not None
            and atr[index] is not None
        )
        uptrend = (
            pivot.last_high > pivot.previous_high
            and pivot.last_low > pivot.previous_low
        )
        downtrend = (
            pivot.last_high < pivot.previous_high
            and pivot.last_low < pivot.previous_low
        )
        slope = sma[index] - sma[past_index]
        threshold = atr[index] * self.config.min_slope_atr
        long_bias = uptrend and bars[index].close > sma[index] and slope > threshold
        short_bias = downtrend and bars[index].close < sma[index] and slope < -threshold
        long_chase = (
            bars[index].close - sma[index] <= atr[index] * self.config.max_chase_atr
        )
        short_chase = (
            sma[index] - bars[index].close <= atr[index] * self.config.max_chase_atr
        )
        return long_bias, short_bias, long_chase, short_chase, pivot

    def _update_pending_and_setup(
        self,
        index: int,
        bar: Bar,
        bars: Sequence[Bar],
        ltf_sma: float | None,
        ltf_atr: float | None,
        bias: tuple[bool, bool, bool, bool, _PivotState] | None,
    ) -> None:
        long_bias = short_bias = long_chase = short_chase = False
        if bias is not None:
            long_bias, short_bias, long_chase, short_chase, _ = bias
        if self._armed is not None:
            expired = index - self._armed.armed_at > self.config.order_expiry_bars
            invalid = (
                self._armed.direction == 1
                and (
                    not long_bias
                    or not long_chase
                    or bar.low < self._armed.range_low
                    or expired
                    or not self.config.allow_entries
                )
            ) or (
                self._armed.direction == -1
                and (
                    not short_bias
                    or not short_chase
                    or bar.high > self._armed.range_high
                    or expired
                    or not self.config.allow_entries
                )
            )
            if invalid:
                self._armed = None
        if (
            self._armed is not None
            or bias is None
            or ltf_sma is None
            or ltf_atr is None
            or not self.config.allow_entries
        ):
            return
        setup = self._setup(index, bar, bars, ltf_sma, ltf_atr, bias)
        if setup is not None:
            self._armed = setup

    def _setup(
        self,
        index: int,
        bar: Bar,
        bars: Sequence[Bar],
        ltf_sma: float,
        ltf_atr: float,
        bias: tuple[bool, bool, bool, bool, _PivotState],
    ) -> _ArmedOrder | None:
        config = self.config
        if index < config.range_bars + config.pullback_lookback:
            return None
        range_items = bars[index - config.range_bars : index]
        impulse_items = bars[
            index - config.range_bars - config.pullback_lookback : index
            - config.range_bars
        ]
        range_high = max(item.high for item in range_items)
        range_low = min(item.low for item in range_items)
        common_high = min(item.high for item in range_items)
        common_low = max(item.low for item in range_items)
        range_width = range_high - range_low
        compact = (
            common_high >= common_low
            and range_width > self.min_tick
            and range_width >= ltf_atr * config.min_range_atr
            and range_width <= ltf_atr * config.max_range_atr
        )
        if not compact:
            return None
        impulse_high = max(item.high for item in impulse_items)
        impulse_low = min(item.low for item in impulse_items)
        long_pullback = (
            impulse_high - range_low >= ltf_atr * config.min_pullback_atr
            and range_high < impulse_high
        )
        short_pullback = (
            range_high - impulse_low >= ltf_atr * config.min_pullback_atr
            and range_low > impulse_low
        )
        long_bias, short_bias, long_chase, short_chase, pivot = bias
        tolerance = ltf_atr * config.zone_tolerance_atr
        long_reference = self._in_zone(
            ltf_sma, range_low, range_high, tolerance
        ) or self._in_zone(pivot.previous_high, range_low, range_high, tolerance)
        short_reference = self._in_zone(
            ltf_sma, range_low, range_high, tolerance
        ) or self._in_zone(pivot.previous_low, range_low, range_high, tolerance)
        long_entry = range_high + self.entry_buffer
        long_stop = range_low - self.stop_buffer
        short_entry = range_low - self.entry_buffer
        short_stop = range_high + self.stop_buffer
        long_risk = long_entry - long_stop
        short_risk = short_stop - short_entry
        long_risk_ok = self._risk_ok(long_risk, ltf_atr)
        short_risk_ok = self._risk_ok(short_risk, ltf_atr)
        upper_wall = self._nearest_above(
            long_entry, pivot.last_high, pivot.previous_high
        )
        lower_wall = self._nearest_below(
            short_entry, pivot.last_low, pivot.previous_low
        )
        long_room_ok = (
            upper_wall is None
            or (upper_wall - long_entry) / long_risk >= config.min_room_r
        )
        short_room_ok = (
            lower_wall is None
            or (short_entry - lower_wall) / short_risk >= config.min_room_r
        )

        if (
            config.direction != "short"
            and long_bias
            and long_chase
            and long_pullback
            and long_reference
            and pivot.last_low is not None
            and range_low > pivot.last_low
            and long_risk_ok
            and long_room_ok
            and bar.high < long_entry
        ):
            return _ArmedOrder(1, index, range_high, range_low, long_entry, long_stop)
        if (
            config.direction != "long"
            and short_bias
            and short_chase
            and short_pullback
            and short_reference
            and pivot.last_high is not None
            and range_high < pivot.last_high
            and short_risk_ok
            and short_room_ok
            and bar.low > short_entry
        ):
            return _ArmedOrder(
                -1, index, range_high, range_low, short_entry, short_stop
            )
        return None

    def _risk_ok(self, risk: float, atr: float) -> bool:
        return (
            risk > self.min_tick
            and risk <= atr * self.config.max_risk_atr
            and (
                self.config.max_risk_pips == 0
                or risk / self.pip_size <= self.config.max_risk_pips
            )
        )

    @staticmethod
    def _in_zone(
        level: float | None, low: float, high: float, tolerance: float
    ) -> bool:
        return level is not None and low - tolerance <= level <= high + tolerance

    @staticmethod
    def _nearest_above(price: float, *levels: float | None) -> float | None:
        candidates = [level for level in levels if level is not None and level > price]
        return min(candidates) if candidates else None

    @staticmethod
    def _nearest_below(price: float, *levels: float | None) -> float | None:
        candidates = [level for level in levels if level is not None and level < price]
        return max(candidates) if candidates else None

    def _process_execution(self, bar: Bar, pivot: _PivotState | None = None) -> bool:
        pivot = pivot or _PivotState()
        allow_entry = self._hour_allowed(bar.time.hour)
        closed = False
        if self._position is not None:
            closed = self._process_position_gap(bar.open, bar.time)
            self._update_runner(bar.close, pivot)
        if (
            self._position is None
            and not closed
            and self._armed is not None
            and allow_entry
        ):
            if self._armed.direction == 1 and bar.open >= self._armed.entry:
                self._enter(max(bar.open, self._armed.entry), bar.time)
            elif self._armed.direction == -1 and bar.open <= self._armed.entry:
                self._enter(min(bar.open, self._armed.entry), bar.time)

        if abs(bar.open - bar.high) <= abs(bar.open - bar.low):
            path = (bar.open, bar.high, bar.low, bar.close)
        else:
            path = (bar.open, bar.low, bar.high, bar.close)
        for start, end in zip(path, path[1:]):
            if self._process_segment(
                start, end, bar.time, bar.close, pivot, allow_entry
            ):
                closed = True
        return closed

    def _process_position_gap(self, price: float, time: datetime) -> bool:
        position = self._position
        assert position is not None
        if position.direction == 1:
            if price <= position.runner_stop:
                self._exit_units(price, position.remaining_units, time)
                return True
            if not position.first_target_reached and price >= position.first_target:
                position.first_target_reached = True
                self._exit_units(
                    price,
                    position.initial_units * self.config.first_target_fraction,
                    time,
                )
        else:
            if price >= position.runner_stop:
                self._exit_units(price, position.remaining_units, time)
                return True
            if not position.first_target_reached and price <= position.first_target:
                position.first_target_reached = True
                self._exit_units(
                    price,
                    position.initial_units * self.config.first_target_fraction,
                    time,
                )
        return self._position is None

    def _process_segment(
        self,
        start: float,
        end: float,
        time: datetime,
        close: float | None = None,
        pivot: _PivotState | None = None,
        allow_entry: bool = True,
    ) -> bool:
        pivot = pivot or _PivotState()
        close = end if close is None else close
        cursor = start
        for _ in range(4):
            if self._position is None:
                if self._armed is None or not allow_entry:
                    return False
                if self._armed.direction == 1 and end >= self._armed.entry > cursor:
                    cursor = self._armed.entry
                    self._enter(cursor, time)
                    continue
                if self._armed.direction == -1 and end <= self._armed.entry < cursor:
                    cursor = self._armed.entry
                    self._enter(cursor, time)
                    continue
                return False

            position = self._position
            if position.direction == 1:
                if end <= position.runner_stop < cursor:
                    self._exit_units(
                        position.runner_stop, position.remaining_units, time
                    )
                    return True
                if (
                    not position.first_target_reached
                    and end >= position.first_target > cursor
                ):
                    cursor = position.first_target
                    position.first_target_reached = True
                    self._exit_units(
                        cursor,
                        position.initial_units * self.config.first_target_fraction,
                        time,
                    )
                    if self._position is None:
                        return True
                    self._update_runner(close, pivot)
                    continue
            else:
                if end >= position.runner_stop > cursor:
                    self._exit_units(
                        position.runner_stop, position.remaining_units, time
                    )
                    return True
                if (
                    not position.first_target_reached
                    and end <= position.first_target < cursor
                ):
                    cursor = position.first_target
                    position.first_target_reached = True
                    self._exit_units(
                        cursor,
                        position.initial_units * self.config.first_target_fraction,
                        time,
                    )
                    if self._position is None:
                        return True
                    self._update_runner(close, pivot)
                    continue
            return False
        return self._position is None

    def _enter(self, chart_price: float, time: datetime) -> None:
        armed = self._armed
        assert armed is not None
        actual_price = (
            chart_price + self.metadata.spread_price
            if armed.direction == 1
            else chart_price
        )
        risk = (
            chart_price - armed.stop
            if armed.direction == 1
            else armed.stop - chart_price
        )
        commission = self.metadata.commission_per_lot * self.lots
        self._cash -= commission
        self._position = _Position(
            direction=armed.direction,
            entry_time=time,
            entry_chart_price=chart_price,
            entry_price=actual_price,
            initial_stop=armed.stop,
            runner_stop=armed.stop,
            first_target=(
                chart_price + armed.direction * risk * self.config.first_target_r
            ),
            initial_units=self.units,
            remaining_units=self.units,
            commission=commission,
        )
        self._armed = None

    def _exit_units(self, chart_price: float, units: float, time: datetime) -> None:
        position = self._position
        assert position is not None
        units = min(units, position.remaining_units)
        actual_price = (
            chart_price
            if position.direction == 1
            else chart_price + self.metadata.spread_price
        )
        gross = position.direction * (actual_price - position.entry_price) * units
        exit_lots = units / self.metadata.lot_size
        commission = self.metadata.commission_per_lot * exit_lots
        self._cash += gross - commission
        position.realized_gross += gross
        position.commission += commission
        position.exit_value += actual_price * units
        position.remaining_units -= units
        if position.remaining_units <= position.initial_units * 1e-12:
            average_exit = position.exit_value / position.initial_units
            net = position.realized_gross - position.commission
            self._trades.append(
                Trade(
                    direction="long" if position.direction == 1 else "short",
                    entry_time=position.entry_time,
                    entry_price=position.entry_price,
                    exit_time=time,
                    exit_price=average_exit,
                    lots=self.lots,
                    units=position.initial_units,
                    gross_pnl=position.realized_gross,
                    commission=position.commission,
                    net_pnl=net,
                    initial_stop=position.initial_stop,
                    first_target=position.first_target,
                    first_target_reached=position.first_target_reached,
                )
            )
            self._position = None
        else:
            position.first_target_reached = True

    def _update_runner(self, close: float, pivot: _PivotState) -> None:
        position = self._position
        if position is None or not position.first_target_reached:
            return
        if self.config.move_stop_to_break_even:
            if position.direction == 1:
                position.runner_stop = max(position.runner_stop, position.entry_price)
            else:
                break_even_bid = position.entry_price - self.metadata.spread_price
                position.runner_stop = min(position.runner_stop, break_even_bid)
        if position.direction == 1 and pivot.last_low is not None:
            candidate = pivot.last_low - self.stop_buffer
            if candidate > position.runner_stop and candidate < close:
                position.runner_stop = candidate
        elif position.direction == -1 and pivot.last_high is not None:
            candidate = pivot.last_high + self.stop_buffer
            if candidate < position.runner_stop and candidate > close:
                position.runner_stop = candidate

    def _hour_allowed(self, hour: int) -> bool:
        return self.config.entry_hours is None or hour in self.config.entry_hours

    def _unrealized(self, chart_close: float) -> float:
        position = self._position
        if position is None:
            return 0.0
        actual_exit = (
            chart_close
            if position.direction == 1
            else chart_close + self.metadata.spread_price
        )
        gross = (
            position.direction
            * (actual_exit - position.entry_price)
            * position.remaining_units
        )
        exit_lots = position.remaining_units / self.metadata.lot_size
        return gross - self.metadata.commission_per_lot * exit_lots

    def _result(
        self,
        start: datetime | None,
        end: datetime | None,
        bars: int,
        max_drawdown: float,
        max_drawdown_pct: float,
    ) -> BacktestResult:
        net_profit = self._cash - self.initial_capital
        wins = [trade.net_pnl for trade in self._trades if trade.net_pnl > 0]
        losses = [trade.net_pnl for trade in self._trades if trade.net_pnl < 0]
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        return BacktestResult(
            symbol=self.metadata.symbol,
            pnl_currency=self.metadata.pnl_currency,
            start=start,
            end=end,
            bars=bars,
            initial_capital=self.initial_capital,
            final_equity=self._cash,
            net_profit=net_profit,
            return_pct=net_profit / self.initial_capital * 100,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            trade_count=len(self._trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate_pct=len(wins) / len(self._trades) * 100 if self._trades else 0.0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=gross_profit / abs(gross_loss) if gross_loss else None,
            trades=tuple(self._trades),
        )
