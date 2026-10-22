import unittest
from edge_core.manual_evidence_queue import build_queue


class ManualEvidenceQueueTests(unittest.TestCase):
    def setUp(self):
        self.shortlist = [{"symbol": "ABC", "isin": "INE000A01001"}]
        self.base = dict(symbol="ABC", isin="INE000A01001",
                         period_end="2026-09-30", period_type="Q",
                         basis="CONSOLIDATED", revenue="100", pat="10",
                         published_on="2026-10-20", source_url="https://example.org/report.pdf")

    def test_missing_period_requests_only_missing_fields(self):
        result = build_queue(self.shortlist, [], "2026-09-30")
        self.assertEqual(result[0]["reason"], "MISSING_PERIOD")
        self.assertIn("revenue", result[0]["missing_fields"])

    def test_partial_record_requests_only_missing_value(self):
        record = dict(self.base, pat="")
        result = build_queue(self.shortlist, [record], "2026-09-30")
        self.assertEqual(result[0]["missing_fields"], "pat")

    def test_complete_record_still_needs_verification(self):
        result = build_queue(self.shortlist, [self.base], "2026-09-30")
        self.assertEqual(result[0]["reason"], "SOURCE_VERIFICATION_REQUIRED")
        self.assertEqual(result[0]["status"], "MANUAL_REVIEW_REQUIRED")

    def test_duplicate_period_blocks(self):
        result = build_queue(self.shortlist, [self.base, self.base], "2026-09-30")
        self.assertEqual(result[0]["reason"], "DUPLICATE_OR_CONFLICTING_PERIOD")

    def test_prior_period_does_not_satisfy_current(self):
        record = dict(self.base, period_end="2026-06-30")
        result = build_queue(self.shortlist, [record], "2026-09-30")
        self.assertEqual(result[0]["reason"], "MISSING_PERIOD")

    def test_duplicate_shortlist_identity_deduplicates(self):
        result = build_queue(self.shortlist * 2, [], "2026-09-30")
        self.assertEqual(len(result), 1)

    def test_null_and_nonfinite_values_are_missing(self):
        for value in (None, float("nan"), float("inf"), "-inf", "null", False):
            with self.subTest(value=str(value)):
                result = build_queue(self.shortlist, [dict(self.base, pat=value)], "2026-09-30")
                self.assertEqual(result[0]["reason"], "MISSING_FIELDS")
                self.assertEqual(result[0]["missing_fields"], "pat")

    def test_bad_basis_rejected(self):
        with self.assertRaises(ValueError):
            build_queue(self.shortlist, [], "2026-09-30", basis="UNKNOWN")


if __name__ == "__main__":
    unittest.main()
