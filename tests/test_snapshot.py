import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from tools.build_upstox_snapshot import build

class SnapshotTests(unittest.TestCase):
    def test_snapshot_outputs(self):
        idx=pd.to_datetime(["2026-10-19", "2026-10-20"])
        candles=pd.DataFrame({"open":[1,2],"high":[2,3],"low":[1,2],"close":[2,3],"volume":[100,200]},index=idx)
        with tempfile.TemporaryDirectory() as d, patch("tools.build_upstox_snapshot.fetch_daily_candles",return_value=candles):
            coverage=build({"TEST":"NSE_EQ|TEST"},"2026-10-01","2026-10-20",d,"fake")
            self.assertEqual(coverage["TEST"]["rows"],2)
            self.assertEqual(len(pd.read_csv(d+"/close.csv")),2)
    def test_empty_mapping_fails(self):
        with self.assertRaises(ValueError):
            build({},"2026-10-01","2026-10-20","unused","fake")

if __name__=="__main__":
    unittest.main()
