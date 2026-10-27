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

    def test_infinite_price_rejected(self):
        self.close.iloc[0, 0] = float("inf")
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            self.check()

    def test_infinite_volume_rejected(self):
        self.volume.iloc[0, 0] = float("inf")
        with self.assertRaisesRegex(ValueError, "Non-finite"):
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


    def test_snapshot_builder_filters_phantom_weekend_but_keeps_special_session(self):
        from tools.publish_edge_snapshot import drop_unverified_weekend_rows
        frame = pd.DataFrame({"close": [100., 101., 102., 103.]},
                             index=pd.to_datetime(["2026-01-30", "2026-02-01",
                                                   "2026-10-25", "2026-10-26"]))
        with self.assertLogs(level="WARNING") as logs:
            clean = drop_unverified_weekend_rows(frame, symbol="AAA")
        self.assertEqual(list(clean.index.strftime("%Y-%m-%d")),
                         ["2026-01-30", "2026-02-01", "2026-10-26"])
        self.assertIn("2026-10-25", logs.output[0])
        self.assertEqual(frame.shape[0], 4)

    def test_snapshot_builder_all_weekend_rows_filtered(self):
        from tools.publish_edge_snapshot import drop_unverified_weekend_rows
        frame = pd.DataFrame({"close": [100.]},
                             index=pd.to_datetime(["2026-10-25"]))
        with self.assertLogs(level="WARNING"):
            clean = drop_unverified_weekend_rows(frame)
        self.assertTrue(clean.empty)

    def test_official_budget_session_is_not_discarded(self):
        for frame in (self.close, self.high, self.low, self.volume):
            frame.index = pd.to_datetime(['2026-01-30', '2026-02-01'])
        result = audit_ohlcv(self.close, self.high, self.low, self.volume)
        self.assertEqual(result['verified_special_sessions'], ['2026-02-01'])

    def test_official_muhurat_session_is_not_discarded(self):
        for frame in (self.close, self.high, self.low, self.volume):
            frame.index = pd.to_datetime(['2026-11-06', '2026-11-08'])
        result = audit_ohlcv(self.close, self.high, self.low, self.volume,
                             expected_last_session='2026-11-08')
        self.assertEqual(result['verified_special_sessions'], ['2026-11-08'])

    def test_unverified_weekend_date_reported_without_dropping(self):
        for frame in (self.close, self.high, self.low, self.volume):
            frame.index = pd.to_datetime(['2026-10-23', '2026-10-25'])
        with self.assertRaisesRegex(ValueError, 'Unverified weekend.*2026-10-25'):
            audit_ohlcv(self.close, self.high, self.low, self.volume)

    def test_special_session_freshness_after_muhurat(self):
        from edge_core.ohlcv_integrity import snapshot_is_fresh
        cases = [
            ('2026-11-08', '2026-11-08T16:00:00+05:30', True),
            ('2026-11-08', '2026-11-09T09:00:00+05:30', True),
            ('2026-11-06', '2026-11-09T09:00:00+05:30', False),
            ('2026-02-01', '2026-02-02T09:00:00+05:30', True),
            ('2026-01-30', '2026-02-02T09:00:00+05:30', False),
        ]
        for session, now, expected in cases:
            with self.subTest(session=session, now=now):
                self.assertEqual(snapshot_is_fresh(session, pd.Timestamp(now)), expected)

    def test_morning_schedule_uses_prior_completed_weekday(self):
        from edge_core.ohlcv_integrity import snapshot_is_fresh
        # Tuesday morning expects Monday, Saturday morning expects Friday.
        cases = [
            ('2026-10-26', '2026-10-27T09:00:00+05:30', True),
            ('2026-10-27', '2026-10-27T09:00:00+05:30', False),
            ('2026-10-23', '2026-10-24T09:00:00+05:30', True),
            ('2026-10-24', '2026-10-24T09:00:00+05:30', False),
            ('2026-10-23', '2026-10-26T09:00:00+05:30', True),
        ]
        for session, now, expected in cases:
            with self.subTest(session=session, now=now):
                self.assertEqual(snapshot_is_fresh(session, pd.Timestamp(now)), expected)

    def test_snapshot_freshness_requires_latest_expected_completed_session(self):
        from edge_core.ohlcv_integrity import snapshot_is_fresh
        cases = [('2026-10-21', '2026-10-22T15:00:00+05:30', True),
                 ('2026-10-21', '2026-10-22T16:00:00+05:30', False),
                 ('2026-10-22', '2026-10-22T15:00:00+05:30', False),
                 ('2026-10-23', '2026-10-25T18:00:00+05:30', True),
                 ('2026-02-01', '2026-02-01T16:00:00+05:30', True)]
        for session, now, expected in cases:
            with self.subTest(session=session, now=now):
                self.assertEqual(snapshot_is_fresh(session, pd.Timestamp(now)), expected)


if __name__ == "__main__":
    unittest.main()
