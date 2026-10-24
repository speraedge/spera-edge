"""Build BSE scrip-code mapping by exact ISIN from a BSE equity Bhavcopy.

Usage:
 python tools/build_bse_bhavcopy_mapping.py
 python tools/build_bse_bhavcopy_mapping.py --manual data/manual/EQ_ISINCODE_DDMMYY.zip
"""
import argparse
import csv
import io
import re
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "data/latest/nifty_500_mapping.csv"
OUTPUT = ROOT / "data/latest/bse_mapping.csv"
BASE = "https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_{date}.zip"


def key(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def rows_from_csv(blob):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            content = blob.decode(encoding)
            reader = csv.DictReader(io.StringIO(content))
            if not reader.fieldnames:
                raise ValueError("Missing CSV header")
            yield list(reader), reader.fieldnames
            return
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV encoding unsupported")


def parse_bhavcopy(blob):
    if zipfile.is_zipfile(io.BytesIO(blob)):
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            files = [n for n in archive.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX")]
            if len(files) != 1:
                raise ValueError(f"Expected one CSV inside BSE ZIP; found {files}")
            blob = archive.read(files[0])
    for records, headers in rows_from_csv(blob):
        lookup = {key(h): h for h in headers}
        code_field = next((lookup[x] for x in ("sccode", "scripcode", "scripcd", "fininstrmid") if x in lookup), None)
        isin_field = next((lookup[x] for x in ("isincode", "isin") if x in lookup), None)
        if not code_field or not isin_field:
            raise ValueError(f"Bhavcopy missing BSE code and ISIN columns: {headers}")
        udiff = "fininstrmid" in lookup
        result = {}
        for record in records:
            if udiff:
                segment = str(record.get(lookup.get("sgmt", ""), "")).strip().upper()
                instrument = str(record.get(lookup.get("fininstrmtp", ""), "")).strip().upper()
                source = str(record.get(lookup.get("src", ""), "")).strip().upper()
                if segment != "CM" or instrument != "STK" or source != "BSE":
                    continue
            isin = str(record.get(isin_field) or "").strip().upper()
            code = str(record.get(code_field) or "").strip()
            if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin) and re.fullmatch(r"[0-9]{5,7}", code):
                result.setdefault(isin, set()).add(code)
        if not result:
            raise ValueError("No valid BSE ISIN/code pairs")
        return result


def load_identity(path=IDENTITY):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = {key(h): h for h in reader.fieldnames or []}
        symbol_field = headers.get("symbol")
        isin_field = headers.get("isin") or headers.get("isincode")
        if not symbol_field or not isin_field:
            raise ValueError("Identity CSV needs Symbol and ISIN")
        items = []
        for row in reader:
            symbol = str(row.get(symbol_field) or "").strip().upper()
            isin = str(row.get(isin_field) or "").strip().upper()
            if symbol:
                items.append((symbol, isin))
        if not items or len({x[0] for x in items}) != len(items):
            raise ValueError("Identity CSV empty or has duplicate symbols")
        return items


def match(identity, bhavcopy):
    output = []
    used = {}
    for symbol, isin in identity:
        codes = bhavcopy.get(isin, set())
        if len(codes) != 1:
            continue
        code = next(iter(codes))
        if code in used and used[code] != isin:
            raise ValueError("BSE code maps to conflicting ISINs")
        used[code] = isin
        output.append({"Symbol": symbol, "ISIN": isin, "bse_scripcode": code})
    return output


def download_latest(days=10, today=None):
    today = today or date.today()
    errors = []
    for offset in range(1, days + 1):
        day = today - timedelta(days=offset)
        url = BASE.format(date=day.strftime("%d%m%y"))
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/zip"})
            with urllib.request.urlopen(request, timeout=20) as response:
                blob = response.read(30_000_001)
            if len(blob) > 30_000_000:
                raise ValueError("Archive too large")
            parse_bhavcopy(blob)
            return blob, url
        except (urllib.error.URLError, TimeoutError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(f"{day.isoformat()}: {type(exc).__name__}")
    raise RuntimeError("No usable Bhavcopy found; " + ", ".join(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual", type=Path, help="Local Bhavcopy ZIP or CSV (no network)")
    args = parser.parse_args()
    identity = load_identity()
    if args.manual:
        blob = args.manual.read_bytes()
        source = str(args.manual)
    else:
        try:
            blob, source = download_latest()
        except RuntimeError as exc:
            raise SystemExit(str(exc) + "\nDownload a Bhavcopy ZIP in your browser and rerun with --manual data/manual/FILENAME.zip")
    matched = match(identity, parse_bhavcopy(blob))
    if not matched:
        raise SystemExit("No ISIN matches; existing BSE mapping preserved")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Symbol", "ISIN", "bse_scripcode"])
        writer.writeheader()
        writer.writerows(matched)
    temporary.replace(OUTPUT)
    print(f"SUCCESS: {len(matched)}/{len(identity)} BSE mappings from {source}")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
