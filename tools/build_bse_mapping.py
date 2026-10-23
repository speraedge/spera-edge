"""Authoritative BSE scrip mapping; never infer codes from ticker spelling.

The ListofScripData response must explicitly carry both NSE symbol and BSE code.
Ambiguous, duplicate, or missing identities are excluded (fail closed).
"""
import json
import re
from pathlib import Path
import pandas as pd
from edge_fundamentals import RateLimitedSession

ENDPOINT = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
CODE = re.compile(r"^[0-9]{5,7}$")
SYMBOL = re.compile(r"^[A-Z0-9.&-]+$")


def extract_mapping(payload, official_symbols):
    if isinstance(payload, dict):
        records = next((payload[k] for k in ("Table", "Table1", "data", "Data")
                        if isinstance(payload.get(k), list)), None)
    elif isinstance(payload, list):
        records = payload
    else:
        records = None
    if records is None:
        raise ValueError("BSE mapping schema unavailable")
    official = set(official_symbols)
    found = {}
    ambiguous = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("NSESymbol") or item.get("NSE_SYMBOL") or item.get("NSECode") or "").strip().upper()
        code = str(item.get("SCRIP_CD") or item.get("ScripCode") or item.get("scripcode") or "").strip()
        if symbol not in official or not SYMBOL.fullmatch(symbol) or not CODE.fullmatch(code):
            continue
        if symbol in found and found[symbol] != code:
            ambiguous.add(symbol)
        found[symbol] = code
    for symbol in ambiguous:
        found.pop(symbol, None)
    return found


def run(membership="data/latest/current_membership.csv",
        output="data/latest/bse_mapping.csv", client=None):
    official = pd.read_csv(membership, dtype=str)["Symbol"].tolist()
    client = client or RateLimitedSession()
    payload = client.get_json(ENDPOINT, {})
    mapping = extract_mapping(payload, official)
    if not mapping:
        raise ValueError("No verified NSE-to-BSE identities; refusing empty mapping replacement")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".csv.tmp")
    pd.DataFrame([{"Symbol": k, "BSE_Scripcode": v} for k, v in sorted(mapping.items())]).to_csv(temp, index=False)
    temp.replace(target)
    print(json.dumps({"verified_mappings": len(mapping), "unmapped": len(official)-len(mapping)}))
    return mapping


if __name__ == "__main__":
    run()
