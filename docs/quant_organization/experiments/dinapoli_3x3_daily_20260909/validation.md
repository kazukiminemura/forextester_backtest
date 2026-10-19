# 日足3×3 DMA Double Repo 実験結果・検証引継ぎ

実験ID: `dinapoli_3x3_daily_20260909`。研究開発担当の実走結果。
研究ゲートは2候補とも不通過。独立検証結果は同じディレクトリの `audit.md` を参照する。
研究者による実運用採用承認ではない。

## 固定ルールと結果

日足の終値SMA3を3本右へ変位したDMAを使用。終値がDMA片側に8本または10本連続し、
逆側へ抜け、一旦元側に戻り、再度逆側に抜けたら反転方向へ翌日始値で入る。
初回から再度の抜けまでは8本/10本以内。構造SLの外側0.1ATR14、利確は価格幅RR1:1全決済。
保有中の時間決済はない。SL/TP同日接触はSLを先とし、損切り方向の窓開けは始値約定。

評価したのは2010-01-01〜2019-01-01未満のtrainingだけ。全15通貨を合計し、
各取引を初期リスク幅で1Rに正規化した研究スコアである。実口座の金額利益ではない。

|ルール|往復コスト|取引数|勝率|PF|平均net R|合計net R|確定損益最大DD|
|---|---|---:|---:|---:|---:|---:|---:|
|単純DMAクロス（比較）|固定1.4pips|2,035|50.57%|0.9986|-0.00068|-1.3868|54.4871R|
|単純DMAクロス（比較）|metadata spread|2,035|50.57%|0.9981|-0.00095|-1.9289|54.5196R|
|Double Repo 8|固定1.4pips|604|47.68%|0.8932|-0.05645|-34.0982|48.2237R|
|Double Repo 8|metadata spread|604|47.68%|0.8926|-0.05682|-34.3212|48.4061R|
|Double Repo 10|固定1.4pips|506|50.40%|0.9962|-0.00188|-0.9532|28.1510R|
|Double Repo 10|metadata spread|506|50.40%|0.9954|-0.00230|-1.1646|28.2491R|

取引数>=100は満たしたが、両候補とも両コストでPF>=1.10、平均net R>0、
集計DD<=20R、個別通貨DD<=10Rに不適合。
DR8の個別最大DDは16.2443R、DR10は固定16.2416R/metadata16.1968R。
利益通貨はDR8が7/15、DR10が8/15。これはtraining内の記述で、
事前ゲートのtraining+validation利益通貨基準を満たしたという意味ではない。

区分末の未決済はDR8が2件（固定含み+0.2605R、metadata+0.2594R）、DR10が1件
（固定-0.2338R、metadata-0.2349R）。比較条件は7件（固定-0.5456R）。
区分末に仮に時価全決済した感度計算でも、固定1.4pipsのPFはDR8が0.8941、DR10が0.9953。
正式ゲートは元仕様どおり未決済を取引数/PFから除く。

確定取引の保有暦日数（entryとexitの日足最初のM1時刻の差を日単位切捨て）の平均は
DR8が17.27日、DR10が19.60日、両候補の最長は1,240日だった。
構造SLと1R利確のみでは年単位の長期保有が起きる。swap=0の仮定は重大な制約であり、
今回のnet Rに実スワップを含めた運用収益としての意味を持たせない。
保有期限を追加して結果を改善する再調整はしていない。

単純DMAクロスに対して2候補の勝率と平均net Rの優位は確認できなかった。
両候補のtraining不通過により、validationとfinal_confirmationの損益は計算していない。
条件再調整・追加候補・Pine移植は実施していない。

## 保存証拠

保存先: `agent_runs/dinapoli_3x3_daily_20260909/completed/`。

- `protocol.json`: 実走前の固定仕様コピー。
- `code_input_hashes.json`: 実走前UTC時刻とprotocol/hypothesis/実装/共通データ読込コードのSHA256。
- `data_manifest.json`: 15通貨の原履歴パス、読込前後stat、使用raw配列SHA256、日足SHA256、metadata。
- `<symbol>_daily.npz`: 15通貨分のtrading dates、OHLC、raw first/last timestamp、M1構成本数。
- `<candidate>__training__<symbol>__<cost>.json`: 90件の取引・未決済・集計成果物。
  全取引はsignal available timestamp、entry実時刻、SL、TP、risk、net pips、net Rを保存。
- 上記と対応する`_equity.npz`: 90件の日足確定損益/含み込みequity。
- `training_results.json`, `selection_before_final.json`, `results.json`: 通貨別/コスト別全数値と選抜理由。

期間と対象: AUDUSD/EURUSD/GBPUSD/NZDUSD/USDCAD/USDCHF/USDJPY/
AUDJPY/CHFJPY/EURCHF/EURGBP/EURJPY/GBPCHF/GBPJPY/NZDJPY。
2009-10-01からウォームアップ、trainingは2010〜2018年。
後続期間の凍結予定はvalidation 2019〜2022年、final 2023-01-01〜2026-08-31未満。
2026-08-30の日曜日足はMondayの8/31ラベルとなるため除外し、保存最終日足は8/28。

## 再現コマンド・実行状態

作業ディレクトリ: `C:\Users\minemura\projects\forextester_backtest`。

```powershell
python -m pytest tests/test_dinapoli_3x3_daily.py -q
python -m scripts.research_dinapoli_3x3_daily
```

実行結果: 21 tests passed、pytest exit 0。研究実行exit 0、最終出力
`RESULT_JSON` のstatusは `REJECTED_BY_FROZEN_GATES`、selected/passは双方空配列。
再実行は既存成果物を上書きせず、新しい出力先を指定する。

```powershell
python -m scripts.research_dinapoli_3x3_daily --output agent_runs/dinapoli_3x3_daily_20260909/reproduction
```

テストはDMAの変位方向、Wilderウォームアップ、未来prefix不変性、日曜併合、
強い推進/抜け/復帰/再抜け/同値/期限境界、売買対称性、セットアップ区分リセット、
翌日始値と実際の1R幅、SL方向gap取消、SL/TP両接触優先、決済当日の再エントリー禁止、
未決済含みと仮強制決済感度、同時刻損益の合計後DD、凍結ゲートを検査した。

## 限界と検証担当への引継ぎ

公開されたDouble Repo条件を検証可能な条件へ具体化したモデルであり、
公式の裁量的な推進強度・コンテキストまで再現したものではない。
元データのタイムゾーンとBid/Ask種別は未確定。Sunday→Mondayは日足境界の近似で、
TradingViewの価格配信・日足OHLCが一致するとは限らない。
5分経路を使わず日足全体でSL優先にするため、実際の足内順序より不利になる可能性がある。
slippage/commission/swapは0で、特に日足の長期保有で実スワップは未評価。
相関・同時保有・口座換算・複利・証拠金を組み込んでいない。
全期間は過去のプロジェクト研究で既閲覧であり、真の未使用holdoutではない。

独立検証担当に渡す範囲: 凍結仕様・実装と全保存成果物の照合、別実装での集約/状態/約定/集計、
未来参照検査、ゲート適用の妥当性。戦略条件を結果に合わせて変更する権限は渡さない。
研究開発担当の所有変更は本実験hypothesis/protocol/validation、専用script/test、専用agent_runsのみ。
原履歴・既存戦略・Pineは変更していない。実注文・外部公開なし。

## 出典と機械化の範囲

- [DiNapoli公式書籍紹介・目次](https://www.dinapolilevels.com/trading-with-dinapoli-levels):
  変位移動平均、Double Repenetration、3×3 DMA計算が収録項目として確認できる。
- [Joe DiNapoli本人インタビュー](https://www.traderslog.com/interview-with-joe-dinapoli):
  終値の単純移動平均、2番目の数字が変位量、日足/週足/月足での利用という説明。
- [IGのDouble Repo解説](https://www.ig.com/it/inversioni-trend-double-repo):
  8〜10本の推進、2回の抜け、初回から再抜けまでの期間、次足始値という公開説明。

研究責任者が結果前に上記を確認して条件選定へ引継ぎ、研究担当もリンクを閲覧確認した。
公開説明に残る裁量を、連続終値のDMA片側条件、構造SL、全決済1R等へ具体化した部分は
今回の研究上の選択である。公式の完全再現や原著の収益性に対する判定とは扱わない。
