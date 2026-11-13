"""Offline regression checks for published EDGE market evidence.

No network, API credentials, or private portfolio access required.
"""
import csv
import hashlib
import json
from pathlib import Path
import unittest
from datetime import date
from edge_core.momentum_universe import NIFTY_500, NIFTY_TOTAL_MARKET

ROOT = Path(__file__).resolve().parents[1] / "data" / "latest"


class PublishedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = json.loads((ROOT / "metadata.json").read_text())
        cls.evidence = json.loads((ROOT / "evidence.json").read_text())
        cls.active_spec = NIFTY_TOTAL_MARKET if cls.meta.get("universe") == "NIFTY_TOTAL_MARKET" else NIFTY_500

    def test_official_membership_matches_published_digest(self):
        path = ROOT / "current_membership.csv"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         self.evidence["membership_sha256"])
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), int(self.evidence["membership_rows"]))
        self.assertEqual(len(rows), int(self.meta["expected"]))
        symbols = [row["Symbol"].strip() for row in rows]
        self.assertEqual(len(symbols), len(set(symbols)))
        self.assertTrue(all(symbols))
        self.assertTrue(all(row["Industry"].strip() for row in rows))
        self.assertLessEqual(int(self.meta["mapped"]), len(rows))
        self.assertIn(self.evidence["membership_source"], self.active_spec.urls)

    def test_placeholder_is_explicitly_classified_when_metadata_available(self):
        placeholders = self.meta.get("official_placeholders")
        if placeholders is None:
            self.skipTest("Published snapshot predates placeholder classification")
        self.assertTrue(all(str(p.get("ISIN", "")).startswith("DUM") for p in placeholders))
        unresolved = self.meta.get("unresolved_identities", [])
        self.assertFalse(any(row.get("Symbol") == "DUMMYHEG" for row in unresolved))
        self.assertEqual(int(self.meta["expected"]) - int(self.meta["mapped"]),
                         len(placeholders) + len(unresolved))

    def test_benchmark_identity_digest_and_completed_sessions(self):
        if self.evidence["benchmark_status"] == "UNAVAILABLE":
            self.assertFalse(self.meta["certified"])
            self.skipTest("Benchmark unavailable: evidence must remain uncertified")
        self.assertEqual(self.evidence["benchmark_status"], "PROVIDER_HISTORY")
        self.assertEqual(self.evidence["benchmark_name"], self.active_spec.display_name)
        self.assertTrue(self.evidence["benchmark_instrument"].startswith("NSE_INDEX|"))
        path = ROOT / "benchmark.csv"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         self.evidence["benchmark_sha256"])
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreaterEqual(len(rows), 253)
        dates = [date.fromisoformat(row["Date"][:10]) for row in rows]
        self.assertEqual(dates, sorted(set(dates)))
        self.assertLessEqual(dates[-1], date.fromisoformat(self.meta["last_session"]))
        self.assertTrue(all(float(row["close"]) > 0 for row in rows))

    def test_unverified_research_cannot_be_promoted(self):
        quality = str(self.meta.get("quality", ""))
        if "UNVERIFIED" in quality or quality.startswith("REVIEW"):
            self.assertIs(self.meta["certified"], False)
        self.assertGreaterEqual(int(self.meta["research_pass"]), 0)
        self.assertGreaterEqual(int(self.meta["research_review"]), 0)
        self.assertGreaterEqual(int(self.meta["research_fail"]), 0)


if __name__ == "__main__":
    unittest.main()
