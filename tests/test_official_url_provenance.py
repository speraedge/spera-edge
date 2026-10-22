"""Reject ambiguous official filing URL provenance."""
import unittest
from tools.acquire_official_filings import validate_url


class OfficialUrlProvenanceTests(unittest.TestCase):
    def test_exact_official_url(self):
        self.assertEqual(validate_url("https://nsearchives.nseindia.com/a.pdf"),
                         "https://nsearchives.nseindia.com/a.pdf")

    def test_fragment_and_untrusted_authority_rejected(self):
        for url in ("https://nsearchives.nseindia.com/a.pdf#other",
                    "https://nsearchives.nseindia.com:443/a.pdf",
                    "https://nsearchives.nseindia.com@evil.example/a.pdf",
                    "http://nsearchives.nseindia.com/a.pdf"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)


if __name__ == "__main__":
    unittest.main()
