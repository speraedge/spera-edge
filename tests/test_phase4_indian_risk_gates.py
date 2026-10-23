import unittest
import pandas as pd
from edge_core.indian_risk_gates import (atr_stop, require_liquidity,
    net_reward_risk, require_earnings_clear, trailing_stop_reminder)

class IndianRiskGatesTests(unittest.TestCase):
    def test_atr_stop(self):
        c = pd.Series([100.0] * 20)
        h = c + 1
        l = c - 1
        self.assertAlmostEqual(atr_stop(100, h, l, c), 95)
    def test_wide_atr_rejected(self):
        c = pd.Series([100.0] * 20)
        with self.assertRaisesRegex(ValueError, "ATR_STOP_TOO_WIDE"):
            atr_stop(100, c+5, c-5, c)
    def test_liquidity_gate(self):
        with self.assertRaisesRegex(ValueError, "ADTV_BELOW_5_CRORE"):
            require_liquidity(pd.Series([100]*20), pd.Series([100]*20))
        self.assertTrue(require_liquidity(pd.Series([100]*20), pd.Series([600000]*20)))
    def test_net_costs_reduce_rr(self):
        result = net_reward_risk(100, 95, 110, 10)
        self.assertLess(result["net_rr"], 2)
    def test_earnings_unknown_fails_closed(self):
        for value in (True, None):
            with self.assertRaisesRegex(ValueError, "EARNINGS_EVENT_GAP_RISK"):
                require_earnings_clear(value)
    def test_2r_reminder(self):
        self.assertTrue(trailing_stop_reminder(100, 95, 110))
        self.assertFalse(trailing_stop_reminder(100, 95, 109))
if __name__ == "__main__":
    unittest.main()
