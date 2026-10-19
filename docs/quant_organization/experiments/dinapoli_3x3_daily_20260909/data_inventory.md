# ディナポリ3×3日足研究 — データ台帳

- 実験ID / 担当 / 次担当: `dinapoli_3x3_daily_20260909` / quant_data / 研究責任者・研究開発・独立検証。
- 状態: DATA_READY_WITH_LIMITATIONS。2026-09-09現在のローカル履歴に基づく。
- 主データ源: `C:\ForexTester6\data\History`。HistoryRepositoryで銘柄・metadata・有効件数・端点を取得し、同じ固定長形式の有効レコードを読み取り専用NumPy memmapで全件検査。
- 編集範囲: この文書のみ。原Bars.dat / ticks.dat / info.datの変更なし、外部データ代替なし、実注文なし。
- 実行環境: Python 3.12.10、NumPy 2.2.6。data.py Git blob `7624b16695502ceea1535fee68168512eb9e08c1`、models.py `54d30eb0b0998f40c7808ed0cb224da07435e143`。
- 戦略成績・採用判定は本担当の成果に含めない。

## 適用可能期間と日足境界

研究責任者と固定した母集団は下表の15標準FX。共通履歴開始はAUDUSDに制約される2009-10-01、原M1の共通終了は2026-09-07 23:59。
本実験は2009-10-01〜2009-12-31をウォームアップ、取引日2010-01-01以上2026-08-31未満を評価範囲とする。
原保存時刻の2026-08-31以降は全通貨で打ち切り、さらに日曜→翌月曜への取引日付変換後にも終端を適用する。
したがって2026-08-30(日)のstubは除外され、実際の最後の評価日足は2026-08-28(金)。
8/30の短い足を完結した8/31日足とみなしてはいけない。

時刻はOLE_EPOCH=1899-12-30を起点にしたタイムゾーンなしdatetime。info.datには時刻帯/DSTの根拠がない。
保存値をUTCと断定せず、NY17時・TradingViewのブローカー日足との同一性も未確認。
現行Repositoryの1d集約は保存日付00:00開始の暦日足であり、日曜足を独立に返す。
本研究の5営業日日足は、保存日付が日曜の観測値を翌月曜の取引日に入れ、同じ取引日の時系列順にO=先頭、H=max、L=min、C=末尾、V=sumとする。
月曜ラベルの足は日曜夕方から始まり得るため、そのラベル00:00を足完成時刻として使ってはいけない。
確定日足のみシグナルに使い、次取引日の実際の観測始値が約定候補になる。
全対象の当範囲に土曜の観測日は0。欠けた暦日を合成せず、日曜統合後にも月曜の観測が少ない日などは残る。

15通貨それぞれの観測日付集合は完全一致ではない。2009Q4込みで全15通貨に実在する統合日付の積集合は4,389日、2009-10-01〜2026-08-28。
これは各通貨に実在する全日足数とは異なる。足数を合わせるための補間・前値補完・結果後の日付選別はしない。
下表の日足数は日付キーの全件集計であり、統合後OHLCを全日付について独立再計算照合した結果ではない。

## 現データ一覧

全15通貨のM1終了は2026-09-07 23:59。spreadはinfo.datの固定設定をpip換算した値。

|通貨|M1開始|原M1全有効件数|spread pips|2009Q4込み統合D1|2010以降統合D1|統合対象日曜数|
|---|---|---:|---:|---:|---:|---:|
|AUDJPY|2003-12-02 00:00|8,479,694|1.4|4,408|4,342|877|
|AUDUSD|2009-10-01 00:00|6,286,639|1.2|4,407|4,342|877|
|CHFJPY|2001-01-02 23:01|9,186,886|1.8|4,401|4,336|873|
|EURCHF|2003-08-05 00:00|8,521,427|1.7|4,410|4,344|878|
|EURGBP|2003-08-05 00:00|8,539,321|1.4|4,407|4,341|878|
|EURJPY|2001-01-02 23:01|9,240,341|1.3|4,401|4,336|873|
|EURUSD|2003-05-06 00:00|8,567,792|1.1|4,410|4,344|878|
|GBPCHF|2003-08-15 08:55|8,588,587|1.6|4,407|4,341|875|
|GBPJPY|2001-01-02 23:01|9,274,454|1.8|4,402|4,337|873|
|GBPUSD|2003-05-06 00:00|8,680,197|1.4|4,410|4,344|877|
|NZDJPY|2006-01-04 00:00|7,624,497|1.7|4,408|4,342|876|
|NZDUSD|2003-08-05 00:00|8,572,858|1.4|4,409|4,343|875|
|USDCAD|2003-08-05 00:00|8,594,859|1.5|4,409|4,343|878|
|USDCHF|2001-01-02 23:01|9,226,394|1.5|4,399|4,334|873|
|USDJPY|2003-05-06 00:00|8,534,100|1.2|4,408|4,343|880|

日曜数は原保存日付2009-10-01以上2026-08-31未満に存在する数で、最後の8/30を含む。D1数はその日曜を翌月曜へ移したあと8/31を除外した数。
その他FXはEURCAD（2018-04-01 21:00〜2018-04-30 23:59、30,404本、tick 0件）とEURHKD（2007-03-14〜2026-09-07 23:59、7,199,617本、tick 0件）。
EURCADは長期不足、EURHKDはExoticで今回の15標準通貨から除外。CADJPYは一覧に存在しない。
既存の2026-09-08初回台帳にあったNZDJPY短期間・各通貨7月までという記述は現在のファイル状態では更新済みである。

## 全件検査と欠損診断

17 FXすべてのBars.dat有効レコード全件について、非有限時刻、時刻重複、逆順、非正/非有限OHLC、H>=O/C/LとL<=O/Cの内部整合違反は各0。
時刻差はOLE浮動小数誤差を除くため分へ丸めて比較した。予約済み未使用スロットは監査対象外。
価格グリッド違反はGBPJPYの1,435 M1のみ。他16通貨は0。GBPJPYも今回の原保存時刻8/31未満では0。
始値/直前終値比が0.8未満または1.2超となる大幅ジャンプはGBPJPYの下記2点のみ。
このしきい値検査は小さな誤配信や実市場価格との一致を保証しない。原ファイルのサイズ・更新時刻は各全件スキャン前後で一致した。

以下は2009-10-01以上2026-08-31未満の原M1全件診断（日曜を含む）。
「時計上不在分」は連続分時計との差であり、正常な週末・休場を含む。真の欠損本数として解釈しない。
営業日/祝日/配信元の稼働予定表がないため、配信欠落と休場の完全な分類は未確認。

|通貨|対象M1|1分超ギャップ数|時計上不在分|最大ギャップ分|暦日数|60 M1未満の暦日数|
|---|---:|---:|---:|---:|---:|---:|
|AUDJPY|6,310,405|6,786|2,585,915|4,325|5,284|3|
|AUDUSD|6,278,131|23,484|2,618,189|4,624|5,282|4|
|CHFJPY|6,195,935|11,995|2,700,385|4,931|5,272|88|
|EURCHF|6,287,846|23,741|2,608,474|4,325|5,287|3|
|EURGBP|6,301,384|12,882|2,594,936|4,325|5,284|3|
|EURJPY|6,201,223|10,070|2,695,097|4,932|5,272|89|
|EURUSD|6,305,142|16,606|2,591,178|4,321|5,288|3|
|GBPCHF|6,296,309|9,370|2,600,011|4,327|5,281|0|
|GBPJPY|6,204,197|9,161|2,692,123|4,931|5,274|85|
|GBPUSD|6,309,023|11,252|2,587,297|4,321|5,286|3|
|NZDJPY|6,296,645|13,567|2,599,675|4,325|5,283|3|
|NZDUSD|6,292,217|19,394|2,604,103|4,325|5,282|2|
|USDCAD|6,300,640|15,647|2,595,680|4,325|5,286|4|
|USDCHF|6,200,016|8,093|2,696,304|4,931|5,270|74|
|USDJPY|6,294,949|19,028|2,601,371|4,325|5,288|5|

最大ギャップはいずれも7日未満だが、それを完全性の保証としない。
EURUSDの1 M1だけの日は2019-05-26(日)、10本の日は2023-12-24(日)。
CHFJPY/GBPJPYの短い日曜足は冬季にも多数ある。これらはSunday mergeにより独立した「1日」として数えない。
日曜統合前に1440本未満を一律削除すると、多くの通常観測日まで落ちるため、その処理は採用しない。
欠損補間・前値補完はせず、欠損を跨ぐ次観測始値のギャップ約定処理と同足TP/SL順序は研究仕様で別途固定する。

## GBPJPY原データ異常と打ち切り

読み取り専用再確認で次の異常を原ファイルとRepository日足双方に確認した。

|時刻/足|値|
|---|---|
|2026-08-30の最後のM1終値|216.792|
|2026-08-31 00:00 M1始値|2.16791|
|2026-08-31保存暦日D1 OHLC|O 2.16791 / H 2.16794 / L 2.16076 / C 2.16436|
|2026-09-01 00:00 M1始値|216.435|

内部OHLCが整合していても桁異常は存在する。全体の「OHLC不整合0」と矛盾しない。
自動的に100倍補正せず、当該日だけを削って履歴を接続することもしない。
本実験は全15通貨同じ終端で打ち切る。将来データが修正されても、本識別子の実験入力を無記録で差し替えない。

## 価格と費用の根拠・限界

- 15通貨のinfo.datはBroker=Advanced Data Feed、lot=100000、LotCurrency/BaseCurrencyは銘柄先頭3文字、ApplyCommission=0、CommPerLot=0.00、SwapLong/SwapShort=0.0000。
- models.pyに従いspread_price=spread_points×10^(-decimals)。JPYクオートはdecimals=3、pip=0.01、その他はdecimals=5、pip=0.0001を本研究の定義とする。したがって全15通貨で1 pip=10 metadata points。
- lot_size=100000はmetadataの設定。クオート通貨はmodels.pyの6文字FX銘柄末尾3文字によるJPY/USD/CHF/GBP/CAD。異なるクオート通貨の金額やpipsを無換算で口座損益として合算しない。
- 設定上commission_per_lot=0は実ブローカー手数料ゼロの証明ではない。メタデータのswap=0も実際の日跨ぎ費用の証明ではなく、日足研究では別途費用仮定と感応度を固定する必要がある。
- Bars.dat自体にはBid/Askの価格種別フィールドがない。data.pyは保存OHLCをそのまま読む。ticks.datは同実装でBid/Askとして解釈している。
- 2026-08-28 12:00の1分サンプルではEURUSD 66 ticksのBid OHLCがM1 OHLC=(1.16450,1.16460,1.16450,1.16450)に一致、Askは一致しない。GBPJPY 192 ticksもBid OHLC=(216.868,216.876,216.855,216.872)に一致。Bidベースの研究モデルを支えるサンプル証拠であり全期間の価格種別検証ではない。
- 同じUSDJPYの1分にはM1があるがRepository.ticks取得0。tick全件の時刻順・欠損・M1との整合は未監査なので、真のtick欠損か読込前提の問題かをこのサンプルだけで確定しない。tick端点があることは全期間tick約定検証の成立を意味しない。
- 最終Bid/Ask約定コスト、変動spread、slippage、日跨ぎswap、換算通貨、足内約定はデータ台帳だけでは確定できない。

## 過去の閲覧状態

現ワークツリーの `experiments/quant70_20260908/protocol.json` は2010–2018 / 2019–2022 / 2023–2024 / 2025–2026の区分と「confirmationは未使用と保証しない」を記録。
board.mdおよび `quant70_intraday_jpy_refreshed_20260908` はNZDJPYを含む円クロスの長期評価、他の実験は2023–2026のUSD主要通貨/EURJPY/GBPJPYの既閲覧を記録している。
したがって今回の過去期間を真の未使用holdoutと呼ばない。USDCAD/EURGBPのより古い期間など、閲覧記録の網羅性が未確認な部分も未使用とは保証しない。
今回、データ担当が全履歴の品質指標・日付数と一部OHLCを確認したことも閲覧記録に含める。

## 入力指紋

SHA256はヘッダを除く、有効件数×48バイトの連続レコード領域全体。ファイル全体SHA256ではない。
同じヘッダ解析結果と件数・端点を合わせて用いる。unused予約スロットは含まない。

|通貨|有効レコードSHA256|
|---|---|
|AUDJPY|a53f4c76d47ebcaf21199f1680a6a1e9c593a477a67c0a89d6e396e8d0034c5f|
|AUDUSD|995ff4fe6ed43c0c01b0a60b4a69f9ed60f2d83d45b6aa6e789c5d5b4d6682ba|
|CHFJPY|bd1da344612f25c2059c0875cf6a0d588e8c1e08f84d19230f50e1c2125eb300|
|EURCHF|77b8bf733ae02dfe2a182a4639ae39a67d3d19fe6120a34cf8755c4ed7afa901|
|EURGBP|80adaf85e585e7456412c21464c9c39cd2c931d13fee6750aede04966e7a0ce8|
|EURJPY|964ea16277fde682db3fc4f1a2b3cdea601e4498406ae70920e9d71cf656d2ff|
|EURUSD|02ca11b946a0c68bf0a51d9216a11f680608b9c9eb8cba939b83bf57ec40d50b|
|GBPCHF|6e987e26ae3fdd1a26de6027dff93efc97b695ae6052ec45f235058959ac8a82|
|GBPJPY|ffce0eec0cf3f0680435a2d0d0db43e4a78a3fb23e13e768d3bb03af766cefe6|
|GBPUSD|9247c65f89f99ab1c381e0b69b256147f42b4ad0a11f936d73e7c6f1ccf31d99|
|NZDJPY|c74b0936d131754e2dc767c6720545c53b801d7d172efefb54f287de17cb6cba|
|NZDUSD|0a8ff97e8f121a35ecf4ff1c38fde5ccf8d5a4c4ffcefa709920f6bd27202bce|
|USDCAD|4abe8900a128924d2f847b95efc2c72ccf568cdf14ca5e0c13a74e9da9538fb5|
|USDCHF|3a39377363305568910e145d4bcf1fd12339ef4228cec1b83dcea34d1ce9beab|
|USDJPY|4e01788e2be154ef59586b5ea4a190cb9dbca85f8f8cd6edd68cee103bfb88d4|

## 再現コマンド・終了コード

作業ディレクトリは本リポジトリ。下記全件監査は実行終了コード0。
初回監査コマンドの `weekday_day_counts` だけは曜日ラベルの対応に誤りがあったため、そのフィールドを結果に採用せず、後掲のMon始まり再集計で修正確認した。他の診断値に影響しない。

```powershell
$env:PYTHONPATH='src'; @'
from forextester_backtest.data import HistoryRepository, OLE_EPOCH
from datetime import datetime,timedelta
import numpy as np,json,hashlib
r=HistoryRepository(); start=(datetime(2009,10,1)-OLE_EPOCH).days; end=(datetime(2026,8,31)-OLE_EPOCH).days
pairs=[s for s in r.symbols() if r.metadata(s).values.get('group') in ('Majors','Crosses','Exotic')]
for s in pairs:
 summary=r.summary(s); path=r.root/s/'Bars.dat'; before=path.stat()
 a=np.memmap(path,dtype='<f8',mode='r',offset=4,shape=(summary.bar_count,6)); t=a[:,0]; p=a[:,1:5]
 dt=np.rint(np.diff(t)*1440).astype('int64'); days=np.floor(t).astype('int64')
 b=a[(t>=start)&(t<end)]; bd=np.floor(b[:,0]).astype('int64'); unique,ix,n=np.unique(bd,return_index=True,return_counts=True)
 diff=np.rint(np.diff(b[:,0])*1440).astype('int64'); jump=np.flatnonzero((a[1:,1]/a[:-1,2]<.8)|(a[1:,1]/a[:-1,2]>1.2))+1
 bad=((p<=0)|(~np.isfinite(p))).any(axis=1)|(a[:,3]<np.maximum(a[:,1],a[:,2]))|(a[:,4]>np.minimum(a[:,1],a[:,2]))|(a[:,3]<a[:,4])
 badix=np.flatnonzero(bad)
 pip=.01 if s.endswith('JPY') else .0001
 grid=np.max(np.abs(p*10**r.metadata(s).decimals-np.rint(p*10**r.metadata(s).decimals)),axis=1)>.00001
 out={'symbol':s,'full_n':len(a),'sha256_active_records':hashlib.sha256(a).hexdigest(),'bytes':before.st_size,'mtime_ns':before.st_mtime_ns,'nonfinite_time':int((~np.isfinite(t)).sum()),'duplicate_times':int((dt==0).sum()),'backwards':int((dt<0).sum()),'bad_ohlc':int(bad.sum()),'bad_first':[str(OLE_EPOCH+timedelta(days=float(t[i]))) for i in badix[:3]],'offgrid_bars':int(grid.sum()),'offgrid_in_range':int(grid[(t>=start)&(t<end)].sum()),'big_jumps':[(str(OLE_EPOCH+timedelta(days=float(t[i]))),float(a[i-1,2]),float(a[i,1])) for i in jump[:12]],'range_m1':len(b),'range_days':len(unique),'range_first':str(OLE_EPOCH+timedelta(days=int(unique[0]))),'range_last':str(OLE_EPOCH+timedelta(days=int(unique[-1]))),'gap_events_gt1m':int((diff>1).sum()),'missing_clock_minutes':int((diff[diff>1]-1).sum()),'largest_gap_minutes':int(diff.max()),'days_lt60m1':int((n<60).sum()),'days_lt1440m1':int((n<1440).sum()),'weekday_day_counts':{(OLE_EPOCH+timedelta(days=i)).strftime('%A'):int(sum(((unique+5)%7)==i)) for i in range(7)},'min_daily_m1':int(n.min()),'max_daily_m1':int(n.max()),'unchanged_stat':before.st_size==path.stat().st_size and before.st_mtime_ns==path.stat().st_mtime_ns}
 print(json.dumps(out),flush=True)
 del a,b,p,t
'@ | python -
```

日曜統合後の数と最終日を確認したコマンド（終了コード0）:

```powershell
$env:PYTHONPATH='src'; @'
from forextester_backtest.data import HistoryRepository,OLE_EPOCH
from datetime import datetime,timedelta
import numpy as np,json
r=HistoryRepository(); start=(datetime(2009,10,1)-OLE_EPOCH).days; end=(datetime(2026,8,31)-OLE_EPOCH).days
all_dates=[]
for s in r.symbols():
 if r.metadata(s).values.get('group') not in ('Majors','Crosses') or s=='EURCAD': continue
 a=np.memmap(r.root/s/'Bars.dat',dtype='<f8',mode='r',offset=4,shape=(r.summary(s).bar_count,6)); d=np.floor(a[:,0]).astype('int64'); d=d[(d>=start)&(d<end)]; u,n=np.unique(d,return_counts=True); sunday=(u+5)%7==6; merged=u+sunday; eligible=merged<end; md=np.unique(merged[eligible]); all_dates.append(md)
 print(json.dumps({'symbol':s,'sunday_days':int(sunday.sum()),'sunday_m1':int(n[sunday].sum()),'drop_final_sunday_m1':int(n[~eligible].sum()),'merged_d1':len(md),'last_trading_date':str((OLE_EPOCH+timedelta(days=int(md[-1]))).date()),'days2010plus':int((md>=(datetime(2010,1,1)-OLE_EPOCH).days).sum())}))
common=all_dates[0]
for d in all_dates[1:]: common=np.intersect1d(common,d)
print('COMMON_ACTUALLY_PRESENT_MERGED_DATES',len(common),str((OLE_EPOCH+timedelta(days=int(common[0]))).date()),str((OLE_EPOCH+timedelta(days=int(common[-1]))).date()))
'@ | python -
```

tick/Bidサンプル・D1異常・曜日ラベルを確認したコマンド（終了コード0）。
初回はUSDJPY tick 0件を非空と仮定してIndexError、終了コード1。以下は空リストを明示した再実行であり、欠損を埋めていない。

```powershell
$env:PYTHONPATH='src'; @'
from forextester_backtest.data import HistoryRepository,OLE_EPOCH
from datetime import datetime,timedelta
from dataclasses import asdict
import numpy as np,json
r=HistoryRepository()
for s in ['EURUSD','USDJPY','GBPJPY']:
 start=datetime(2026,8,28,12); end=start+timedelta(minutes=1)-timedelta(microseconds=1)
 b=list(r.bars(s,start,end)); ts=list(r.ticks(s,start,end)); bid=[x.bid for x in ts]; ask=[x.ask for x in ts]
 print(json.dumps({'symbol':s,'bars':[asdict(x) for x in b],'ticks':len(ts),'bid_ohlc':[bid[0],max(bid),min(bid),bid[-1]] if bid else None,'ask_ohlc':[ask[0],max(ask),min(ask),ask[-1]] if ask else None,'d1_sample':[asdict(x) for x in r.bars(s,datetime(2026,8,28),datetime(2026,9,1,23,59),timeframe='1d')]},default=str))
for s in ['EURUSD','GBPJPY','CHFJPY']:
 a=np.memmap(r.root/s/'Bars.dat',dtype='<f8',mode='r',offset=4,shape=(r.summary(s).bar_count,6)); d=np.floor(a[:,0]).astype(int); u,n=np.unique(d[(d>=(datetime(2009,10,1)-OLE_EPOCH).days)&(d<(datetime(2026,8,31)-OLE_EPOCH).days)],return_counts=True)
 print(json.dumps({'symbol':s,'weekday_counts':{name:int(np.sum((u+5)%7==i)) for i,name in enumerate(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])},'short_days_lt60':[(str((OLE_EPOCH+timedelta(days=int(day))).date()),int(count)) for day,count in zip(u,n) if count<60][:12]}))
'@ | python -
```

端点・metadata取得は `HistoryRepository.summary/metadata` と `dataclasses.asdict` の銘柄別JSON出力、終了コード0。
ローカル文書確認は `git diff --check -- docs/quant_organization/experiments/dinapoli_3x3_daily_20260909/data_inventory.md`。
新規未追跡文書はdiffだけでは本文検証されないため、実ファイル存在と表行数/コードフェンスも確認する。

次工程へ渡せる範囲は、上記15通貨・固定取引日期間・Sunday merge・既閲覧扱い・費用と配信時刻の限界を保持した再現可能な研究入力。
実市場同等性、tick全件、TradingView配信元日足一致、最終戦略実装の集約/約定一致は次担当で別途検証する。

