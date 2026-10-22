"""Financial comparability regression tests."""
import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.financial_comparability import review_comparability


class ComparabilityTests(unittest.TestCase):
    def test_annual_same_basis_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "financial.csv"
            fields = ["symbol", "isin", "period_end", "period_type", "basis",
                      "revenue", "pat", "source_url", "published_on"]
            with source.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for period, revenue, pat, basis in [
                    ("2025-03-31", "100", "10", "CONSOLIDATED"),
                    ("2026-03-31", "120", "12", "CONSOLIDATED"),
                    ("2026-03-31", "999", "99", "STANDALONE")]:
                    writer.writerow(dict(symbol="ABC", isin="INE000A01001",
                        period_end=period, period_type="FY", basis=basis,
                        revenue=revenue, pat=pat, source_url="https://example.org/report",
                        published_on=period))
            result = review_comparability(source, root / "out")
            self.assertEqual(result["status_counts"]["CANDIDATE_COMPARABLE_UNVERIFIED"], 1)
            self.assertEqual(result["status_counts"]["MISSING_OR_DUPLICATE_PRIOR_PERIOD"], 2)
            self.assertFalse(result["certified"])
            with (root / "out" / "financial_comparability.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[1]["revenue_growth_candidate_pct"], "20.0")
            self.assertEqual(rows[1]["certified"], "False")

    def test_future_and_reversed_publication_dates_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "financial.csv"
            fields = ["symbol", "isin", "period_end", "period_type", "basis",
                      "revenue", "pat", "source_url", "published_on"]
            for prior_published, current_published in (
                ("2025-03-31", "2099-01-01"),
                ("2026-04-15", "2026-04-01"),
            ):
                with self.subTest(prior=prior_published, current=current_published):
                    with source.open("w", newline="") as stream:
                        writer = csv.DictWriter(stream, fieldnames=fields)
                        writer.writeheader()
                        for period, published, revenue in (
                            ("2025-03-31", prior_published, "100"),
                            ("2026-03-31", current_published, "120"),
                        ):
                            writer.writerow(dict(symbol="ABC", isin="INE000A01001",
                                period_end=period, period_type="FY",
                                basis="CONSOLIDATED", revenue=revenue, pat="10",
                                source_url="https://example.org/report",
                                published_on=published))
                    result = review_comparability(source, root / "out")
                    self.assertEqual(result["status_counts"].get("CANDIDATE_COMPARABLE_UNVERIFIED", 0), 0)
                    self.assertEqual(result["status_counts"]["INVALID_PUBLICATION_DATE"], 1)

    def test_quarterly_previous_quarter_boundary(self):
        from edge_core.financial_comparability import _prior_period
        self.assertEqual(_prior_period("2026-03-31", "Q"), "2025-12-31")
        self.assertEqual(_prior_period("2026-06-30", "Q"), "2026-03-31")
