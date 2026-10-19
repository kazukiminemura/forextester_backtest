import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "stock_data_cache", Path(__file__).resolve().parents[1] / "scripts/stock_data_cache.py")
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class StockCacheTests(unittest.TestCase):
    def test_copy_reuse_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "source", Path(folder) / "cache"
            source.mkdir()
            records = {}
            for i in range(10):
                records[str(i)] = {}
                for suffix, key in (("json", "raw_sha256"), ("csv", "csv_sha256")):
                    content = f"original-{i}-{suffix}".encode()
                    (source / f"{i}.{suffix}").write_bytes(content)
                    records[str(i)][key] = hashlib.sha256(content).hexdigest()
            (source / "manifest.json").write_text(json.dumps({"symbols": records}))
            self.assertEqual(cache.preserve(source, target), target)
            self.assertEqual(len(cache.verify(target)), 21)
            before = (target / "manifest.json").stat().st_mtime_ns
            self.assertEqual(cache.preserve(Path(folder) / "missing", target), target)
            self.assertEqual((target / "manifest.json").stat().st_mtime_ns, before)
            (target / "0.csv").write_text("corrupted")
            with self.assertRaises(ValueError):
                cache.preserve(source, target)
            self.assertEqual((target / "0.csv").read_text(), "corrupted")


if __name__ == "__main__":
    unittest.main()
