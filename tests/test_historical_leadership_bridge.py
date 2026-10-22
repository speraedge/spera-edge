import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from edge_core.historical_leadership_bridge import historical_leadership_context


class HistoricalBridgeTests(unittest.TestCase):
    def test_prior_week_only_and_missing_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b"Ticker,Pure_Momentum_Rank,Data_Quality\nABC,7,REVIEW\n"
            (root / "week.csv").write_bytes(data)
            (root / "manifest.json").write_text(json.dumps({
                "universe": "NIFTY_500", "weeks": [{
                    "weekly_key": "2026-10-16", "file": "week.csv",
                    "rows": 1, "sha256": hashlib.sha256(data).hexdigest()}]}))
            events = pd.DataFrame({"Symbol": ["ABC", "ABC", "ABC", "OTHER"],
                                   "Session": ["2026-10-15", "2026-10-16",
                                               "2026-10-19", "2026-10-19"]})
            result = historical_leadership_context(events, root)
            self.assertTrue(pd.isna(result.iloc[0]["Wisdom_Rank"]))
            self.assertTrue(pd.isna(result.iloc[1]["Wisdom_Rank"]))
            self.assertEqual(result.iloc[2]["Wisdom_Rank"], 7)
            self.assertTrue(pd.isna(result.iloc[3]["Wisdom_Rank"]))
            self.assertEqual(result.iloc[2]["Wisdom_Week"], "2026-10-16")

    def test_tampered_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "week.csv").write_text("Ticker,Pure_Momentum_Rank,Data_Quality\nA,1,PASS\n")
            (root / "manifest.json").write_text(json.dumps({
                "universe": "NIFTY_500", "weeks": [{
                    "weekly_key": "2026-10-16", "file": "week.csv",
                    "rows": 1, "sha256": "wrong"}]}))
            with self.assertRaises(ValueError):
                historical_leadership_context(pd.DataFrame({"Symbol":["A"],"Session":["2026-10-20"]}),root)
