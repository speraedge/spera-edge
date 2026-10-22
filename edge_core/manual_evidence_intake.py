"""Offline evidence intake for SPERA EDGE review queue.

Produces quarantined CSV candidates, never a certified record. No network access
or production D1 writes. Source documents must be checked independently.
"""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

COLUMNS = ("symbol", "isin", "period_end", "period_type", "basis",
           "revenue", "pat", "published_on", "source_url")
OUT_COLUMNS = COLUMNS + ("intake_status", "intake_reason", "certified")


def _valid_url(value):
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def review_intake(queue, submissions):
    """Validate identities and fields against a generated review queue.

    Queue entries must come from build_queue, not from arbitrary operator symbols.
    """
    expected = {}
    for item in queue:
        key = tuple(str(item.get(k, "")).strip().upper() for k in COLUMNS[:5])
        if key in expected:
            raise ValueError("Duplicate queue identity")
        expected[key] = item
    output = []
    seen = set()
    for item in submissions:
        key = tuple(str(item.get(k, "")).strip().upper() for k in COLUMNS[:5])
        reasons = []
        if key in seen:
            reasons.append("DUPLICATE_SUBMISSION")
        seen.add(key)
        if key not in expected:
            reasons.append("NOT_IN_REVIEW_QUEUE")
        for field in COLUMNS:
            if not str(item.get(field, "")).strip():
                reasons.append("MISSING_" + field.upper())
        try:
            period = date.fromisoformat(str(item.get("period_end", "")))
            published = date.fromisoformat(str(item.get("published_on", "")))
            if published < period:
                reasons.append("PUBLICATION_BEFORE_PERIOD_END")
        except ValueError:
            reasons.append("INVALID_DATE")
        if item.get("period_type") not in ("Q", "FY") or item.get("basis") not in ("CONSOLIDATED", "STANDALONE"):
            reasons.append("INVALID_PERIOD_OR_BASIS")
        for field in ("revenue", "pat"):
            try:
                value = Decimal(str(item.get(field, "")))
                if not value.is_finite() or (field == "revenue" and value < 0):
                    reasons.append("INVALID_" + field.upper())
            except InvalidOperation:
                reasons.append("INVALID_" + field.upper())
        if not _valid_url(str(item.get("source_url", ""))):
            reasons.append("INVALID_SOURCE_URL")
        result = {name: str(item.get(name, "")).strip() for name in COLUMNS}
        result.update(intake_status="REJECTED" if reasons else "QUARANTINED_UNVERIFIED",
                      intake_reason=";".join(dict.fromkeys(reasons)), certified="false")
        output.append(result)
    return output


def review_csv(queue_csv, submission_csv, output_csv):
    with Path(queue_csv).open(newline="", encoding="utf-8-sig") as stream:
        queue = list(csv.DictReader(stream))
    with Path(submission_csv).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
            raise ValueError("Missing intake columns")
        submissions = list(reader)
    findings = review_intake(queue, submissions)
    destination = Path(output_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        writer.writerows(findings)
    return findings
