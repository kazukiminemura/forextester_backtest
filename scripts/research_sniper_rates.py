"""Lagged daily US yield filters on existing gold intraday signals."""
import hashlib
import itertools
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.sniper import SniperReplay
from research_sniper_daytrade import OUT, PERIODS, ROOT, SOURCE, evaluate

SERIES = ("DGS2", "DGS10", "DFII10")
DATA = ROOT / "scripts/sniper_rates_data"


def lagged_features(frame, entry_dates):
    """No observation newer than entry date minus three calendar days is admitted."""
    cutoffs = pd.DatetimeIndex(entry_dates).normalize() - pd.Timedelta(days=3)
    indexes = frame.index.searchsorted(cutoffs, side="right") - 1
    output = np.full((len(indexes), 3), np.nan)
    for i, j in enumerate(indexes):
        if j >= 0 and (cutoffs[i] - frame.index[j]).days <= 7:
            output[i] = frame.iloc[j][["change1", "change5", "correlation"]].to_numpy()
    return output


def main():
    source = SOURCE.read_text(encoding="utf-8")
    old = json.loads((ROOT / "scripts/sniper_xauusd_daytrade_results.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == old["source_sha256"]
    cache = OUT / "XAUUSD_60.npz"
    assert hashlib.sha256(cache.read_bytes()).hexdigest() == old["cache_sha256"]["60"]
    rows = np.load(cache)["rows"]
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    base = list(repo.bars("XAUUSD", datetime(2009, 1, 1), datetime(2026, 7, 17, 23, 59, 59), "5m"))
    bars = list(_aggregate_bars(base, timedelta(hours=1)))
    daily = list(_aggregate_bars(base, timedelta(days=1)))
    gold = pd.Series([b.close for b in daily], index=pd.DatetimeIndex([b.time for b in daily]), name="gold")
    replay = SniperReplay(source, 10 ** -repo.metadata("XAUUSD").decimals, 60)
    edges = np.array([replay.update_signals(b) for b in bars])
    entries = rows[:, 0].astype(int)
    sides = edges[entries - 1]
    assert np.isin(sides, [-1, 1]).all()
    dates = [bars[i].time for i in entries]
    features, correlations, hashes = {}, {}, {}
    for series in SERIES:
        path = DATA / f"{series}.csv"
        hashes[series] = hashlib.sha256(path.read_bytes()).hexdigest()
        raw = pd.read_csv(path, index_col=0, parse_dates=True)
        raw[series] = pd.to_numeric(raw[series], errors="coerce")
        joint = raw.join(gold, how="inner").dropna()
        joint["return"] = joint.gold.pct_change(fill_method=None)
        joint["change1"] = joint[series].diff()
        joint["change5"] = joint[series].diff(5)
        joint["correlation"] = joint["return"].rolling(60, min_periods=60).corr(joint.change1)
        features[series] = lagged_features(joint, dates)
        correlations[series] = [float(joint.loc[(joint.index.year >= a) & (joint.index.year <= b), ["return", "change1"]].corr().iloc[0, 1]) for a, b in PERIODS]
    # Freeze 24 filters plus 2 baselines. No retuning of hours, targets or later periods.
    candidates = []
    for adx, series, days, require_corr in itertools.product((18, 25), SERIES, (1, 5), (False, True)):
        feature = features[series]
        mask = sides * feature[:, 0 if days == 1 else 1] < 0
        if require_corr:
            mask &= feature[:, 2] <= -0.2
        subset = rows[mask & (rows[:, 2] <= 2022)]
        result = evaluate({"XAUUSD": subset}, (adx, 100, 100, (6, 16)))["periods"][:2]
        candidates.append(dict(adx=adx, series=series, days=days, require_negative_correlation=require_corr,
                               train=result[0], validation=result[1]))
    # Same counts as the previous single-symbol study; do not lower them to obtain a winner.
    eligible = [c for c in candidates if c["train"]["n"] >= 250 and c["validation"]["n"] >= 100]
    profitable = [c for c in eligible if all((c[k]["pf"] or 0) >= 1.2 and c[k]["mean_r"] > 0 for k in ("train", "validation"))]
    ranked = sorted(profitable or eligible, key=lambda c: (min(c["train"]["win_rate"], c["validation"]["win_rate"]), c["validation"]["mean_r"]), reverse=True)
    # If the sample gate fails for every candidate, only report the predeclared real-yield hypothesis.
    chosen = ranked[0] if ranked else next(c for c in candidates if c["adx"] == 18 and c["series"] == "DFII10" and c["days"] == 5 and not c["require_negative_correlation"])
    feature = features[chosen["series"]]
    mask = sides * feature[:, 0 if chosen["days"] == 1 else 1] < 0
    if chosen["require_negative_correlation"]:
        mask &= feature[:, 2] <= -0.2
    final = evaluate({"XAUUSD": rows[mask]}, (chosen["adx"], 100, 100, (6, 16)))["periods"]
    baseline = evaluate({"XAUUSD": rows}, (chosen["adx"], 100, 100, (6, 16)))["periods"]
    gates = [m["n"] >= n and (m["win_rate"] or 0) >= 68 and (m["pf"] or 0) >= 1.2 and m["mean_r"] > 0 for m, n in zip(final, (250, 100, 50, 50))]
    result = dict(selected=chosen, eligible_count=len(eligible), profitable_development_count=len(profitable),
                  selection_passed=bool(ranked), results=final, baseline=baseline,
                  descriptive_daily_correlations=correlations, development_candidates=candidates,
                  gates=gates, adopted=bool(ranked) and all(gates), data_sha256=hashes,
                  cache_sha256=old["cache_sha256"]["60"], source_sha256=old["source_sha256"],
                  limitations="Daily revised FRED snapshot with 3-calendar-day lag; not release-vintage or intraday yields. Gold broker timezone unknown. Later aggregate periods previously inspected.")
    path = ROOT / "scripts/sniper_rates_results.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 金と米金利の追加検証", "", f"24条件＋2基準条件。件数基準通過{len(eligible)}、両開発期間でPF1.2以上・平均損益プラス{len(profitable)}。", "",
             f"選択候補：1時間足、ADX≥{chosen['adx']}、{chosen['series']}の{chosen['days']}観測日変化と逆方向の売買だけ。60観測日の相関≤−0.2条件：{chosen['require_negative_correlation']}。", "",
             "| 決済期間 | 件数 | 金利条件あり勝率 | PF | 同じADX・金利条件なし勝率 / PF（件数） |",
             "|---|---:|---:|---:|---:|"]
    for (a, b), m, base_result in zip(PERIODS, final, baseline):
        lines.append(f"| {a}–{b} | {m['n']} | {m['win_rate']:.2f}% | {m['pf']:.3f} | {base_result['win_rate']:.2f}% / {base_result['pf']:.3f}（{base_result['n']}） |")
    lines += ["", f"約70%目標の判定：{'数値基準通過' if result['adopted'] else '未達・不採用'}。Pineの売買条件は変更していない。", "",
              "金利低下なら買いのみ、上昇なら売りのみ。1観測日または5観測日の金利差を使用。相関条件は金の日次リターンと金利の日次変化の過去60共通観測日の相関。価格水準どうしの相関ではない。", "",
              "2018年までで条件作成、2019〜2022年で選択、2023年以降は選択後に評価。件数は順に250 / 100 / 50 / 50、各期間勝率68%以上・PF1.2以上・平均Rプラスを採用基準とし、後半を見て選び直していない。", "",
              "## 日次変化の相関（説明用・売買成績ではない）", "", "| 金利 | 2013–2018 | 2019–2022 | 2023–2024 | 2025–2026 |", "|---|---:|---:|---:|---:|"]
    for series, values in correlations.items():
        lines.append(f"| {series} | " + " | ".join(f"{v:+.3f}" for v in values) + " |")
    lines += ["", "2026年は7月17日まで。金の履歴は2013年5月開始。", "",
              "データは[FRED DGS2](https://fred.stlouisfed.org/series/DGS2)、[DGS10](https://fred.stlouisfed.org/series/DGS10)、[DFII10](https://fred.stlouisfed.org/series/DFII10)。"
              "[H.15](https://www.federalreserve.gov/releases/h15/)の公表遅延を考慮し、エントリー保存日より3暦日以上前の観測だけ利用。休日は既知の過去値を使い、基準日から7日超古い値は使わない。", "",
              "保存時刻のタイムゾーンが不明なため、日次の同期には誤差がある。取得時点の改訂後データであり、公表当時の版を再現していない。"
              "3日の遅延は改訂による先読みまで解消しない。今回扱うのは日次環境フィルターであり、リアルタイムの金利変動を使うデイトレードの検証ではない。", "",
              "[共通の執行条件](sniper_daytrade_protocol.md)：利確3ATR・損切り1.5ATR、4時間決済、設定スプレッド・仮定スリッページ込み。後半期間の既存集計は既に見ているため完全な未見データではない。", ""]
    (ROOT / "docs/sniper_rates_results.md").write_text("\n".join(lines), encoding="utf-8")
    print("RESULT_JSON", path)
    print(json.dumps(dict(selected=chosen, results=final, eligible=len(eligible)), ensure_ascii=False))


if __name__ == "__main__":
    main()
