import base64
import gzip
import json
import tempfile
import unittest
from tools.import_spera_history import decode_blob,import_history,query

class HistoryBridgeTests(unittest.TestCase):
    def test_select_only(self):
        with self.assertRaises(ValueError):
            query("DELETE FROM weekly_snapshots",account="x",database="y",token="z")
    def test_decode_source_format(self):
        blob=base64.b64encode(gzip.compress(json.dumps({"columns":["Pure_Momentum_Rank"],"data":[[1]]}).encode())).decode()
        self.assertEqual(decode_blob([{"data":blob}]).iloc[0,0],1)
    def test_import_trusted_only(self):
        meta={"display_state":"READY","snapshot_freshness":"PASS","session_authority":"PASS",
              "corporate_action_authority":"PASS","snapshot_is_expected_session":True,"pass_count":3}
        blob=base64.b64encode(gzip.compress(json.dumps({"columns":["Symbol","Pure_Momentum_Rank"],"data":[["AAA",1]]}).encode())).decode()
        def reader(sql,params):
            if "FROM weekly_snapshots" in sql:
                return [{"weekly_key":"2026-10-16","commit_id":"abc","meta_json":json.dumps(meta),"freshness":"PASS","source":"LIVE"}]
            return [{"data":blob}]
        with tempfile.TemporaryDirectory() as d:
            result=import_history(d,reader=reader)
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]["rows"],1)

if __name__=="__main__":
    unittest.main()
