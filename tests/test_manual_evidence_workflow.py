import csv
import json
import tempfile
import unittest
from pathlib import Path
from tools.manual_evidence_workflow import execute


class WorkflowTests(unittest.TestCase):
    def test_shortlist_membership_queue_and_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def write(name, rows):
                path = root / name
                with path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                return path
            member = write("members.csv", [{"Symbol": "ABC", "ISIN Code": "INE000A01001"}])
            shortlist = write("short.csv", [{"Symbol": "ABC"}])
            financials = write("financial.csv", [dict(symbol="ABC", isin="INE000A01001",
                period_end="2026-09-30", period_type="Q", basis="CONSOLIDATED",
                revenue="100", pat="", published_on="2026-10-20",
                source_url="https://example.org/filing.pdf")])
            submissions = write("sub.csv", [dict(symbol="ABC", isin="INE000A01001",
                period_end="2026-09-30", period_type="Q", basis="CONSOLIDATED",
                revenue="100", pat="12", published_on="2026-10-20",
                source_url="https://example.org/filing.pdf")])
            out = root / "output"
            result = execute(shortlist, member, financials, "2026-09-30", out, submissions)
            self.assertEqual(result["queue_rows"], 1)
            self.assertEqual(result["quarantined"], 1)
            self.assertFalse(result["certified"])
            self.assertIn("pat", (out / "manual_evidence_queue.csv").read_text())
            self.assertFalse(json.loads((out / "manual_evidence_summary.json").read_text())["certified"])

    def test_unknown_shortlist_symbol_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "membership.csv").write_text("Symbol,ISIN Code\nABC,INE000A01001\n")
            (root / "short.csv").write_text("Symbol\nUNKNOWN\n")
            (root / "financial.csv").write_text("symbol,isin\n")
            with self.assertRaises(ValueError):
                execute(root / "short.csv", root / "membership.csv",
                        root / "financial.csv", "2026-09-30", root / "out")


if __name__ == "__main__":
    unittest.main()
