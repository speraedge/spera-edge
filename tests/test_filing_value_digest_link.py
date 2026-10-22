"""Ensure financial transcriptions cannot borrow arbitrary document hashes."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.filing_value_reconciliation import reconcile_filing_values


class DocumentDigestLinkTests(unittest.TestCase):
    def test_wrong_digest_blocks_matching_financial_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fields = ["symbol", "isin", "period_end", "period_type", "basis",
                      "source_url", "published_on", "revenue", "pat"]
            record = dict(symbol="ABC", isin="INE000A01001", period_end="2026-03-31",
                          period_type="FY", basis="CONSOLIDATED", source_url="https://example.org/filing",
                          published_on="2026-04-30", revenue="100", pat="10")
            for name, extra in [("financials.csv", []), ("transcriptions.csv", ["document_sha256"])]:
                with (root / name).open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields + extra)
                    writer.writeheader()
                    row = dict(record)
                    if extra:
                        row["document_sha256"] = "a" * 64
                    writer.writerow(row)
            with (root / "docs.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["symbol", "isin", "period_end",
                    "basis", "source_url", "computed_sha256", "status"])
                writer.writeheader()
                writer.writerow(dict(symbol="ABC", isin="INE000A01001", period_end="2026-03-31",
                    basis="CONSOLIDATED", source_url="https://example.org/filing",
                    computed_sha256="b" * 64, status="REVIEW_ORIGINAL_DOCUMENT"))
            result = reconcile_filing_values(root / "financials.csv", root / "transcriptions.csv",
                                             root / "out", root / "docs.csv")
            self.assertEqual(result["status_counts"]["DOCUMENT_PROVENANCE_MISMATCH"], 1)
            self.assertFalse(result["certified"])
