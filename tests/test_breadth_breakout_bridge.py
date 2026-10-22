import unittest
import pandas as pd
from edge_core.breadth_breakout_bridge import breadth_breakout_summary


class BreadthBreakoutBridgeTests(unittest.TestCase):
    def test_same_session_breadth_and_missing_stay_separate(self):
        idx = pd.to_datetime(["2026-10-12", "2026-10-13", "2026-10-14"])
        breadth = pd.DataFrame({"Above_50_Pct": [65, 30, 50],
                                "Above_200_Pct": [70, 55, 50]}, index=idx)
        events = pd.DataFrame({"Session": ["2026-10-12", "2026-10-13",
                                            "2026-10-14", "2026-10-15"],
                               "Outcome": ["SUCCESS", "STOP_BREACH",
                                           "UNRESOLVED", "SUCCESS"]})
        result = breadth_breakout_summary(events, breadth).set_index("Breadth_At_Breakout")
        self.assertEqual(result.loc["BROAD", "Successes"], 1)
        self.assertEqual(result.loc["DEFENSIVE", "Failures_Incl_Stops"], 1)
        self.assertEqual(result.loc["MIXED", "Unresolved"], 1)
        self.assertEqual(result.loc["NO_BREADTH", "Successes"], 1)

    def test_missing_breadth_columns_fail_closed(self):
        with self.assertRaises(ValueError):
            breadth_breakout_summary(pd.DataFrame({"Session": [], "Outcome": []}),
                                     pd.DataFrame({"Above_50_Pct": []}))
