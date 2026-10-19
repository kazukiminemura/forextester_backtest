# FXSPACE M5判断研究：データ台帳

2026-10-11 JST。データ担当。状態 `DATA_READY_WITH_LIMITATIONS`。今回の編集は本書のみ。原履歴・旧NPZを読取専用で再利用し、再ダウンロード・データコピー・原履歴変更は行っていない。新戦略の結果は参照していない。

## 入力ID・期間・利用方法

既存 `agent_runs/fxspace_proxy_20261011/{USDJPY,EURUSD,GBPUSD}_m5.npz` を直接使用する。新実験フォルダに複製しない。

|ファイル|固定SHA256|
|---|---|
|USDJPY_m5.npz|76274aed9f0dc45c8d743e21f1678ba4ca98d37bcc3af6e947f99f1e2e795a58|
|EURUSD_m5.npz|28037e993217cd35e9576eeb04e844100ae3d05b53d559a713c0306d05fd5703|
|GBPUSD_m5.npz|861656a577d392e6e14f1ab00bf6752cc2a3103177b00d7ae0da9afaf1f1f5b7|

全3通貨の保存範囲は2019-12-01 22:00〜2025-12-31 21:55（M5開始、元時計）。2019年12月を初期化、2020-01-01以上2026-01-01未満を記述評価に適用できる。過去研究で既閲覧の期間であり、未使用holdoutを保証しない。

|キー|型と意味|
|---|---|
|times|int64、元時計のM5開始、1970-01-01との差の算術秒。UTC/JST扱い不可|
|prices|float64、N×4、Open / High / Low / Close|
|complete|bool、元M1が5本すべて存在する完全M5|
|starts_at_open|bool、M5開始時刻そのものにM1観測が存在する|
|observed_open_times|int64、該当M5内で最初に観測されたM1時刻|

## 今回確認した範囲

全3NPZのSHA256は旧台帳と一致。全1,365,021 M5行についてキー・型・配列長・有限正値・OHLC包絡・時刻の厳密昇順・重複なし・300秒境界を検査した。実観測始値が当該M5区間内の60秒境界に存在すること、`starts_at_open == (observed_open_times == times)`、完全足の始値存在も全件確認した。異常0。

今回の検査はM5キャッシュ全件であり、原M1の再検査ではない。原履歴からの生成根拠は次節の既存全件監査に依拠する。SHA一致により、今回参照しているM5アーカイブが当該検証済み成果物と同一であることを確認した。

|通貨|M5保存|完全M5|不完全M5|ラベル始値欠損|間隔>300秒|
|---|---:|---:|---:|---:|---:|
|USDJPY|455,085|446,773|8,312|1,843|415|
|EURUSD|455,004|445,417|9,587|2,265|441|
|GBPUSD|454,932|447,550|7,382|1,754|447|

gapは週末・休日を含み、市場営業中の障害数とは同義でない。完全足だけを抜き出して隣接添字を連続5分と扱わない。判断窓に必要な連続性・不完全足・欠損後状態の扱いは新仕様で固定する。300秒執行を使用し、実観測始値が遅れた場合にラベル時刻で観測済みと扱わない。保有中の不完全足を削除して、その間の観測SL/TP接触を失わない。M5 OHLCのみでは同一足内のTP/SL到達順序を特定できない。

## 原M1からの検証履歴

前回資料：`docs/quant_organization/experiments/fxspace_proxy_20261011/data.md`。さらにその比較元は `docs/quant_organization/experiments/new_logic_20261011/data.md` と `agent_runs/ytt_monthly5_fx_20261009/run_manifest.json`。

前回は `HistoryRepository.summary/metadata` を優先し、原 `C:/ForexTester6/data/History/{symbol}/Bars.dat` の固定長形式をread-onlyで読み、対象M1全6,788,346行から直接M5を生成した。M1全対象行のOHLC・有限・時刻順・60秒境界の異常0、新M5全件の同様検査にも異常0だった。M5→M15再集約の全455,174行は既存監査済みM15の時刻・OHLC・complete・実観測始値・開始フラグと完全一致（価格最大差0）した。

当時の原Bars.dat全bytes SHA256は下記で旧manifestと一致していた。今回原Bars全bytesの再ハッシュは実施していない。原M1の2003〜2026全保存期間を内容全件検査したものではなく、対象2019年12月〜2025年末に限定した検証履歴である。tick内容は未検査。

|通貨|前回原Bars.dat SHA256|
|---|---|
|USDJPY|31fc474177e6b2235dbd6a46760d5f428d53de3bc864120677647f651b1828a7|
|EURUSD|a7c97f167fb1b0bb016872f73796d1870b68286395b9a5818a797301065d016c|
|GBPUSD|573be0820fb6ea2147266084bbec85bb3824b0a7e0eb9032edf10bf4d3d3d601|

## 費用・単位と制約

今回も `HistoryRepository.metadata` で現物info.datを読み、次の値を再確認した。全通貨lot_size=100,000、commission_per_lot=0、SwapLong/Short=0.0000。ただし設定0は実口座の費用0を証明しない。

|通貨|decimals / tick|pip|設定spread|引継ぐ往復仮定費用|quote|
|---|---|---:|---:|---:|---|
|USDJPY|3 / 0.001|0.01|12 points = 1.2 pip|1.6 pip|JPY|
|EURUSD|5 / 0.00001|0.0001|11 points = 1.1 pip|1.5 pip|USD|
|GBPUSD|5 / 0.00001|0.0001|14 points = 1.4 pip|1.8 pip|USD|

pipは既存proxy台帳が示す `agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json` のFX単位。quoteは `InstrumentMetadata.pnl_currency` の6文字銘柄名末尾3文字の定義。往復費用は設定spread＋片道0.2 pipずつであり、実測費用ではない。コスト2倍もstress仮定として扱う。複数quoteのR集計と円口座損益は異なる。

元時計のzone/DSTとOHLCのBid/Ask/中値は未確定。実spread履歴・slippage・swap・broker数量刻み/最小lotも未確認。元時計00:00集約とTradingView/OANDA/JSTの一致を保証しない。M5化で取引数や収益性が増えるかはデータ担当の判定対象ではない。

## 再現コマンド・次担当

リポジトリルートのPowerShell。実行終了コード0、末尾 `READ_ONLY_ALL_M5_ROWS_PASS`。読み取りのみ。

```powershell
$env:PYTHONPATH='src'
@'
import hashlib,json
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from forextester_backtest.data import HistoryRepository
root=Path('agent_runs/fxspace_proxy_20261011')
expected={
'USDJPY':'76274aed9f0dc45c8d743e21f1678ba4ca98d37bcc3af6e947f99f1e2e795a58',
'EURUSD':'28037e993217cd35e9576eeb04e844100ae3d05b53d559a713c0306d05fd5703',
'GBPUSD':'861656a577d392e6e14f1ab00bf6752cc2a3103177b00d7ae0da9afaf1f1f5b7'}
repo=HistoryRepository()
for s,h in expected.items():
    path=root/(s+'_m5.npz')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==h
    z=np.load(path,allow_pickle=False)
    assert set(z.files)=={'times','prices','complete','starts_at_open','observed_open_times'}
    t,p,c,o,a=(z[k] for k in ('times','prices','complete','starts_at_open','observed_open_times'))
    assert t.dtype==np.int64 and a.dtype==np.int64 and p.dtype==np.float64
    assert c.dtype==bool and o.dtype==bool and p.shape==(len(t),4)
    assert c.shape==o.shape==a.shape==t.shape
    assert (np.diff(t)>0).all() and (t%300==0).all()
    assert np.isfinite(p).all() and (p>0).all()
    assert (p[:,1]>=p[:,[0,3]].max(axis=1)).all()
    assert (p[:,2]<=p[:,[0,3]].min(axis=1)).all()
    assert ((a>=t)&(a<t+300)&(a%60==0)).all()
    assert np.array_equal(o,a==t) and o[c].all()
    m=repo.metadata(s)
    stamp=lambda v:(datetime(1970,1,1)+timedelta(seconds=int(v))).isoformat(' ')
    print(json.dumps(dict(symbol=s,sha256=h,rows=len(t),complete=int(c.sum()),incomplete=int((~c).sum()),
      missing_open=int((~o).sum()),gap_gt300=int((np.diff(t)>300).sum()),first=stamp(t[0]),last=stamp(t[-1]),
      lot_size=m.lot_size,commission=m.commission_per_lot,spread_points=m.spread_points,decimals=m.decimals,
      quote=m.pnl_currency,swap_long=m.values['SwapLong'],swap_short=m.values['SwapShort'])))
print('READ_ONLY_ALL_M5_ROWS_PASS')
'@ | python -
```

次担当：研究開発 `fxspace_source`、独立検証 `fxspace_gap_audit`、研究責任者。新仕様に入力SHA・既閲覧・300秒執行・欠損・費用仮定を固定する。

