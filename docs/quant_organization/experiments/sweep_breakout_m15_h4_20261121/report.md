# スイープ足突破の売買成績

Forex TesterのUSDJPY・EURUSD・GBPUSD・AUDUSD・USDCHF、2017〜2025年エントリー。利益が正の決済を勝ち、建値を分母に含めた。PFは初期リスクを一定の1Rとした総利益÷総損失の絶対値。建値は丸め誤差1e-10R以内。費用は各取引から往復1 pipを控除した。

|時間足|方向|取引数|費用前勝率|費用前PF|費用後勝率|費用後PF|
|---|---|---:|---:|---:|---:|---:|
|15分|買い|14,649|47.17%|0.881|43.97%|0.410|
|15分|売り|14,204|48.11%|0.917|45.00%|0.443|
|15分|合算|28,853|47.63%|0.898|44.48%|0.426|
|4時間|買い|1,011|48.47%|0.933|48.37%|0.786|
|4時間|売り|990|49.39%|0.972|49.19%|0.814|
|4時間|合算|2,001|48.93%|0.952|48.78%|0.800|

|エントリー期間|15分足 件数／費用後勝率／PF|4時間足 件数／費用後勝率／PF|
|---|---|---|
|2017〜2019|9,351／44.13%／0.413|658／47.42%／0.746|
|2020〜2022|9,566／45.14%／0.459|640／50.94%／0.873|
|2023〜2025|9,936／44.16%／0.409|703／48.08%／0.787|

現行Pineの各時間足で、上ヒゲのスイープ足高値を後続足の終値が抜けば買い、下ヒゲのスイープ足安値を終値が割れば売り。次足始値で入り、元のピボットで損切り、等幅1Rで全利確。買いと売りは独立に判定した。保存M1で到達順を判定し、同じ1分内で両方に触れ順序不明なら損切り優先。損切りを飛び越えた場合は始値約定。手数料やスワップを個別に再現していない。

4時間足は保存時刻0時を起点としたため、TradingViewの配信元によっては足の境界やシグナルが異なる。USDCHFの粗い保存価格を考慮し除外した場合も、費用後PFは15分足0.421、4時間足0.820。どちらの時間足も3つの期間すべてで費用後の総損失が総利益を上回った。

[事前仕様](protocol.json) / [取引明細](../../../../agent_runs/sweep_breakout_m15_h4_20261121/trades.csv.gz) / [通貨・期間別結果](../../../../agent_runs/sweep_breakout_m15_h4_20261121/results.json) / [データ台帳](data_inventory.md) / [独立再生](validation.md) / [監査](audit.md)

## 検証版とチャート表示版の再現

検証時のPineはコミット `e77c837f57f2d385588a2b87df4320fef3984270` の `scripts/tradingview/sweep_breakdown_levels_m15.pine` に保存した。後続の表示版はスイープ点線と価格帯を同じインジケーターに追加している。固定した研究の再実行は、Windowsの同じ保存履歴を持つ環境で以下をプロジェクト直下から実行する。現在の表示版をメモリに保持し、終了時に戻す。

```python
from pathlib import Path
import os
import subprocess

source = Path("scripts/tradingview/sweep_breakdown_levels_m15.pine")
current = source.read_bytes()
frozen = subprocess.check_output([
    "git", "show", "e77c837f57f2d385588a2b87df4320fef3984270:" + source.as_posix(),
])
environment = dict(os.environ, PYTHONPATH="src;.")
try:
    source.write_bytes(frozen)
    subprocess.run(["python", "-m", "scripts.research_sweep_breakout_m15_h4"],
                   env=environment, check=True)
finally:
    source.write_bytes(current)
```

公開時の再確認で研究コードの回帰12項目とruffが合格した。共通依存 `research_fx65_pf15.py` の既存E741 2件は入力SHAを維持するため保持し、この依存だけE741を除外してruffを確認した。新規3 Pythonファイルは除外指定なしで合格した。
