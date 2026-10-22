import unittest
from edge_core.decision_links import validate_trade_link

class DecisionLinkTests(unittest.TestCase):
    def setUp(self):
        self.decisions=[{'decision_id':'d1','decision':'TAKE','symbol':'ABC'}]
        self.events=[{'event_id':'e1','kind':'BUY','symbol':'ABC'}]
    def test_valid_explicit_link(self):
        self.assertEqual(validate_trade_link(self.decisions,self.events,'d1','e1')['symbol'],'ABC')
    def test_wrong_symbol_rejected(self):
        self.events[0]['symbol']='XYZ'
        with self.assertRaises(ValueError):
            validate_trade_link(self.decisions,self.events,'d1','e1')
    def test_no_implicit_trade(self):
        with self.assertRaises(ValueError):
            validate_trade_link(self.decisions,[],'d1','e1')
    def test_rejected_setup_cannot_link(self):
        self.decisions[0]['decision']='REJECT'
        with self.assertRaises(ValueError):
            validate_trade_link(self.decisions,self.events,'d1','e1')
