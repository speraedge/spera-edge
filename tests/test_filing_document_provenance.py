"""Test local filing document identity and digest verification."""
import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from edge_core.filing_document_provenance import audit_filing_documents


class FilingDocumentTests(unittest.TestCase):
    def test_digest_and_missing_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            payload = b"%PDF-1.4\nsynthetic filing bytes for unit test"
            (docs / "report.pdf").write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            register = root / "register.csv"
            with register.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["symbol", "isin", "period_end", "basis", "source_url",
                                 "document_filename", "expected_sha256"])
                writer.writerow(["ABC", "INE000A01001", "2026-03-31", "CONSOLIDATED",
                                 "https://nsearchives.nseindia.com/filing.pdf", "report.pdf", digest])
                writer.writerow(["XYZ", "INE000B01001", "2026-03-31", "CONSOLIDATED",
                                 "https://nsearchives.nseindia.com/missing.pdf", "missing.pdf", digest])
            summary = audit_filing_documents(register, docs, root / "out")
            self.assertEqual(summary["status_counts"]["REVIEW_ORIGINAL_DOCUMENT"], 1)
            self.assertEqual(summary["status_counts"]["MISSING_LOCAL_DOCUMENT"], 1)
            self.assertFalse(summary["certified"])

    def test_reject_untrusted_url_and_non_pdf_even_if_digest_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"not a pdf"
            (root / "report.pdf").write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            register = root / "register.csv"
            register.write_text(
                "symbol,isin,period_end,basis,source_url,document_filename,expected_sha256\n"
                "ABC,INE000A01001,2026-03-31,CONSOLIDATED,https://nsearchives.nseindia.com/report.pdf,report.pdf,"
                + digest + "\n")
            summary = audit_filing_documents(register, root, root / "out")
            self.assertEqual(summary["status_counts"]["INVALID_PDF_DOCUMENT"], 1)
            register.write_text(
                "symbol,isin,period_end,basis,source_url,document_filename,expected_sha256\\n"
                "ABC,INE000A01001,2026-03-31,CONSOLIDATED,https://example.org/report.pdf,report.pdf,"
                + digest + "\\n")
            summary = audit_filing_documents(register, root, root / "out")
            self.assertEqual(summary["status_counts"]["INVALID_OFFICIAL_SOURCE_URL"], 1)

    def test_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.pdf").write_bytes(b"wrong")
            register = root / "register.csv"
            register.write_text("symbol,isin,period_end,basis,source_url,document_filename,expected_sha256\nABC,INE000A01001,2026-03-31,CONSOLIDATED,https://nsearchives.nseindia.com/filing.pdf,report.pdf," + "a" * 64 + "\n")
            summary = audit_filing_documents(register, root, root / "out")
            self.assertEqual(summary["status_counts"]["DOCUMENT_HASH_MISMATCH"], 1)
