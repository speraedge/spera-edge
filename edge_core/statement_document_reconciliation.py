"""Join financial statement records to locally hashed filing evidence.

The join is intentionally conservative: one exact statement/document match
is required. A matching digest does not certify issuer authenticity or values.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def reconcile_statement_documents(financials_csv, document_review_csv, output_dir):
    with Path(financials_csv).open(encoding="utf-8-sig", newline="") as stream:
        financials = list(csv.DictReader(stream))
    with Path(document_review_csv).open(encoding="utf-8-sig", newline="") as stream:
        documents = list(csv.DictReader(stream))
    index = defaultdict(list)
    for doc in documents:
        key = (str(doc["symbol"]).strip().upper(), str(doc["isin"]).strip().upper(),
               str(doc["period_end"]).strip(), str(doc.get("period_type", "")).strip().upper(),
               str(doc["basis"]).strip().upper(), str(doc.get("published_on", "")).strip(),
               str(doc["source_url"]).strip())
        index[key].append(doc)
    findings = []
    for number, record in enumerate(financials, 2):
        key = (str(record["symbol"]).strip().upper(), str(record["isin"]).strip().upper(),
               str(record["period_end"]).strip(), str(record.get("period_type", "")).strip().upper(),
               str(record["basis"]).strip().upper(), str(record.get("published_on", "")).strip(),
               str(record["source_url"]).strip())
        matches = index.get(key, [])
        if not matches:
            status = "MISSING_MATCHING_FILING"
        elif len(matches) != 1:
            status = "AMBIGUOUS_FILING_MATCH"
        elif matches[0]["status"] != "REVIEW_ORIGINAL_DOCUMENT":
            status = "FILING_DOCUMENT_UNRESOLVED"
        else:
            status = "MATCHED_DOCUMENT_UNCERTIFIED"
        findings.append({"row": number, "symbol": key[0], "isin": key[1],
                         "period_end": key[2], "period_type": key[3], "basis": key[4],
                         "published_on": key[5], "source_url": key[6],
                         "document_status": status, "certified": False})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fields = ["row", "symbol", "isin", "period_end", "period_type", "basis", "published_on", "source_url",
              "document_status", "certified"]
    with (out / "statement_document_reconciliation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(findings)
    summary = {"financial_rows": len(findings),
               "status_counts": dict(Counter(x["document_status"] for x in findings)),
               "verified_financial_values": 0, "certified": False}
    (out / "statement_document_reconciliation_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
