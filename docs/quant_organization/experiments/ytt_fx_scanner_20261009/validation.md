# FX候補一覧 独立レビュー

更新日: 2026-10-09。担当: ytt_scanner_review。所有は本レポートのみ。実装変更なし。

## 判定

表示補助の静的レビュー: **重大な差戻し事項なし**。既存assistantとの候補判定の対応、確定値参照、通知の抑制条件を確認した。

収益戦略としての判定: **未検証**。本依頼は候補一覧の表示改善であり、新しい凍結仮説・データ台帳・利益採用基準は入力されていない。月利5%の研究合格や実運用承認を意味しない。以前の利益研究の不採用は変更しない。

TradingView実コンパイル・表示・実通知は主担当の別証拠で確認する。このレビューとPython述語検算だけからPine実行成功を主張しない。

## 入力識別子

- 計画: `docs/quant_organization/experiments/ytt_fx_scanner_20261009/plan.md`
- 新規ソース: `scripts/tradingview/yosuga_ytt_fx_scanner.pine`
- 読取時SHA256: `7095369e0e5d91c17189fb914a397fba09b9aad0817e1208dfdc0aa00250f8cd`
- 比較元: `scripts/tradingview/yosuga_ytt_assistant.pine`
- 比較元SHA256: `857a0548729c96ddba326d7b0e5d6f573e7dfad1eded603fec7dafd42ad0f1ad`

途中版EC1140…から表の行位置・時間足名を改善した709536…を読み直した。以後ソースが変わる場合は最終差分を確認して識別子を更新する。

## 読取で確認したこと

1. **候補イベントと消費済み管理**: `f_state()`の方向転換は更新前高安の厳密な終値突破で判定する。エントリー足も`h[1]`/`l[1]`と更新前のconsumedフラグを使い、イベント→消費→新ピボットで再armの順序がassistantと一致する。上位足不一致中の突破も消費し、合意後の追い掛けをイベントにしない。同価格の新ピボットでも再armする。成立時に表示するのは新ピボット価格でなく実際に突破した事前価格。
2. **確定値・銘柄文脈**: 内側の上位足要求は全3成分を1上位足前へずらし、外側のSnapshotも状態・価格文字列・上位方向2項目・確定時刻の全5成分を1判定足前へずらす。二重のoffsetは、それぞれ上位足確定と判定足確定を実現する。内側空tickerは外側の監視銘柄を継承し、チャート銘柄の上位方向を8通貨に使い回す設計ではない。価格整形も外側の監視銘柄文脈で`format.mintick`を使う。
3. **設定と不足値**: 標準チャート、チャート足≦判定足、判定足より大きく異なる2上位足を要求する。不正時は要求処理を飛ばして設定不正表示。上位方向2値と上位高安4値が揃わなければデータ不足、方向0・不一致なら見送り。無効銘柄の外側要求は`ignore_invalid_symbol=true`、naオブジェクトにはフィールド参照を行わない分岐を使う。チャート足が判定足より大きい場合に下位足を一部だけ抽出して候補とすることはない。
4. **通知と鮮度**: 通知は既定OFF。初回リアルタイム実行を抑制し、各銘柄stampの厳密増加と新成立状態3/4、リアルタイム、鮮度をすべて要求する。stamp記憶は`varip`で同じリアルタイム足内の繰り返し通知を防ぐ。8通貨を処理後に初回フラグを立てるため通貨2以降だけ初回通知になる問題もない。2判定足分を超えたデータは更新待ちへ変え、通知を抑制する。
5. **要求数と表示**: 最大8銘柄×判定足・上位2足=24文脈の要求を想定し、通常の40要求枠内。SnapshotというUDTで外側のタプル要素増加を避けている。計算は毎履歴足で行い、最終足だけで新銘柄を初要求する構造ではない。表は専用パネルに表示する。

内側文脈の継承、確定offset、UDT/要求数の確認根拠: [TradingView公式 Other timeframes and data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/)。実際のコンパイラー・データ配信の動作確認は主担当の実機検証で補う。

## 独立境界検算

Pineを実行するテストではなく、比較元とスキャナーの分岐式を読んだ上で独立Python述語により18境界を検算した。実行終了コード0、18/18 PASS、同時にソースSHAを読取り済み。

- 終値タッチだけでは不成立（買い/売り）、厳密突破で成立（買い/売り）。
- 消費済みは再成立しない（買い/売り）、同価格新ピボットで再arm（買い/売り）。
- 新ピボットでも既に反対側へ終値がある場合は消費済み維持（買い/売り）、成立価格は更新前の値。
- 初回リアルタイム・同stamp・古い成立・突破済み・前stamp不足は通知なし。新stampの買い/売り成立は通知対象。

再現はリポジトリ直下PowerShellで以下を実行する。

```powershell
@'
def event(side, prior, prev, close, consumed, pivot=None):
    s = 1 if side == 'buy' else -1
    e = not consumed and s * close > s * prior and s * prev <= s * prior
    used = consumed or s * close > s * prior
    if pivot is not None:
        used = s * close > s * pivot
    return e, used
cases = [
 ('buy',100,99,100,False,None,(False,False)),
 ('sell',100,101,100,False,None,(False,False)),
 ('buy',100,100,101,False,None,(True,True)),
 ('sell',100,100,99,False,None,(True,True)),
 ('buy',100,99,101,True,None,(False,True)),
 ('sell',100,101,99,True,None,(False,True)),
 ('buy',100,99,99,True,100,(False,False)),
 ('sell',100,101,101,True,100,(False,False)),
 ('buy',100,101,101,True,100,(False,True)),
 ('sell',100,99,99,True,100,(False,True)),
 ('buy',100,99,101,False,102,(True,False)),
]
for *args, expected in cases:
    assert event(*args) == expected
def notify(initialized, stamp, prev, state, age):
    return initialized and stamp is not None and prev is not None and stamp > prev and state in (3,4) and age <= 30
alerts = [
 (False,200,100,3,0,False), (True,200,200,3,0,False),
 (True,200,100,3,0,True), (True,200,100,4,0,True),
 (True,200,100,3,31,False), (True,200,100,5,0,False),
 (True,200,None,3,0,False),
]
for *args, expected in alerts:
    assert notify(*args) == expected
print('Independent predicate checks: 18 PASS')
'@ | python -
Get-FileHash scripts/tradingview/yosuga_ytt_fx_scanner.pine -Algorithm SHA256
```

## 限界と引継ぎ

1. 判定は監視銘柄の直近確定足に基づくため、同銘柄assistantの形成中バーのパネルと瞬間的に一致しない場合がある。現在バーを先読みするための差ではない。
2. 更新はホストチャートの実行に依存する。休場チャート・配信遅延・Bar Replayでは実時刻基準の鮮度表示が古い判定となり得る。過去リプレイを常に新鮮なリアルタイム候補にする機能ではない。
3. 成立は直近確定足のイベントであり、いつでも約定してよい意味や勝率の順位ではない。待ち/成立/突破済みの色分けは収益優位性を示さない。
4. TP/SL同時到達、ギャップ約定、数量、スプレッド・手数料・スリッページ・スワップは本表示補助の計算対象外。取引数・PF・期待値・DDや複数期間/通貨の利益検証を新たに実施したとは扱わない。
5. 次担当は主担当。最終ソース識別子とTradingViewの実コンパイル・8通貨表示・設定不正表示を照合し、実受信未確認のアラートはその旨を残す。
