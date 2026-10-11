# 新規ロジック研究：入力台帳

2026-10-11 JST。データ担当、`DATA_READY_WITH_LIMITATIONS`。本書のみ編集。原履歴・キャッシュ・既存結果は読取専用。API呼出なし。戦略成績の新規計算・採用判定は担当外。

## 研究担当への入力

`agent_runs/ytt_monthly5_fx_20261009/{USDJPY,EURUSD,GBPUSD}_execution.npz` を優先する。`np.load(path, allow_pickle=False)`。

- `times`: M15開始のint秒。元時計の算術座標で、UTC/JSTとは未確認。
- `prices`: float64、列順 Open, High, Low, Close。
- `complete`: 元M1が開始から終了まで15本揃うbool。
- `starts_at_open`: ラベル時点のM1が存在するbool。
- `observed_open_times`: 実際に最初に観測されたM1の時刻。
- `sides/stops/thresholds` は旧YTT専用なので、新ロジックでは流用しない。

`entry900.npz` は不完全足を除いた列なので、単純な連続配列添字を15分の連続時間と見なせない。新規計算はexecutionを使い、必要なlookbackの完全性・`diff(times)==900` を確認する。欠損を跨ぐ状態を持ち越すか、取消すかは新仕様で固定する。保有中の不完全足を丸ごと捨てると、その間のSL/TP接触を隠すので、執行時の扱いを別に固定する。

共通保存期間は2019-12-01 22:00から2025-12-31 21:45（元時計）。2019年12月は初期化、2020-01-01以上2026-01-01未満を記述評価に利用できる。2020–2025は過去研究で既閲覧。2026も別研究で使われており未使用holdoutを保証しない。

## 今回の全件検査

`HistoryRepository.summary/metadata` を最初に使用し、同Repositoryの固定長形式に従うread-only memmapで対象M1を集約した。元Bars全bytes SHAは旧manifestと3/3一致。元M1全保存期間の内容検査ではなく、上記キャッシュに対応する6,788,346 M1行すべてを検査した。M15全455,174行の有限・正値・OHLC包絡・厳密昇順・重複なし・900秒境界、および対象M1全行の同様の条件・60秒境界は異常0。

原M1→M15再集約で、時刻、全OHLC（最大差0）、complete、observed_open_times、starts_at_openが全件完全一致した。tick内容検査は未実施。原履歴の対象外期間はsummary端点/件数と全bytes SHAのみであり、OHLC品質を保証しない。

|通貨|M15保存|完全M15|不完全M15|ラベル始値欠損|M15間隔>900秒|対象M1行|M1間隔>60秒|
|---|---:|---:|---:|---:|---:|---:|---:|
|USDJPY|151,740|145,410|6,330|592|329|2,263,374|8,948|
|EURUSD|151,718|144,440|7,278|716|337|2,261,333|10,386|
|GBPUSD|151,716|146,152|5,564|595|332|2,263,639|7,996|

上記gapは週末・休日を含む。市場営業中の障害数と同義ではない。全暦15分グリッドの欠落は61,572/61,594/61,596本。市場カレンダーとの照合は未実施。

|年|USDJPY 保存/完全|EURUSD 保存/完全|GBPUSD 保存/完全|
|---|---:|---:|---:|
|2020|25,000 / 23,820|24,998 / 23,531|24,995 / 24,539|
|2021|24,960 / 22,803|24,959 / 22,934|24,960 / 23,488|
|2022|24,946 / 24,194|24,948 / 24,185|24,947 / 24,233|
|2023|24,895 / 24,201|24,884 / 23,841|24,888 / 24,204|
|2024|24,984 / 24,280|24,983 / 23,793|24,981 / 23,840|
|2025|24,903 / 24,189|24,892 / 24,148|24,892 / 23,817|

原M1の全保存件数はUSDJPY 8,534,100、EURUSD 8,567,792、GBPUSD 8,680,197。全3通貨2003-05-06 00:00〜2026-09-07 23:59。原tick件数は422,111,274 / 462,163,350 / 448,346,540。tickとOHLC価格側の照合は未実施。

## 費用・価格単位

現物`info.dat`を`HistoryRepository.metadata`で読んだ値。全3通貨lot_size=100,000、commission_per_lot=0、SwapLong/Short=0.0000。ただし保存設定0は実口座の費用0の証明ではない。

|通貨|decimals / tick|pip定義|metadata spread|旧YTT研究の往復費用|quote|
|---|---|---:|---:|---:|---|
|USDJPY|3 / 0.001|0.01|12points=1.2pip|1.6pip|JPY|
|EURUSD|5 / 0.00001|0.0001|11points=1.1pip|1.5pip|USD|
|GBPUSD|5 / 0.00001|0.0001|14points=1.4pip|1.8pip|USD|

pipは既存`agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json`のFX定義。quoteは`InstrumentMetadata.pnl_currency`の6文字通貨名末尾3文字に基づく。旧YTT費用はspread＋片道0.2pipずつ、stressは往復額2倍。新研究で用いるなら仮定として明記する。OHLCがBid/Ask/中値のどれかは未確定。実spread履歴、スワップ、実slippage、broker数量step/最小lotは未確認。複数quoteの円口座換算をR集計と同一視しない。

日足・週足を作る場合は元時計00:00・月曜00:00であり、TradingView/OANDAの区切り一致を保証しない。時間帯フィルターをJSTと呼ぶにはsource timezone/DSTの別証拠が必要。

## 入力SHA256

|入力|SHA256|
|---|---|
|USDJPY_execution.npz|7b34e08c0edd67a85adc27498734863d66d8af94e6d8c1f2cff91fa965131f68|
|EURUSD_execution.npz|21ee41245dcc62f8a14861405ecc0a1336ec4fbd8328f12b728554cf5353e938|
|GBPUSD_execution.npz|e09cbca0ffdb39bfa822ff7a1c0530a67a621ca31b0ce5732f9088b5283a895c|
|C:/ForexTester6/data/History/USDJPY/Bars.dat|31fc474177e6b2235dbd6a46760d5f428d53de3bc864120677647f651b1828a7|
|C:/ForexTester6/data/History/EURUSD/Bars.dat|a7c97f167fb1b0bb016872f73796d1870b68286395b9a5818a797301065d016c|
|C:/ForexTester6/data/History/GBPUSD/Bars.dat|573be0820fb6ea2147266084bbec85bb3824b0a7e0eb9032edf10bf4d3d3d601|

## 既存の不採用・低採算の証拠への案内

以下は既存ファイルの場所と保存済み記載の紹介であり、今回新たな戦略成績・採用判断を作ったものではない。

1. YTT D/W M15/H1：`agent_runs/ytt_monthly5_fx_20261009/results.json` と同実験の`validation.md/audit.md`。例として保存済みUSDJPY D/W M15の2023–2024 PF=0.8038372181、973取引、mean_net_R=-0.0817434587。通貨/期間/費用別recordsと円口座結果を区別する。
2. YTT×Jev：`agent_runs/ytt_jev_20261010/training_summary_root.json`、`training_results.json`、`docs/ytt_jev_20261010.md`。保存済みJev RR1 PF=0.8131848178・実現payoff=0.9409710034、RR1.5 PF=0.7967405819・payoff=1.0853237849。部分API研究であり未送信候補を全体評価に含めない。RR2も既存報告参照。新APIは不要。
3. BB原型/BB2回復/W-M：`agent_runs/bb_alternatives_2020_2025_20260925/results.json`、同ディレクトリ各取引JSON。7通貨・2020–2025、旧往復1/1.2pip。`docs/bb_night_rr1_20261007.md`には比較BB・レンジBB・H1順行の条件付き時計研究が不採用と記載され、比較BB PF=0.698（2020–2022）、0.679（2023–2024）。JST実適合は時計不足。

旧費用・判断足・最大保有・終了条件が異なるため、異なる研究のPFを横並びにして同条件の優劣と扱わない。目標RRと実現payoffは別指標。

## 再現コマンドと終了状態

リポジトリルート、PowerShell。初回はOLE浮動小数点の下限一致で先頭M1を除いてしまいassert失敗(exit 1)。既存core同様に下限を1秒手前として検索した再実行はexit 0で、上記全件一致を確認した。以下は修正後の再現コード。旧研究ファイルは変更していない。

```powershell
$env:PYTHONPATH='src;scripts'
@'
import hashlib,json
from pathlib import Path
from datetime import datetime
import numpy as np
from forextester_backtest.data import HistoryRepository,_to_ole
r=HistoryRepository(); root=Path('agent_runs/ytt_monthly5_fx_20261009')
for m in json.loads((root/'run_manifest.json').read_text())['inputs']:
    s=m['symbol']; path=root/(s+'_execution.npz')
    z=np.load(path,allow_pickle=False); t=z['times']; p=z['prices']; c=z['complete']
    raw=r.root/s/'Bars.dat'; n=r.summary(s).bar_count
    assert hashlib.file_digest(raw.open('rb'),'sha256').hexdigest()==m['raw_sha256']
    a=np.memmap(raw,mode='r',dtype='<f8',offset=4,shape=(n,6))
    epoch=_to_ole(datetime(1970,1,1))
    lo,hi=np.searchsorted(a[:,0],[(t[0]-1)/86400+epoch,(t[-1]+900)/86400+epoch])
    rt=np.rint((a[lo:hi,0]-epoch)*86400).astype(np.int64)
    rp=np.array(a[lo:hi][:,[1,3,4,2]])
    for tt,pp,width in [(t,p,900),(rt,rp,60)]:
        assert (np.diff(tt)>0).all() and (tt%width==0).all()
        assert np.isfinite(pp).all() and (pp>0).all()
        assert (pp[:,1]>=pp[:,[0,3]].max(axis=1)).all()
        assert (pp[:,2]<=pp[:,[0,3]].min(axis=1)).all()
    labels=rt//900*900
    starts=np.r_[0,np.flatnonzero(np.diff(labels))+1]; ends=np.r_[starts[1:],len(rt)]
    ap=np.column_stack([rp[starts,0],np.maximum.reduceat(rp[:,1],starts),
                       np.minimum.reduceat(rp[:,2],starts),rp[ends-1,3]])
    valid=(ends-starts==15)&(rt[starts]==labels[starts])&(rt[ends-1]==labels[starts]+840)
    assert np.array_equal(labels[starts],t) and np.array_equal(ap,p)
    assert np.array_equal(valid,c)
    assert np.array_equal(rt[starts],z['observed_open_times'])
    assert np.array_equal(rt[starts]==t,z['starts_at_open'])
    print(s,len(rt),len(t),int(c.sum()),hashlib.sha256(path.read_bytes()).hexdigest())
print('READ_ONLY_ALL_SELECTED_ROWS_PASS')
'@ | python -
```

次担当：研究責任者・研究担当。上記入力SHAと欠損・費用・時計・既閲覧制約を新protocolに固定する。
