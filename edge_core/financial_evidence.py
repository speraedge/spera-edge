"""Financial evidence source audit; no automatic certification."""

import csv
import hashlib
from pathlib import Path


def inspect_source(path):
    source = Path(path)
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"symbol", "isin", "period_end", "period_type", "basis", "source_url"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Financial source is missing required columns")
        records = list(reader)
    return {"rows": len(records), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "certified": False}
