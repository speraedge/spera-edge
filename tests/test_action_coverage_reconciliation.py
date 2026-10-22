"""Offline reconciliation tests for missing months and unverified event terms."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.action_coverage_reconciliation import reconcile_action_coverage


class ReconciliationTests(unittest.TestCase):
    def test_missing_month_and_unverified_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            coverage = root / "coverage.csv"
            actions = root / "actions.csv"
            with coverage.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["month", "status"])
                writer.writerow(["2026-01", "REVIEW_ASSERTED_COMPLETE"])
            with actions.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["row", "symbol", "ex_date", "status"])
                writer.writerow(["2", "ABC", "2026-01-15", "REVIEW_OFFICIAL_TERMS"])
                writer.writerow(["3", "ABC", "2026-02-15", "REVIEW_OFFICIAL_TERMS"])
                writer.writerow(["4", "XYZ", "2026-01-20", "MISSING_OFFICIAL_SOURCE"])
            result = reconcile_action_coverage(actions, coverage, root / "out")
            self.assertEqual(result["event_count"], 3)
            self.assertEqual(result["status_counts"]["HISTORICAL_COVERAGE_GAP"], 1)
            self.assertEqual(result["status_counts"]["EVENT_EVIDENCE_UNRESOLVED"], 1)
            self.assertEqual(result["status_counts"]["REQUIRES_INDEPENDENT_EVENT_VERIFICATION"], 1)
            self.assertFalse(result["certified"])
            self.assertFalse(result["historical_price_adjustments_authorized"])

    def test_duplicate_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "coverage.csv").write_text("month,status\n2026-01,REVIEW_ASSERTED_COMPLETE\n2026-01,MISSING_SOURCE\n")
            (root / "actions.csv").write_text("row,symbol,ex_date,status\n")
            with self.assertRaises(ValueError):
                reconcile_action_coverage(root / "actions.csv", root / "coverage.csv", root / "out")
