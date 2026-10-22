"""Offline coverage tests: missing periods and duplicate source records fail closed."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.historical_evidence_coverage import audit_coverage, months_between


class CoverageTests(unittest.TestCase):
    def test_month_rollover(self):
        self.assertEqual(list(months_between("2025-12-15", "2026-02-03")),
                         ["2025-12", "2026-01", "2026-02"])

    def test_missing_month_is_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "register.csv"
            with source.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["month", "source_url",
                    "source_sha256", "reviewed", "completeness_verified"])
                writer.writeheader()
                writer.writerow({"month": "2026-01", "source_url": "https://www.nseindia.com/example",
                                 "source_sha256": "a" * 64, "reviewed": "true",
                                 "completeness_verified": "true"})
            result = audit_coverage(source, "2026-01-01", "2026-02-28", root / "out")
            self.assertEqual(result["expected_months"], 2)
            self.assertEqual(result["missing_months"], 1)
            self.assertFalse(result["certified"])
            self.assertFalse(result["all_months_review_asserted"])

    def test_duplicate_month_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "register.csv"
            with source.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["month", "source_url", "source_sha256", "reviewed",
                                 "completeness_verified"])
                writer.writerow(["2026-01", "https://nseindia.com", "a" * 64, "true", "true"])
                writer.writerow(["2026-01", "https://nseindia.com", "a" * 64, "true", "true"])
            with self.assertRaises(ValueError):
                audit_coverage(source, "2026-01-01", "2026-01-31", root / "out")
