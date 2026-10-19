# 2020–2025 BB固定条件延長・独立検証

## 現在の判定

**不採用 / VERIFIED_REJECTED_DESCRIPTIVE**。336ケースの最終results.json complete=true、研究担当からのRESULT_JSON/exit 0引継ぎ、独立再計算の最終出力/exit 0を確認した。担当編集は本レポートとdata_inventory.mdのみ。戦略コード、採用基準、Pine、API、元データは変更していない。実運用承認ではない。

## 完了証拠と結果

- 独立テスト48 passed / exit 0。初回研究プロセスはNumbaキャッシュのpackage import不整合で特徴量生成前に停止し、run_manifest.failed1.jsonを保存。修正はimport経路のみ、売買ルール/閾値は不変。再実行は完了。
- 全7原Bars.datの全bytes SHA、キャッシュSHA、凍結protocol/runner/依存コード/Pine SHAを照合。元M1から別式で全M5を再集計し時刻/OHLCが完全一致。全3844 W/M候補の確定ピボット・バンド・ネックライン・取消条件、14 prefix、BB2全候補を独立照合。
- 研究側simulate/executeを呼ばない再生で **336ケース・561,796取引観測**、全個別MTM・48集約/合算MTM/DD・62ゲートが一致。全取引の方向・足index/日時・Entry/TP/SL/決済・risk・純pips/R・決済理由、占有/見送り/未決済/pendingも照合。許容差は1e-7を基本とする。561,796は両コスト/年別/連続/重複bookの重複を含む観測数。
- W/Mは原stop_anchorを直接SL判定に用い、TPから再構成した研究SLとの浮動小数差を許容範囲で照合。今回の全約定足・理由は一致。将来の任意価格について恒等性を保証しない。
- 2023–2025独立overlap book **42ケース**の全明細をindex→日時正規化後に前回と完全一致、MTMは1e-9内一致。6重複集約も一致。6年連続bookの途中切出しを旧3年bookと誤って比較していない。
- 独立出力は `INDEPENDENT_REPLAY_COMPLETE 336 cases 561796 trade observations 48 aggregates and combined MTM`、`INDEPENDENT_GATES_OVERLAP_COMPLETE 62 gates 42 pair overlap cases 6 overlap aggregates`。独立検証process exit 0を確認。

|6年連続・1pip|件数|勝率|PF_R|平均R|確定純R|含み込みR|終値MTM DD_R|
|---|---:|---:|---:|---:|---:|---:|---:|
|現行BB3|1,225|50.20%|0.708|-0.173|-212.277|-212.277|219.031|
|BB2終値復帰|108,051|50.44%|0.770|-0.131|-14,119.331|-14,119.261|14,121.762|
|W底/M天井|3,653|47.58%|0.765|-0.135|-493.050|-492.704|497.462|

新2案は全6年それぞれで100件以上の件数基準だけ通過し、PF・期待値・ストレス・4/7黒字基準はすべて未達。連続DD基準も未達。1.2pipの6年含み込みRはBB2 -17,169.201、W/M -552.051。2020–2022を追加しても利益が残る根拠は得られず、期間追加後の最良銘柄/年の後付け選抜は行わない。

年別flatの新2案PF_RはBB2が2020から順に0.750/0.739/0.815/0.779/0.767/0.767、W/Mが0.720/0.722/0.914/0.893/0.742/0.655。全期間・通貨別の件数/勝率/PF/期待値/DDは同実験results.mdとresults.jsonのpair_summaries・annual_pair_summaries・overlap_pair_summariesにあり、全行を上記独立式で照合した。年別flatの合計を6年連続成績とは扱わない。

USDJPY W/Mは6年477件/PF_R0.998817/確定-0.282R、未決済+0.346Rで含み込み+0.064Rとなる。そのため黒字通貨数1/7と確定純益負は矛盾しない。等pip PF1.186/+856.8pipsと、等初期リスクR成績は別尺度。これを口座通貨利益や研究合格として報告しない。

両案不採用の証拠を主担当・品質監査へ引継ぐ。Pine変更はしない。次の仮説/感度検査は別実験として事前固定し、真の未使用期間での確認は別工程。

## 凍結入力と検査計画

`protocol.json` の SPEC_FROZEN と過去2案の継承仕様を読了。新しい戦略探索ではなく、BB2終値復帰・W底/M天井・現行BB3の同じ3仕様を2020–2025へ延長する。全7通貨、M5、RR1、コスト1/1.2pip。6つの独立年別flat book、6年連続book、前回と同じ2023–2025独立overlap bookを分けた336ケースを予定する。

元7通貨は2019-12 warmupと全6年のデータが存在し、全選択M1で時刻/基本OHLC異常0を確認した。ギャップは存在し、詳細はdata_inventory.md参照。

年別各100件・RPF1.2以上・平均R正・ストレス損益正・4/7通貨黒字、6年合算MTM DDは元手法の1.2倍以内という事前基準を変更しない。全期間既閲覧または未使用と証明できないため、学習選抜/真のholdout/実運用承認とは扱わない。

## 実施した独立照合

1. 旧関数の再使用、AI売買入力0、確定足だけの指標/ピボット、次連続足始値、SL優先、ギャップ、数量/費用の限界を確認。
2. 原M1から別式のM5集計と派生キャッシュ照合、旧2023–2025特徴量・候補・独立bookの一致を確認。
3. 保存候補から研究側simulate/executeを呼ばないevent-driven方式で全336約定・未決済・MTMを再計算。W/Mは原stop_anchorを直接用いて浮動小数差も監視する。
4. 48集約、全合算MTM/DD、固定基準、最終results.jsonとプロセスexit 0を確認してから最終判定する。

## 未実装・未確認

歴史的GMO実スプレッド、スワップ、追加slippage、流動性、数量/口座通貨、intrabar最大DDは対象外。BB期間/σ/ピボット幅等のパラメータ感度は今回変更しないため未検証。今回の成功する再現を戦略の頑健性と混同しない。

## 再現コマンド

研究側は次のコマンドで別outputへ再現し、既存成果物を上書きしない。

```powershell
python -m pytest tests/test_bb_alternatives_sixyear.py tests/test_bb_alternatives.py tests/test_bb3_jev_engine.py -q
python scripts/research_bb_alternatives_sixyear.py --output agent_runs/bb_alternatives_2020_2025_20260925_replay
```

以下の独立監査はリポジトリ直下で各Pythonブロックを実行する。研究側simulate/executeは呼ばず、価格・保存候補・保存明細から照合する。監査ブロックは元実験outputに対する読取専用検査。年度別と連続bookには重複取引があり、総照合取引数はユニークな独立標本数ではない。

### 独立データ検査コード

```python
import json,hashlib,math,sys
from pathlib import Path
from datetime import datetime
import numpy as np
from forextester_backtest.data import _RecordFile,_to_ole
sys.path.insert(0,'scripts')
import research_bb_alternatives as alg
root=Path.cwd();out=root/'agent_runs/bb_alternatives_2020_2025_20260925';old=root/'agent_runs/bb_alternatives_20260925';cache=root/'agent_runs/bb3_gmo_2023_2025'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=read(out/'run_manifest.json');m=read(out/'data_manifest.json');assert len(m)==7
assert manifest['model_trade_calls']==manifest['model_trade_cache_reads']==0
for p,h in manifest['code_hashes'].items():assert sha(root/p)==h,p
assert sha(root/'docs/quant_organization/experiments/bb_alternatives_2020_2025_20260925/protocol.json')==manifest['protocol_sha256']
idxfields=('index','prep_index','confirmed_index','first','second','confirmed','entry_index','exit_index')
def norm(items,times):
 return [{k:int(times[v]) if k in idxfields else v for k,v in s.items()} for s in items]
checks=wmcount=0
for row in m:
 symbol=row['symbol'];path=Path(row['raw_path']);assert path.stat().st_size==row['raw_stat']['bytes'];assert path.stat().st_mtime_ns==row['raw_stat']['mtime_ns']
 assert sha(path)==row['raw_sha256'];assert sha(out/f'{symbol}_features.npz')==row['cache_sha256'];assert sha(cache/f'{symbol}_features.npz')==row['old_cache_sha256']
 n=_RecordFile(path,48).count();a=np.memmap(path,dtype='<f8',mode='r',offset=4,shape=(n,6))
 first,last=np.searchsorted(a[:,0],[_to_ole(datetime(2019,12,1)),_to_ole(datetime(2026,1,1))]);a=a[first:last]
 sec=np.rint((a[:,0]-25569)*86400).astype('int64');buckets=sec//300*300
 edges=np.r_[0,np.flatnonzero(np.diff(buckets))+1];ends=np.r_[edges[1:]-1,len(a)-1]
 prices=np.column_stack((a[edges,1],np.maximum.reduceat(a[:,3],edges),np.minimum.reduceat(a[:,4],edges),a[ends,2]))
 with np.load(out/f'{symbol}_features.npz') as z:f=z['features'];times=z['times']
 np.testing.assert_array_equal(times,buckets[edges]);np.testing.assert_array_equal(f[:,:4],prices)
 windows=np.lib.stride_tricks.sliding_window_view(f[:,3],20);mid=windows.mean(axis=1);dev=windows.std(axis=1)
 np.testing.assert_allclose(f[19:,4:7],np.column_stack((mid,mid+3*dev,mid-3*dev)),rtol=0,atol=1e-10)
 bb=np.full((len(f),3),np.nan);bb[19:]=np.column_stack((mid,mid+2*dev,mid-2*dev));np.testing.assert_array_equal(alg.bands(f[:,3]),bb)
 with np.load(cache/f'{symbol}_features.npz') as z:ot=z['times'];of=z['features']
 newmask=times>=1672531200;oldmask=ot>=1672531200
 np.testing.assert_array_equal(times[newmask],ot[oldmask]);np.testing.assert_allclose(f[newmask],of[oldmask],rtol=0,atol=1e-10)
 for policy in ('original','bb2_reentry','wm'):
  ss=read(out/f'{symbol}_{policy}_candidates.json');previous=read(old/f'{symbol}_{policy}_candidates.json')
  assert norm([s for s in ss if times[s['index']]>=1672531200],times)==norm(previous,ot)
  if policy=='bb2_reentry':
   inside=(f[1:,3]>bb[1:,2])&(f[1:,3]<bb[1:,1])&(np.diff(times)==300)
   sides=np.where(f[:-1,3]<bb[:-1,2],1,np.where(f[:-1,3]>bb[:-1,1],-1,0))
   indexes=np.flatnonzero(inside&(sides!=0))+1; indexes=indexes[times[indexes]>=1577836800]
   assert [(s['index'],s['side']) for s in ss]==[(int(i),int(sides[i-1])) for i in indexes]
  if policy=='wm':
   for s in ss:
    side=s['side'];p=s['first'];q=s['second'];i=s['index'];c=s['confirmed'];wmcount+=1
    assert c==q+2 and c<=i and i-p<=60 and np.all(np.diff(times[p-2:i+1])==300)
    for j in (p,q):assert all(side*(f[j,3]-f[k,3])<0 for k in (j-2,j-1,j+1,j+2))
    assert side*(f[p,3]-bb[p,2 if side==1 else 1])<0
    assert side*(f[q,3]-f[p,3])<0 and bb[q,2]<f[q,3]<bb[q,1]
    assert np.any(side*(f[p+1:q,3]-bb[p+1:q,0])>=0)
    assert s['extreme']==f[q,2 if side==1 else 1]
    assert np.all(side*(f[q+1:i+1,2 if side==1 else 1]-s['extreme'])>=0)
    neck=float(np.max(f[p+1:q,1]) if side==1 else np.min(f[p+1:q,2]))
    assert neck==s['neckline'] and side*(f[i,3]-neck)>0 and np.all(side*(f[c:i,3]-neck)<=0)
   for end in (1000,76000):
    got=alg.wm_signals(f[:end],times[:end],bb[:end],row['tick'])
    full=alg.wm_signals(f[:end+100],times[:end+100],bb[:end+100],row['tick'])
    assert got==[s for s in full if s['index']<end];checks+=1
 print('INDEPENDENT_DATA_COMPLETE',symbol,len(f),'M5',flush=True)
print('INDEPENDENT_DATA_ALL_COMPLETE',len(m),'pairs',wmcount,'WM candidates',checks,'WM prefix checks',flush=True)
```

### 独立約定・会計・ゲート検査コード

```python
import json, math, hashlib
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
root=Path.cwd(); out=root/'agent_runs/bb_alternatives_2020_2025_20260925'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
results=read(out/'results.json'); assert results['complete']
ts=lambda y:int(datetime(y,1,1,tzinfo=timezone.utc).timestamp())
spans={'all':(ts(2020),ts(2026)),**{str(y):(ts(y),ts(y+1)) for y in range(2020,2026)},'overlap':(ts(2023),ts(2026))}
policies=['original','bb2_reentry','wm']
rows=results['pair_summaries']+results['annual_pair_summaries']+results.get('overlap_pair_summaries',[])
curves={}; groups={}; casecount=tradecount=0
def equal(a,b):
 if a is None or b is None: assert a==b,(a,b)
 elif isinstance(a,(float,int,np.number)): assert math.isclose(float(a),float(b),rel_tol=1e-8,abs_tol=1e-7),(a,b)
 else: assert a==b,(a,b)
for symbol in results['protocol']['symbols']:
 with np.load(out/f'{symbol}_features.npz') as z: f=z['features']; times=z['times']
 pip=.01 if symbol.endswith('JPY') else .0001
 for policy in policies:
  signals=read(out/f'{symbol}_{policy}_candidates.json')
  for cost in (1.,1.2):
   arm=f'{policy}_rr1.0_cost{cost}'
   for period,(start,end) in spans.items():
    suffix=arm if period=='all' else f'{arm}_{period}'
    expected=read(out/f'{symbol}_{suffix}_trades.json')
    with np.load(out/f'{symbol}_{suffix}_mtm.npz') as z: saved=z['mtm']
    first,last=np.searchsorted(times,[start,end]); n=last-first
    delta=np.zeros(n+1); open_curve=np.zeros(n); items=[]; exitidx=first; holding=False
    accepted=occupied=gap=room=0; pending_side=open_side=0; open_r=open_pips=0.
    for s in signals:
     i=s['index']; side=s['side']
     if times[i]<start or times[i]>=end: continue
     if i<exitidx or holding: occupied+=1; continue
     accepted+=1; e=i+1
     if e>=last: pending_side=side; continue
     if times[e]-times[i]!=300: gap+=1; continue
     entry=float(f[e,0])
     if policy=='wm': stop=s['stop_anchor']; target=2*entry-stop
     else: target=s['target']; stop=2*entry-target
     reward=side*(target-entry)/pip
     if reward<=0 or reward+1e-9<3.: room+=1; continue
     risk=side*(entry-stop)/pip
     x=last; block=e; k=0
     for block in range(e,last,128):
      bound=min(last,block+128); ops=f[block:bound,0]; hi=f[block:bound,1]; lo=f[block:bound,2]
      stop_open=side*(ops-stop)<=0; target_open=side*(ops-target)>=0
      stop_hit=lo<=stop if side==1 else hi>=stop
      target_hit=hi>=target if side==1 else lo<=target
      hit=np.flatnonzero(stop_open|target_open|stop_hit|target_hit)
      if len(hit): k=int(hit[0]); x=block+k; break
     open_curve[e-first:x-first]=(side*(f[e:x,3]-entry)/pip-cost)/risk
     if x==last:
      holding=True; open_side=side; open_pips=float(side*(f[last-1,3]-entry)/pip-cost);open_r=open_pips/risk;continue
     price=float(ops[k] if stop_open[k] or target_open[k] else stop if stop_hit[k] else target)
     net=side*(price-entry)/pip-cost; netr=net/risk
     reason='gap_stop' if stop_open[k] else 'gap_target' if target_open[k] else 'stop' if stop_hit[k] else 'target'
     trade=dict(index=i,side=side,entry_index=e,exit_index=x,entry=entry,target=target,stop=stop,exit=price,risk_pips=risk,net_pips=net,net_r=netr,exit_reason=reason,entry_time=int(times[e]),exit_time=int(times[x]),signal_time=int(times[i]))
     items.append(trade);delta[x-first]+=netr;exitidx=x
    assert len(items)==len(expected),(symbol,policy,period,len(items),len(expected))
    for a,b in zip(items,expected):
     for key,value in a.items(): equal(value,b[key])
    eq=np.cumsum(delta[:-1])+open_curve
    np.testing.assert_array_equal(saved[:,0],times[first:last])
    np.testing.assert_allclose(eq,saved[:,1],rtol=1e-8,atol=1e-7)
    rr=[r for r in rows if r['symbol']==symbol and r['arm']==arm and (r.get('period')==period or ('year' in r and str(r['year'])==period) or period=='all' and 'year' not in r and r not in results.get('overlap_pair_summaries',[]))]
    assert len(rr)==1,(symbol,arm,period,len(rr))
    row=rr[0]; vals=np.array([t['net_r'] for t in items]); pv=np.array([t['net_pips'] for t in items])
    gp=vals[vals>0].sum();gl=-vals[vals<0].sum(); net=float(vals.sum()); wins=int((pv>1e-9).sum())
    check=dict(trades=len(items),wins=wins,win_rate_pct=100*wins/len(items) if items else None,gross_profit_r=gp,gross_loss_r=gl,net_r=net,average_r=net/len(items) if items else None,profit_factor_r=gp/gl if gl else None,net_pips=float(pv.sum()),open_net_pips=open_pips,open_net_r=open_r,net_plus_open_r=net+open_r,bar_close_mtm_drawdown_r=float(np.max(np.maximum.accumulate(np.maximum(eq,0))-eq)) if len(eq) else 0,accepted_candidates=accepted,occupied_candidates=occupied,rejected_entry_gap=gap,rejected_entry_room=room,pending_side=pending_side,open_side=open_side)
    for key,value in check.items(): equal(value,row[key])
    curves.setdefault((arm,period),[]).append((times[first:last],eq))
    groups.setdefault((arm,period),[]).append((check,items))
    casecount+=1;tradecount+=len(items)
 print('INDEPENDENT_PAIR_COMPLETE',symbol,casecount,tradecount,flush=True)
for (arm,period),values in groups.items():
 t=results['totals'][arm][period]
 items=[x for row,li in values for x in li]; vals=np.array([x['net_r'] for x in items]); pips=np.array([x['net_pips'] for x in items])
 n=len(vals);wins=int((pips>1e-9).sum());gp=vals[vals>0].sum();gl=-vals[vals<0].sum()
 checks=dict(trades=n,wins=wins,win_rate_pct=100*wins/n if n else 0,profit_factor_r=gp/gl if gl else None,net_r=float(vals.sum()),average_r=float(vals.mean()) if n else 0,net_plus_open_r=sum(row['net_plus_open_r'] for row,li in values),open_net_r=sum(row['open_net_r'] for row,li in values),positive_pairs=sum(row['net_plus_open_r']>0 for row,li in values))
 for key,value in checks.items():equal(value,t[key])
 suffix=arm if period=='all' else f'{arm}_{period}'
 with np.load(out/f'{suffix}_combined_mtm.npz') as z: combined=z['mtm']
 timeline=combined[:,0]; change=np.zeros(len(timeline))
 for timestamps,eq in curves[arm,period]:
  idx=np.searchsorted(timeline,timestamps);np.add.at(change,idx,np.diff(eq,prepend=0))
 eq=np.cumsum(change);np.testing.assert_allclose(eq,combined[:,1],rtol=1e-8,atol=1e-7)
 equal(float(np.max(np.maximum.accumulate(np.maximum(eq,0))-eq)),t['bar_close_mtm_drawdown_r'])
print('INDEPENDENT_REPLAY_COMPLETE',casecount,'cases',tradecount,'trade observations',len(groups),'aggregates and combined MTM',flush=True)

gate_count=0
for p in ('bb2_reentry','wm'):
 gates=results['gates'][p]
 for year in map(str,range(2020,2026)):
  a=results['totals'][f'{p}_rr1.0_cost1.0'][year];b=results['totals'][f'{p}_rr1.0_cost1.2'][year]
  check=dict(count=a['trades']>=100,pf=a['profit_factor_r'] is not None and a['profit_factor_r']>=1.2,average_r=a['average_r']>0,cost_stress=b['net_plus_open_r']>0,cross_pair=a['positive_pairs']>=4)
  assert gates[year]==check;gate_count+=len(check)
 a=results['totals'][f'{p}_rr1.0_cost1.0']['all'];base=results['totals']['original_rr1.0_cost1.0']['all']
 assert gates['continuous']==dict(drawdown=a['bar_close_mtm_drawdown_r']<=1.2*base['bar_close_mtm_drawdown_r']);gate_count+=1
 assert results['numeric_gates_pass'][p]==all(all(g.values()) for g in gates.values())
old=root/'agent_runs/bb_alternatives_20260925';previous=read(old/'results.json')
idxfields=('index','prep_index','confirmed_index','first','second','confirmed','entry_index','exit_index')
norm=lambda items,times:[{k:int(times[v]) if k in idxfields else v for k,v in t.items()} for t in items]
overlaps=0
for symbol in results['protocol']['symbols']:
 with np.load(out/f'{symbol}_features.npz') as z: nt=z['times']
 with np.load(root/f'agent_runs/bb3_gmo_2023_2025/{symbol}_features.npz') as z:ot=z['times']
 for policy in policies:
  for cost in (1.,1.2):
   arm=f'{policy}_rr1.0_cost{cost}'
   a=read(out/f'{symbol}_{arm}_overlap_trades.json');b=read(old/f'{symbol}_{arm}_trades.json')
   assert norm(a,nt)==norm(b,ot),(symbol,arm)
   with np.load(out/f'{symbol}_{arm}_overlap_mtm.npz') as z: a=z['mtm']
   with np.load(old/f'{symbol}_{arm}_mtm.npz') as z:b=z['mtm']
   np.testing.assert_allclose(a,b,rtol=0,atol=1e-9);overlaps+=1
for arm,periods in previous['totals'].items():
 for k,v in periods['all'].items():equal(v,results['totals'][arm]['overlap'][k])
print('INDEPENDENT_GATES_OVERLAP_COMPLETE',gate_count,'gates',overlaps,'pair overlap cases 6 overlap aggregates',flush=True)
```
