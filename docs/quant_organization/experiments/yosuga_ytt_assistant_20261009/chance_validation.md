# 突破候補表示の独立検証

- 担当: 独立検証。次担当: 主担当・品質監査。
- 入力: `chance_plan.md`、`scripts/tradingview/yosuga_ytt_assistant.pine`。
- 最終ソースSHA256: `0726d293005b3ab7da30e847d2a58e282ab0bceb9ff5336af824112363ee6d06`。初回レビューSHAは `dab45c16d4b6923329afeb194ea14c6f7082708ae3f9f047ca4f80b67eef7fa4`、描画修正の中間SHAは `f3b1293e4554bdfad04af70ebb036104e87ec7abf96cc75c82697a9c2653ec5d`。
- 編集範囲: 本レポートのみ。Pine・testsは編集していない。
- 判定: **未検証（公式YTTとの同一性・収益性）**。今回の補助表示仕様への静的適合確認と独立仕様検算は、下記実行結果を参照する。
- 新機能のPine実機コンパイル・描画は本担当では実行していない。主担当の別証拠と区別する。
- 実注文・Forex Tester収益バックテスト: なし。

## 読取確認

1. `candidatePriorHigh/Low` は `confirmedHigh/Low` 更新前に保存され、イベント価格とclosecrossに使われる。新ピボットと旧閾値を同足で取り違える経路は見つからなかった。
2. 2上位足の秒数がそれぞれ現足より厳密に長く、互いに異なることを要求。方向は両方+1か両方-1だけを許す。HTFは既存の全成分 `[1]` と `lookahead_on` を使う。既定H1/H4は現足H1以上で無効になり、理由を表示する。
3. イベントは確定足、未消費ピボット、前終値が閾値の手前または等値、現終値が厳密に向こう側、上位合意が必要。等値・ヒゲのみ・未確定足では成立しない。
4. `candidateHighBroken/LowBroken` は上位合意と独立して確定足で消費される。消費後に戻って再突破しても成立しない。新ピボット発生時は価格の不等比較を使わず `not na(pivotHigh/Low)` で更新するため、同値の別ピボットも新規扱いになる。監視表示はlive closeを参照せず、この確定済み消費状態と確定pivotだけを使う。
5. 候補イベントラベル20件、監視線/ラベル各1件に限定。水平線120・チャネル・手動表示を含め最大line126/label145、一時追加でもline127/label146で上限150内。新規constructorも `force_overlay=true`。左右のテーブルは別位置。

初回utilityと価格スケール修正の過去6 passedは今回追加機能の検証には流用しない。追加後の全constructor検査は個数7の固定が外れ、存在する全constructorを対象としている。

主担当が実機で検出した監視線の1ms幅の縮退に対し、1足幅へ修正した。さらに品質監査の指摘により、最終版の起点は `time_close`、終点は `time_close + (time_close - time)`、ラベルは `time_close` に統一されたことを再読確認した。新pivot確認前へ描画を戻さず、1ms縮退も回避する。方向・イベント・消費状態の条件は変更されていない。

## 独立仕様検算（Pineを実行しない参照モデル）

下記モデルはPython側で別に状態遷移を記述したもの。Pineコードを実行・変換したものではなく、`ta.pivothigh/low` の計算自体やTradingViewのrollbackを実証しない。価格は整数で比較境界を固定し、未来の高安やヒゲを成立判定へ渡さない。

```python
from itertools import product

checks = 0
def check(value):
    global checks
    assert value
    checks += 1

def gate(chart, t1, t2, directions):
    if None in (chart, t1, t2) or not (t1 > chart and t2 > chart and t1 != t2):
        return 0
    return 1 if directions == (1, 1) else -1 if directions == (-1, -1) else 0

def initial(last=99, high=100, low=90):
    return {'last': last, 'levels': {1: high, -1: low}, 'used': {1: False, -1: False}}

def step(state, close, direction, confirmed=True, new_pivots=None):
    result = {'last': state['last'], 'levels': dict(state['levels']), 'used': dict(state['used'])}
    events = []
    if confirmed:
        for side, level in state['levels'].items():
            beyond = level is not None and side * (close - level) > 0
            was_before = level is not None and state['last'] is not None and side * (state['last'] - level) <= 0
            if beyond and was_before and not state['used'][side] and direction == side:
                events.append((side, level))
            result['used'][side] = state['used'][side] or beyond
        for side, level in (new_pivots or {}).items():
            result['levels'][side] = level
            result['used'][side] = side * (close - level) > 0
        result['last'] = close
    level = result['levels'].get(direction)
    watch = (direction, level) if level is not None and not result['used'][direction] else None
    return result, events, watch

for chart,t1,t2,expected in [
    (900,3600,14400,1), (900,14400,3600,1),
    (3600,3600,14400,0), (14400,3600,14400,0),
    (900,3600,3600,0), (900,300,14400,0), (None,3600,14400,0),
]:
    check(gate(chart,t1,t2,(1,1)) == expected)
for directions in product((1,-1,0,None), repeat=2):
    expected = 1 if directions == (1,1) else -1 if directions == (-1,-1) else 0
    check(gate(900,3600,14400,directions) == expected)

for side, before, level, beyond in [(1,99,100,101),(-1,91,90,89)]:
    state = initial(last=before)
    r, events, watch = step(state,beyond,side)
    check(events == [(side,level)] and watch is None and r['used'][side])
    r, events, watch = step(state,level,side)
    check(events == [] and watch == (side,level) and not r['used'][side])
    # Wick can be beyond; close remains before the threshold.
    r, events, watch = step(state,before,side)
    check(events == [] and watch == (side,level))
    r, events, watch = step(state,beyond,side,confirmed=False)
    check(r == state and events == [] and watch == (side,level))
    # Non-aligned break consumes the pivot without an event.
    r, events, watch = step(state,beyond,0)
    check(events == [] and watch is None and r['used'][side])
    r, events, watch = step(r,before,side)
    check(events == [] and watch is None)
    r, events, watch = step(r,beyond,side)
    check(events == [] and watch is None)
    # A new confirmed pivot at the SAME price rearms it.
    r, events, watch = step(r,before,side,new_pivots={side: level})
    check(events == [] and watch == (side,level) and not r['used'][side])
    r, events, watch = step(r,beyond,side)
    check(events == [(side,level)] and watch is None)

# Old threshold must produce the event; fresh threshold supplies the next watch.
r, events, watch = step(initial(),101,1,new_pivots={1:105})
check(events == [(1,100)] and watch == (1,105))
r, events, watch = step(initial(last=91),89,-1,new_pivots={-1:85})
check(events == [(-1,90)] and watch == (-1,85))
# First known close already beyond is consumed but is not a crossover event.
r, events, watch = step(initial(last=None),101,1)
check(events == [] and watch is None and r['used'][1])
r, events, watch = step(initial(high=None),101,1)
check(events == [] and watch is None)
print('INDEPENDENT_SPEC_CHECKS', checks, 'PASS; NOT PINE EXECUTION')
```

再現コマンド（リポジトリルート、PowerShell）:

```powershell
@'
from pathlib import Path
s = Path('docs/quant_organization/experiments/yosuga_ytt_assistant_20261009/chance_validation.md').read_text(encoding='utf-8')
code = s.split('```python\n', 1)[1].split('\n```', 1)[0]
exec(compile(code, '<independent-chance-spec>', 'exec'))
'@ | python -
```

## 実行結果と引継ぎ

1. 上記レポート内Pythonモデルを抽出して実行: `INDEPENDENT_SPEC_CHECKS 45 PASS; NOT PINE EXECUTION`、終了コード0。7つのTF境界、全16方向組合せ、両方向の確定/等値/ヒゲ/未確定/消費/同値新pivot、同足pivot更新、データ不足を含む。
2. `python -m pytest tests/test_yosuga_ytt_assistant.py -q`: 中間版は9 passed in 0.04s、最終 `0726d293...6d06` は再実行して **9 passed in 0.05s、終了コード0**。すべてPineソース構造検査。独立モデル45検算とは別であり、54件のPine実行テストとは呼ばない。
3. 最終再実行と同時のSHA確認は `0726d293...6d06` に一致。レポートファイルの存在も確認済み。重大な未解決静的所見なし。

Pine実機のコンパイル・最終本文一致・右上候補価格・成立ラベル・無効TF・価格スケールを主担当が別記録する。収益採用基準・学習/検証/最終確認の取引数/PF/期待値/DDは今回の表示機能の対象外であり算出しない。費用・約定・ギャップ執行・同一足TP/SL順序の新検証はない。アラート作成・通知受信は別工程。
