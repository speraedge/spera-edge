"""Tests for OHLCV validation without external market data."""
import unittest
import pandas as pd
from edge_core.ohlcv_integrity import audit_ohlcv


class OhlcvIntegrityTests(unittest.TestCase):
    def setUp(self):
        index = pd.to_datetime(["2026-10-19", "2026-10-20"])
        self.close = pd.DataFrame({"AAA": [100., 101.]}, index=index)
        self.high = pd.DataFrame({"AAA": [102., 103.]}, index=index)
        self.low = pd.DataFrame({"AAA": [99., 100.]}, index=index)
        self.volume = pd.DataFrame({"AAA": [1000., 2000.]}, index=index)

    def check(self):
        return audit_ohlcv(self.close, self.high, self.low, self.volume,
                           expected_last_session="2026-10-20")

    def test_valid_is_research_only(self):
        result = self.check()
        self.assertEqual(result["observed_candles"], 2)
        self.assertFalse(result["certified"])

    def test_bad_high_low_close(self):
        self.high.iloc[0, 0] = 98
        with self.assertRaises(ValueError):
            self.check()

    def test_negative_volume(self):
        self.volume.iloc[0, 0] = -1
        with self.assertRaises(ValueError):
            self.check()

    def test_partial_candle(self):
        self.high.iloc[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            self.check()

    def test_aligned_missing_candle_reported(self):
        for frame in (self.close, self.high, self.low, self.volume):
            frame.iloc[0, 0] = float("nan")
        result = self.check()
        self.assertEqual(result["missing_candles"], 1)

    def test_misaligned_symbols(self):
        self.high.columns = ["OTHER"]
        with self.assertRaises(ValueError):
            self.check()

    def test_stale_metadata(self):
        with self.assertRaises(ValueError):
            audit_ohlcv(self.close, self.high, self.low, self.volume,
                        expected_last_session="2026-10-21")

    def test_weekend_session_rejected(self):
        self.close.index = pd.to_datetime(["2026-10-18", "2026-10-20"])
        for frame in (self.high, self.low, self.volume):
            frame.index = self.close.index
        with self.assertRaises(ValueError):
            self.check()


if __name__ == "__main__":
    unittest.main()
