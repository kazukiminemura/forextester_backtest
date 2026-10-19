# BB3σ / YTT 表示統合・独立検証

2026-10-09。担当 `/root/ytt_bb_review`。この文書だけを編集し、戦略コード・採用基準は変更していない。

**静的移植整合: PASS。収益判定: 未検証。TradingViewの実コンパイル・表示は主担当の実機証拠で別途確認する。**

## 入力識別子

SHA256:

|入力|SHA256|
|---|---|
|`scripts/tradingview/bb3_reversal_confirmation_indicator.pine`|`f25233397c332af785ea6912d672f2ed25b68b9007b0f803357cde712914b154`|
|`scripts/tradingview/yosuga_ytt_assistant.pine`|`857a0548729c96ddba326d7b0e5d6f573e7dfad1eded603fec7dafd42ad0f1ad`|
|`scripts/tradingview/yosuga_ytt_fx_scanner.pine`|`7095369e0e5d91c17189fb914a397fba09b9aad0817e1208dfdc0aa00250f8cd`|
|確認済み統合版 `scripts/tradingview/yosuga_ytt_combined.pine`|`767bdee5731a91d0b3840a614177d5f922b4878da221d953032b88f8aa74163d`|

## 確認方法と結果

元BBソースを読んで、統合部の `BB_` 識別子だけをトークン単位で逆変換し、元ソースと比較した。文字列・コメントは逆変換しない。次の5区間が文字単位で一致した。

1. `recentImpulse` 本体: 511文字。
2. `candidateCheck` から候補状態遷移の末尾まで: 3,294文字。
3. 仮想RR1台帳本体: 2,644文字。
4. `scannerImpulse` と `scannerSnapshot`: 5,422文字。
5. scannerの状態名と並べ替え順位: 449文字。

最終版の追加変更はBB履歴ラベルの300件FIFOと一覧の空行/行オフセット。状態遷移・台帳を変更しないことを再読確認した。FIFOはBBの履歴ラベルだけを削除し、YTT水平線ラベル、チャネルラベル、候補ラベル、BB稼働中の価格ラベルを巻き込まない。YTT側の保持上限と合計しても500ラベル未満。

最終余白調整を追加照合: YTT/BB両一覧の空行 `height=4` を `height=8` に変更した2箇所のみ。現ファイルのこの2箇所をメモリ上で戻したSHA256は `d27cdb193d608d5a205ff31b32ae6acfe4878adf4dd73b8a810ae33c94c3036e` と一致した。既確認版から売買条件・描画座標・資源数の変更なし。主担当は旧余白版の実機版2でBB一覧15分/5分、価格plot、共有8通貨、右上仮想成績の重なりなしを確認済みと報告。最終版3は再コンパイル確認中であり、その成功はこの静的照合だけでは認定しない。

```powershell
python -m pytest tests/test_bb3_reversal_confirmation_indicator.py tests/test_yosuga_ytt_combined.py -q
Get-FileHash scripts/tradingview/yosuga_ytt_combined.pine
```

テスト結果: **35 passed / exit 0**。これは構造検査・元BBのローカル検査でありPineコンパイル成功を意味しない。

## 条件・価格・時系列

- BBはタッチ準備の次足以降で陽線/陰線のバンド内回帰、その次足以降で高値/安値の厳密突破。候補の出力は足確定時。突破足の終値が基準を越えていることは要求していない。YTTの終値突破条件とは独立。
- 準備足の極値更新、欠損、反対バンド、勢い、長いヒゲ、期限などの取消を突破より先に判定。同一足で取消と突破を満たす場合は取消。
- 候補の参考価格は買い `max(open, trigger + mintick)`、売り `min(open, trigger - mintick)`。判定幅は前足BB中央線。タッチや候補価格を実約定とは表示しない。
- 仮想RR1台帳は候補確定後の連続した次足始値のみ入場、TPは候補確定時の中央線を価格刻みへ丸め固定、SLは `2 * Entry - TP`。同足TP/SLはSL優先、ギャップで両価格を越えて始まった場合は始値で決済。費用は仮定の往復pipsを一度控除。
- BB scannerは要求先銘柄の価格刻み・クオート通貨を使用し、6返却フィールドすべて `[1]`。YTT scannerも全フィールド `[1]`、上位足も確定値。BBにYTT方向フィルターを付加していない。

## 統合表示・資源

- 価格plot/plotshape/line/labelは `force_overlay=true`。BBのfillは同じ価格paneのplotを参照。YTT水平線・チャネルの生成経路は保持。
- 主価格paneはYTT状態=左下、YTT候補=右下、任意BB仮想成績=右上。一覧paneはYTT/BBどちらかだけtableを生成する。BB表は6列11行、データは3〜10行の8通貨まで。
- 監視銘柄は同じ8つの `symbol1`〜`symbol8` を共有。元BBの11銘柄inputは重複生成しない。BB側重複銘柄除去は保持。
- BBの既定「5分足に限定」はOFFへ変更。現在チャート足でBBを計算し、設定ONで旧5分足限定へ復帰できる。YTT一覧の判定足inputをBBへ流用していない。
- BBの見送り理由ラベルと仮想成績は既定OFF。BB通知も既定OFF。通知ON時の確定足条件は保持し、YTTの通知との併存のため `alert.freq_all` を使用。
- 静的plot見積: plot 10本 + 条件付き色の追加1 + plotshape 4本 + alertcondition 6本 = **21**。64未満。
- requestは現足状態最大8、YTTの8銘柄×(判定1+上位2)=24、BB8で保守的最大**40**。既定15分では既存状態の同一足/重複要求が減る。上限に余裕はないため、将来通貨/時間足を増やす場合は再確認必須。
- tupleはソース上の要求式が4/3/3/UDT/6要素。UDTによりYTT多項目の展開を回避している。実際のコンパイラ展開後の資源カウントと任意設定の動作は静的検査だけでは断定せず、主担当の実機確認対象とする。

公式制限: [TradingView Pine Script limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/)（2026-10-09確認）。request通常40、plot64、合計tuple127、label最大500。

## 判定・引継ぎ

移植の静的監査では重大な条件変更・価格参照不一致を認めない。最終コードのTradingViewコンパイル、15分/5分でYTT一覧とBB一覧切替、BB価格線とYTT水平線/チャネル共存、任意のBB成績表示は主担当が確認する。

収益に関する凍結仮説・データ台帳・事前採用基準はこの表示統合では入力されておらず、利益検証は実施しない。通貨/期間別PF・期待値・DD、パラメータ感度、費用増加耐性の成績は算出していない。単一チャートの仮想勝率を研究合格や実運用承認にしない。

未実装の実費用は銘柄/時刻別スプレッド、実際の滑り・手数料・スワップ。台帳は数量・口座通貨換算を持たずpipsのみ。他クオート通貨の金銭損益を合算しない。実注文なし。
