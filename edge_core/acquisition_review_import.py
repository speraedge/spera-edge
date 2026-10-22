"""Strict offline validator for importing acquisition outcomes into private review.

Reject the entire batch on an invalid or unmatched record; never silently
drop evidence or promote a certification flag.
"""
from datetime import date
from edge_core.financial_evidence_ledger import FinancialEvidenceLedger
from tools.acquire_official_filings import validate_url

KEYS = ("symbol", "isin", "period_end", "period_type", "basis")
ALLOWED = frozenset(("SOURCE_NOT_FOUND", "AMBIGUOUS_SOURCE",
    "INVALID_PUBLICATION_DATE", "INVALID_SOURCE_METADATA",
    "ACQUISITION_PENDING_UNVERIFIED", "ACQUIRED_UNVERIFIED",
    "HTTP_403", "HTTP_429", "HTTP_ERROR", "DOWNLOAD_ERROR",
    "INVALID_PDF", "TOO_LARGE", "REVIEW_REQUIRED"))


def validate_acquisition_import(payload, queue):
    if not isinstance(payload, dict) or payload.get("certified") is not False:
        raise ValueError("Acquisition review must explicitly be uncertified")
    if payload.get("ready_for_trading_signals", False) is not False:
        raise ValueError("Trading signal readiness is forbidden")
    outcomes = payload.get("review", payload.get("decisions"))
    if not isinstance(outcomes, list) or not 0 < len(outcomes) <= 1000:
        raise ValueError("Invalid acquisition review count")
    allowed = {tuple(str(q.get(k, "")).strip().upper() for k in KEYS) for q in queue}
    if len(allowed) != len(queue):
        raise ValueError("Duplicate review queue identity")
    seen = set()
    checked = []
    for item in outcomes:
        if not isinstance(item, dict):
            raise ValueError("Invalid acquisition review record")
        key = tuple(str(item.get(k, "")).strip().upper() for k in KEYS)
        if key not in allowed:
            raise ValueError("Acquisition identity outside current owner queue")
        if key in seen:
            raise ValueError("Duplicate acquisition identity")
        seen.add(key)
        if item.get("certified") is not False or item.get("ready_for_trading_signals", False) is not False:
            raise ValueError("Certification claim in acquisition outcome")
        if str(item.get("acquisition_status", "")).strip().upper() not in ALLOWED:
            raise ValueError("Invalid acquisition outcome status")
        status = str(item["acquisition_status"]).strip().upper()
        if status == "ACQUIRED_UNVERIFIED":
            try:
                validate_url(str(item.get("source_url", "")))
            except (ValueError, TypeError) as exc:
                raise ValueError("Acquired evidence requires an official HTTPS source") from exc
            digest = item.get("document_sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(
                char not in "0123456789abcdefABCDEF" for char in digest
            ):
                raise ValueError("Acquired evidence requires a valid SHA256 digest")
            published = item.get("published_on")
            if not isinstance(published, str):
                raise ValueError("Acquired evidence requires a publication date")
            try:
                publication_date = date.fromisoformat(published)
                period_date = date.fromisoformat(str(item["period_end"]))
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid acquired evidence date") from exc
            if publication_date < period_date or publication_date > date.today():
                raise ValueError("Publication date outside valid period")
        checked.append({**{k: v for k, v in zip(KEYS, key)},
                        "acquisition_status": str(item["acquisition_status"]).strip().upper(),
                        "source_url": str(item.get("source_url", "")).strip(),
                        "published_on": str(item.get("published_on", "")).strip(),
                        "document_sha256": str(item.get("document_sha256", "")).strip()})
    return checked


def import_acquisition_review(ledger: FinancialEvidenceLedger, queue, payload, *,
                              event_ids=None):
    """Prevalidate all records before any append; deterministic IDs support replay."""
    import hashlib
    import json
    checked = validate_acquisition_import(payload, queue)
    if event_ids is not None and len(event_ids) != len(checked):
        raise ValueError("Incorrect event ID count")
    written = []
    for index, item in enumerate(checked):
        event_id = (event_ids[index] if event_ids is not None else
                    hashlib.sha256((ledger.owner + ":" +
                        json.dumps(item, sort_keys=True)).encode()).hexdigest())
        written.append(ledger.append_reconciliation(queue, item, event_id=event_id))
    return written
