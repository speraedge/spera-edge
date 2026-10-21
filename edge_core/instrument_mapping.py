"""Map official NSE constituent ISINs to Upstox NSE equity instrument keys.

Fail closed on duplicate identities and absent instruments. Does not rank stocks.
"""
import gzip
import io
import json
import requests
import pandas as pd

UPSTOX_NSE_MASTER = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"

def parse_instrument_master(payload):
    if isinstance(payload,bytes):
        if payload[:2] == b"\x1f\x8b":
            payload=gzip.decompress(payload)
        payload=payload.decode("utf-8")
    rows=json.loads(payload) if isinstance(payload,str) else payload
    if not isinstance(rows,list):
        raise ValueError("Upstox instrument master must be a JSON array")
    records=[]
    for row in rows:
        if not isinstance(row,dict) or row.get("segment")!="NSE_EQ":
            continue
        isin=str(row.get("isin") or "").strip().upper()
        key=str(row.get("instrument_key") or "").strip()
        symbol=str(row.get("trading_symbol") or "").strip().upper()
        if isin and key.startswith("NSE_EQ|") and symbol:
            records.append({"ISIN":isin,"instrument_key":key,"trading_symbol":symbol})
    df=pd.DataFrame(records,columns=["ISIN","instrument_key","trading_symbol"])
    if df.empty:
        raise ValueError("No valid NSE equity instrument identities")
    duplicate=df[df.duplicated("ISIN",keep=False)]
    if not duplicate.empty:
        # Ambiguous provider identity cannot be safely resolved by guessing.
        df=df[~df["ISIN"].isin(duplicate["ISIN"])].copy()
    return df

def join_official_universe(universe,instruments):
    if "Symbol" not in universe or "ISIN Code" not in universe:
        raise ValueError("Official NSE universe must include Symbol and ISIN Code")
    base=universe.copy()
    base["ISIN"]=base["ISIN Code"].fillna("").astype(str).str.strip().str.upper()
    if base["ISIN"].eq("").any() or base["ISIN"].duplicated().any():
        raise ValueError("Missing or duplicate official NSE ISIN")
    if instruments["ISIN"].duplicated().any():
        raise ValueError("Duplicate provider ISIN")
    joined=base.merge(instruments,on="ISIN",how="left",validate="one_to_one")
    joined["Mapping_Status"]=joined["instrument_key"].notna().map({True:"MAPPED",False:"MISSING"})
    return joined

def fetch_upstox_instruments(timeout=40):
    response=requests.get(UPSTOX_NSE_MASTER,timeout=timeout)
    response.raise_for_status()
    return parse_instrument_master(response.content)
