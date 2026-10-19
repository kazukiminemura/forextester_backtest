"""Export the saved deep-study summary for the read-only stock dashboard."""
import json
from pathlib import Path

from stock_dashboard import DEEP
from research_tamukai_stocks_daily import sha256

NAMES = {'trend_strength': 'トレンド強度', 'shallow_pullback': '浅い押し',
         'strong_rejection': '強い引け', 'risk_band': '信号時の値幅2–4%',
         'trend_shallow': '強度＋浅い押し', 'trend_risk': '強度＋値幅',
         'no_dow': '高安切上げなし（固定比較）', 'baseline': '初回条件（固定比較）',
         'buyhold': '買い持ち（固定比較）'}


def export():
    paths = {name: DEEP / 'results' / f'{name}.json' for name in ('training', 'validation', 'final')}
    loaded = {name: json.loads(path.read_text(encoding='utf-8')) for name, path in paths.items()}
    training, validation, final = (loaded[k] for k in ('training', 'validation', 'final'))
    candidates = []
    for candidate, name in NAMES.items():
        periods = {}
        def add(period, results, note):
            if candidate in results:
                periods[period] = dict(main=results[candidate]['main']['metrics'],
                                       stress=results[candidate]['stress']['metrics'], note=note)
        reference = candidate in ('no_dow', 'baseline', 'buyhold')
        add('training', training['results'], '固定比較・選抜外' if reference else
            '訓練通過' if candidate in training['eligible_candidates'] else '訓練基準未達')
        add('validation', validation['results'], '検証通過' if candidate in validation['eligible_candidates'] else '検証基準未達')
        add('final_confirmation', final['selected_final']['results'], '最終確認・採用は監査後')
        for period, data in final['references'].items():
            add(period, data['results'], '固定比較・選抜外')
        candidates.append(dict(candidate=candidate, name=name, periods=periods))
    result = dict(available=True, candidates=candidates,
        status='採用なし・検証期間で再現せず' if final['selected_candidate'] == 'none' else '選抜あり・監査を確認',
        intro='6仮説＋固定比較。全10銘柄・初期100万円、通常片道0.1%／費用2倍0.2%。下の初回実験とは独立。',
        note='未実施はゼロ取引ではありません。訓練不適格は後期を計算せず、固定比較の好成績を採用へ繰り上げません。全期間は既閲覧・データ品質制約あり。Jev再送なし。',
        robustness_note='独立した頑健性診断を確認中。',
        evidence_sha256={str(path.relative_to(DEEP)): sha256(path) for path in paths.values()})
    robust_path = DEEP / 'independent/robustness.json'
    if robust_path.exists():
        robust = json.loads(robust_path.read_text(encoding='utf-8'))
        group = next(row for key, row in robust['groups'].items()
                     if key.replace('\\', '/') == 'reference_continuous/main/no_dow')
        ci = group['block_bootstrap']['3']['net_pf_95ci']
        ci6 = group['block_bootstrap']['6']['net_pf_95ci']
        rate = group['cost_break_even']['one_way_rate']
        result['robustness_note'] = (
            f"固定比較『高安切上げなし』の9年連続：PFの3か月ブロック95%区間 {ci[0]:.3f}–{ci[1]:.3f}、6か月では{ci6[0]:.3f}–{ci6[1]:.3f}。"
            f"1銘柄を除く10通り中{group['leave_one_out_positive_count']}通りが黒字。"
            f"最大黒字銘柄の利益寄与 {group['concentration']['top1_positive_share']*100:.1f}%（黒字銘柄利益合計に対して）。"
            + (f"費用損益分岐は片道約{rate*100:.3f}%。" if rate is not None else '費用損益分岐は所定範囲で未定義。')
            + '既存経路の条件付き診断で、多重比較未補正。将来利益や勝率の予測ではありません。')
        result['evidence_sha256'][str(robust_path.relative_to(DEEP))] = sha256(robust_path)
    target = DEEP / 'dashboard.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(target)


if __name__ == '__main__':
    export()
