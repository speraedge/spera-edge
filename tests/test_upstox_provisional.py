"""Fail-closed provisional Upstox adapter tests."""
import unittest
from unittest.mock import Mock
import pandas as pd
from edge_core.upstox import UpstoxDataError, fetch_intraday_daily_candle, reconcile_provisional_daily

class ProvisionalUpstoxTests(unittest.TestCase):
    def provider(self, candles):
        response = Mock()
        response.json.return_value = {"status": "success", "data": {"candles": candles}}
        response.raise_for_status.return_value = None
        client = Mock()
        client.get.return_value = response
        return client

    def test_reconcile_does_not_mutate_history(self):
        row = ["2026-10-27T15:30:00+05:30", 100, 105, 99, 103, 1000]
        candle = fetch_intraday_daily_candle("test", "2026-10-27", token="fake", session=self.provider([row]))
        history = pd.DataFrame({"open": [90.], "high": [94.], "low": [89.],
                                "close": [93.], "volume": [500.]}, index=[pd.Timestamp("2026-10-26").date()])
        merged = reconcile_provisional_daily(history, candle, "2026-10-27")
        self.assertEqual(len(history), 1)
        self.assertEqual(len(merged), 2)

    def test_invalid_provisional_rows_fail_closed(self):
        row = ["2026-10-27T15:30:00+05:30", 100, 105, 99, 103, 1000]
        for candles in ([row, row], [[row[0], 100, 101, 99, 103, 1000]], [], [["2026-10-26T15:30:00+05:30", 100, 105, 99, 103, 1000]]):
            with self.subTest(candles=candles):
                with self.assertRaises(UpstoxDataError):
                    fetch_intraday_daily_candle("test", "2026-10-27", token="fake", session=self.provider(candles))
