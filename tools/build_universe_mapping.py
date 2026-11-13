"""Publish an isolated identity audit artifact; no secrets and no production writes."""
import json
from pathlib import Path
from datetime import datetime,timezone
from edge_core.momentum_universe import NIFTY_500, NIFTY_TOTAL_MARKET, fetch_official_universe
from edge_core.instrument_mapping import fetch_upstox_instruments,join_official_universe

def main():
    out=Path("snapshot")
    out.mkdir(exist_ok=True)
    report={"generated_utc":datetime.now(timezone.utc).isoformat(),"universes":{}}
    instruments=fetch_upstox_instruments()
    for spec in (NIFTY_500, NIFTY_TOTAL_MARKET):
        try:
            universe,_=fetch_official_universe(spec,attempts_per_url=1)
            joined=join_official_universe(universe,instruments)
            path=out/(spec.universe_id.lower()+"_mapping.csv")
            joined.to_csv(path,index=False)
            mapped=int(joined["Mapping_Status"].eq("MAPPED").sum())
            report["universes"][spec.universe_id]={
                "count":len(joined),"mapped":mapped,"missing":len(joined)-mapped,
                "constituent_count_status":universe.attrs["universe_count_status"],
                "source":universe.attrs.get("universe_source_url"),
                "research_only":True
            }
        except Exception as exc:
            report["universes"][spec.universe_id]={"status":"FAILED","error_type":type(exc).__name__}
    (out/"mapping_audit.json").write_text(json.dumps(report,indent=2))
    if any(x.get("status")=="FAILED" for x in report["universes"].values()):
        raise RuntimeError("Official identity audit failed; see artifact.")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
