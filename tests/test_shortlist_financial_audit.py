"""Cross-module shortlist-to-filing-audit smoke tests; no external network."""
import tempfile
import unittest
from pathlib import Path
from tools.shortlist_financial_audit import run_shortlist_financial_audit

C = {"symbol": "ABC", "isin": "INE000A01001"}
F = {**C, "period_end": "2026-09-30", "period_type": "Q",
     "basis": "CONSOLIDATED", "published_on": "2026-10-20",
     "source_url": "https://nsearchives.nseindia.com/abc.pdf"}
R = {**F, "revenue": "100", "pat": "10"}


class Response:
    def __init__(self, code):
        self.status_code = code
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size=65536):
        yield b"%PDF-1.4\\nsynthetic fixture\\n"


class Session:
    def __init__(self, code):
        self.code = code
    def get(self, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        return Response(self.code)


class ShortlistAuditTests(unittest.TestCase):
    def run_case(self, filings, transcriptions=None, code=200):
        with tempfile.TemporaryDirectory() as tmp:
            return run_shortlist_financial_audit(
                [C], filings, [R], "2026-09-30", Path(tmp),
                transcriptions=transcriptions, session=Session(code))

    def test_no_source_remains_review(self):
        result = self.run_case([])
        self.assertEqual(result["status_counts"], {"SOURCE_NOT_FOUND": 1})
        self.assertFalse(result["certified"])

    def test_ambiguous_source_is_not_acquired(self):
        result = self.run_case([F, F])
        self.assertEqual(result["status_counts"], {"AMBIGUOUS_SOURCE": 1})
        self.assertIsNone(result["audit"])

    def test_explicit_source_requires_transcription_for_full_audit(self):
        result = self.run_case([F])
        self.assertEqual(result["registered"], 1)
        self.assertIsNone(result["audit"])
        self.assertFalse(result["ready_for_trading_signals"])

    def test_http_403_remains_review(self):
        result = self.run_case([F], transcriptions=[], code=403)
        self.assertEqual(result["status_counts"], {"HTTP_403": 1})
        self.assertFalse(result["certified"])

    def test_pdf_acquisition_still_uncertified(self):
        result = self.run_case([F], transcriptions=[], code=200)
        self.assertEqual(result["status_counts"], {"ACQUIRED_UNVERIFIED": 1})
        self.assertFalse(result["audit"]["certified"])


if __name__ == "__main__":
    unittest.main()
