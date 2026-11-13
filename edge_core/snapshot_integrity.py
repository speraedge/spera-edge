"""Validate the complete independently generated EDGE snapshot before publication."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
from edge_core.ohlcv_integrity import audit_ohlcv
from edge_core.momentum_universe import NIFTY_500, NIFTY_TOTAL_MARKET

def validate_snapshot(directory="data/latest"):
    root = Path(directory)
    meta = json.loads((root / "metadata.json").read_text())
    universe_id = meta.get("universe", "NIFTY_500")
    spec = NIFTY_TOTAL_MARKET if universe_id == "NIFTY_TOTAL_MARKET" else NIFTY_500
    
    expected = int(meta["expected"])
    mapped = int(meta["mapped"])
    retrieved = int(meta["retrieved"])
    
    if (universe_id not in ("NIFTY_500", "NIFTY_TOTAL_MARKET") or meta.get("certified") is not False
            or not spec.min_count <= expected <= spec.max_count 
            or not spec.min_count <= mapped <= expected
            or not spec.min_count <= retrieved <= mapped):
        raise ValueError(f"Invalid {spec.display_name} snapshot coverage or certification contract")
        
    if "official_placeholders" in meta or "unresolved_identities" in meta:
        placeholders = meta.get("official_placeholders", [])
        unresolved = meta.get("unresolved_identities", [])
        if not isinstance(placeholders, list) or not isinstance(unresolved, list):
            raise ValueError("Invalid unmapped-identity metadata")
        all_missing = placeholders + unresolved
        symbols = [row.get("Symbol") for row in all_missing if isinstance(row, dict)]
        if (len(symbols) != len(all_missing) or any(not x for x in symbols)
                or len(set(symbols)) != len(symbols)
                or mapped + len(all_missing) != expected):
            raise ValueError("Unmapped identities do not reconcile with universe coverage")
            
        # Relaxed policy check: any ISIN starting with DUM is a valid placeholder
        if any(not str(row.get("ISIN", "")).startswith("DUM") for row in placeholders):
            raise ValueError("Unknown identity incorrectly classified as official placeholder")
            
    failures = meta.get("retrieval_failures", [])
    if (not isinstance(failures, list) or retrieved + len(failures) != mapped):
        raise ValueError("Retrieved and failed provider histories do not reconcile")
    ranks = pd.read_csv(root / "leadership.csv")
    if (len(ranks) != expected or not {"Symbol","Data_Quality"}.issubset(ranks.columns)
            or ranks["Symbol"].isna().any() or ranks["Symbol"].duplicated().any()
            or not ranks["Data_Quality"].isin(["PASS","REVIEW","FAIL"]).all()
            or ranks["Data_Quality"].eq("PASS").any()):
        raise ValueError("Invalid uncertified leadership research identities or quality")
        
    for quality in ("pass","review","fail"):
        if int(meta["research_" + quality]) != int(ranks["Data_Quality"].eq(quality.upper()).sum()):
            raise ValueError("Research quality counts do not match metadata")
            
    frames = {}
    for name in ("close","high","low","volume"):
        df = pd.read_csv(root / (name + ".csv"), index_col="Date")
        if df.index.has_duplicates or df.columns.has_duplicates or len(df) < 200:
            raise ValueError("Invalid OHLCV sessions or columns: " + name)
        frames[name] = df
    open_path = root / "open.csv"
    if not open_path.is_file():
        raise ValueError("Required open.csv missing from snapshot")
    opened = pd.read_csv(open_path, index_col="Date")
    
    if (not opened.index.equals(frames["close"].index)
            or not opened.columns.equals(frames["close"].columns)
            or (opened.notna() != frames["close"].notna()).any().any()):
        raise ValueError("Opening price alignment or completeness failure")
    numeric_open = opened.apply(pd.to_numeric, errors="coerce")
    
    if ((opened.notna() & numeric_open.isna()).any().any()
            or (numeric_open.notna() & ~pd.DataFrame(np.isfinite(numeric_open.to_numpy(dtype=float)), index=opened.index, columns=opened.columns)).any().any()
            or (numeric_open.notna() & (numeric_open <= 0)).any().any()):
        raise ValueError("Invalid observed opening price")
    if ((numeric_open > frames["high"]) | (numeric_open < frames["low"])).any().any():
        raise ValueError("Opening prices outside observed candle range")
        
    close = frames["close"]
    if len(close.columns) != retrieved:
        raise ValueError("Retrieved symbol count does not match close columns")
    for name, df in frames.items():
        if not df.index.equals(close.index) or not df.columns.equals(close.columns):
            raise ValueError("OHLCV alignment mismatch: " + name)
            
    if str(pd.Timestamp(close.index.max()).date()) != str(pd.Timestamp(meta["last_session"]).date()):
        raise ValueError("Snapshot session does not match price data")
    audit_ohlcv(frames["close"], frames["high"], frames["low"], frames["volume"],
                expected_last_session=meta["last_session"])
                
    if not set(close.columns).issubset(set(ranks["Symbol"])):
        raise ValueError("OHLCV symbols absent from leadership")
    return {"expected":expected,"retrieved":retrieved,"rows":len(ranks),"sessions":len(close)}
