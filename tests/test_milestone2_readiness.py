"""Milestone 2 readiness must never imply data certification."""
import tempfile
import unittest
from pathlib import Path
from edge_core.milestone2_readiness import assess_readiness, REQUIRED


class ReadinessTests(unittest.TestCase):
    def test_missing_sources_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess_readiness({"financials": {"status_counts": {}}}, Path(tmp))
            self.assertIn("corporate_actions", result["missing_sections"])
            self.assertFalse(result["technical_audit_complete"])
            self.assertFalse(result["ready_for_trading_signals"])

    def test_all_sections_still_not_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = {key: {"status_counts": {}} for key in REQUIRED}
            result = assess_readiness(results, Path(tmp))
            self.assertTrue(result["technical_audit_complete"])
            self.assertFalse(result["certified"])
            self.assertEqual(result["decision"], "BLOCKED_PENDING_INDEPENDENT_EVIDENCE")
