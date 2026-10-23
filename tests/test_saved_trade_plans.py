import unittest
from edge_core.saved_trade_plans import OwnerPlanStore, validate_plan, evaluate_plans, status


class FakeD1:
    def __init__(self):
        self.rows = []

    def __call__(self, sql, params=()):
        if sql.startswith("CREATE TABLE"):
            return []
        if sql.startswith("INSERT"):
            owner, pid, symbol, day, pivot, stop, target, created = params
            self.rows.append(dict(owner_id=owner, plan_id=pid, symbol=symbol,
                                  setup_date=day, pivot=pivot, stop=stop, target=target,
                                  status="ACTIVE"))
            return []
        if sql.startswith("UPDATE"):
            _, owner, pid = params
            for row in self.rows:
                if row["owner_id"] == owner and row["plan_id"] == pid:
                    row["status"] = "INVALID"
            return []
        if sql.startswith("SELECT"):
            owner = params[0]
            matches = [x for x in self.rows if x["owner_id"] == owner and x["status"] == "ACTIVE"]
            if len(params) > 1:
                matches = [x for x in matches if x["plan_id"] == params[1]]
            return matches
        raise AssertionError(sql)


class SavedPlansTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeD1()
        self.a = OwnerPlanStore("owner-A", self.db)
        self.b = OwnerPlanStore("owner-B", self.db)
        self.a.initialize()
        self.plan = validate_plan("ABC", 100, 95, 120, "2026-10-23")

    def test_owner_isolation(self):
        pid = self.a.add(self.plan)
        self.assertEqual(len(self.a.list_active()), 1)
        self.assertEqual(self.b.list_active(), [])
        with self.assertRaises(ValueError):
            self.b.load_active(pid)
        self.b.invalidate(pid)
        self.assertEqual(len(self.a.list_active()), 1)

    def test_invalidated_retained_for_audit(self):
        pid = self.a.add(self.plan)
        self.a.invalidate(pid)
        self.assertEqual(self.a.list_active(), [])
        self.assertEqual(len(self.db.rows), 1)
        self.assertEqual(self.db.rows[0]["status"], "INVALID")

    def test_status_precedence(self):
        self.assertEqual(status(self.plan, 94), "INVALID")
        self.assertEqual(status(self.plan, 100), "WAITING")
        self.assertEqual(status(self.plan, 102), "TRIGGERED")
        self.assertEqual(status(self.plan, 106), "EXTENDED")
        self.assertEqual(status(self.plan, None), "NO_PRICE")

    def test_no_price_does_not_invalidate(self):
        rows = evaluate_plans([self.plan], {})
        self.assertEqual(rows[0]["Status"], "NO_PRICE")

    def test_bad_levels_rejected(self):
        with self.assertRaises(ValueError):
            validate_plan("ABC", 100, 105, 120, "2026-10-23")


if __name__ == "__main__":
    unittest.main()
