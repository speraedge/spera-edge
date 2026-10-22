"""Financial statement evidence review; no automatic certification."""
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = {"symbol", "isin", "period_end", "period_type", "basis",
          "revenue", "pat", "source_url", "published_on"}

def inspect_source(path):
    source = Path(path)
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError("Financial source is missing required columns")
        records = list(reader)
    return {"rows": len(records),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "certified": False}

def review_financials(path, destination, symbol_to_isin):
    """Inspect source records; never infer growth from mismatched periods."""
    summary = inspect_source(path)
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.DictReader(stream))
    identity = {str(k).upper(): str(v).upper() for k, v in symbol_to_isin.items()}
    findings = []
    seen = set()
    for line, record in enumerate(records, 2):
        symbol = str(record["symbol"] or "").strip().upper()
        isin = str(record["isin"] or "").strip().upper()
        basis = str(record["basis"] or "").strip().upper()
        period_type = str(record["period_type"] or "").strip().upper()
        key = (isin, record["period_end"], period_type, basis)
        status = "REVIEW_SOURCE_AND_COMPARABILITY"
        try:
            period = date.fromisoformat(str(record["period_end"]))
            published = date.fromisoformat(str(record["published_on"]))
            revenue = Decimal(str(record["revenue"]))
            pat = Decimal(str(record["pat"]))
            if not revenue.is_finite() or not pat.is_finite() or revenue < 0:
                status = "INVALID_FINANCIAL_VALUES"
            elif published < period:
                status = "INVALID_PUBLICATION_DATE"
        except (ValueError, InvalidOperation, TypeError):
            status = "INVALID_DATES_OR_VALUES"
        if symbol not in identity or identity[symbol] != isin:
            status = "IDENTITY_MISMATCH"
        elif period_type not in ("FY", "Q") or basis not in ("CONSOLIDATED", "STANDALONE"):
            status = "INVALID_REPORTING_BASIS"
        elif not str(record["source_url"] or "").startswith("https://"):
            status = "MISSING_SOURCE"
        elif key in seen and status == "REVIEW_SOURCE_AND_COMPARABILITY":
            status = "DUPLICATE_PERIOD_REVIEW"
        seen.add(key)
        findings.append({"row": line, "symbol": symbol, "isin": isin,
                         "period_end": record["period_end"], "period_type": period_type,
                         "basis": basis, "status": status, "certified": False})
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    columns = ["row", "symbol", "isin", "period_end", "period_type", "basis", "status", "certified"]
    with (out / "financial_evidence_review.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(findings)
    summary.update({"status_counts": dict(Counter(x["status"] for x in findings)),
                    "certified_rows": 0, "growth_ready": False})
    (out / "financial_evidence_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
