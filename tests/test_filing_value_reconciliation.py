"""Financial value transcription audit tests."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.filing_value_reconciliation import reconcile_filing_values


class FilingValueTests(unittest.TestCase):
    def test_match_and_mismatch_are_not_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fields = ["symbol", "isin", "period_end", "period_type", "basis",
                      "source_url", "published_on", "revenue", "pat"]
            source = root / "financials.csv"
            transcriptions = root / "transcriptions.csv"
            rows = [
                dict(symbol="ABC", isin="INE000A01001", period_end="2026-03-31",
                     period_type="FY", basis="CONSOLIDATED", source_url="https://example.org/report",
                     published_on="2026-04-30", revenue="100", pat="10"),
                dict(symbol="XYZ", isin="INE000B01001", period_end="2026-03-31",
                     period_type="FY", basis="STANDALONE", source_url="https://example.org/report2",
                     published_on="2026-04-30", revenue="200", pat="20")]
            with source.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with transcriptions.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields + ["document_sha256"])
                writer.writeheader()
                for idx, row in enumerate(rows):
                    entry = dict(row)
                    entry["document_sha256"] = "a" * 64
                    if idx == 1:
                        entry["pat"] = "21"
                    writer.writerow(entry)
            summary = reconcile_filing_values(source, transcriptions, root / "out")
            self.assertEqual(summary["status_counts"]["VALUES_MATCH_UNVERIFIED_TRANSCRIPTION"], 1)
            self.assertEqual(summary["status_counts"]["SOURCE_VALUE_MISMATCH"], 1)
            self.assertFalse(summary["certified"])
