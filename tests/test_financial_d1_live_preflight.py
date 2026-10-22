import os
import unittest
from unittest.mock import patch

from tools.verify_financial_d1_live import verify_live


class FinancialD1LivePreflightTests(unittest.TestCase):
    def test_missing_credentials_prevents_any_live_query(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("tools.verify_financial_d1_live.d1_query") as query:
                with self.assertRaisesRegex(RuntimeError, "credentials required"):
                    verify_live()
                query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
