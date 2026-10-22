"""Compare archived EDGE replay evidence without mixing different source snapshots.

Usage: python tools/compare_replay_archives.py old_dir new_dir
"""
import json
import sys
from pathlib import Path


def compare(old_dir, new_dir):
    old_dir, new_dir = Path(old_dir), Path(new_dir)
    old = json.loads((old_dir / "summary.json").read_text())
    new = json.loads((new_dir / "summary.json").read_text())
    a = json.loads((old_dir / "provenance.json").read_text())
    b = json.loads((new_dir / "provenance.json").read_text())
    required = ("universe", "symbols", "replay_sessions")
    if any(old.get(k) != new.get(k) for k in required):
        raise ValueError("Incompatible universe, coverage or replay window")
    parameters = ("outcome_horizon_sessions", "volume_multiple", "lookback_signal_sessions")
    if any(a.get(k) != b.get(k) for k in parameters):
        raise ValueError("Different rule parameters: comparison blocked")
    if old.get("certified") is not False or new.get("certified") is not False:
        raise ValueError("Research evidence certification flag must be false")
    # Overlapping rolling windows mean deltas are descriptive, not new trades.
    fields = ("qualified", "resolved", "successes", "stop_breaches", "unresolved")
    return {"earlier_session": old["session"], "later_session": new["session"],
            "same_snapshot": a.get("snapshot_sha256") == b.get("snapshot_sha256"),
            "research_only": True,
            "warning": "Rolling-window cohorts overlap; changes are not incremental trades or returns.",
            "changes": {key: new[key] - old[key] for key in fields}}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: compare_replay_archives.py OLD_DIR NEW_DIR")
    print(json.dumps(compare(sys.argv[1], sys.argv[2]), indent=2, sort_keys=True))
