"""Regression tests for statement-document provenance matching."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.statement_document_reconciliation import reconcile_statement_documents


class StatementDocumentTests(unittest.TestCase):
    def test_missing_and_matching_filing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            financials = root / "financials.csv"
            docs = root / "docs.csv"
            with financials.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["symbol", "isin", "period_end", "basis", "source_url"])
                writer.writerow(["ABC", "INE000A01001", "2026-03-31", "CONSOLIDATED",
                                 "https://example.org/filing"])
                writer.writerow(["XYZ", "INE000B01001", "2026-03-31", "STANDALONE",
                                 "https://example.org/other"])
            with docs.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["symbol", "isin", "period_end", "basis", "source_url", "status"])
                writer.writerow(["ABC", "INE000A01001", "2026-03-31", "CONSOLIDATED",
                                 "https://example.org/filing", "REVIEW_ORIGINAL_DOCUMENT"])
            result = reconcile_statement_documents(financials, docs, root / "out")
            self.assertEqual(result["status_counts"]["MATCHED_DOCUMENT_UNCERTIFIED"], 1)
            self.assertEqual(result["status_counts"]["MISSING_MATCHING_FILING"], 1)
            self.assertFalse(result["certified"])
