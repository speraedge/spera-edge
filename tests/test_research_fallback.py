import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from edge_core.research_fallback import load_leadership


class FallbackTests(unittest.TestCase):
    def test_missing_latest_uses_most_recent_eligible_verified_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            latest, history = root / "latest", root / "history"
            latest.mkdir()
            history.mkdir()
            weeks = []
            for day in ("2026-10-09", "2026-10-16", "2026-10-30"):
                archive = history / f"nifty500_{day}.csv"
                pd.DataFrame({"Ticker": ["AAA", "BBB"], "Data_Quality": ["REVIEW", "PASS"],
                              "Ret_6M": [0.2, 0.3], "Ret_12M": [0.4, 0.5],
                              "AnnVol": [0.2, 0.3], "Percentile": [85, 95],
                              "Pure_Momentum_Rank": [2, 1]}).to_csv(archive, index=False)
                weeks.append({"weekly_key": day, "file": archive.name,
                              "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
            (history / "manifest.json").write_text(json.dumps({"universe": "NIFTY_500", "weeks": weeks}))
            frame, day, historical = load_leadership(latest, history, latest_date="2026-10-23")
            self.assertEqual(day, "2026-10-16")
            self.assertTrue(historical)
            self.assertEqual(len(frame), 2)
            (history / "nifty500_2026-10-16.csv").write_text("corrupt")
            frame, day, historical = load_leadership(latest, history, latest_date="2026-10-23")
            self.assertEqual(day, "2026-10-09")
            self.assertTrue(historical)
            self.assertEqual(len(frame), 2)

    def test_missing_latest_uses_verified_historical_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            latest = root / "latest"
            history = root / "history"
            latest.mkdir()
            history.mkdir()
            archive = history / "nifty500_2026-10-16.csv"
            pd.DataFrame({
                "Ticker": ["AAA", "BBB"],
                "Data_Quality": ["REVIEW", "PASS"],
                "Ret_6M": [0.2, 0.3],
                "Ret_12M": [0.4, 0.5],
                "AnnVol": [0.2, 0.3],
                "Percentile": [85, 95],
                "Pure_Momentum_Rank": [2, 1],
            }).to_csv(archive, index=False)
            (history / "manifest.json").write_text(json.dumps({
                "universe": "NIFTY_500",
                "weeks": [{"weekly_key": "2026-10-16", "file": archive.name,
                           "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}],
            }))
            frame, day, fallback = load_leadership(latest, history)
            self.assertTrue(fallback)
            self.assertEqual(day, "2026-10-16")
            self.assertEqual(set(frame["Symbol"]), {"AAA", "BBB"})
            archive.write_text("tampered")
            frame, _, _ = load_leadership(latest, history)
            self.assertIsNone(frame)


if __name__ == "__main__":
    unittest.main()
