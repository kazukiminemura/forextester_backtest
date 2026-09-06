"""Choose a single-instrument filter using development years only."""
import argparse
import hashlib
import json

import numpy as np

from research_sniper_daytrade import FRAMES, OUT, PERIODS, ROOT, RULES, SOURCE, evaluate


def run(symbol):
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    previous = json.loads((ROOT / "scripts/sniper_daytrade_results.json").read_text(encoding="utf-8"))
    if source_hash != previous["source_sha256"]:
        raise ValueError("Pine changed; regenerate the daytrade data before reuse")
    candidates, data, hashes = [], {}, {}
    for minutes in FRAMES:
        path = OUT / f"{symbol}_{minutes}.npz"
        hashes[str(minutes)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path) as cache:
            rows = cache["rows"]
        if not np.isfinite(rows).all():
            raise ValueError("Non-finite cached observation")
        data[minutes] = {symbol: rows}
        development = {symbol: rows[rows[:, 2] <= 2022]}
        for rule in RULES:
            train, validation = evaluate(development, rule)["periods"][:2]
            # Fixed single-symbol sample gates, declared before evaluating later years.
            if train["n"] >= 250 and validation["n"] >= 100:
                candidates.append(dict(minutes=minutes, rule=rule, train=train, validation=validation))
    profitable = [c for c in candidates if all((c[k]["pf"] or 0) >= 1.2 and c[k]["mean_r"] > 0 for k in ("train", "validation"))]
    ranked = sorted(profitable or candidates,
                    key=lambda c: (min(c["train"]["win_rate"], c["validation"]["win_rate"]), c["validation"]["mean_r"]), reverse=True)
    if not ranked:
        raise ValueError("No candidate passed the declared sample counts")
    chosen = ranked[0]
    final = evaluate(data[chosen["minutes"]], chosen["rule"])["periods"]
    baseline = evaluate(data[chosen["minutes"]], (18, 100, 100, (6, 16)))["periods"]
    gates = [m["n"] >= n and (m["win_rate"] or 0) >= 68 and (m["pf"] or 0) >= 1.2 and m["mean_r"] > 0
             for m, n in zip(final, (250, 100, 50, 50))]
    result = dict(symbol=symbol, source_sha256=source_hash, cache_sha256=hashes,
                  search_count=len(FRAMES)*len(RULES), eligible_count=len(candidates),
                  profitable_development_count=len(profitable), selected=chosen, periods=PERIODS,
                  results=final, baseline_same_timeframe=baseline, gates=gates, adopted=all(gates),
                  development_top10=ranked[:10],
                  limitations="Reuses prior audited cache. Later aggregate results were previously inspected; not pristine unseen data. Fixed spread, assumed slippage, no live fills.")
    stem = f"sniper_{symbol.lower()}_daytrade"
    path = ROOT / "scripts" / f"{stem}_results.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rule = chosen["rule"]
    lines = [f"# {symbol} 専用条件の検証", "",
             f"探索{result['search_count']}候補、件数基準通過{len(candidates)}、条件作成・選択の両期間でPF1.2以上・平均損益プラス{len(profitable)}候補。", "",
             f"選択条件：{chosen['minutes']}分足、ADX≥{rule[0]}、方向別RSI≤{rule[1]}、EMAからの方向別距離≤{rule[2]}ATR、保存時刻{rule[3][0]:02d}〜{rule[3][1]:02d}時未満。", "",
             "| 決済期間 | 件数 | 勝率 | PF | 平均R | 同時間足・追加制限なし勝率 / PF |",
             "|---|---:|---:|---:|---:|---:|"]
    for period, m, b in zip(PERIODS, final, baseline):
        lines.append(f"| {period[0]}–{period[1]} | {m['n']:,} | {m['win_rate']:.2f}% | {m['pf']:.3f} | {m['mean_r']:+.4f} | {b['win_rate']:.2f}% / {b['pf']:.3f}（{b['n']:,}件） |")
    lines += ["", "2026年は7月17日まで。XAUUSDの履歴は2013年5月開始。勝率は時間決済を含めコスト後の損益がプラスだった割合。", "",
              f"採用判定：{'数値基準通過' if all(gates) else '未達・不採用'}。Pineの売買条件は変更していない。", "",
              "2010〜2018年で条件作成、2019〜2022年で条件選択。単一銘柄の必要件数を順に250・100件とし、両期間PF1.2以上の候補を優先、両期間の勝率の低い方が最大の候補を選択。"
              "2023〜2024年と2025〜2026年は選択後に評価し、結果による選び直しはしない。採用には全4期間で勝率68%以上、PF1.2以上、平均Rプラス、後半各期間50件以上も必要。", "",
              "12銘柄共通条件から金専用条件へ探索対象を変更した追加調査。後半期間の集計は既に見ているため完全な未見データではない。"
              "金を含む既存の監査済み候補データを再利用し、そのSHA-256をJSONに保存。", "",
              "利確3ATR・損切り1.5ATR、最長4時間決済、次足始値で約定。固定スプレッドと不利な成行スリッページを含む。"
              "データ欠損による決済遅延も損益に含める。取引時刻は保存時刻であり、日本時間とは断定しない。", "",
              "[共通の執行条件・制約](sniper_daytrade_protocol.md)", ""]
    report = ROOT / "docs" / f"{stem}_results.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("RESULT_JSON " + str(path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD", choices=("XAUUSD",))
    run(parser.parse_args().symbol)
