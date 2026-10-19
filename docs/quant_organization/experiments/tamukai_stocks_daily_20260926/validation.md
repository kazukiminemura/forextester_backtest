# 独立検証: 日本大型株・日足田向式派生押し目

実験ID: `tamukai_stocks_daily_20260926`。検証日: 2026-09-26。

判定: **不採用（事前観察基準不通過）／VERIFIED_REJECTED_DESCRIPTIVE_DATA_LIMITED**。
固定モデルの計算再現は確認できたが、10銘柄データを厳密な分割のみ調整・実売買収益として保証しない。実運用承認ではない。
Ponytailに従い戦略や採用閾値の追加・最適化を行わず、独立参照計算は本レポート内に置いた。編集対象はこのレポートのみ。

## 入力・凍結・終了証拠

- 仕様: `hypothesis.md` と `protocol.json` rev2。2017–2019 / 2020–2022 / 2023–2025、別途2017–2025連続。各独立区間は資金と保有をリセット、連続評価は持越。
- 期間変更と品質除外診断は損益閲覧前に固定。単一候補の全期間記述評価で選抜はなく、最終区間も真の未使用holdoutと呼ばない。
- コードSHA256: `ea45264616f7f8f83f835571cd1fbd9f73e20560456b75f460e0ed2f3387c6b7`。
- protocol SHA256: `7a6958c68e62d45685f98dadbcc8955286c115d923959a911011259602ddee7e`。
- data manifest SHA256: `fdaf2c5e0d283d853cc295faf13cd031fbc2c03de3aa43e4301d32d83e12866b`。
- `agent_runs/tamukai_stocks_daily_20260926/results/run_start_manifest.json` は計算前に保存。開始2026-09-26 05:50:19 UTC、完了05:50:20 UTC。source/protocol/tests/reused SMA/data manifest/10 CSVのhashが現ファイルとsummaryに一致、原10 JSONもdata manifestのhashに一致。
- 開発担当実走は `RESULT_JSON=.../results/summary.json`、プロセス終了コード0。独立側でも最終summary・160明細・160個別equity・48集約equityが読み取れ、全明細再計算後の終了コード0を確認。
- データ台帳: [data_inventory.md](data_inventory.md)。原29,530行、派生23,140行。2017–2025は2,198営業日×10。内閣府祝日CSV・JPX休場モデル・2020-10-01売買停止を用いた日付集合検査を独立再実行し欠損/余剰0、exit0。

## 検証内容と結果

- 10銘柄23,140日足について、窓内極値の一意性でstrict pivot、`math.fsum`でSMAを独立算出。全pivotトレンド状態・全261信号一致。各信号時点を含む420 prefixで後方データを切っても過去信号不変、exit0。
- 左右2本pivotは中心から2日後の引けで利用可能。上位足は不使用。SMAの学習・推論モデルはなく、後日価格の漏洩・未確定足の使用なし。
- OHLCから独立状態再生し、翌営業日始値、直前3本SL、建値から1R TP、始値<=SLの見送り、同日エントリー/決済、窓優先、同日両hitのSL優先、当日決済後翌日再エントリー、期末清算を全明細照合。
- 160ケース（2費用×4期間×2手法×10銘柄）、740取引観測、175,840個別MTM行、48集約曲線、108年別指標、927,256 scalar比較が一致。740は区間/費用/買持ちを含む重複観測であり独立した戦略740取引ではない。
- 各銘柄初期100,000円、units=cash/(open×(1+cost))、両端費用、複利、現金/保有評価を確認。すべてJPYなので円合算可能。PF・勝率は費用後純損益に基づく。建値を金銭勝ちへ置換していない。
- MTM DDは初期資金をピーク候補に含む。年別は前年最後のMTMを年初資金/ピークとして再計算。年間MTM損益と決済年別実現損益を分離。
- 本番strategy関数を呼ばず再生した会計と各指標が一致。買持ちも同じ初期銘柄別資金、期間、両端費用で一致。
- 境界条件6 unittestを独立再実行して全成功、exit0。コスト2倍診断も照合。
- パラメータ感度は実施していない。今回の単一候補・最適化なしの範囲として未検証を保持し、安定した最適値・近傍頑健性を主張しない。

## 事前基準と不採用理由

|観察基準|2020–2022|2023–2025|
|---|---:|---:|
|100取引以上|52件: 不通過|59件: 不通過|
|純PF>=1.1|0.9351: 不通過|1.3019: 通過|
|純損益>0|−8,839.76円: 不通過|+39,761.99円: 通過|
|合算引けMTM DD<=20%|3.8802%: 通過|3.4656%: 通過|

最終区間の黒字6/10銘柄およびコスト2倍時の最終区間純益+27,515.60円は通過。総合基準はFalse。
最終区間だけの利益や4件PF infinity等の小標本を採用根拠にしない。
連続通常コストは165件・PF0.9975・−980.18円、費用2倍で−34,049.26円。Sony除外9銘柄も費用2倍で赤字、既知3問題銘柄除外7銘柄は通常費用から赤字。
近年の黒字だけでは一貫した期待値とコスト頑健性を確認できない。データ品質制約による未保証と、この固定データ上の数値基準不通過は別の論点。

main=片道0.1%、stress=片道0.2%。training=2017–2019、validation=2020–2022、final_confirmation=2023–2025、continuous=2017–2025。
平均純損益は円/決済件数で、勝率ではない。全表のDDは引けMTMで日中最大損失ではない。

## 期間別・全10銘柄
|費用/期間|取引|勝率%|純PF|純損益 円|平均純損益 円/件|収益率%|最大DD%|
|---|---:|---:|---:|---:|---:|---:|---:|
|main/training|54|48.15|0.7610|-30,014.82|-555.83|-3.0015|6.1413|
|main/validation|52|46.15|0.9351|-8,839.76|-170.00|-0.8840|3.8802|
|main/final_confirmation|59|55.93|1.3019|39,761.99|673.93|3.9762|3.4656|
|main/continuous|165|50.30|0.9975|-980.18|-5.94|-0.0980|7.1251|
|stress/training|54|48.15|0.6903|-40,308.32|-746.45|-4.0308|6.5891|
|stress/validation|52|46.15|0.8651|-19,026.09|-365.89|-1.9026|4.6877|
|stress/final_confirmation|59|55.93|1.2024|27,515.60|466.37|2.7516|3.9295|
|stress/continuous|165|50.30|0.9141|-34,049.26|-206.36|-3.4049|7.7877|

## 通常コスト・銘柄別
|期間|銘柄|取引|純PF|純損益 円|平均純損益 円/件|最大DD%|
|---|---|---:|---:|---:|---:|---:|
|training|7203.T|4|4.4149|7,508.98|1,877.24|2.7008|
|training|6758.T|4|0.7931|-2,092.83|-523.21|10.9986|
|training|8306.T|7|0.6575|-5,296.08|-756.58|10.1277|
|training|9432.T|4|1.5918|2,800.10|700.03|7.6929|
|training|9984.T|6|0.3876|-12,585.11|-2,097.52|16.2041|
|training|6501.T|6|2.7576|12,147.92|2,024.65|5.0348|
|training|6861.T|4|1.2142|1,767.34|441.83|8.2369|
|training|8035.T|9|0.5395|-13,100.53|-1,455.61|27.7199|
|training|8058.T|5|0.1938|-12,134.17|-2,426.83|13.5725|
|training|4502.T|5|0.3488|-9,030.44|-1,806.09|10.6492|
|validation|7203.T|4|1.4024|3,829.35|957.34|13.2552|
|validation|6758.T|3|0.5117|-8,594.92|-2,864.97|18.0876|
|validation|8306.T|7|1.9943|8,674.07|1,239.15|5.9225|
|validation|9432.T|3|1.1043|679.68|226.56|7.9948|
|validation|9984.T|4|0.5110|-7,057.83|-1,764.46|10.6318|
|validation|6501.T|4|4.4256|15,574.88|3,893.72|5.7082|
|validation|6861.T|7|0.5282|-10,413.34|-1,487.62|18.2713|
|validation|8035.T|6|1.7467|10,567.56|1,761.26|8.3224|
|validation|8058.T|7|0.5858|-7,823.55|-1,117.65|20.7719|
|validation|4502.T|7|0.2795|-14,275.67|-2,039.38|17.5651|
|final_confirmation|7203.T|7|1.1961|3,706.30|529.47|16.4553|
|final_confirmation|6758.T|8|0.3733|-17,418.90|-2,177.36|26.0126|
|final_confirmation|8306.T|12|2.3470|26,350.06|2,195.84|10.6233|
|final_confirmation|9432.T|7|0.2397|-9,720.58|-1,388.65|10.7791|
|final_confirmation|9984.T|5|0.7172|-6,781.20|-1,356.24|16.2243|
|final_confirmation|6501.T|5|0.9661|-412.03|-82.41|11.2076|
|final_confirmation|6861.T|3|5.8840|7,852.23|2,617.41|2.7844|
|final_confirmation|8035.T|4|5.0864|22,820.32|5,705.08|8.2119|
|final_confirmation|8058.T|4|1.2345|2,192.62|548.15|5.9142|
|final_confirmation|4502.T|4|infinity|11,173.18|2,793.29|2.9036|
|continuous|7203.T|15|1.4702|15,763.07|1,050.87|16.4553|
|continuous|6758.T|15|0.5003|-26,096.41|-1,739.76|37.4783|
|continuous|8306.T|26|1.5893|26,815.28|1,031.36|13.6773|
|continuous|9432.T|14|0.7339|-6,561.87|-468.70|12.1696|
|continuous|9984.T|15|0.5392|-24,264.11|-1,617.61|27.3996|
|continuous|6501.T|15|2.0473|29,080.77|1,938.72|11.2076|
|continuous|6861.T|14|0.9481|-1,671.18|-119.37|24.2905|
|continuous|8035.T|19|1.3906|18,008.99|947.84|27.7199|
|continuous|8058.T|16|0.5606|-17,232.56|-1,077.04|27.5033|
|continuous|4502.T|16|0.5543|-14,822.16|-926.39|25.6756|

## 連続評価の年別・通常コスト
|年|決済件数|純PF|MTM損益 円|実現損益 円|平均実現損益 円/件|年内最大DD%|
|---|---:|---:|---:|---:|---:|---:|
|2017|19|0.8348|-6,049.55|-6,514.73|-342.88|2.4221|
|2018|15|0.5714|-20,394.58|-19,929.40|-1,328.63|3.6905|
|2019|19|0.9117|-3,475.89|-3,493.07|-183.85|2.6709|
|2020|18|1.1085|5,422.53|5,439.71|302.21|3.3783|
|2021|20|0.7727|-10,101.05|-10,624.23|-531.21|2.3409|
|2022|14|0.9334|-3,251.02|-2,288.65|-163.47|3.1105|
|2023|21|1.4727|18,023.22|17,584.02|837.33|2.3353|
|2024|18|0.8229|-13,684.34|-10,092.54|-560.70|3.5815|
|2025|21|1.8003|32,530.50|28,938.70|1,378.03|2.1197|

## 買持ち対照・通常コスト
|期間|損益 円|収益率%|最大DD%|
|---|---:|---:|---:|
|training|396,350.91|39.6351|30.4124|
|validation|349,483.81|34.9484|29.4012|
|final_confirmation|1,220,798.78|122.0799|30.9244|
|continuous|3,274,385.31|327.4385|33.1004|

## 連続評価のデータ品質除外診断
|集合/費用|初期資金 円|取引|純PF|純損益 円|収益率%|最大DD%|
|---|---:|---:|---:|---:|---:|---:|
|exclude_sony/main|900,000|150|1.0750|25,116.23|2.7907|8.2799|
|exclude_three_known_issues/main|700,000|105|0.9190|-19,708.04|-2.8154|7.9891|
|exclude_sony/stress|900,000|150|0.9832|-5,768.66|-0.6410|8.9869|
|exclude_three_known_issues/stress|700,000|105|0.8406|-39,766.82|-5.6810|8.9163|



銘柄別stress、全期間の除外9/7銘柄、買持ちstress、年別その他は `results/summary.json` に全保存され、独立照合済み。
除外診断は既存の同額sleeveを合算し直しただけで再配分せず、9銘柄90万円・7銘柄70万円からの収益率。選抜・新候補・clean認証ではない。
買持ちの通常連続+327.44%に対し戦略は−0.10%、一方DDは33.10%対7.13%。保有時間・リスク量が異なり、同等リスクの優劣判定ではない。

## 未実装・未検証コストとデータ限界

- 手数料/滑りは代金に比例する包括費用であり、滑りによるTP/SL判定自体の変化、寄付競合、ストップ高安の約定不能、板、最小呼値、単元注文は未実装。
- 各10万円を連続調整株数へ全額配分する合成モデル。100株単元を買える銘柄/資金額の実戦再現ではない。
- 普通配当、税金、現金金利、企業行動の株式受領/換金は未算入。
- Sonyはスピンオフ遡及調整混入を復元できず、10銘柄は参考値。8306/8035の2包絡異常は原JSONを保ちCSVで合成修復、二次価格照合済みだが取引所原票保証ではない。
- 現在存続する大型株の固定便宜標本で、生存/銘柄選択バイアス。全価格/企業行動の一次原票照合なし。7銘柄除外診断でもこの制約は残る。

## 再現コマンド

workspace rootから実行。保存データで再現する場合にデータ再取得は不要。

```powershell
python -m unittest discover -s tests -p test_tamukai_stocks_daily.py -v
python scripts/research_tamukai_stocks_daily.py --output agent_runs/tamukai_stocks_daily_20260926/reproduction
```

以下は独立再計算に実際に使用したPython。PowerShellの `@' ... '@ | python -` で実行できる。既存結果・仕様・元CSVを読取のみとし、戦略実装のsimulate/metricsを呼ばない。上記再実行先を照合するときは `O` のみ変更する。

```python
import csv,json,math,hashlib
from pathlib import Path
R=Path("agent_runs/tamukai_stocks_daily_20260926"); D=R/"data"; O=R/"results"
P=Path("docs/quant_organization/experiments/tamukai_stocks_daily_20260926/protocol.json")
spec=json.loads(P.read_text()); summary=json.loads((O/"summary.json").read_text()); started=json.loads((O/"run_start_manifest.json").read_text())
ledger=json.loads((D/"manifest.json").read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for key,path in [("source_sha256",Path("scripts/research_tamukai_stocks_daily.py")),("protocol_sha256",P),("tests_sha256",Path("tests/test_tamukai_stocks_daily.py")),("reused_source_sha256",Path("src/forextester_backtest/tamukai.py")),("data_manifest_sha256",D/"manifest.json")]:
 assert sha(path)==summary[key]==started[key],key
assert started["periods"]=={} and started["started_at"]<=summary["completed_at"]
def rows(path):
 return [{k:v if k in ("date","signal_date","entry_date","exit_date","reason") else float(v) for k,v in x.items()} for x in csv.DictReader(path.open())]
bars={s:rows(D/(s+".csv")) for s in spec["symbols"]}
signals={}
for s,b in bars.items():
 assert sha(D/(s+".csv"))==summary["data_sha256"][s]==ledger["symbols"][s]["csv_sha256"]
 assert sha(D/(s+".json"))==ledger["symbols"][s]["raw_sha256"]
 assert len(b)==2314 and sum(x["date"]>="2017" for x in b)==2198
 assert [x["date"] for x in b]==[x["date"] for x in next(iter(bars.values()))]
 av=[None if i<20 else math.fsum(x["close"] for x in b[i-20:i+1])/21 for i in range(len(b))]
 out=[None]*len(b); highs=[]; lows=[]
 for t in range(4,len(b)):
  c=t-2; w=b[c-2:c+3]
  if b[c]["high"]==max(x["high"] for x in w) and sum(x["high"]==b[c]["high"] for x in w)==1: highs.append(b[c]["high"])
  if b[c]["low"]==min(x["low"] for x in w) and sum(x["low"]==b[c]["low"] for x in w)==1: lows.append(b[c]["low"])
  up=len(highs)>=2 and len(lows)>=2 and highs[-1]>highs[-2] and lows[-1]>lows[-2]
  if t>=23 and up and b[t]["close"]>av[t]>av[t-2] and min(b[k]["low"]-av[k] for k in range(t-3,t))<=0 and b[t]["close"]>max(x["high"] for x in b[t-3:t]): out[t]=min(x["low"] for x in b[t-3:t])
 signals[s]=out
checks=0
def compare(got,want,tag):
 global checks
 assert len(got)==len(want),(tag,"length",len(got),len(want))
 for i,(a,b) in enumerate(zip(got,want)):
  for key,value in b.items():
   v=a[key]
   assert (math.isclose(v,value,abs_tol=1e-7,rel_tol=1e-11) if isinstance(value,(int,float)) else v==value),(tag,i,key,v,value)
   checks+=1
def replay(b,sg,start,end,cost,hold):
 indexes=[i for i,x in enumerate(b) if start<=x["date"]<=end]
 cash=100000.; pos=None; tr=[]; curve=[]
 for i in indexes:
  x=b[i]; date=x["date"]; op=x["open"]
  if pos is None and ((hold and i==indexes[0]) or (not hold and i>indexes[0] and sg[i-1] is not None and op>sg[i-1])):
   stop=0. if hold else sg[i-1]; q=cash/op/(1+cost)
   pos=dict(signal_date=date if hold else b[i-1]["date"],entry_date=date,entry=op,stop=stop,target=2*op-stop,units=q,entry_cost=q*op*cost)
   invested=cash; cash=0.
  exposed=int(pos is not None)
  if pos:
   price=None; reason=None
   if not hold:
    if op<=pos["stop"]: price,reason=op,"gap_stop"
    elif op>=pos["target"]: price,reason=op,"gap_target"
    elif x["low"]<=pos["stop"]: price,reason=pos["stop"],"stop"
    elif x["high"]>=pos["target"]: price,reason=pos["target"],"target"
   if price is None and i==indexes[-1]: price,reason=x["close"],"period_end"
   if price is not None:
    fee=pos["units"]*price*cost; cash=pos["units"]*price-fee
    tr.append(dict(pos,exit_date=date,exit=price,exit_cost=fee,net_pnl=cash-invested,return_pct=100*(cash-invested)/invested,reason=reason)); pos=None
  curve.append(dict(date=date,equity=cash+(pos["units"]*x["close"] if pos else 0),cash=cash,exposed=exposed))
 return tr,curve
def metrics(tr,eq,initial,year=False):
 pnl=[x["net_pnl"] for x in tr]; win=sum(x for x in pnl if x>0); loss=-sum(x for x in pnl if x<0)
 peak=initial; dd=0.
 for r in eq:
  peak=max(peak,r["equity"]); dd=max(dd,(1-r["equity"]/peak)*100)
 profit=eq[-1]["equity"]-initial
 return dict(initial_capital=initial,final_equity=eq[-1]["equity"],net_profit=profit,return_pct=profit/initial*100,trades=len(tr),win_rate_pct=100*sum(x>0 for x in pnl)/len(tr) if tr else 0,net_pf=win/loss if loss else ("infinity" if win else "undefined"),average_net_profit=(sum(pnl) if year else profit)/len(tr) if tr else 0,max_drawdown_pct=dd,exposure_pct=sum(x["exposed"] for x in eq)/len(eq)*100)
def combine(sleeves):
 eqs=[v[1] for v in sleeves.values()]
 eq=[dict(date=r[0]["date"],equity=sum(x["equity"] for x in r),cash=sum(x["cash"] for x in r),exposed=sum(x["exposed"] for x in r)/len(r)) for r in zip(*eqs)]
 return [x for v in sleeves.values() for x in v[0]],eq
cases=trades_n=mtm=portfolios=years=0
for cn,cost in [("main",.001),("stress",.002)]:
 for period,(start,end) in spec["periods"].items():
  for method in ["strategy","buyhold"]:
   saved=summary["periods"][cn][period][method]; folder=O/cn/period/method; sleeves={}
   for s,b in bars.items():
    tr,eq=replay(b,signals[s],start,end,cost,method=="buyhold")
    compare(rows(folder/(s+"_trades.csv")),tr,(cn,period,method,s,"trades"))
    compare(rows(folder/(s+"_equity.csv")),eq,(cn,period,method,s,"equity"))
    compare([saved["by_symbol"][s]],[metrics(tr,eq,100000)],(cn,period,method,s,"metrics"))
    assert math.isclose(sum(t["net_pnl"] for t in tr),eq[-1]["equity"]-100000,abs_tol=1e-7)
    sleeves[s]=(tr,eq); cases+=1; trades_n+=len(tr); mtm+=len(eq)
   for group,exclude in [("portfolio",set()),("exclude_sony",{"6758.T"}),("exclude_three_known_issues",{"6758.T","8306.T","8035.T"})]:
    subset={s:v for s,v in sleeves.items() if s not in exclude}; tr,eq=combine(subset); init=100000*len(subset)
    val=saved if group=="portfolio" else saved["quality_diagnostics"][group]
    compare(rows(folder/(group+"_equity.csv")),eq,(cn,period,method,group,"curve"))
    compare([val],[metrics(tr,eq,init)],(cn,period,method,group,"metrics")); portfolios+=1
    if period=="continuous":
     prev=init
     for y in range(2017,2026):
      ye=[x for x in eq if x["date"].startswith(str(y))]; yt=[x for x in tr if x["exit_date"].startswith(str(y))]
      expect=metrics(yt,ye,prev,True); expect["net_realized_profit"]=sum(x["net_pnl"] for x in yt)
      compare([val["yearly"][str(y)]],[expect],(cn,method,group,y)); prev=ye[-1]["equity"]; years+=1
gates={}
for p in ("validation","final_confirmation"):
 z=summary["periods"]["main"][p]["strategy"]; pf=z["net_pf"]
 gates[p]=dict(min_trades=z["trades"]>=100,min_pf=pf=="infinity" or isinstance(pf,(float,int)) and pf>=1.1,positive_profit=z["net_profit"]>0,max_drawdown=z["max_drawdown_pct"]<=20)
gates["final_cross_symbol"]=sum(z["net_profit"]>0 for z in summary["periods"]["main"]["final_confirmation"]["strategy"]["by_symbol"].values())>=6
gates["final_stress_positive"]=summary["periods"]["stress"]["final_confirmation"]["strategy"]["net_profit"]>0
assert gates==summary["gates"]
passed=all(gates["validation"].values()) and all(gates["final_confirmation"].values()) and gates["final_cross_symbol"] and gates["final_stress_positive"]
assert passed==summary["observational_gate_pass"]
print("INDEPENDENT_REPLAY_PASS",dict(cases=cases,trades=trades_n,mtm_rows=mtm,portfolios=portfolios,yearly=years,scalar_checks=checks,signal_bars=sum(map(len,bars.values())),signals=sum(x is not None for sg in signals.values() for x in sg)))
print("GATES",gates,"PASS",passed)
for cn in ["main","stress"]:
 for p in spec["periods"]:
  z=summary["periods"][cn][p]["strategy"]
  print(cn,p,{k:z[k] for k in ["trades","win_rate_pct","net_pf","net_profit","return_pct","max_drawdown_pct","average_net_profit"]})

```

## 担当引継ぎ

- 担当/次担当: 独立検証 → 主担当/品質監査。
- 状態: 不採用、記述モデル会計確認済み、DATA_LIMITED。
- 変更ファイル: 本 `validation.md` のみ。戦略・基準・データを変更していない。
- 成果物: `agent_runs/tamukai_stocks_daily_20260926/results/` と本レポート。再計算Pythonは上記。
- 修正依頼: 仕様rev2内の旧2014 warmup・split-only断定残存を実走前に指摘し、開発担当修正後のhashで再検証済み。残る実装不一致なし。
- 次工程に渡してよい範囲: 不採用の単純株式モデルとして報告可能。採用/Pine移植/実運用承認の根拠には渡さない。
- 実注文: なし。

