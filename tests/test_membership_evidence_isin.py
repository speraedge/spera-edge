import unittest
from unittest.mock import patch, Mock
import pandas as pd
from tempfile import TemporaryDirectory
from pathlib import Path
from edge_evidence import publish


class MembershipEvidenceIdentityTests(unittest.TestCase):
    @patch("edge_evidence.fetch_official_universe")
    def test_missing_isin_fails_closed(self, fetch):
        universe = pd.DataFrame({"Symbol": ["ABC"], "Industry": ["Industrial"]})
        universe.attrs["universe_source_url"] = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        fetch.return_value = (universe, "Industry")
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "missing ISIN"):
                publish(directory)

    @patch("edge_evidence.fetch_official_universe")
    def test_duplicate_isin_fails_closed(self, fetch):
        universe = pd.DataFrame({"Symbol": ["ABC", "DEF"], "Industry": ["Industrial"] * 2,
                                 "ISIN Code": ["INE000A01001"] * 2})
        universe.attrs["universe_source_url"] = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        fetch.return_value = (universe, "Industry")
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "duplicate ISIN"):
                publish(directory)


if __name__ == "__main__":
    unittest.main()
