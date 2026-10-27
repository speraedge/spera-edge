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
PAT_SQL = """CREATE TABLE IF NOT EXISTS edge_screener_quarter_pat (
 owner_id TEXT NOT NULL, symbol TEXT NOT NULL, quarter_end TEXT NOT NULL,
 revenue REAL NOT NULL, net_profit REAL, source TEXT NOT NULL,
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
            if re.fullmatch(r"[A-Za-z]{3}[- ]?[0-9]{4}", text):
                normalized = text.replace("-", " ")
                d = (pd.Timestamp(datetime.strptime(normalized, "%b %Y")) + pd.offsets.MonthEnd(0)).date()
            else:
                d = pd.to_datetime(text, dayfirst=not text[:4].isdigit()).date()
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
    """Parse Screener's Data Sheet quarterly Report Date/Sales/Net profit block.

    Never substitute PAT for EPS. If EPS is absent, retain PAT evidence and
    mark the EPS component unavailable, rather than inventing a per-share value.
    """
    path = Path(path)
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        raise ValueError("An .xlsx or .xlsm workbook is required")
    book = pd.ExcelFile(path, engine="openpyxl")
    selected = sheet or next((name for name in book.sheet_names if name.strip().lower()
                              == "data sheet"), None)
    if selected is None or selected not in book.sheet_names:
        raise ValueError("Quarterly Data Sheet not found")
    raw = pd.read_excel(book, sheet_name=selected, header=None, engine="openpyxl")
    candidates = []
    for idx in range(len(raw)):
        label = str(raw.iat[idx, 0]).strip().lower()
        if selected.strip().lower() == "data sheet" and label != "report date":
            continue
        dates = [(col, _quarter(raw.iat[idx, col])) for col in range(1, min(raw.shape[1], 11))]
        dates = [(col, date) for col, date in dates if date is not None]
        if len(dates) >= 6:
            candidates.append((idx, dates))
    if len(candidates) != 1:
        raise ValueError("Ambiguous or missing Report Date quarterly header")
    idx, dates = candidates[0]
    if len({d for _, d in dates}) != len(dates):
        raise ValueError("Duplicate quarterly dates")
    # Stop at next section header: do not mix annual or balance-sheet metrics.
    end = len(raw)
    for i in range(idx + 1, len(raw)):
        label = str(raw.iat[i, 0]).strip().lower()
        if label == "report date":
            end = i
            break
    labels = {}
    for i in range(idx + 1, end):
        label = str(raw.iat[i, 0]).strip().lower()
        if label in ("sales", "sales +", "revenue", "revenue +", "sales / revenue"):
            labels.setdefault("revenue", []).append(i)
        if label in ("net profit", "net profit +", "net profit / loss", "profit after tax"):
            labels.setdefault("net_profit", []).append(i)
        if label in ("eps", "eps in rs", "eps in rs.", "eps in ₹", "eps (rs.)"):
            labels.setdefault("eps", []).append(i)
    if len(labels.get("revenue", [])) != 1:
        raise ValueError("Exactly one Sales/Revenue row required")
    if len(labels.get("eps", [])) > 1 or len(labels.get("net_profit", [])) > 1:
        raise ValueError("Ambiguous EPS or Net profit row")
    if len(labels.get("net_profit", [])) != 1:
        raise ValueError("Exactly one Net profit row required")
    rows = []
    for col, date in dates:
        revenue = _number(raw.iat[labels["revenue"][0], col])
        eps_cell = raw.iat[labels["eps"][0], col] if labels.get("eps") else None
        # Formula cells without cached values are NaN; never infer EPS from PAT.
        eps = None if eps_cell is None or pd.isna(eps_cell) or str(eps_cell).lstrip().startswith("=") else _number(eps_cell)
        pat = _number(raw.iat[labels["net_profit"][0], col]) if labels.get("net_profit") else None
        if revenue < 0:
            raise ValueError("Quarterly revenue cannot be negative")
        rows.append({"quarter_end": date, "revenue": revenue, "eps": eps, "net_profit": pat})
    rows.sort(key=lambda row: row["quarter_end"])
    for previous, current in zip(rows, rows[1:]):
        if pd.Timestamp(current["quarter_end"]) != pd.Timestamp(previous["quarter_end"]) + pd.offsets.QuarterEnd(1):
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
        values = [r.get(key) for r in rows]
        if any(v is None for v in values[-7:]):
            metrics[key] = {"qoq_growth_pct": [], "yoy_growth_pct": [],
                            "qoq_accelerating": False, "yoy_accelerating": False,
                            "available": False}
            continue
        values = [float(v) for v in values]
        qoq = [_growth(values[i], values[i - 1]) for i in range(len(values) - 3, len(values))]
        yoy = [_growth(values[i], values[i - 4]) for i in range(len(values) - 3, len(values))]
        metrics[key] = {"qoq_growth_pct": qoq, "yoy_growth_pct": yoy,
                        "qoq_accelerating": all(x is not None for x in qoq) and qoq[0] < qoq[1] < qoq[2],
                        "yoy_accelerating": all(x is not None for x in yoy) and yoy[0] < yoy[1] < yoy[2],
                        "available": True}
    if not metrics["eps"]["available"]:
        status = "REVIEW_MISSING_EPS"
    elif any(None in metrics[key][kind] for key in metrics for kind in ("qoq_growth_pct", "yoy_growth_pct")):
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
    query(PAT_SQL)
    stamp = datetime.now(timezone.utc).isoformat()
    for row in rows:
        query("""INSERT INTO edge_screener_quarter_pat
                 (owner_id,symbol,quarter_end,revenue,net_profit,source,imported_utc)
                 VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner_id,symbol,quarter_end)
                 DO UPDATE SET revenue=excluded.revenue,net_profit=excluded.net_profit,
                   source=excluded.source,imported_utc=excluded.imported_utc""",
              (owner, symbol, row["quarter_end"], row["revenue"],
               row.get("net_profit"), "SCREENER_MANUAL_EXCEL", stamp))
        if row["eps"] is None:
            query("DELETE FROM edge_screener_quarters WHERE owner_id=? AND symbol=? AND quarter_end=?",
                  (owner, symbol, row["quarter_end"]))
        else:
            query("""INSERT INTO edge_screener_quarters
                     (owner_id,symbol,quarter_end,revenue,eps,source,imported_utc)
                     VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner_id,symbol,quarter_end)
                     DO UPDATE SET revenue=excluded.revenue,eps=excluded.eps,
                       source=excluded.source,imported_utc=excluded.imported_utc""",
                  (owner, symbol, row["quarter_end"], row["revenue"], row["eps"],
                   "SCREENER_MANUAL_EXCEL", stamp))
    query("""INSERT INTO edge_fundamental_acceleration
             (owner_id,symbol,latest_quarter,status,metrics_json,updated_utc)
             VALUES(?,?,?,?,?,?) ON CONFLICT(owner_id,symbol) DO UPDATE SET
             latest_quarter=excluded.latest_quarter,status=excluded.status,
             metrics_json=excluded.metrics_json,updated_utc=excluded.updated_utc""",
          (owner, symbol, rows[-1]["quarter_end"], result["status"],
           json.dumps(result["metrics"], allow_nan=False), stamp))
    return {"symbol": symbol, "quarters": len(rows), **result}


def import_directory(directory, owner, *, query=d1_query, sheet=None, dry_run=False):
    """Import each xlsx independently, continuing after errors."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("Import directory does not exist")
    paths = sorted(p for p in directory.iterdir()
                   if p.is_file() and p.suffix.lower() == ".xlsx"
                   and not p.name.startswith("~$"))
    if not paths:
        raise ValueError("No .xlsx files found in import directory")
    report = {"total": len(paths), "imported": 0, "failed": 0, "results": []}
    for path in paths:
        symbol = path.stem.upper()
        try:
            if not SYMBOL.fullmatch(symbol):
                raise ValueError("Filename is not a valid NSE symbol")
            result = import_workbook(path, symbol, owner, query=query,
                                     sheet=sheet, dry_run=dry_run)
            report["imported"] += 1
            report["results"].append({"file": path.name, "status": "OK",
                                      "gate": result["status"], "quarters": result["quarters"]})
        except Exception as exc:
            report["failed"] += 1
            report["results"].append({"file": path.name, "status": "FAILED",
                                      "error_type": type(exc).__name__,
                                      "error": str(exc) if isinstance(exc, (ValueError, OSError)) else "Import failed; check D1 connectivity"})
    return report


def main():
    parser = argparse.ArgumentParser(description="Import private Screener quarterly Excel into EDGE D1")
    parser.add_argument("excel", nargs="?")
    parser.add_argument("--dir", dest="directory", help="Folder containing symbol-named .xlsx files")
    parser.add_argument("--symbol", help="Required for single workbook only")
    parser.add_argument("--owner-id", required=True, help="Existing authenticated EDGE owner hash")
    parser.add_argument("--sheet")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if bool(args.directory) == bool(args.excel):
        parser.error("Specify exactly one of --dir or an Excel workbook")
    if args.directory:
        if args.symbol:
            parser.error("--symbol cannot be combined with --dir")
        report = import_directory(args.directory, args.owner_id, sheet=args.sheet, dry_run=args.dry_run)
    else:
        if not args.symbol:
            parser.error("--symbol is required for single workbook import")
        report = import_workbook(args.excel, args.symbol.strip().upper(), args.owner_id,
                                 sheet=args.sheet, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    if args.directory and report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
