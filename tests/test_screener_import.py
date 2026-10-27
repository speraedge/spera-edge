"""Screener Excel importer and fundamental acceleration safety tests."""
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from tools.import_screener_excel import (
    parse_screener_excel, calculate_acceleration, import_workbook,
)

OWNER = "a" * 64


class ScreenerImportTests(unittest.TestCase):
    def make_book(self, *, duplicate=False, missing=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "company.xlsx"
        periods = pd.date_range("2024-03-31", periods=8, freq="QE-MAR")
        headers = [p.strftime("%b %Y") for p in periods]
        if duplicate:
            headers[-1] = headers[-2]
        data = [
            ["Quarterly Results"] + [None] * 8,
            ["Particulars"] + headers,
            ["Sales +"] + [100, 110, 125, 145, 170, 205, 250, 310],
            ["EPS in Rs"] + [2, 3, 4, 5, 7, 11, 18, 30],
        ]
        if missing:
            data[-1][-1] = None
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame(data).to_excel(writer, sheet_name="Quarters", header=False, index=False)
        return path

    def test_growth_acceleration_pass(self):
        rows = parse_screener_excel(self.make_book())
        self.assertEqual(len(rows), 8)
        result = calculate_acceleration(rows)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["metrics"]["eps"]["yoy_accelerating"])

    def test_duplicate_dates_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_screener_excel(self.make_book(duplicate=True))

    def test_missing_eps_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_screener_excel(self.make_book(missing=True))

    def test_dry_run_has_no_d1_calls(self):
        def reject(*args, **kwargs):
            raise AssertionError("D1 must not be called")
        result = import_workbook(self.make_book(), "ABC", OWNER, query=reject, dry_run=True)
        self.assertEqual(result["status"], "PASS")

    def test_private_owner_scoped_d1_writes(self):
        calls = []
        def query(sql, params=()):
            calls.append((sql, params))
            return []
        result = import_workbook(self.make_book(), "ABC", OWNER, query=query)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(calls), 11)
        for sql, params in calls[2:]:
            self.assertEqual(params[0], OWNER)
            self.assertEqual(params[1], "ABC")
        self.assertFalse(any("data/latest" in sql or "public" in sql.lower() for sql, _ in calls))

    def test_nonpositive_eps_base_never_passes(self):
        rows = [{"quarter_end": str(x.date()), "revenue": 100 + i * 10, "eps": -1 if i == 3 else 2 + i}
                for i, x in enumerate(pd.date_range("2024-03-31", periods=8, freq="QE-MAR"))]
        self.assertNotEqual(calculate_acceleration(rows)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
