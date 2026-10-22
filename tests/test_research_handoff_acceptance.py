"""Gate A: synthetic end-to-end research handoff; never market certification."""
import csv
import io
import unittest
from datetime import date

import pandas as pd
from openpyxl import load_workbook

from edge_core.evidence_shortlist import evidence_shortlist
from edge_core.manual_evidence_queue import build_queue
from edge_core.trading_readiness import trading_readiness
from edge_exports import export_bytes


class ResearchHandoffAcceptance(unittest.TestCase):
    def setUp(self):
        self.period = "2026-09-30"
        self.scored = pd.DataFrame([
            {"Symbol": "AAA", "Percentile": 96.0, "Data_Quality": "PASS", "Pure_Momentum_Rank": 1},
            {"Symbol": "BBB", "Percentile": 88.0, "Data_Quality": "REVIEW", "Pure_Momentum_Rank": 2},
            {"Symbol": "CCC", "Percentile": 45.0, "Data_Quality": "FAIL", "Pure_Momentum_Rank": 3},
        ])
        self.membership = pd.DataFrame([
            {"Symbol": "AAA", "ISIN Code": "INE000A01001"},
            {"Symbol": "BBB", "ISIN Code": "INE000B01002"},
            {"Symbol": "CCC", "ISIN Code": "INE000C01003"},
        ])

    def test_shortlist_queue_readiness_and_all_export_formats(self):
        shortlist = evidence_shortlist(self.scored, self.membership)
        self.assertEqual([r["symbol"] for r in shortlist], ["AAA", "BBB"])
        self.assertEqual(self.scored["Pure_Momentum_Rank"].tolist(), [1, 2, 3])
        queue = build_queue(shortlist, [], self.period)
        self.assertEqual([r["reason"] for r in queue], ["MISSING_PERIOD", "MISSING_PERIOD"])
        technical = pd.DataFrame([
            {"Symbol": "AAA", "Price_Template_Pass": True,
             "RS_80th_Percentile_Diagnostic": True},
            {"Symbol": "BBB", "Price_Template_Pass": False,
             "RS_80th_Percentile_Diagnostic": False},
        ])
        result = trading_readiness(
            self.scored, self.membership, [], self.period,
            technical_evidence=technical, snapshot_fresh=True,
        )
        self.assertEqual(result["candidate_count"], 2)
        self.assertFalse(result["certified"])
        self.assertFalse(result["ready_for_trading_signals"])
        self.assertTrue(all(r["decision"] == "REVIEW_REQUIRED"
                            and not r["eligible_for_trading"] for r in result["candidates"]))
        frame = pd.DataFrame(queue)
        csv_data = export_bytes(frame, "CSV", "Evidence queue").decode("utf-8-sig")
        csv_rows = list(csv.DictReader(io.StringIO(csv_data)))
        self.assertEqual([r["No."] for r in csv_rows], ["1", "2"])
        self.assertEqual(csv_rows[1]["symbol"], "BBB")
        excel = load_workbook(io.BytesIO(export_bytes(frame, "Excel", "Evidence queue")))
        self.assertEqual(excel.active.max_row, 3)
        self.assertEqual(excel.active.max_column, len(frame.columns) + 1)
        self.assertTrue(export_bytes(frame, "PDF", "Evidence queue").startswith(b"%PDF"))

    def test_stale_and_missing_evidence_fail_closed(self):
        result = trading_readiness(self.scored, self.membership, [], self.period,
                                   snapshot_fresh=False)
        self.assertTrue(all(r["gates"]["market_breadth"] == "NOT_VERIFIED"
                            for r in result["candidates"]))
        self.assertTrue(all(r["gates"]["financial_evidence"] == "REVIEW_REQUIRED"
                            and r["gates"]["corporate_actions"] == "NOT_VERIFIED"
                            for r in result["candidates"]))
        self.assertFalse(result["ready_for_trading_signals"])

    def test_wrong_membership_identity_rejected(self):
        membership = self.membership.loc[self.membership["Symbol"] != "AAA"]
        with self.assertRaises(ValueError):
            trading_readiness(self.scored, membership, [], self.period)

    def test_duplicate_financial_record_never_certifies(self):
        record = {"isin": "INE000A01001", "period_end": self.period,
                  "period_type": "Q", "basis": "CONSOLIDATED",
                  "revenue": 100, "pat": 10, "published_on": "2026-10-20",
                  "source_url": "https://example.org/unverified.pdf"}
        result = trading_readiness(self.scored, self.membership,
                                   [record, dict(record)], self.period)
        self.assertEqual(result["candidates"][0]["evidence_reason"],
                         "DUPLICATE_OR_CONFLICTING_PERIOD")
        self.assertFalse(result["ready_for_trading_signals"])


if __name__ == "__main__":
    unittest.main()
