# DSH実行環境でのローカル研究環境（2026-10-19 実測）

このプロジェクトは `pyproject.toml` の `dependencies = []` のとおり、追加依存を宣言していない。
研究スクリプトが使う numpy / numba / pandas / scipy / pytest は、このPCの**Microsoft Store版 Python 3.12 の
ローカルパッケージ領域**に入っている。通常の `python` / `py -3.12` ではユーザー site-packages が
`%APPDATA%\Python\Python312\site-packages`（存在しない）を指すため `ModuleNotFoundError` になる。

## 実測結果

| コマンド | 結果 |
|---|---|
| `python -c "import numpy"` | ModuleNotFoundError（既定の `python` は依存なし） |
| `py -3.12 -c "import numpy"` | ModuleNotFoundError（同上） |
| `uv run --no-project --with numpy ...` | 失敗。uvキャッシュ `%LOCALAPPDATA%\uv\cache` が書込不可（DSH sandbox: workspace-write） |
| **下記 PYTHONPATH 方式** | **成功**。numpy 2.2.6 / numba 0.65.1 / pandas 2.3.3 / pytest 9.0.2、numba JIT 実行も成功 |

## 研究実行の推奨コマンド（DSH sandbox: workspace-write）

```powershell
$env:PYTHONPATH = "src;$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\site-packages"
python -B <script>.py
```

- `-B` を付けて bytecode 書込みを抑止する。
- テストは `.pytest_cache` への書込みが sandbox で拒否される場合があるため
  `python -B -m pytest <tests> -q -p no:cacheprovider` を使う。
- リポジトリ内 `src` を `PYTHONPATH` の先頭に置く（`from forextester_backtest...` のため）。
- リポジトリ外（uvキャッシュ、`%APPDATA%\Python` 等）への書込みは sandbox により拒否される。
  追加パッケージが必要な場合は、無断で外部書込みを要求せず、責任者へ確認する。

## 制約・未確認

- pytest の `tmp_path` フィクスチャは `%TEMP%` への書込み拒否で失敗する。テストは `capsys` や
  インメモリ比較で書く（`tests/test_gap_fill_m5.py` はこの方式で68件緑、`--basetemp` 不要）。
- `--basetemp` で作った `pytest_tmp_gap/`・`.pytest_tmp_gap/` および `.pytest_cache/` は
  sandbox の ACL により**列挙・削除が拒否**され、通常権限では消せない（2026-10-19 実測）。
  回避するには最初から作らないこと。
- 上記は本セッション（DSH / workspace-write）での実測であり、Codex CLI や別 sandbox 設定での再現は未確認。
- Python 3.12 + numpy 2.2.6 での再現であり、過去実験が使った解釈系と同一とは限らない。
  既存の凍結済み結果と数値照合する場合は、この点を差分要因として扱う。
- この文書は環境の記録であり、戦略の性能評価ではない。
