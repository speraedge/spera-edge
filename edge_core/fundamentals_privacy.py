"""Strict public auto-fundamentals CSV contract. No manual indicators or values."""
import csv
import math
from pathlib import Path

COLUMNS = ("Symbol", "PE", "Market_Cap", "Quarter_Revenue", "Quarter_PAT",
           "Quarter_EPS", "Quarter_End", "Source", "Status")
NUMERIC = ("PE", "Market_Cap", "Quarter_Revenue", "Quarter_PAT", "Quarter_EPS")


def validate_public_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("FUNDAMENTALS_PRIVACY_GATE: unexpected CSV columns")
        seen = set()
        for row in reader:
            symbol = row["Symbol"]
            if None in row or not symbol or not symbol.isascii() or not all(
                    c.isalnum() or c in ".-&" for c in symbol) or symbol in seen:
                raise ValueError("FUNDAMENTALS_PRIVACY_GATE: invalid identity")
            seen.add(symbol)
            if row["Status"] not in ("AUTO", "AUTO_FAILED") or row["Source"] not in ("NSE", "BSE", "NONE"):
                raise ValueError("FUNDAMENTALS_PRIVACY_GATE: invalid status/source")
            if row["Status"] == "AUTO_FAILED" and any(row[k] for k in (*NUMERIC, "Quarter_End")):
                raise ValueError("FUNDAMENTALS_PRIVACY_GATE: failed row contains values")
            for key in NUMERIC:
                if row[key] and not math.isfinite(float(row[key])):
                    raise ValueError("FUNDAMENTALS_PRIVACY_GATE: invalid number")
    return True


def publish_public_csv(rows, path):
    """Construct an allowlisted CSV; reject extra fields instead of dropping them."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="raise")
            writer.writeheader()
            for row in rows:
                if set(row) != set(COLUMNS):
                    raise ValueError("FUNDAMENTALS_PRIVACY_GATE: private/unknown field")
                writer.writerow(row)
        validate_public_csv(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
