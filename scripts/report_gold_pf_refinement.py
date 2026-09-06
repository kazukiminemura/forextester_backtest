"""Publish all phases of the PF>1 investigation without hiding failed periods."""
import json

from research_sniper_daytrade import ROOT,PERIODS


def aggregate(periods):
    # Recover gross loss from PF and net R stored by the audited study.
    loss = sum(m["total_r"]/(m["pf"]-1) for m in periods)
    net = sum(m["total_r"] for m in periods)
    return dict(n=sum(m["n"] for m in periods),pf=1+net/loss,net_r=net)


def main():
    def read(name):
        return json.loads((ROOT/"scripts"/f"{name}.json").read_text(encoding="utf-8"))

    original,refined,minute,limit = (read(n) for n in ("gold_pf_results","gold_pf_refinement_results","gold_pf_minute_results","gold_limit_results"))
    assert refined["selected"]==minute["selected"]
    assert refined["baseline_verified"] and not minute["candidate_reselected"]
    overall = dict(original_hourly=aggregate(original["results"]),refined_hourly=aggregate(refined["results"]),
                   refined_minute=aggregate(minute["minute_execution"]))
    (ROOT/"scripts/gold_pf_refinement_summary.json").write_text(json.dumps(overall,indent=2),encoding="utf-8")
    lines = ["# PF1超えを目指した金の追加改善", "",
             f"合算PF：前の55本突破版 {overall['original_hourly']['pf']:.3f} → 勢い確認版 {overall['refined_hourly']['pf']:.3f}（1時間足決済）→ {overall['refined_minute']['pf']:.3f}（1分足で到達順を監査）。"
             "各期間すべてでPF1超えという目標は未達。", "",
             "| 決済期間 | 新件数 | 勢い確認・1時間足PF | 勢い確認・1分足PF | 1分足・スプレッド2倍PF |",
             "|---|---:|---:|---:|---:|"]
    for (a,b),hour,m,s in zip(PERIODS,refined["results"],minute["minute_execution"],minute["minute_doubled_spread"]):
        lines.append(f"| {max(a, 2013)}–{b} | {m['n']} | {hour['pf']:.3f} | {m['pf']:.3f} | {s['pf']:.3f} |")
    lines += ["", "2013年5月〜2026年7月17日のXAUUSD。合算667取引。合算PFは期間PFの平均ではなく、各取引の利益・損失をR単位で合計して算出。"
              "PF1付近の期間はコストの変化に弱く、スプレッド2倍では3期間がPF1未満となった。", "",
              "## 改良したルール", "",
              "元の1時間足・EMA50/200方向一致・55本高安の終値突破に、ADX14が18以上、方向と一致するローソク足の実体が0.5ATR以上、終値が方向側の端25%以内、を追加。"
              "買いなら終値が足の上側25%、売りなら下側25%。次足始値の成行、SL1.5ATR、TP3ATR、保存時刻06〜16時エントリー・20時決済、最低5本の間隔は継続。", "",
              "## 比較した方式", "",
              f"30/60分足で、直接突破・勢い確認・最初の突破・3本/6本以内の戻し確認と、ADX下限なし/18/25を比較。出口は1R/2R、1R到達後の建値移動、半分利確、半分利確＋建値移動。計{refined['candidate_count']}条件。"
              f"件数基準通過{refined['eligible_count']}、条件作成・選択の両期間でPF1超え{refined['development_profitable_count']}。", "",
              "2018年までと2019〜2022年のPFの低い方が最大になる1候補を固定した。後半を見て再選択せず、その候補について1分足の到達順を確認。"
              f"{minute['captured_minutes']:,}本の1分足を使用し、予定エントリー時刻の欠損は{minute['missing_minute_open_signals']}件。1分足内でもTP/SL両方に触れたらSL優先。", "",
              "さらに既存2種類のサインについて、0.1/0.25/0.5ATRの戻し指値、1/2時間の有効期限、約定価格/サイン終値に固定したTP・SLの24方式を比較。"
              "未約定は勝ちに含めず、指値に触れた1分足では約定前のTPを拾わないよう、その足のTPは始値約定以外では認めない。", ""]
    if limit["selected"]:
        lines += ["指値の選択候補（開発期間から選択）は次の成績で、成行改良版より開発期間のPFが低かったため採用しなかった。", "",
                  "| 決済期間 | 指値PF | 件数 |", "|---|---:|---:|"]
        for (a,b),m in zip(PERIODS,limit["results"]["periods"]):
            lines.append(f"| {max(a, 2013)}–{b} | {m['pf']:.3f} | {m['n']} |")
        lines += ["", f"指値の全期間約定率{limit['results']['fill_rate']:.2f}%、未約定失効{limit['results']['expired']}件。指値は約定価格上限/下限を守るモデルで、成行と同じ滑りを加算していない。", ""]
    lines += ["## 判定と使用上の区別", "",
              "各期間の件数基準250/100/50/50を維持し、PF1超え・平均Rプラスを要求。成行改良版は3期間のみ通過。2019〜2022年の0.977を1へ丸めて通過扱いにはしていない。"
              "これまで何度も見た後半期間を再利用した追加研究であり、完全な未見データではない。", "",
              "[TradingView用・勢い確認版](../scripts/tradingview/gold_breakout55_pf_refined.pine)を追加した。Pineは1時間足OHLCでの集計なので、上表の1時間足列に対応する方式。"
              "1分足監査のPFをPineの実測結果として表示しない。基準時刻の初期値はUTCだが、Forex Tester保存時刻との一致は未確認。", "",
              "公式Pineコンパイル・実チャート・アラートは未確認。Pythonの因果性・約定処理と、Pineに書き出した売買条件の一致をローカルテストした。"
              "既存の直接突破版も比較用に残し、全期間で優位性を確認済みとは扱わない。", "",
              "[条件比較JSON](../scripts/gold_pf_refinement_results.json) / [1分足監査JSON](../scripts/gold_pf_minute_results.json) / [指値比較JSON](../scripts/gold_limit_results.json)", ""]
    (ROOT/"docs/gold_pf_refinement_results.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(overall,ensure_ascii=False))


if __name__=="__main__":
    main()
