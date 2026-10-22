"""Deterministic evidence requests for technically shortlisted symbols.

Pure research utility. Never certifies an observation or changes frozen V1.
"""
import csv
import math
from datetime import date
from pathlib import Path

REQUIRED = ("revenue", "pat", "published_on", "source_url")
FIELDS = ("symbol", "isin", "period_end", "period_type", "basis",
          "missing_fields", "reason", "status")


def build_queue(shortlist, financial_records, expected_period_end, period_type="Q",
                basis="CONSOLIDATED"):
    """Return review requests only where required financial fields are absent.

    Inputs are mappings. A complete record is not automatically verified:
    this module does not infer source authenticity or promote PASS.
    """
    date.fromisoformat(expected_period_end)
    if period_type not in ("Q", "FY") or basis not in ("CONSOLIDATED", "STANDALONE"):
        raise ValueError("Unsupported reporting period or basis")
    def present(record, field):
        value = record.get(field)
        if value is None or isinstance(value, bool):
            return False
        if isinstance(value, (float, int)):
            return math.isfinite(value)
        text = str(value).strip()
        return bool(text) and text.lower() not in ("nan", "none", "null", "nat", "inf", "-inf")

    index = {}
    for record in financial_records:
        key = (str(record.get("isin", "")).strip().upper(),
               str(record.get("period_end", "")).strip(),
               str(record.get("period_type", "")).strip().upper(),
               str(record.get("basis", "")).strip().upper())
        index.setdefault(key, []).append(record)
    output = []
    seen = set()
    for item in shortlist:
        symbol = str(item.get("symbol", "")).strip().upper()
        isin = str(item.get("isin", "")).strip().upper()
        if not symbol or not isin:
            raise ValueError("Shortlist needs symbol and ISIN")
        if (symbol, isin) in seen:
            continue
        seen.add((symbol, isin))
        matches = index.get((isin, expected_period_end, period_type, basis), [])
        if len(matches) == 1:
            record = matches[0]
            missing = [field for field in REQUIRED if not present(record, field)]
            reason = "MISSING_FIELDS" if missing else "SOURCE_VERIFICATION_REQUIRED"
        elif len(matches) > 1:
            missing = []
            reason = "DUPLICATE_OR_CONFLICTING_PERIOD"
        else:
            missing = list(REQUIRED)
            reason = "MISSING_PERIOD"
        # All records remain reviewable until the separate independent audit approves.
        output.append(dict(symbol=symbol, isin=isin, period_end=expected_period_end,
                           period_type=period_type, basis=basis,
                           missing_fields=";".join(missing), reason=reason,
                           status="MANUAL_REVIEW_REQUIRED"))
    return output


def write_queue(path, queue):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(queue)
