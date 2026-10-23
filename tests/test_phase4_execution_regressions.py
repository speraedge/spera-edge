"""End-to-end Phase 4 fail-closed liquidity, earnings and sizing checks."""
import unittest
import pandas as pd
from edge_workspace import plan_quantity
from edge_core.indian_risk_gates import require_liquidity, trailing_stop_reminder


class Phase4ExecutionGatesTests(unittest.TestCase):
    def setUp(self):
        self.close = pd.Series([100.0] * 20)
        self.high = self.close + 1
        self.low = self.close - 1
        self.atr = (self.high, self.low, self.close)
        self.base = dict(equity=500000, risk_pct=1, entry=100, stop=95,
                         committed_risk=0, exposure=0, target=111,
                         atr_candles=self.atr, earnings_within_five_days=False,
                         liquidity_candles=(self.close, pd.Series([600000] * 20)))

    def test_low_volume_candidate_excluded_by_full_sizing_pipeline(self):
        inputs = dict(self.base, liquidity_candles=(self.close, pd.Series([100] * 20)))
        with self.assertRaisesRegex(ValueError, "ADTV_BELOW_5_CRORE"):
            plan_quantity(**inputs)

    def test_sizing_8_percent_ceiling(self):
        with self.assertRaisesRegex(ValueError, "maximum initial stop distance is 8%"):
            plan_quantity(**dict(self.base, stop=91))

    def test_earnings_unknown_and_near_block_sizing(self):
        for value in (None, True):
            with self.subTest(earnings=value):
                with self.assertRaisesRegex(ValueError, "EARNINGS_EVENT_GAP_RISK"):
                    plan_quantity(**dict(self.base, earnings_within_five_days=value))

    def test_fees_can_reduce_reward_risk_below_two(self):
        with self.assertRaisesRegex(ValueError, "at least 2:1"):
            plan_quantity(**dict(self.base, target=110))

    def test_valid_atr_liquidity_earnings_and_fees(self):
        result = plan_quantity(**self.base)
        self.assertGreater(result["quantity"], 0)
        self.assertLessEqual(result["planned_risk"], 5000)

    def test_original_r_remains_unchanged_after_stop_moved(self):
        self.assertFalse(trailing_stop_reminder(100, 95, 109))
        self.assertTrue(trailing_stop_reminder(100, 95, 110))
        # A breakeven trailing stop must not be substituted for the initial stop.
        self.assertFalse(trailing_stop_reminder(100, 100, 110))


if __name__ == "__main__":
    unittest.main()
