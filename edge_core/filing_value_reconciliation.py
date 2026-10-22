"""Compare reported financial values with independently transcribed filing values.

Transcriptions are operator supplied and never automatically certified.
Both financial and transcription identity, basis and publication date must
match before a numerical comparison is meaningful.
"""
import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


def reconcile_filing_values(financials_csv, transcriptions_csv, output_dir, document_review_csv=None):
    with Path(financials_csv).open(encoding="utf-8-sig", newline="") as stream:
        financials = list(csv.DictReader(stream))
    with Path(transcriptions_csv).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"symbol", "isin", "period_end", "period_type", "basis",
                    "source_url", "published_on", "revenue", "pat", "document_sha256"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Transcriptions missing required columns")
        transcriptions = list(reader)
    documents = defaultdict(list)
    if document_review_csv is not None:
        with Path(document_review_csv).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required_docs = {"symbol", "isin", "period_end", "period_type", "basis", "published_on", "source_url",
                             "computed_sha256", "status"}
            if not reader.fieldnames or not required_docs.issubset(reader.fieldnames):
                raise ValueError("Filing document review missing required columns")
            for document in reader:
                document_key = tuple(str(document.get(field) or "").strip().upper()
                                     for field in ("symbol", "isin", "period_end", "period_type", "basis", "source_url", "published_on"))
                documents[document_key].append(document)
    def key(record):
        return tuple(str(record.get(field) or "").strip().upper() for field in
                     ("symbol", "isin", "period_end", "period_type", "basis",
                      "source_url", "published_on"))
    index = defaultdict(list)
    for item in transcriptions:
        index[key(item)].append(item)
    rows = []
    for number, financial in enumerate(financials, 2):
        identity = key(financial)
        matches = index.get(identity, [])
        status = "MISSING_SOURCE_TRANSCRIPTION"
        if not all(identity):
            status = "INCOMPLETE_FILING_IDENTITY"
        elif len(matches) > 1:
            status = "AMBIGUOUS_SOURCE_TRANSCRIPTION"
        elif len(matches) == 1:
            item = matches[0]
            digest = str(item["document_sha256"]).strip().lower()
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                status = "INVALID_DOCUMENT_DIGEST"
            elif document_review_csv is not None and not documents.get(key(financial)):
                status = "MISSING_REVIEWED_DOCUMENT"
            elif document_review_csv is not None and (
                len(documents[key(financial)]) != 1
                or documents[key(financial)][0]["status"] != "REVIEW_ORIGINAL_DOCUMENT"
                or documents[key(financial)][0]["computed_sha256"].lower() != digest):
                status = "DOCUMENT_PROVENANCE_MISMATCH"
            else:
                try:
                    revenue_match = Decimal(str(financial["revenue"])) == Decimal(str(item["revenue"]))
                    pat_match = Decimal(str(financial["pat"])) == Decimal(str(item["pat"]))
                    values = [Decimal(str(x)) for x in
                              (financial["revenue"], item["revenue"], financial["pat"], item["pat"])]
                    if not all(x.is_finite() for x in values):
                        status = "INVALID_FINANCIAL_VALUES"
                    elif not revenue_match or not pat_match:
                        status = "SOURCE_VALUE_MISMATCH"
                    else:
                        status = "VALUES_MATCH_UNVERIFIED_TRANSCRIPTION"
                except (InvalidOperation, ValueError):
                    status = "INVALID_FINANCIAL_VALUES"
        rows.append({"row": number, "symbol": financial["symbol"], "isin": financial["isin"],
                     "period_end": financial["period_end"], "period_type": financial["period_type"],
                     "basis": financial["basis"], "published_on": financial["published_on"],
                     "source_url": financial["source_url"], "status": status,
                     "certified": False})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "filing_value_reconciliation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["row", "symbol", "isin", "period_end", "period_type", "basis",
                                                       "published_on", "source_url", "status", "certified"])
        writer.writeheader()
        writer.writerows(rows)
    result = {"rows": len(rows), "status_counts": dict(Counter(x["status"] for x in rows)),
              "independently_verified_values": 0, "certified": False}
    (out / "filing_value_reconciliation_summary.json").write_text(json.dumps(result, indent=2))
    return result
