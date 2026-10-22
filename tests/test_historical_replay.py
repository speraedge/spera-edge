import unittest
import numpy as np
import pandas as pd
from edge_core.historical_replay import replay_breakout_rules


class HistoricalReplayTests(unittest.TestCase):
    def fixture(self):
        idx = pd.bdate_range("2025-01-01", periods=85)
        close = pd.DataFrame({"A": np.full(85, 100.0)}, index=idx)
        high = pd.DataFrame({"A": np.full(85, 101.0)}, index=idx)
        low = pd.DataFrame({"A": np.full(85, 99.0)}, index=idx)
        volume = pd.DataFrame({"A": np.full(85, 100.0)}, index=idx)
        close.iloc[65, 0] = 105
        high.iloc[65, 0] = 106
        volume.iloc[65, 0] = 200
        close.iloc[75:, 0] = 110
        high.iloc[75:, 0] = 111
        return close, high, low, volume

    def test_historical_signal_and_forward_outcome(self):
        c, h, l, v = self.fixture()
        result = replay_breakout_rules(c, h, l, v, start=c.index[65], end=c.index[65])
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Outcome"], "SUCCESS")
        self.assertEqual(result.iloc[0]["Session"], str(c.index[65].date()))

    def test_no_future_prices_required_for_signal(self):
        c, h, l, v = self.fixture()
        result = replay_breakout_rules(c.iloc[:66], h.iloc[:66], l.iloc[:66],
                                       v.iloc[:66], start=c.index[65])
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["Outcome"], "UNRESOLVED")

    def test_stop_precedes_positive_horizon_close(self):
        c, h, l, v = self.fixture()
        l.iloc[70, 0] = 95
        result = replay_breakout_rules(c, h, l, v, start=c.index[65], end=c.index[65])
        self.assertEqual(result.iloc[0]["Outcome"], "STOP_BREACH")

    def test_misaligned_input_fails(self):
        c, h, l, v = self.fixture()
        with self.assertRaises(ValueError):
            replay_breakout_rules(c, h.iloc[:-1], l, v)
