"""Phase 3 offline D1 SQL, identity isolation and exchange-schema regressions."""
import sqlite3
import unittest
from edge_core.manual_fundamentals import CREATE_SQL, ManualFundamentals
from edge_fundamentals import _quarter_result, fetch_one
from tools.build_bse_mapping import extract_mapping


class FakeExchange:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
    def get_json(self, url, params):
        self.calls.append((url, params))
        return self.payload


class Phase3IntegrationTests(unittest.TestCase):
    def test_owner_scoped_sqlite_d1_roundtrip(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        def query(sql, params=()):
            cursor = connection.execute(sql, params)
            connection.commit()
            return [dict(row) for row in cursor.fetchall()]
        a = ManualFundamentals("a" * 64, query)
        b = ManualFundamentals("b" * 64, query)
        a.initialize()
        values = dict(pe=21.0, market_cap=1234.0, quarter_revenue=100.0,
                      quarter_pat=12.0, quarter_eps=2.0, quarter_end="2026-09-30")
        a.save("ABC", values)
        self.assertEqual(a.get("ABC")["quarter_revenue"], 100.0)
        self.assertIsNone(b.get("ABC"))
        b.save("ABC", dict(values, quarter_revenue=200.0))
        self.assertEqual(a.get("ABC")["quarter_revenue"], 100.0)
        self.assertEqual(b.get("ABC")["quarter_revenue"], 200.0)

    def test_explicit_quarter_fields(self):
        client = FakeExchange({"Table": [{"QuarterEnd": "2026-09-30",
             "PeriodType": "QUARTER", "Revenue": "100", "PAT": "10", "EPS": "2.5"}]})
        data = _quarter_result("500325", client)
        self.assertEqual(data["Quarter_Revenue"], 100.0)
        self.assertEqual(data["Quarter_PAT"], 10.0)
        self.assertEqual(data["Quarter_EPS"], 2.5)

    def test_annual_is_not_quarter(self):
        client = FakeExchange({"Table": [{"QuarterEnd": "2026-09-30",
             "PeriodType": "ANNUAL", "Revenue": 100, "PAT": 10, "EPS": 2}]})
        with self.assertRaises(ValueError):
            _quarter_result("500325", client)

    def test_bse_mapping_requires_explicit_symbol(self):
        self.assertEqual(extract_mapping([{"NSESymbol": "ABC", "SCRIP_CD": "500325"}],
                                         ["ABC"]), {"ABC": "500325"})
        self.assertEqual(extract_mapping([{"SecurityName": "ABC", "SCRIP_CD": "500325"}],
                                         ["ABC"]), {})


if __name__ == "__main__":
    unittest.main()
