import unittest
import pandas as pd
from edge_core.relative_strength import relative_strength

class RelativeStrengthTests(unittest.TestCase):
    def test_outperformance(self):
        idx=pd.date_range("2025-01-01",periods=253,freq="B")
        stock=pd.Series([100+i for i in range(253)],index=idx)
        benchmark=pd.Series([100+i*.5 for i in range(253)],index=idx)
        result=relative_strength(stock,benchmark)
        self.assertGreater(result["RS_252D"],0)
        self.assertEqual(result["RS_Evidence"],"COMPUTED_ALIGNED")

    def test_insufficient(self):
        idx=pd.date_range("2025-01-01",periods=100,freq="B")
        result=relative_strength(pd.Series([100]*100,index=idx),pd.Series([100]*100,index=idx))
        self.assertEqual(result["RS_Evidence"],"INSUFFICIENT_HISTORY")

if __name__=="__main__":
    unittest.main()
