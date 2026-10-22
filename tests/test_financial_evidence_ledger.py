import sqlite3
import unittest

from edge_core.financial_evidence_ledger import FinancialEvidenceLedger


class FinancialEvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row

        def query(sql, params=()):
            cursor = self.db.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()] if cursor.description else []

        self.ledger = FinancialEvidenceLedger("owner-a", query)
        self.ledger.initialize()
        self.queue = [{"symbol": "ABC", "isin": "INE000A01001", "period_end": "2026-09-30",
                       "period_type": "Q", "basis": "CONSOLIDATED"}]
        self.submission = dict(self.queue[0], revenue="123.4", pat="12.3",
                               published_on="2026-10-20", source_url="https://example.com/filing.pdf")

    def test_quarantine_and_idempotency(self):
        self.ledger.append_intake(self.queue, self.submission, event_id="event-1")
        self.ledger.append_intake(self.queue, self.submission, event_id="event-1")
        self.assertEqual(len(self.ledger.events()), 1)
        self.assertEqual(self.ledger.events()[0]["intake_status"], "QUARANTINED_UNVERIFIED")
        with self.assertRaises(ValueError):
            self.ledger.append_intake(self.queue, dict(self.submission, revenue="999"), event_id="event-1")

    def test_owner_isolation_and_append_only(self):
        self.ledger.append_intake(self.queue, self.submission, event_id="event-1")
        other = FinancialEvidenceLedger("owner-b", self.ledger.query)
        self.assertEqual(other.events(), [])
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM edge_financial_evidence_events")

    def test_invalid_input_is_not_saved(self):
        with self.assertRaises(ValueError):
            self.ledger.append_intake(self.queue, dict(self.submission, source_url="http://example.com"))
        self.assertEqual(self.ledger.events(), [])


if __name__ == "__main__":
    unittest.main()
