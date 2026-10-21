import unittest
import pandas as pd
from edge_core.leadership_levels import classify_leadership
from edge_core.setup_scanner import compute_setup_scanner, setup_scanner_coverage

class LeadershipIntegrationTests(unittest.TestCase):
    def test_provisional_setup_never_certified(self):
        ranks=pd.DataFrame({"Symbol":["ABC"],"Data_Quality":["REVIEW"],"Percentile":[95]})
        close=pd.DataFrame({"ABC":[100+i*.5 for i in range(253)]})
        setups=pd.DataFrame({"Ticker":["ABC"]})
        out=classify_leadership(ranks,close,setups)
        self.assertTrue(out.loc[0,"Setup_Diagnostic"])
        self.assertEqual(out.loc[0,"Setup_Status"],"NOT_CERTIFIED")
        self.assertEqual(out.loc[0,"SEPA_Status"],"PENDING_RS_SECTOR_AND_SOURCE_VERIFICATION")

    def test_bare_nse_symbol_ohlcv_supported(self):
        idx=pd.date_range("2025-01-01",periods=253,freq="B")
        close=pd.DataFrame({"ABC":[100+i*.1 for i in range(253)]},index=idx)
        high=close+1
        low=close-1
        volume=pd.DataFrame({"ABC":[10000]*253},index=idx)
        coverage=setup_scanner_coverage(close,volume,high,low,symbols=["ABC"])
        self.assertEqual(coverage["symbols_examined"],1)
        self.assertEqual(coverage["symbols_with_sufficient_history"],1)
        result=compute_setup_scanner(close,volume,symbols=["ABC"],high_df=high,low_df=low)
        self.assertIn("Ticker",result.columns)

if __name__=="__main__":
    unittest.main()
