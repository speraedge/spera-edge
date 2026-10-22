"""Static release contract checks; live authentication and D1 require separate probes."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EdgeAcceptanceContractTests(unittest.TestCase):
    def test_five_tabs_and_research_only_boundary(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        expected = ('"Market Pulse", "Leadership Scanner", "Trade Desk", '
                    '"Portfolio & Journal", "Financial Evidence Review"')
        self.assertIn(expected, app)
        self.assertIn("## Five tabs", readme)
        self.assertIn("No brokerage execution", app)

    def test_weekday_snapshot_requires_validation_before_d1(self):
        workflow = (ROOT / ".github/workflows/edge-snapshot.yml").read_text(encoding="utf-8")
        steps = (
            "Build isolated NIFTY 500 snapshot",
            "Validate complete snapshot files and metadata",
            "Publish dated current official membership and benchmark research",
            "Validate published membership and benchmark evidence",
            "Publish validated leadership research to EDGE D1",
            "Publish non-secret research snapshot to EDGE repository",
        )
        offsets = [workflow.index(step) for step in steps]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("30 3 * * 2-6", workflow)
        self.assertIn("30 14 * * 1-5", workflow)
        self.assertNotIn("30 1,2,3 * * 2-6", workflow)
        self.assertNotIn("- cron: '0 14 * * 1-5'", workflow)
        freshness = "Enforce latest completed NSE session before live publication"
        self.assertIn(freshness, workflow)
        self.assertLess(workflow.index("Validate complete snapshot files and metadata"), workflow.index(freshness))
        self.assertLess(workflow.index(freshness), workflow.index("Publish validated leadership research to EDGE D1"))
        self.assertIn("if ! git diff --cached --quiet", workflow)

    def test_snapshot_validation_requires_no_certified_research(self):
        code = (ROOT / "edge_core/snapshot_integrity.py").read_text(encoding="utf-8")
        self.assertIn('meta.get("certified") is not False', code)
        self.assertIn('ranks["Data_Quality"].eq("PASS").any()', code)


if __name__ == "__main__":
    unittest.main()
