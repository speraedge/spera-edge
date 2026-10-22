"""Fail-closed historical evidence coverage ledger for SPERA EDGE.

A downloaded file or an empty result is never evidence of complete coverage.
All dates are inclusive. Each expected month requires an explicit reviewed
source record and any gaps remain visible; no certification is granted here.
"""
import csv
import hashlib
import json
from calendar import monthrange
from datetime import date
from pathlib import Path


def months_between(start, end):
    first = date.fromisoformat(str(start))
    last = date.fromisoformat(str(end))
    if first > last:
        raise ValueError("start must not exceed end")
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month == 13:
            year, month = year + 1, 1


def audit_coverage(register_csv, start, end, output_dir):
    """Audit a source register; never infer that a zero-event month is complete.

    Required CSV columns: month, source_url, source_sha256, reviewed,
    completeness_verified. The latter is an operator assertion only, not
    independent proof. A source with no recorded events may be valid, but
    that must be explicitly reconciled outside this function.
    """
    path = Path(register_csv)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"month", "source_url", "source_sha256", "reviewed",
                    "completeness_verified"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Source register is missing required columns")
        records = list(reader)
    expected = list(months_between(start, end))
    by_month = {}
    for line, record in enumerate(records, 2):
        month = str(record["month"] or "").strip()
        if month not in expected:
            raise ValueError(f"Row {line}: month outside requested interval")
        if month in by_month:
            raise ValueError(f"Row {line}: duplicate month {month}")
        by_month[month] = record
    rows = []
    for month in expected:
        record = by_month.get(month)
        if record is None:
            status = "MISSING_SOURCE"
        elif (not str(record["source_url"]).startswith("https://")
              or len(str(record["source_sha256"]).strip()) != 64
              or any(c not in "0123456789abcdefABCDEF"
                     for c in str(record["source_sha256"]).strip())):
            status = "INVALID_SOURCE_PROVENANCE"
        elif str(record["reviewed"]).strip().lower() != "true":
            status = "NOT_REVIEWED"
        elif str(record["completeness_verified"]).strip().lower() != "true":
            status = "COVERAGE_UNVERIFIED"
        else:
            status = "REVIEW_ASSERTED_COMPLETE"
        rows.append({"month": month, "status": status,
                     "source_url": record["source_url"] if record else "",
                     "source_sha256": record["source_sha256"] if record else ""})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "historical_coverage.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["month", "status", "source_url", "source_sha256"])
        writer.writeheader()
        writer.writerows(rows)
    result = {"requested_start": str(start), "requested_end": str(end),
              "expected_months": len(expected), "registered_months": len(by_month),
              "missing_months": sum(x["status"] == "MISSING_SOURCE" for x in rows),
              "all_months_review_asserted": all(x["status"] == "REVIEW_ASSERTED_COMPLETE" for x in rows),
              "independently_verified": False, "certified": False,
              "register_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (out / "historical_coverage_summary.json").write_text(json.dumps(result, indent=2))
    return result
