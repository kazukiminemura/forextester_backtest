# Holy Grail first pullback — データ台帳

- 実験ID / 担当 / 次担当: `holy_grail_first_pullback_20260913` / quant_data / 研究責任者・研究開発・独立検証。
- 状態: `DATA_READY_WITH_LIMITATIONS`（11通貨を主母集団に推奨）。4通貨のBars/ticks整合には `NEEDS_EVIDENCE`。
- 調査日: 2026-09-13 JST。主データ源: `C:\ForexTester6\data\History`。
- 入力識別子: `HistoryRepository`で銘柄・metadata・有効件数・端点を取得し、同じ48バイト形式をread-only NumPy memmapで全件検査。Python 3.12.10 / NumPy 2.2.6。
- 変更したファイル / 成果物: この文書のみ。原Bars.dat / ticks.dat / info.datへの書込みなし。外部データへの代替なし。
- 実注文: なし。戦略成績・採用判定は本担当の成果に含まない。

## 適用可能期間と母集団

15主要FXの端点上の共通期間は保存時刻2009-10-01 00:00〜2026-09-07 23:59。
今回の共通推奨読込範囲は **2009-10-01以上2026-08-31未満**。前半は指標初期化に使い、実際の取引開始条件は新戦略側で必要足数を満たすこと。
GBPJPYの2026-08-31桁異常が残るため、既存研究と比較できる保守的な共通終端を維持する。異常点を100倍補正したり、当日のみ削除して接続したりしない。

今回の45分のtick照合サンプルで、**CHFJPY / EURJPY / GBPJPY / USDCHF は全3サンプルでM1とtick Bid OHLCが不一致**。
この4通貨は内部OHLC検査に通っても価格系列の由来/同期を保証できない。原因確定まで主評価から隔離するデータ品質上の提案である。
主母集団に推奨する11通貨は **AUDJPY AUDUSD EURCHF EURGBP EURUSD GBPCHF GBPUSD NZDJPY NZDUSD USDCAD USDJPY**。
この11通貨も全期間tick一致を検査したわけではなく、Bid判定の根拠は各3分のサンプルである。
最終的な母集団は責任者が戦略結果を見る前にprotocolへ固定する。

EURCADは2018年4月だけ、EURHKDはExoticかつtickなしで今回の主要FX母集団に含めない。
CADJPYは銘柄一覧にない。30銘柄の一覧には株価・貴金属・暗号資産等もあるが、本監査の全件対象は下表の17 FXのみ。

## 現在のM1・tick台帳

下表のM1終了はEURCADを除き全通貨2026-09-07 23:59、EURCADのみ2018-04-30 23:59。
tick数/端点はRepositoryによるヘッダと端点の確認で、tick全件監査の結果ではない。

|通貨|M1開始（保存時刻）|全有効M1件数|tick件数|tick開始|tick終了|
|---|---|---:|---:|---|---|
|AUDJPY|2003-12-02 00:00|8,479,694|498,065,287|2003-12-02 00:00:16|2026-09-07 23:59:59|
|AUDUSD|2009-10-01 00:00|6,286,639|289,757,770|2009-10-01 00:00:03|2026-09-07 23:59:46|
|CHFJPY|2001-01-02 23:01|9,186,886|485,791,468|2003-08-05 00:00:07|2026-09-07 23:59:59|
|EURCHF|2003-08-05 00:00|8,521,427|328,634,791|2003-08-05 00:00:02|2026-09-07 23:59:49|
|EURGBP|2003-08-05 00:00|8,539,321|371,132,475|2003-08-05 00:00:00|2026-09-07 23:59:47|
|EURJPY|2001-01-02 23:01|9,240,341|639,155,484|2003-08-05 00:00:05|2026-09-07 23:59:59|
|EURUSD|2003-05-06 00:00|8,567,792|462,163,350|2003-05-06 00:00:05|2026-09-07 23:59:55|
|GBPCHF|2003-08-15 08:55|8,588,587|474,674,768|2003-08-15 08:55:04|2026-09-07 23:59:59|
|GBPJPY|2001-01-02 23:01|9,274,454|609,845,224|2003-08-05 00:00:06|2026-09-07 23:59:59|
|GBPUSD|2003-05-06 00:00|8,680,197|448,346,540|2003-05-06 00:00:19|2026-09-07 23:59:55|
|NZDJPY|2006-01-04 00:00|7,624,497|358,421,038|2006-01-04 00:00:05|2026-09-07 23:59:59|
|NZDUSD|2003-08-05 00:00|8,572,858|275,916,080|2003-08-05 00:00:14|2026-09-07 23:59:59|
|USDCAD|2003-08-05 00:00|8,594,859|335,993,773|2003-08-05 00:00:01|2026-09-07 23:59:41|
|USDCHF|2001-01-02 23:01|9,226,394|315,149,861|2003-05-06 00:00:13|2026-09-07 23:59:59|
|USDJPY|2003-05-06 00:00|8,534,100|422,111,274|2003-05-06 00:00:05|2026-09-07 23:59:59|
|EURCAD|2018-04-01 21:00|30,404|0|なし|なし|
|EURHKD|2007-03-14 00:00|7,199,617|0|なし|なし|

## 全件検査と欠損診断

17 FXの有効M1 **135,148,067本**を全件検査した。主要15 FXは127,918,046本。
時刻/OHLC/volumeの非有限値、非正OHLC、内部OHLC違反（H>=O/C/L、L<=O/C）、
分単位時刻の重複/逆順、分格子外時刻はすべて0。
OLE浮動小数の誤差を除くため、分へ丸めて時刻順を検査した。予約スロットは対象外。
価格格子検査はmetadata decimalsへ丸めた距離で判定し、GBPJPYの1,435 M1だけに違反。
原M1の全件検査であって、すべての品質リスクを網羅した保証ではない。

始値/直前終値比が0.8未満または1.2超のジャンプはGBPJPYの2点のみ：

|時刻|直前終値|始値|
|---|---:|---:|
|2026-08-31 00:00|216.792|2.16791|
|2026-09-01 00:00|2.16436|216.435|

この閾値では小さな誤配信やBars/ticks不一致は検出できない。17銘柄それぞれのBars.dat/ticks.dat/info.datのsize/mtime_nsは監査前後で一致した。全ファイルの暗号学的な前後一致を検査したという意味ではない。

以下は2009-10-01以上2026-08-31未満の原M1全件。15主要FX合計94,074,062本。
時計上不在分には正常な週末・休場を含む。配信元の営業日/休日/稼働予定表がないため、真の欠落本数への分類は未確認。

|通貨|対象M1|1分超ギャップ数|時計上不在分|最大ギャップ分|spread pips|主評価の品質提案|
|---|---:|---:|---:|---:|---:|---|
|AUDJPY|6,310,405|6,786|2,585,915|4,325|1.4|制約付き利用|
|AUDUSD|6,278,131|23,484|2,618,189|4,624|1.2|制約付き利用|
|CHFJPY|6,195,935|11,995|2,700,385|4,931|1.8|Bars/ticks不一致で隔離|
|EURCHF|6,287,846|23,741|2,608,474|4,325|1.7|制約付き利用|
|EURGBP|6,301,384|12,882|2,594,936|4,325|1.4|制約付き利用|
|EURJPY|6,201,223|10,070|2,695,097|4,932|1.3|Bars/ticks不一致で隔離|
|EURUSD|6,305,142|16,606|2,591,178|4,321|1.1|制約付き利用|
|GBPCHF|6,296,309|9,370|2,600,011|4,327|1.6|制約付き利用|
|GBPJPY|6,204,197|9,161|2,692,123|4,931|1.8|Bars/ticks不一致で隔離|
|GBPUSD|6,309,023|11,252|2,587,297|4,321|1.4|制約付き利用|
|NZDJPY|6,296,645|13,567|2,599,675|4,325|1.7|制約付き利用|
|NZDUSD|6,292,217|19,394|2,604,103|4,325|1.4|制約付き利用|
|USDCAD|6,300,640|15,647|2,595,680|4,325|1.5|制約付き利用|
|USDCHF|6,200,016|8,093|2,696,304|4,931|1.5|Bars/ticks不一致で隔離|
|USDJPY|6,294,949|19,028|2,601,371|4,325|1.2|制約付き利用|

最大ギャップが7日未満であることは完全性の保証ではない。欠損M1/日付を補間しない。
欠損を跨ぐシグナル状態、発注期限、始値ギャップ、未完足の扱いは新実験仕様で固定する。
Repositoryは構成M1が不足した集約足も返すため、「H1がある=60 M1完備」と仮定しない。

## 時刻・集約・価格種別

`data.py`はOLE_EPOCH=1899-12-30を起点にnaive datetimeへ変換し、時刻帯やDST変換を行わない。
info.datに時間帯/DSTを示すキーはなく、保存時刻をUTCと断定しない。NY17時区切りやTradingView特定配信元との足境界一致も未確認。

Repositoryの集約はOLE基準のバケット始点ラベル。15mは00/15/30/45分、H1は毎時00分、H4は保存日付00/04/08/12/16/20時、D1は保存日付00時。
足のラベルは完成時刻ではない。シグナルは構成元M1の時刻と期間終了を確認して確定足だけで生成する。
`bars(end=...)`は終了時刻を包含するので、今回の終端未満は別途 `time < 2026-08-31` で適用する。

EURUSD/GBPJPYの2024-01-02各1日を15m/H1/H4/D1へ集約し、計254足について構成M1から別計算したOHLCVが全件一致した。これは **2通貨各1日のサンプル集約検査** で、対象全期間の集約監査ではない。
RepositoryのD1は日曜を独立に返す。前の日足研究が使ったSunday→Monday統合を今回に暗黙適用しない。採用する場合は実時刻順で合成し、翌月曜へ移したラベルにも排他的終端を適用して、2026-08-30 stubを8/31完成日足と誤認しない。

Bars.datはOpen, Close, High, Low順で、Bid/Ask区別のフィールドを持たない。ticks.datをRepositoryはBid/Askとして読む。
価格種別の追加検査は15通貨×2015-06-01 / 2023-06-01 / 2024-01-02の各12:00〜12:01未満、計45分のサンプル。
11通貨の33サンプルはM1 OHLCとtick Bid OHLCが完全一致した。残る4通貨の12サンプルは不一致：

|通貨|2015-06-01最大差pips|2023-06-01最大差pips|2024-01-02最大差pips|
|---|---:|---:|---:|
|CHFJPY|7.9|74.8|46.2|
|EURJPY|9.7|26.4|12.1|
|GBPJPY|6.4|21.5|13.4|
|USDCHF|4.2|7.5|9.1|

差は対応O/H/L/Cの絶対差の最大を研究pipで割ったもの。
例：GBPJPYの2024-01-02 12:00のM1 O/H/L/Cは全179.650だが、144 ticksのBid OHLCは179.584/179.596/179.516/179.516、Ask OHLCも一致しない。
同時刻EURUSDは124 ticksでBid OHLCが完全一致しAskは不一致。初回この2分ではBid>Askとtick時刻逆順は0。
残るtickの全件順序・重複・欠損・変動spreadを監査していない。4通貨について時刻ずれ・異なる履歴由来・粗い価格等の原因は未確定。
Barsとticksを同じ系列として混在約定検証すること、過去の別分の一致を全履歴のBid証明にすることはできない。

## 費用・lot・pip・クオートの根拠

主要15 FXのinfo.datを現在読取り、Broker=Advanced Data Feed、lot=100000、LotCurrency/BaseCurrency=銘柄先頭3文字、
ApplyCommission=0、CommPerLot=0、SwapLong/SwapShort=0を確認。
`models.py`はlotをlot_size、spread×10^(-decimals)をspread_price、6文字FX末尾3文字をpnl_currencyとして返す。
したがってクオートはJPY/CHF/GBP/CAD/USD（銘柄末尾の通貨）で、MarginCurrencyはクオート通貨の根拠には使わない。

pipはJPYクオート0.01、その他0.0001という研究定義である。
対象metadataはJPY decimals=3、その他5で、1pip=10 metadata points。上表のspreadは保存固定設定をpip換算した値。
metadataから実時間変動spreadや実約定スリッページを観測したとは言えない。
Bidベースの一定spreadモデルでは、ロング入口Ask/ショート出口Askに対応する1 spreadを往復全体へ反映する。
往復固定費用や追加slippageを設定する場合はmetadata観測値と研究上の仮定を分け、片道/往復単位をprotocolに記載する。
ApplyCommission=0やswap=0は保存設定で、実ブローカーの費用ゼロの証拠ではない。
保有を伴う場合の実swap時系列は未確認であり、仮想pips/暦日費用なら感度仮定として記録する。
異なるクオートのpips/金額を無換算で口座金額損益として足さない。

## 閲覧済み・未使用期間

`board.md`には2010–2018、2019–2022、2023–2026の別戦略検証・探索が記録されている。
日足研究の後半が未計算でも、他研究での閲覧と価格/品質検査は存在する。
本監査も全履歴を読み、2015/2023/2024の価格サンプルを確認した。
今回の戦略の結果を未計算の期間と、真に未使用の期間は別である。**既存履歴のどの過去期間も未使用とは保証しない**。
推奨終端後の2026-08-31〜09-07も今回異常診断で閲覧済みであり、未使用として再利用しない。

## 入力識別子

- `src/forextester_backtest/data.py` SHA256: `bbbe0e0212480ea463726eac437c5262f380a78cd57eeedbde5d55c088d14af0`
- `src/forextester_backtest/models.py` SHA256: `9a815c3b304a5df57dcd4036486b2bd6112f259be0720c75377cc3a44757b8b7`

次表は2009-10-01以上2026-08-31未満の有効48バイトM1レコード列のSHA256。
原ファイル全体のSHAではなく、ヘッダ・予約スロット・範囲外レコードは含まない。

|通貨|研究領域SHA256|
|---|---|
|AUDJPY|`b294f1c2069bf9f1e5e319de49425309c10061b4b2ca8c49d7161a83d5dc66d1`|
|AUDUSD|`be6c2b9c32c62b76ceac796a17c43bf2ce6c5d8f038556eb49ea7eed3c0395e3`|
|CHFJPY|`9b2e142629c7c144a85a718715c6b2faabf5f03a7c6969e0491865e09b5b1352`|
|EURCHF|`cd2a4ff693ae6e4847916726c2c22114b28acdcee5c318c38d6f267a898c1825`|
|EURGBP|`b9af2fea3d18d03b881e8a0c419a414a365a5ac56defb1f1b209882b5cd0ea90`|
|EURJPY|`f8fd9d03a9317ed49d4f4db818924d3ee7f266f5b32b57db04c614185a55c6f4`|
|EURUSD|`7ef9d33800fcbe04fe0c6833426aeed4455e7e17edc91fe2d73c0e5efa193471`|
|GBPCHF|`c8b26109d028c517531f88b481ca0d500456a7dcce34dca36816e31388b1d472`|
|GBPJPY|`05521a6ac1aae7f9ead7caabc1399f621391974bf3b41e88f99406946613ea41`|
|GBPUSD|`9219f69f94579ea2c44cb729f505a145fb9dc5d98d272a0107b65a53fba72536`|
|NZDJPY|`a134675ac7dcb8ff4b5ec7ccdfe030151e1e3697869b30a28352be925124720f`|
|NZDUSD|`108d1a941a650d39fea4ca7cee41487b403f6f2e75ba72982b4624cf508cf08c`|
|USDCAD|`4ca8fd5325fd5da98a9465c1c5a71d13c4e6c2ec7777aa0adccc2ac086f3e064`|
|USDCHF|`a0f733e04a160a386994a4f9e1e5f6030dd283b2b2d1215ded3c7d07b3ee89da`|
|USDJPY|`ae6db69af975e7b3f0395e64462169cc20ea72a2c879f1f3b52f6c1b45405343`|
|EURCAD|`b6f723084cb60ccf3b122b3e4374725709531af15533068d1a56af4bc4a2c877`|
|EURHKD|`cb6926584e91630ba21b4a768f623602d7e9bac70921a53648ea9caab954246c`|

## 再現コマンドと終了コード

作業ディレクトリはリポジトリ直下。以下3コマンドを実走し、すべて **終了コード0**。
第1は `DATA_AUDIT_COMPLETED`、第2は `SAMPLE_AGGREGATION_TICKS_COMPLETED`、第3は `EXTENDED_TICK_SAMPLE_COMPLETED` まで完了した。
出力はこの文書の数値と入力識別子へ転記。外部ファイルの作成・更新は行わない。
第1の実行中、ツール側の未定義終了コードの保存で出力転送エラーが1回発生したが、Pythonプロセスは継続し最終exit0を確認した。

### 1. 全有効M1監査

```powershell
$env:PYTHONPATH='src'
@'
from forextester_backtest.data import HistoryRepository, OLE_EPOCH, _to_datetime
from dataclasses import asdict
from pathlib import Path
from datetime import datetime
import numpy as np,json,hashlib,sys
r=HistoryRepository()
print(json.dumps({'python':sys.version.split()[0],'numpy':np.__version__,'symbols':r.symbols()}),flush=True)
pairs='AUDJPY AUDUSD CHFJPY EURCHF EURGBP EURJPY EURUSD GBPCHF GBPJPY GBPUSD NZDJPY NZDUSD USDCAD USDCHF USDJPY EURCAD EURHKD'.split()
lo=(datetime(2009,10,1)-OLE_EPOCH).total_seconds()/86400
hi=(datetime(2026,8,31)-OLE_EPOCH).total_seconds()/86400
for s in pairs:
 summary=r.summary(s); meta=r.metadata(s); p=r.root/s/'Bars.dat'
 before={n:(r.root/s/n).stat() for n in ['Bars.dat','ticks.dat','info.dat']}
 a=np.memmap(p,mode='r',dtype='<f8',offset=4,shape=(summary.bar_count,6))
 t=a[:,0]; minutes=np.rint(t*1440).astype(np.int64); delta=np.diff(minutes)
 prices=a[:,1:5]; o,c,h,l=prices.T
 bad_grid=np.any(np.abs(prices*10**meta.decimals-np.rint(prices*10**meta.decimals))>1e-5,axis=1)
 jumps=np.flatnonzero((o[1:]/c[:-1]<0.8)|(o[1:]/c[:-1]>1.2))+1
 left,right=int(np.searchsorted(t,lo)),int(np.searchsorted(t,hi))
 use=a[left:right]; dm=np.diff(minutes[left:right])
 pip=0.01 if s.endswith('JPY') else 0.0001
 out=asdict(summary)
 out.update(metadata=meta.values,pip=pip,spread_pips=meta.spread_price/pip,quote_currency=meta.pnl_currency,
 nonfinite=int(np.count_nonzero(~np.isfinite(a))),nonpositive_ohlc=int(np.count_nonzero(prices<=0)),
 ohlc_bad=int(np.count_nonzero((h<o)|(h<c)|(h<l)|(l>o)|(l>c))),
 duplicate_minutes=int(np.count_nonzero(delta==0)),reverse_minutes=int(np.count_nonzero(delta<0)),
 off_minute_grid=int(np.count_nonzero(np.abs(t*1440-minutes)>1e-5)),
 price_grid_bad=int(bad_grid.sum()),
 jumps=[{'time':str(_to_datetime(t[i])),'previous_close':float(c[i-1]),'open':float(o[i])} for i in jumps],
 study_rows=right-left,study_price_grid_bad=int(bad_grid[left:right].sum()),
 gap_count=int(np.count_nonzero(dm>1)),clock_absent_minutes=int(np.maximum(dm-1,0).sum()),
 max_gap_minutes=int(dm.max()) if len(dm) else 0,study_sha256=hashlib.sha256(use.tobytes()).hexdigest(),
 source_stats={n:{'size':v.st_size,'mtime_ns':v.st_mtime_ns} for n,v in before.items()},
 source_unchanged=all((v.st_size,v.st_mtime_ns)==((r.root/s/n).stat().st_size,(r.root/s/n).stat().st_mtime_ns) for n,v in before.items()))
 assert out['source_unchanged']
 print(json.dumps(out,default=str),flush=True)
 del a,prices,o,c,h,l,t,use
print('DATA_AUDIT_COMPLETED',flush=True)
'@ | python -
```

### 2. 集約と初回tickサンプル

```powershell
$env:PYTHONPATH='src'
@'
from forextester_backtest.data import HistoryRepository
from datetime import datetime,timedelta
from pathlib import Path
import json,hashlib
r=HistoryRepository()
for s in ['EURUSD','GBPJPY']:
 start=datetime(2024,1,2,12); end=start+timedelta(minutes=1)-timedelta(microseconds=1)
 bs=list(r.bars(s,start,end)); ts=list(r.ticks(s,start,end))
 b=bs[0]; bid=[t.bid for t in ts]; ask=[t.ask for t in ts]
 def ohlc(v): return [v[0],max(v),min(v),v[-1]]
 print(json.dumps({'symbol':s,'sample_minute':str(start),'m1_ohlc':[b.open,b.high,b.low,b.close],'ticks':len(ts),'bid_ohlc':ohlc(bid),'ask_ohlc':ohlc(ask),'bid_matches':ohlc(bid)==[b.open,b.high,b.low,b.close],'ask_matches':ohlc(ask)==[b.open,b.high,b.low,b.close],'bid_gt_ask':sum(x.bid>x.ask for x in ts),'tick_reverse':sum(x.time>y.time for x,y in zip(ts,ts[1:]))}))
 raw=list(r.bars(s,datetime(2024,1,2),datetime(2024,1,2,23,59)))
 for tf,minutes in [('15m',15),('1h',60),('4h',240),('1d',1440)]:
  agg=list(r.bars(s,datetime(2024,1,2),datetime(2024,1,2,23,59),tf))
  for a in agg:
   included=[b for b in raw if a.time<=b.time<a.time+timedelta(minutes=minutes)]
   assert [a.open,a.high,a.low,a.close,a.volume]==[included[0].open,max(b.high for b in included),min(b.low for b in included),included[-1].close,sum(b.volume for b in included)]
  print(json.dumps({'symbol':s,'sample_day':'2024-01-02','timeframe':tf,'aggregated_bars':len(agg),'all_sample_ohlcv_match':True,'first_label':str(agg[0].time),'last_label':str(agg[-1].time)}))
for f in ['src/forextester_backtest/data.py','src/forextester_backtest/models.py']:
 print(f,hashlib.sha256(Path(f).read_bytes()).hexdigest())
print('SAMPLE_AGGREGATION_TICKS_COMPLETED')

'@ | python -
```

### 3. 15通貨の追加tickサンプル

```powershell
$env:PYTHONPATH='src'
@'
from forextester_backtest.data import HistoryRepository
from datetime import datetime,timedelta
import json
r=HistoryRepository()
pairs='AUDJPY AUDUSD CHFJPY EURCHF EURGBP EURJPY EURUSD GBPCHF GBPJPY GBPUSD NZDJPY NZDUSD USDCAD USDCHF USDJPY'.split()
for day in ['2015-06-01','2023-06-01','2024-01-02']:
 for s in pairs:
  dt=datetime.fromisoformat(day+' 12:00:00'); end=dt+timedelta(minutes=1)-timedelta(microseconds=1)
  bs=list(r.bars(s,dt,end)); ticks=list(r.ticks(s,dt,end))
  if not bs or not ticks:
   print(json.dumps({'symbol':s,'minute':str(dt),'bars':len(bs),'ticks':len(ticks)})); continue
  b=bs[0]; q=[x.bid for x in ticks]; actual=[b.open,b.high,b.low,b.close]; tick=[q[0],max(q),min(q),q[-1]]
  print(json.dumps({'symbol':s,'minute':str(dt),'ticks':len(ticks),'bid_match':actual==tick,'max_diff_pips':max(abs(x-y) for x,y in zip(actual,tick))/(.01 if s.endswith('JPY') else .0001),'bars_ohlc':actual,'tick_bid_ohlc':tick}))
print('EXTENDED_TICK_SAMPLE_COMPLETED')

'@ | python -
```

## 次担当へ渡してよい範囲

11通貨・保存時刻の推奨共通範囲で、費用/時刻/不完全足/未使用性の制約をprotocolに固定したM1ベースの研究へ渡せる。
4通貨は価格由来/同期の証拠が得られるまで主評価から隔離する提案。全期間tick品質、実配信時刻帯、実約定コスト、実swap、TradingView配信元との一致は未確認。
次工程で今回採用する集約足の全件検査と指標ウォームアップ・確定時刻・足内約定順序の検証を行う。

