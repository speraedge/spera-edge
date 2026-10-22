"""Fail-closed bridge from technical candidates to an explicit official filing register.

Discovery is NOT implied: URLs must come from a separately sourced, auditable
register. No downloaded file or register entry constitutes certification.
"""
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from edge_core.manual_evidence_queue import build_queue
from tools.acquire_official_filings import validate_url

FIELDS = ("symbol", "isin", "period_end", "period_type", "basis", "source_url", "published_on")
REGISTER_FIELDS = ("symbol", "isin", "period_end", "source_url", "period_type", "basis", "published_on")


def prepare_official_acquisition(shortlist, filings, financial_records, expected_period_end,
                                 output_dir, *, period_type="Q", basis="CONSOLIDATED"):
    """Generate exact-match acquisition register and review cases; never certify.

    filings: externally obtained official filing references, not inferred URLs.
    Every ambiguous match is blocked. Missing source becomes a review request.
    """
    date.fromisoformat(expected_period_end)
    if period_type not in ("Q", "FY") or basis not in ("CONSOLIDATED", "STANDALONE"):
        raise ValueError("Unsupported financial period or basis")
    queue = build_queue(shortlist, financial_records, expected_period_end, period_type, basis)
    indexed = defaultdict(list)
    for filing in filings:
        key = tuple(str(filing.get(k, "")).strip().upper() for k in
                    ("symbol", "isin", "period_end", "period_type", "basis"))
        indexed[key].append(filing)
    register, decisions = [], []
    for item in queue:
        key = tuple(str(item[k]).strip().upper() for k in
                    ("symbol", "isin", "period_end", "period_type", "basis"))
        matches = indexed.get(key, [])
        status = "SOURCE_NOT_FOUND"
        if len(matches) > 1:
            status = "AMBIGUOUS_SOURCE"
        elif len(matches) == 1:
            candidate = matches[0]
            try:
                url = validate_url(candidate.get("source_url", ""))
                published = date.fromisoformat(str(candidate.get("published_on", "")))
                if published < date.fromisoformat(expected_period_end):
                    status = "INVALID_PUBLICATION_DATE"
                else:
                    record = {k: str(candidate.get(k, "")).strip() for k in REGISTER_FIELDS}
                    record.update(symbol=item["symbol"], isin=item["isin"],
                                  period_end=expected_period_end, period_type=period_type,
                                  basis=basis, source_url=url)
                    register.append(record)
                    status = "ACQUISITION_PENDING_UNVERIFIED"
            except (ValueError, TypeError):
                status = "INVALID_SOURCE_METADATA"
        decisions.append({**item, "acquisition_status": status, "certified": False})
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "official_acquisition_register.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTER_FIELDS)
        writer.writeheader()
        writer.writerows(register)
    with (destination / "official_acquisition_review.json").open("w", encoding="utf-8") as f:
        json.dump({"decisions": decisions, "certified": False,
                   "ready_for_trading_signals": False}, f, indent=2)
    return {"registered": len(register), "review": decisions, "certified": False}
