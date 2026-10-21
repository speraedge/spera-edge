import unittest
import pandas as pd
from edge_core.momentum_universe import NIFTY_500, parse_constituent_csv

class UniverseTests(unittest.TestCase):
    def test_rejects_tiny_universe(self):
        text="Symbol,Industry,ISIN Code\nAAA,Industrials,INE000000001\n"*12
        with self.assertRaises(ValueError):
            parse_constituent_csv(text,NIFTY_500)
    def test_accepts_valid_official_shape(self):
        rows=["Symbol,Industry,ISIN Code"]
        for i in range(500):
            rows.append(f"SYM{i},Industry,INE{i:09d}")
        df,col=parse_constituent_csv("\n".join(rows),NIFTY_500)
        self.assertEqual(len(df),500)
        self.assertEqual(df.attrs["universe_count_status"],"PASS")
    def test_duplicate_isin_fails(self):
        rows=["Symbol,Industry,ISIN Code"]
        for i in range(500):
            rows.append(f"SYM{i},Industry,INE000000001")
        with self.assertRaises(ValueError):
            parse_constituent_csv("\n".join(rows),NIFTY_500)

if __name__=="__main__":
    unittest.main()
