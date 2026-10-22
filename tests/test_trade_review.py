import unittest
from edge_core.trade_review import journal_quality

class JournalQualityTests(unittest.TestCase):
    def test_entry_note_check(self):
        result = journal_quality([{'symbol':'AAA','kind':'BUY','note':''}, {'symbol':'BBB','kind':'BUY','note':'Reviewed'}]).set_index('Symbol')
        self.assertEqual(result.loc['AAA','Review_Status'], 'REVIEW_NEEDED')
        self.assertEqual(result.loc['BBB','Review_Status'], 'DOCUMENTED_BUYS')
    def test_empty(self):
        self.assertTrue(journal_quality([]).empty)
