# YTT / Jev 入力再利用調査

2026-10-10 JST、データ品質担当。状態 `DATA_READY_WITH_LIMITATIONS`。
本書のみ編集。原 `Bars.dat / ticks.dat / info.dat`、旧cache、Pine、研究実装は読取専用。API呼出・秘密値読取・戦略再計算・採用判定なし。

## 結論

1. 現行YTT M15/D1/W1の研究には、既存3通貨のM5価格と完全性maskを再利用できる。新規Jev評価用入力は現行候補から作り直す必要がある。
2. 旧Jev応答はBB **M5、上位足なし、ヒゲ突破** 専用。YTTの終値突破やM15 BBの評価として転用できない。
3. 旧Jev予定828件のうち、保存811件、有効808件、accept562件、無効3件、未応答17件。これは分類件数であり取引勝率ではない。未応答/無効を有効なskipや成功例と呼ばない。
4. 2020–2025は既閲覧。2026も旧研究で使用されており、未使用holdoutを保証できない。

## 今回の読取検査

主データ源 `C:/ForexTester6/data/History`。現物の期間・件数・設定は `HistoryRepository.summary/metadata` で再確認した。

- BB保存M5全1,611,265行のOHLC有限・正値・包絡、時刻昇順/重複なし、300秒境界、内容SHAを再検査。7/7入力SHA一致。原Barsのsize/mtime_nsも7/7一致。ただしstat一致は原データ全bytesの一致証明ではない。
- YTT保存M5全1,365,021行のOHLC有限・正値・包絡・時刻昇順を再検査。3通貨それぞれのcache/mask全bytes SHA、計6/6一致。mask長一致。
- 元M1/tick全件の再検査は今回未実施。元M1/tickは件数と端点のみ。BBの元M1対照21サンプル一致は旧 `bb3_jev_20260925/data_inventory.md` の記録であり、今回再実施したものではない。
- 旧Jev保存811件すべてのrequest内容SHAとファイル名/hash一致、manifestにない余分応答0件。responseを既存validatorへ通し808件validを確認。無効理由は `Choice is not maximum` 1件、`Invalid choice distribution` 2件。
- 初回監査は「全予定応答がある」というassertが17件不足で停止（exit 1）。続く診断コマンドはexit 0で欠損/無効を上記のとおり確定。欠損を修復・再送していない。
- 旧Jev runner / engine / BB Pineの現在SHAは旧run_manifestの3ファイルと一致。旧resultsの`complete=false`、811/808/562の記載は今回cache検査と一致。

## 再利用可能期間・件数

BB cache: `agent_runs/bb3_gmo_2023_2025/<symbol>_features.npz`。全通貨2022-12-01 00:00〜2025-12-31 21:55。2022-12は初期化、評価可能区間2023-01-01以上2026-01-01未満。

|通貨|保存M5件数|M5間隔300秒超|原M1件数|原M1開始日|spread pips|pip / quote|
|---|---:|---:|---:|---|---:|---|
|USDJPY|230,571|231|8,534,100|2003-05-06|1.2|0.01 / JPY|
|EURUSD|230,485|247|8,567,792|2003-05-06|1.1|0.0001 / USD|
|GBPUSD|230,492|231|8,680,197|2003-05-06|1.4|0.0001 / USD|
|AUDUSD|229,752|267|6,286,639|2009-10-01|1.2|0.0001 / USD|
|NZDUSD|229,944|291|8,572,858|2003-08-05|1.4|0.0001 / USD|
|AUDJPY|230,095|299|8,479,694|2003-12-02|1.4|0.01 / JPY|
|NZDJPY|229,926|286|7,624,497|2006-01-04|1.7|0.01 / JPY|

原M1終了は全7通貨2026-09-07 23:59。gap件数は休日/週末も含み、市場カレンダーで欠損と分類した数ではない。

YTT cache: `agent_runs/bb_alternatives_2020_2025_20260925/<symbol>_features.npz`。
mask: `agent_runs/yosuga_channel_20261003/completed/<symbol>_complete_m5.npz`。
全3通貨2019-12-01 22:00〜2025-12-31 21:55、2019-12初期化、2020–2025記述評価に利用可能。

|通貨|保存M5|完全M5|M5間隔300秒超|
|---|---:|---:|---:|
|USDJPY|455,085|446,773|415|
|EURUSD|455,004|445,417|441|
|GBPUSD|454,932|447,550|447|

SHA照合は `agent_runs/ytt_profit_feasibility_20261009/run_manifest.json` の `inputs` を使用。旧初回 `first_run_before_m1_open_fix` を再利用しない。

## 時刻・価格・費用の制約

`HistoryRepository` はOLE日時をtimezoneなしで復号する。epoch整数は元時計の算術座標でありUTCの根拠ではない。D1は元時計00:00、W1は元時計月曜00:00。TradingView/OANDAの日週境界と一致する保証はない。

M5/M15のラベルはbucket開始。集約は不完全bucketも保持するので、完全性maskと原M1の実最初観測時刻が必要。旧YTT core `actual_open_times/raw_open_metadata` を再利用する際は時間幅900秒の前提を確認する。先頭M1がないbucketをラベル時点で約定したことにしない。

全7通貨info.datはAdvanced Data Feed、lot_size=100,000、ApplyCommission=0、CommPerLot=0、SwapLong/Short=0。設定上の0は実取引費用0の証明ではない。spreadはmetadata points×tick（JPY小数3桁、他5桁）。pipは既存FX定義、quoteは`InstrumentMetadata.pnl_currency`の末尾3文字に基づく。

OHLCのBid/Ask/中値は未確定。旧Jevの往復1.0/1.2pipは仮費用で、現在のmetadata spreadや実測約定費用ではない。円口座合算にはUSD等の損益換算時点・換算レート・欠損規則を別途固定する。スリッページ、swap、broker数量step/最小lotも自動で引き継がない。

## 現行条件との対応

`scripts/research_ytt_monthly5_fx.py` は完了D/Wの方向一致、左右2本ピボット、終値突破、同じ水準の消費/新ピボット再準備を実装し、現行YTT scannerの概念と対応する。しかしPythonは完全M15だけを状態へ投入し、ピボット同値規則を明示的近似と記載する。feed/日週境界も異なるため、現行Pineと全信号一致済みとは呼ばない。

さらに旧YTT研究は反対ピボット±1tick SL、RR1、保有上限96 M15、元時計23:45終値決済を付加している。現行Pineの分析候補表示だけにはこの執行契約がない。これらを勝手に「現行の実売買ルール」としない。

`research_bb3_jev_engine.py` はM5 touch→後続反転足→後続ヒゲ突破、上位足なし。`research_bb3_jev.py` のpromptもこの前提で、直近12本のATR正規化OHLC等を送る。旧Jev模型jev-1.13.0のaccept確率は状況分類の確率であって利益確率ではない。

`research_bb3_jev_refine.py` は決定的ルール比較で、明記された通りAPIもJev trade cacheも読まない。ファイル名だけでJev連携済みの検証結果と解釈しない。

## 最小の検証可能な入力設計

研究責任者に渡すデータ条件であり、戦略採用基準や成績は本書で作らない。

1. まずUSDJPY/EURUSD/GBPUSD、M15/DW、左右2ピボットの候補を凍結。YTTとBBは別のevent種別とし、BBをM15にするならM5の旧判定cacheを流用しない。
2. 候補確定時点までのOHLC・ATR・完了HTF・SL/突破水準・gap/完全性を決定的に抽出。future/結果/未確定HTFをpayloadに含めない。payload/model/rubricをSHA識別する。
3. 即時の決定的baseline、AI待機と同じ遅延のno-AI対照、Jev gateを分ける。API失敗・期限超過・無効確率は見送りとして全件台帳に残す。返答後に遡ってsignal-closeや過去openで約定しない。
4. SLを動かしてRRだけ増やす方式と、同じSLでTPを遠ざける方式は別仕様。ユーザー希望のRR改善を価格計算の契約として固定し、AIに価格/損益算術を任せない。
5. 過去2020–2025は記述評価とする。新規凍結後に到来するデータをforward対象として保存すれば、少なくともこの新仕様に対する事後調整を区別できる。2026既存データを未使用と呼ばない。

## 入力識別子

|保存物|今回SHA256|
|---|---|
|旧Jev results.json|7d5c4d7993f0b14ff7581d89f48f58d8de46c67ca83c0c3b465053899598d697|
|旧Jev run_manifest.json|1def1673c468816c7364f20737e0467c41de88dfc78b9012f397f1b9a3f27ad0|
|旧Jev candidates.json|a16fbe8cf08c1b9db7ae0b74dd9d62c9557b89e0de4781034b17256b77c574c0|

## 再現コマンド

リポジトリルート、PowerShell。外部送信なし。下記は保存cacheの全行とresponse契約を再検査し、原履歴はsummary端点のみ読む。戦略成績を作らない。

```powershell
$env:PYTHONPATH='src;scripts'
@'
import json, hashlib
from pathlib import Path
import numpy as np
from forextester_backtest import HistoryRepository
from research_bb3_jev import digest, validate_response
r = HistoryRepository()
b = Path('agent_runs/bb3_gmo_2023_2025')
for m in json.loads((b/'data_manifest.json').read_text()):
    z = np.load(b/(m['symbol']+'_features.npz'), allow_pickle=False)
    t, f = z['times'], z['features']; p = f[:,:4]
    assert hashlib.sha256(t.tobytes()+f.tobytes()).hexdigest()==m['input_sha256']
    assert np.isfinite(p).all() and (p>0).all() and (np.diff(t)>0).all() and (t%300==0).all()
    assert (p[:,1]>=p[:,[0,3]].max(axis=1)).all() and (p[:,2]<=p[:,[0,3]].min(axis=1)).all()
    st=Path(m['raw_path']).stat()
    assert dict(size=st.st_size,mtime_ns=st.st_mtime_ns)==m['stat']
    print(m['symbol'], len(t), int((np.diff(t)>300).sum()), r.summary(m['symbol']))
y=Path('agent_runs/bb_alternatives_2020_2025_20260925')
c=Path('agent_runs/yosuga_channel_20261003/completed')
old=json.loads(Path('agent_runs/ytt_profit_feasibility_20261009/run_manifest.json').read_text())
for m in old['inputs']:
    s=m['symbol']; p=y/(s+'_features.npz'); q=c/(s+'_complete_m5.npz')
    assert hashlib.sha256(p.read_bytes()).hexdigest()==m['cache_sha256']
    assert hashlib.sha256(q.read_bytes()).hexdigest()==m['mask_sha256']
    z=np.load(p,allow_pickle=False); t=z['times']; o=z['features'][:,:4]
    mask=np.load(q,allow_pickle=False)['complete']
    assert len(mask)==len(t) and (np.diff(t)>0).all() and np.isfinite(o).all() and (o>0).all()
    assert (o[:,1]>=o[:,[0,3]].max(axis=1)).all() and (o[:,2]<=o[:,[0,3]].min(axis=1)).all()
    print(s, len(t), int(mask.sum()))
j=Path('agent_runs/bb3_jev_20260925')
m=json.loads((j/'run_manifest.json').read_text()); found=set(); valid=accepted=0
for p in (j/'responses').glob('*.json'):
    a=json.loads(p.read_text()); assert digest(a['request'])==p.stem==a['hash']; found.add(p.stem)
    try:
        choice=validate_response(a['response'])
        assert a['valid'] and a['seconds']<300 and choice==a['accepted']
        valid+=1; accepted+=int(choice)
    except (ValueError, KeyError, AssertionError): pass
print('responses',len(found),'valid',valid,'accepted',accepted,'missing',len(set(m['payload_hashes'])-found))
assert not found-set(m['payload_hashes'])
print('READ_ONLY_AUDIT_OK')
'@ | python -
```

次担当: 研究責任者・実装担当。上記の母集団差と未応答件数を保持して新payload/執行仕様を固定する。
