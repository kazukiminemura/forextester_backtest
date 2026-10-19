# FXSPACE数値近似研究：データ台帳

2026-10-11 JST。データ担当。状態 `DATA_READY_WITH_LIMITATIONS`。原履歴・旧キャッシュは読取専用。新規書込は本書と `agent_runs/fxspace_proxy_20261011/*_m5.npz` のみ。戦略成績・採用判断は担当外。

## 入力と適用可能期間

`HistoryRepository.summary/metadata` を優先して原形式・件数・設定を確認し、同Repositoryの固定長M1形式（先頭4 byte、1行little-endian float64×6）をread-only memmapで読み直してM5を作成した。外部データは使っていない。

共通期間は2019-12-01 22:00〜2025-12-31 21:55（M5開始、元時計）。2019年12月を初期化、2020-01-01以上2026-01-01未満を記述評価に利用できる。これは2019年全体の履歴ではない。2020〜2025は既存YTT/BB等の研究で既閲覧であり、真の未使用holdoutとは保証しない。2026も別研究で利用履歴があり、未使用と主張できない。

`np.load("agent_runs/fxspace_proxy_20261011/USDJPY_m5.npz", allow_pickle=False)`（他2通貨も同形式）：

|キー|型・意味|
|---|---|
|times|int64、M5ラベル開始の算術秒座標。元時計のUTC/JST/DSTは未確認|
|prices|float64 N×4、Open, High, Low, Close|
|complete|bool、該当300秒にM1が開始から5本揃う|
|starts_at_open|bool、ラベル時刻のM1が存在する|
|observed_open_times|int64、最初に観測したM1の時刻|

元M1が不足するM5も執行観測のため保持した。完全足だけ抽出すると隣接添字が5分連続とは限らない。`diff(times)==300`、`complete`、`starts_at_open`を目的別に扱う。M15/H1シグナルを作る際は、同じ元時計の00:00基準で3/12本の完全・連続M5を必要とする。欠損で窓や状態をリセットする条件は研究仕様で固定する。

執行幅は300秒。既存YTT simulatorは900秒固定箇所があるためそのまま流用できない。始値が欠けたラベル時刻で約定したことにせず、`observed_open_times`を使用する。保有中の不完全足を無言で削除すると観測されたSL/TP接触も消える。M5内の価格経路・TP/SL到達順序はOHLCのみでは特定できない。

## 全件検査と集約照合

既存のM1監査は `docs/quant_organization/experiments/new_logic_20261011/data.md` と `agent_runs/ytt_monthly5_fx_20261009/run_manifest.json` に記録されている。今回はM5生成に必要な対象M1全6,788,346行を再読込したため、同対象の有限・正値・OHLC包絡・厳密昇順・重複なし・60秒境界も再確認した。生成M5全1,365,021行でも同様の検査（300秒境界）に異常0。

全M5をM15へ再集約し、既監査の `*_execution.npz` 全455,174行と times、全OHLC（最大差0）、complete、observed_open_times、starts_at_open が完全一致した。元Bars.dat全bytes SHA256も3通貨とも旧manifestと一致した。

これは対象2019年12月〜2025年末の**全件検査**であり、2003〜2026の元M1全保存期間の全件内容検査ではない。対象外M1はsummary端点/件数と全bytes SHAのみ。tick内容の検査・価格側照合は未実施。

|通貨|対象M1|M1間隔>60秒|M5保存|完全M5|不完全M5|ラベル始値欠損|M5間隔>300秒|
|---|---:|---:|---:|---:|---:|---:|---:|
|USDJPY|2,263,374|8,948|455,085|446,773|8,312|1,843|415|
|EURUSD|2,261,333|10,386|455,004|445,417|9,587|2,265|441|
|GBPUSD|2,263,639|7,996|454,932|447,550|7,382|1,754|447|

全暦M5グリッド欠落はUSDJPY 184,851、EURUSD 184,932、GBPUSD 185,004本。これらのgap・欠落は週末/休日を含み、市場営業中の障害数と同義ではない。市場カレンダーとの照合は未実施。

|年|USDJPY 保存/完全|EURUSD 保存/完全|GBPUSD 保存/完全|
|---|---:|---:|---:|
|2019年12月|6,156 / 6,012|6,158 / 6,105|6,155 / 6,124|
|2020|74,983 / 73,571|74,973 / 73,036|74,948 / 74,389|
|2021|74,873 / 72,017|74,863 / 72,155|74,841 / 72,913|
|2022|74,809 / 73,768|74,833 / 73,785|74,801 / 73,784|
|2023|74,654 / 73,727|74,602 / 73,176|74,637 / 73,767|
|2024|74,927 / 73,990|74,924 / 73,405|74,912 / 73,386|
|2025|74,683 / 73,688|74,651 / 73,755|74,638 / 73,187|

原M1全保存は3通貨とも2003-05-06 00:00〜2026-09-07 23:59。全保存件数はUSDJPY 8,534,100、EURUSD 8,567,792、GBPUSD 8,680,197。tick件数は同順422,111,274 / 462,163,350 / 448,346,540（summaryのみ）。

## 費用・単位・未確認事項

現物 `C:/ForexTester6/data/History/{symbol}/info.dat` を `HistoryRepository.metadata` で確認。全3通貨 lot_size=100,000、ApplyCommission=0 / CommPerLot=0.00、SwapLong/Short=0.0000。保存設定0は実口座の費用0を保証しない。Broker欄はAdvanced Data Feed。

|通貨|decimals / tick|pip定義|metadata spread|旧研究の往復仮定費用|quote|
|---|---|---:|---:|---:|---|
|USDJPY|3 / 0.001|0.01|12 points = 1.2 pip|1.6 pip|JPY|
|EURUSD|5 / 0.00001|0.0001|11 points = 1.1 pip|1.5 pip|USD|
|GBPUSD|5 / 0.00001|0.0001|14 points = 1.4 pip|1.8 pip|USD|

pipは既存研究 `agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json` のFX単位を引き継いだ。quoteは `InstrumentMetadata.pnl_currency` の6文字銘柄名末尾3文字定義に基づく。旧往復費用はmetadata spread＋片道0.2 pipずつ。新研究がこれを使用する際は仮定としてprotocolに明記し、実費履歴と呼ばない。stressを2倍にする場合も仮定。

OHLCのBid/Ask/中値は未確定。元時計のzone/DST、実spread履歴、実slippage、swap、broker数量step/最小lotは未確認。時刻は1970-01-01との差から得た算術秒でありUTCと解釈していない。元時計00:00集約をTradingView/OANDA/JST区切りと同一視しない。複数quoteのR集計は円口座損益ではない。

## 固定SHA256

|入力/出力|SHA256|
|---|---|
|USDJPY_m5.npz|76274aed9f0dc45c8d743e21f1678ba4ca98d37bcc3af6e947f99f1e2e795a58|
|EURUSD_m5.npz|28037e993217cd35e9576eeb04e844100ae3d05b53d559a713c0306d05fd5703|
|GBPUSD_m5.npz|861656a577d392e6e14f1ab00bf6752cc2a3103177b00d7ae0da9afaf1f1f5b7|
|C:/ForexTester6/data/History/USDJPY/Bars.dat|31fc474177e6b2235dbd6a46760d5f428d53de3bc864120677647f651b1828a7|
|C:/ForexTester6/data/History/EURUSD/Bars.dat|a7c97f167fb1b0bb016872f73796d1870b68286395b9a5818a797301065d016c|
|C:/ForexTester6/data/History/GBPUSD/Bars.dat|573be0820fb6ea2147266084bbec85bb3824b0a7e0eb9032edf10bf4d3d3d601|

## 再現コマンドと引継ぎ

リポジトリルートのPowerShellで以下を実行。実行終了コード0、末尾 `DATA_READY_ALL_SELECTED_M1_AND_M5_ROWS_PASS` を確認。既存の出力ファイルがある場合は上書きせず全キー値を照合する。新規生成時のZIPメタデータによりNPZファイルSHAは変わる可能性があるため、再生成したアーカイブは全配列一致も確認する。

```powershell
$env:PYTHONPATH='src;scripts'
@'
import hashlib,json
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from forextester_backtest.data import HistoryRepository,_to_ole
out=Path('agent_runs/fxspace_proxy_20261011'); out.mkdir(parents=True,exist_ok=True)
old=Path('agent_runs/ytt_monthly5_fx_20261009')
repo=HistoryRepository()
epoch=_to_ole(datetime(1970,1,1))
for m in json.loads((old/'run_manifest.json').read_text())['inputs']:
    s=m['symbol']; raw=repo.root/s/'Bars.dat'; summary=repo.summary(s)
    with raw.open('rb') as f: raw_hash=hashlib.file_digest(f,'sha256').hexdigest()
    assert raw_hash==m['raw_sha256']
    oldz=np.load(old/(s+'_execution.npz'),allow_pickle=False)
    start=int(oldz['times'][0]); end=int(oldz['times'][-1])+900
    a=np.memmap(raw,mode='r',dtype='<f8',offset=4,shape=(summary.bar_count,6))
    lo,hi=np.searchsorted(a[:,0],[(start-1)/86400+epoch,end/86400+epoch])
    rt=np.rint((a[lo:hi,0]-epoch)*86400).astype(np.int64)
    rp=np.array(a[lo:hi][:,[1,3,4,2]])
    assert np.all((rt>=start)&(rt<end))
    assert (np.diff(rt)>0).all() and (rt%60==0).all()
    assert np.isfinite(rp).all() and (rp>0).all()
    assert (rp[:,1]>=rp[:,[0,3]].max(axis=1)).all()
    assert (rp[:,2]<=rp[:,[0,3]].min(axis=1)).all()
    labels=rt//300*300
    first=np.r_[0,np.flatnonzero(np.diff(labels))+1]; last=np.r_[first[1:],len(rt)]
    t=labels[first]
    p=np.column_stack([rp[first,0],np.maximum.reduceat(rp[:,1],first),
                       np.minimum.reduceat(rp[:,2],first),rp[last-1,3]])
    complete=(last-first==5)&(rt[first]==t)&(rt[last-1]==t+240)
    observed=rt[first]; starts_at_open=observed==t
    assert (np.diff(t)>0).all() and (t%300==0).all()
    assert np.isfinite(p).all() and (p>0).all()
    assert (p[:,1]>=p[:,[0,3]].max(axis=1)).all()
    assert (p[:,2]<=p[:,[0,3]].min(axis=1)).all()
    path=out/(s+'_m5.npz')
    if path.exists():
        z=np.load(path,allow_pickle=False)
        assert all(np.array_equal(z[k],v) for k,v in dict(times=t,prices=p,complete=complete,starts_at_open=starts_at_open,observed_open_times=observed).items())
    else:
        np.savez_compressed(path,times=t,prices=p,complete=complete,starts_at_open=starts_at_open,observed_open_times=observed)
    # All M5 bars aggregated back to M15 must match the previously audited input.
    k=t//900*900; f=np.r_[0,np.flatnonzero(np.diff(k))+1]; e=np.r_[f[1:],len(t)]
    q=np.column_stack([p[f,0],np.maximum.reduceat(p[:,1],f),np.minimum.reduceat(p[:,2],f),p[e-1,3]])
    valid=(e-f==3)&(t[f]==k[f])&(t[e-1]==k[f]+600)&np.logical_and.reduceat(complete,f)
    assert np.array_equal(k[f],oldz['times']) and np.array_equal(q,oldz['prices'])
    assert np.array_equal(valid,oldz['complete'])
    assert np.array_equal(observed[f],oldz['observed_open_times'])
    assert np.array_equal(starts_at_open[f]&(t[f]==k[f]),oldz['starts_at_open'])
    stamp=lambda v:(datetime(1970,1,1)+timedelta(seconds=int(v))).isoformat(' ')
    yearly={}
    for year in range(2019,2026):
        l=(datetime(year,1,1)-datetime(1970,1,1)).total_seconds()
        h=(datetime(year+1,1,1)-datetime(1970,1,1)).total_seconds()
        keep=(t>=l)&(t<h)
        yearly[str(year)]={'stored':int(keep.sum()),'complete':int(complete[keep].sum())}
    meta=repo.metadata(s)
    print(json.dumps(dict(symbol=s,raw_sha256=raw_hash,npz_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
      raw_selected=len(rt),raw_gap_gt60=int((np.diff(rt)>60).sum()),m5=len(t),
      complete=int(complete.sum()),incomplete=int((~complete).sum()),missing_open=int((~starts_at_open).sum()),
      gap_gt300=int((np.diff(t)>300).sum()),calendar_missing=int((t[-1]-t[0])//300+1-len(t)),
      first=stamp(t[0]),last=stamp(t[-1]),yearly=yearly,
      full_raw_count=summary.bar_count,full_raw_first=str(summary.bar_start),full_raw_last=str(summary.bar_end),
      ticks_count=summary.tick_count,metadata=meta.values,pnl_currency=meta.pnl_currency),ensure_ascii=False))
print('DATA_READY_ALL_SELECTED_M1_AND_M5_ROWS_PASS')
'@ | python -
```

次担当：研究責任者・研究開発・独立検証。上記3NPZのSHAを固定し、300秒執行・不完全足・実観測始値・元時計未確定・既閲覧期間の制約を仕様と実装で扱う。

