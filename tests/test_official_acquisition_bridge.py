"""Offline integration tests for the official acquisition register bridge."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.official_acquisition_bridge import prepare_official_acquisition

CANDIDATE = {"symbol": "ABC", "isin": "INE000A01001"}
FILING = {**CANDIDATE, "period_end": "2026-09-30", "period_type": "Q",
          "basis": "CONSOLIDATED", "published_on": "2026-10-20",
          "source_url": "https://nsearchives.nseindia.com/abc.pdf"}


class OfficialAcquisitionBridgeTests(unittest.TestCase):
    def run_bridge(self, filings):
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare_official_acquisition([CANDIDATE], filings, [], "2026-09-30", tmp)
            with (Path(tmp) / "official_acquisition_register.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            return result, rows

    def test_exact_official_source_stays_uncertified(self):
        result, rows = self.run_bridge([FILING])
        self.assertEqual(result["registered"], 1)
        self.assertFalse(result["certified"])
        self.assertEqual(rows[0]["published_on"], "2026-10-20")
        self.assertEqual(result["review"][0]["acquisition_status"],
                         "ACQUISITION_PENDING_UNVERIFIED")

    def test_missing_source_is_review(self):
        result, rows = self.run_bridge([])
        self.assertEqual(rows, [])
        self.assertEqual(result["review"][0]["acquisition_status"], "SOURCE_NOT_FOUND")

    def test_duplicate_exact_sources_blocked(self):
        result, rows = self.run_bridge([FILING, FILING])
        self.assertEqual(rows, [])
        self.assertEqual(result["review"][0]["acquisition_status"], "AMBIGUOUS_SOURCE")

    def test_wrong_isin_never_matches(self):
        result, rows = self.run_bridge([{**FILING, "isin": "INE999A01001"}])
        self.assertEqual(rows, [])

    def test_invalid_host_and_date_blocked(self):
        for bad in ({**FILING, "source_url": "https://example.com/x.pdf"},
                    {**FILING, "published_on": "2026-09-01"},
                    {**FILING, "published_on": "2099-01-01"}):
            result, rows = self.run_bridge([bad])
            self.assertEqual(rows, [])
            self.assertNotEqual(result["review"][0]["acquisition_status"],
                                "ACQUISITION_PENDING_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
