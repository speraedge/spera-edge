"""Private Screener.in quarterly import and evidence-based acceleration gate.

Never writes public CSV. Excel is untrusted input. Use explicit symbol and owner
hash; no guessing ticker from filename or company name.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import pandas as pd
from edge_core.d1_store import d1_query
from edge_core.manual_fundamentals import SYMBOL

QUARTERLY_SQL = """CREATE TABLE IF NOT EXISTS edge_screener_quarters (
 owner_id TEXT NOT NULL, symbol TEXT NOT NULL, quarter_end TEXT NOT NULL,
 revenue REAL NOT NULL, eps REAL NOT NULL, source TEXT NOT NULL,
 imported_utc TEXT NOT NULL, PRIMARY KEY(owner_id,symbol,quarter_end))"""
GATE_SQL = """CREATE TABLE IF NOT EXISTS edge_fundamental_acceleration (
 owner_id TEXT NOT NULL, symbol TEXT NOT NULL, latest_quarter TEXT NOT NULL,
 status TEXT NOT NULL, metrics_json TEXT NOT NULL, updated_utc TEXT NOT NULL,
 PRIMARY KEY(owner_id,symbol))"""
DATE_PATTERN = re.compile(r"^(?:[A-Za-z]{3}[- ]?\d{2,4}|\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})$")


def _quarter(value):
    if isinstance(value, (pd.Timestamp, datetime)):
        d = pd.Timestamp(value).date()
    else:
        text = str(value).strip()
        if not DATE_PATTERN.fullmatch(text):
            return None
        try:
            d = pd.to_datetime(text, dayfirst=not text[:4].isdigit()).date()
            if re.fullmatch(r"[A-Za-z]{3}[- ]?\\d{2,4}", text):
                d = (pd.Timestamp(d) + pd.offsets.MonthEnd(0)).date()
        except (ValueError, TypeError):
            return None
    if d.month not in (3, 6, 9, 12) or d.day not in (30, 31):
        return None
    return d.isoformat()


def _number(value):
    if value is None or pd.isna(value) or isinstance(value, bool):
        raise ValueError("Missing or invalid financial value")
    text = str(value).strip().replace(",", "")
    if text in ("", "-", "--", "N/A", "nan"):
        raise ValueError("Missing quarterly financial value")
    try:
        n = float(text)
    except ValueError as exc:
        raise ValueError("Nonnumeric quarterly financial value") from exc
    if not math.isfinite(n):
        raise ValueError("Nonfinite quarterly financial value")
    return n


def parse_screener_excel(path, *, sheet=None):
    """Accept Screener-style wide Quarters sheet with dated columns and row labels.

    Requires explicit Sales/Revenue and EPS rows; refuses mixed or ambiguous
    sheets, TTM columns and non-quarterly headers.
    """
    path = Path(path)
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        raise ValueError("An .xlsx or .xlsm workbook is required")
    book = pd.ExcelFile(path, engine="openpyxl")
    selected = sheet or next((name for name in book.sheet_names if name.strip().lower() in
                              ("quarters", "quarterly results", "quarterly")), None)
    if selected is None or selected not in book.sheet_names:
        raise ValueError("Quarterly sheet not found; specify --sheet")
    raw = pd.read_excel(book, sheet_name=selected, header=None)
    candidates = []
    for header_idx in range(min(len(raw), 35)):
        header = raw.iloc[header_idx].tolist()
        dates = [(i, _quarter(v)) for i, v in enumerate(header)]
        dates = [(i, d) for i, d in dates if d is not None]
        if len(dates) >= 6:
            candidates.append((header_idx, dates))
    if len(candidates) != 1:
        raise ValueError("Ambiguous or missing quarterly date header")
    header_idx, dates = candidates[0]
    periods = [d for _, d in dates]
    if len(set(periods)) != len(periods):
        raise ValueError("Duplicate quarterly dates")
    labels = {}
    for i in range(header_idx + 1, len(raw)):
        label = str(raw.iat[i, 0]).strip().lower()
        if re.fullmatch(r"(sales|sales \+|revenue|revenue \+|sales / revenue)", label):
            labels.setdefault("revenue", []).append(i)
        if re.fullmatch(r"(eps|eps in rs|eps in rs\.|eps in ₹|eps \(rs\.?\))", label):
            labels.setdefault("eps", []).append(i)
    if any(len(labels.get(key, [])) != 1 for key in ("revenue", "eps")):
        raise ValueError("Exactly one quarterly Sales/Revenue row and EPS row required")
    rows = []
    for col, date in dates:
        revenue = _number(raw.iat[labels["revenue"][0], col])
        eps = _number(raw.iat[labels["eps"][0], col])
        if revenue < 0:
            raise ValueError("Quarterly revenue cannot be negative")
        rows.append({"quarter_end": date, "revenue": revenue, "eps": eps})
    rows.sort(key=lambda row: row["quarter_end"])
    dates_sorted = [pd.Timestamp(row["quarter_end"]) for row in rows]
    for previous, current in zip(dates_sorted, dates_sorted[1:]):
        if current != previous + pd.offsets.QuarterEnd(1):
            raise ValueError("Nonconsecutive quarters; acceleration not certified")
    return rows


def _growth(current, previous):
    # Negative or zero base makes a positive percentage growth interpretation
    # misleading; report unknown, not an invented acceleration.
    if previous <= 0:
        return None
    return round((current / previous - 1) * 100, 4)


def calculate_acceleration(rows):
    if len(rows) < 7:
        return {"status": "INSUFFICIENT_HISTORY", "metrics": {}}
    rows = sorted(rows, key=lambda x: x["quarter_end"])
    metrics = {}
    for key in ("revenue", "eps"):
        values = [float(r[key]) for r in rows]
        qoq = [_growth(values[i], values[i - 1]) for i in range(len(values) - 3, len(values))]
        yoy = [_growth(values[i], values[i - 4]) for i in range(len(values) - 3, len(values))]
        metrics[key] = {"qoq_growth_pct": qoq, "yoy_growth_pct": yoy,
                        "qoq_accelerating": all(x is not None for x in qoq) and qoq[0] < qoq[1] < qoq[2],
                        "yoy_accelerating": all(x is not None for x in yoy) and yoy[0] < yoy[1] < yoy[2]}
    if any(None in metrics[key][kind] for key in metrics for kind in ("qoq_growth_pct", "yoy_growth_pct")):
        status = "REVIEW_NONPOSITIVE_BASE"
    elif all(metrics[key][kind] for key in metrics for kind in ("qoq_accelerating", "yoy_accelerating")):
        status = "PASS"
    else:
        status = "FAIL"
    return {"status": status, "metrics": metrics}


def import_workbook(path, symbol, owner, *, query=d1_query, sheet=None, dry_run=False):
    if not SYMBOL.fullmatch(symbol):
        raise ValueError("Explicit valid NSE symbol required")
    if not re.fullmatch(r"[a-f0-9]{64}", owner):
        raise ValueError("Verified owner hash required; never use email as D1 owner_id")
    rows = parse_screener_excel(path, sheet=sheet)
    result = calculate_acceleration(rows)
    if dry_run:
        return {"symbol": symbol, "quarters": len(rows), **result}
    # Complete validation before any D1 write. Each quarter is owner-scoped.
    query(QUARTERLY_SQL)
    query(GATE_SQL)
    stamp = datetime.now(timezone.utc).isoformat()
    for row in rows:
        query("""INSERT INTO edge_screener_quarters
                 (owner_id,symbol,quarter_end,revenue,eps,source,imported_utc)
                 VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner_id,symbol,quarter_end)
                 DO UPDATE SET revenue=excluded.revenue,eps=excluded.eps,
                   source=excluded.source,imported_utc=excluded.imported_utc""",
              (owner, symbol, row["quarter_end"], row["revenue"], row["eps"], "SCREENER_MANUAL_EXCEL", stamp))
    query("""INSERT INTO edge_fundamental_acceleration
             (owner_id,symbol,latest_quarter,status,metrics_json,updated_utc)
             VALUES(?,?,?,?,?,?) ON CONFLICT(owner_id,symbol) DO UPDATE SET
             latest_quarter=excluded.latest_quarter,status=excluded.status,
             metrics_json=excluded.metrics_json,updated_utc=excluded.updated_utc""",
          (owner, symbol, rows[-1]["quarter_end"], result["status"],
           json.dumps(result["metrics"], allow_nan=False), stamp))
    return {"symbol": symbol, "quarters": len(rows), **result}


def main():
    parser = argparse.ArgumentParser(description="Import private Screener.in quarterly workbook into EDGE D1")
    parser.add_argument("excel")
    parser.add_argument("--symbol", required=True, help="Verified NSE symbol, not inferred from workbook")
    parser.add_argument("--owner-id", required=True, help="64-char owner hash from authenticated EDGE identity")
    parser.add_argument("--sheet")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = import_workbook(args.excel, args.symbol.strip().upper(), args.owner_id,
                             sheet=args.sheet, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
