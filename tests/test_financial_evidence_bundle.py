import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.run_financial_evidence_bundle import run_bundle


def write_csv(path, columns, records):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


class FinancialBundleIntegrationTests(unittest.TestCase):
    def test_full_audit_chain_stays_uncertified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            documents = root / "documents"
            documents.mkdir()
            original = b"%PDF-1.4\nsynthetic document\n%%EOF"
            (documents / "original.pdf").write_bytes(original)
            digest = hashlib.sha256(original).hexdigest()
            url = "https://archives.nseindia.com/fictional.pdf"
            membership = root / "membership.csv"
            financials = root / "financials.csv"
            register = root / "register.csv"
            transcription = root / "transcription.csv"
            write_csv(membership, ["Symbol", "ISIN Code"],
                      [{"Symbol": "ABC", "ISIN Code": "INE000A01001"}])
            common = dict(symbol="ABC", isin="INE000A01001", period_type="Q",
                          basis="CONSOLIDATED", source_url=url)
            rows = [
                dict(common, period_end="2025-09-30", revenue="100", pat="10",
                     published_on="2025-10-20"),
                dict(common, period_end="2026-09-30", revenue="120", pat="12",
                     published_on="2026-10-20"),
            ]
            write_csv(financials, list(rows[0]), rows)
            write_csv(register, ["symbol", "isin", "period_end", "period_type", "basis",
                                 "published_on", "source_url", "document_filename", "expected_sha256"],
                      [dict(symbol="ABC", isin="INE000A01001", period_end=row["period_end"],
                            basis="CONSOLIDATED", period_type="Q",
                            published_on=row["published_on"], source_url=url,
                            document_filename="original.pdf", expected_sha256=digest)
                       for row in rows])
            write_csv(transcription, list(rows[0]) + ["document_sha256"],
                      [dict(row, document_sha256=digest) for row in rows])
            summary = run_bundle(membership, financials, register, documents,
                                 transcription, root / "out")
            self.assertEqual(summary["financial_source"]["rows"], 2)
            self.assertFalse(summary["certified"])
            self.assertFalse(summary["ready_for_trading_signals"])
            self.assertEqual(summary["filing_values"]["status_counts"],
                             {"VALUES_MATCH_UNVERIFIED_TRANSCRIPTION": 2})
            self.assertTrue((root / "out" / "evidence_bundle_summary.json").exists())

    def test_duplicate_membership_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "membership.csv"
            write_csv(path, ["Symbol", "ISIN Code"], [
                {"Symbol": "ABC", "ISIN Code": "INE000A01001"},
                {"Symbol": "DEF", "ISIN Code": "INE000A01001"}])
            from tools.run_financial_evidence_bundle import _membership
            with self.assertRaises(ValueError):
                _membership(path)


if __name__ == "__main__":
    unittest.main()
