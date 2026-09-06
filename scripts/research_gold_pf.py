"""A frozen 120-candidate entry redesign, ranked on development PF only."""
import hashlib
import itertools
import json
from datetime import datetime, timedelta

import numpy as np

from forextester_backtest import HistoryRepository
from forextester_backtest.data import _aggregate_bars
from forextester_backtest.gold_signals import FAMILIES, features, signals
from research_sniper_daytrade import ROOT, PERIODS, outcome, evaluate, selected

FRAMES = (15, 30, 60)


def write_report(result):
    c = result["selected"]
    lines = ["# 金の売買ロジック変更とPF比較", "",
             f"入口を作り直し{result['search_count']}条件を検証。件数基準通過{result['eligible_count']}。選択：{c['minutes']}分足 / {c['family']} / {c['direction']} / 利確{c['target_atr']}ATR / 時間決済{c['hold_hours'] if c['hold_hours'] else '当日20時'}。", "",
             "| 決済期間 | 件数 | 勝率 | 新PF | 以前のPF | 平均R | 最大DD（R） | スプレッド2倍PF |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for (a,b),m,old,s in zip(PERIODS,result["results"],result["baseline_previous_entry"],result["doubled_spread"]):
        lines.append(f"| {a}–{b} | {m['n']} | {m['win_rate']:.2f}% | {m['pf']:.3f} | {old['pf']:.3f} | {m['mean_r']:+.4f} | {m['max_drawdown_r']:.2f} | {s['pf']:.3f} |")
    lines += ["", "2026年は7月17日まで、金の履歴は2013年5月から。以前のPFは1時間足の独自SNIPER条件・ADX25以上・TP3ATR・SL1.5ATR・4時間決済。"
              "新候補は入口に加えて時間決済も変更しているため、改善を入口だけの効果とは解釈しない。", "",
              f"採用基準：{'数値基準通過' if result['adopted'] else '未達'}。最新期間の改善はあるが、複数期間を通じてPF1.2以上にはならなかった。", "",
              "## 選ばれたロジック", "",
              "買い：EMA50がEMA200より上、EMA200が5本前より上、終値がEMA200と直前55本の最高値を上回る。売りは対称条件。"
              "現在足を55本の高安計算に含めない。確定足の次の通常足で入り、前回エントリーから最低5本を空ける。", "",
              "保存時刻06〜16時未満にエントリー。SLは1.5ATR、TPは3ATR、当日20時までに決済予定。欠損による遅延も損益に含める。"
              "Bid OHLCに設定スプレッド0.376を使い、成行は片道スプレッドの10%の不利なスリッページ。金利条件は使用していない。", "",
              "## 探索と限界", "",
              "EMA20回復、押し目後の前足高安突破、20本突破、55本突破、20本高安の突破失敗からの反転を比較。15/30/60分、両方向/買いのみ、TP1.5/3ATR、4時間/20時決済で120条件。"
              "2018年までと2019〜2022年のPFの低い方が最大になる候補を選択し、その1候補だけを後半期間で評価。件数は順に250/100/50/50以上、全4期間PF1.2以上・平均Rプラスを採用基準とした。", "",
              "後半の既存集計を既に見ており、今回も同じ期間を再利用する追加研究である。完全な未見データとは呼べない。直近のPF1.802だけを根拠に実運用向けの採用判定はしていない。"
              "最大DDは期間内で損益を0から累積したR単位の値で、実口座の資金・レバレッジ・円換算損益を表さない。", "",
              "## TradingView検証版", "",
              "[独立した検証用Pine](../scripts/tradingview/gold_breakout55_pf_candidate.pine)を追加。既存版とは別のインジケーター。Entry/TP/SL、想定コスト込みPF・勝率を表示する。"
              "全期間での採用基準未達を画面に明記。公式Pineコンパイル、TradingView上での表示と計算一致は未確認。", "",
              "1時間足の通常ローソク足で使用。時刻設定は初期値UTCであり、Forex Testerの保存時刻との一致は未確認。データ提供元、履歴の長さ、価格の種類が違えば結果も異なる。"
              "新たな足の確定時にその足の始値での仮想エントリーを集計し、実発注は行わない。アラートは直前のサイン確定時の候補であり、実約定を保証しない。", "",
              "[全結果JSON](../scripts/gold_pf_results.json) / [固定した探索条件](../scripts/gold_pf_protocol.json)", ""]
    (ROOT/"docs/gold_pf_results.md").write_text("\n".join(lines),encoding="utf-8")


def simulate(bars, indexes, sides, atr, spread, minutes, target, hours):
    rows = []
    for signal_index in indexes:
        i = signal_index+1
        trade = outcome(bars, i, int(sides[signal_index]), atr[signal_index], spread, minutes, target, hours)
        if trade is None:
            continue
        j, reward, reason, late = trade
        rows.append((i,j,bars[j].time.year,reward,25,55,0,bars[i].time.hour,late,reason == "target",spread/atr[signal_index],reason == "time"))
    return np.asarray(rows, dtype=float).reshape((-1,12))


def main():
    specification = dict(frames=FRAMES, families=FAMILIES, target_atr=(1.5,3), hold_hours=(4,None),
                         direction=("both","long"), stop_atr=1.5, entry_hours=(6,16), cooldown_bars=5,
                         selection="max minimum train/validation PF; tie validation mean R",
                         counts=(250,100,50,50), required_pf=1.2,
                         periods=PERIODS, evaluation_previously_seen=True)
    (ROOT / "scripts/gold_pf_protocol.json").write_text(json.dumps(specification,indent=2),encoding="utf-8")
    repo = HistoryRepository(r"C:\ForexTester6\data\History")
    meta = repo.metadata("XAUUSD")
    assert meta.commission_per_lot == 0
    base = list(repo.bars("XAUUSD",datetime(2009,1,1),datetime(2026,7,17,23,59,59),"5m"))
    candidates, contexts = [], {}
    for minutes in FRAMES:
        bars = list(_aggregate_bars(base,timedelta(minutes=minutes)))
        frame = features(bars)
        contexts[minutes] = (bars,frame)
        allowed = np.array([i+1 < len(bars) and b.time.year >= 2010 and
                            bars[i+1].time == b.time+timedelta(minutes=minutes) and
                            6 <= bars[i+1].time.hour < 16 for i,b in enumerate(bars)])
        for family in FAMILIES:
            sides = signals(frame,family)
            for target,hours,direction in itertools.product((1.5,3),(4,None),("both","long")):
                indexes = np.flatnonzero(allowed & (sides != 0) & ((sides == 1) if direction == "long" else True))
                rows = simulate(bars,indexes,sides,frame.atr.to_numpy(),meta.spread_price,minutes,target,hours)
                dev = evaluate({"XAUUSD":rows[rows[:,2] <= 2022]},(18,100,100,(6,16)))["periods"][:2]
                candidates.append(dict(minutes=minutes,family=family,target_atr=target,hold_hours=hours,direction=direction,
                                       train=dev[0],validation=dev[1]))
        print("FRAME_COMPLETE",minutes,flush=True)
    eligible = [c for c in candidates if c["train"]["n"] >= 250 and c["validation"]["n"] >= 100]
    if not eligible:
        raise ValueError("No candidate satisfies sample counts")
    ranking = sorted(eligible,key=lambda c:(min(c["train"]["pf"] or 0,c["validation"]["pf"] or 0),c["validation"]["mean_r"]),reverse=True)
    chosen = ranking[0]
    bars,frame = contexts[chosen["minutes"]]
    sides = signals(frame,chosen["family"])
    indexes = np.array([i for i in np.flatnonzero(sides) if i+1<len(bars) and bars[i].time.year>=2010 and
                        bars[i+1].time==bars[i].time+timedelta(minutes=chosen["minutes"]) and 6<=bars[i+1].time.hour<16 and
                        (chosen["direction"]=="both" or sides[i]==1)])
    results = []
    for spread in (meta.spread_price,meta.spread_price*2):
        rows = simulate(bars,indexes,sides,frame.atr.to_numpy(),spread,chosen["minutes"],chosen["target_atr"],chosen["hold_hours"])
        stats = evaluate({"XAUUSD":rows},(18,100,100,(6,16)))["periods"]
        admitted = selected(rows,(18,100,100,(6,16)))
        for (a,b),m in zip(PERIODS,stats):
            rewards = admitted[(admitted[:,2]>=a)&(admitted[:,2]<=b),3]
            equity = np.r_[0,rewards.cumsum()]
            m["max_drawdown_r"] = float(np.max(np.maximum.accumulate(equity)-equity))
        results.append(stats)
    gates = [m["n"]>=n and (m["pf"] or 0)>=1.2 and m["mean_r"]>0 for m,n in zip(results[0],(250,100,50,50))]
    old = json.loads((ROOT/"scripts/sniper_xauusd_daytrade_results.json").read_text(encoding="utf-8"))
    result = dict(specification=specification,search_count=len(candidates),eligible_count=len(eligible),selected=chosen,
                  results=results[0],doubled_spread=results[1],baseline_previous_entry=old["results"],
                  gates=gates,adopted=all(gates),development_top10=ranking[:10],development_candidates=candidates,
                  logic_sha256=hashlib.sha256((ROOT/"src/forextester_backtest/gold_signals.py").read_bytes()).hexdigest())
    path = ROOT/"scripts/gold_pf_results.json"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    write_report(result)
    print("RESULT_JSON",path,flush=True)
    print(json.dumps(dict(selected=chosen,results=results[0],doubled_spread=results[1],adopted=all(gates)),ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
