"""Cloudflare D1 response-contract tests without network or credentials."""
import unittest
from unittest.mock import patch
from edge_core.d1_store import d1_query


class Response:
    def __init__(self, payload, code=200):
        self.payload, self.code = payload, code

    def raise_for_status(self):
        if self.code >= 400:
            raise RuntimeError("HTTP failure")

    def json(self):
        return self.payload


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class D1ClientContractTests(unittest.TestCase):
    def test_append_only_rejection_is_distinct_from_transport_failure(self):
        from edge_core.d1_store import D1ConstraintError
        with self.assertRaises(D1ConstraintError):
            self.query(Response({'success': False, 'result': None, 'errors': [{'message': 'Private records are append-only: SQLITE_CONSTRAINT'}]}, code=400))
        with self.assertRaises(RuntimeError) as failure:
            self.query(Response({}, code=403))
        self.assertNotIsInstance(failure.exception, D1ConstraintError)
    def query(self, response):
        session = Session(response)
        with patch.dict("os.environ", {}, clear=True):
            result = d1_query("SELECT ?", ("value",), account_id="account",
                              database_id="database", token="secret", session=session)
        return result, session

    def test_successful_parameterized_query(self):
        result, session = self.query(Response({"success": True, "result": [
            {"success": True, "results": [{"value": 1}]}]}))
        self.assertEqual(result, [{"value": 1}])
        self.assertEqual(session.calls[0][1]["json"], {"sql": "SELECT ?", "params": ["value"]})
        self.assertEqual(session.calls[0][1]["timeout"], 40)
        self.assertEqual(session.calls[0][1]["headers"]["Authorization"], "Bearer secret")

    def test_failed_query_cannot_look_like_empty_success(self):
        for payload in (
            {"success": False, "result": [{"success": False, "results": []}]},
            {"success": True, "result": []},
            {"success": True, "result": [{"success": False, "results": []}]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(RuntimeError):
                    self.query(Response(payload))

    def test_http_failure_rejected(self):
        with self.assertRaises(RuntimeError):
            self.query(Response({}, code=403))

    def test_missing_credentials_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "credentials"):
                d1_query("SELECT 1")


if __name__ == "__main__":
    unittest.main()
