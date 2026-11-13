"""Regression checks for locally owned fundamentals publication."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/edge-snapshot.yml").read_text()
SCRIPT = (ROOT / "tools/fetch_fundamentals_local.py").read_text()


class LocalFundamentalsTests(unittest.TestCase):
    def test_snapshot_does_not_fetch_fundamentals(self):
        self.assertNotIn("python -m edge_fundamentals", WORKFLOW)
        self.assertNotIn("python -m tools.build_bse_mapping", WORKFLOW)
        self.assertIn("git restore --staged data/latest/fundamentals_auto.csv", WORKFLOW)

    def test_local_script_reuses_privacy_gate_and_preserves_last_good(self):
        self.assertIn("fetch = dalal.fundamentals", SCRIPT)
        self.assertIn("validate_public_csv(OUTPUT)", SCRIPT)
        self.assertIn("shutil.copy2(backup, OUTPUT)", SCRIPT)
        self.assertIn("if not verified:", SCRIPT)
        self.assertIn("if __name__ == \"__main__\":", SCRIPT)


if __name__ == "__main__":
    unittest.main()
