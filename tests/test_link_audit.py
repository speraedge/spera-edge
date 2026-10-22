import unittest
from edge_core.link_audit import audit_decision_links

class LinkAuditTests(unittest.TestCase):
    def test_valid_and_unlinked(self):
        decisions=[{'decision_id':'d1','decision':'TAKE','symbol':'ABC'}]
        events=[{'event_id':'e1','kind':'BUY','symbol':'ABC'}, {'event_id':'e2','kind':'BUY','symbol':'XYZ'}]
        links=[{'decision_id':'d1','event_id':'e1'}]
        result=audit_decision_links(decisions,events,links)
        self.assertEqual(result['Status'].tolist(),['VALID','UNLINKED_BUY'])
    def test_mismatch_and_missing_reference(self):
        decisions=[{'decision_id':'d1','decision':'TAKE','symbol':'ABC'}]
        events=[{'event_id':'e1','kind':'BUY','symbol':'XYZ'}]
        links=[{'decision_id':'d1','event_id':'e1'}, {'decision_id':'missing','event_id':'missing'}]
        self.assertEqual(audit_decision_links(decisions,events,links)['Status'].tolist(),['SYMBOL_MISMATCH','MISSING_REFERENCED_RECORD'])
    def test_duplicate_event(self):
        decisions=[{'decision_id':'d1','decision':'TAKE','symbol':'ABC'}]
        events=[{'event_id':'e1','kind':'BUY','symbol':'ABC'}]
        links=[{'decision_id':'d1','event_id':'e1'}, {'decision_id':'d1','event_id':'e1'}]
        self.assertEqual(audit_decision_links(decisions,events,links)['Status'].iloc[1],'DUPLICATE_BUY_LINK')
