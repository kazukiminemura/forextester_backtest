# BTCUSD データ台帳 — 2026-10-07

- 実験ID / 担当 / 次担当: `btc_spot_rr1_20261007` / quant_data / 研究開発・独立検証
- 状態: ローカルBTCUSDあり。構造品質の全M1検査完了。現物取引所データ・時刻・全価格sideは未確認。
- 入力: `C:/ForexTester6/data/History/BTCUSD/{Bars.dat,ticks.dat,info.dat}`。読取は既存 `src/forextester_backtest/data.py` の `HistoryRepository` を優先。
- 変更したファイル / 成果物: 本文書のみ。原データの補完・修正なし。cache作成は研究開発担当。
- 実行結果: 本文の監査に対応するPowerShell/Python読取コマンドはすべて終了コード0。損益・戦略成績・採用判定は計算していない。
- 次工程に渡してよい範囲: 当該FT履歴での買いのみ・非レバレッジ模擬。現物取引所約定を再現した結果とは扱えない。
- 実注文: なし。

## 1. データの存在・識別子

`HistoryRepository.symbols()` がBTCUSDを認識。BTC以外は本実験の対象外。Bars/ticksは非空。

|入力|有効レコード|開始（保存時計）|終了（保存時計）|bytes|
|---|---:|---|---|---:|
|Bars.dat M1|4,309,797|2017-05-09 02:00:00|2026-10-06 23:59:00|206,880,772|
|ticks.dat|455,152,746|2017-05-09 02:00:00|2026-10-06 23:59:59|12,744,480,004|
|info.dat|設定テキスト|—|—|326|

ファイル先頭uint32 countは上記有効件数と一致。Barsは4,310,016スロットのうち末尾219、ticksは455,160,000スロットのうち末尾7,254が全バイト0の予約領域。予約領域を実際の欠損足として数えない。

|ファイル|SHA256|mtime_ns|
|---|---|---:|
|Bars.dat|`886ebaa8249eaa3ce84ae16a32c706fb1db3a3e51e3fa4120e997b05d732be9e`|1791370606804472900|
|ticks.dat|`4dce0fd41f5531cd76b3d4188adeeba3ab13d6cba91778f207c8934282dd7f2d`|1791370624227634200|
|info.dat|`f9b6ddb5627c113ddec848e4ae84176a120bdea8b104f00b73db50c2f0b0b813`|1620240062000000000|

最初の存在確認と監査後で全3ファイルのsize/mtime一致。Bars/infoは別読取のSHAが一致。ticksは全バイトSHAを初回M1監査後に初めて取得した。その後、本文の再現コマンドで全M1監査を再実行し、全3ファイルのsize/mtime/SHAが前回読取と一致した（終了コード0）。初回監査より前のticks SHAは取得していない。全バイトhashは全レコードの品質検査を意味しない。

## 2. 全M1検査と適用期間

有効M1 **4,309,797件すべて** を `HistoryRepository.bars('BTCUSD')` で検査した。サンプル検査ではない。

|項目|結果|
|---|---:|
|OHLC不整合 (`low <= min(open,close) <= max(open,close) <= high` 違反)|0|
|OHLC/volume非有限|0|
|OHLC非正値 / 負volume|0 / 0|
|時刻逆転 / 隣接同時刻|0 / 0|
|分境界外（秒・マイクロ秒）|0|
|60秒を超える隣接間隔|35,988|
|24時間365日を基準とする内部の欠落分|640,803|
|隣接close→openが倍率1.1超で変化|14（すべて空白時間を跨ぐ）|

時刻が厳密昇順なので非隣接重複もない。欠落は最初～最後の間を毎分期待した算術差であり、配信元休場か欠損かは判別していない。0件OHLC不整合は相場価格の正しさを証明しない。14件の大きな変動を自動的な異常価格・修復対象とはしない。

最大間隔は4,322分（2017-12-29 21:59→2018-01-01 22:01、間の欠落4,321分）。2017–2019年は**土曜足が0件**。BTC現物の連続24/7履歴としての利用には重大な制約がある。

|年|M1件数|土曜件数|日曜件数|その年の最初～最後の内部欠落分|
|---|---:|---:|---:|---:|
|2017|224,482|0|4,891|113,678|
|2018|365,060|0|7,063|159,100|
|2019|370,282|0|8,308|153,879|
|2020|421,030|22,836|29,484|104,628|
|2021|523,366|74,682|74,719|493|
|2022|488,131|61,143|60,573|36,208|
|2023|482,288|64,450|65,851|41,900|
|2024|518,788|72,197|72,385|6,439|
|2025|522,102|74,552|73,247|2,112|
|2026（10/6まで）|394,268|55,623|57,390|6,652|

年別内部欠落には年を跨ぐ空白を含まないため、合計は全期間欠落と一致しない。

物理的適用範囲は2017-05-09 02:00～2026-10-06 23:59。責任者の区分は2017年をwarmup、2018–2020年、2021–2023年、2024–2026-10-06の3評価区分。いずれも空白時間を含むため連続完全データの区分ではない。空白内でのTP/SL到達はM1で観察不能。補完しないこと、空白跨ぎの約定規則、指標warmup、保有中の空白扱いを結果前に固定する必要がある。

過去のBTC閲覧・探索履歴を網羅的に確認していない。今回は全期間の品質と端点を閲覧した。3区分を未使用holdoutと保証しない。

## 3. 時刻と1h/4h集約

`data.py` はOLE epoch `1899-12-30` からのnaive datetimeを返す。timezone/DSTオフセットはinfo.datにない。**UTC/JST/取引所時刻のいずれとも断定しない。** Unix秒への変換時も `naive_datetime - naive_epoch` とし、OSのlocal timezone解釈を混入させない。

`_aggregate_bars` はOLE基準の整数秒floorで左端ラベルを付ける。1hは毎時00分、4hは保存時計の00/04/08/12/16/20時開始。終端は排他的に考え、確定情報が利用可能になる時刻はラベル+時間幅。`bars(end=...)` 自体はend時刻を含むため、実験の排他endを明示的に扱う必要がある。

|集約幅|観察されたbucket|M1全数あり|部分bucket|規定件数超過|
|---|---:|---:|---:|---:|
|1h|72,960|65,256|7,704|0|
|4h|18,496|14,877|3,619|0|

これは全M1をbucketに数えた全件監査。重複なし・分境界一致も確認したため、60/240件bucketは各分を満たす。観察ゼロのbucketは表のbucket件数に含まない。既存Repositoryは部分bucketも返すので、完全足要件がある実装は件数を別途判定すること。

Repository集約を2026-10-06の1日でサンプル確認: 1h 24本（00:00～23:00）、4h 6本（00:00～20:00）。集約OHLCと独立実装の全足照合は本担当では行っていない。

## 4. 商品・費用・価格sideの根拠

info.dat実値:

```text
name=BTCUSD
type=0
decimals=3
spread=60643
lot=100000
LotCurrency=BTC
BaseCurrency=BTC
SwapLong=0.0000
SwapShort=0.0000
MinDistToPrice=60643
Margin=1000.00
HedgedMargin=500.00
MarginCurrency=BTC
Broker=Advanced Data Feed
CreditShoulder=100
UseCreditShoulder=1
CommPerLot=0.00
ApplyCommission=0
group=Crypto
```

1. `models.InstrumentMetadata.spread_price` により60643×10^-3 = **60.643価格単位**。クオートをUSDと解釈する場合は60.643 USD/BTC。これは静的metadataであり過去全期間の実測spreadではない。
2. `lot_size=100000` はFT設定の1 lotあたりBTC単位。現物枚数へ無批判に流用しない。手数料0・swap0もFT設定であり現物取引所料金の保証ではない。
3. `decimals=3` から表示point=0.001。ただし**暗号資産pipの契約定義は未確認**。JPY銘柄向けpip変換を使わず、BTC数量とUSD価格差で計算するのが再現可能。
4. quote USDは`BTCUSD`識別子と`models.py`の末尾3文字規則による推定。明示QuoteCurrencyはない。BaseCurrency/LotCurrencyはBTC。MarginCurrency=BTCを損益クオートUSDの根拠には使わない。
5. Broker=Advanced Data Feed、証拠金とレバレッジ設定あり。type=0の契約上の意味は未検証。**現物配信と保証できず、CFD契約と断定する根拠も不足**。元取引所・約定可能性・出金可能BTC所有権は不明。

### Tickは限定サンプル検査

3つの1時間窓の計**25,422 tickのみ**を検査。全455,152,746 tickの検査ではない。

|保存時計の開始（1時間、終端排他）|tick数|不正bid/ask・逆転|同一時刻の隣接tick|spread最小/最大/平均|M1 bid OHLC一致|
|---|---:|---:|---:|---|---:|
|2017-05-09 02:00|8,326|0|5,857|0 / 44.1 / 3.725102|56/60|
|2021-01-04 00:00|15,256|0|11,813|0.9 / 55.7 / 45.735370|56/60|
|2026-10-06 00:00|1,840|0|644|50 / 50 / 50|60/60|

同一時刻は秒分解能内の複数tickの可能性があり、同一内容重複と断定しない。bid/askは有限正値かつask>=bidを確認。180 M1中172本がtickのbid OHLCと許容誤差1e-6以内で一致した。8本は不一致で原因未確定。最初の窓でaskとmidも各1本一致するが、side判定を反転する証拠にはならない。**bid主体を示唆する限定証拠であり全M1のside確認ではない。** 不一致8本を修復していない。

静的60.643とサンプルの実測spreadは異なる。バックテストで60.643を使う場合、固定仮定のシナリオと明記する。現物手数料・slippageは別の仮定として固定し、実測と呼ばない。

## 5. 再現コマンド

リポジトリrootでPowerShellから実行。Pythonと既存パッケージを使用し、原ファイルは読取のみ。全M1品質、bucket数、年/曜日、hashを再出力する:

```powershell
@'
from forextester_backtest.data import HistoryRepository, OLE_EPOCH
from dataclasses import asdict
from collections import Counter
import math, json, hashlib, struct
r=HistoryRepository(); s=r.summary('BTCUSD'); root=r.root/'BTCUSD'
out={'summary':asdict(s),'invalid_ohlc':0,'nonfinite':0,'nonpositive':0,
     'negative_volume':0,'duplicate_adjacent':0,'backward':0,'off_minute':0,
     'gaps':0,'missing_minutes_24x7':0,'large_jumps':[], 'years':{},'longest_gaps':[]}
buckets={60:Counter(),240:Counter()}; previous=None
for b in r.bars('BTCUSD'):
    vals=[b.open,b.high,b.low,b.close,b.volume]
    out['invalid_ohlc']+=not(b.low<=min(b.open,b.close)<=max(b.open,b.close)<=b.high)
    out['nonfinite']+=not all(math.isfinite(v) for v in vals)
    out['nonpositive']+=min(vals[:4])<=0
    out['negative_volume']+=b.volume<0
    out['off_minute']+=bool(b.time.second or b.time.microsecond)
    y=out['years'].setdefault(str(b.time.year),{'first':b.time,'last':b.time,'bars':0,'weekdays':Counter()})
    y['last']=b.time; y['bars']+=1; y['weekdays'][b.time.strftime('%A')]+=1
    for m,c in buckets.items(): c[int((b.time-OLE_EPOCH).total_seconds())//(m*60)]+=1
    if previous:
        dt=(b.time-previous.time).total_seconds()
        out['duplicate_adjacent']+=dt==0; out['backward']+=dt<0
        if dt>60:
            out['gaps']+=1; out['missing_minutes_24x7']+=round(dt/60)-1
            out['longest_gaps'].append((dt/60,str(previous.time),str(b.time)))
            out['longest_gaps']=sorted(out['longest_gaps'],reverse=True)[:10]
        if min(previous.close,b.open)>0 and abs(math.log(b.open/previous.close))>math.log(1.1):
            out['large_jumps'].append((str(previous.time),previous.close,str(b.time),b.open))
    previous=b
for y in out['years'].values():
    y['missing_between_year_edges']=int((y['last']-y['first']).total_seconds()/60)+1-y['bars']
out['aggregation']={m:{'buckets':len(c),'full_buckets':sum(v==m for v in c.values()),
    'partial_buckets':sum(v<m for v in c.values()),'excess_buckets':sum(v>m for v in c.values())} for m,c in buckets.items()}
out['metadata']=asdict(r.metadata('BTCUSD')); out['files']={}
for name,n,size in [('Bars.dat',s.bar_count,48),('ticks.dat',s.tick_count,28),('info.dat',0,0)]:
    p=root/name; st=p.stat()
    with p.open('rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
    entry={'size':st.st_size,'mtime_ns':st.st_mtime_ns,'sha256':sha}
    if size:
        with p.open('rb') as f:
            entry['header_count']=struct.unpack('<I',f.read(4))[0]
            f.seek(4+n*size); tail=f.read()
        entry.update(slots=(st.st_size-4)//size,padding_records=len(tail)//size,padding_all_zero=not any(tail))
    out['files'][name]=entry
print(json.dumps(out,default=str,indent=2))
'@ | python -
```

Tickと集約の限定サンプルを再現:

```powershell
@'
from forextester_backtest.data import HistoryRepository
from datetime import datetime,timedelta
from collections import Counter
import json,math
r=HistoryRepository(); out={}
for start in [datetime(2017,5,9,2),datetime(2021,1,4),datetime(2026,10,6)]:
    end=start+timedelta(hours=1)-timedelta(microseconds=1)
    ts=list(r.ticks('BTCUSD',start,end)); bs=list(r.bars('BTCUSD',start,end))
    groups={}; spreads=[]; bad=back=duplicate=0; previous=None
    for t in ts:
        if previous: back+=t.time<previous.time; duplicate+=t.time==previous.time
        previous=t
        bad+=not(all(math.isfinite(v) and v>0 for v in [t.bid,t.ask]) and t.ask>=t.bid)
        spreads.append(t.ask-t.bid)
        groups.setdefault(t.time.replace(second=0,microsecond=0),[]).append(t)
    matches=Counter()
    for b in bs:
        ticks=groups.get(b.time,[])
        if not ticks: continue
        for side in ['bid','ask','mid']:
            ps=[(t.bid+t.ask)/2 if side=='mid' else getattr(t,side) for t in ticks]
            if all(abs(a-z)<1e-6 for a,z in zip([b.open,b.high,b.low,b.close],[ps[0],max(ps),min(ps),ps[-1]])):
                matches[side]+=1
    out[str(start)]={'ticks':len(ts),'bars':len(bs),'invalid_ticks':bad,'backward':back,
        'same_timestamp_adjacent':duplicate,'spread_min':min(spreads),'spread_max':max(spreads),
        'spread_mean':sum(spreads)/len(spreads),'ohlc_full_matches':matches}
for tf in ['1h','4h']:
    bs=list(r.bars('BTCUSD',datetime(2026,10,6),datetime(2026,10,7)-timedelta(microseconds=1),tf))
    out[tf]={'count':len(bs),'first':str(bs[0].time),'last':str(bs[-1].time)}
print(json.dumps(out,indent=2))
'@ | python -
```

## 6. 未確認事項

1. 取引所・現物/デリバティブ契約種別・価格時刻のtimezone/DST・全M1のbid/ask/last種別。
2. tick全件の時刻順/重複/価格品質、8サンプルM1のtick OHLC不一致原因。
3. 実際の現物手数料、注文サイズ別slippage、現物lot/pip最小数量規則。
4. 過去探索・閲覧の網羅的記録と真の未使用評価期間。
5. 欠落時間中の価格経路。土曜なしの初期期間と近年の配信構造差は戦略期間比較に影響し得る。

## 7. 検査出力の主要数値（JSON）

本文の2つのPowerShellコードブロックをそのまま再実行し、初回と一致した。両方exit0。以下は再実行出力からの抜粋であり戦略結果ではない。

```json
{
  "symbol": "BTCUSD",
  "bar_count": 4309797,
  "tick_count": 455152746,
  "invalid_ohlc": 0,
  "nonfinite": 0,
  "nonpositive": 0,
  "negative_volume": 0,
  "duplicate_adjacent": 0,
  "backward": 0,
  "off_minute": 0,
  "gaps": 35988,
  "missing_minutes_24x7": 640803,
  "aggregation": {
    "60": {"buckets": 72960, "full_buckets": 65256, "partial_buckets": 7704, "excess_buckets": 0},
    "240": {"buckets": 18496, "full_buckets": 14877, "partial_buckets": 3619, "excess_buckets": 0}
  },
  "tick_sample_count": 25422,
  "sample_m1_bid_ohlc_matches": 172,
  "sample_m1_total": 180,
  "sample_invalid_ticks": 0,
  "sample_tick_backwards": 0
}
```
