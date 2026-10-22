import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from tools.compare_replay_archives import compare


class ReplayIntegrityCompletionTests(unittest.TestCase):
    def archive(self, folder):
        folder.mkdir()
        summary = dict(universe='NIFTY_500', symbols=500, replay_sessions=60,
                       session='2026-10-21', qualified=0, resolved=0, successes=0,
                       stop_breaches=0, unresolved=0, certified=False)
        (folder / 'summary.json').write_text(json.dumps(summary))
        (folder / 'breakout_events.csv').write_text('Symbol,Session,Outcome\n')
        provenance = dict(outcome_horizon_sessions=10, volume_multiple=1.5,
                          lookback_signal_sessions=60)
        return provenance

    def test_missing_fingerprints_are_not_proof_of_same_snapshot(self):
        with TemporaryDirectory() as directory:
            folders = [Path(directory) / name for name in ('old', 'new')]
            for folder in folders:
                provenance = self.archive(folder)
                (folder / 'provenance.json').write_text(json.dumps(provenance))
            result = compare(*folders)
            self.assertFalse(result['same_snapshot'])
            self.assertEqual(result['archive_integrity'], 'UNVERIFIED_LEGACY')

    def test_changed_archived_outputs_are_rejected(self):
        with TemporaryDirectory() as directory:
            folders = [Path(directory) / name for name in ('old', 'new')]
            for folder in folders:
                provenance = self.archive(folder)
                provenance['artifact_sha256'] = {
                    name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                    for name in ('summary.json', 'breakout_events.csv')}
                (folder / 'provenance.json').write_text(json.dumps(provenance))
            self.assertEqual(compare(*folders)['archive_integrity'], 'VERIFIED_HASHES')
            (folders[1] / 'breakout_events.csv').write_text('tampered synthetic output')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                compare(*folders)
