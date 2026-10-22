import json
import tempfile
import unittest
from pathlib import Path
from tools.compare_replay_archives import compare


class ReplayArchiveComparisonTests(unittest.TestCase):
    def test_compatible_archives_and_overlap_warning(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a", Path(d) / "b"
            a.mkdir()
            b.mkdir()
            baseline = dict(universe="NIFTY_500", symbols=500, replay_sessions=60,
                            qualified=10, resolved=8, successes=4, stop_breaches=1,
                            unresolved=2, certified=False)
            for folder, session, count in ((a, "2026-10-20", 10), (b, "2026-10-21", 12)):
                (folder / "summary.json").write_text(json.dumps(
                    {**baseline, "session": session, "qualified": count}))
                (folder / "provenance.json").write_text(json.dumps(
                    dict(outcome_horizon_sessions=10, volume_multiple=1.5,
                         lookback_signal_sessions=60, snapshot_sha256={"close.csv": session})))
            report = compare(a, b)
            self.assertEqual(report["changes"]["qualified"], 2)
            self.assertFalse(report["same_snapshot"])
            self.assertIn("overlap", report["warning"].lower())
            provenance = json.loads((b / "provenance.json").read_text())
            provenance["volume_multiple"] = 2
            (b / "provenance.json").write_text(json.dumps(provenance))
            with self.assertRaises(ValueError):
                compare(a, b)
