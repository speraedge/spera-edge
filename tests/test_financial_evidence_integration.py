"""End-to-end offline EDGE evidence flow using D1-compatible SQLite SQL."""
import sqlite3
import unittest

import pandas as pd
from edge_core.evidence_shortlist import evidence_shortlist
from edge_core.manual_evidence_queue import build_queue
from edge_core.financial_evidence_ledger import FinancialEvidenceLedger


class FinancialEvidenceIntegrationTests(unittest.TestCase):
    def test_shortlist_queue_quarantine_and_owner_isolation(self):
        scored = pd.DataFrame([
            {"Symbol": "ABC", "Percentile": 94, "Data_Quality": "PASS"},
            {"Symbol": "DEF", "Percentile": 70, "Data_Quality": "PASS"},
        ])
        membership = pd.DataFrame([
            {"Symbol": "ABC", "ISIN Code": "INE000A01001"},
            {"Symbol": "DEF", "ISIN Code": "INE000B01001"},
        ])
        candidates = evidence_shortlist(scored, membership)
        self.assertEqual([c["symbol"] for c in candidates], ["ABC"])
        queue = build_queue(candidates, [], "2026-09-30")
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["reason"], "MISSING_PERIOD")
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row

        def query(sql, params=()):
            cursor = connection.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()] if cursor.description else []

        owner = FinancialEvidenceLedger("owner-one", query)
        owner.initialize()
        submission = {
            k: queue[0][k] for k in ("symbol", "isin", "period_end", "period_type", "basis")
        }
        submission.update(revenue="123", pat="12", published_on="2026-10-20",
                          source_url="https://example.com/filing.pdf")
        owner.append_intake(queue, submission, event_id="integration-1")
        self.assertEqual(owner.events()[0]["intake_status"], "QUARANTINED_UNVERIFIED")
        self.assertEqual(FinancialEvidenceLedger("owner-two", query).events(), [])
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("UPDATE edge_financial_evidence_events SET symbol='XYZ'")

    def test_missing_official_identity_fails_before_intake(self):
        scored = pd.DataFrame([{"Symbol": "ABC", "Percentile": 90, "Data_Quality": "PASS"}])
        membership = pd.DataFrame([{"Symbol": "ABC", "ISIN Code": ""}])
        with self.assertRaises(ValueError):
            evidence_shortlist(scored, membership)


if __name__ == "__main__":
    unittest.main()
