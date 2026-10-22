"""Audit an existing EDGE snapshot without altering data or issuing trade signals.

Usage: python tools/audit_edge_snapshot.py --directory data/latest
Writes machine-readable JSON to stdout. Exit status 1 means invalid data.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from edge_core.snapshot_integrity import validate_snapshot
from edge_core.ohlcv_integrity import audit_ohlcv


def audit(directory):
    root = Path(directory)
    baseline = validate_snapshot(root)
    meta = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    frames = {
        name: pd.read_csv(root / (name + ".csv"), index_col="Date")
        for name in ("close", "high", "low", "volume")
    }
    candle = audit_ohlcv(**frames, expected_last_session=meta["last_session"])
    return {"status": "RESEARCH_INTEGRITY_PASS", "directory": str(root),
            "last_session": meta["last_session"],
            "baseline": baseline, "ohlcv": candle,
            "certified": False,
            "missing_acceptance": ["Independent corporate-action adjustments",
                                   "Historical point-in-time membership",
                                   "Provider freshness and official-source provenance"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="data/latest")
    args = parser.parse_args()
    try:
        result = audit(args.directory)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc), "certified": False}))
        raise SystemExit(1)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
