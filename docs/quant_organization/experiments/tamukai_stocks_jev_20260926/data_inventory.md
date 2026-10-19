# 保存株価データ再確認

実験ID: `tamukai_stocks_jev_20260926`。確認日: 2026-09-26。
状態: **DATA_READY_WITH_QUALIFICATIONS / DATA_LIMITED**。この確認は研究入力の同一性を示し、戦略採用や株価の完全な正確性を保証しない。

## 入力と再利用確認

入力は `data/stocks/yahoo/jp_largecap10_20260926/` の保存Yahoo日足。再ダウンロード・原データ編集は行っていない。
前実験 `tamukai_stocks_daily_20260926` の `agent_runs/.../data/` とraw10 JSON・派生10 CSV・manifestのSHA256が一致する。

manifest SHA256: `fdaf2c5e0d283d853cc295faf13cd031fbc2c03de3aa43e4301d32d83e12866b`。

全CSV23,140行を今回再走査し、OHLCの有限性/正値/包絡、出来高正、日付の重複なし/昇順、全10銘柄の同一日付集合を確認した。各2,314行、2016-07-12〜2025-12-30。評価2017-01-04〜2025-12-30は各2,198日。読取検査はexit 0。
独立した取引所原票の再取得や最新株価更新は今回行っていない。営業日モデルの完全照合は前実験データ台帳・独立検証を継承し、同じスナップショットであることを今回hashで確認した。

|銘柄|会社|CSV SHA256|
|---|---|---|
|7203.T|トヨタ|0ab55ff8cf84f91e685a9d58ec29b2b421ca6c516c9e12aa7a90bc5e5f9199e8|
|6758.T|ソニーグループ|c8c6ba3f0be91879b3d4a899fda0dfc64583145970a2cf2755f51997ebb533be|
|8306.T|三菱UFJ FG|4f6a43484c1494b97cb07f0762f5d6b5afc8531436a09f389fcc0f57383fde1f|
|9432.T|NTT|58d1637f106d3dd90bc26eb6dcd5d879854d074861fe53a0e73d94a0362ecdbb|
|9984.T|ソフトバンクグループ|954672eb1b8f0ffd5d7202401303eae6a7857d0712c021c0b87cc274b9177ec4|
|6501.T|日立|47fd60ca582c5429479daf463e1d1e349bc9ab5aa8589e92d695943e72c47a53|
|6861.T|キーエンス|d06587f8fe32cbc09db7686e9113602d17fc999d57f3b90319004f7d44858470|
|8035.T|東京エレクトロン|6fe3115a5aefebbafe3483128fa03dacdd85f768559725f75a05599b9522907b|
|8058.T|三菱商事|01f819aa243cfc45f92734500a493050b864ff5a01c793be6f193b97636da855|
|4502.T|武田|4a11585725fcf488f5a4ce20e2d6492c8273a2cb2e8c74eb36502471a91c72aa|

raw10ファイルのhash・取得URL・企業行動・修復原値は同一manifestおよび[前実験データ台帳](../tamukai_stocks_daily_20260926/data_inventory.md)に保存されている。

## 継承する品質制約

- 現在存続する日本大型株10銘柄の便宜標本であり、当時の大型株母集団や退場銘柄を含まない。選択/生存バイアスがある。
- 元Yahoo JSONの出来高0ダミー行を除外済み。2015-12-25/2016-07-11は実営業日欠測なので2016-07-12より前を指標にも用いない。無断補間していない。
- 8306.Tの2022-05-17安値と8035.Tの同日高値の2件は始値/終値を包む合成修復。別公開価格表で方向・値を裏付けたが取引所原票の保証ではない。rawは無変更でCSVとmanifestに修復を保存。
- Sonyの2025年金融子会社分離に関する遡及OHLC調整は復元できていない。Yahoo quote OHLCは厳密なsplit-onlyとは断定できず、普通配当込み総収益でもない。全10銘柄をDATA_LIMITED参考価格損益として扱う。
- Sony除外9銘柄/既知問題3銘柄除外7銘柄の集約は品質診断で、成績による銘柄選抜やclean認証ではない。
- 通貨はJPY、営業日日付はAsia/Tokyo。日足時刻09:00はラベルであり、同時刻に高安終値が既知ではない。
- 板・寄付競合・最小呼値・過去単元・ストップ高安時の約定不能・全企業行動は未再現。費用は包括仮定、各10万円の端株資金枠は実際の100株単元注文モデルではない。配当・税・金利なしという会計制約を引き継ぐ。

## 既閲覧と選抜の境界

**2017–2025全期間の旧単一戦略成績は前実験で既に閲覧済み。** 新しい候補を2017–2019だけで選抜しても、2020–2022/2023–2025を真の未使用holdoutと呼べない。新実験内でtraining結果確定→候補選抜記録→選抜候補だけ後期評価の順序を守ることと、データの真の未使用性は別である。

今回予定する3候補は別仕様として結果前に固定し、全滅なら停止する。Jevへ渡す集計も段階ごとに限定し、後期成績をtraining選抜用入力へ混入させない。これはデータの利用境界の引継ぎであり、本データ確認担当が選抜・戦略修正・API送信を行うものではない。

## 再確認コマンド

workspace rootから、保存入力を読取のみで検査できる。

```powershell
@'
import csv,json,hashlib,math
from pathlib import Path
d=Path('data/stocks/yahoo/jp_largecap10_20260926')
old=Path('agent_runs/tamukai_stocks_daily_20260926/data')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(d/'manifest.json')=='fdaf2c5e0d283d853cc295faf13cd031fbc2c03de3aa43e4301d32d83e12866b'
m=json.loads((d/'manifest.json').read_text()); reference=None
for s,rec in m['symbols'].items():
 for ext,key in [('json','raw_sha256'),('csv','csv_sha256')]:
  f=d/f'{s}.{ext}'; assert sha(f)==rec[key]
  if (old/f.name).exists(): assert sha(f)==sha(old/f.name)
 rows=list(csv.DictReader((d/f'{s}.csv').open())); dates=[x['date'] for x in rows]
 assert len(rows)==2314 and sum(x>='2017-01-01' for x in dates)==2198
 assert dates==sorted(set(dates)) and dates[0]=='2016-07-12' and dates[-1]=='2025-12-30'
 if reference is not None: assert dates==reference
 reference=dates
 for r in rows:
  o,h,l,c=[float(r[k]) for k in ('open','high','low','close')]
  assert all(math.isfinite(x) and x>0 for x in (o,h,l,c))
  assert l<=min(o,c)<=max(o,c)<=h and float(r['volume'])>0
print('DATA_REUSE_SHA_OHLC_CALENDAR_PASS: 20 files, 23140 CSV rows')
'@ | python -
```

次担当: 研究開発・独立検証・研究責任者。入力同一性を確認済みとして条件付き記述研究へ進める。結果/AI使用証拠が揃った後の監査判定は別紙audit.mdで行う。
