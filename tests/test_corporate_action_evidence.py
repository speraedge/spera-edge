"""Offline tests for Milestone 2 corporate-action audit. No external requests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from edge_core.corporate_action_evidence import review_events


class CorporateActionEvidenceTests(unittest.TestCase):
    def test_official_isin_mismatch_is_quarantined(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "events.csv"
            with source.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["symbol", "isin", "purpose", "ex_date", "source_url"])
                writer.writeheader()
                writer.writerow({"symbol": "ABC", "isin": "WRONG", "purpose": "Split 1:2",
                                 "ex_date": "2026-10-20", "source_url": "https://www.nseindia.com/example"})
            review_events(source, root / "out", {"ABC": "INE000A00001"})
            with (root / "out" / "corporate_action_review.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["status"], "ISIN_MISMATCH_REVIEW")
            self.assertEqual(rows[0]["approved"], "False")

    def test_fail_closed_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "official_input.csv"
            with source.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["symbol", "isin", "purpose", "ex_date", "source_url"])
                writer.writeheader()
                writer.writerows([
                    {"symbol": "ABC", "isin": "INE000A00001", "purpose": "Bonus 1:1",
                     "ex_date": "2026-10-20", "source_url": "https://www.nseindia.com/example"},
                    {"symbol": "ABC", "isin": "INE000A00001", "purpose": "Split",
                     "ex_date": "2026-10-20", "source_url": "https://www.nseindia.com/example"},
                    {"symbol": "XYZ", "isin": "", "purpose": "Bonus 1:1",
                     "ex_date": "2026-10-20", "source_url": ""},
                    {"symbol": "ABC", "isin": "INE000A00001", "purpose": "Cancelled bonus",
                     "ex_date": "2026-10-21", "source_url": "https://www.nseindia.com/example"}
                ])
            summary = review_events(source, root / "audit", {"ABC", "XYZ"})
            self.assertEqual(summary["source_rows"], 4)
            self.assertEqual(summary["approved_factors"], 0)
            self.assertFalse(summary["adjusted_prices_ready"])
            with (root / "audit" / "corporate_action_review.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["status"], "MULTIPLE_EVENTS_SAME_DATE_REVIEW")
            self.assertEqual(rows[1]["status"], "MULTIPLE_EVENTS_SAME_DATE_REVIEW")
            self.assertEqual(rows[2]["status"], "MISSING_OFFICIAL_SOURCE")
            self.assertEqual(rows[3]["status"], "CANCELLED_EVENT")
            self.assertTrue(all(row["approved"] == "False" and not row["adjustment_factor"] for row in rows))
            self.assertEqual(json.loads((root / "audit" / "corporate_action_summary.json").read_text())["source_rows"], 4)


if __name__ == "__main__":
    unittest.main()
