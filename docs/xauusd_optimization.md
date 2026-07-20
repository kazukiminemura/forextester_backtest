# XAUUSD（金）パラメータ探索

## 結論（RR 1:1再探索後）

初回探索の0.75R半分利確候補は完全未使用期間（2025–2026年）で崩れた。
その後、RR 1:1を「1Rで全量決済」と定義して他のパラメータを再探索した結果、
学習・検証だけで首位になった候補が完全未使用期間でもプラスを維持した。

ただし最終確認は13取引に留まるため、現時点では実運用プリセットではなく
`xauusd-rr1-research`候補として扱う。

## データと分割

- 銘柄: XAUUSD（Advanced Data Feed）
- 1時間足: 2013-05-01～2026-07-17
- 学習: 2013～2021年
- 検証: 2022～2024年
- 最終確認（候補選定には不使用）: 2025～2026年
- 固定ロット: 0.1 lot
- 固定スプレッド: 0.376 USD

## RR 1:1候補

```text
direction                  long
first_target_r             1.00
first_target_fraction      1.00（全量決済）
move_stop_to_break_even    false
range_bars                 4
max_range_atr              1.50
min_slope_atr              0.06
min_pullback_atr           0.25
zone_tolerance_atr         0.40
entry_buffer_pips          40（0.40 USD）
stop_buffer_pips           40（0.40 USD）
min_room_r                 1.00
max_risk_pips              0（絶対上限なし）
max_risk_atr               2.00
order_expiry_bars          8
```

| 期間 | 取引数 | 勝率 | 純損益 | PF | 期待値R |
|---|---:|---:|---:|---:|---:|
| 学習 2013–2021 | 83 | 63.86% | +766.62 USD | 1.485 | +0.171 |
| 検証 2022–2024 | 27 | 62.96% | +268.95 USD | 1.405 | +0.176 |
| 最終確認 2025–2026 | 13 | 53.85% | +190.41 USD | 1.222 | +0.048 |

全期間では123取引、勝率62.60%、純損益+1,225.98 USD、PF 1.395、
最大ドローダウン421.34 USD（3.71%）だった。
勝率のWilson 95%信頼区間は53.79～70.65%だった。

候補選定は学習・検証期間だけで行った。2025–2026年は順位付けやパラメータ変更に
使わず、選定後の最終確認にだけ使用した。

## RR 1:1の探索範囲

段階的に合計597通りを評価した。

1. シグナル条件192通り: 方向、最大レンジ、4H傾き、最小押し戻り
2. リスク条件243通り: バッファ、壁までの余地、ATRリスク上限、注文期限
3. 文脈条件162通り: レンジ本数、参照帯許容幅、時間帯

実践候補の最低条件は、学習60取引・検証15取引、両期間で純損益プラス、
PF 1超、期待値Rプラスとした。第3段階では30候補がこの条件を満たし、
首位候補を未使用期間へ一度だけ通した。

## 安定性上の注意

近傍値も確認したところ、`zone_tolerance_atr=0.40`を0.25または0.15へ下げると、
未使用期間は13取引、純損益-37.26 USD、PF 0.96になった。候補は参照帯の
許容幅に感度がある。

年別では2013～2026年の14年中、純損益プラスが8年、マイナスが6年だった。
2026年は7月17日までの2取引だけで-50.72 USDのため、年単位の安定性が
確認できたとはまだ判断しない。

固定スプレッド0.376 USDは反映しているが、スリッページ、可変スプレッド、
スワップ、資金量に応じたポジションサイズは未実装である。

## 金向けの前処理

Pine既定値は最大リスク80 pipsで、XAUUSDでは価格差0.80 USDに相当する。
この上限では全期間0取引だった。探索では絶対pips上限を無効化し、既存の
`max_risk_atr=2.5`をリスク上限として残した。また、スプレッドを考慮して
エントリーとストップのバッファを各20 pips（0.20 USD）とした。

## 初回探索（RR 1:1以外を含む）

108通りを比較した。

- 売買方向: both / long / short
- 最大レンジ幅: 0.75 / 1.0 / 1.25 / 1.5 ATR
- 第1利確: 0.5R / 0.75R / 1.0R
- 決済: 全決済、半分決済、半分決済＋建値移動

候補順位は学習・検証期間だけで決め、最終確認期間の結果は順位に使っていない。
最低件数は学習60取引、検証15取引とした。

## 初回探索の最良候補（不採用）

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

RR 1:1の三段階探索:

```powershell
$env:PYTHONPATH='src'
python scripts/optimize_xauusd.py --stage rr1-signal --top 192 `
  --output scripts/xauusd_rr1_signal_results.json
python scripts/optimize_xauusd.py --stage rr1-risk `
  --seed-json scripts/xauusd_rr1_signal_results.json `
  --seed-index 59 --seed-index 98 --seed-index 22 --top 243 `
  --output scripts/xauusd_rr1_risk_results.json
python scripts/optimize_xauusd.py --stage rr1-context `
  --seed-json scripts/xauusd_rr1_risk_results.json `
  --seed-index 9 --seed-index 10 --seed-index 0 --top 162 `
  --output scripts/xauusd_rr1_context_results.json
```

RR 1:1候補単体の再現:

```powershell
$env:PYTHONPATH='src'
python -m forextester_backtest backtest XAUUSD `
  --start 2013-05-01 --end 2026-07-17 --preset pine --direction long `
  --range-bars 4 --max-range-atr 1.5 --min-slope-atr 0.06 `
  --min-pullback-atr 0.25 --zone-tolerance-atr 0.40 `
  --entry-buffer-pips 40 --stop-buffer-pips 40 --min-room-r 1 `
  --max-risk-pips 0 --max-risk-atr 2 --order-expiry-bars 8 `
  --target-r 1 --target-fraction 1 --json
```

初回探索:

```powershell
$env:PYTHONPATH='src'
python scripts/optimize_xauusd.py --top 108 --output scripts/xauusd_optimization_results.json
```

初回研究候補単体の再現:

```powershell
$env:PYTHONPATH='src'
python -m forextester_backtest backtest XAUUSD `
  --start 2013-05-01 --end 2026-07-17 --preset pine `
  --entry-buffer-pips 20 --stop-buffer-pips 20 --max-risk-pips 0 `
  --max-range-atr 1.25 --target-r 0.75 --target-fraction 0.5 `
  --direction short --json
```

各段階の個別結果は`../scripts/xauusd_rr1_signal_results.json`、
`../scripts/xauusd_rr1_risk_results.json`、
`../scripts/xauusd_rr1_context_results.json`に保存している。
