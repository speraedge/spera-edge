"""Read-only SPERA Wisdom NIFTY 500 historical snapshot bridge.

Reads the original D1 tables with SELECT only. Writes independent EDGE CSVs.
Never changes SPERA Wisdom data or labels historical snapshots as current prices.
"""
import argparse
import base64
import gzip
import json
import os
from pathlib import Path
import pandas as pd
import requests

API="https://api.cloudflare.com/client/v4/accounts/{account}/d1/database/{database}/query"

def query(sql,params=(),*,account=None,database=None,token=None,session=None):
    account=account or os.environ["SPERA_SOURCE_CF_ACCOUNT_ID"]
    database=database or os.environ["SPERA_SOURCE_D1_DATABASE_ID"]
    token=token or os.environ["SPERA_SOURCE_CF_READ_TOKEN"]
    # Hard restriction: no mutation can be sent by this adapter.
    if not sql.lstrip().upper().startswith("SELECT "):
        raise ValueError("Only SELECT statements are permitted")
    r=(session or requests).post(API.format(account=account,database=database),
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
        json={"sql":sql,"params":list(params)},timeout=45)
    r.raise_for_status()
    obj=r.json()
    if not obj.get("success") or not obj.get("result") or not obj["result"][0].get("success"):
        raise RuntimeError("Source D1 read failed")
    return obj["result"][0].get("results",[])

def decode_blob(chunks):
    if not chunks:
        raise ValueError("Missing historical snapshot chunks")
    data=json.loads(gzip.decompress(base64.b64decode("".join(x["data"] for x in chunks))))
    if not isinstance(data,dict) or not {"columns","data"}.issubset(data):
        raise ValueError("Invalid source snapshot encoding")
    return pd.DataFrame(data["data"],columns=data["columns"])

def import_history(outdir="data/history",weeks=7,reader=query):
    rows=reader("SELECT weekly_key, commit_id, meta_json, freshness, source FROM weekly_snapshots WHERE freshness='PASS' AND source='LIVE' ORDER BY weekly_key DESC LIMIT ?",(int(weeks),))
    if not rows:
        raise RuntimeError("No trusted historical NIFTY 500 snapshots available")
    target=Path(outdir)
    target.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for row in rows:
        meta=json.loads(row["meta_json"])
        # Original source trust gates; never upgrade REVIEW or stale legacy PASS.
        trusted=(meta.get("display_state")=="READY"
            and meta.get("snapshot_freshness")=="PASS"
            and meta.get("session_authority")=="PASS"
            and meta.get("corporate_action_authority")=="PASS"
            and meta.get("snapshot_is_expected_session") is True
            and int(meta.get("pass_count") or 0)>0)
        if not trusted:
            continue
        key=row["weekly_key"]
        chunks=reader("SELECT data FROM snapshot_chunks WHERE weekly_key=? AND commit_id=? AND kind='history' ORDER BY seq",(key,row["commit_id"]))
        frame=decode_blob(chunks)
        if frame.empty or "Pure_Momentum_Rank" not in frame:
            continue
        filename=f"nifty500_{key}.csv"
        frame.to_csv(target/filename,index=False)
        manifest.append({"weekly_key":key,"file":filename,"rows":len(frame),
                         "source":"SPERA Wisdom D1 trusted weekly history","historical_only":True})
    if not manifest:
        raise RuntimeError("No source snapshots passed independent trust checks")
    (target/"manifest.json").write_text(json.dumps({"universe":"NIFTY_500","weeks":manifest},indent=2))
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--outdir",default="data/history")
    p.add_argument("--weeks",type=int,default=7)
    args=p.parse_args()
    print(json.dumps(import_history(args.outdir,args.weeks),indent=2))
