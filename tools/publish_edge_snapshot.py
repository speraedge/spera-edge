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
    expected=len(mapping)
    missing=mapping.loc[mapping["Mapping_Status"].ne("MAPPED"),["Symbol","ISIN"]].to_dict("records")
    if not (495<=expected<=505):
        raise RuntimeError(f"Official NIFTY 500 count outside safe range: {expected}")
    # Preserve official source rows, but explicitly distinguish the known NSE
    # placeholder from a genuine provider-mapping failure. Never synthesize prices.
    known_placeholder = {"Symbol": "DUMMYHEG", "ISIN": "DUM545A01024"}
    placeholders = [row for row in missing if row == known_placeholder]
    unresolved_identities = [row for row in missing if row != known_placeholder]
    if missing:
        print(json.dumps({"official_count":expected,"mapped":expected-len(missing),
                          "official_placeholders":placeholders,
                          "unresolved_identities":unresolved_identities},indent=2))
    # Original SPERA audit verified 501 constituents and one provider failure.
    if expected-len(missing)<495:
        raise RuntimeError("NIFTY 500 mapped identity coverage below safe threshold")
    mapping_ok=mapping.loc[mapping["Mapping_Status"].eq("MAPPED")]
    end=date.today()
    start=end-timedelta(days=490)
    fields={name:{} for name in ("open","close","high","low","volume")}
    failures=[]
    successful=0
    for row in mapping_ok.itertuples(index=False):
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
    if successful<495:
        raise RuntimeError(f"Only {successful}/{expected} symbols retrieved; minimum safe coverage is 495")
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
    if len(research)!=successful:
        raise RuntimeError("Research retrieved-universe coverage gate failed")
    import tempfile, shutil
    from edge_core.snapshot_integrity import validate_snapshot
    destination=Path(outdir)
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.edge-snapshot-',dir=destination.parent))
    # Preserve the official universe even when a provider symbol is missing.
    missing=[symbol for symbol in mapping["Symbol"] if symbol not in fields["close"]]
    if missing:
        import numpy as np
        extra=pd.DataFrame({"Symbol":missing,"Data_Quality":"FAIL","Reason":"Upstox historical retrieval unavailable",
                            "Ret_6M":np.nan,"Ret_12M":np.nan,"AnnVol":np.nan})
        research=pd.concat([research,extra],ignore_index=True)
    if len(research)!=expected or research["Symbol"].isna().any() or research["Symbol"].duplicated().any():
        raise RuntimeError("Research universe identity gate failed")
    research.to_csv(staging/"leadership.csv",index=False)
    # Store recent OHLCV for chart inspection; do not expose provider secrets.
    for name,frame in matrices.items():
        frame.tail(253).to_csv(staging/f"{name}.csv",index_label="Date")
    metadata={
        "universe":"NIFTY_500","expected":expected,"mapped":len(mapping_ok),
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
    # Keep raw provider OHLCV available for diagnostics if validation fails.
    # This directory is diagnostic-only; never publish it to the trusted snapshot.
    diagnostic = destination.parent / "phase2-open-diagnostic"
    diagnostic.mkdir(parents=True, exist_ok=True)
    for name in ("open.csv", "close.csv", "metadata.json"):
        shutil.copy2(staging / name, diagnostic / name)
    opened = matrices["open"].tail(253)
    closed = matrices["close"].tail(253)
    missing_open = closed.notna() & opened.isna()
    missing_close = opened.notna() & closed.isna()
    rows = []
    for direction, mask in (("close_without_open", missing_open), ("open_without_close", missing_close)):
        for session, symbol in zip(*__import__("numpy").where(mask.to_numpy())):
            rows.append({"direction": direction, "session": str(mask.index[session]),
                         "symbol": str(mask.columns[symbol]),
                         "open": opened.iat[session, symbol], "close": closed.iat[session, symbol]})
    pd.DataFrame(rows, columns=["direction", "session", "symbol", "open", "close"]).to_csv(
        diagnostic / "open_close_mismatches.csv", index=False)
    print("PHASE2_OPEN_DIAGNOSTIC:", json.dumps({
        "close_without_open": int(missing_open.to_numpy().sum()),
        "open_without_close": int(missing_close.to_numpy().sum()),
        "sample": rows[:20]}, default=str))
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
