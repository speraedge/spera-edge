"""Contract tests for EDGE D1 snapshot manifest; no live credentials needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.edge_snapshot_publication import publish_manifest


class PublicationContractTests(unittest.TestCase):
    def test_idempotent_publish_and_readback(self):
        saved = {}
        def fake_query(sql, params=()):
            if sql.startswith("CREATE TABLE"):
                return []
            if sql.startswith("INSERT OR IGNORE"):
                digest, session, body, published = params
                saved.setdefault(digest, body)
                return []
            if sql.startswith("SELECT manifest"):
                return [{"manifest": saved[params[0]]}]
            raise AssertionError(sql)
        fixture = {"snapshot_session": "2026-10-21", "generated_utc": "2026-10-22T02:32:56+00:00",
                   "universe": "NIFTY_500", "quality": "REVIEW", "certified": False}
        with patch("tools.edge_snapshot_publication.manifest", return_value=fixture):
            first = publish_manifest("unused", query=fake_query)
            second = publish_manifest("unused", query=fake_query)
        self.assertEqual(first, second)
        self.assertFalse(first["file_delivery"])
        self.assertFalse(first["certified"])

    def test_readback_mismatch_fails_closed(self):
        def fake_query(sql, params=()):
            if sql.startswith("SELECT"):
                return [{"manifest": "{}"}]
            return []
        with patch("tools.edge_snapshot_publication.manifest",
                   return_value={"snapshot_session": "2026-10-21", "certified": False}):
            with self.assertRaisesRegex(RuntimeError, "readback mismatch"):
                publish_manifest("unused", query=fake_query)


if __name__ == "__main__":
    unittest.main()
