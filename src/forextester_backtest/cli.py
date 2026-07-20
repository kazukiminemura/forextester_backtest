from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Iterable, Sequence

from .data import HistoryRepository
from .engine import BacktestEngine, BacktestResult
from .models import Bar, Tick, Trade
from .strategies import SmaCrossoverStrategy


def _datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "日時は YYYY-MM-DD または YYYY-MM-DD HH:MM:SS 形式です"
        ) from exc


def _end_datetime(value: str) -> datetime:
    parsed = _datetime(value)
    if len(value.strip()) == 10:
        return parsed.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return parsed


def _add_range(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", type=_datetime, help="開始日時（含む）")
    parser.add_argument("--end", type=_end_datetime, help="終了日時（含む）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forextester-backtest",
        description="Forex Tester 6 History reader and bar backtester",
    )
    parser.add_argument(
        "--history-dir",
        default=r"C:\ForexTester6\data\History",
        help="Forex Tester Historyディレクトリ",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("symbols", help="参照可能な銘柄と期間を一覧表示")

    info = commands.add_parser("info", help="銘柄メタ情報を表示")
    info.add_argument("symbol")

    bars = commands.add_parser("bars", help="バーをCSVで表示または保存")
    bars.add_argument("symbol")
    _add_range(bars)
    bars.add_argument("--timeframe", default="1m", help="1m, 5m, 1h, 1d")
    bars.add_argument("--limit", type=int, default=1000, help="最大出力件数")
    bars.add_argument("--output", type=Path, help="CSV保存先（省略時は標準出力）")

    ticks = commands.add_parser("ticks", help="tickをCSVで表示または保存")
    ticks.add_argument("symbol")
    _add_range(ticks)
    ticks.add_argument("--limit", type=int, default=1000, help="最大出力件数")
    ticks.add_argument("--output", type=Path, help="CSV保存先（省略時は標準出力）")

    backtest = commands.add_parser("backtest", help="SMAクロスをバックテスト")
    backtest.add_argument("symbol")
    _add_range(backtest)
    backtest.add_argument("--timeframe", default="1h", help="1m, 5m, 1h, 1d")
    backtest.add_argument("--fast", type=int, default=20)
    backtest.add_argument("--slow", type=int, default=50)
    backtest.add_argument("--lots", type=float, default=0.1)
    backtest.add_argument("--initial-capital", type=float, default=10_000.0)
    backtest.add_argument("--json", action="store_true", help="結果をJSON表示")
    backtest.add_argument("--trades-output", type=Path, help="取引明細CSV保存先")
    return parser


def _format_time(value: datetime | None) -> str:
    return value.isoformat(sep=" ") if value else "-"


def _symbols(repository: HistoryRepository) -> None:
    print("symbol\tbars\tbar_start\tbar_end\tticks\ttick_start\ttick_end")
    for symbol in repository.symbols():
        summary = repository.summary(symbol)
        print(
            summary.symbol,
            summary.bar_count,
            _format_time(summary.bar_start),
            _format_time(summary.bar_end),
            summary.tick_count,
            _format_time(summary.tick_start),
            _format_time(summary.tick_end),
            sep="\t",
        )


def _write_rows(
    rows: Iterable[Bar] | Iterable[Tick],
    limit: int,
    output: Path | None,
) -> None:
    if limit <= 0:
        raise ValueError("limit は1以上にしてください")
    selected = islice(rows, limit)
    stream = output.open("w", encoding="utf-8-sig", newline="") if output else sys.stdout
    try:
        writer = csv.writer(stream, lineterminator="\n")
        first = next(selected, None)
        if first is None:
            return
        fields = list(asdict(first))
        writer.writerow(fields)
        writer.writerow(_csv_values(first, fields))
        for row in selected:
            writer.writerow(_csv_values(row, fields))
    finally:
        if output:
            stream.close()


def _csv_values(row: Bar | Tick | Trade, fields: list[str]) -> list[object]:
    return [
        value.isoformat(sep=" ") if isinstance(value, datetime) else value
        for value in (getattr(row, field) for field in fields)
    ]


def _write_trades(path: Path, trades: Sequence[Trade]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = list(Trade.__dataclass_fields__)
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        for trade in trades:
            writer.writerow(_csv_values(trade, fields))


def _print_result(result: BacktestResult) -> None:
    values = result.as_dict()
    labels = {
        "symbol": "Symbol",
        "pnl_currency": "P&L currency",
        "start": "Start",
        "end": "End",
        "bars": "Bars",
        "initial_capital": "Initial capital",
        "final_equity": "Final equity",
        "net_profit": "Net profit",
        "return_pct": "Return %",
        "max_drawdown": "Max drawdown",
        "max_drawdown_pct": "Max drawdown %",
        "trade_count": "Trades",
        "winning_trades": "Winning trades",
        "losing_trades": "Losing trades",
        "win_rate_pct": "Win rate %",
        "gross_profit": "Gross profit",
        "gross_loss": "Gross loss",
        "profit_factor": "Profit factor",
    }
    for key, label in labels.items():
        value = values[key]
        if isinstance(value, float):
            print(f"{label:20} {value:.4f}")
        else:
            print(f"{label:20} {value}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repository = HistoryRepository(args.history_dir)
        if args.command == "symbols":
            _symbols(repository)
        elif args.command == "info":
            metadata = repository.metadata(args.symbol)
            summary = repository.summary(args.symbol)
            print(
                json.dumps(
                    {
                        "symbol": metadata.symbol,
                        "metadata": metadata.values,
                        "derived": {
                            "spread_price": metadata.spread_price,
                            "lot_size": metadata.lot_size,
                            "pnl_currency": metadata.pnl_currency,
                        },
                        "data": {
                            key: (_format_time(value) if isinstance(value, datetime) else value)
                            for key, value in asdict(summary).items()
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "bars":
            _write_rows(
                repository.bars(
                    args.symbol, args.start, args.end, args.timeframe
                ),
                args.limit,
                args.output,
            )
        elif args.command == "ticks":
            _write_rows(
                repository.ticks(args.symbol, args.start, args.end),
                args.limit,
                args.output,
            )
        elif args.command == "backtest":
            metadata = repository.metadata(args.symbol)
            strategy = SmaCrossoverStrategy(args.fast, args.slow)
            engine = BacktestEngine(metadata, args.lots, args.initial_capital)
            result = engine.run(
                repository.bars(
                    args.symbol, args.start, args.end, args.timeframe
                ),
                strategy,
            )
            if args.json:
                print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            else:
                _print_result(result)
            if args.trades_output:
                _write_trades(args.trades_output, result.trades)
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
