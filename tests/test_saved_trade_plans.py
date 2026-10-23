import tempfile
import unittest
from pathlib import Path
from edge_core.saved_trade_plans import validate_plan, add_plan, load_plans, evaluate_plans, status


class SavedPlansTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "saved_plans.json"
        self.plan = validate_plan("ABC", 100, 95, 120, "2026-10-23")

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip_and_duplicate_rejected(self):
        add_plan(self.plan, self.path)
        self.assertEqual(load_plans(self.path), [self.plan])
        with self.assertRaises(ValueError):
            add_plan(self.plan, self.path)

    def test_status_precedence(self):
        self.assertEqual(status(self.plan, 94), "INVALID")
        self.assertEqual(status(self.plan, 100), "WAITING")
        self.assertEqual(status(self.plan, 102), "TRIGGERED")
        self.assertEqual(status(self.plan, 106), "EXTENDED")
        self.assertEqual(status(self.plan, None), "NO_PRICE")

    def test_invalid_removed_only_from_active_list(self):
        rows, active = evaluate_plans([self.plan], {"ABC": 94})
        self.assertEqual(rows, [])
        self.assertEqual(active, [])

    def test_bad_levels_rejected(self):
        with self.assertRaises(ValueError):
            validate_plan("ABC", 100, 105, 120, "2026-10-23")
        with self.assertRaises(ValueError):
            validate_plan("ABC", 100, 95, float("nan"), "2026-10-23")

    def test_no_price_does_not_invalidate(self):
        rows, active = evaluate_plans([self.plan], {})
        self.assertEqual(len(active), 1)
        self.assertEqual(rows[0]["Status"], "NO_PRICE")


if __name__ == "__main__":
    unittest.main()
