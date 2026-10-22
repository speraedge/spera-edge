"""Offline tests for NSE downloaded corporate-action intake."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.import_nse_actions import import_nse_actions


class NSEActionsImportTests(unittest.TestCase):
    def test_import_preserves_source_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            members = root / "members.csv"
            actions = root / "actions.csv"
            with members.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Symbol", "ISIN Code"])
                writer.writerow(["ABC", "INE000A01001"])
            with actions.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["SYMBOL", "PURPOSE", "EX-DATE"])
                writer.writerow(["ABC", "Bonus 1:1", "20-Oct-2026"])
            manifest = import_nse_actions(actions, members, root / "output")
            self.assertEqual(manifest["source_rows"], 1)
            self.assertFalse(manifest["certified"])
            self.assertFalse(manifest["adjustment_factors_approved"])
            with (root / "output" / "review" / "corporate_action_review.csv").open(newline="") as stream:
                finding = next(csv.DictReader(stream))
            self.assertEqual(finding["status"], "MISSING_OFFICIAL_SOURCE")
            self.assertEqual(finding["approved"], "False")
            self.assertEqual(finding["isin"], "INE000A01001")

    def test_rejects_unknown_export_shape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "members.csv").write_text("Symbol,ISIN Code\nABC,INE000A01001\n")
            (root / "actions.csv").write_text("SYMBOL,PURPOSE\nABC,Split\n")
            with self.assertRaises(ValueError):
                import_nse_actions(root / "actions.csv", root / "members.csv", root / "out")


if __name__ == "__main__":
    unittest.main()
