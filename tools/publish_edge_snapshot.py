"""Publish NIFTY 500 or Total Market research snapshots independently of SPERA production.

Only a complete, identity-validated mapping is accepted. No trusted PASS labels.
"""
import json
import logging
import os
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
import pandas as pd
from edge_core.momentum_universe import NIFTY_500, NIFTY_TOTAL_MARKET, fetch_official_universe
from edge_core.instrument_mapping import fetch_upstox_instruments,join_official_universe
from edge_core.upstox import fetch_daily_candles
from edge_core.research_pipeline import derive_research
from edge_core.ohlcv_integrity import VERIFIED_SPECIAL_SESSIONS

def drop_unverified_weekend_rows(frame, *, symbol=None):
    """Discard only unverified weekend dates from provider history."""
    if frame.empty:
        return frame
    sessions = pd.to_datetime(frame.index, errors="raise")
    rejected = [i for i, session in enumerate(sessions)
                if session.dayofweek >= 5
                and session.date().isoformat() not in VERIFIED_SPECIAL_SESSIONS]
    if rejected:
        dates = sorted({sessions[i].date().isoformat() for i in rejected})
        logging.warning("UPSTOX_UNVERIFIED_WEEKEND_ROWS_DROPPED symbol=%s count=%d dates=%s",
                        symbol or "UNKNOWN", len(rejected), ",".join(dates))
        return frame.iloc[[i for i in range(len(frame)) if i not in set(rejected)]]
    return frame


def build(outdir="data/latest",token=None,fetcher=fetch_daily_candles,universe=None,instruments=None):
    token=token or os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_ANALYTIC_TOKEN")
    if not token:
        raise RuntimeError("Upstox token missing; refusing to publish")
        
    universe_id = os.getenv("EDGE_UNIVERSE", "NIFTY_500")
    spec = NIFTY_TOTAL_MARKET if universe_id == "NIFTY_TOTAL_MARKET" else NIFTY_500
    
    if universe is None:
        universe,_=fetch_official_universe(spec,attempts_per_url=2)
    if instruments is None:
        instruments=fetch_upstox_instruments()
    mapping=join_official_universe(universe,instruments)
    expected=len(mapping)
    missing=mapping.loc[mapping["Mapping_Status"].ne("MAPPED"),["Symbol","ISIN"]].to_dict("records")
    
    if not (spec.min_count <= expected <= spec.max_count):
        raise RuntimeError(f"Official {spec.display_name} count outside safe range: {expected}")
        
    # Policy check for placeholders (any ISIN starting with DUM)
    placeholders = [row for row in missing if str(row.get("ISIN", "")).startswith("DUM")]
    unresolved_identities = [row for row in missing if not str(row.get("ISIN", "")).startswith("DUM")]
    
    if missing:
        print(json.dumps({"official_count":expected,"mapped":expected-len(missing),
                          "official_placeholders":placeholders,
                          "unresolved_identities":unresolved_identities},indent=2))
                          
    if expected-len(missing) < spec.mapped_min_count:
        raise RuntimeError(f"{spec.display_name} mapped identity coverage below safe threshold")
        
    mapping_ok=mapping.loc[mapping["Mapping_Status"].eq("MAPPED")]
    end=date.today()
    start=end-timedelta(days=800)
    fields={name:{} for name in ("open","close","high","low","volume")}
    failures=[]
    successful=0
    for row in mapping_ok.itertuples(index=False):
        symbol=row.Symbol
        try:
            frame=fetcher(row.instrument_key,start,end,token=token)
            if frame.empty:
                raise ValueError("No historical sessions")
            frame=drop_unverified_weekend_rows(frame, symbol=symbol).sort_index()
            if frame.empty:
                raise ValueError("No verified trading sessions after weekend filtering")
            successful+=1
            for name in fields:
                fields[name][symbol]=frame[name]
        except Exception as exc:
            failures.append({"symbol":symbol,"error":type(exc).__name__})
            
    if successful < spec.mapped_min_count:
        raise RuntimeError(f"Only {successful}/{expected} symbols retrieved; minimum safe coverage is {spec.mapped_min_count}")
        
    matrices={}
    for name,series in fields.items():
        matrices[name]=pd.DataFrame(series).sort_index()
    close=matrices["close"]
    volume=matrices["volume"].reindex(close.index)
    
    if len(close)<253:
        raise RuntimeError("Insufficient market calendar history; refusing publication")
    research,breadth=derive_research(close,volume)
    if len(research)!=successful:
        raise RuntimeError("Research retrieved-universe coverage gate failed")
        
    import tempfile, shutil
    from edge_core.snapshot_integrity import validate_snapshot
    destination=Path(outdir)
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.edge-snapshot-',dir=destination.parent))
    
    missing=[symbol for symbol in mapping["Symbol"] if symbol not in fields["close"]]
    if missing:
        import numpy as np
        extra=pd.DataFrame({"Symbol":missing,"Data_Quality":"FAIL","Reason":"Upstox historical retrieval unavailable",
                            "Ret_6M":np.nan,"Ret_12M":np.nan,"AnnVol":np.nan})
        research=pd.concat([research,extra],ignore_index=True)
        
    if len(research)!=expected or research["Symbol"].isna().any() or research["Symbol"].duplicated().any():
        raise RuntimeError("Research universe identity gate failed")
        
    research.to_csv(staging/"leadership.csv",index=False)
    for name,frame in matrices.items():
        frame.tail(500).to_csv(staging/f"{name}.csv",index_label="Date")
        
    metadata={
        "universe":spec.universe_id,"expected":expected,"mapped":len(mapping_ok),
        "retrieved":successful,"retrieval_failures":failures,
        "official_placeholders":placeholders,
        "unresolved_identities":unresolved_identities,
        "research_pass":int(research["Data_Quality"].eq("PASS").sum()),
        "research_review":int(research["Data_Quality"].eq("REVIEW").sum()),
        "research_fail":int(research["Data_Quality"].eq("FAIL").sum()),
        "last_session":str(close.index.max()),
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "source":"Upstox historical candles + official NSE constituent identities",
        "quality":"REVIEW_UNVERIFIED_CORPORATE_ACTIONS",
        "certified":False,"breadth":breadth
    }
    (staging/"metadata.json").write_text(json.dumps(metadata,indent=2))
    
    try:
        validate_snapshot(staging)
        latest = pd.Timestamp(metadata["last_session"]).date()
        if (end - latest).days > 5:
            raise RuntimeError("Provider snapshot stale; preserving last-known-good")
        destination.mkdir(parents=True,exist_ok=True)
        for name in ("leadership.csv","open.csv","close.csv","high.csv","low.csv","volume.csv"):
            os.replace(staging/name,destination/name)
        os.replace(staging/"metadata.json",destination/"metadata.json")
    finally:
        shutil.rmtree(staging,ignore_errors=True)
    return metadata

if __name__=="__main__":
    print(json.dumps(build(),indent=2))
