"""Preserve and verify the existing Japanese stock snapshot; never access network."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agent_runs/tamukai_stocks_daily_20260926/data"
CACHE = ROOT / "data/stocks/yahoo/jp_largecap10_20260926"


def verify(directory: Path) -> list[Path]:
    manifest = directory / "manifest.json"
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    files = [manifest]
    if len(metadata["symbols"]) != 10:
        raise ValueError("Expected the fixed ten-symbol snapshot")
    for symbol, record in metadata["symbols"].items():
        if Path(symbol).name != symbol or "/" in symbol or "\\" in symbol:
            raise ValueError("Invalid symbol path")
        for suffix, key in (("json", "raw_sha256"), ("csv", "csv_sha256")):
            path = directory / f"{symbol}.{suffix}"
            if hashlib.sha256(path.read_bytes()).hexdigest() != record[key]:
                raise ValueError(f"Snapshot checksum mismatch: {path}")
            files.append(path)
    return files


def preserve(source: Path = SOURCE, destination: Path = CACHE) -> Path:
    if destination.exists():
        verify(destination)
        return destination
    files = verify(source)
    destination.mkdir(parents=True)
    for path in files:
        shutil.copy2(path, destination / path.name)
    verify(destination)
    return destination


if __name__ == "__main__":
    print(preserve())
