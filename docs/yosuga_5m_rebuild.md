# よすが式 5分足ロジック再構築

## 新しい判断順序

1. 確定済み4時間足ピボットの HH+HL / LH+LL で方向を決める。
2. 確定済み15分足ピボットで押し目（安値切り上げ）・戻り（高値切り下げ）を確認する。
3. 5分足が15分足の支持抵抗またはEMAへ戻った場所だけを見る。
4. 長いヒゲまたは包み足に加え、既定では前足高値・安値の更新を要求する。
5. Entryはシグナル確定価格、SLは15分足スイング外、TPは全決済の1Rとする。

## 検証結果

Forex TesterのUSDJPY、GBPJPY、AUDJPY、CHFJPYを2010-2026年の4期間に分けて検証した。

- 4H + 5分足PA: 64候補、合格0
- 4H + 15分足構造 + 5分足PA: 64候補、合格0
- 15分足ラインのダマシ抜け回収: 64候補、合格0
- 通貨別でも学習期間と検証期間を同時にPF 1以上とした候補: 0
- 同一5分足内のSL/TP同時到達は主要候補で概ね0-4%であり、敗因の中心ではない

以上から、再構築したロジックは研究用として表示できる状態まで実装するが、実運用プリセットには採用しない。勝率を合わせるための追加条件探索も行わない。

## 成果物

- Pine: `scripts/tradingview/yosuga_5m_rebuilt_indicator.pine`
- 検証器: `scripts/research_strict_rr_portfolio.py`
- 結果: `scripts/strict_rr_portfolio_5m_yosuga_ambiguity_results.json`
- 結果: `scripts/strict_rr_portfolio_5m_yosuga_sweep_results.json`

## 通貨ペア・狙い目一覧

Pine v2では12通貨を同じ条件で監視し、チャート右下へ次の順で表示する。

- `BUY候補` / `SELL候補`: 4H方向、15分構造、5分PA、リスク条件がすべて成立
- `押し目待ち` / `戻り待ち`: 4H方向と15分構造まで成立
- `上昇監視` / `下降監視`: 4Hダウだけ成立
- `なし`: 4Hダウが不明確

既定の12通貨は EURUSD、GBPUSD、USDJPY、AUDUSD、NZDUSD、USDCAD、USDCHF、EURJPY、GBPJPY、AUDJPY、CHFJPY、EURGBP。設定画面から任意のTradingView銘柄へ変更できる。
