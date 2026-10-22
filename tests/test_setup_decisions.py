import unittest
from edge_core.setup_decisions import validate_decision

class DecisionTests(unittest.TestCase):
    def test_valid(self):
        x=validate_decision('abc','2026-10-21','REJECT','RISK','Position limit reached')
        self.assertEqual(x['symbol'],'ABC')
    def test_rationale_required(self):
        with self.assertRaises(ValueError):
            validate_decision('ABC','2026-10-21','TAKE','RISK',' ')
    def test_unknown_decision(self):
        with self.assertRaises(ValueError):
            validate_decision('ABC','2026-10-21','UNKNOWN','RISK','Reason')
