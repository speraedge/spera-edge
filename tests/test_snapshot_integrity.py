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
            (root/"metadata.json").write_text(json.dumps({"universe":"NIFTY_TOTAL_MARKET","certified":False,"expected":750,"mapped":750,"retrieved":2}))
            with self.assertRaises(ValueError):
                validate_snapshot(root)

    def test_rejects_mismatched_quality_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"metadata.json").write_text(json.dumps({"universe":"NIFTY_TOTAL_MARKET","certified":False,"expected":750,"mapped":750,"retrieved":750,"research_pass":0,"research_review":749,"research_fail":1}))
            pd.DataFrame({"Symbol":[f"S{i}" for i in range(750)],"Data_Quality":["REVIEW"]*750}).to_csv(root/"leadership.csv",index=False)
            with self.assertRaises(ValueError):
                validate_snapshot(root)

if __name__=="__main__":
    unittest.main()
