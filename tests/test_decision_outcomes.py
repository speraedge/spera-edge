import unittest
import pandas as pd
from edge_core.decision_outcomes import decision_outcomes

class DecisionOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.close = pd.DataFrame({'AAA':[100,102,105,110], 'BBB':[20,21,22,23]}, index=pd.bdate_range('2026-10-19', periods=4))
        self.events = [{'decision_id':'event-1','symbol':'AAA','session':'2026-10-19','decision':'REJECT'}]
    def test_exact_session_and_horizon(self):
        result = decision_outcomes(self.events,self.close,2).iloc[0]
        self.assertEqual(result['Observation'],'OBSERVED')
        self.assertEqual(result['Forward_Change_Pct'],5.0)
        self.assertEqual(result['decision_id'],'event-1')
    def test_no_future_data(self):
        result=decision_outcomes(self.events,self.close,10).iloc[0]
        self.assertEqual(result['Observation'],'AWAITING_FUTURE_SESSIONS')
    def test_missing_session(self):
        self.events[0]['session']='2026-10-18'
        self.assertEqual(decision_outcomes(self.events,self.close,2).iloc[0]['Observation'],'SESSION_NOT_IN_SNAPSHOT')
    def test_missing_symbol(self):
        self.events[0]['symbol']='ZZZ'
        self.assertEqual(decision_outcomes(self.events,self.close,2).iloc[0]['Observation'],'SYMBOL_NOT_IN_SNAPSHOT')
