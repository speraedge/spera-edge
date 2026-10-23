"""Integration regression: canonical snapshot validator rejects corrupt OHLCV."""
import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from edge_core.snapshot_integrity import validate_snapshot


class CanonicalSnapshotOhlcvTests(unittest.TestCase):
    def build(self, root, *, corrupt=False):
        names = [f"S{i:03d}" for i in range(500)]
        pd.DataFrame({"Symbol": names, "Data_Quality": ["REVIEW"] * 500}).to_csv(
            root / "leadership.csv", index=False)
        dates = pd.bdate_range("2025-12-01", periods=220)
        for name, value in (("open", 100.5), ("close", 100.0), ("high", 102.0),
                            ("low", 99.0), ("volume", 1000.0)):
            data = pd.DataFrame(value, index=dates, columns=names)
            if corrupt and name == "high":
                data.iloc[0, 0] = 90.0
            data.index.name = "Date"
            data.to_csv(root / (name + ".csv"))
        (root / "metadata.json").write_text(json.dumps({
            "universe": "NIFTY_500", "certified": False, "expected": 500,
            "mapped": 500, "retrieved": 500, "retrieval_failures": [],
            "research_pass": 0, "research_review": 500, "research_fail": 0,
            "last_session": str(dates[-1].date())
        }), encoding="utf-8")

    def test_valid_research_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.build(root)
            self.assertEqual(validate_snapshot(root)["retrieved"], 500)

    def test_invalid_candle_fails_canonical_validator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.build(root, corrupt=True)
            with self.assertRaisesRegex(ValueError, "Opening prices outside observed candle range"):
                validate_snapshot(root)


if __name__ == "__main__":
    unittest.main()
