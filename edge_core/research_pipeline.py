"""Derive research-only cross-sectional momentum inputs from aligned OHLCV."""
import numpy as np
import pandas as pd
from edge_core.momentum_v1 import apply_frozen_v1_scores
from edge_core.analytics import stage2_template, market_breadth

def derive_research(close, volume, minimum_history=253):
    """Fail closed on missing sessions; do not claim adjusted prices or trusted PASS."""
    if not isinstance(close,pd.DataFrame) or close.empty or not close.index.equals(volume.index):
        raise ValueError("Close and volume need a common, nonempty date index.")
    if not close.columns.equals(volume.columns) or close.index.has_duplicates:
        raise ValueError("Prices must have identical symbol columns and unique sessions.")
    if not close.index.is_monotonic_increasing:
        raise ValueError("Dates must be sorted.")
    records=[]
    for symbol in close.columns:
        s=pd.to_numeric(close[symbol],errors="coerce")
        v=pd.to_numeric(volume[symbol],errors="coerce")
        good=(s.notna() & v.notna() & (s>0) & (v>=0))
        if len(s)<minimum_history or not good.iloc[-minimum_history:].all():
            records.append({"Symbol":symbol,"Data_Quality":"FAIL","Reason":"Missing or insufficient aligned sessions",
                            "Ret_6M":np.nan,"Ret_12M":np.nan,"AnnVol":np.nan})
            continue
        s=s.iloc[-minimum_history:]
        returns=np.log(s/s.shift(1)).dropna()
        vol=float(returns.std(ddof=1)*np.sqrt(252))
        records.append({"Symbol":symbol,"Data_Quality":"REVIEW","Reason":"Corporate actions, membership and source integrity unverified",
                        "Ret_6M":float(s.iloc[-1]/s.iloc[-127]-1),
                        "Ret_12M":float(s.iloc[-1]/s.iloc[-253]-1),
                        "AnnVol":vol if np.isfinite(vol) and vol>0 else np.nan,
                        "Price_Trend_Template":stage2_template(s)["eligible"]})
    research=pd.DataFrame.from_records(records)
    if len(research)>1:
        research=apply_frozen_v1_scores(research)
    return research,market_breadth(close)
