from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque

from .models import Bar


class Strategy(ABC):
    """A strategy returns a desired position: -1 short, 0 flat, 1 long."""

    @abstractmethod
    def on_bar(self, bar: Bar) -> int:
        raise NotImplementedError


class SmaCrossoverStrategy(Strategy):
    """Long above the slow SMA and short below it after an SMA crossover."""

    def __init__(self, fast_period: int = 20, slow_period: int = 50) -> None:
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("SMA期間は1以上にしてください")
        if fast_period >= slow_period:
            raise ValueError("fast_period は slow_period より小さくしてください")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self._fast: deque[float] = deque()
        self._slow: deque[float] = deque()
        self._fast_sum = 0.0
        self._slow_sum = 0.0

    def on_bar(self, bar: Bar) -> int:
        self._fast.append(bar.close)
        self._slow.append(bar.close)
        self._fast_sum += bar.close
        self._slow_sum += bar.close
        if len(self._fast) > self.fast_period:
            self._fast_sum -= self._fast.popleft()
        if len(self._slow) > self.slow_period:
            self._slow_sum -= self._slow.popleft()
        if len(self._slow) < self.slow_period:
            return 0
        fast = self._fast_sum / self.fast_period
        slow = self._slow_sum / self.slow_period
        if fast > slow:
            return 1
        if fast < slow:
            return -1
        return 0
