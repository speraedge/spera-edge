"""Integrated trader handoff acceptance; synthetic fixtures are not market evidence."""
import unittest
import pandas as pd
from edge_core.trading_readiness import trading_readiness

class TradingReadinessTests(unittest.TestCase):
    def setUp(self):
        self.scored = pd.DataFrame([
            {"Symbol": "AAA", "Percentile": 95, "Data_Quality": "PASS"},
            {"Symbol": "BBB", "Percentile": 90, "Data_Quality": "REVIEW"},
            {"Symbol": "CCC", "Percentile": 60, "Data_Quality": "PASS"},
        ])
        self.membership = pd.DataFrame([
            {"Symbol": "AAA", "ISIN Code": "INE000A01001"},
            {"Symbol": "BBB", "ISIN Code": "INE000B01002"},
            {"Symbol": "CCC", "ISIN Code": "INE000C01003"},
        ])
        self.records = []

    def run_case(self, acquisition=None):
        return trading_readiness(self.scored, self.membership, self.records,
                                 "2026-09-30", acquisition=acquisition)

    def test_shortlist_filters_but_never_issues_trade(self):
        result = self.run_case()
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual([x["symbol"] for x in result["candidates"]], ["AAA", "BBB"])
        self.assertTrue(all(x["decision"] == "REVIEW_REQUIRED" for x in result["candidates"]))
        self.assertTrue(all(not x["eligible_for_trading"] for x in result["candidates"]))
        self.assertFalse(result["ready_for_trading_signals"])

    def test_official_pdf_acquisition_does_not_promote_trading(self):
        queue = [
            {"symbol": symbol, "isin": isin, "period_end": "2026-09-30",
             "period_type": "Q", "basis": "CONSOLIDATED"}
            for symbol, isin in [("AAA", "INE000A01001"), ("BBB", "INE000B01002")]
        ]
        acquisition = {"certified": False, "ready_for_trading_signals": False,
                       "review": [
                           {**queue[0], "certified": False,
                            "acquisition_status": "ACQUIRED_UNVERIFIED",
                            "source_url": "https://nsearchives.nseindia.com/aaa.pdf",
                            "document_sha256": "a" * 64,
                            "published_on": "2026-10-20"},
                           {**queue[1], "certified": False,
                            "acquisition_status": "HTTP_403"},
                       ]}
        result = self.run_case(acquisition)
        self.assertEqual(result["candidates"][0]["acquisition_status"], "ACQUIRED_UNVERIFIED")
        self.assertEqual(result["candidates"][1]["acquisition_status"], "HTTP_403")
        self.assertTrue(all(not row["certified"] for row in result["candidates"]))

    def test_wrong_identity_and_certification_claim_fail_closed(self):
        for record in (
            {"symbol": "OTHER", "isin": "INE000Z01001"},
            {"symbol": "AAA", "isin": "INE000A01001", "certified": True},
        ):
            payload = {"certified": False, "review": [
                {"period_end": "2026-09-30", "period_type": "Q",
                 "basis": "CONSOLIDATED", "acquisition_status": "HTTP_403",
                 "certified": False, **record}]}
            with self.assertRaises(ValueError):
                self.run_case(payload)

    def test_price_template_and_rs_research_never_certify_trade(self):
        evidence = pd.DataFrame([
            {"Symbol": "AAA", "Price_Template_Pass": True,
             "RS_80th_Percentile_Diagnostic": True},
            {"Symbol": "BBB", "Price_Template_Pass": False,
             "RS_80th_Percentile_Diagnostic": False},
        ])
        result = trading_readiness(self.scored, self.membership, [],
                                   "2026-09-30", technical_evidence=evidence,
                                   snapshot_fresh=True)
        a, b = result["candidates"]
        self.assertEqual(a["gates"]["sepa_trend_template"], "PASS_RESEARCH_ONLY")
        self.assertEqual(a["gates"]["relative_strength"], "PASS_RESEARCH_ONLY")
        self.assertEqual(a["gates"]["market_breadth"], "RESEARCH_AVAILABLE_UNCERTIFIED")
        self.assertEqual(b["gates"]["sepa_trend_template"], "NOT_VERIFIED")
        self.assertFalse(a["eligible_for_trading"])
        self.assertFalse(result["ready_for_trading_signals"])

    def test_duplicate_technical_evidence_rejected(self):
        evidence = pd.DataFrame([
            {"Symbol": "AAA", "Price_Template_Pass": True,
             "RS_80th_Percentile_Diagnostic": True}] * 2)
        with self.assertRaises(ValueError):
            trading_readiness(self.scored, self.membership, [],
                              "2026-09-30", technical_evidence=evidence)

    def test_setup_scanner_diagnostic_remains_research_only(self):
        setups = pd.DataFrame([
            {"Ticker": "AAA", "VCP_Setup": "VCP", "VCP_Score": 11},
        ])
        result = trading_readiness(self.scored, self.membership, [],
                                   "2026-09-30", setup_evidence=setups)
        self.assertEqual(result["candidates"][0]["gates"]["vcp_pivot_volume"],
                         "SETUP_RESEARCH_ONLY")
        self.assertEqual(result["candidates"][0]["setup_score"], 11.0)
        self.assertEqual(result["candidates"][1]["gates"]["vcp_pivot_volume"],
                         "NOT_VERIFIED")
        self.assertFalse(result["candidates"][0]["eligible_for_trading"])

    def test_duplicate_setup_tickers_rejected(self):
        setups = pd.DataFrame([{"Ticker": "AAA", "VCP_Setup": "VCP",
                                "VCP_Score": 10}] * 2)
        with self.assertRaises(ValueError):
            trading_readiness(self.scored, self.membership, [],
                              "2026-09-30", setup_evidence=setups)

    def test_risk_plan_rejects_stale_or_ambiguous_batch(self):
        inputs = {"capital": 500000, "risk_pct": 1, "entry": 100,
                  "stop": 95, "committed_risk": 20000}
        for fresh in (False, True):
            with self.assertRaises(ValueError):
                trading_readiness(self.scored, self.membership, [],
                                  "2026-09-30", risk_inputs=inputs,
                                  snapshot_fresh=fresh)

    def test_risk_plan_single_candidate_capped_by_portfolio(self):
        one = self.scored.iloc[[0]]
        inputs = {"capital": 500000, "risk_pct": 1, "entry": 100,
                  "stop": 95, "committed_risk": 24500}
        result = trading_readiness(one, self.membership, [], "2026-09-30",
                                   risk_inputs=inputs, snapshot_fresh=True)
        plan = result["candidates"][0]["risk_plan"]
        self.assertEqual(plan["quantity"], 100)
        self.assertEqual(plan["planned_risk"], 500)
        self.assertFalse(result["candidates"][0]["eligible_for_trading"])

    def test_duplicate_membership_rejected(self):
        membership = pd.concat([self.membership, self.membership.iloc[[0]]],
                               ignore_index=True)
        with self.assertRaises(ValueError):
            trading_readiness(self.scored, membership, [], "2026-09-30")

if __name__ == "__main__":
    unittest.main()
