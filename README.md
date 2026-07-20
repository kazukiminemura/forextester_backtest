# Forex Tester History Backtester

Forex Tester 6 の `History` ディレクトリを読み取り専用で参照し、バー抽出、
時間足集約、tick 抽出、簡易ストラテジーのバックテストを行う Python ツールです。

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

# SMA 20/50 クロスを1時間足でバックテスト
forextester-backtest backtest EURUSD --start 2023-01-01 --end 2024-01-01 --timeframe 1h --fast 20 --slow 50 --lots 0.1 --trades-output trades.csv
```

`--end` を日付だけで指定した場合は、その日の23:59:59までを含みます。

既定の履歴場所は `C:\ForexTester6\data\History` です。別の場所は各コマンドの
前に `--history-dir PATH` を指定します。

```powershell
forextester-backtest --history-dir D:\History symbols
```

## バックテストの前提

- シグナルはバー終値で計算し、次のバー始値で約定します（先読み防止）。
- `Bars.dat` は Bid 価格として扱い、買い約定時に `info.dat` の spread を加算します。
- 最終バーで未決済ポジションを強制決済します。
- 損益は銘柄のクオート通貨基準です。たとえば EURUSD は USD、EURJPY は JPY です。
- 口座通貨への換算、スワップ、スリッページ、証拠金・ロスカットは未実装です。
- `ticks.dat` は参照できますが、現在のバックテスト約定モデルはバー単位です。

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
