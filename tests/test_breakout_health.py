import unittest
import numpy as np
import pandas as pd
from edge_core.breakout_health import breakout_health


class BreakoutHealthTests(unittest.TestCase):
    def fixtures(self):
        idx = pd.bdate_range("2026-01-01", periods=90)
        close = pd.DataFrame({"A": np.full(90, 100.0)}, index=idx)
        high = pd.DataFrame({"A": np.full(90, 101.0)}, index=idx)
        volume = pd.DataFrame({"A": np.full(90, 100.0)}, index=idx)
        close.iloc[65, 0] = 105.0
        high.iloc[65, 0] = 106.0
        volume.iloc[65, 0] = 200.0
        close.iloc[75:, 0] = 110.0
        high.iloc[75:, 0] = 111.0
        return close, high, volume

    def test_resolved_success_uses_forward_close(self):
        c, h, v = self.fixtures()
        result = breakout_health(c, h, v, lookback=30)
        self.assertEqual(result["successes"], 1)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(result["success_rate_pct"], 100.0)

    def test_unresolved_not_counted_as_success(self):
        c, h, v = self.fixtures()
        c.iloc[65, 0] = 100.0
        h.iloc[65, 0] = 101.0
        v.iloc[65, 0] = 100.0
        c.iloc[85, 0] = 115.0
        h.iloc[85, 0] = 116.0
        v.iloc[85, 0] = 200.0
        result = breakout_health(c, h, v, lookback=30)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(result["unresolved"], 1)
        self.assertIsNone(result["success_rate_pct"])

    def test_misaligned_inputs_rejected(self):
        c, h, v = self.fixtures()
        with self.assertRaises(ValueError):
            breakout_health(c, h.iloc[:-1], v)


if __name__ == "__main__":
    unittest.main()
