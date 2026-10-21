import unittest
from edge_core.portfolio import position_size, journal_entry

class PortfolioTests(unittest.TestCase):
    def test_position_sizing(self):
        result=position_size(500000,1,100,95)
        self.assertEqual(result["quantity"],1000)
        self.assertEqual(result["planned_risk"],5000)
    def test_invalid_stop(self):
        with self.assertRaises(ValueError):
            journal_entry("ABC","LONG",100,105,10,"bad")
    def test_journal_entry(self):
        row=journal_entry("abc","LONG",100,95,10,"test")
        self.assertEqual(row["Risk_Rupees"],50)
        self.assertEqual(row["Symbol"],"ABC")

if __name__=="__main__":
    unittest.main()
