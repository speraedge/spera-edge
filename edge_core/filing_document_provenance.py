"""Audit a local register of original financial filing documents.

Files are operator supplied. Hashes prove byte identity only, not authenticity.
This does not fetch filings or certify their financial figures.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def audit_filing_documents(register_csv, documents_dir, output_dir):
    source = Path(register_csv)
    documents = Path(documents_dir).resolve()
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"symbol", "isin", "period_end", "basis", "source_url",
                    "document_filename", "expected_sha256"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Filing register missing required columns")
        records = list(reader)
    findings = []
    seen = set()
    for number, item in enumerate(records, 2):
        name = str(item["document_filename"] or "").strip()
        expected = str(item["expected_sha256"] or "").strip().lower()
        key = (item["isin"], item["period_end"], item["basis"])
        status = "REVIEW_ORIGINAL_DOCUMENT"
        digest = ""
        if key in seen:
            status = "DUPLICATE_FILING_IDENTITY"
        elif not str(item["source_url"]).startswith("https://"):
            status = "MISSING_SOURCE_URL"
        elif not name or Path(name).name != name or name in (".", ".."):
            status = "INVALID_DOCUMENT_FILENAME"
        elif len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            status = "INVALID_EXPECTED_SHA256"
        else:
            file = (documents / name).resolve()
            if not file.is_relative_to(documents) or not file.is_file():
                status = "MISSING_LOCAL_DOCUMENT"
            else:
                digest = hashlib.sha256(file.read_bytes()).hexdigest()
                if digest != expected:
                    status = "DOCUMENT_HASH_MISMATCH"
        seen.add(key)
        findings.append({"row": number, "symbol": item["symbol"], "isin": item["isin"],
                         "period_end": item["period_end"], "basis": item["basis"],
                         "source_url": item["source_url"], "document_filename": name,
                         "computed_sha256": digest, "status": status, "certified": False})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fields = ["row", "symbol", "isin", "period_end", "basis", "source_url",
              "document_filename", "computed_sha256", "status", "certified"]
    with (out / "filing_document_review.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(findings)
    summary = {"documents": len(findings), "status_counts": dict(Counter(x["status"] for x in findings)),
               "original_document_authenticity_verified": False,
               "financial_values_reconciled_to_documents": False, "certified": False,
               "register_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    (out / "filing_document_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
