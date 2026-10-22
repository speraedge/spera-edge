"""SQLite-backed owner isolation and replay tests for reconciliation evidence."""
import json
import sqlite3
import unittest

from edge_core.financial_evidence_ledger import FinancialEvidenceLedger

Q = [{"symbol":"ABC","isin":"INE000A01001","period_end":"2026-09-30",
      "period_type":"Q","basis":"CONSOLIDATED"}]
O = {**Q[0],"acquisition_status":"HTTP_403"}


class LedgerReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        def query(sql, params=()):
            rows = self.db.execute(sql, params)
            result = [dict(x) for x in rows] if rows.description else []
            self.db.commit()
            return result
        self.a = FinancialEvidenceLedger("owner-a", query)
        self.b = FinancialEvidenceLedger("owner-b", query)
        self.a.initialize()

    def tearDown(self):
        self.db.close()

    def test_owner_scoped_append_and_idempotent_replay(self):
        event = self.a.append_reconciliation(Q, O, event_id="fixed")
        self.assertEqual(event, self.a.append_reconciliation(Q, O, event_id="fixed"))
        self.assertEqual(len(self.a.events()), 1)
        self.assertEqual(self.b.events(), [])
        payload = json.loads(self.a.events()[0]["payload_json"])
        self.assertFalse(payload["certified"])

    def test_collision_other_owner_blocked(self):
        self.a.append_reconciliation(Q, O, event_id="fixed")
        with self.assertRaises(ValueError):
            self.b.append_reconciliation(Q, O, event_id="fixed")

    def test_changed_replay_blocked(self):
        self.a.append_reconciliation(Q, O, event_id="fixed")
        with self.assertRaises(ValueError):
            self.a.append_reconciliation(Q, {**O,"acquisition_status":"HTTP_429"}, event_id="fixed")

    def test_unknown_identity_and_status_blocked(self):
        with self.assertRaises(ValueError):
            self.a.append_reconciliation(Q, {**O,"isin":"INE999A01001"})
        with self.assertRaises(ValueError):
            self.a.append_reconciliation(Q, {**O,"acquisition_status":"CERTIFIED"})

    def test_append_only(self):
        self.a.append_reconciliation(Q, O)
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.execute("DELETE FROM edge_financial_evidence_events")


if __name__ == "__main__":
    unittest.main()
