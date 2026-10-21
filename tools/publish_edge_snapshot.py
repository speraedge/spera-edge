"""Publish NIFTY 500 research snapshots independently of SPERA production.

Only a complete, identity-validated mapping is accepted. No trusted PASS labels.
"""
import json
import os
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
import pandas as pd
from edge_core.momentum_universe import NIFTY_500,fetch_official_universe
from edge_core.instrument_mapping import fetch_upstox_instruments,join_official_universe
from edge_core.upstox import fetch_daily_candles
from edge_core.research_pipeline import derive_research

def build(outdir="data/latest",token=None,fetcher=fetch_daily_candles,universe=None,instruments=None):
    token=token or os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_ANALYTIC_TOKEN")
    if not token:
        raise RuntimeError("Upstox token missing; refusing to publish")
    if universe is None:
        universe,_=fetch_official_universe(NIFTY_500,attempts_per_url=2)
    if instruments is None:
        instruments=fetch_upstox_instruments()
    mapping=join_official_universe(universe,instruments)
    if len(mapping)!=500 or not mapping["Mapping_Status"].eq("MAPPED").all():
        raise RuntimeError("NIFTY 500 identity coverage incomplete; refusing to publish")
    end=date.today()
    start=end-timedelta(days=490)
    fields={name:{} for name in ("close","high","low","volume")}
    failures=[]
    successful=0
    for row in mapping.itertuples(index=False):
        symbol=row.Symbol
        try:
            frame=fetcher(row.instrument_key,start,end,token=token)
            if frame.empty:
                raise ValueError("No historical sessions")
            frame=frame.sort_index()
            successful+=1
            for name in fields:
                fields[name][symbol]=frame[name]
        except Exception as exc:
            failures.append({"symbol":symbol,"error":type(exc).__name__})
    if successful<2:
        raise RuntimeError(f"Only {successful}/500 symbols retrieved; refusing publication")
    matrices={}
    for name,series in fields.items():
        matrices[name]=pd.DataFrame(series).sort_index()
    close=matrices["close"]
    volume=matrices["volume"].reindex(close.index)
    # This pipeline intentionally requires 253 common sessions across the entire universe.
    # Individual provider gaps fail closed rather than distorting point-in-time breadth.
    if len(close)<253:
        raise RuntimeError("Insufficient market calendar history; refusing publication")
    research,breadth=derive_research(close,volume)
    if len(research)!=500:
        raise RuntimeError("Research universe coverage gate failed")
    destination=Path(outdir)
    destination.mkdir(parents=True,exist_ok=True)
    # Preserve the official universe even when a provider symbol is missing.
    missing=[symbol for symbol in mapping["Symbol"] if symbol not in fields["close"]]
    if missing:
        import numpy as np
        extra=pd.DataFrame({"Symbol":missing,"Data_Quality":"FAIL","Reason":"Upstox historical retrieval unavailable",
                            "Ret_6M":np.nan,"Ret_12M":np.nan,"AnnVol":np.nan})
        research=pd.concat([research,extra],ignore_index=True)
    if len(research)!=500 or research["Symbol"].duplicated().any():
        raise RuntimeError("Research universe identity gate failed")
    research.to_csv(destination/"leadership.csv",index=False)
    # Store recent OHLCV for chart inspection; do not expose provider secrets.
    for name,frame in matrices.items():
        frame.tail(253).to_csv(destination/f"{name}.csv",index_label="Date")
    metadata={
        "universe":"NIFTY_500","expected":500,"mapped":500,
        "retrieved":successful,"retrieval_failures":failures,
        "research_pass":int(research["Data_Quality"].eq("PASS").sum()),
        "research_review":int(research["Data_Quality"].eq("REVIEW").sum()),
        "research_fail":int(research["Data_Quality"].eq("FAIL").sum()),
        "last_session":str(close.index.max().date()),
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "source":"Upstox historical candles + official NSE constituent identities",
        "quality":"REVIEW_UNVERIFIED_CORPORATE_ACTIONS",
        "certified":False,"breadth":breadth
    }
    (destination/"metadata.json").write_text(json.dumps(metadata,indent=2))
    return metadata

if __name__=="__main__":
    print(json.dumps(build(),indent=2))
