"""Publish a validated EDGE research snapshot to its own D1 database.

No original SPERA source credentials are accessed. Re-running a snapshot is idempotent.
"""
import hashlib
import json
from pathlib import Path
import pandas as pd
from edge_core.d1_store import d1_query
from edge_core.snapshot_integrity import validate_snapshot

def publish(path="data/latest", query=d1_query):
    root=Path(path)
    validate_snapshot(root)
    raw=(root/"leadership.csv").read_bytes()
    meta=json.loads((root/"metadata.json").read_text())
    
    if meta.get("certified") is not False:
        raise ValueError("EDGE snapshot metadata contract invalid")
        
    df=pd.read_csv(root/"leadership.csv").where(lambda x: pd.notna(x),None)
    if len(df)!=int(meta["expected"]) or "Symbol" not in df or "Data_Quality" not in df:
        raise ValueError("EDGE research identity contract invalid")
    if df["Symbol"].isna().any() or df["Symbol"].duplicated().any():
        raise ValueError("EDGE research symbol identity invalid")
    if not df["Data_Quality"].isin(("PASS","REVIEW","FAIL")).all():
        raise ValueError("EDGE research quality invalid")
    if df["Data_Quality"].eq("PASS").any():
        raise ValueError("Uncertified research cannot contain trusted PASS rows")
        
    digest=hashlib.sha256(raw).hexdigest()
    run_id="edge-"+digest[:32]
    rows=[]
    for rec in df.to_dict("records"):
        clean={k:(None if pd.isna(v) else v) for k,v in rec.items()}
        rank=clean.get("Pure_Momentum_Rank")
        rows.append((run_id,str(clean["Symbol"]),str(clean["Data_Quality"]),
                     int(rank) if rank is not None else None,
                     json.dumps(clean,allow_nan=False,default=str)))
                     
    existing=query("SELECT run_id, rows_count FROM edge_snapshot_runs WHERE run_id=?", (run_id,))
    if existing and int(existing[0]["rows_count"])==len(df):
        count=query("SELECT COUNT(*) AS n FROM edge_leadership WHERE run_id=?", (run_id,))
        if count and int(count[0]["n"])==len(df):
            return {"run_id":run_id,"rows":len(df),"already_published":True}
            
    query("""INSERT INTO edge_snapshot_runs
    (run_id,universe_id,weekly_key,source,quality,is_certified,rows_count,generated_utc,source_hash,metadata_json)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(run_id) DO UPDATE SET metadata_json=excluded.metadata_json""",
    (run_id, str(meta["universe"]), str(meta["last_session"]), str(meta["source"]), "REVIEW", 0,
     len(df), str(meta["generated_utc"]), digest, json.dumps(meta,allow_nan=False,default=str)))
     
    for row in rows:
        query("""INSERT INTO edge_leadership (run_id,symbol,data_quality,momentum_rank,source_row_json)
        VALUES (?,?,?,?,?)
        ON CONFLICT(run_id,symbol) DO UPDATE SET
        data_quality=excluded.data_quality,momentum_rank=excluded.momentum_rank,
        source_row_json=excluded.source_row_json""",row)
        
    result=query("SELECT COUNT(*) AS n FROM edge_leadership WHERE run_id=?", (run_id,))
    if not result or int(result[0]["n"])!=len(df):
        raise RuntimeError("D1 EDGE leadership row verification failed")
    return {"run_id":run_id,"rows":len(df),"already_published":False}

if __name__=="__main__":
    print(json.dumps(publish(),indent=2))
