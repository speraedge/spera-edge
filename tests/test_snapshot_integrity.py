import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from edge_core.snapshot_integrity import validate_snapshot

class SnapshotIntegrityTests(unittest.TestCase):
    def test_rejects_bad_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"metadata.json").write_text(json.dumps({"universe":"NIFTY_500","certified":False,"expected":501,"mapped":500,"retrieved":2}))
            with self.assertRaises(ValueError):
                validate_snapshot(root)

    def test_rejects_mismatched_quality_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"metadata.json").write_text(json.dumps({"universe":"NIFTY_500","certified":False,"expected":500,"mapped":500,"retrieved":500,"research_pass":0,"research_review":499,"research_fail":1}))
            pd.DataFrame({"Symbol":[f"S{i}" for i in range(500)],"Data_Quality":["REVIEW"]*500}).to_csv(root/"leadership.csv",index=False)
            with self.assertRaises(ValueError):
                validate_snapshot(root)

if __name__=="__main__":
    unittest.main()
