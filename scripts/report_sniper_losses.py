"""Report original Pine losses separately from cost-aware defense experiments."""
from collections import Counter
import gzip
import hashlib
import json

from research_sniper_daytrade import ROOT, SOURCE, PERIODS


def original_diagnostics():
    first, counts, duration = {}, Counter(), Counter()
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    baseline = json.loads((ROOT/'scripts/sniper_vip_results.json').read_text(encoding='utf-8'))
    assert baseline['pine_sha256'] == source_hash
    with gzip.open(ROOT/'scripts/sniper_vip_samples.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            key = r['symbol'], r['entry_time']
            if r['target_number'] == 1 and r['outcome'] == 'win':
                first[key] = r['exit_time']
            if r['target_number'] != 3:
                continue
            counts['signals'] += 1
            counts[r['outcome'] or 'pending'] += 1
            if r['outcome'] == 'loss':
                hours = (r['exit_time']-r['entry_time'])/3_600_000
                duration['within1h' if hours <= 1 else '1to4h' if hours <= 4 else 'over4h'] += 1
                counts['tp1_won_on_prior_bar'] += int(key in first and first[key] < r['exit_time'])
    expected = baseline['aggregate']['all']['TP3']
    assert counts['win'] == expected['wins'] and counts['loss'] == expected['losses']
    result = dict(source_sha256=source_hash, timeframe='15m',
                  execution='Original Pine signal-close reference, no costs, no time exit',
                  counts=dict(counts), loss_duration=dict(duration))
    (ROOT/'scripts/sniper_original_loss_diagnostics.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    original = original_diagnostics()
    reports = {name: json.loads((ROOT/f'scripts/sniper_{name}_results.json').read_text(encoding='utf-8'))
               for name in ('loss', 'purple', 'defense')}
    c, durations = original['counts'], original['loss_duration']
    defense = reports['defense']
    names = dict(breakeven_tp1='TP1到達後、次足から建値SL', half_tp1='TP1で半分利確、残りは元のTP3/SL',
                 half_tp1_breakeven='TP1で半分利確、残りは次足から建値SL')
    lines = ['# Sniper独自再現版：負けトレード分析と抑制実験', '',
             '本家の非公開コードではなく、このリポジトリのSniper独自再現版を対象とする。金の55本突破ロジックは使用していない。', '',
             '結論：入口27条件、既存の紫色限定1条件、TP1防御3方式を調べたが、期間をまたいで採用基準を満たす対策は確認できなかった。元のPine売買条件は変更していない。防御3方式はPythonの再検証用ロジックとして保存した。', '',
             '## 元の15分足表示ロジックの負け', '',
             f"12銘柄・2010年〜2026年7月17日（金は2013年5月以降）、TP3基準の決済済み{c['win']+c['loss']:,}件、勝ち{c['win']:,}、負け{c['loss']:,}、未決済{c['pending']}件。サイン終値を基準とした価格到達の統計で、コストは含まない。", '',
             f"- 負けの{100*durations['within1h']/c['loss']:.1f}%（{durations['within1h']:,}件）は1時間以内にSLへ到達。",
             f"- 負けの{100*c['tp1_won_on_prior_bar']/c['loss']:.1f}%（{c['tp1_won_on_prior_bar']:,}件）は、前の足までにTP1へ到達してからSLへ戻った。",
             '- この内訳だけでは建値移動の効果は確定しない。建値で撤退した後にTP3へ届く勝ち取引もあるため、約定を再計算して比較する。', '',
             '## 検証方法', '',
             '前回の比較で選択済みの1時間足・12銘柄に固定。元のPineのサイン条件を使い、次の通常足始値、SL1.5ATR・TP3ATR、4時間決済、保存時刻06〜16時未満、1件保有・最低5本間隔、設定スプレッドと片道0.1スプレッドの滑りを適用。元の表示ロジックの15分足・コストなし統計とは区別する。', '',
             '条件変更後にポジションの採用順を再計算した。入口を見送ると新たに採用可能になる取引も含めた。出口変更では元々の4時間決済より5本間隔制限が長いため、今回の採用件数は基準と一致した。基準成績は前回JSONと一致。出口変更では全候補の元の損益・決済位置を元データから再計算し、一致を確認してから比較した。', '',
             '2018年までを条件作成、2019〜2022年を選択に使用。選択後は後半を見て候補を入れ替えていない。ただし後半期間はこれまで何度も参照しているため、完全な未見検証ではない。', '',
             '## 入口で避ける方法', '',
             '前半ではスプレッドがATRの10%超の取引はPF0.800、10%以下では0.911。EMAから2ATR超の取引はPF0.916、2ATR以下は0.822で、離れすぎだけを理由に除く方法は改善につながらなかった。これは基準取引の分類であり、フィルター適用後の再計算結果とは異なる。', '',
             'スプレッド/ATR上限3種類、EMA距離下限3種類、方向別RSI下限3種類の27条件を比較。件数500/200/100/100以上、基準取引数の30%以上を残し、前半は6銘柄以上の件数を確保する条件で選択。選ばれたのはEMA距離2ATR以上・方向別RSI60以上（買いRSI≥60、売りRSI≤40）。', '',
             '紫色サイン（ADX25以上・実体0.5ATR以上）は既存の固定条件として別途比較し、数値を調整していない。', '',
             '| 決済期間 | 基準PF | EMA距離＋RSI PF | 紫色限定PF |', '|---|---:|---:|---:|']
    for period, b, entry, purple in zip(PERIODS, reports['loss']['baseline'], reports['loss']['results'], reports['purple']['results']):
        lines.append(f'| {period[0]}–{period[1]} | {b["pf"]:.3f} | {entry["pf"]:.3f} | {purple["pf"]:.3f} |')
    lines += ['', '入口条件は直近のPF悪化、紫色限定は後半3期間のPF悪化があるため標準採用しない。負け件数の減少だけでは、取引を減らした効果との区別がつかない。', '',
              '## TP1到達後に守る方法', '',
              'TP1=1ATRで建値移動、半分利確、半分利確＋建値移動の3方式を固定して比較。建値SLはTP1に触れた次の足から有効とし、同じ足の安値へ遡って適用しない。半分利確は数量で加重し、1回の取引として集計する。建値撤退でもコスト後にマイナスなら負けに数える。', '',
              f"前半2期間の低い方のPFで選択：**{names[defense['selected']]}**。", '',
              '| 決済期間 | 基準→変更後の件数 | 基準→変更後のPF | 基準→変更後の負け率 | 基準→変更後の平均R | 損失合計Rの減少 |',
              '|---|---:|---:|---:|---:|---:|']
    for period, b, m in zip(PERIODS, defense['baseline'], defense['results']):
        reduction = 100*(1-m['gross_loss_r']/b['gross_loss_r'])
        lines.append(f'| {period[0]}–{period[1]} | {b["n"]:,}→{m["n"]:,} | {b["pf"]:.3f}→{m["pf"]:.3f} | {b["loss_rate"]:.2f}%→{m["loss_rate"]:.2f}% | {b["mean_r"]:+.4f}→{m["mean_r"]:+.4f} | {reduction:+.1f}% |')
    lines += ['', f"損失抑制の基準（全期間でPF・平均R改善、損失合計R減少、必要件数）：{'通過' if defense['loss_reduction_passed'] else '未達'}。全期間PF1超え：{'通過' if defense['profitable_all_periods'] else '未達'}。", '',
              '損失合計Rは各取引の初期リスクを1Rとして集計したもので、口座残高や同時保有相関を反映した金額ではない。取引数、勝ちの取り逃し、PFと平均Rを合わせて判断する。', '',
              '[入口比較JSON](../scripts/sniper_loss_results.json) / [紫色比較JSON](../scripts/sniper_purple_results.json) / [出口比較JSON](../scripts/sniper_defense_results.json)', '',
              '## 再実行', '', '```powershell', 'python scripts/research_sniper_losses.py', 'python scripts/research_sniper_purple.py',
              'python scripts/research_sniper_defense.py', 'python scripts/report_sniper_losses.py', '```', '',
              '入力は前回のsniper_daytrade_cacheとForex Tester履歴。キャッシュがない場合はresearch_sniper_daytrade.pyで先に再生成する。', '']
    (ROOT/'docs/sniper_loss_analysis.md').write_text('\n'.join(lines), encoding='utf-8')
    print('REPORT', ROOT/'docs/sniper_loss_analysis.md')


if __name__ == '__main__':
    main()
