"""Owner-bound, append-only financial signoff eligibility audit."""
import sqlite3
import unittest
from edge_core.financial_evidence_ledger import FinancialEvidenceLedger
from edge_core.financial_certification_gate import REQUIRED


class SignoffLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        def query(sql, params=()):
            cursor = self.db.execute(sql, params)
            rows = [dict(x) for x in cursor] if cursor.description else []
            self.db.commit()
            return rows
        self.owner = FinancialEvidenceLedger("owner-one", query)
        self.owner.initialize()
        self.queue = [{"symbol": "ABC", "isin": "INE000A01001",
                       "period_end": "2026-09-30", "period_type": "Q",
                       "basis": "CONSOLIDATED"}]
        self.candidate = {**self.queue[0], "published_on": "2026-10-20",
                          "acquisition_status": "ACQUIRED_UNVERIFIED",
                          "reconciliation": dict(REQUIRED),
                          "source_url": "https://nsearchives.nseindia.com/abc.pdf",
                          "document_sha256": "a" * 64}

    def tearDown(self):
        self.db.close()

    def test_eligible_review_is_logged_but_not_certified(self):
        result = self.owner.append_signoff_review(
            self.queue, self.candidate, reviewer="owner-one",
            source_authenticated=True, figures_independently_checked=True)
        self.assertTrue(result["financial_certification_eligible"])
        self.assertFalse(result["certified"])
        self.assertEqual(len(self.owner.events()), 1)
        self.owner.append_signoff_review(
            self.queue, self.candidate, reviewer="owner-one",
            source_authenticated=True, figures_independently_checked=True)
        self.assertEqual(len(self.owner.events()), 1)

    def test_reject_other_reviewer_or_unqueued_company(self):
        with self.assertRaises(ValueError):
            self.owner.append_signoff_review(
                self.queue, self.candidate, reviewer="another-owner",
                source_authenticated=True, figures_independently_checked=True)
        with self.assertRaises(ValueError):
            self.owner.append_signoff_review(
                self.queue, {**self.candidate, "isin": "WRONG"}, reviewer="owner-one",
                source_authenticated=True, figures_independently_checked=True)
        self.assertEqual(self.owner.events(), [])

    def test_missing_checks_recorded_as_review_required(self):
        result = self.owner.append_signoff_review(
            self.queue, self.candidate, reviewer="owner-one",
            source_authenticated=False, figures_independently_checked=False)
        self.assertFalse(result["financial_certification_eligible"])
        self.assertEqual(result["decision"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
