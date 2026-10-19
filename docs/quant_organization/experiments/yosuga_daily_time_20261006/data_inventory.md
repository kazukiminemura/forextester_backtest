# 日・時間の取引休止研究：データ台帳と仕様レビュー

調査日: 2026-10-06。担当: quant_data。状態: `DATA_READY_WITH_LIMITATIONS`。
編集責任は本書のみ。原履歴、保存キャッシュ、旧研究、実装、protocolは変更していない。
この台帳はデータの利用可能性と日次品質条件を扱い、戦略成績・採用判定を作成しない。

## 入力と監査範囲

主データ源は `C:/ForexTester6/data/History`。端点・件数・metadataの現物確認に
`src/forextester_backtest/data.py` の `HistoryRepository.summary/metadata` を使用した。
再利用入力は `agent_runs/bb_alternatives_2020_2025_20260925/<symbol>_features.npz` の
`times` と `features[:, :4]`（OHLC）。残りの特徴量を今回の条件へ流用しない。
構成M1完全性は `agent_runs/yosuga_channel_20261003/completed/<symbol>_complete_m5.npz`
の `complete` を使用する。

出典は [旧データ台帳](../yosuga_channel_20261003/data_inventory.md)、
[旧protocol](../yosuga_channel_20261003/protocol.json)、元キャッシュの `data_manifest.json`、
旧実走の `completed/run_manifest.json`。運営規約とboardも確認した。

今回の現物監査は以下の範囲で完了した（終了コード0）。

- 保存M5キャッシュ7件、完全性mask7件、info.dat7件の全bytes SHA256は保存manifestと **21/21一致**。
- 原Bars.datは7件ともファイルサイズ・mtime_nsが保存manifestと一致。今回、原Bars全bytes SHA256は再計算していない。サイズ・mtime一致だけで内容完全一致を保証しない。
- 保存M5 **3,182,106本を全件検査**。非有限・非正OHLC、包絡違反、高値<安値、重複時刻、逆転、300秒グリッド外はいずれも0件。
- 原M1の2019-12から2025末の全件OHLC監査・元M1から全保存M5の完全再集計一致は、2026-10-03の旧台帳にある過去の検証結果。今回の再実行とは区別する。
- 原M1全履歴、2026年OHLC、全tickの品質を今回全件検査していない。tickはAPIが返す件数と端点のみ確認。市場稼働カレンダーとの全gap照合は未実施。

## 利用可能な期間・足

全7通貨の保存M5は2019-12-01 22:00から2025-12-31 21:55まで。
2019-12をウォームアップとして2020-01-01以上2026-01-01未満を評価できる。
時刻はすべて保存時計。UTCを意味しない。原履歴の最終M1は、今回のAPI確認でも全7通貨が2026-09-07 23:59。

|通貨|原M1全件数|保存M5|完全M5|完全M15|完全H4|完全24時間日|M5間隔300秒超|
|---|---:|---:|---:|---:|---:|---:|---:|
|USDJPY|8,534,100|455,085|446,773|145,410|7,007|95|415|
|EURUSD|8,567,792|455,004|445,417|144,440|6,840|79|441|
|GBPUSD|8,680,197|454,932|447,550|146,152|7,369|138|447|
|AUDUSD|6,286,639|454,115|443,670|143,970|7,216|34|491|
|NZDUSD|8,572,858|454,315|442,249|142,862|6,890|33|557|
|AUDJPY|8,479,694|454,390|450,179|148,211|7,722|105|503|
|NZDJPY|7,624,497|454,265|449,430|147,977|7,696|53|525|

完全M15/H4/日欄は、今回保存M5とmaskから算定した利用可能bucket数。
別の保存H4ファイルを監査したという意味ではない。範囲には2019-12を含む。
各幅の境界から連続した所定本数のM5が存在し、全構成M5のM1完全性maskがtrueであることを要求した。
M5の間隔超には週末・祝日・その他欠損が混在するため、全件を市場休場とは扱わない。

日次状態の前提を「1440本M1がすべてある日」にすると、約6年の保存範囲で通貨ごと33〜138日しか残らない。
このため本研究は完全日ではなく、事前固定した研究用の許容欠損条件を用いる。
これは不明な価格を補完したことや、真の日中高安が回復できたことを意味しない。

## 時刻・日境界・2026年の扱い

`data.py` はOLE日時をtimezoneなしdatetimeへ変換する。全7通貨のinfo.datに
time/zone/GMT/DSTを含むキーは今回見つからなかった。保存時計のUTCとの差、JST換算、DST履歴を確定できない。
1970年からの秒表現も時刻帯の証拠ではない。

1. 今回は保存時計00:00境界のカレンダー日、保存時計上の直近確定12本M5を使用できる。
   実市場の東京・ロンドン・NY時間や、日中/夜間の日本時間での意味を付けない。
2. 曜日・固定時刻窓を追加する場合も保存時計の定義に限定する。実市場時刻やTradingViewの実時刻と同一に扱うには、元時計の歴史的offset/DSTの根拠を先に確定する必要がある。
3. 集約ラベルは足開始。M5確定は開始+300秒、M15は開始+900秒。
   `HistoryRepository.bars(end=...)` は終端を包含するので、半開期間は別途保証する。
4. 2026年は初期再構築に必須ではない。追加するなら既存原履歴から別キャッシュを生成し、その範囲の品質監査を追加する。
   2026-09-08以降、特に10月の朝シナリオの履歴再現は今回確認した原履歴ではできない。
5. 2020〜2025は既閲覧。2026にも旧研究の閲覧記録があり、追加しただけで未使用holdoutとは保証できない。

## 日次品質条件の独立レビュー

レビュー対象は本実験の `protocol.json`（`last_offset_min_seconds=84300` の版）。
指定された品質閾値の間に論理的な矛盾は認めなかった。
ただし品質閾値は完全性の証明ではなく研究用の許容基準であり、以下の限界を伴う。

|条件|意味・残る制約|
|---|---|
|observed_min=270|24時間最大288本のうち最大18本のM5全欠落を許容する。実際の市場稼働時間を証明する基準ではない。|
|complete_min=260|M1が完全なM5を最低260本要求。観測M5にはM1不完全な足を含み得る。|
|first_offset_max_seconds=1800|前日最初のM5開始が00:30以内。日初の未観測価格が残り得る。|
|last_offset_min_seconds=84300|前日最後のM5開始が23:25以降、観測終値の名目確定が23:30以降。日末最大30分が未観測の可能性。23:25を23:30開始と取り違えない。|
|max_gap_seconds=1800|隣接する観測M5の開始時刻間隔を最大30分にする。内部で最大25分相当のM5全欠落を許容する。M5内部M1の欠損は別のcomplete条件で扱う。|

日初・日末条件は端の不足、max_gapは日内の隣接観測間隔、observed/completeは全体の観測数を扱う。
相互に代用しない。すべてM5開始時刻を基準に計算し、価格値の有限性/OHLC整合が成立する入力を使う。
各日がこれらの条件を満たす頻度や戦略成績を見て閾値を変更してはいけない。

前日は「直前カレンダー日」。週末を飛び越えて金曜日へ置き換えない。
直前日が欠落または品質不適合なら日次gateを休止する。月曜日などの除外はこのルールの帰結であり、曜日別成績からの選抜ではない。
前日品質・方向は前日終了後にのみ利用し、当日の最終高安や欠損件数を当日途中へ遡及適用しない。

日跨ぎ新規入場拒否は **signal足開始の保存時計日 != actual next-openの保存時計日** とする明確化が妥当。追補されたprotocolの文言でも確認した。
例: 23:55開始M5の確定で出たsignalを翌00:00に入場させる場合は拒否する。
「signal確定日の比較」にするとこの例を通すため同じ仕様ではない。
既存の次足連続性条件は併用し、gateがoffでも保有中のSL/TPと出口処理は継続する。

初回レビュー時点で `daily/hourly efficiency` の数式、方向ゼロ、分母ゼロの処理が未記載だったため、研究責任者へ明文化を依頼した。
追補された `efficiency_definition` に `abs(last_close-first_open)/(max_high-min_low)`、
高安幅ゼロまたは方向ゼロなら停止、方向は `sign(last_close-first_open)` と明記されたことを再確認した。
日次は直前カレンダー日の全観測M5、時間状態はsignal確定までの連続・完全12本M5を使う。
この範囲は過去の確定情報から再現できる。未観測価格のため日次の高安幅と効率が変わり得る限界は残る。
追補 `quality_threshold_rationale` も、事前固定の許容欠損、未最適化、完全日保証なし、閾値感度未検証を明記している。
本データ・日次品質仕様レビューの範囲で未解消の論理的矛盾はない。実装一致・戦略結果の判定は独立検証担当の責任範囲。

## 価格・費用と入力制約

info.datのBrokerは全7通貨 `Advanced Data Feed`、lot_size=100000、commission設定0。
OHLCのBid/Ask側は未確定。tickのbid/askとOHLCの全照合は行っていない。
設定spreadはUSDJPY 1.2、EURUSD 1.1、GBPUSD 1.4、AUDUSD 1.2、NZDUSD 1.4、AUDJPY 1.4、NZDJPY 1.7 pips。
これは歴史的実測spreadではない。JPYペアはpip=0.01/tick=0.001、他4通貨はpip=0.0001/tick=0.00001。
quote通貨はJPYペアJPY、他4通貨USD（metadata APIの6文字銘柄末尾3文字による）。
等R/等pipを換算済み口座利益と表示しない。commission/swap設定0も実口座の歴史的費用0を保証しない。

## 再現コマンド

以下は今回の小監査と同じ検査。保存M5全件と入力hashを確認し、原BarsはstatとAPI端点だけを読む。
原M1全再監査のコマンドは旧データ台帳の再現コマンド節にある。

```powershell
$env:PYTHONPATH='src'
@'
import json, hashlib
from pathlib import Path
from dataclasses import asdict
import numpy as np
from forextester_backtest.data import HistoryRepository
b=Path('agent_runs/bb_alternatives_2020_2025_20260925')
c=Path('agent_runs/yosuga_channel_20261003/completed')
r=HistoryRepository()
inputs={e['symbol']:e for e in json.loads((c/'run_manifest.json').read_text())['inputs']}
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
for q in json.loads((b/'data_manifest.json').read_text()):
    s=q['symbol']; raw=Path(q['raw_path']); st=raw.stat()
    cache=b/(s+'_features.npz'); mask=c/(s+'_complete_m5.npz')
    assert sha(cache)==q['cache_sha256']
    assert sha(mask)==inputs[s]['mask_sha256']
    assert sha(raw.parent/'info.dat')==q['metadata_sha256']
    with np.load(cache,allow_pickle=False) as z: t=z['times']; a=z['features'][:,:4]
    with np.load(mask,allow_pickle=False) as z: complete=z['complete']
    assert len(t)==len(complete)
    bad=(~np.isfinite(a)).any(axis=1)|(a<=0).any(axis=1)
    bad|=(a[:,1]<a[:,2])|(a[:,1]<np.maximum(a[:,0],a[:,3]))|(a[:,2]>np.minimum(a[:,0],a[:,3]))
    assert not bad.any() and (np.diff(t)>0).all() and (t%300==0).all()
    counts={}
    for width in (900,14400,86400):
        bucket=t//width*width
        starts=np.r_[0,np.flatnonzero(np.diff(bucket))+1]; ends=np.r_[starts[1:],len(t)]
        full=(ends-starts==width//300)&(t[starts]==bucket[starts])&(t[ends-1]==bucket[starts]+width-300)
        prefix=np.r_[0,np.cumsum(~complete)]
        full&=prefix[ends]-prefix[starts]==0
        counts[str(width)]=int(full.sum())
    print(json.dumps(dict(symbol=s,summary=asdict(r.summary(s)),
        raw_stat_unchanged=st.st_size==q['raw_stat']['bytes'] and st.st_mtime_ns==q['raw_stat']['mtime_ns'],
        m5=len(t),complete_m5=int(complete.sum()),full_buckets=counts,
        gaps_m5=int((np.diff(t)>300).sum())),default=str))
'@ | python -
```

次担当: 研究責任者と研究開発。時刻基準、日次許容欠損、効率の数式を凍結し、独立検証で境界動作を確認する。
今回のデータ調査では市場データ再取得、外部API課金、戦略実走、実注文を行っていない。
