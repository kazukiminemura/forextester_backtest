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
from .engine import BacktestResult
from .models import Bar, Tick, Trade
from .presets import resolve_preset
from .tamukai import TamukaiBacktester, TamukaiConfig


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


def _hours(value: str) -> tuple[int, ...]:
    try:
        hours = tuple(sorted({int(item.strip()) for item in value.split(",")}))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "時間帯は 3,6,8,9 のように指定してください"
        ) from exc
    if not hours or any(hour < 0 or hour > 23 for hour in hours):
        raise argparse.ArgumentTypeError("時間帯は0から23で指定してください")
    return hours


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

    backtest = commands.add_parser(
        "backtest", help="田向式 4Hダウ＋1H押し目レンジをバックテスト"
    )
    backtest.add_argument("symbol")
    _add_range(backtest)
    backtest.add_argument(
        "--preset",
        choices=(
            "auto",
            "pine",
            "jpy-cross",
            "eurusd-research",
            "usd-cross",
            "usdjpy-70",
        ),
        default="auto",
        help="autoはJPYクロスとEURUSD専用の探索済み設定を使用",
    )
    backtest.add_argument("--lots", type=float, default=0.1)
    backtest.add_argument("--initial-capital", type=float, default=10_000.0)
    backtest.add_argument("--higher-hours", type=int, default=4)
    backtest.add_argument("--htf-sma", type=int, default=21)
    backtest.add_argument("--htf-pivot-left", type=int, default=2)
    backtest.add_argument("--htf-pivot-right", type=int, default=2)
    backtest.add_argument("--slope-bars", type=int, default=2)
    backtest.add_argument("--min-slope-atr", type=float, default=0.03)
    backtest.add_argument("--ltf-sma", type=int, default=21)
    backtest.add_argument("--range-bars", type=int, default=3)
    backtest.add_argument("--pullback-lookback", type=int, default=12)
    backtest.add_argument("--min-pullback-atr", type=float, default=0.50)
    backtest.add_argument("--max-range-atr", type=float)
    backtest.add_argument("--zone-tolerance-atr", type=float, default=0.25)
    backtest.add_argument("--ltf-pivot-left", type=int, default=2)
    backtest.add_argument("--ltf-pivot-right", type=int, default=2)
    backtest.add_argument("--entry-buffer-pips", type=float, default=4.0)
    backtest.add_argument("--stop-buffer-pips", type=float, default=4.0)
    backtest.add_argument("--min-room-r", type=float, default=1.5)
    backtest.add_argument("--max-risk-pips", type=float, default=80.0)
    backtest.add_argument("--max-risk-atr", type=float, default=2.5)
    backtest.add_argument("--max-chase-atr", type=float, default=2.0)
    backtest.add_argument("--order-expiry-bars", type=int, default=8)
    backtest.add_argument("--min-range-atr", type=float, default=0.0)
    backtest.add_argument("--target-r", type=float)
    backtest.add_argument("--target-fraction", type=float)
    backtest.add_argument("--move-stop-to-breakeven", action="store_true")
    backtest.add_argument("--direction", choices=("both", "long", "short"))
    backtest.add_argument(
        "--entry-hours",
        type=_hours,
        help="新規約定を許可するデータ時間（例: 3,6,8,9）",
    )
    backtest.add_argument(
        "--disable-entries",
        action="store_true",
        help="全期間の新規エントリーを停止",
    )
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
    stream = (
        output.open("w", encoding="utf-8-sig", newline="") if output else sys.stdout
    )
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


def _write_trades(
    path: Path, trades: Sequence[Trade], symbol: str, preset_name: str
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = list(Trade.__dataclass_fields__)
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["symbol", "preset", *fields])
        for trade in trades:
            writer.writerow([symbol, preset_name, *_csv_values(trade, fields)])


def _print_result(result: BacktestResult, preset_name: str | None = None) -> None:
    if preset_name:
        print(f"{'Preset':20} {preset_name}")
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
                            key: (
                                _format_time(value)
                                if isinstance(value, datetime)
                                else value
                            )
                            for key, value in asdict(summary).items()
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "bars":
            _write_rows(
                repository.bars(args.symbol, args.start, args.end, args.timeframe),
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
            preset = resolve_preset(metadata.symbol, args.preset)
            if preset.validation == "recent OOS failed":
                print(
                    "warning: EURUSD research preset failed recent OOS validation "
                    "(2023-2024 expectancy < 0)",
                    file=sys.stderr,
                )
            config = TamukaiConfig(
                higher_hours=args.higher_hours,
                htf_sma_length=args.htf_sma,
                htf_pivot_left=args.htf_pivot_left,
                htf_pivot_right=args.htf_pivot_right,
                htf_slope_bars=args.slope_bars,
                min_slope_atr=args.min_slope_atr,
                ltf_sma_length=args.ltf_sma,
                range_bars=args.range_bars,
                pullback_lookback=args.pullback_lookback,
                min_pullback_atr=args.min_pullback_atr,
                max_range_atr=(
                    args.max_range_atr
                    if args.max_range_atr is not None
                    else preset.max_range_atr
                ),
                zone_tolerance_atr=args.zone_tolerance_atr,
                ltf_pivot_left=args.ltf_pivot_left,
                ltf_pivot_right=args.ltf_pivot_right,
                entry_buffer_pips=args.entry_buffer_pips,
                stop_buffer_pips=args.stop_buffer_pips,
                min_room_r=args.min_room_r,
                max_risk_pips=args.max_risk_pips,
                max_risk_atr=args.max_risk_atr,
                max_chase_atr=args.max_chase_atr,
                order_expiry_bars=args.order_expiry_bars,
                allow_entries=not args.disable_entries,
                min_range_atr=args.min_range_atr,
                first_target_r=(
                    args.target_r
                    if args.target_r is not None
                    else preset.first_target_r
                ),
                first_target_fraction=(
                    args.target_fraction
                    if args.target_fraction is not None
                    else preset.first_target_fraction
                ),
                move_stop_to_break_even=args.move_stop_to_breakeven,
                direction=args.direction or preset.direction,
                entry_hours=args.entry_hours,
            )
            engine = TamukaiBacktester(
                metadata, config, args.lots, args.initial_capital
            )
            # Read the earlier 1H history as indicator/pivot warm-up. The
            # engine only permits orders inside the requested date range.
            result = engine.run(
                repository.bars(args.symbol, None, args.end, "1h"),
                start=args.start,
                end=args.end,
            )
            if args.json:
                print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            else:
                _print_result(result, preset.name)
            if args.trades_output:
                _write_trades(
                    args.trades_output, result.trades, metadata.symbol, preset.name
                )
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
