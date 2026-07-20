# Forex Tester History Backtester

Forex Tester 6 の `History` ディレクトリを読み取り専用で参照し、バー抽出、
時間足集約、tick 抽出、田向式「4Hダウ＋1H押し目レンジ」のバックテストを行う
Python ツールです。

## セットアップ

Python 3.11 以上だけで動作します。外部パッケージは不要です。

```powershell
cd C:\Users\minemura\projects\forextester_backtest
python -m pip install -e .
```

インストールせずに使う場合は、コマンドの先頭を
`$env:PYTHONPATH='src'; python -m forextester_backtest` に置き換えてください。

## 基本操作

```powershell
# 参照可能な銘柄とデータ期間
forextester-backtest symbols

# 銘柄情報
forextester-backtest info EURUSD

# 1時間足を表示（CSV）
forextester-backtest bars EURUSD --start 2024-01-01 --end 2024-01-07 --timeframe 1h --limit 20

# tickを抽出（巨大ファイルも日時から二分探索するため全件ロードしません）
forextester-backtest ticks EURUSD --start "2024-08-30 20:59:50" --end "2024-08-30 21:00:00" --limit 100

# 田向式 4Hダウ＋1H押し目レンジをバックテスト
forextester-backtest backtest EURUSD --start 2024-01-01 --end 2024-08-30 --lots 0.1 --trades-output trades.csv
```

`--preset auto`（既定）は銘柄名からプリセットを自動選択します。JPYクロス
（`USDJPY`、`EURJPY` など）はUSDJPYの探索値、`EURUSD`だけはEURUSDで独立探索した
研究用設定を使用します。EURUSD設定をGBPUSDへ移した未使用期間テストが4戦全敗
だったため、他のUSDクロスには共有せずPine既定値を使用します。`XAUUSD`、
`BTCUSD`などもFXクロスとして扱いません。

```powershell
python -m forextester_backtest backtest USDJPY --start 2004-01-01 --end 2024-08-30 --lots 0.1 --trades-output trades.csv
```

JPYクロスは「買いのみ・小レンジ1.0 ATR以下・0.5R全決済」、EURUSD研究設定は
「買いのみ・小レンジ0.75 ATR以下・0.5R全決済」です。
添付Pineと同じ設定へ戻す場合は `--preset pine` を指定します。個別の
`--direction`、`--max-range-atr`、`--target-r`、`--target-fraction` はプリセットより優先されます。

プリセットを明示する場合は `--preset jpy-cross` または
`--preset eurusd-research` を指定します。旧名称 `--preset usdjpy-70` と
`--preset usd-cross` は互換性のための別名として残しています。

探索条件、期間別成績、過学習上の注意は
[`docs/usdjpy_optimization.md`](docs/usdjpy_optimization.md) を参照してください。
EURUSDの独立探索結果は
[`docs/eurusd_optimization.md`](docs/eurusd_optimization.md) を参照してください。
XAUUSD（金）の探索結果と不採用理由は
[`docs/xauusd_optimization.md`](docs/xauusd_optimization.md) を参照してください。

TradingViewへ追加できるシグナル表示用Pine Scriptは
[`scripts/tradingview/tamukai_pair_signal_indicator.pine`](scripts/tradingview/tamukai_pair_signal_indicator.pine)、
追加手順は[`scripts/tradingview/README.md`](scripts/tradingview/README.md)にあります。

`--end` を日付だけで指定した場合は、その日の23:59:59までを含みます。

取引CSVには、別銘柄の実行結果との取り違えを防ぐため `symbol` と `preset` を
各行へ出力します。

既定の履歴場所は `C:\ForexTester6\data\History` です。別の場所は各コマンドの
前に `--history-dir PATH` を指定します。

```powershell
forextester-backtest --history-dir D:\History symbols
```

## バックテストの前提

- 参照元は [`tamukai_1h_pullback_range_strategy.pine`](https://github.com/kazukiminemura/chart_analyser_y/blob/main/scrips/tamukai_1h_pullback_range_strategy.pine) です。
- 確定済み4時間足のダウ構造、21SMA、ATR、確定済みピボットだけで方向を判定します。
- 直前3本の1時間足から小レンジを作り、押し・戻り、SMA・旧高安値、SL幅、上位足の壁までの余地を検査します。
- 条件成立後にレンジ外へ逆指値を置き、既定8本で失効します。条件成立バー内では約定しません。
- 構造SLを固定し、半分を1Rで利確後、残りを確定1時間足ピボットで追随します。
- 開始日より前の履歴も4H構造と指標のウォームアップに使いますが、注文は指定期間内だけです。
- 重要指標カレンダーは取得しません。Pine版の手動停止は `--disable-entries` で全期間に適用できます。
- `Bars.dat` は Bid 価格として扱い、買い約定時に `info.dat` の spread を加算します。
- 同一バー内の価格経路はTradingView同様、始値に近い高値・安値側を先に通るOHLC経路で判定します。tick再生ではありません。
- 最終バーで未決済ポジションを強制決済します。
- 損益は銘柄のクオート通貨基準です。たとえば EURUSD は USD、EURJPY は JPY です。
- 口座通貨への換算、スワップ、スリッページ、証拠金・ロスカットは未実装です。
- `ticks.dat` は参照できますが、現在のバックテスト約定モデルはバー単位です。

Pine版の表示専用の日足・週足ラインと状態テーブルは、売買判定に使われないため移植していません。
また、Pine版の「資産の10%」ではなく、CLIの `--lots` で固定数量を指定します。

主要パラメータはPine版と同じ既定値です。変更可能な全項目は次で確認できます。

```powershell
forextester-backtest backtest --help
```

このため、結果は手法の一次検証用です。実運用判断には、口座通貨換算、可変スプレッド、
スリッページ、スワップ、ブローカー固有ルールを追加してください。

## 独自手法を追加する

`Strategy` を継承し、各バーで希望するポジションを `-1`（売り）、`0`（なし）、
`1`（買い）として返します。判定結果はエンジンが次バー始値で執行します。

```python
from forextester_backtest import BacktestEngine, HistoryRepository, Strategy

class MyStrategy(Strategy):
    def on_bar(self, bar):
        return 1 if bar.close > bar.open else -1

history = HistoryRepository(r"C:\ForexTester6\data\History")
engine = BacktestEngine(history.metadata("EURUSD"), lots=0.1)
result = engine.run(history.bars("EURUSD", timeframe="1h"), MyStrategy())
print(result.as_dict())
```

田向式専用エンジンは `TamukaiBacktester`、設定値は `TamukaiConfig` から利用できます。

## ライセンスと出典

田向式戦略モジュールは、MPL-2.0で公開された上記Pine Scriptを基にしています。
原典URLとMPL-2.0表示をコードに残し、パッケージのライセンス表記もMPL-2.0にしています。

## データ形式

実ファイルから次の固定長形式を読み取ります。

- `Bars.dat`: 4 byte 件数 + 48 byte/件（OLE日時、Open、Close、High、Low、Volume）
- `ticks.dat`: 4 byte 件数 + 28 byte/件（OLE日時、Bid、Ask、Volume）
- `info.dat`: `key=value` 形式の銘柄メタ情報

History 配下は一切変更せず、読み取り専用で開きます。

## テスト

```powershell
python -m unittest discover -s tests -v
```
