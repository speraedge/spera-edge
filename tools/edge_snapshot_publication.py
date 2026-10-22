"""Fail-closed EDGE snapshot publication manifest in independent Cloudflare D1.

The database stores provenance and content hashes, not raw market history.
The dashboard continues reading validated files; this does NOT deploy files.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from edge_core.snapshot_integrity import validate_snapshot
from edge_core.d1_store import d1_query

FILES = ("metadata.json", "leadership.csv", "close.csv", "high.csv", "low.csv", "volume.csv")


def manifest(directory):
    root = Path(directory)
    validated = validate_snapshot(root)
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in FILES}
    return {
        "snapshot_session": metadata["last_session"],
        "generated_utc": metadata["generated_utc"],
        "universe": metadata["universe"],
        "retrieved": validated["retrieved"],
        "quality": metadata["quality"],
        "certified": False,
        "sha256": hashes,
    }


def publish_manifest(directory, query=d1_query):
    record = manifest(directory)
    digest = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    query("""CREATE TABLE IF NOT EXISTS edge_snapshot_publications (
        digest TEXT PRIMARY KEY, session TEXT NOT NULL, manifest TEXT NOT NULL,
        published_utc TEXT NOT NULL)""")
    query("INSERT OR IGNORE INTO edge_snapshot_publications (digest, session, manifest, published_utc) VALUES (?, ?, ?, ?)",
          (digest, record["snapshot_session"], json.dumps(record, sort_keys=True),
           datetime.now(timezone.utc).isoformat()))
    rows = query("SELECT manifest FROM edge_snapshot_publications WHERE digest=?", (digest,))
    if len(rows) != 1 or json.loads(rows[0]["manifest"]) != record:
        raise RuntimeError("EDGE D1 publication readback mismatch")
    return {"status": "VERIFIED_MANIFEST", "digest": digest, "session": record["snapshot_session"],
            "file_delivery": False, "certified": False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="data/latest")
    parser.add_argument("--publish", action="store_true",
                        help="Explicitly write and verify manifest in independent EDGE D1")
    args = parser.parse_args()
    result = publish_manifest(args.directory) if args.publish else manifest(args.directory)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
