"""Cross-module shortlist-to-filing-audit smoke tests; no external network."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tools.shortlist_financial_audit import run_shortlist_financial_audit
from edge_core.acquisition_review_import import import_acquisition_review, validate_acquisition_import
from edge_core.financial_evidence_ledger import FinancialEvidenceLedger

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

    def test_acquisition_to_append_only_ledger_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_shortlist_financial_audit(
                [C], [F], [R], "2026-09-30", Path(tmp),
                transcriptions=[], session=Session(200))
            expected = hashlib.sha256(b"%PDF-1.4\\nsynthetic fixture\\n").hexdigest()
            self.assertEqual(result["review"][0]["document_sha256"], expected)
            self.assertEqual(result["review"][0]["source_url"], F["source_url"])
            self.assertEqual(result["review"][0]["acquisition_status"], "ACQUIRED_UNVERIFIED")
            self.assertEqual(result["review"][0]["reconciliation_status"], "REVIEW_REQUIRED")
            self.assertFalse(result["review"][0]["financial_values_verified"])
            self.assertFalse(result["review"][0]["ready_for_trading_signals"])
            self.assertIn("document_status", result["review"][0]["reconciliation"])
            self.assertIn("value_status", result["review"][0]["reconciliation"])
            queue = [{key: R[key] for key in (
                "symbol", "isin", "period_end", "period_type", "basis")}]
            self.assertEqual(validate_acquisition_import(result, queue)[0]["document_sha256"], expected)
            db = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
            def query(sql, params=()):
                cursor = db.execute(sql, params)
                rows = [dict(row) for row in cursor] if cursor.description else []
                db.commit()
                return rows
            ledger = FinancialEvidenceLedger("test-owner", query)
            ledger.initialize()
            first = import_acquisition_review(ledger, queue, result)
            self.assertEqual(first, import_acquisition_review(ledger, queue, result))
            self.assertEqual(len(ledger.events()), 1)
            self.assertEqual(ledger.events()[0]["intake_status"], "REVIEW_REQUIRED")
            self.assertEqual(db.execute("SELECT source_sha256 FROM edge_financial_evidence_events").fetchone()[0], expected)
            db.close()

    def test_distinct_company_evidence_cannot_cross_match(self):
        """An identical period must not allow one issuer's transcription to pass another."""
        second = {"symbol": "DEF", "isin": "INE000B01002"}
        second_filing = {**F, **second,
                         "source_url": "https://nsearchives.nseindia.com/def.pdf"}
        second_financial = {**R, **second,
                            "source_url": second_filing["source_url"], "revenue": "200"}
        digest = hashlib.sha256(b"%PDF-1.4\\nsynthetic fixture\\n").hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            result = run_shortlist_financial_audit(
                [C, second], [F, second_filing], [R, second_financial],
                "2026-09-30", Path(tmp),
                transcriptions=[
                    {**R, "document_sha256": digest},
                    {**second_financial, "revenue": "201", "document_sha256": digest},
                ], session=Session(200))
        reviews = {row["symbol"]: row for row in result["review"]}
        self.assertEqual(reviews["ABC"]["reconciliation"].get("value_status"),
                         "VALUES_MATCH_UNVERIFIED_TRANSCRIPTION", reviews)
        self.assertEqual(reviews["DEF"]["reconciliation"].get("value_status"),
                         "SOURCE_VALUE_MISMATCH", reviews)
        for row in reviews.values():
            self.assertEqual(row["reconciliation"]["identity_status"],
                             "FULL_IDENTITY_VERIFIED")
            self.assertFalse(row["certified"])
            self.assertFalse(row["ready_for_trading_signals"])

    def test_multi_company_mixed_sources_stay_quarantined(self):
        second = {"symbol": "DEF", "isin": "INE000B01002"}
        third = {"symbol": "GHI", "isin": "INE000C01003"}
        fourth = {"symbol": "JKL", "isin": "INE000D01004"}
        candidates = [C, second, third, fourth]
        filings = [F, {**F, **second, "source_url": "https://nsearchives.nseindia.com/def.pdf"},
                   {**F, **third, "source_url": "https://nsearchives.nseindia.com/ghi.pdf"}]
        records = [{**R, **candidate} for candidate in candidates]
        class MixedSession:
            def get(self, url, **kwargs):
                self_kwargs = kwargs
                assert self_kwargs["allow_redirects"] is False
                return Response(403 if url.endswith("/def.pdf") else 200)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_shortlist_financial_audit(
                candidates, filings, records, "2026-09-30", Path(tmp),
                transcriptions=[], session=MixedSession())
            statuses = {x["symbol"]: x["acquisition_status"] for x in result["review"]}
            self.assertEqual(statuses, {
                "ABC": "ACQUIRED_UNVERIFIED", "DEF": "HTTP_403",
                "GHI": "ACQUIRED_UNVERIFIED", "JKL": "SOURCE_NOT_FOUND"})
            queue = [{k: record[k] for k in (
                "symbol", "isin", "period_end", "period_type", "basis")}
                for record in records]
            checked = validate_acquisition_import(result, queue)
            self.assertEqual(len(checked), 4)
            self.assertTrue(all(not x["certified"] for x in result["review"]))
            self.assertFalse(result["ready_for_trading_signals"])
            with self.assertRaises(ValueError):
                validate_acquisition_import({**result, "review": [
                    *result["review"][:1], {**result["review"][1], "isin": "WRONG"},
                    *result["review"][2:]]}, queue)
            with self.assertRaises(ValueError):
                validate_acquisition_import({**result, "review": [
                    *result["review"][:1], {**result["review"][1], "certified": True},
                    *result["review"][2:]]}, queue)

    def test_multi_company_import_is_idempotent_and_owner_isolated(self):
        candidates = [C, {"symbol": "DEF", "isin": "INE000B01002"}]
        filings = [F, {**F, **candidates[1],
                       "source_url": "https://nsearchives.nseindia.com/def.pdf"}]
        records = [{**R, **candidate} for candidate in candidates]
        class MixedSession:
            def get(self, url, **kwargs):
                assert kwargs["allow_redirects"] is False
                return Response(403 if url.endswith("/def.pdf") else 200)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_shortlist_financial_audit(
                candidates, filings, records, "2026-09-30", Path(tmp),
                transcriptions=[], session=MixedSession())
            queue = [{k: record[k] for k in (
                "symbol", "isin", "period_end", "period_type", "basis")}
                for record in records]
            db = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
            def query(sql, params=()):
                cursor = db.execute(sql, params)
                rows = [dict(row) for row in cursor] if cursor.description else []
                db.commit()
                return rows
            owner = FinancialEvidenceLedger("owner-one", query)
            owner.initialize()
            first = import_acquisition_review(owner, queue, result)
            self.assertEqual(len(first), 2)
            self.assertEqual(first, import_acquisition_review(owner, queue, result))
            self.assertEqual(len(owner.events()), 2)
            self.assertEqual(FinancialEvidenceLedger("owner-two", query).events(), [])
            self.assertTrue(all(x["intake_status"] == "REVIEW_REQUIRED" for x in owner.events()))
            with self.assertRaises(sqlite3.DatabaseError):
                query("DELETE FROM edge_financial_evidence_events WHERE owner_id=?",
                      ("owner-one",))
            self.assertEqual(len(owner.events()), 2)
            db.close()

    def test_pdf_acquisition_still_uncertified(self):
        result = self.run_case([F], transcriptions=[], code=200)
        self.assertEqual(result["status_counts"], {"ACQUIRED_UNVERIFIED": 1})
        self.assertFalse(result["audit"]["certified"])


if __name__ == "__main__":
    unittest.main()
