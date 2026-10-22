"""SPERA EDGE corporate-action evidence triage. No automatic price adjustment.

Adapted conceptually from the read-only SPERA corporate-action source register
and reconciliation approach. Input must be an independently sourced CSV.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def _date(value):
    value = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def review_events(events_csv, output_dir, universe_symbols):
    """Build immutable-source provenance and exception ledger, never approved factors."""
    source = Path(events_csv)
    raw = source.read_bytes()
    with source.open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    identities = ({str(k).strip().upper(): str(v).strip().upper() for k, v in universe_symbols.items()}\n                  if hasattr(universe_symbols, "items") else None)\n    universe = set(identities) if identities is not None else {str(x).strip().upper() for x in universe_symbols}
    findings = []
    seen = defaultdict(list)
    for number, record in enumerate(records, start=2):
        symbol = str(record.get("symbol") or record.get("SYMBOL") or "").strip().upper()
        purpose = str(record.get("purpose") or record.get("PURPOSE") or "").strip()
        ex_date = _date(record.get("ex_date") or record.get("EX-DATE"))
        isin = str(record.get("isin") or record.get("ISIN") or "").strip().upper()
        url = str(record.get("source_url") or "").strip()
        status = "REVIEW_OFFICIAL_TERMS"
        if not symbol or not purpose or not ex_date:
            status = "INVALID_EVENT_FIELDS"
        elif symbol not in universe:
            status = "OUTSIDE_CURRENT_UNIVERSE_REVIEW"
        elif identities is not None and isin and identities.get(symbol) != isin:\n            status = "ISIN_MISMATCH_REVIEW"\n        elif not url.startswith("https://"):
            status = "MISSING_OFFICIAL_SOURCE"
        elif any(word in purpose.lower() for word in ("cancel", "withdraw", "revok")):
            status = "CANCELLED_EVENT"
        elif not isin:
            status = "MISSING_ISIN_REVIEW"
        if symbol and ex_date:
            seen[(symbol, ex_date)].append(number)
        findings.append({"row": number, "symbol": symbol, "isin": isin,
                         "purpose": purpose, "ex_date": ex_date or "",
                         "source_url": url, "status": status,
                         "approved": False, "adjustment_factor": ""})
    for finding in findings:
        key = (finding["symbol"], finding["ex_date"])
        if key[0] and key[1] and len(seen[key]) > 1 and finding["status"] == "REVIEW_OFFICIAL_TERMS":
            finding["status"] = "MULTIPLE_EVENTS_SAME_DATE_REVIEW"
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "corporate_action_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(findings[0]) if findings else
                                ["row", "symbol", "isin", "purpose", "ex_date", "source_url",
                                 "status", "approved", "adjustment_factor"])
        writer.writeheader()
        writer.writerows(findings)
    summary = {"source_sha256": hashlib.sha256(raw).hexdigest(),
               "source_filename": source.name, "source_rows": len(records),
               "status_counts": dict(Counter(x["status"] for x in findings)),
               "approved_factors": 0, "adjusted_prices_ready": False,
               "complete_historical_coverage": False,
               "note": "Source review only. No adjustment or SEPA certification authorized."}
    (destination / "corporate_action_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
