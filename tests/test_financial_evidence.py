"""Financial evidence audit regression tests."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.financial_evidence import review_financials

class FinancialEvidenceTests(unittest.TestCase):
    def test_unverified_and_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "statements.csv"
            fields = ["symbol","isin","period_end","period_type","basis",
                      "revenue","pat","source_url","published_on"]
            with source.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(dict(zip(fields,["ABC","INE000A00001","2026-03-31","FY",
                    "CONSOLIDATED","100","10","https://example.org/filing","2026-05-20"])))
                writer.writerow(dict(zip(fields,["ABC","WRONG","2026-03-31","FY",
                    "CONSOLIDATED","100","10","https://example.org/filing","2026-05-20"])))
                writer.writerow(dict(zip(fields,["ABC","INE000A00001","2026-06-30","Q",
                    "CONSOLIDATED","-1","10","https://example.org/filing","2026-08-20"])))
            summary = review_financials(source, root / "out", {"ABC":"INE000A00001"})
            self.assertEqual(summary["rows"], 3)
            self.assertEqual(summary["certified_rows"], 0)
            self.assertFalse(summary["growth_ready"])
            with (root / "out" / "financial_evidence_review.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([r["status"] for r in rows], [
                "REVIEW_SOURCE_AND_COMPARABILITY", "IDENTITY_MISMATCH",
                "INVALID_FINANCIAL_VALUES"])
            self.assertTrue(all(r["certified"] == "False" for r in rows))

if __name__ == "__main__":
    unittest.main()
