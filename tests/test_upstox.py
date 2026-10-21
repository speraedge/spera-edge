import unittest
from edge_core.upstox import fetch_daily_candles, UpstoxDataError

class Response:
    def raise_for_status(self):
        pass
    def json(self):
        return {"status": "success", "data": {"candles": [
            ["2026-10-20T00:00:00+05:30", 100, 105, 98, 102, 12345, 0],
            ["2026-10-19T00:00:00+05:30", 99, 101, 97, 100, 11234, 0],
        ]}}

class Session:
    def __init__(self):
        self.url = None
        self.headers = None
    def get(self, url, headers, timeout):
        self.url, self.headers = url, headers
        return Response()

class UpstoxTests(unittest.TestCase):
    def test_historical_response(self):
        session = Session()
        df = fetch_daily_candles("NSE_EQ|INE002A01018", "2026-10-01", "2026-10-20", token="test", session=session)
        self.assertEqual(len(df), 2)
        self.assertEqual(float(df.iloc[-1]["close"]), 102)
        self.assertIn("NSE_EQ%7CINE002A01018", session.url)
        self.assertEqual(session.headers["Authorization"], "Bearer test")
    def test_missing_token(self):
        with self.assertRaises(UpstoxDataError):
            fetch_daily_candles("NSE_EQ|test", "2026-10-01", "2026-10-20", token="")

if __name__ == "__main__":
    unittest.main()
