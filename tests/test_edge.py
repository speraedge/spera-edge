import unittest
import numpy as np
import pandas as pd
from edge_core.analytics import stage2_template, market_breadth
from edge_core.momentum_v1 import apply_frozen_v1_scores

class EdgeTests(unittest.TestCase):
    def test_stage2_short_history_fails_closed(self):
        self.assertFalse(stage2_template(pd.Series(range(100)))["eligible"])

    def test_breadth_no_data(self):
        self.assertIsNone(market_breadth(pd.DataFrame())["above_50_pct"])

    def test_frozen_ranking_excludes_fail(self):
        df = pd.DataFrame({"Data_Quality":["PASS","PASS","FAIL"],"Ret_6M":[.4,.2,.9],"Ret_12M":[.8,.4,1.4],"AnnVol":[.3,.4,.2]})
        out=apply_frozen_v1_scores(df)
        self.assertTrue(np.isnan(out.loc[2,"Pure_Momentum_Rank"]))
        self.assertEqual(int(out.loc[0,"Pure_Momentum_Rank"]),1)

if __name__ == "__main__":
    unittest.main()
