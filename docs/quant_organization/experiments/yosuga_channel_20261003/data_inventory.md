# よすが式チャンネル再構築：データ・既存実装台帳

調査日 2026-10-03。担当 quant_data、次担当 研究責任者・研究開発・独立検証。
状態 `DATA_READY_WITH_LIMITATIONS`。原履歴・既存コード・旧成果物は読取専用。今回の変更はこの文書のみ。戦略成績や採用判定は作成していない。

## 最短の入力経路

主データ源は `C:\ForexTester6\data\History`。`src/forextester_backtest/data.py` の `HistoryRepository` を使用する。既存で同APIから作成された保存M5は `agent_runs/bb_alternatives_2020_2025_20260925/<symbol>_features.npz`。キー `times` は元時計を1970-01-01からの秒として数値化した配列、`features[:, :4]` は Open/High/Low/Close。BB等の残り11列をよすが式の条件へ無条件流用しない。

対象候補は USDJPY/EURUSD/GBPUSD/AUDUSD/NZDUSD/AUDJPY/NZDJPY、2019-12ウォームアップ＋2020–2025本評価。7通貨すべてキャッシュの先頭は2019-12-01 22:00、最終M5は2025-12-31 21:55。元M1末尾は21:58。開始/終了時刻は保存時計でありUTCではない。

この期間区分は入力候補であり研究計画の凍結ではない。より長い指標の初期化に必要ならウォームアップを別途増やす。今回は原履歴から新しいキャッシュを作成していない。

## 今回の現物確認

`HistoryRepository.summary/metadata` で端点・有効件数・設定を取得。7通貨の原Bars.dat全bytes、info.dat全bytes、保存NPZ全bytesのSHA256を再計算し、既存 `agent_runs/bb_alternatives_2020_2025_20260925/data_manifest.json` と **21/21一致**。元Bars.datの2019-12-01以上2026-01-01未満をread-only NumPy memmapで全件監査した。価格検査はこの選択期間の全件であり、全履歴・全tickの品質監査ではない。

|通貨|全M1開始|全M1件数|選択範囲M1|保存M5|60秒超の間隔|5本未満のM5|設定spread pips|
|---|---|---:|---:|---:|---:|---:|---:|
|USDJPY|2003-05-06|8,534,100|2,263,374|455,085|8,948|8,312|1.2|
|EURUSD|2003-05-06|8,567,792|2,261,333|455,004|10,386|9,587|1.1|
|GBPUSD|2003-05-06|8,680,197|2,263,639|454,932|7,996|7,382|1.4|
|AUDUSD|2009-10-01|6,286,639|2,254,834|454,115|11,237|10,445|1.2|
|NZDUSD|2003-08-05|8,572,858|2,253,046|454,315|13,036|12,066|1.4|
|AUDJPY|2003-12-02|8,479,694|2,264,688|454,390|4,638|4,211|1.4|
|NZDJPY|2006-01-04|7,624,497|2,262,305|454,265|5,266|4,835|1.7|

全履歴の最終M1は7通貨とも2026-09-07 23:59。選択範囲の最初M1はすべて2019-12-01 22:00、最後は2025-12-31 21:58。2026年部分は今回のOHLC監査範囲外。

全7通貨の選択M1で非有限値、非正OHLC、包絡違反、高値<安値、重複時刻、時刻逆転は **0件**。最大間隔はUSDJPY/EURUSD/GBPUSDが259,260秒、その他が259,500秒。間隔件数には週末・祝日を含み、市場稼働カレンダーとの照合は未実施。既存台帳にはAUDJPY/NZDJPYの2023-06-01 23:59以降にも248,700/248,760秒の空白が記録されており、全間隔を週末とみなさない。

今回、原M1を独立に5分bucketへ集計し、**全7通貨・全保存M5の時刻とOHLCが完全一致**した。5分内の最初open、最大high、最小low、最後close。5本未満のM5も既存方式どおり保持される。欠損補間はない。M5が連続していても内部M1やtickが完全とは限らない。

特に「完全M15」を連続3本のM5だけで判定すると、各M5内部の欠損M1を見逃す。保存NPZは構成M1数を持たないため、15本の連続M1まで保証したい場合は元M1から構成数/連続性を監査してから集約する必要がある。3本M5が揃う条件を採用する場合は「M5が3本あるM15」と表現し、全M1充足と区別する。

### 入力SHA256

原Bars.dat/metadataの完全識別子は一致を再確認した前記data_manifest.jsonを参照。以下は実際に再計算した保存M5のSHA256。

|通貨|SHA256|
|---|---|
|USDJPY|a0ea23715fdc88187195661181b402f3c05b480d0403eb2e42c5b64b2f144866|
|EURUSD|e2026fa0e136eef4a20fbab8098492e2f63fc251eee38be6eef782634ca2fe42|
|GBPUSD|7cf11d7c8f98e00f9b64f57fd1136af2873a7a7cfc9f01866e1b2113728dbc9c|
|AUDUSD|0b3c3ab7d89f23316b99cd2dce1b88c19f2ee4cd5fb70047a9c1aa292b13ea26|
|NZDUSD|eb77341cad4a4dd7f8190947930a54d20e4b9de439eb55a10e06efc7661ec914|
|AUDJPY|aec44b0b95598134765ff7eb9f7ef7fce2b5223aa0dfbe7a431e4ea9f054c08a|
|NZDJPY|1b08cc26f87b5a5351dba3e199e0f8a3dbaed2871caa61b6dc7c548420834417|

## 時刻・価格・費用の根拠と未確認事項

- `data.py` はOLE日時をtimezoneなしdatetimeへ変換する。元info.datにも今回確認した範囲で時刻帯の根拠はない。UTC/JST/DSTを確定できていない。旧市場セッションrunnerの `naive Forex Tester timestamps are UTC` は仮定の記載であり証明ではない。東京/ロンドン等の時計フィルターを今回引き継がない。
- `HistoryRepository` の集約はOLE_EPOCH基準の整数時間bucketで、ラベルは足開始時刻。M15/H1/H4の確定時刻は足開始＋足幅として扱う。未完成bucketの除外・構成足不足の取扱いは新仕様で明示する。`bars(end=...)` は終了日時を包含するため半開区間は別途処理する。
- info.datのBrokerは全7通貨 `Advanced Data Feed`。OHLCが実行可能なBid/Askのどちらかを今回資料だけで確定できない。ticks.dat APIはbid/askを区別するが全tick経路とOHLC照合は未実施。tickの件数・端点はsummaryだけを確認し、tick SHAや全件品質は確認していない。
- info.datのdecimalsはJPYペア3、USD建て5。tick単位は `10**(-decimals)`。既存研究のpip定義はJPYペア0.01、USD建て0.0001。spreadはinfo.datのpoints×tickで、表はそれをpip換算した静的設定値。歴史的実測spreadではない。
- 全7通貨の `lot=100000`、`ApplyCommission=0`、`CommPerLot=0`。これらは設定の事実であり実口座の無料手数料の証拠ではない。SwapLong/Shortも設定0だが歴史的スワップを再現しない。
- `models.InstrumentMetadata.pnl_currency` は6文字通貨の末尾3文字からquote通貨を求める。JPYペアはJPY、他4通貨はUSD。USD/JPYの金額を換算なしで合計しない。等pipや等R集計を口座通貨利益と表示しない。
- 2020–2025は既存よすが・BB等の研究で閲覧済み。2010–2026にも既存探索がある。今回の新ルールを初めて計算することと、真の未使用holdoutは別。真の未使用期間は保証できない。
- GBPJPYの2026-08-31桁異常はboardの既知問題。本7通貨・2025末までには含めない。他の通貨/2026年まで拡大する場合はその入力を追加監査する。

## 既存よすが資産と再利用境界

|資産|場所|今回の取扱い|
|---|---|---|
|旧ダウ・MA・上位足フィルター|scripts/research_yosuga_dow_filters.py、research_yosuga_dow_htf_filter.py|確定pivotの実装例。今回チャンネル一次資料との対応は再証明が必要|
|4H/15m/5m構造・PA|scripts/research_strict_rr_portfolio.py、research_yosuga_15m_entry_context.py、research_yosuga_5m_time_filters.py|旧yosuga_pa/yosuga_sweep/yosuga_15mは異なる機械化定義。新仕様の代用品にしない|
|既存資料|docs/yosuga_5m_rebuild.md、yosuga_15m_entry_context_research.md等|旧研究の範囲・閲覧履歴の確認用。新成績の証拠に流用しない|
|Pine|scripts/tradingview/yosuga_dow_expectancy_indicator.pine、yosuga_5m_rebuilt_indicator.pine等|過去に実装された表示・機械化。チャンネルの正式再現や実機検証の保証なし|
|旧保存結果|scripts/yosuga_*_results.json、strict_rr_portfolio_*_yosuga*_results.json|保存継続。新実験で上書きしない|

`research_strict_rr_portfolio._simulate` は翌足始値/1R/同足SL優先を扱う一方、ストップ超えgapの損失も固定−1Rとし、期末まで決済しない保有を取引一覧へ記録しない。今回の最終会計へそのまま利用するには不足がある。

より新しい `scripts/research_bb3_jev_engine.py:simulate` は決定的な次始値約定、gap約定、同足SL優先、費用、含みMTM、未決済状態を扱う再利用候補。`scripts/research_bb_alternatives.py:execute` のW/M adapterは固定SLを `target=2*fill-stop_anchor` へ写す例を持つ。ただし既定の最小値幅・300秒連続性・BB由来のtarget設計等に依存するため、そのまま「汎用よすがエンジン」とはしない。新仕様が合う場合に限定し、独立担当がgap/同足両到達/期末/費用/確定足を確認する。

最小の新研究経路は、保存NPZのOHLC/時刻のみ読込→確定情報だけでM15/H1/H4等を構築→今回の出典に対応した新signalsを別ファイル生成→仕様に適合する決定的会計→別experiment出力。M5より細かい約定が必要ならHistoryRepositoryの対象M1を読む。今回のデータ担当はこの実装・売買評価を行っていない。

## 再現コマンド

作業場所はリポジトリルート。以下は実行済み2つのPython読取監査を統合した同等コマンド。実行した2監査はいずれも終了コード0、21 hash一致・全7集約一致。探索時にPowerShellのrgへワイルドカードを直接渡した呼出しが失敗したが、ファイル探索を訂正済みでデータ監査とは無関係。

```powershell
$env:PYTHONPATH='src'
@'
import json, hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
import numpy as np
from forextester_backtest.data import HistoryRepository, _to_ole
r=HistoryRepository()
b=Path('agent_runs/bb_alternatives_2020_2025_20260925')
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
for q in json.loads((b/'data_manifest.json').read_text()):
    s=q['symbol']; p=Path(q['raw_path']); summary=r.summary(s)
    paths={'raw_sha256':p,'metadata_sha256':p.parent/'info.dat',
           'cache_sha256':b/(s+'_features.npz')}
    hashes={k:sha(v) for k,v in paths.items()}
    assert all(hashes[k]==q[k] for k in hashes)
    a=np.memmap(p,mode='r',dtype='<f8',offset=4,shape=(summary.bar_count,6))
    lo,hi=np.searchsorted(a[:,0],[_to_ole(datetime(2019,12,1)),_to_ole(datetime(2026,1,1))])
    a=a[lo:hi]; dt=np.diff(a[:,0])*86400
    errors=int(np.sum((a[:,3]<np.maximum(a[:,1],a[:,2]))|
                     (a[:,4]>np.minimum(a[:,1],a[:,2]))|(a[:,3]<a[:,4])))
    t=np.rint((a[:,0]-_to_ole(datetime(1970,1,1)))*86400).astype(np.int64)
    bucket=t//300*300; ix=np.r_[0,np.flatnonzero(np.diff(bucket))+1]
    ends=np.r_[ix[1:],len(a)]
    ohlc=np.column_stack([a[ix,1],np.maximum.reduceat(a[:,3],ix),
                         np.minimum.reduceat(a[:,4],ix),a[ends-1,2]])
    with np.load(paths['cache_sha256'],allow_pickle=False) as z:
        assert np.array_equal(bucket[ix],z['times'])
        assert np.array_equal(ohlc,z['features'][:,:4])
    print(json.dumps(dict(symbol=s,summary=asdict(summary),hashes=hashes,
        m1=len(a),m5=len(ix),incomplete_m5=int(np.sum(ends-ix<5)),
        nonfinite=int(np.sum(~np.isfinite(a))),nonpositive=int(np.sum(a[:,1:5]<=0)),
        ohlc_errors=errors,duplicates=int(np.sum(dt==0)),reversed=int(np.sum(dt<0)),
        gaps=int(np.sum(dt>60.01)),max_gap=round(float(dt.max()))),default=str))
'@ | python -
```

次担当に渡せるものは、この7通貨・期間・入力同一性・OHLC品質の確認と上記限界。チャンネルのルール再現、優位性、採用、TradingView成功について本台帳は判定していない。実注文・外部API・新ダウンロードなし。
