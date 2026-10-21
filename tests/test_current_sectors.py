import unittest
import pandas as pd
from edge_core.current_sectors import current_sector_research

class CurrentSectorTests(unittest.TestCase):
    def test_current_returns_not_archived_scores(self):
        idx=pd.date_range("2025-01-01",periods=70,freq="B")
        prices=pd.DataFrame({"A":[100+i for i in range(70)],"B":[100-i*.1 for i in range(70)]},index=idx)
        mapping=pd.DataFrame({"ticker":["A","B"],"sector":["Strong","Weak"],"week_key":["2026-10-16"]*2})
        result=current_sector_research(prices,mapping,"2026-10-16")
        self.assertEqual(result.iloc[0]["Sector"],"Strong")
        self.assertEqual(result.iloc[0]["Sector_Trust"],"PROVISIONAL_HISTORICAL_MEMBERSHIP")

    def test_rejects_wrong_mapping_week(self):
        prices=pd.DataFrame({"A":[100]*70})
        mapping=pd.DataFrame({"ticker":["A"],"sector":["Strong"],"week_key":["2026-10-09"]})
        with self.assertRaises(ValueError):
            current_sector_research(prices,mapping,"2026-10-16")

if __name__=="__main__":
    unittest.main()
