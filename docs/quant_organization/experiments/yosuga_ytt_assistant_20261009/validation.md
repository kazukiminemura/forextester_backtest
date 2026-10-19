# 独立検証引継ぎ — よすが式分析補助

- 実験ID / 担当 / 次担当: `yosuga_ytt_assistant_20261009` / 独立検証 / 研究責任者・品質監査。
- 日付: 2026-10-09 JST。
- 判定: **未検証（収益性・公式YTTとの同一性）**。表示補助の静的レビューは修正後に重大な未解決所見なし。研究合格・実運用承認ではない。
- 入力: `plan.md` の SPEC_FROZEN_UTILITY、`scripts/tradingview/yosuga_ytt_assistant.pine`、`docs/yosuga_ytt_assistant.md`。
- 最終レビュー対象Pine SHA256: `af207f62ebebfa2d8011a67d17d8484e6dbb693d0f7f95251cdd1aac485b3079`。初回レビュー対象は `eee83ea9569f2708e90df94c269082733fc6a3cc598fd4f41a352cd0cf07fbaa`。
- この担当の変更: 本レポートだけ。Pine・採用条件・testsは変更していない。
- TradingView実機: 本担当は実行していない。責任者が別途保存する実機証拠を参照し、本レポートのローカル確認と区別する。
- 実注文: なし。

## 修正依頼と解消確認

**チャネルが描画されない小さな傾き（修正済み）。** 初版は `slope = (p2 - p1) / (t2 - t1)` を価格/msで計算し、`slope > 0` / `< 0` で方向を判定していた。EURUSDで差0.001、時間差4時間なら傾きは約6.94e-11。Pineは比較演算時にfloatを小数9桁へ丸めるため、ゼロとして判定される。

担当へ価格点 `p2 > p1` / `p2 < p1` による符号判定を依頼し、上記SHAで修正確認した。傾きそのものは描画算術にだけ残る。[Pine公式のfloat比較精度](https://www.tradingview.com/pine-script-docs/language/type-system/)を2026-10-09に参照した。Pythonの通常比較をPine比較と同一視しない。

**同じSL幅でLongとShortの数量が異なる減算誤差（修正済み）。** 責任者の実機確認でEntry=1.121、Long SL=1.120 / Short SL=1.122、同じ資金・係数に対して数量1と0.99になることを検出。Pine担当が距離を `math.round(math.abs(entry - stop) / syminfo.mintick) * syminfo.mintick` に正規化した。tick整列済みの価格差を整数tick数へ戻す方法であり、数量floorへepsilonを足して予算を超える修正ではない。最終SHAでこの変更を再読し、参照計算は両方向100ticks、距離0.001、数量1.0を確認した。実機の最終版・両方向再確認は責任者の別証拠を参照する。

最終版のその他の変更は水平線の既定保持12件（最大120は維持）、テーブル文字small、左上配置。配列保持上限・因果性・売買注文なしの確認結果は変わらない。

責任者からの検出確定時刻への線起点変更、最小数量未満の無効表示も、最終読取時に確認した。

## 静的に確認できたこと

1. HTFは `f_previousState()` の全4成分を `[1]` にして `lookahead_on` で取得。requested TFが大きい場合だけrequestし、同足は確定状態を使う。下位足は値を返さず無効表示する。未確定HTFの値を返す経路は見つからなかった。[Pine公式HTF説明](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/)。
2. ピボットの水平線追加と突破・接触判定はチャート足確定時のみ。線起点は `time_close`。既存線の検査後に新線を追加するため、検出足の過去接触を通知しない。チャネルも確認時刻から先だけに描画する。
3. 線・ラベル・方向・有効状態の4配列は同時push/shift/remove。逆順削除により連続削除時のindex飛ばしを避ける。水平線最大120、チャネル2、手動3で線125、追加直後でも126。ラベル最大124、追加直後でも125。宣言上限150の範囲内。手動配列は再描画前に削除し3件で固定。[Pine公式描画上限](https://www.tradingview.com/pine-script-docs/visuals/lines-and-boxes/)。
4. 手動Entry/SL/TPを最小tickへ丸め、正価格・方向に沿うSL/TP・1tick以上の距離・開始時刻を確認。Long/ShortのTPと実効RRの式は整合する。数量は口座通貨換算係数の明示入力を使い刻み切下げ。資金/係数ゼロ・無効scenarioでは算定せず、最小刻み未満では算定不可と表示する。
5. strategy注文、取引台帳、勝率・PFの出力はない。線接触は確定足の高安範囲内という観察であり約定ではない。スプレッドや同一足内TP/SLの順序を検証したという解釈にはならない。

## 実行確認と再現

Python標準ライブラリによる10項目の構造assertと、DecimalによるLong/Short/最小数量未満の独立参照算術を実行した。最終stdoutは `STRUCTURAL_CHECKS 10 PASS; REFERENCE_ARITHMETIC PASS; NOT PINE EXECUTION`、プロセス終了コード0。Pineのコンパイルや実行の証明ではない。

責任者が保存した `tests/test_yosuga_ytt_assistant.py` を本担当でも再実行: `python -m pytest tests/test_yosuga_ytt_assistant.py -q` → **5 passed in 0.04s、終了コード0**。この5件はソース構造検査である。テスト後もPine SHAは上記と一致し、本レポート最終ファイルの存在を確認した。

最終版 `af207f...3079` でも同コマンドを再実行し **5 passed in 0.04s、終了コード0**。手動距離の整数tick正規化guardが追加済みである。参照のみのIEEE float計算はLong差0.0009999999999998899、Short差0.001000000000000112を確認し、`floor(abs差 / 0.00001 + 0.5) * 0.00001` が双方0.001へ戻ること、予算100・係数100000・数量刻み0.01で双方数量1.0となることをassert、終了コード0。Python参照算術はPine実機証拠とは別である。

再現する最小コマンド（PowerShell、リポジトリルート）:

```powershell
@'
from pathlib import Path
from decimal import Decimal as D, ROUND_FLOOR
import hashlib
p = Path('scripts/tradingview/yosuga_ytt_assistant.pine')
s = p.read_text(encoding='utf-8')
checks = {
 'all_htf_components_offset': '[d[1], h[1], l[1], s[1]]' in s,
 'htf_request_guard': 'if timeframe.in_seconds(tf) > timeframe.in_seconds()' in s and 'lookahead=barmerge.lookahead_on' in s,
 'same_tf_confirmed': 'd := confirmedDirection' in s and 'if barstate.isconfirmed' in s,
 'confirmed_level_origin': 'line.new(time_close, price' in s,
 'bounded_levels': 'if array.size(levels) > keepLevels' in s and 'array.shift(levelActive)' in s,
 'reverse_remove': 'int i = array.size(levels) - 1' in s and 'while i >= 0' in s and 'i -= 1' in s,
 'tiny_slope_guard_fixed': 'rising and p2 > p1 and width > 0' in s and 'rising and slope > 0' not in s,
 'manual_tick_round': 'math.round_to_mintick(entryInput)' in s and 'math.round_to_mintick(stopInput)' in s,
 'qty_floor_and_invalid': 'math.floor(riskBudget / lossPerQty / quantityStep)' in s and 'quantityTooSmall' in s,
 'not_a_strategy': 'strategy(' not in s and 'strategy.entry' not in s,
}
assert all(checks.values()), checks
for side,entry,stop,target in [(1,'150','149','151'),(-1,'150','151','149')]:
    e,st = D(entry),D(stop)
    distance = abs(e-st)
    assert e+D(side)*distance == D(target)
    q=(D('1000')/(distance*D('100'))/D('1')).to_integral_value(rounding=ROUND_FLOOR)
    assert q==10 and q*distance*D('100')==1000
assert (D('1')/D('100')).to_integral_value(rounding=ROUND_FLOOR)==0
assert round(0.001/(4*60*60*1000),9)==0
print('STRUCTURAL_CHECKS', len(checks), 'PASS; REFERENCE_ARITHMETIC PASS; NOT PINE EXECUTION')
print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
'@ | python -
```

## 未確認事項・引渡し条件

- 公式YTTの内部数値ルール・ソース・同一性証拠は未取得。固定ピボットと終値突破は本実装の近似。
- 凍結済み売買戦略、データ台帳、期間・通貨別採用基準は本utilityの入力ではない。収益研究としては未検証。学習/検証/最終確認の取引数、コスト後PF、期待値、DDは算出しない。複数クオート通貨の損益合算もない。
- 未実装費用はスプレッド、手数料、スリッページ、スワップ/資金調達。数量は費用なし理論値であり、証拠金・レバレッジ・上限・ブローカー契約への適合を確認していない。
- 時刻ベースチャネルは休日の空白時間も勾配に含める。ピボット左右本数の感度・収益頑健性は未評価。手動価格の過去起点は、その時点で情報が利用可能だった証明ではない。
- 責任者へ渡してよい範囲: このSHAの静的レビュー結果と参照算術。最終ソースの実コンパイル、描画、Long/Short/無効SL/最小数量、下位足無効、リプレイでのピボット確定・HTF途中変動・突破線保持の実機証拠は別に確認する。ソースが変わった場合は変更箇所とSHAを再確認する。
