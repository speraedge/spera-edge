"""Official filing acquisition tests use no external network."""
import csv
import tempfile
import unittest
from pathlib import Path
from tools.acquire_official_filings import acquire, validate_url


class FakeResponse:
    status_code = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size):
        yield b"%PDF-1.4\n"
        yield b"test"


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()


class AcquisitionTests(unittest.TestCase):
    def test_official_host_only(self):
        with self.assertRaises(ValueError):
            validate_url("https://nseindia.com.evil.example/filing.pdf")
        with self.assertRaises(ValueError):
            validate_url("http://www.nseindia.com/filing.pdf")
        self.assertEqual(validate_url("https://www.nseindia.com/filing.pdf"),
                         "https://www.nseindia.com/filing.pdf")

    def test_pdf_acquisition_is_hashed_but_not_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            register = root / "register.csv"
            with register.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["symbol", "isin", "period_end", "source_url"])
                writer.writerow(["ABC", "INE000A01001", "2026-03-31",
                                 "https://www.nseindia.com/filing.pdf"])
            result = acquire(register, root / "out", session=FakeSession())
            self.assertEqual(result["documents"][0]["status"], "ACQUIRED_UNVERIFIED")
            self.assertEqual(len(result["documents"][0]["sha256"]), 64)
            self.assertFalse(result["certified"])
            self.assertTrue((root / "out" / result["documents"][0]["file"]).exists())
