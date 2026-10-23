"""Phase 2 candlestick safety and rendering regression tests."""
import unittest
import numpy as np
import pandas as pd
from edge_symbol_charts import render_validated_ohlcv_png


class CandlestickChartTests(unittest.TestCase):
    def setUp(self):
        index = pd.bdate_range("2025-01-01", periods=260)
        base = np.linspace(100, 160, len(index))
        self.open_ = pd.DataFrame({"AAA": base}, index=index)
        self.high = pd.DataFrame({"AAA": base + 2}, index=index)
        self.low = pd.DataFrame({"AAA": base - 2}, index=index)
        self.close = pd.DataFrame({"AAA": base + 1}, index=index)
        self.volume = pd.DataFrame({"AAA": np.full(len(index), 10000)}, index=index)

    def render(self, **kwargs):
        return render_validated_ohlcv_png(self.open_, self.high, self.low,
                                          self.close, self.volume, "AAA", **kwargs)

    def test_png_with_research_levels(self):
        raw = self.render(pivot=165, stop=145)
        self.assertTrue(raw.startswith(bytes.fromhex("89504e470d0a1a0a")))
        self.assertGreater(len(raw), 1000)

    def test_rejects_missing_actual_open(self):
        with self.assertRaises(ValueError):
            render_validated_ohlcv_png(pd.DataFrame(index=self.open_.index),
                                       self.high, self.low, self.close,
                                       self.volume, "AAA")

    def test_rejects_invalid_candle(self):
        self.high.iloc[-1, 0] = 0
        with self.assertRaises(ValueError):
            self.render()

    def test_bad_date_in_open_csv_fails_gracefully(self):
        from io import StringIO
        csv = self.open_.reset_index().rename(columns={"index": "Date"}).to_csv(index=False)
        csv += "not-a-date,101.0\\n"
        bad = pd.read_csv(StringIO(csv), index_col="Date")
        with self.assertRaisesRegex(ValueError, "Chart unavailable: invalid dates in Open"):
            render_validated_ohlcv_png(bad, self.high, self.low, self.close,
                                       self.volume, "AAA")

    def test_mixed_index_types_are_coerced_before_alignment(self):
        open_string = self.open_.copy()
        open_string.index = open_string.index.strftime("%Y-%m-%d")
        raw = render_validated_ohlcv_png(open_string, self.high, self.low,
                                         self.close, self.volume, "AAA")
        self.assertTrue(raw.startswith(bytes.fromhex("89504e470d0a1a0a")))

    def test_mismatched_dates_use_intersection_not_union(self):
        extra = self.open_.iloc[:1].copy()
        extra.index = pd.DatetimeIndex(["2024-12-31"])
        open_extra = pd.concat([extra, self.open_])
        raw = render_validated_ohlcv_png(open_extra, self.high, self.low,
                                         self.close, self.volume, "AAA")
        self.assertTrue(raw.startswith(bytes.fromhex("89504e470d0a1a0a")))

    def test_rejects_missing_history(self):
        with self.assertRaises(ValueError):
            self.render(bars=60)


if __name__ == "__main__":
    unittest.main()
