import sqlite3
import unittest
from pathlib import Path


class FinancialEvidenceSchemaTests(unittest.TestCase):
    def test_append_only_and_owner_index(self):
        db = sqlite3.connect(":memory:")
        schema = (Path(__file__).resolve().parents[1] / "migrations" /
                  "edge_financial_evidence_events.sql").read_text()
        db.executescript(schema)
        values = ("evt1", "owner", "ABC", "INE000A01001", "2026-09-30",
                  "Q", "CONSOLIDATED", "2026-10-22T10:00:00Z", "INTAKE",
                  "QUARANTINED_UNVERIFIED", None, "{}", None)
        db.execute("INSERT INTO edge_financial_evidence_events VALUES (" +
                   ",".join("?" for _ in values) + ")", values)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("UPDATE edge_financial_evidence_events SET symbol='DEF' WHERE event_id='evt1'")
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("DELETE FROM edge_financial_evidence_events WHERE event_id='evt1'")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM edge_financial_evidence_events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
