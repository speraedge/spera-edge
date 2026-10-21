import unittest
import numpy as np
import pandas as pd
from edge_core.research_pipeline import derive_research

class ResearchPipelineTests(unittest.TestCase):
    def test_research_remains_uncertified(self):
        dates=pd.bdate_range("2025-01-01",periods=260)
        close=pd.DataFrame({"AAA.NS":np.linspace(100,200,260),"BBB.NS":np.linspace(90,110,260)},index=dates)
        volume=pd.DataFrame(10000,index=dates,columns=close.columns)
        result,breadth=derive_research(close,volume)
        self.assertTrue((result["Data_Quality"]=="REVIEW").all())
        self.assertEqual(breadth["coverage"],2)
        self.assertTrue(result["Pure_Momentum_Rank"].notna().all())
    def test_insufficient_history_fails_closed(self):
        dates=pd.bdate_range("2026-01-01",periods=40)
        close=pd.DataFrame({"AAA.NS":[100.0]*40},index=dates)
        volume=pd.DataFrame({"AAA.NS":[1000]*40},index=dates)
        result,_=derive_research(close,volume)
        self.assertEqual(result.iloc[0]["Data_Quality"],"FAIL")

if __name__=="__main__":
    unittest.main()
