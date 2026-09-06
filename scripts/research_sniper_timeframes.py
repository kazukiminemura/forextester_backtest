"""Compare fixed Sniper Pine settings across timeframes, reusing 5m history reads."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import time

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.sniper import SniperReplay
from research_sniper_vip import SYMBOLS, millis, rates, pct


FRAMES = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def period_ranges(start, end):
    periods = {
        "all": (start, end),
        "2010–2018": (datetime(2010, 1, 1), datetime(2018, 12, 31, 23, 59, 59)),
        "2019–2022": (datetime(2019, 1, 1), datetime(2022, 12, 31, 23, 59, 59)),
        "2023–2024": (datetime(2023, 1, 1), datetime(2024, 12, 31, 23, 59, 59)),
        "2025–2026": (datetime(2025, 1, 1), end),
    }
    return {key: (max(millis(start), millis(a)), min(millis(end), millis(b))) for key, (a, b) in periods.items()}


def run_symbol(symbol, history_dir, source, start, end, frames):
    repository = HistoryRepository(history_dir)
    metadata = repository.metadata(symbol)
    summary = repository.summary(symbol)
    print(f"LOAD {symbol}", flush=True)
    # floor(floor(t / 5m) * 5m / T) == floor(t / T) for the supported T.
    # Thus OHLC is identical to direct aggregation, without six disk reads.
    base = list(repository.bars(symbol, start - timedelta(days=365), end, "5m"))
    previous_time = None
    for bar in base:
        if previous_time is not None and bar.time <= previous_time:
            raise ValueError(f"Non-increasing bars: {symbol} {bar.time}")
        if not (0 < bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            raise ValueError(f"Invalid OHLC: {symbol} {bar}")
        previous_time = bar.time
    periods = period_ranges(start, end)
    result = dict(source_start=summary.bar_start.isoformat(), source_end=summary.bar_end.isoformat(),
                  source_records=summary.bar_count, tick_size=10 ** -metadata.decimals,
                  metadata_spread=metadata.spread_price, timeframes={})
    for name in frames:
        minutes = FRAMES[name]
        duration = timedelta(minutes=minutes)
        replay = SniperReplay(source, result["tick_size"], minutes=minutes, start_ms=millis(start), end_ms=millis(end))
        bars = iter(base) if minutes == 5 else _aggregate_bars(base, duration)
        count = 0
        first = last = None
        for bar in bars:
            if bar.time + duration > end:
                continue
            first = first or bar.time
            last = bar.time
            replay.update(bar)
            count += 1
        rows = [sample.rows for sample in replay.samples]
        stats = {period: rates(rows, a, b) for period, (a, b) in periods.items()}
        for number, sample in enumerate(replay.samples, 1):
            current = stats["all"][f"TP{number}"]
            assert current["wins"] == sample.wins
            assert current["losses"] == sample.losses
            assert current["pending"] == int(sample.pendingSide != 0)
            assert current["signals"] == replay.env["sampledSignals"]
        yearly = {str(year): rates(rows, max(millis(start), millis(datetime(year, 1, 1))), min(millis(end), millis(datetime(year, 12, 31, 23, 59, 59)))) for year in range(start.year, end.year + 1)}
        result["timeframes"][name] = dict(periods=stats, yearly=yearly, bars=count,
                                          first_bar=first.isoformat() if first else None,
                                          last_bar=last.isoformat() if last else None,
                                          last_close=(last+duration).isoformat() if last else None,
                                          accounting_verified=True)
        rate_text = pct(stats['all']['TP3']['win_rate_pct']).replace("—", "n/a")
        print(f"DONE {symbol} {name}: n={stats['all']['TP3']['signals']} TP3={rate_text}", flush=True)
    return symbol, result


def aggregate(symbols, frames, ranges):
    result = {}
    for frame in frames:
        result[frame] = {}
        for period in ranges:
            result[frame][period] = {}
            for target in ("TP1", "TP2", "TP3"):
                rows = [symbol["timeframes"][frame]["periods"][period][target] for symbol in symbols.values()]
                total = {field: sum(row[field] for row in rows) for field in ("signals", "wins", "losses", "pending", "ambiguous_stop_first")}
                settled = total["wins"] + total["losses"]
                assert settled + total["pending"] == total["signals"]
                total["win_rate_pct"] = total["wins"] * 100 / settled if settled else None
                result[frame][period][target] = total
    return result


def write_report(payload, path):
    lines = ["# Sniper VIP：時間足別の勝率比較", "",
             f"11通貨ペア＋金。対象期間 {payload['start']} ～ {payload['end']}（金は2013年5月以降）。Pine既定値を全時間足で固定。", "",
             "## 全期間・全銘柄合計", "", "| 時間足 | 採用件数 | TP1勝率 | TP2勝率 | TP3勝率 | TP3 勝 / 負 / 未決着 |", "| --- | ---: | ---: | ---: | ---: | --- |"]
    for frame, periods in payload["aggregate"].items():
        row = periods["all"]
        t = row["TP3"]
        lines.append(f"| {frame} | {t['signals']:,} | {pct(row['TP1']['win_rate_pct'])} | {pct(row['TP2']['win_rate_pct'])} | {pct(t['win_rate_pct'])} | {t['wins']:,} / {t['losses']:,} / {t['pending']} |")
    lines += ["", "## TP3の期間別比較", "", "| 時間足 | 2010–2018 | 2019–2022 | 2023–2024 | 2025–2026年7月 |", "| --- | ---: | ---: | ---: | ---: |"]
    names = [name for name in next(iter(payload["aggregate"].values())) if name != "all"]
    for frame, periods in payload["aggregate"].items():
        cells = [pct(periods[name]["TP3"]["win_rate_pct"]) + f" ({periods[name]['TP3']['wins']+periods[name]['TP3']['losses']:,}件)" for name in names]
        lines.append("| " + frame + " | " + " | ".join(cells) + " |")
    lines += ["", "## TP3の銘柄別比較", "", "| 銘柄 | " + " | ".join(payload["aggregate"]) + " |", "| --- | " + " | ".join("---:" for _ in payload["aggregate"]) + " |"]
    for symbol, details in payload["symbols"].items():
        cells = [pct(details["timeframes"][frame]["periods"]["all"]["TP3"]["win_rate_pct"]) for frame in payload["aggregate"]]
        lines.append("| " + symbol + " | " + " | ".join(cells) + " |")
    lines += ["", "## 集計上の注意", "",
              "- Pineの同じ判定式・価格追跡・初期TP勝敗集計を再利用。EMA100、ATR14、SL1.5 ATR、TP1/2/3 ATR、サイン間隔5本などの本数・倍率は変更していない。時間足ごとの最適化はしていない。",
              "- 時間足を変えると、EMA100などが表す実時間の長さも変わる。上位足フィルターを追加した比較ではない。",
              "- SLより先に初期TPへ到達した割合。未決着を分母から除外。同一足TP/SLはSL優先。スプレッド・手数料・滑りは未考慮。",
              "- コスト前の理論上の損益分岐勝率はTP1=60%、TP2=42.86%、TP3=33.33%。設定倍率からの参考値で、価格丸めによる差を無視。",
              "- 高い時間足ほどOHLCの中の順番が曖昧になる。今回は時間足の高安だけでSL優先判定しており、元の1分足で約定順序を解決した比較ではない。曖昧足の件数はJSONに記録。",
              "- 4時間足・日足の区切りはForex Testerの保存時刻の0時基準。ブローカー固有の日足セッションへ変換していない。最終の確定扱いとなる足は時間足ごとに異なり、JSONのlast_closeに記録。",
              "- 上位足の方が件数が少ない。期間別は当該期間に採用し、当該期間内に決着した件数を括弧内に示す。今回比較した中の高勝率だけを根拠に採用しない。",
              "- 指標計算はPython側で補うため、TradingView公式ランタイムとの完全一致は未確認。PineファイルのSHA256を記録。",
              f"- 15分足の前回結果との一致確認: {payload['baseline_15m_verified']}。全時間足の勝敗件数と内部カウンターも照合済み。",
              "", "## 再実行", "", "```powershell", "python scripts/research_sniper_timeframes.py", "```", "",
              "[詳細JSON](../scripts/sniper_vip_timeframe_results.json)", "",
              f"Pine SHA256: `{payload['pine_sha256']}`"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS)
    parser.add_argument("--timeframes", nargs="+", choices=FRAMES, default=list(FRAMES))
    parser.add_argument("--workers", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default="2026-07-17T23:59:59")
    parser.add_argument("--output", type=Path, default=Path("scripts/sniper_vip_timeframe_results.json"))
    parser.add_argument("--report", type=Path, default=Path("docs/sniper_vip_timeframe_results.md"))
    args = parser.parse_args()
    start, end = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    if start > end:
        parser.error("start must precede end")
    source = Path("scripts/tradingview/sniper_vip_pro_reconstruction.pine").read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode()).hexdigest()
    started = time.monotonic()
    symbols = {}
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        jobs = [executor.submit(run_symbol, symbol, args.history_dir, source, start, end, args.timeframes) for symbol in args.symbols]
        for job in as_completed(jobs):
            symbol, data = job.result()
            symbols[symbol] = data
    symbols = {symbol: symbols[symbol] for symbol in args.symbols}
    baseline_verified = False
    baseline_path = Path("scripts/sniper_vip_results.json")
    if "15m" in args.timeframes and baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        if baseline["pine_sha256"] == digest and baseline["start"] == start.isoformat() and baseline["end"] == end.isoformat():
            for symbol, details in symbols.items():
                for name, row in details["timeframes"]["15m"]["periods"].items():
                    assert row == baseline["symbols"][symbol][name], (symbol, name, "15m mismatch")
                assert details["timeframes"]["15m"]["bars"] == baseline["symbols"][symbol]["bars"]
            baseline_verified = True
    payload = dict(start=start.isoformat(), end=end.isoformat(), pine_sha256=digest, symbols=symbols,
                   aggregate=aggregate(symbols, args.timeframes, period_ranges(start, end)),
                   baseline_15m_verified=baseline_verified, elapsed_seconds=round(time.monotonic()-started, 2))
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(payload, args.report)
    print("RESULT_JSON " + json.dumps({frame: rows["all"] for frame, rows in payload["aggregate"].items()}), flush=True)


if __name__ == "__main__":
    main()
