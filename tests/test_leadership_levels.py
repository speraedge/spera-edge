import unittest
import pandas as pd
from edge_core.leadership_levels import classify_leadership

class LeadershipLevelsTests(unittest.TestCase):
    def test_review_cannot_become_leader(self):
        df = pd.DataFrame({"Symbol":["AAA","BBB"],"Data_Quality":["REVIEW","PASS"],"Percentile":[99,90]})
        result = classify_leadership(df,None)
        self.assertFalse(result.loc[0,"Momentum_Leader"])
        self.assertTrue(result.loc[1,"Momentum_Leader"])
        self.assertTrue(result["Setup_Status"].eq("NOT_CERTIFIED").all())
        self.assertTrue(result.loc[0,"Provisional_Momentum_Candidate"])
        self.assertFalse(result.loc[1,"Provisional_Momentum_Candidate"])
        self.assertEqual(result.loc[0,"Research_Level"],"PROVISIONAL_MOMENTUM")

    def test_duplicate_identity_fails(self):
        df = pd.DataFrame({"Symbol":["AAA","AAA"],"Data_Quality":["PASS","PASS"]})
        with self.assertRaises(ValueError):
            classify_leadership(df,None)

if __name__ == "__main__":
    unittest.main()
