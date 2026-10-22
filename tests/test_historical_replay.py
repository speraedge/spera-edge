import unittest
import numpy as np
import pandas as pd
from edge_core.historical_replay import replay_breakout_rules
from edge_core.breakout_health import breakout_health


class HistoricalReplayTests(unittest.TestCase):
    def fixture(self):
        idx = pd.bdate_range("2025-01-01", periods=85)
        close = pd.DataFrame({"A": np.full(85, 100.0)}, index=idx)
        high = pd.DataFrame({"A": np.full(85, 101.0)}, index=idx)
        low = pd.DataFrame({"A": np.full(85, 99.0)}, index=idx)
        low.iloc[66:, 0] = 101.0
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

    def test_signal_never_uses_future_candles(self):
        c, h, l, v = self.fixture()
        full = replay_breakout_rules(c, h, l, v, start=c.index[65], end=c.index[65])
        partial = replay_breakout_rules(c.iloc[:66], h.iloc[:66],
                                        l.iloc[:66], v.iloc[:66], start=c.index[65])
        self.assertEqual(full.iloc[0]["Pivot"], partial.iloc[0]["Pivot"])
        self.assertEqual(full.iloc[0]["Volume_Ratio"], partial.iloc[0]["Volume_Ratio"])
        self.assertEqual(full.iloc[0]["Stop"], partial.iloc[0]["Stop"])

    def test_reference_scanner_parity(self):
        c, h, l, v = self.fixture()
        reference = breakout_health(c, h, v, low=l, horizon=10, lookback=len(c))["events"]
        replay = replay_breakout_rules(c, h, l, v, horizon=10)
        self.assertEqual(reference["Session"].tolist(), replay["Session"].tolist())
        self.assertEqual(reference["Outcome"].tolist(), replay["Outcome"].tolist())
        self.assertEqual(reference["Pivot"].tolist(), replay["Pivot"].tolist())

    def test_candidate_subset_matches_full_universe(self):
        c, h, l, v = self.fixture()
        for frame in (c, h, l, v):
            frame["B"] = frame["A"]
        full = replay_breakout_rules(c, h, l, v, start=c.index[65], end=c.index[65])
        selected = replay_breakout_rules(c[["A"]], h[["A"]], l[["A"]], v[["A"]],
                                         start=c.index[65], end=c.index[65])
        self.assertEqual(len(full), 2)
        self.assertEqual(len(selected), 1)
        self.assertEqual(full[full["Symbol"].eq("A")].reset_index(drop=True).to_dict("records"),
                         selected.to_dict("records"))

    def test_misaligned_input_fails(self):
        c, h, l, v = self.fixture()
        with self.assertRaises(ValueError):
            replay_breakout_rules(c, h.iloc[:-1], l, v)
