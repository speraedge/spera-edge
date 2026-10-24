import unittest
from edge_workspace import Ledger
from edge_core.stops import validate_stop_update


def event(kind, stop, qty=0, price=0):
    return dict(kind=kind, symbol="TEST", quantity=qty, price=price, stop=stop, fee=0, note="")


class StopWideningTests(unittest.TestCase):
    def test_raise_stop(self):
        positions, _ = Ledger._replay([event("BUY", 90, 1, 100), event("STOP", 105)], {})
        self.assertEqual(positions.iloc[0]["Stop"], 105)

    def test_lower_stop_forbidden(self):
        with self.assertRaisesRegex(ValueError, "STOP_WIDENING_FORBIDDEN"):
            Ledger._replay([event("BUY", 90, 1, 100), event("STOP", 89)], {})

    def test_equal_stop_accepted(self):
        positions, _ = Ledger._replay([event("BUY", 90, 1, 100), event("STOP", 90)], {})
        self.assertEqual(positions.iloc[0]["Stop"], 90)

    def test_second_buy_cannot_lower_stop(self):
        positions, _ = Ledger._replay([event("BUY", 90, 1, 100), event("BUY", 80, 1, 110)], {})
        self.assertEqual(positions.iloc[0]["Stop"], 90)
        self.assertEqual(positions.iloc[0]["Quantity"], 2)

    def test_reentry_after_full_exit_uses_fresh_stop(self):
        positions, _ = Ledger._replay([
            event("BUY", 90, 10, 100),
            event("SELL", 0, 10, 110),
            event("BUY", 72, 10, 80),
        ], {})
        self.assertEqual(positions.iloc[0]["Stop"], 72)
        self.assertEqual(positions.iloc[0]["Quantity"], 10)

    def test_partial_exit_then_buy_keeps_existing_stop(self):
        positions, _ = Ledger._replay([
            event("BUY", 90, 10, 100),
            event("SELL", 0, 5, 110),
            event("BUY", 72, 10, 80),
        ], {})
        self.assertEqual(positions.iloc[0]["Stop"], 90)
        self.assertEqual(positions.iloc[0]["Quantity"], 15)

    def test_nonpositive_stop_rejected(self):
        with self.assertRaises(ValueError):
            Ledger._replay([event("BUY", 90, 1, 100), event("STOP", 0)], {})

    def test_shared_validator(self):
        self.assertEqual(validate_stop_update(90, 100), 100)
        with self.assertRaisesRegex(ValueError, "STOP_WIDENING_FORBIDDEN"):
            validate_stop_update(90, 80)


if __name__ == "__main__":
    unittest.main()
