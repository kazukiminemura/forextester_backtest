"""USDJPY M15 close/EMA50 crossover; next-open reversal, no fixed TP/SL."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from forextester_backtest.data import HistoryRepository
from forextester_backtest.engine import BacktestEngine
from forextester_backtest.strategies import Strategy


class Ema50Cross(Strategy):
    def __init__(self):
        self.ema = None
        self.previous_close = None
        self.count = 0
        self.target = 0

    def on_bar(self, bar):
        previous_ema = self.ema
        self.ema = bar.close if self.ema is None else self.ema + 2 / 51 * (bar.close - self.ema)
        self.count += 1
        # Stabilize EMA before allowing the first actual crossing.
        if self.count > 250:
            if self.previous_close <= previous_ema and bar.close > self.ema:
                self.target = 1
            elif self.previous_close >= previous_ema and bar.close < self.ema:
                self.target = -1
        self.previous_close = bar.close
        return self.target


def summarize(trades):
    profits = [t.net_pnl / t.units / 0.01 for t in trades]
    wins = sum(p > 1e-8 for p in profits)
    losses = sum(p < -1e-8 for p in profits)
    gain = sum(p for p in profits if p > 1e-8)
    loss = -sum(p for p in profits if p < -1e-8)
    return dict(trades=len(profits), wins=wins, losses=losses,
                breakevens=len(profits)-wins-losses,
                win_rate_pct=100*wins/len(profits) if profits else 0,
                profit_factor=gain/loss if loss else None,
                net_pips=sum(profits), mean_pips=sum(profits)/len(profits) if profits else 0)


def main():
    history = HistoryRepository(r"C:\ForexTester6\data\History")
    metadata = history.metadata("USDJPY")
    result = BacktestEngine(metadata).run(history.bars("USDJPY", timeframe="15m"), Ema50Cross())
    # Independent price arithmetic verifies the engine's cost and direction handling.
    for trade in result.trades:
        direction = 1 if trade.direction == "long" else -1
        assert abs(trade.net_pnl - (direction * (trade.exit_price-trade.entry_price)*trade.units-trade.commission)) < 1e-6
        assert trade.exit_time >= trade.entry_time
    report = dict(symbol="USDJPY", timeframe="15m", ema_period=50,
                  rule="Close crosses EMA50; buy above/sell below; reverse next available bar open; final position closed at final close",
                  warmup_bars=250, spread_pips=metadata.spread_price/0.01,
                  commission_per_lot_per_side=metadata.commission_per_lot,
                  swap_included=False, slippage_included=False,
                  start=str(result.start), end=str(result.end), bars=result.bars,
                  overall=summarize(result.trades),
                  by_direction={d: summarize([t for t in result.trades if t.direction == d]) for d in ("long", "short")},
                  yearly_by_exit={str(y): summarize([t for t in result.trades if t.exit_time.year == y]) for y in range(result.start.year, result.end.year+1)},
                  recent_2023_onward_by_exit=summarize([t for t in result.trades if t.exit_time.year >= 2023]))
    assert report['overall']['trades'] == sum(v['trades'] for v in report['yearly_by_exit'].values())
    output = Path(__file__).resolve().parent
    (output / "ema50_usdjpy_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (output / "ema50_usdjpy_trades.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result.trades[0].as_dict()))
        writer.writeheader()
        writer.writerows(t.as_dict() for t in result.trades)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
