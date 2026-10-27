"""Provisional isolation and hard execution lock contracts."""
import unittest
from pathlib import Path
from unittest.mock import Mock
import pandas as pd
from tools.publish_edge_provisional import publish_provisional

ROOT = Path(__file__).resolve().parents[1]

class ProvisionalSafetyTests(unittest.TestCase):
    def test_verified_path_refused_before_fetch(self):
        with self.assertRaisesRegex(ValueError, "isolated"):
            publish_provisional(outdir="data/latest", token="fake", now="2026-10-27T19:00:00+05:30")

    def test_no_completed_session_refused(self):
        with self.assertRaises(ValueError):
            publish_provisional(outdir="data/provisional", token="fake", now="2026-10-27T14:00:00+05:30")

    def test_publisher_has_no_d1_or_verified_write(self):
        source = (ROOT / "tools/publish_edge_provisional.py").read_text()
        self.assertNotIn("d1_query(", source)
        self.assertIn('outdir="data/provisional"', source)
        self.assertIn("reconcile_provisional_daily", source)

    def test_execution_boundaries_fail_closed(self):
        workspace = (ROOT / "edge_workspace.py").read_text()
        app = (ROOT / "app.py").read_text()
        self.assertIn("if data_source == 'provisional':", workspace)
        self.assertIn("def render_private_portfolio(close, snapshot_usable, *, data_source='verified'):", workspace)
        self.assertIn("return\n    from edge_core.d1_store import d1_query", workspace)
        self.assertIn("snapshot_usable=(not is_provisional)", app)
        self.assertIn("data_source='provisional' if is_provisional else 'verified'", app)

if __name__ == "__main__":
    unittest.main()
