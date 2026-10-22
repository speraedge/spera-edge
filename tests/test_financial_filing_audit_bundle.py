import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.financial_filing_audit_bundle import run_bundle


class FakeResponse:
    status_code = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size=65536):
        yield b"%PDF-1.4\nsynthetic fixture\n"


class FakeSession:
    def get(self, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        return FakeResponse()


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class BundleTests(unittest.TestCase):
    def test_acquisition_to_value_audit_is_uncertified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = dict(symbol="ABC", isin="INE000A01001",
                        period_end="2026-09-30", period_type="Q",
                        basis="CONSOLIDATED",
                        source_url="https://nsearchives.nseindia.com/example.pdf",
                        published_on="2026-10-20", revenue="100", pat="10")
            register = root / "register.csv"
            financials = root / "financials.csv"
            transcriptions = root / "transcriptions.csv"
            write_csv(register, ["symbol", "isin", "period_end", "basis", "source_url"], [base])
            write_csv(financials, list(base), [base])
            transcription = dict(base, document_sha256=hashlib.sha256(
                b"%PDF-1.4\nsynthetic fixture\n").hexdigest())
            write_csv(transcriptions, list(transcription), [transcription])
            result = run_bundle(register, financials, transcriptions,
                                root / "output", session=FakeSession())
            self.assertEqual(result["acquisition"]["ACQUIRED_UNVERIFIED"], 1)
            self.assertEqual(result["value_reconciliation"][
                "VALUES_MATCH_UNVERIFIED_TRANSCRIPTION"], 1)
            self.assertFalse(result["certified"])
            self.assertFalse(result["ready_for_trading_signals"])
            self.assertTrue((root / "output" / "bundle_summary.json").exists())

    def test_blocked_download_does_not_certify(self):
        class Denied(FakeSession):
            def get(self, url, **kwargs):
                class Blocked(FakeResponse):
                    status_code = 403
                return Blocked()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = dict(symbol="ABC", isin="INE000A01001",
                        period_end="2026-09-30", period_type="Q",
                        basis="CONSOLIDATED",
                        source_url="https://nsearchives.nseindia.com/blocked.pdf",
                        published_on="2026-10-20", revenue="100", pat="10")
            register = root / "register.csv"
            financials = root / "financials.csv"
            transcriptions = root / "transcriptions.csv"
            write_csv(register, ["symbol", "isin", "period_end", "basis", "source_url"], [base])
            write_csv(financials, list(base), [base])
            write_csv(transcriptions, list(base) + ["document_sha256"],
                      [dict(base, document_sha256="")])
            result = run_bundle(register, financials, transcriptions,
                                root / "output", session=Denied())
            self.assertEqual(result["acquisition"]["HTTP_403"], 1)
            self.assertEqual(result["value_reconciliation"]["INVALID_DOCUMENT_DIGEST"], 1)
            self.assertFalse(result["certified"])


if __name__ == "__main__":
    unittest.main()
