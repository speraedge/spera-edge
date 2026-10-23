import csv
import tempfile
import unittest
from pathlib import Path
from edge_core.fundamentals_privacy import COLUMNS, validate_public_csv, publish_public_csv
from edge_core.manual_fundamentals import ManualFundamentals, merge_in_memory
from edge_fundamentals import fetch_one


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fundamentals_auto.csv"
        self.row = dict.fromkeys(COLUMNS, "")
        self.row.update(Symbol="ABC", Source="NONE", Status="AUTO_FAILED")

    def test_public_failed_row(self):
        publish_public_csv([self.row], self.path)
        self.assertTrue(validate_public_csv(self.path))

    def test_user_id_contamination_rejected(self):
        with self.assertRaisesRegex(ValueError, "PRIVACY_GATE"):
            publish_public_csv([dict(self.row, user_id="secret")], self.path)

    def test_private_revenue_contamination_rejected(self):
        with self.assertRaisesRegex(ValueError, "PRIVACY_GATE"):
            publish_public_csv([dict(self.row, manual_revenue=999)], self.path)

    def test_manual_flag_rejected(self):
        with self.assertRaisesRegex(ValueError, "PRIVACY_GATE"):
            publish_public_csv([dict(self.row, Status="MANUAL")], self.path)

    def test_existing_csv_contamination_rejected(self):
        with self.path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(COLUMNS) + ["user_id"])
            writer.writeheader()
            writer.writerow(dict(self.row, user_id="private"))
        with self.assertRaisesRegex(ValueError, "PRIVACY_GATE"):
            validate_public_csv(self.path)

    def test_owner_scoped_queries_and_merge(self):
        calls = []
        def query(sql, params=()):
            calls.append((sql, params))
            return [{"symbol": "ABC", "pe": 22, "market_cap": None,
                     "quarter_revenue": None, "quarter_pat": None,
                     "quarter_eps": None, "quarter_end": None}] if sql.startswith("SELECT") else []
        store = ManualFundamentals("a" * 64, query)
        row = store.get("ABC")
        self.assertEqual(calls[-1][1], ("a" * 64, "ABC"))
        self.assertEqual(merge_in_memory({"PE": 18, "Market_Cap": 500}, row),
                         {"PE": 22, "Market_Cap": 500})
        self.assertEqual(fetch_one("bad symbol", None)["Status"], "AUTO_FAILED")


if __name__ == "__main__":
    unittest.main()
