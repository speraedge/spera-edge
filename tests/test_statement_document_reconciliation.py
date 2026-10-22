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
                writer.writerow(["symbol", "isin", "period_end", "period_type", "basis", "published_on", "source_url"])
                writer.writerow(["ABC", "INE000A01001", "2026-03-31", "FY", "CONSOLIDATED", "2026-04-30",
                                 "https://example.org/filing"])
                writer.writerow(["XYZ", "INE000B01001", "2026-03-31", "FY", "STANDALONE", "2026-04-30",
                                 "https://example.org/other"])
            with docs.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["symbol", "isin", "period_end", "period_type", "basis", "published_on", "source_url", "status"])
                writer.writerow(["ABC", "INE000A01001", "2026-03-31", "FY", "CONSOLIDATED", "2026-04-30",
                                 "https://example.org/filing", "REVIEW_ORIGINAL_DOCUMENT"])
            result = reconcile_statement_documents(financials, docs, root / "out")
            self.assertEqual(result["status_counts"]["MATCHED_DOCUMENT_UNCERTIFIED"], 1)
            self.assertEqual(result["status_counts"]["MISSING_MATCHING_FILING"], 1)
            self.assertFalse(result["certified"])

    def test_incomplete_identity_does_not_match_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            columns = ["symbol", "isin", "period_end", "period_type", "basis",
                       "published_on", "source_url"]
            record = dict(symbol="ABC", isin="INE000A01001", period_end="2026-03-31",
                          period_type="FY", basis="CONSOLIDATED", published_on="",
                          source_url="https://example.org/filing")
            for name, extra in [("financials.csv", []), ("docs.csv", ["status"])]:
                with (root / name).open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=columns + extra)
                    writer.writeheader()
                    writer.writerow({**record, **({"status": "REVIEW_ORIGINAL_DOCUMENT"} if extra else {})})
            result = reconcile_statement_documents(root / "financials.csv",
                                                   root / "docs.csv", root / "out")
            self.assertEqual(result["status_counts"], {"INCOMPLETE_FILING_IDENTITY": 1})
            self.assertFalse(result["certified"])
