import unittest
from edge_core.portfolio_risk import risk_budget

class PortfolioRiskTests(unittest.TestCase):
    def test_available_budget(self):
        result = risk_budget(500000, 1, 22000, 5)
        self.assertEqual(result["new_trade_budget"], 3000)
        self.assertEqual(result["portfolio_ceiling"], 25000)

    def test_full_portfolio(self):
        self.assertEqual(risk_budget(500000, 1, 25000)["new_trade_budget"], 0)

    def test_invalid_input(self):
        for committed in (-1, float("nan")):
            with self.assertRaises(ValueError):
                risk_budget(500000, 1, committed)

if __name__ == "__main__":
    unittest.main()
