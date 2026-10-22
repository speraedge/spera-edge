import sqlite3
import unittest

from tools.verify_edge_d1 import verify


class LiveD1ProbeTests(unittest.TestCase):
    def test_explicit_live_required(self):
        with self.assertRaisesRegex(ValueError, "explicit"):
            verify(lambda *args: [], live=False)

    def test_synthetic_record_isolated_and_idempotent(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row

        def query(sql, params=()):
            cursor = db.execute(sql, params)
            return [dict(x) for x in cursor.fetchall()] if cursor.description else []

        result = verify(query, live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["certified"])
        self.assertEqual(db.execute(
            "SELECT COUNT(*) FROM edge_financial_evidence_events"
        ).fetchone()[0], 2)
        self.assertEqual(dict(db.execute(
            "SELECT event_kind, COUNT(*) FROM edge_financial_evidence_events GROUP BY event_kind"
        ).fetchall()), {"INTAKE": 1, "SOURCE_RECONCILIATION": 1})


if __name__ == "__main__":
    unittest.main()
