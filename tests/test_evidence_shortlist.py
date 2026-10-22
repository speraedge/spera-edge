import unittest
import pandas as pd
from edge_core.evidence_shortlist import evidence_shortlist
from edge_core.manual_evidence_queue import build_queue


class EvidenceShortlistTests(unittest.TestCase):
    def setUp(self):
        self.scored = pd.DataFrame([
            {"Symbol": "ABC", "Percentile": 95, "Data_Quality": "PASS"},
            {"Symbol": "DEF", "Percentile": 88, "Data_Quality": "REVIEW"},
            {"Symbol": "GHI", "Percentile": 99, "Data_Quality": "FAIL"},
            {"Symbol": "JKL", "Percentile": 65, "Data_Quality": "PASS"}])
        self.members = pd.DataFrame([
            {"Symbol": "ABC", "ISIN Code": "INE000A01001"},
            {"Symbol": "DEF", "ISIN Code": "INE000B01002"},
            {"Symbol": "GHI", "ISIN Code": "INE000C01003"},
            {"Symbol": "JKL", "ISIN Code": "INE000D01004"}])

    def test_frozen_scores_select_candidates_without_certification(self):
        selected = evidence_shortlist(self.scored, self.members)
        self.assertEqual([x["symbol"] for x in selected], ["ABC", "DEF"])
        self.assertTrue(all(x["certified"] is False for x in selected))
        queue = build_queue(selected, [], "2026-09-30")
        self.assertEqual(len(queue), 2)

    def test_unknown_isin_blocks(self):
        with self.assertRaises(ValueError):
            evidence_shortlist(self.scored, self.members.iloc[1:])

    def test_duplicate_membership_blocks(self):
        with self.assertRaises(ValueError):
            evidence_shortlist(self.scored, pd.concat([self.members, self.members.iloc[:1]]))


if __name__ == "__main__":
    unittest.main()
