# XAUUSD（金）パラメータ探索

## 結論

金向けの候補パラメータは得られたものの、完全未使用期間（2025–2026年）で
崩れたため、実運用プリセットには採用しない。

## データと分割

- 銘柄: XAUUSD（Advanced Data Feed）
- 1時間足: 2013-05-01～2026-07-17
- 学習: 2013～2021年
- 検証: 2022～2024年
- 最終確認（候補選定には不使用）: 2025～2026年
- 固定ロット: 0.1 lot
- 固定スプレッド: 0.376 USD

## 金向けの前処理

Pine既定値は最大リスク80 pipsで、XAUUSDでは価格差0.80 USDに相当する。
この上限では全期間0取引だった。探索では絶対pips上限を無効化し、既存の
`max_risk_atr=2.5`をリスク上限として残した。また、スプレッドを考慮して
エントリーとストップのバッファを各20 pips（0.20 USD）とした。

## 探索範囲

108通りを比較した。

- 売買方向: both / long / short
- 最大レンジ幅: 0.75 / 1.0 / 1.25 / 1.5 ATR
- 第1利確: 0.5R / 0.75R / 1.0R
- 決済: 全決済、半分決済、半分決済＋建値移動

候補順位は学習・検証期間だけで決め、最終確認期間の結果は順位に使っていない。
最低件数は学習60取引、検証15取引とした。

## 学習・検証での最良候補

```text
direction                  short
max_range_atr              1.25
first_target_r             0.75
first_target_fraction      0.50
move_stop_to_break_even    false
entry_buffer_pips          20
stop_buffer_pips           20
max_risk_pips              0（絶対上限なし）
max_risk_atr               2.5
```

| 期間 | 取引数 | 勝率 | 純損益 | PF | 期待値R |
|---|---:|---:|---:|---:|---:|
| 学習 2013–2021 | 82 | 34.15% | +782.11 USD | 1.529 | +0.250 |
| 検証 2022–2024 | 18 | 44.44% | +248.95 USD | 1.753 | +0.219 |
| 最終確認 2025–2026 | 16 | 12.50% | -1,522.45 USD | 0.299 | -0.484 |

全期間では116取引、純損益-491.39 USD、PF 0.877、最大ドローダウン
1,658.98 USD（14.86%）だった。学習・検証条件を満たした21候補すべてが
最終確認期間でマイナス期待値となった。

この結果は、近年の金相場に対して過去の売り優位性が継続しなかったことを示す。
直近期間に合わせてlongへ最適化することは可能だが、取引数が少なく、同じ
過学習を繰り返すため採用しない。

## 再実行

```powershell
$env:PYTHONPATH='src'
python scripts/optimize_xauusd.py --top 108 --output scripts/xauusd_optimization_results.json
```

研究候補単体の再現:

```powershell
$env:PYTHONPATH='src'
python -m forextester_backtest backtest XAUUSD `
  --start 2013-05-01 --end 2026-07-17 --preset pine `
  --entry-buffer-pips 20 --stop-buffer-pips 20 --max-risk-pips 0 `
  --max-range-atr 1.25 --target-r 0.75 --target-fraction 0.5 `
  --direction short --json
```

全108候補の個別結果は`../scripts/xauusd_optimization_results.json`に保存している。
