"""End-to-end financial audit integration test."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class FinancialAuditIntegrationTests(unittest.TestCase):
    def test_financial_growth_remains_uncertified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            membership = root / "membership.csv"
            financials = root / "financials.csv"
            with membership.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Symbol", "ISIN Code"])
                writer.writerow(["ABC", "INE000A01001"])
            with financials.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["symbol", "isin", "period_end", "period_type", "basis",
                                 "revenue", "pat", "source_url", "published_on"])
                for period, sales in [("2025-03-31", "100"), ("2026-03-31", "120")]:
                    writer.writerow(["ABC", "INE000A01001", period, "FY", "CONSOLIDATED",
                                     sales, "10", "https://example.org/filing", period])
            subprocess.run([sys.executable, "-m", "tools.audit_milestone2_evidence",
                            "--membership", str(membership), "--financials", str(financials),
                            "--output", str(root / "out")], check=True, capture_output=True)
            result = json.loads((root / "out" / "evidence_manifest.json").read_text())
            self.assertIn("financial_growth_reconciliation", result)
            self.assertFalse(result["financial_growth_reconciliation"]["certified"])
            self.assertFalse(result["financial_growth_ready"])
            with (root / "out" / "growth_reconciliation" / "financial_growth_reconciliation.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[1]["status"], "CANDIDATE_UNCERTIFIED")
            self.assertEqual(rows[1]["revenue_growth_candidate_pct"], "20.0")
