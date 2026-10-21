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
    for row in mapping.itertuples(index=False):
        symbol=row.Symbol
        try:
            frame=fetcher(row.instrument_key,start,end,token=token)
            if frame.empty or len(frame)<253:
                raise ValueError("Insufficient historical sessions")
            frame=frame.sort_index()
            for name in fields:
                fields[name][symbol]=frame[name]
        except Exception as exc:
            failures.append({"symbol":symbol,"error":type(exc).__name__})
    if failures:
        raise RuntimeError(f"Historical coverage incomplete: {len(failures)}/500 symbols; refusing publication")
    matrices={}
    for name,series in fields.items():
        matrices[name]=pd.DataFrame(series).sort_index()
    close=matrices["close"]
    volume=matrices["volume"].reindex(close.index)
    # This pipeline intentionally requires 253 common sessions across the entire universe.
    # Individual provider gaps fail closed rather than distorting point-in-time breadth.
    if len(close)<253 or close.tail(253).isna().any().any() or volume.tail(253).isna().any().any():
        raise RuntimeError("Insufficient common price and volume sessions; refusing publication")
    research,breadth=derive_research(close,volume)
    if len(research)!=500 or research["Data_Quality"].eq("FAIL").any():
        raise RuntimeError("Research quality/coverage gate failed")
    destination=Path(outdir)
    destination.mkdir(parents=True,exist_ok=True)
    research.to_csv(destination/"leadership.csv",index=False)
    # Store recent OHLCV for chart inspection; do not expose provider secrets.
    for name,frame in matrices.items():
        frame.tail(253).to_csv(destination/f"{name}.csv",index_label="Date")
    metadata={
        "universe":"NIFTY_500","expected":500,"mapped":500,
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
