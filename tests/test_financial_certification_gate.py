"""Financial certification eligibility cannot be self-certified."""
import unittest
from edge_core.financial_certification_gate import assess_financial_certification, REQUIRED


class CertificationGateTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "symbol": "ABC", "isin": "INE000A01001",
            "period_end": "2026-09-30", "published_on": "2026-10-20",
            "acquisition_status": "ACQUIRED_UNVERIFIED",
            "reconciliation": dict(REQUIRED),
        }

    def test_reconciled_without_independent_review_remains_blocked(self):
        result = assess_financial_certification(self.candidate)
        self.assertFalse(result["financial_certification_eligible"])
        self.assertFalse(result["certified"])
        self.assertIn("independent_source_authentication", result["missing_gates"])

    def test_all_review_conditions_enable_signoff_not_automatic_certification(self):
        result = assess_financial_certification(
            self.candidate, reviewer="authorized-reviewer",
            source_authenticated=True, figures_independently_checked=True)
        self.assertEqual(result["decision"], "READY_FOR_AUTHORIZED_SIGNOFF")
        self.assertTrue(result["financial_certification_eligible"])
        self.assertFalse(result["certified"])
        self.assertFalse(result["ready_for_trading_signals"])

    def test_missing_layer_and_future_date_block(self):
        candidate = {**self.candidate, "published_on": "2099-01-01",
                     "reconciliation": {**REQUIRED, "value_status": "SOURCE_VALUE_MISMATCH"}}
        result = assess_financial_certification(
            candidate, reviewer="reviewer", source_authenticated=True,
            figures_independently_checked=True)
        self.assertIn("value_status", result["missing_gates"])
        self.assertIn("publication_chronology", result["missing_gates"])


if __name__ == "__main__":
    unittest.main()
