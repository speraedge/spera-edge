"""Offline SQLite test for the complete opt-in D1 smoke verifier."""
import sqlite3
import unittest
from tools.verify_edge_d1 import verify


class D1SmokeVerifierTests(unittest.TestCase):
    def test_reconciliation_and_intake_lifecycle(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row

        def query(sql, params=()):
            cursor = db.execute(sql, params)
            result = [dict(row) for row in cursor] if cursor.description else []
            db.commit()
            return result

        result = verify(query, live=True)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["reconciliation_review_required"])
        self.assertTrue(result["reconciliation_idempotency"])
        self.assertTrue(result["owner_isolation"])
        self.assertFalse(result["certified"])
        db.close()

    def test_requires_explicit_live_flag(self):
        with self.assertRaises(ValueError):
            verify(lambda sql, params=(): [], live=False)


if __name__ == "__main__":
    unittest.main()
