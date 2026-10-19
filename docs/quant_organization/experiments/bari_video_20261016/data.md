# バリ式動画検証準備：入力データ台帳

2026-10-16 JST。担当 `bari_data_audit`。状態 `DATA_READY_WITH_LIMITATIONS`。動画仕様・戦略成績・採用判定は対象外。本書だけを新規作成。原履歴、キャッシュ、他者の変更は保持した。

## 利用すべき入力

主データ源は `C:/ForexTester6/data/History`。今回 `HistoryRepository.summary/metadata` で現物の件数・端点・設定を確認し、保存済み `agent_runs/fxspace_proxy_20261011/{USDJPY,EURUSD,GBPUSD}_m5.npz` を読取検査した。外部取得・原履歴再構築・キャッシュ複製は不要。

共通範囲は **2019-12-01 22:00〜2025-12-31 21:55（M5開始、元時計）**。2019年12月を初期化用、2020年初〜2026年初未満を候補評価範囲にできる。2020–2025は過去のYTT・BB・FXSPACE研究で既閲覧。未使用holdoutと呼べない。2026も別研究での使用履歴があり、未使用とは保証しない。

|通貨|今回再確認したM5アーカイブSHA256|
|---|---|
|USDJPY|76274aed9f0dc45c8d743e21f1678ba4ca98d37bcc3af6e947f99f1e2e795a58|
|EURUSD|28037e993217cd35e9576eeb04e844100ae3d05b53d559a713c0306d05fd5703|
|GBPUSD|861656a577d392e6e14f1ab00bf6752cc2a3103177b00d7ae0da9afaf1f1f5b7|

キーは `times`（元時計M5開始int64算術秒）、`prices`（float64 N×4、O/H/L/C）、`complete`（元M1が全5本存在）、`starts_at_open`（開始ラベル時刻の観測あり）、`observed_open_times`（最初の実観測M1時刻）。秒数は1970-01-01との差という座標であり、UTC/JSTの証拠ではない。

## 今回の検査結果と前回からの引継ぎ

今回のNPZ全件検査は1,365,021行。キー・型・配列長、有限正値、OHLC包絡、厳密時刻昇順、重複なし、300秒境界、実始値観測の区間内・60秒境界、始値フラグ一致、完全足の始値ありに異常0。全3ファイルのSHAが2026-10-11台帳と一致。これはキャッシュ全件検査であり、原M1・tickの全件再検査ではない。

|通貨|M5保存/完全|不完全M5|開始M1欠損|間隔>300秒|M15保存/完全|H1保存/完全|
|---|---:|---:|---:|---:|---:|---:|
|USDJPY|455,085 / 446,773|8,312|1,843|415|151,740 / 145,410|37,939 / 34,045|
|EURUSD|455,004 / 445,417|9,587|2,265|441|151,718 / 144,440|37,936 / 33,515|
|GBPUSD|454,932 / 447,550|7,382|1,754|447|151,716 / 146,152|37,935 / 34,465|

M15/H1件数は今回 `scripts.research_fxspace_proxy_20261011.aggregate` を読み取り実行して確認。開始は同じ2019-12-01 22:00、最後の開始はM15が2025-12-31 21:45、H1が21:00。元時計00:00基準の900/3600秒区切り。完全・連続した3/12本のM5が必要。ギャップには週末・休日を含み、営業中の通信欠損数ではない。

今回の現物summaryでは3通貨のM1全保存端点は2003-05-06 00:00〜2026-09-07 23:59。M1件数はUSDJPY 8,534,100、EURUSD 8,567,792、GBPUSD 8,680,197。tick件数は422,111,274 / 462,163,350 / 448,346,540。ここはヘッダ・ファイルサイズ・端点の確認に限り、全保存内容の品質を保証しない。

原M1からの作成根拠は `docs/quant_organization/experiments/fxspace_proxy_20261011/data.md` と `.../fxspace_m5_20261011/data.md` の既存監査。前回は対象6,788,346 M1行を全件検査し、M5生成とM5→旧M15全455,174行の一致を確認している。今回原Bars全bytesの再ハッシュやM1再集約は実施していない。今回同一SHAを確認したキャッシュからの品質継承である。

## 費用・単位・未確認事項

現物 `info.dat` を今回 `HistoryRepository.metadata` で再読込。全通貨lot_size=100,000、commission_per_lot=0、SwapLong/Short=0.0000。保存設定0は実口座費用0の証明ではない。

|通貨|decimals / tick|pip|設定spread|旧研究の往復費用仮定|quote|
|---|---|---:|---:|---:|---|
|USDJPY|3 / 0.001|0.01|12 points = 1.2 pip|1.6 pip|JPY|
|EURUSD|5 / 0.00001|0.0001|11 points = 1.1 pip|1.5 pip|USD|
|GBPUSD|5 / 0.00001|0.0001|14 points = 1.4 pip|1.8 pip|USD|

pipは旧台帳に示されたFX単位（出典 `agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json`）。quoteは `src/forextester_backtest/models.py` の `InstrumentMetadata.pnl_currency` が6文字銘柄名末尾3文字を返す定義。旧費用はspread＋片道0.2 pipずつ。今回採用する費用は研究責任者がprotocolへ明記する。実測spread/slippageとは呼べない。

元時計のzone/DST、OHLCのBid/Ask/中値、実spread・slippage・swap履歴、口座数量刻み/最小lotは未確認。TradingView/OANDA/JSTの区切りと同一とは保証しない。時刻窓をJST条件として検証するには別の時差根拠が必要。複数quoteのR集計を円口座損益として表示しない。

## 最小の読込・実行部品

1. 原データ端点・設定：`src/forextester_backtest/data.py:100` の `HistoryRepository`。`summary(symbol)` と `metadata(symbol)` は軽量。`bars(symbol,start,end,timeframe='1m')` は原履歴を必要範囲だけ調べる場合に使用する。
2. 既存キャッシュ：`np.load(path, allow_pickle=False)` で上記5キーのみ取得。旧戦略のsignal/stopsを新方式へ転用しない。M15が必要でも同M5を元に計算すれば入力が一貫する。
3. M15/H1：`scripts/research_fxspace_proxy_20261011.py:20` の `aggregate(data,900/3600)`。戻り値は開始時刻・OHLC・完全フラグ。上位足は `start+seconds<=decision_time` になってから参照する。
4. 執行部品の参照先：同ファイル202行の `simulate` は300秒実行幅、実観測始値、ギャップ・同一足接触・コスト・資金停止を扱う。ただし固定TP/最低RR、元金100万円/90万円停止等を含む**旧仕様専用**であり、動画の出口・時間制限・同時保有条件との適合確認なしにそのまま呼ばない。`scripts/research_ytt_profit_feasibility.py` の旧simulatorは900秒固定でM5へ直接流用不可。

不完全足を判断入力から除外しても、保有中のSL/TP接触観測まで削除しない。完全足のみ圧縮した添字を連続時間として扱わない。M5 OHLCだけでは足内到達順を確定できない。動画がtick順序、厳密な時刻窓、現在のfeedを要する場合はこの台帳だけでは足りない。

## 再現コマンド

リポジトリルートのPowerShell。今回実行は終了コード0、末尾確認ラベル `READ_ONLY_ALL_M5_ROWS_PASS`。既存台帳内の読取専用検査を再利用し、今回のsummaryとM15/H1件数を追加した。戦略実走はしていない。

```powershell
$env:PYTHONPATH='src'
@'
from pathlib import Path
s=Path('docs/quant_organization/experiments/fxspace_m5_20261011/data.md').read_text(encoding='utf-8')
code=s.split("@'\n",1)[1].split("\n'@ | python",1)[0]
exec(code)
from dataclasses import asdict
from scripts.research_fxspace_proxy_20261011 import aggregate
for symbol in expected:
 print('SUMMARY',asdict(repo.summary(symbol)))
 with np.load(root/(symbol+'_m5.npz'),allow_pickle=False) as z:
  d={k:z[k] for k in ('times','prices','complete','starts_at_open','observed_open_times')}
 for seconds in (900,3600):
  t,p,c=aggregate(d,seconds)
  print('AGG',symbol,seconds,len(t),int(c.sum()),stamp(t[0]),stamp(t[-1]))
'@ | python -
```

次担当：研究責任者・動画仕様担当。動画で確定した銘柄、時間足、時刻条件と上記適用範囲を照合し、入力SHA・既閲覧・費用仮定・欠損時の取消条件をprotocolへ固定する。

## 追記：H4参考状態の利用範囲

2026-10-16、研究責任者の追加依頼により、同じM5キャッシュを `aggregate(data,14400)` で読み取り集約した。H4は参考状態記録用、主案の方向フィルターはH1のみとする方針であり、この追記はH4フィルター追加を意味しない。終了コード0。

|通貨|H4保存|完全H4|不完全H4|2020年開始前の保存/完全/不完全|初期化区間の完全・連続H4最長|
|---|---:|---:|---:|---:|---:|
|USDJPY|9,807|7,007|2,800|134 / 59 / 75|9本|
|EURUSD|9,805|6,840|2,965|134 / 100 / 34|17本|
|GBPUSD|9,805|7,369|2,436|134 / 115 / 19|29本|

全通貨の先頭ラベルは **2019-12-01 20:00**、最初の完全足ラベルは **2019-12-02 00:00**、最終ラベルは **2025-12-31 20:00**（すべて元時計）。原M5入力は12月1日22:00開始なので、先頭H4は20:00に実始値があることを意味せず、不完全である。最終H4も入力終端21:55のため不完全。完全H4には48本の完全・連続M5が必要。

2020-01-01 00:00以前に終了したH4を初期化範囲とした。12月分のカレンダー余裕は約30日あるが、完全足の数と連続性は上表のとおり。必要lookbackが未確定の段階で初期化完了を保証しない。例えば欠損・週末ごとにリセットして20本連続の完全H4を要求すると、USDJPYとEURUSDはこの初期化区間内で20本を満たせない。H4参考状態が準備不足なら未確定として記録し、将来足や不完全足で補完しない。

区切りは**保存時計の00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00**。保存時計のzone/DSTが不明なため、TradingView/OANDAのH4境界・OHLCと同値とは保証できない。完了判定は `H4開始+14400 <= 判断時刻` を守る。

再現コマンド（読み取りのみ）：

```powershell
$env:PYTHONPATH='src'
@'
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from scripts.research_fxspace_proxy_20261011 import aggregate
start=int((datetime(2020,1,1)-datetime(1970,1,1)).total_seconds())
stamp=lambda x:(datetime(1970,1,1)+timedelta(seconds=int(x))).isoformat(' ')
for symbol in ('USDJPY','EURUSD','GBPUSD'):
 with np.load(Path('agent_runs/fxspace_proxy_20261011')/(symbol+'_m5.npz'),allow_pickle=False) as z:
  d={k:z[k] for k in ('times','prices','complete')}
 t,p,c=aggregate(d,14400)
 warm=t+14400<=start
 leading=np.flatnonzero(c)
 longest=run=0
 for i in np.flatnonzero(warm):
  run=run+1 if c[i] and (i==0 or t[i]==t[i-1]+14400) else int(c[i])
  longest=max(longest,run)
 print(dict(symbol=symbol,total=len(t),complete=int(c.sum()),incomplete=int((~c).sum()),first=stamp(t[0]),last=stamp(t[-1]),first_complete=stamp(t[leading[0]]),warm_bars=int(warm.sum()),warm_complete=int(c[warm].sum()),warm_incomplete=int((~c[warm]).sum()),longest_contiguous_complete_warmup=longest))
'@ | python -
```
