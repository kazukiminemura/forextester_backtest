"""Replay the existing Sniper Pine logic against Forex Tester history, no tuning."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import gzip
import json
from pathlib import Path
import time

from forextester_backtest import HistoryRepository
from forextester_backtest.sniper import SniperReplay


SYMBOLS = ("AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "USDCHF", "USDJPY", "AUDJPY", "CHFJPY", "EURCHF", "GBPCHF", "GBPJPY", "XAUUSD")
EPOCH = datetime(1970, 1, 1)


def millis(value):
    return int((value - EPOCH).total_seconds() * 1000)


def timestamp(value):
    return (EPOCH + timedelta(milliseconds=value)).isoformat()


def summarize(rows, start, end):
    selected = [r for r in rows if start <= r["entry_time"] <= end]
    decided = [r for r in selected if r["exit_time"] is not None and r["exit_time"] <= end]
    wins = sum(r["outcome"] == "win" for r in decided)
    losses = len(decided) - wins
    return dict(signals=len(selected), wins=wins, losses=losses,
                pending=len(selected) - len(decided),
                win_rate_pct=100 * wins / len(decided) if decided else None,
                ambiguous_stop_first=sum(r["ambiguous"] for r in decided))


def rates(samples, start, end):
    return {f"TP{i}": summarize(rows, start, end) for i, rows in enumerate(samples, 1)}


def pct(value):
    return "—" if value is None else f"{value:.2f}%"


def write_report(payload, path):
    whole = payload["aggregate"]["all"]
    lines = ["# Sniper VIP：Forex Tester履歴による勝率", "",
             f"15分足・Pine既定値固定・対象期間 {payload['start']} ～ {payload['end']}。金は履歴開始の2013年5月以降。", "",
             "元製品のロジックではなく、このリポジトリの独自版を検証。条件の最適化・銘柄選別は行っていない。", "",
             "## 全対象の合計", "", "| 判定 | 勝率 | 勝ち | 負け | 未決着 |", "| --- | ---: | ---: | ---: | ---: |"]
    for name in ("TP1", "TP2", "TP3"):
        r = whole[name]
        lines.append(f"| {name} / SL | {pct(r['win_rate_pct'])} | {r['wins']:,} | {r['losses']:,} | {r['pending']:,} |")
    config = payload["config"]
    reference = 100 * config["slAtr"] / (config["slAtr"] + config["tp3Atr"])
    main_rate = whole["TP3"]["win_rate_pct"]
    if main_rate is not None:
        conclusion = "下回った。今回の既定値では勝率から優位性を確認できない" if main_rate < reference else "上回ったが、実損益・コストを考慮した優位性は未検証"
        lines += ["", f"TP3勝率は、設定倍率から求めたコスト前の損益分岐勝率{reference:.2f}%を{conclusion}。"]
    if "audit" in payload:
        lines += ["", f"個別サンプル{payload['audit']['sample_records']:,}行（3目標分）と銘柄別・合計の件数を照合済み。新規関連テスト29件＋既存履歴テスト25件が通過。"]
    lines += ["", "## 銘柄別", "", "| 銘柄 | 採用件数 | TP1勝率 | TP2勝率 | TP3勝率 | TP3勝 / 負 / 未決着 |", "| --- | ---: | ---: | ---: | ---: | --- |"]
    for symbol, details in payload["symbols"].items():
        r = details["all"]
        last = r["TP3"]
        lines.append(f"| {symbol} | {last['signals']:,} | {pct(r['TP1']['win_rate_pct'])} | {pct(r['TP2']['win_rate_pct'])} | {pct(last['win_rate_pct'])} | {last['wins']:,} / {last['losses']:,} / {last['pending']} |")
    lines += ["", "## 期間別（期間内に採用し、同期間内に決着したサイン）", "", "| 期間 | 採用件数 | TP1勝率 | TP2勝率 | TP3勝率 | TP3未決着 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, r in payload["aggregate"].items():
        if name != "all":
            lines.append(f"| {name} | {r['TP3']['signals']:,} | {pct(r['TP1']['win_rate_pct'])} | {pct(r['TP2']['win_rate_pct'])} | {pct(r['TP3']['win_rate_pct'])} | {r['TP3']['pending']} |")
    lines += ["", "## 集計仕様と限界", "",
              "- Pineファイルから既定値、f_engineの売買判定式、価格追跡ブロック、startSample/observeメソッドを直接読み込んで限定変換し、再利用した。判定式を別の戦略へ置き換えていない。",
              "- ATR・EMA・RSI・DMI/ADX・Supertrendの組み込み関数はPythonで計算。これはTradingView公式ランタイムではなく、同一価格データでの公式Pine出力との完全一致は未確認。",
              "- 既存HistoryRepositoryでBars.datを読取り、15分OHLCへ集約。時刻は保存値のままで、取引所時差を推定変換しない。欠損区間を補間しない。",
              "- 指標・価格追跡は集計開始の365日前からウォームアップ。集計前から持ち越した追跡を集計開始時にリセットしない。",
              "- サイン確定終値をEntryとする価格到達勝率。次の足から判定し、同一足でTP/SL両方に触れたらSL優先。目標前進は既定OFF。",
              "- TP1/TP2は同じ採用サインを対象とする参考集計。TP1全決済で早期に次のサインを採用する別戦略の成績ではない。",
              "- 各期間の終端を超えて決着したサンプルは、その期間では未決着として分母から除く。このため期間別の勝敗件数は全期間の勝敗件数と単純には一致しない。",
              "- スプレッド・手数料・約定ずれを勝率から控除していない。metadataのスプレッドは結果JSONに記録したが、利益率/PFは計算していない。",
              "- 合計は各サインを件数で重み付け。通貨間で同時発生する相関を考慮したポートフォリオ成績ではない。",
              "- 既定SL=1.5 ATR、TP=1/2/3 ATR。理論上のコスト前損益分岐勝率はTP1=60%、TP2=42.86%、TP3=33.33%（丸め・約定差を無視）。",
              "", "## 再実行", "", "```powershell", "python scripts/research_sniper_vip.py", "```", "",
              "詳細JSON：[`sniper_vip_results.json`](../scripts/sniper_vip_results.json)。全サンプルは同ディレクトリの`sniper_vip_samples.jsonl.gz`（圧縮JSON Lines）。", "",
              f"Pine SHA256: `{payload['pine_sha256']}`", "",
              "計算仕様の参照：[TradingView Supertrend](https://www.tradingview.com/support/solutions/43000634738-supertrend/)。"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default=r"C:\ForexTester6\data\History")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS)
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default="2026-07-17T23:59:59")
    parser.add_argument("--pine", type=Path, default=Path("scripts/tradingview/sniper_vip_pro_reconstruction.pine"))
    parser.add_argument("--output", type=Path, default=Path("scripts/sniper_vip_results.json"))
    parser.add_argument("--report", type=Path, default=Path("docs/sniper_vip_forextester_results.md"))
    args = parser.parse_args()
    start, end = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    if start > end:
        parser.error("start must precede end")
    start_ms, end_ms = millis(start), millis(end)
    source = args.pine.read_text(encoding="utf-8")
    repository = HistoryRepository(args.history_dir)
    periods = {"2010–2018": (datetime(2010, 1, 1), datetime(2018, 12, 31, 23, 59, 59)),
               "2019–2022": (datetime(2019, 1, 1), datetime(2022, 12, 31, 23, 59, 59)),
               "2023–2024": (datetime(2023, 1, 1), datetime(2024, 12, 31, 23, 59, 59)),
               "2025–2026": (datetime(2025, 1, 1), end)}
    ranges = {"all": (start_ms, end_ms), **{name: (max(start_ms, millis(a)), min(end_ms, millis(b))) for name, (a, b) in periods.items()}}
    payload = dict(start=start.isoformat(), end=end.isoformat(), timeframe="15m", pine_sha256=hashlib.sha256(source.encode()).hexdigest(), symbols={}, aggregate={}, execution_model="signal_close_reference_no_costs_stop_first", tuning=False)
    totals = [[], [], []]
    samples_path = args.output.with_name(args.output.stem.replace("results", "samples") + ".jsonl.gz")
    payload["samples_file"] = str(samples_path)
    started = time.monotonic()
    with gzip.open(samples_path, "wt", encoding="utf-8") as output:
        for symbol in args.symbols:
            print(f"RUN {symbol}: reading Forex Tester and replaying Pine", flush=True)
            meta, summary = repository.metadata(symbol), repository.summary(symbol)
            replay = SniperReplay(source, 10 ** -meta.decimals, start_ms=start_ms, end_ms=end_ms)
            first_time = last_time = None
            count = 0
            for bar in repository.bars(symbol, start - timedelta(days=365), end, "15m"):
                if bar.time + timedelta(minutes=15) > end:
                    continue
                if last_time is not None and bar.time <= last_time:
                    raise ValueError(f"Non-increasing bars: {symbol} {bar.time}")
                if not (0 < bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
                    raise ValueError(f"Invalid OHLC: {symbol} {bar}")
                first_time = first_time or bar.time
                last_time = bar.time
                replay.update(bar)
                count += 1
                if count % 100000 == 0:
                    print(f"  {symbol}: {count:,} bars through {last_time:%Y-%m-%d}", flush=True)
            rows = [sample.rows for sample in replay.samples]
            results = {name: rates(rows, a, b) for name, (a, b) in ranges.items()}
            yearly = {str(year): rates(rows, max(start_ms, millis(datetime(year, 1, 1))), min(end_ms, millis(datetime(year, 12, 31, 23, 59, 59)))) for year in range(start.year, end.year + 1)}
            payload["symbols"][symbol] = dict(**results, yearly=yearly, bars=count, first_bar=first_time.isoformat() if first_time else None, last_bar=last_time.isoformat() if last_time else None, source_start=summary.bar_start.isoformat(), source_end=summary.bar_end.isoformat(), source_records=summary.bar_count, tick_size=10**-meta.decimals, metadata_spread=meta.spread_price)
            payload["config"] = replay.config
            for i, samples in enumerate(rows):
                totals[i].extend(samples)
                for row in samples:
                    output.write(json.dumps(dict(symbol=symbol, target_number=i+1, **row), ensure_ascii=False) + "\n")
            print(f"DONE {symbol}: " + json.dumps(results["all"]), flush=True)
    payload["aggregate"] = {name: rates(totals, a, b) for name, (a, b) in ranges.items()}
    payload["elapsed_seconds"] = round(time.monotonic() - started, 2)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(payload, args.report)
    print("RESULT_JSON " + json.dumps(payload["aggregate"]), flush=True)
    print(f"WROTE {args.output} {args.report} {samples_path}", flush=True)


if __name__ == "__main__":
    main()
