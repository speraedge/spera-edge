"""Best-effort public NSE/BSE fundamentals acquisition; never reads private D1.

Exchange APIs change and may rate-limit automated clients. Missing/unverified
fields remain blank; no synthetic financials or cross-quarter substitutions.
"""
import json
import re
import time
from pathlib import Path
import requests
import pandas as pd
from edge_core.fundamentals_privacy import COLUMNS, publish_public_csv

NSE = "https://www.nseindia.com/api/quote-equity"
BSE = "https://api.bseindia.com/BseIndiaAPI/api/ComHeader/w"
BSE_RESULTS = "https://api.bseindia.com/BseIndiaAPI/api/CompResults/w"
SYMBOL_RE = re.compile(r"^[A-Z0-9.\-&]+$")


class RateLimitedSession:
    def __init__(self, session=None, sleep=time.sleep, clock=time.monotonic):
        self.session = session or requests.Session()
        self.sleep, self.clock, self.last = sleep, clock, None
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SPERA-EDGE-research/1.0)",
                                     "Accept": "application/json", "Referer": "https://www.nseindia.com/"})

    def get_json(self, url, params):
        now = self.clock()
        if self.last is not None:
            delay = 1.0 - (now - self.last)
            if delay > 0:
                self.sleep(delay)
        self.last = self.clock()
        response = self.session.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()


def _number(value):
    if value in (None, "", "-", "NA", "N/A"):
        return ""
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return ""


def _nse(symbol, client):
    data = client.get_json(NSE, {"symbol": symbol})
    # Only explicit NSE quote fields. Quarterly revenue/PAT/EPS are not
    # inferred from annual, TTM or unrelated fields.
    metadata = data.get("metadata") or {}
    details = data.get("priceInfo") or {}
    fundamentals = data.get("securityInfo") or {}
    pe = _number(metadata.get("pdSymbolPe") or metadata.get("pdSectorPe"))
    # Sector PE is NOT stock PE: do not use it.
    pe = _number(metadata.get("pdSymbolPe"))
    cap = _number(fundamentals.get("marketCap"))
    if not pe and not cap:
        raise ValueError("NSE quote lacks independently identified company fundamentals")
    return {"PE": pe, "Market_Cap": cap, "Source": "NSE"}


def _bse(symbol, client, scrip_code=None):
    # BSE ComHeader requires a verified BSE numeric scrip code, never an
    # NSE ticker guessed into a code. Skip unless an authoritative mapping exists.
    if not scrip_code or not str(scrip_code).isdigit():
        raise ValueError("No verified BSE scrip code")
    data = client.get_json(BSE, {"quotetype": "EQ", "scripcode": str(scrip_code), "seriesid": ""})
    if not isinstance(data, dict):
        raise ValueError("Unexpected BSE response")
    pe = _number(data.get("PE"))
    cap = _number(data.get("MktCap") or data.get("MarketCap"))
    if not pe and not cap:
        raise ValueError("BSE quote lacks independently identified company fundamentals")
    return {"PE": pe, "Market_Cap": cap, "Source": "BSE"}



def _quarter_result(scrip_code, client):
    """Fail closed on unknown BSE result schemas; no annual or TTM substitutes."""
    if not scrip_code or not str(scrip_code).isdigit():
        raise ValueError("Verified BSE scripcode required")
    payload = client.get_json(BSE_RESULTS, {"scripcode": str(scrip_code)})
    if not isinstance(payload, dict):
        raise ValueError("Unknown quarterly result schema")
    rows = next((payload[k] for k in ("Table", "Table1", "data")
                 if isinstance(payload.get(k), list)), None)
    if not rows:
        raise ValueError("No quarterly results")
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        period = str(row.get("QuarterEnd") or row.get("Quarter_End") or "").strip()
        basis = str(row.get("PeriodType") or row.get("Period_Type") or "").strip().upper()
        if basis not in ("QUARTER", "QUARTERLY", "Q") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
            continue
        values = {"Quarter_Revenue": _number(row.get("Revenue")),
                  "Quarter_PAT": _number(row.get("PAT")),
                  "Quarter_EPS": _number(row.get("EPS"))}
        if any(value == "" for value in values.values()):
            continue
        candidates.append((period, values))
    if not candidates:
        raise ValueError("Quarterly fields missing or unverified")
    period, values = max(candidates, key=lambda item: item[0])
    return dict(values, Quarter_End=period)


def fetch_one(symbol, client, bse_code=None):
    row = dict.fromkeys(COLUMNS, "")
    row.update(Symbol=symbol, Source="NONE", Status="AUTO_FAILED")
    if not SYMBOL_RE.fullmatch(symbol):
        return row
    for source in (lambda: _nse(symbol, client), lambda: _bse(symbol, client, bse_code)):
        try:
            values = source()
            row.update(values, Status="AUTO")
            break
        except (ValueError, TypeError, KeyError, requests.RequestException, json.JSONDecodeError):
            continue
    try:
        row.update(_quarter_result(bse_code, client))
    except (ValueError, TypeError, KeyError, requests.RequestException, json.JSONDecodeError):
        row = dict.fromkeys(COLUMNS, "")
        row.update(Symbol=symbol, Source="NONE", Status="AUTO_FAILED")
    return row


def run(membership="data/latest/current_membership.csv",
        output="data/latest/fundamentals_auto.csv", client=None,
        mapping_path="data/latest/bse_mapping.csv"):
    frame = pd.read_csv(membership, dtype=str)
    if "Symbol" not in frame or frame["Symbol"].isna().any() or frame["Symbol"].duplicated().any():
        raise ValueError("Unique official symbols required")
    client = client or RateLimitedSession()
    mapping = {}
    if Path(mapping_path).is_file():
        mapped = pd.read_csv(mapping_path, dtype=str)
        if {"Symbol", "BSE_Scripcode"}.issubset(mapped.columns) and not mapped["Symbol"].duplicated().any():
            mapping = dict(zip(mapped["Symbol"], mapped["BSE_Scripcode"]))
    rows = [fetch_one(symbol, client, mapping.get(symbol)) for symbol in frame["Symbol"].tolist()]
    publish_public_csv(rows, output)
    print(json.dumps({"rows": len(rows), "auto": sum(r["Status"] == "AUTO" for r in rows),
                      "auto_failed": sum(r["Status"] == "AUTO_FAILED" for r in rows)}))
    return rows


if __name__ == "__main__":
    run()
