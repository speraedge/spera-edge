"""Local BSE quarterly fundamentals using dalal; no private data or exchange bypass.

Place nifty_500_mapping.csv in data/latest/ (or repository root), with a verified
Symbol and BSE Scrip Code column. Run: python tools/fetch_fundamentals_local.py
"""
import csv
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from edge_core.fundamentals_privacy import COLUMNS, publish_public_csv, validate_public_csv

MEMBERSHIP = ROOT / "data/latest/current_membership.csv"
OUTPUT = ROOT / "data/latest/fundamentals_auto.csv"
MAPPING_PATHS = [ROOT / "data/latest/nifty_500_mapping.csv",
                 ROOT / "nifty_500_mapping.csv",
                 ROOT / "data/latest/bse_mapping.csv"]
CODE_RE = re.compile(r"^[0-9]{5,7}$")
MONTHS = {name: n for n, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def number(value):
    try:
        result = float(str(value).replace(",", "").strip())
        if not __import__("math").isfinite(result):
            return ""
        return result
    except (ValueError, TypeError):
        return ""


def quarter_end(label):
    match = re.fullmatch(r"([A-Za-z]{3})[- ](\d{2}|\d{4})", str(label).strip())
    if not match or match.group(1).title() not in MONTHS:
        raise ValueError("Unknown quarterly period")
    year = int(match.group(2))
    if year < 100:
        year += 2000
    month = MONTHS[match.group(1).title()]
    import calendar
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def mapping_from_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        def pick(names):
            return next((h for h in headers if re.sub(r"[^a-z0-9]", "", h.lower()) in names), None)
        symbol_key = pick({"symbol", "nsesymbol", "nseticker"})
        code_key = pick({"bsescripcode", "bsescrip", "bsecode", "scripcode", "scripcd"})
        if not symbol_key or not code_key:
            raise ValueError(f"Mapping needs Symbol and BSE Scrip Code columns; found {headers}")
        found, ambiguous = {}, set()
        for item in reader:
            symbol = str(item.get(symbol_key) or "").strip().upper()
            code = str(item.get(code_key) or "").strip()
            if not symbol or not CODE_RE.fullmatch(code):
                continue
            if symbol in found and found[symbol] != code:
                ambiguous.add(symbol)
            found[symbol] = code
        for symbol in ambiguous:
            found.pop(symbol, None)
        return found


def extract(payload):
    if not isinstance(payload, dict):
        raise ValueError("Unexpected dalal response")
    period = quarter_end(payload.get("col2"))
    entries = payload.get("resultinCr")
    if not isinstance(entries, list):
        raise ValueError("Missing crore-denominated quarterly table")
    titles = {str(item.get("title", "")).strip().lower(): item for item in entries if isinstance(item, dict)}
    revenue = number((titles.get("revenue") or {}).get("v1"))
    pat = number((titles.get("net profit") or {}).get("v1"))
    eps = number((titles.get("eps") or {}).get("v1"))
    if any(x == "" for x in (revenue, pat, eps)):
        raise ValueError("Incomplete latest-quarter Revenue, PAT or EPS")
    return {"Quarter_Revenue": revenue, "Quarter_PAT": pat,
            "Quarter_EPS": eps, "Quarter_End": period,
            "Source": "BSE", "Status": "AUTO"}


def main(fetch=None, sleep=time.sleep):
    if not MEMBERSHIP.is_file():
        raise SystemExit(f"Missing official membership: {MEMBERSHIP}")
    mapping_file = next((p for p in MAPPING_PATHS if p.is_file()), None)
    if mapping_file is None:
        raise SystemExit("Missing nifty_500_mapping.csv. Place it in data/latest/ before running.")
    mapping = mapping_from_csv(mapping_file)
    if not mapping:
        raise SystemExit("No verified BSE codes in mapping")
    with MEMBERSHIP.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if "Symbol" not in (reader.fieldnames or []):
            raise SystemExit("Official membership requires Symbol column")
        symbols = [r["Symbol"].strip().upper() for r in reader]
    if len(set(symbols)) != len(symbols) or not symbols:
        raise SystemExit("Official membership contains duplicates or is empty")
    if fetch is None:
        import dalal
        fetch = dalal.fundamentals
    rows = []
    errors = {}
    for i, symbol in enumerate(symbols):
        row = dict.fromkeys(COLUMNS, "")
        row.update(Symbol=symbol, Source="NONE", Status="AUTO_FAILED")
        code = mapping.get(symbol)
        if code:
            try:
                row.update(extract(fetch(code)))
            except Exception as exc:
                kind = type(exc).__name__
                errors[kind] = errors.get(kind, 0) + 1
            sleep(1.0)
        rows.append(row)
        if (i + 1) % 50 == 0:
            print(f"Processed {i+1}/{len(symbols)}; verified {sum(r['Status']=='AUTO' for r in rows)}", flush=True)
    verified = sum(r["Status"] == "AUTO" for r in rows)
    if not verified:
        raise SystemExit(f"0 verified records; errors={errors}. Existing CSV preserved; do NOT upload.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        backup = Path(directory) / "previous.csv"
        if OUTPUT.exists():
            validate_public_csv(OUTPUT)
            shutil.copy2(OUTPUT, backup)
        try:
            publish_public_csv(rows, OUTPUT)
            validate_public_csv(OUTPUT)
        except Exception:
            if backup.exists():
                shutil.copy2(backup, OUTPUT)
            else:
                OUTPUT.unlink(missing_ok=True)
            raise
    print(f"SUCCESS: {verified}/{len(rows)} verified BSE quarterly records saved to {OUTPUT}")
    print(f"Missing mapping: {sum(s not in mapping for s in symbols)}; errors: {errors}")
    print("P/E and Market_Cap intentionally blank; dalal response does not establish them.")


if __name__ == "__main__":
    main()
