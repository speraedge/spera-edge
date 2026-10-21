"""Benchmark-relative strength from aligned daily closes; research only."""
import numpy as np
import pandas as pd

def relative_strength(stock_close, benchmark_close, lookbacks=(63,126,252)):
    stock=pd.to_numeric(stock_close,errors="coerce")
    benchmark=pd.to_numeric(benchmark_close,errors="coerce")
    aligned=pd.concat([stock.rename("stock"),benchmark.rename("benchmark")],axis=1).dropna().sort_index()
    if aligned.index.has_duplicates or (aligned<=0).any().any():
        raise ValueError("Invalid or duplicated benchmark/stock sessions")
    result={}
    for n in lookbacks:
        if len(aligned)<=n:
            result[f"RS_{n}D"]=np.nan
            continue
        a=aligned.iloc[-1]
        b=aligned.iloc[-n-1]
        result[f"RS_{n}D"]=float(a["stock"]/b["stock"]-a["benchmark"]/b["benchmark"])
    result["RS_Evidence"]="COMPUTED_ALIGNED" if all(np.isfinite(v) for v in result.values()) else "INSUFFICIENT_HISTORY"
    return result
