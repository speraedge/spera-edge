import unittest
from edge_core.manual_evidence_intake import review_intake


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.record = dict(symbol="ABC", isin="INE000A01001", period_end="2026-09-30",
                           period_type="Q", basis="CONSOLIDATED", revenue="100",
                           pat="10", published_on="2026-10-20",
                           source_url="https://example.org/official.pdf")
        self.queue = [dict(self.record, status="MANUAL_REVIEW_REQUIRED")]

    def test_valid_submission_is_quarantined_not_certified(self):
        result = review_intake(self.queue, [self.record])[0]
        self.assertEqual(result["intake_status"], "QUARANTINED_UNVERIFIED")
        self.assertEqual(result["certified"], "false")

    def test_unrequested_stock_rejected(self):
        result = review_intake(self.queue, [dict(self.record, isin="OTHER")])[0]
        self.assertIn("NOT_IN_REVIEW_QUEUE", result["intake_reason"])

    def test_invalid_revenue_rejected(self):
        result = review_intake(self.queue, [dict(self.record, revenue="-1")])[0]
        self.assertIn("INVALID_REVENUE", result["intake_reason"])

    def test_future_publication_relative_to_period_rejected(self):
        result = review_intake(self.queue, [dict(self.record, published_on="2026-09-01")])[0]
        self.assertIn("PUBLICATION_BEFORE_PERIOD_END", result["intake_reason"])

    def test_non_https_source_rejected(self):
        result = review_intake(self.queue, [dict(self.record, source_url="http://example.org")])[0]
        self.assertIn("INVALID_SOURCE_URL", result["intake_reason"])

    def test_duplicate_submissions_rejected(self):
        result = review_intake(self.queue, [self.record, self.record])
        self.assertIn("DUPLICATE_SUBMISSION", result[1]["intake_reason"])


if __name__ == "__main__":
    unittest.main()
